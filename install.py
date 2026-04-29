#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
from pathlib import Path

MNT = "/mnt"
BLOCK_SNAPS = input("Block snaps and unwanted packages? (yes/no): ").strip().lower()
FORMAT = input("Format and partition disk? (yes/no): ").strip().lower()
DISK = input("Enter disk device (e.g., /dev/sda, /dev/nvme0n1): ").strip()

def run(cmd, check=True, shell=True, capture=False, cwd=None):
    if isinstance(cmd, str):
        result = subprocess.run(cmd, shell=shell, check=check, capture_output=capture, cwd=cwd)
    else:
        result = subprocess.run(cmd, check=check, capture_output=capture, cwd=cwd)
    if capture:
        return result
    return result.returncode == 0

def check_root():
    if os.geteuid() != 0:
        os.execvpe("/usr/bin/sudo", ["sudo"] + sys.argv)

def write_file(path, content):
    full_path = f"{MNT}{path}"
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)

def main():
    check_root()


    if not os.path.exists(DISK):
        print(f"Error: {DISK} is not a block device")
        sys.exit(1)

    RELEASE = "resolute"
    HOSTNAME = "ubuntu"
    LUKS_PART = f"{DISK}2"
    EFI_PART = f"{DISK}1"


    if FORMAT == "yes":
        print("Installing required packages...")
        run("apt update && apt install -y arch-install-scripts debootstrap")

        print("Creating partitions...")
        run(f"parted {DISK} mklabel gpt")
        run(f"parted {DISK} mkpart ESP fat32 1MiB 2049MiB set 1 esp on")
        run(f"parted {DISK} mkpart primary 2049MiB 100%")

        print("Formatting partitions...")
        run(f"mkfs.fat -F 32 {EFI_PART}")

        print("Setting up LUKS encryption...")
        run(f"cryptsetup luksFormat --type luks2 {LUKS_PART}")
        run(f"cryptsetup open {LUKS_PART} root")
        run("mkfs.btrfs /dev/mapper/root")

        print("Creating BTRFS subvolumes...")
        run("mount /dev/mapper/root /mnt")
        run("btrfs subvolume create /mnt/@")
        run("btrfs subvolume create /mnt/@home")
        run("btrfs subvolume create /mnt/@cache")
        run("btrfs subvolume create /mnt/@log")
        run("umount /mnt")
    else:
        print("Opening encrypted partition...")
        run(f"cryptsetup open {LUKS_PART} root")

    SUBVOL_ROOT = input("Subvolume for /: ").strip() or "@"
    SUBVOL_HOME = input("Subvolume for /home: ").strip() or "@home"
    SUBVOL_CACHE = input("Subvolume for /cache: ").strip() or "@cache"
    SUBVOL_LOG = input("Subvolume for /log: ").strip() or "@log"

    print("Mounting disk...")
    run(f"mount -o subvol={SUBVOL_ROOT} /dev/mapper/root /mnt")
    os.makedirs(f"{MNT}/home", exist_ok=True)
    os.makedirs(f"{MNT}/var/cache", exist_ok=True)
    os.makedirs(f"{MNT}/var/log", exist_ok=True)
    run(f"mount -o subvol={SUBVOL_HOME} /dev/mapper/root /mnt/home")
    run(f"mount -o subvol={SUBVOL_CACHE} /dev/mapper/root /mnt/var/cache")
    run(f"mount -o subvol={SUBVOL_LOG} /dev/mapper/root /mnt/var/log")
    os.makedirs(f"{MNT}/boot", exist_ok=True)
    run(f"mount {EFI_PART} /mnt/boot")

    print("Running debootstrap...")
    run(f"debootstrap {RELEASE} {MNT}")

    print("Generating fstab...")
    run(f"genfstab -U {MNT} >> {MNT}/etc/fstab", shell=True)

    print("Copying DNS resolver...")
    shutil.copy("/etc/resolv.conf", f"{MNT}/etc/resolv.conf")

    result = run(f"blkid -s UUID -o value {LUKS_PART}", capture=True)
    LUKS_UUID = result.stdout.decode().strip()

    print("Configuring system...")

    os.symlink("/usr/share/zoneinfo/America/Belem", f"{MNT}/etc/localtime")

    write_file("/etc/locale.conf", "LANG=en_US.UTF-8\n")

    with open(f"{MNT}/etc/locale.gen", "a") as f:
        f.write("en_US.UTF-8 UTF-8\n")
    run(f"chroot {MNT} locale-gen")

    write_file("/etc/hostname", f"{HOSTNAME}\n")

    hosts_content = f"""127.0.0.1   localhost
127.0.1.1   {HOSTNAME}
::1         localhost ip6-localhost ip6-loopback
"""
    write_file("/etc/hosts", hosts_content)

    sources_content = f"""deb http://archive.ubuntu.com/ubuntu {RELEASE} main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu {RELEASE}-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu {RELEASE}-backports main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu {RELEASE}-security main restricted universe multiverse
"""
    write_file("/etc/apt/sources.list", sources_content)

    run(f"chroot {MNT} apt update")

    print("Setting root password...")
    run(f"chroot {MNT} passwd root")

    print("Creating user dbrugan...")
    run(f"chroot {MNT} useradd -m -G sudo,video,audio,input,render -s /bin/bash dbrugan")
    print("Setting dbrugan password...")
    run(f"chroot {MNT} passwd dbrugan")

    write_file("/etc/kernel-img.conf", "do_symlinks = no\n")

    PACKAGES = "linux-image-generic linux-headers-generic cryptsetup cryptsetup-initramfs btrfs-progs initramfs-tools neovim flatpak network-manager sudo curl wget xorg kitty alacritty ghostty hyprland sddm locales console-setup"
    print("Installing packages...")
    run(f"chroot {MNT} apt install -y {PACKAGES}")

    print("Enabling flatpak Flathub...")
    run(f"chroot {MNT} flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo")

    with open(f"{MNT}/etc/crypttab", "a") as f:
        f.write(f"root UUID={LUKS_UUID} none luks,discard\n")

    with open(f"{MNT}/etc/initramfs-tools/modules", "a") as f:
        f.write("dm_crypt\n")
        f.write("btrfs\n")

    os.makedirs(f"{MNT}/etc/initramfs-tools/conf.d", exist_ok=True)
    write_file("/etc/initramfs-tools/conf.d/cryptsetup.conf", "CRYPTSETUP=y\n")

    run(f"chroot {MNT} update-initramfs -u -k all")

    boot_files = os.listdir(f"{MNT}/boot")
    kernel_file = [f for f in boot_files if f.startswith("vmlinuz-")][0]
    initrd_file = [f for f in boot_files if f.startswith("initrd.img-")][0]
    KERNEL_VERSION = kernel_file.replace("vmlinuz-", "").replace("-generic", "")
    INITRD_VERSION = initrd_file.replace("initrd.img-", "").replace("-generic", "")

    print("Installing Limine bootloader...")
    run(f"chroot {MNT} apt install -y build-essential gcc nasm mtools autoconf git efibootmgr")
    run(f"chroot {MNT} git clone https://github.com/Limine-Bootloader/Limine.git --branch=v11.x-binary --depth=1 /tmp/limine")
    run(f"chroot {MNT} bash -c 'cd /tmp/limine && make'")

    os.makedirs(f"{MNT}/boot/EFI/limine", exist_ok=True)
    shutil.copy(f"{MNT}/tmp/limine/BOOTX64.EFI", f"{MNT}/boot/EFI/limine/")

    limine_conf = f"""timeout: 5
default_entry: 1

/Ubuntu Linux
    protocol: linux
    kernel_path: boot():/vmlinuz-{KERNEL_VERSION}-generic
    module_path: boot():/initrd.img-{INITRD_VERSION}-generic
    cmdline: root=/dev/mapper/root rootflags=subvol=@ rd.luks.name={LUKS_UUID}=root rd.luks.options=discard cryptdevice={LUKS_UUID}:root:allow-discards rootfstype=btrfs quiet splash loglevel=3
"""
    write_file("/boot/EFI/limine/limine.conf", limine_conf)

    os.makedirs(f"{MNT}/etc/apt/preferences.d", exist_ok=True)

    if BLOCK_SNAPS == "yes":
        shutil.copy("config/apt/blocked_packages", f"{MNT}/etc/apt/preferences.d/blocked-packages")

        for pkg in ["snapd", "cloud-init", "landscape-common", "popularity-contest", "ubuntu-advantage-tools"]:
            run(f"chroot {MNT} bash -c 'echo {pkg} hold | dpkg --set-selections'")

    run(f"chroot {MNT} systemctl enable sddm")

    os.makedirs(f"{MNT}/usr/share/xsessions", exist_ok=True)
    hyprland_desktop = """[Desktop Entry]
Name=Hyprland
Comment=Hyprland Session
Exec=Hyprland
Type=Application
"""
    write_file("/usr/share/xsessions/hyprland.desktop", hyprland_desktop)

    run(f"chroot {MNT} systemctl enable NetworkManager")

    os.makedirs(f"{MNT}/etc/NetworkManager/conf.d", exist_ok=True)
    shutil.copy("config/NetworkManager/managed.conf", f"{MNT}/etc/NetworkManager/conf.d/managed.conf")

    print("Creating EFI boot entry...")
    run(f"efibootmgr --create --disk {DISK} --part 1 --label 'Limine' --loader '\\\\EFI\\\\limine\\\\BOOTX64.EFI' --unicode")

    print("Unmounting...")
    run("umount -R /mnt")
    print("Done! You can now reboot.")

if __name__ == "__main__":
    main()
