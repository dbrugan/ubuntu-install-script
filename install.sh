#!/bin/bash
set -e

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        exec sudo "$0" "$@"
    fi
}

check_root "$@"

export MNT="/mnt"

read -p "Enter disk device (e.g., /dev/sda, /dev/nvme0n1): " DISK

if [ ! -b "$DISK" ]; then
    echo "Error: $DISK is not a block device"
    exit 1
fi

echo "Installing required packages..."
apt update && apt install -y arch-install-scripts debootstrap

echo "Creating partitions..."
parted "$DISK" mklabel gpt mkpart ESP fat32 1MiB 2049MiB set 1 esp on
parted "$DISK" mkpart primary 2049MiB 100%

echo "Formatting partitions..."
mkfs.fat -F 32 "${DISK}1"

echo "Setting up LUKS encryption..."
cryptsetup luksFormat --type luks2 "${DISK}2"
cryptsetup open "${DISK}2" root
mkfs.btrfs /dev/mapper/root

echo "Creating BTRFS subvolumes..."
mount /dev/mapper/root /mnt
btrfs subvolume create /mnt/@
btrfs subvolume create /mnt/@home
btrfs subvolume create /mnt/@cache
btrfs subvolume create /mnt/@log
umount /mnt

echo "Mounting disk..."
mount -o subvol=@ /dev/mapper/root /mnt
mkdir -p /mnt/{home,var/cache,var/log}
mount -o subvol=@home /dev/mapper/root /mnt/home
mount -o subvol=@cache /dev/mapper/root /mnt/var/cache
mount -o subvol=@log /dev/mapper/root /mnt/var/log
mkdir -p /mnt/boot
mount "${DISK}1" /mnt/boot

RELEASE=resolute
HOSTNAME=ubuntu

echo "Running debootstrap..."
debootstrap ${RELEASE} /mnt

echo "Generating fstab..."
genfstab -U /mnt >> /mnt/etc/fstab

echo "Copying DNS resolver..."
cp /etc/resolv.conf ${MNT}/etc/resolv.conf

LUKS_UUID=$(blkid -s UUID -o value "${DISK}2")

echo "Chrooting and configuring system..."

arch-chroot /mnt /bin/bash << CHROOTEOF
set -e

ln -sf /usr/share/zoneinfo/America/Belem /etc/localtime

echo "LANG=en_US.UTF-8" > /etc/locale.conf
echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
locale-gen

echo "${HOSTNAME}" > /etc/hostname

cat > /etc/hosts << 'HOSTEOF'
127.0.0.1   localhost
127.0.1.1   ${HOSTNAME}
::1         localhost ip6-localhost ip6-loopback
HOSTEOF

cat > /etc/apt/sources.list << 'APTEOF'
deb http://archive.ubuntu.com/ubuntu ${RELEASE} main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu ${RELEASE}-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu ${RELEASE}-backports main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu ${RELEASE}-security main restricted universe multiverse
APTEOF

apt update

echo "Configuring users..."
passwd root
useradd -m -G sudo,video,audio,input,render -s /bin/bash dbrugan
passwd dbrugan

touch /etc/kernel-img.conf
echo "do_symlinks = no" > /etc/kernel-img.conf

PACKAGES="linux-image-generic linux-headers-generic cryptsetup cryptsetup-initramfs
         btrfs-progs initramfs-tools neovim flatpak network-manager sudo curl wget xorg
         kitty alacritty ghostty hyprland sddm locales console-setup"

echo "Installing packages..."
apt install -y $PACKAGES

echo "Enabling flatpak Flathub..."
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

echo "root UUID=${LUKS_UUID} none luks,discard" >> /etc/crypttab

echo "dm_crypt" >> /etc/initramfs-tools/modules
echo "btrfs"    >> /etc/initramfs-tools/modules
echo "CRYPTSETUP=y" > /etc/initramfs-tools/conf.d/cryptsetup.conf
update-initramfs -u -k all

KERNEL_VERSION=\$(ls /boot/vmlinuz-* | head -1 | sed 's|/boot/vmlinuz-||')
INITRD_VERSION=\$(ls /boot/initrd.img-* | head -1 | sed 's|/boot/initrd.img-||')

echo "Installing Limine bootloader..."
apt install build-essential gcc nasm mtools autoconf git efibootmgr
git clone https://github.com/Limine-Bootloader/Limine.git --branch=v11.x-binary --depth=1 limine
cd limine
make
mkdir -p /boot/EFI/limine
cp limine/BOOTX64.EFI /boot/EFI/limine/

cat > /boot/EFI/limine/limine.conf << LIMINEEOF
timeout: 5
default_entry: 1

/Ubuntu Linux
    protocol: linux
    kernel_path: boot():/vmlinuz-\${KERNEL_VERSION}-generic
    module_path: boot():/initrd.img-\${INITRD_VERSION}-generic
    cmdline: root=/dev/mapper/root rootflags=subvol=@ rd.luks.name=${LUKS_UUID}=root rd.luks.options=discard cryptdevice=${LUKS_UUID}:root:allow-discards rootfstype=btrfs quiet splash loglevel=3
LIMINEEOF

cat > /etc/apt/preferences.d/blocked-packages << 'APTBLOCK'
Package: snapd
Pin: release *
Pin-Priority: -1

Package: cloud-init
Pin: release *
Pin-Priority: -1

Package: landscape-common
Pin: release *
Pin-Priority: -1

Package: popularity-contest
Pin: release *
Pin-Priority: -1

Package: ubuntu-advantage-tools
Pin: release *
Pin-Priority: -1
APTBLOCK

for pkg in snapd cloud-init landscape-common popularity-contest ubuntu-advantage-tools; do
  echo "\${pkg} hold" | dpkg --set-selections
done

systemctl enable sddm

mkdir -p /usr/share/xsessions
cat > /usr/share/xsessions/hyprland.desktop << 'HYPREOF'
[Desktop Entry]
Name=Hyprland
Comment=Hyprland Session
Exec=Hyprland
Type=Application
HYPREOF

systemctl enable NetworkManager
systemctl disable systemd-networkd 2>/dev/null || true

cat > /etc/NetworkManager/conf.d/managed.conf << 'NMEOF'
[main]
plugins=keyfile

[keyfile]
unmanaged-devices=none
NMEOF
CHROOTEOF

echo "Creating EFI boot entry..."
efibootmgr --create --disk "$DISK" --part 1 --label "Limine" --loader '\EFI\limine\BOOTX64.EFI' --unicode

echo "Exiting chroot..."
umount -R /mnt
echo "Done! You can now reboot."
