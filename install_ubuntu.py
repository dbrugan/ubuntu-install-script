import os
import subprocess
import sys

def run_command(command, check=True):
    """Run a shell command."""
    print(f"Running: {' '.join(command)}")
    result = subprocess.run(command, check=check)
    return result

def ask_for_disk():
    """Ask the user for the disk path."""
    disk = input("Enter the disk path (e.g., /dev/sda): ").strip()
    if not disk.startswith('/dev/'):
        print("Invalid disk path. It should start with /dev/.")
        sys.exit(1)
    return disk

def get_password(prompt):
    """Get a password from the user without echoing it."""
    password = input(prompt).strip()
    return password

def erase_disk(disk):
    """Erase previous disk information."""
    print(f"Erasing previous disk info on {disk}...")
    run_command(['sudo', 'wipefs', '-af', disk])
    run_command(['sudo', 'sgdisk', '-Zo', disk])

def create_partitions(disk):
    """Create partitions on the disk."""
    print(f"Creating partitions on {disk}...")
    run_command(['sudo', 'parted', '--script', disk, 'mklabel', 'gpt'])
    run_command(['sudo', 'parted', '--script', disk, 'mkpart', 'ESP', 'fat32', '1MiB', '513MiB'])
    run_command(['sudo', 'parted', '--script', disk, 'set', '1', 'esp', 'on'])
    run_command(['sudo', 'parted', '--script', disk, 'mkpart', 'primary', 'ext4', '513MiB', '1.5GiB'])
    run_command(['sudo', 'parted', '--script', disk, 'mkpart', 'CRYPTROOT', 'btrfs', '1.5GiB', '100%'])

def format_partitions(disk):
    """Format the partitions."""
    print(f"Formatting partitions on {disk}...")
    run_command(['sudo', 'mkfs.fat', '-F', '32', f'{disk}1'])
    run_command(['sudo', 'mkfs.ext4', f'{disk}2'])
    run_command(['sudo', 'cryptsetup', 'luksFormat', f'{disk}3'])
    run_command(['sudo', 'cryptsetup', 'open', f'{disk}3', 'cryptroot'])
    run_command(['sudo', 'mkfs.btrfs', '--force', '/dev/mapper/cryptroot'])

def configure_btrfs_subvolumes():
    """Configure Btrfs subvolumes."""
    print("Configuring Btrfs subvolumes...")
    mount_point = '/mnt/install'
    os.makedirs(mount_point, exist_ok=True)
    run_command(['sudo', 'mount', '/dev/mapper/cryptroot', mount_point])

    subvolumes = ['@', '@home', '@snapshots', '@cache', '@log']
    for subvol in subvolumes:
        run_command(['sudo', 'btrfs', 'subvolume', 'create', f'{mount_point}/{subvol}'])

    run_command(['sudo', 'umount', mount_point])

def mount_system_partitions(disk):
    """Mount system partitions."""
    print("Mounting system partitions...")
    mount_point = '/mnt/install'
    os.makedirs(mount_point, exist_ok=True)
    mount_options = "noatime,discard,compress=zstd,ssd,space_cache=v2,commit=120,autodefrag"
    run_command(['sudo', 'mount', '-o', f'subvol=@,{mount_options}', '/dev/mapper/cryptroot', mount_point])

    directories = ['home', '.snapshots', 'var/cache', 'var/log']
    for directory in directories:
        os.makedirs(f'{mount_point}/{directory}', exist_ok=True)

    run_command(['sudo', 'mount', '-o', f'subvol=@home,{mount_options}', '/dev/mapper/cryptroot', f'{mount_point}/home'])
    run_command(['sudo', 'mount', '-o', f'subvol=@snapshots,{mount_options}', '/dev/mapper/cryptroot', f'{mount_point}/.snapshots'])
    run_command(['sudo', 'mount', '-o', f'subvol=@cache,{mount_options}', '/dev/mapper/cryptroot', f'{mount_point}/var/cache'])
    run_command(['sudo', 'mount', '-o', f'subvol=@log,{mount_options}', '/dev/mapper/cryptroot', f'{mount_point}/var/log'])

    os.makedirs(f'{mount_point}/boot', exist_ok=True)
    run_command(['sudo', 'mount', f'{disk}2', f'{mount_point}/boot'])

    os.makedirs(f'{mount_point}/boot/efi', exist_ok=True)
    run_command(['sudo', 'mount', f'{disk}1', f'{mount_point}/boot/efi'])

def enable_universe_repo_and_install_tools():
    """Enable universe repository and install necessary tools."""
    print("Enabling universe repository and installing necessary tools...")
    run_command(['sudo', 'add-apt-repository', 'universe'])
    run_command(['sudo', 'apt', 'update'])
    run_command(['sudo', 'apt', 'install', '-y', 'debootstrap', 'arch-install-scripts'])

def debootstrap_system(mount_point):
    """Debootstrap the Ubuntu system."""
    print("Debootstrapping Ubuntu system...")
    run_command(['sudo', 'debootstrap', 'noble', mount_point, 'http://archive.ubuntu.com/ubuntu/'])

def create_fstab(mount_point):
    """Create new mounting table."""
    print("Creating new mounting table...")
    run_command(['sudo', 'genfstab', '-U', mount_point, '>>', f'{mount_point}/etc/fstab'])

def enable_repositories(mount_point):
    """Enable repositories."""
    print("Enabling repositories...")
    sources = """\
deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-security main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-backports main restricted universe multiverse
"""
    with open(f'{mount_point}/etc/apt/sources.list', 'w') as f:
        f.write(sources)

def configure_apt_blacklist(mount_point):
    """Configure apt to not install certain packages."""
    print("Configuring apt to not install certain packages...")
    blacklist = """\
Package: snapd
Pin: release *
Pin-Priority: -1001

Package: cloud-init
Pin: release *
Pin-Priority: -1001

Package: landscape-common
Pin: release *
Pin-Priority: -1001

Package: popularity-contest
Pin: release *
Pin-Priority: -1001

Package: ubuntu-advantage-tools
Pin: release *
Pin-Priority: -1001
"""
    with open(f'{mount_point}/etc/apt/preferences.d/ignored-packages.pref', 'w') as f:
        f.write(blacklist)

def get_root_uuid(disk):
    """Get the UUID of the encrypted partition."""
    print("Getting the UUID of the encrypted partition...")
    root_uuid = subprocess.check_output(['sudo', 'blkid', '-s', 'UUID', '-o', 'value', f'{disk}3']).decode().strip()
    return root_uuid

def set_default_shell(mount_point):
    """Set Bash as the default shell for new users."""
    print("Setting Bash as the default shell for new users...")
    with open(f'{mount_point}/etc/default/useradd', 'a') as f:
        f.write('SHELL=/bin/bash\n')

def define_zram_config():
    """Define zram configuration."""
    print("Defining zram configuration...")
    zram_config = """\
[zram0]
zram-size = min(ram, 8192)
"""
    return zram_config

def chroot_and_configure_system(mount_point, root_password, user_password, root_uuid, zram_config):
    """Chroot into the installed system and perform further configuration."""
    print("Chrooting into the installed system...")
    chroot_script = f"""\
export LANG=C
export DEBIAN_FRONTEND=noninteractive

# install kernel and some system utils
apt update && apt install -y --no-install-recommends \\
    linux-image-generic linux-firmware grub-efi btrfs-progs bash \\
    bash-completion curl neovim initramfs-tools cryptsetup cryptsetup-initramfs \\
    efibootmgr systemd-zram-generator wget

# configure locale
echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
locale-gen
update-locale LANG=en_US.UTF-8

# configure keyboard
echo "KEYMAP=br-abnt2" > /etc/vconsole.conf

# configure timezone
ln -sf /usr/share/zoneinfo/America/Belem /etc/localtime
echo "America/Belem" > /etc/timezone

# set hostname
echo "ubuntu" > /etc/hostname
echo "127.0.1.1 ubuntu" >> /etc/hosts

# set root password
echo "root:{root_password}" | chpasswd

# create user
useradd -mG sudo dbrugan
echo "dbrugan:{user_password}" | chpasswd

# configure crypttab
echo "cryptroot UUID={root_uuid} none luks,discard" >> /etc/crypttab

# configure bootloader
sed -i "/^GRUB_CMDLINE_LINUX=/ s/\"$/ cryptdevice=UUID={root_uuid}:cryptroot\"/" /etc/default/grub
grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=ubuntu --recheck
update-grub

# update initramfs
update-initramfs -u
update-grub

# configure zram
echo "{zram_config}" >> /etc/systemd/zram-generator.conf

# cleaning unwanted files
rm /etc/apt/preferences.d/ubuntu-pro-esm-apps
rm /etc/apt/preferences.d/ubuntu-pro-esm-infra

# install desktop environment and other userful packages
apt install -y --no-install-recommends \\
    gnome-session gnome-shell gdm3 gnome-backgrounds gnome-console gnome-software \\
    gnome-menus gnome-keyring gnome-online-accounts gnome-online-accounts-gtk \\
    nautilus nautilus-sendto flatpak gnome-software-plugin-flatpak power-profiles-daemon \\
    gnome-tweaks eog baobab gnome-control-center gnome-disk-utility gnome-bluetooth \\
    gvfs-fuse gnome-user-share evince totem avahi-autoipd bluez btop cups fwupd \\
    fwupd-signed fonts-noto-color-emoji fonts-liberation fonts-liberation-sans-narrow \\
    gamemode gstreamer1.0-libav gstreamer1.0-plugins-ugly gstreamer1.0-vaapi liba52-0.7.4 \\
    libavcodec-extra libfuse2 nala network-manager network-manager-config-connectivity-ubuntu \\
    network-manager-openvpn-gnome network-manager-pptp-gnome neofetch packagekit systemd-oomd \\
    update-manager yaru-theme-sound yaru-theme-icon timeshift xdg-utils xdg-user-dirs-gtk \\
    xdg-user-dirs
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub \\
    org.mozilla.firefox \\
    com.mattjakeman.ExtensionManager \\
    org.gnome.FileRoller
"""

    chroot_script = chroot_script.format(root_password=root_password, user_password=user_password, root_uuid=root_uuid, zram_config=zram_config)
    chroot_command = ['sudo', 'arch-chroot', mount_point]
    run_command(chroot_command + ['bash', '-c', chroot_script])

def unmount_all(mount_point):
    """Unmount all mounted filesystems."""
    print("Unmounting all filesystems...")
    subvolumes = ['@home', '@snapshots', '@cache', '@log']
    for subvol in subvolumes:
        subvol_path = f'{mount_point}/{subvol}'
        run_command(['sudo', 'umount', subvol_path])
    run_command(['sudo', 'umount', f'{mount_point}/boot/efi'])
    run_command(['sudo', 'umount', f'{mount_point}/boot'])
    run_command(['sudo', 'umount', mount_point])

def main():
    disk = ask_for_disk()
    root_password = get_password("Choose the root password: ")
    user_password = get_password("Choose the password for the user: ")

    erase_disk(disk)
    create_partitions(disk)
    format_partitions(disk)
    configure_btrfs_subvolumes()
    mount_system_partitions(disk)
    enable_universe_repo_and_install_tools()
    debootstrap_system('/mnt/install')
    create_fstab('/mnt/install')
    enable_repositories('/mnt/install')
    configure_apt_blacklist('/mnt/install')
    root_uuid = get_root_uuid(disk)
    set_default_shell('/mnt/install')
    zram_config = define_zram_config()
    chroot_and_configure_system('/mnt/install', root_password, user_password, root_uuid, zram_config)
    unmount_all('/mnt/install')
    print("Installation complete.")

if __name__ == "__main__":
    main()
