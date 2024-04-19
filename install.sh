#!/bin/bash

disk="/dev/sda"

# Erase existing disk labels and partitions
wipefs -af "$disk"

# creating partitions
parted --script "$disk" mklabel gpt
parted --script "$disk" mkpart ESP fat32 1MiB 513MiB
parted --script "$disk" set 1 esp on
parted --script "$disk" mkpart ROOT btrfs 513MiB 100%

# formatting partitions
mkfs.fat -F 32 "${disk}"1
mkfs.btrfs --force "${disk}"2

# configure btrfs subvolumes
mount "${disk}"2 /mnt

btrfs subvolume create /mnt/@
btrfs subvolume create /mnt/@home
btrfs subvolume create /mnt/@snapshots
btrfs subvolume create /mnt/@cache
btrfs subvolume create /mnt/@log

umount /mnt

# mounting system partitions
mount -o subvol=@ "${disk}"2 /mnt

mkdir -p /mnt/{home,.snapshots,var/{cache,log},boot/efi}

mount -o subvol=@home "${disk}"2 /mnt/home
mount -o subvol=@snapshots "${disk}"2 /mnt/.snapshots
mount -o subvol=@cache "${disk}"2 /mnt/var/cache
mount -o subvol=@log "${disk}"2 /mnt/var/log
mount "${disk}"1 /mnt/boot/efi

# installing base system
apt install debootstrap
debootstrap jammy /mnt

# preparing necessary mount directories for chroot
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

# chroot in the installed system
chroot /mnt /bin/bash <<EOF
  export LANG=C
  export DEBIAN_FRONTEND=noninteractive

  apt update && apt install -y linux-image-generic grub-efi btrfs-progs flatpak neovim

  flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

  grub-install --target=x86_64-efi --efi-directory=/boot/efi bootloader-id=ubuntu --recheck
  update-grub
  
EOF

umount -R /mnt
