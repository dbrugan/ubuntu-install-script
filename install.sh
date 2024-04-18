#!/bin/bash

disk="/dev/sda"
# creating partitions
parted --script "$disk" mklabel gpt
parted --script "$disk" mkpart ESP fat32 1MiB 513MiB
parted --script "$disk" set 1 esp on
parted --script "$disk" mkpart CRYPTROOT btrfs 513MiB 100%

# formatting partitions
mkfs.fat -F 32 "${disk}"1
cryptsetup luksFormat "${disk}"2
cryptsetup open "${disk}"2 cryptroot
mkfs.btrfs /dev/mapper/cryptroot

# configure btrfs subvolumes
mount /dev/mapper/cryptroot /mnt

btrfs subvolume create /mnt/root
btrfs subvolume create /mnt/home
btrfs subvolume create /mnt/snapshots
btrfs subvolume create /mnt/cache
btrfs subvolume create /mnt/log
umount /mnt

# mounting system partitions
mount -o subvol=root /dev/mapper/cryptroot /mnt

mkdir /mnt/home
mount -o subvol=home /dev/mapper/cryptroot /mnt/home

mkdir /mnt/.snapshots
mount -o subvol=snapshots /dev/mapper/cryptroot /mnt/.snapshots

mkdir -p /mnt/var/cache
mount -o subvol=cache /dev/mapper/cryptroot /mnt/var/cache

mkdir /mnt/var/log
mount -o subvol=log /dev/mapper/cryptroot /mnt/var/log

mkdir -p /mnt/boot/efi
mount "${disk}"1 /mnt/boot/efi

apt install debootstrap
debootstrap jammy /mnt

mount --bind /dev /mnt/dev
mount --bind /dev/pts /mnt/dev/pts
mount --bind /proc /mnt/proc
mount --bind /sys /mnt/sys
cp /etc/resolv.conf /mnt/etc/resolv.conf

# define jammy sources
jammy_sources="\
  deb http://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse
  deb http://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse
  deb http://archive.ubuntu.com/ubuntu jammy-security main restricted universe multiverse
  deb http://archive.ubuntu.com/ubuntu jammy-backports main restricted universe multiverse
  "

echo "$jammy_sources" > /mnt/etc/apt/sources.list

chroot /mnt /bin/bash <<EOF
export LANG=C
export DEBIAN_FRONTEND=noninteractive

apt update && apt install -y linux-image-generic grub-efi btrfs-progs cryptsetup flatpak neovim

flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

grub-install --target=x86_64-efi --efi-directory=/boot/efi bootloader-id=ubuntu --recheck
update-grub
EOF

umount -R /mnt
cryptsetup close cryptroot
