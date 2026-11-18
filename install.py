#!/usr/bin/env python3
"""Ubuntu installer with resume support.

Progress is recorded in /tmp/ubuntu-install-script/install.state.
Re-running the script skips steps that already completed successfully
(including steps completed by a previous run that crashed before any
state was saved, via auto-detection where possible).

Pass --reset (or delete the state file) to start over from scratch.
"""
import os
import re
import sys
import json
import subprocess
import shutil
from pathlib import Path

MNT = "/mnt"
STATE_FILE = "/tmp/ubuntu-install-script/install.state"


def run(cmd, check=True, shell=True, capture=False, cwd=None):
    if isinstance(cmd, str):
        result = subprocess.run(cmd, shell=shell, check=check, capture_output=capture, cwd=cwd)
    else:
        result = subprocess.run(cmd, check=check, capture_output=capture, cwd=cwd)
    if capture:
        return result
    return result.returncode == 0


STATE = {}


def load_state():
    global STATE
    STATE = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                STATE = json.load(f)
        except (json.JSONDecodeError, OSError):
            STATE = {}


def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(STATE, f, indent=2)


def mark_done(step_name):
    STATE[step_name] = True
    save_state()


def step(name, fn, skip_check=None):
    """Run fn() unless the step is already recorded as done.

    skip_check() may auto-detect that the step's effect already exists
    (useful when resuming after a crash that happened before state was
    recorded); in that case the step is marked done and skipped.
    """
    if name in STATE or (skip_check and skip_check()):
        if name not in STATE:
            mark_done(name)
        print(f"[*] {name}: already done, skipping")
        return
    print(f"[+] {name}...")
    fn()
    mark_done(name)
    print(f"[OK] {name} completed")


def check_root():
    if os.geteuid() != 0:
        os.execvpe("/usr/bin/sudo", ["sudo"] + sys.argv)


def write_file(path, content):
    full_path = f"{MNT}{path}"
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)


def append_lines_once(path, lines):
    """Append lines to {MNT}{path}, skipping lines already present (idempotent)."""
    full_path = f"{MNT}{path}"
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    existing = set()
    if os.path.exists(full_path):
        with open(full_path) as f:
            existing = {line.strip() for line in f}
    with open(full_path, "a") as f:
        for line in lines:
            if line.strip() not in existing:
                f.write(line + "\n")


def is_mounted(path):
    return run(f"mountpoint -q {path}", check=False)


def mount_chroot_vfs():
    """Bind-mount virtual filesystems into the chroot.

    Without /proc (and friends), package postinst scripts warn heavily and
    tools like flatpak fail outright ("Unable to create repository at
    /var/lib/flatpak/repo"). Also required for cryptroot initramfs hooks to
    detect the root device correctly.
    """
    for src in ("/proc", "/sys", "/dev", "/dev/pts", "/run"):
        dst = f"{MNT}{src}"
        os.makedirs(dst, exist_ok=True)
        if not is_mounted(dst):
            run(f"mount --bind {src} {dst}")


def umount_chroot_vfs():
    for src in ("/run", "/dev/pts", "/dev", "/sys", "/proc"):
        dst = f"{MNT}{src}"
        if is_mounted(dst):
            run(f"umount {dst}", check=False)


def set_localtime():
    """Point /mnt/etc/localtime at America/Belem, idempotently.

    debootstrap/tzdata already creates /etc/localtime inside the target,
    so a blind os.symlink() here used to fail with FileExistsError.
    """
    zone = "/usr/share/zoneinfo/America/Belem"
    localtime = f"{MNT}/etc/localtime"
    if os.path.islink(localtime):
        if os.readlink(localtime) == zone:
            return  # already correct
        os.remove(localtime)
    elif os.path.exists(localtime):
        os.remove(localtime)
    os.symlink(zone, localtime)


def main():
    check_root()

    if "--reset" in sys.argv:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print("Cleared previous state; starting fresh.")
        sys.argv.remove("--reset")

    load_state()
    done_count = len([k for k in STATE if k != "disk"])
    if done_count:
        print(f"Resuming: {done_count} step(s) already completed.")

    DISK = input("Enter disk device (e.g., /dev/sda, /dev/nvme0n1): ").strip()
    FORMAT = input("Format and partition disk? (yes/no; answer 'no' when resuming an install): ").strip().lower()
    BLOCK_SNAPS = input("Block snaps and unwanted packages? (yes/no): ").strip().lower()

    if not os.path.exists(DISK):
        print(f"Error: {DISK} is not a block device")
        sys.exit(1)

    RELEASE = "resolute"
    HOSTNAME = "ubuntu"
    LUKS_PART = f"{DISK}2"
    EFI_PART = f"{DISK}1"

    prev_disk = STATE.get("disk")
    if prev_disk and prev_disk != DISK:
        print(f"Warning: previous run used {prev_disk}; recorded progress may not match {DISK}.")
    STATE["disk"] = DISK
    save_state()

    if FORMAT == "yes":
        def host_packages():
            print("Installing required packages...")
            run("apt update && apt install -y arch-install-scripts debootstrap")
        step("host_packages", host_packages)

        def partition_disk():
            print("Creating partitions...")
            run(f"parted {DISK} mklabel gpt")
            run(f"parted {DISK} mkpart ESP fat32 1MiB 2049MiB set 1 esp on")
            run(f"parted {DISK} mkpart primary 2049MiB 100%")
        step("partition_disk", partition_disk)

        def format_partitions():
            print("Formatting partitions...")
            run(f"mkfs.fat -F 32 {EFI_PART}")
            print("Setting up LUKS encryption...")
            run(f"cryptsetup luksFormat --type luks2 {LUKS_PART}")
        step("format_partitions", format_partitions)

        def btrfs_format():
            if not os.path.exists("/dev/mapper/root"):
                run(f"cryptsetup open {LUKS_PART} root")
            run("mkfs.btrfs /dev/mapper/root")
        step("btrfs_format", btrfs_format)

        def create_subvolumes():
            print("Creating BTRFS subvolumes...")
            run("mount /dev/mapper/root /mnt")
            for name in ("@", "@home", "@cache", "@log"):
                if not os.path.exists(f"{MNT}/{name}"):
                    run(f"btrfs subvolume create {MNT}/{name}")
            run("umount /mnt")
        step("create_subvolumes", create_subvolumes)

    # The LUKS mapping does not survive a reboot, so never checkpoint it:
    # just make sure it is open before mounting.
    if not os.path.exists("/dev/mapper/root"):
        print("Opening encrypted partition...")
        run(f"cryptsetup open {LUKS_PART} root")

    SUBVOL_ROOT = input("Subvolume for /: ").strip() or "@"
    SUBVOL_HOME = input("Subvolume for /home: ").strip() or "@home"
    SUBVOL_CACHE = input("Subvolume for /cache: ").strip() or "@cache"
    SUBVOL_LOG = input("Subvolume for /log: ").strip() or "@log"

    def mount_disk():
        print("Mounting disk...")
        if not is_mounted(MNT):
            run(f"mount -o subvol={SUBVOL_ROOT} /dev/mapper/root {MNT}")
        os.makedirs(f"{MNT}/home", exist_ok=True)
        os.makedirs(f"{MNT}/var/cache", exist_ok=True)
        os.makedirs(f"{MNT}/var/log", exist_ok=True)
        if not is_mounted(f"{MNT}/home"):
            run(f"mount -o subvol={SUBVOL_HOME} /dev/mapper/root {MNT}/home")
        if not is_mounted(f"{MNT}/var/cache"):
            run(f"mount -o subvol={SUBVOL_CACHE} /dev/mapper/root {MNT}/var/cache")
        if not is_mounted(f"{MNT}/var/log"):
            run(f"mount -o subvol={SUBVOL_LOG} /dev/mapper/root {MNT}/var/log")
        os.makedirs(f"{MNT}/boot", exist_ok=True)
        if not is_mounted(f"{MNT}/boot"):
            run(f"mount {EFI_PART} {MNT}/boot")
    step("mount_disk", mount_disk)

    def base_system_present():
        return (os.path.exists(f"{MNT}/usr/bin/dpkg")
                and os.path.exists(f"{MNT}/usr/bin/apt-get"))

    def run_debootstrap():
        print("Running debootstrap...")
        run(f"debootstrap {RELEASE} {MNT}")
    step("debootstrap", run_debootstrap, skip_check=base_system_present)

    mount_chroot_vfs()

    def fstab_present():
        fstab = Path(f"{MNT}/etc/fstab")
        if not fstab.exists():
            return False
        for line in fstab.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "UUID=" in line or "/dev/" in line:
                return True
        return False

    def generate_fstab():
        print("Generating fstab...")
        run(f"genfstab -U {MNT} >> {MNT}/etc/fstab")
    step("generate_fstab", generate_fstab, skip_check=fstab_present)

    def copy_dns():
        print("Copying DNS resolver...")
        src = "/etc/resolv.conf"
        dst = f"{MNT}/etc/resolv.conf"
        if os.path.exists(dst) and os.path.samefile(src, dst):
            print("[*] copy_dns: source and destination are the same file, skipping")
            return
        shutil.copy(src, dst)
    step("copy_dns", copy_dns)

    result = run(f"blkid -s UUID -o value {LUKS_PART}", capture=True)
    LUKS_UUID = result.stdout.decode().strip()

    def configure_base():
        print("Configuring system...")
        set_localtime()
        write_file("/etc/locale.conf", "LANG=en_US.UTF-8\n")
        append_lines_once("/etc/locale.gen", ["en_US.UTF-8 UTF-8"])
        run(f"chroot {MNT} locale-gen")
        write_file("/etc/hostname", f"{HOSTNAME}\n")
        hosts_content = Path("config/hostname/hosts").read_text().format(HOSTNAME=HOSTNAME)
        write_file("/etc/hosts", hosts_content)
        sources_content = Path("config/apt/sources.list").read_text().format(RELEASE=RELEASE)
        write_file("/etc/apt/sources.list", sources_content)
        run(f"chroot {MNT} apt update")
    step("configure_base", configure_base)

    def create_users():
        print("Setting root password...")
        run(f"chroot {MNT} passwd root")
        print("Creating user dbrugan...")
        run(f"chroot {MNT} useradd -m -G sudo,video,audio,input,render -s /bin/bash dbrugan")
        print("Setting dbrugan password...")
        run(f"chroot {MNT} passwd dbrugan")

    def users_exist():
        result = run(f"chroot {MNT} id -u dbrugan", check=False, capture=True)
        return result.returncode == 0
    step("create_users", create_users, skip_check=users_exist)

    write_file("/etc/kernel-img.conf", "do_symlinks = no\n")

    PACKAGES = "linux-image-generic linux-headers-generic cryptsetup cryptsetup-initramfs btrfs-progs initramfs-tools neovim flatpak network-manager sudo curl wget xorg kitty alacritty ghostty hyprland sddm locales console-setup"

    def packages_present():
        result = run(
            f"chroot {MNT} dpkg-query -W -f='${{Status}}' linux-image-generic",
            check=False, capture=True,
        )
        return result.returncode == 0 and b"install ok installed" in result.stdout

    def apt_install():
        print("Installing packages...")
        run(f"chroot {MNT} apt install -y {PACKAGES}")
    step("apt_install_packages", apt_install, skip_check=packages_present)

    def flathub_present():
        result = run(f"chroot {MNT} flatpak remotes", check=False, capture=True)
        return "flathub" in result.stdout.decode(errors="replace").lower()

    def enable_flatpak():
        print("Enabling flatpak Flathub...")
        run(f"chroot {MNT} flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo")
    step("enable_flatpak", enable_flatpak, skip_check=flathub_present)

    def cryptsetup_ready():
        return any(f.startswith("initrd.img-") for f in os.listdir(f"{MNT}/boot"))

    def configure_cryptsetup():
        append_lines_once("/etc/crypttab", [f"root UUID={LUKS_UUID} none luks,discard"])
        append_lines_once("/etc/initramfs-tools/modules", ["dm_crypt", "btrfs"])
        os.makedirs(f"{MNT}/etc/initramfs-tools/conf.d", exist_ok=True)
        write_file("/etc/initramfs-tools/conf.d/cryptsetup.conf", "CRYPTSETUP=y\n")
        run(f"chroot {MNT} update-initramfs -u -k all")
    step("configure_cryptsetup", configure_cryptsetup, skip_check=cryptsetup_ready)

    boot_files = os.listdir(f"{MNT}/boot")
    kernel_file = [f for f in boot_files if f.startswith("vmlinuz-")][0]
    initrd_file = [f for f in boot_files if f.startswith("initrd.img-")][0]
    KERNEL_VERSION = kernel_file.replace("vmlinuz-", "").replace("-generic", "")
    INITRD_VERSION = initrd_file.replace("initrd.img-", "").replace("-generic", "")

    def limine_present():
        return (os.path.exists(f"{MNT}/boot/EFI/limine/BOOTX64.EFI")
                and os.path.exists(f"{MNT}/boot/EFI/limine/limine.conf"))

    def install_limine():
        print("Installing Limine bootloader...")
        run(f"chroot {MNT} apt install -y build-essential gcc nasm mtools autoconf git efibootmgr")
        if not os.path.exists(f"{MNT}/tmp/limine"):
            run(f"chroot {MNT} git clone https://github.com/Limine-Bootloader/Limine.git --branch=v11.x-binary --depth=1 /tmp/limine")
        run(f"chroot {MNT} bash -c 'cd /tmp/limine && make'")
        os.makedirs(f"{MNT}/boot/EFI/limine", exist_ok=True)
        shutil.copy(f"{MNT}/tmp/limine/BOOTX64.EFI", f"{MNT}/boot/EFI/limine/")
        limine_conf = Path("config/limine/limine.conf").read_text().format(
            KERNEL_VERSION=KERNEL_VERSION,
            INITRD_VERSION=INITRD_VERSION,
            LUKS_UUID=LUKS_UUID,
        )
        write_file("/boot/EFI/limine/limine.conf", limine_conf)
    step("install_limine", install_limine, skip_check=limine_present)

    def limine_fallback_present():
        return (os.path.exists(f"{MNT}/boot/EFI/BOOT/BOOTX64.EFI")
                and os.path.exists(f"{MNT}/boot/EFI/BOOT/limine.conf"))

    def install_limine_fallback():
        print("Installing Limine UEFI fallback (EFI/BOOT)...")
        os.makedirs(f"{MNT}/boot/EFI/BOOT", exist_ok=True)
        shutil.copy(f"{MNT}/boot/EFI/limine/BOOTX64.EFI", f"{MNT}/boot/EFI/BOOT/BOOTX64.EFI")
        # Limine looks for `<EFI app dir>/limine.conf` first, so the fallback
        # binary needs its own copy of the config next to it.
        shutil.copy(f"{MNT}/boot/EFI/limine/limine.conf", f"{MNT}/boot/EFI/BOOT/limine.conf")
    step("install_limine_fallback", install_limine_fallback, skip_check=limine_fallback_present)

    os.makedirs(f"{MNT}/etc/apt/preferences.d", exist_ok=True)

    def block_snaps():
        shutil.copy("config/apt/blocked_packages", f"{MNT}/etc/apt/preferences.d/blocked-packages")
        for pkg in ["snapd", "cloud-init", "landscape-common", "popularity-contest", "ubuntu-advantage-tools"]:
            run(f"chroot {MNT} bash -c 'echo {pkg} hold | dpkg --set-selections'")
    if BLOCK_SNAPS == "yes":
        step("block_snaps", block_snaps)

    def enable_services():
        run(f"chroot {MNT} systemctl enable sddm")
        run(f"chroot {MNT} systemctl enable NetworkManager")
        os.makedirs(f"{MNT}/etc/NetworkManager/conf.d", exist_ok=True)
        shutil.copy("config/NetworkManager/managed.conf", f"{MNT}/etc/NetworkManager/conf.d/managed.conf")
    step("enable_services", enable_services)

    def efi_entry_present():
        result = run("efibootmgr", check=False, capture=True)
        return "Limine" in result.stdout.decode(errors="replace")

    def create_efi_entry():
        print("Creating EFI boot entry...")
        # efibootmgr must run on the live system (it writes NVRAM), but the
        # package was only installed inside the chroot further up. Make sure
        # it exists here too.
        if shutil.which("efibootmgr") is None:
            print("Installing efibootmgr on the live system...")
            run("apt update && apt install -y efibootmgr")
        # Single backslashes: subprocess+sh passes the string to efibootmgr
        # verbatim, so double backslashes produce an unloadable path.
        run(f"efibootmgr --create --disk {DISK} --part 1 --label 'Limine' "
            f"--loader '\\EFI\\limine\\BOOTX64.EFI' --unicode")
        listing = run("efibootmgr", check=False, capture=True).stdout.decode(errors="replace")
        match = re.search(r"Boot([0-9A-Fa-f]{4})\*?\s+Limine", listing)
        if not match:
            print("[!] Warning: could not create a Limine NVRAM entry. The "
                  "\\EFI\\BOOT\\BOOTX64.EFI fallback should still boot the system.")
            return
        bootnum = match.group(1)
        bootorder = []
        for line in listing.splitlines():
            if line.startswith("BootOrder:"):
                bootorder = [b.strip() for b in line.split(":", 1)[1].split(",") if b.strip()]
                break
        new_order = [bootnum] + [b for b in bootorder if b != bootnum]
        run(f"efibootmgr --bootorder {','.join(new_order)}", check=False)
    step("create_efi_entry", create_efi_entry, skip_check=efi_entry_present)

    print("Unmounting...")
    umount_chroot_vfs()
    run("umount -R /mnt", check=False)
    print("Done! You can now reboot.")
    print(f"(Progress was recorded in {STATE_FILE}; delete it or pass --reset to start over.)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user. Progress is saved; re-run the script to resume.")
        sys.exit(130)
    except subprocess.CalledProcessError as e:
        print(f"\nCommand failed (exit {e.returncode}): {e.cmd}")
        print("Progress is saved; fix the issue and re-run the script to resume.")
        sys.exit(1)
