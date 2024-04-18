#!/bin/bash

parted --script /dev/sda mklabel gpt
parted --script /dev/sda mkpart ESP fat32 1MiB 513MiB
parted --script /dev/sda set 1 esp on
parted --script /dev/sda mkpart Root btrfs 512MiB 100%

cryptsetup luksFormat /dev/sda2
cryptsetup open --type luks /dev/sda2 sda2_crypt
mkfs.btrfs /dev/mapper/sda2_crypt 

mount /dev/mapper/sda2_crypt /mnt

btrfs subvolume create /mnt/root
btrfs subvolume create /mnt/home
btrfs subvolume create /mnt/snapshots
btrfs subvolume create /mnt/cache
btrfs subvolume create /mnt/log
umount /mnt

mount -o subvol=root /dev/mapper/sda2_crypt /mnt
mkdir /mnt/home
mount -o subvol=home /dev/mapper/sda2_crypt /mnt/home
mkdir /mnt/.snapshots
mount -o subvol=snapshots /dev/mapper/sda2_crypt /mnt/.snapshots
mkdir -p /mnt/var/cache
mount -o subvol=cache /dev/mapper/sda2_crypt /mnt/var/cache
mkdir /mnt/var/log
mount -o subvol=log /dev/mapper/sda2_crypt /mnt/var/log

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
cryptsetup close sda2_crypt
