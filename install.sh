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
mkfs.fat -F 32 "${disk}1"
mkfs.btrfs --force "${disk}2"

# configure btrfs subvolumes
mount "${disk}2" /mnt

btrfs subvolume create /mnt/@
btrfs subvolume create /mnt/@home
btrfs subvolume create /mnt/@snapshots
btrfs subvolume create /mnt/@cache
btrfs subvolume create /mnt/@log

umount /mnt

# mounting system partitions
mount_options="noatime,compress=zstd,space_cache=v2"
mount -o "subvol=@,$mount_options" "${disk}2" /mnt

mkdir -p /mnt/{home,.snapshots,var/{cache,log},boot/efi}

mount -o "subvol=@home,$mount_options" "${disk}2" /mnt/home
mount -o "subvol=@snapshots,$mount_options" "${disk}2" /mnt/.snapshots
mount -o "subvol=@cache,$mount_options" "${disk}2" /mnt/var/cache
mount -o "subvol=@log,$mount_options" "${disk}2" /mnt/var/log
mount "${disk}1" /mnt/boot/efi

# enable universe repository and install necessary tools
add-apt-repository universe
apt update && apt install -y debootstrap arch-install-scripts

# installing base system
debootstrap jammy /mnt

# create new mounting table
genfstab -U /mnt >> /mnt/etc/fstab

# enabling repositories
jammy_sources="\
  deb http://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse
  deb http://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse
  deb http://archive.ubuntu.com/ubuntu jammy-security main restricted universe multiverse
  deb http://archive.ubuntu.com/ubuntu jammy-backports main restricted universe multiverse
  "

echo "$jammy_sources" > /mnt/etc/apt/sources.list

# configure apt to not install certain packages
blacklist="\
  Package: snapd cloud-init landscape-common popularity-contest ubuntu-advantage-tools
  Pin: release *
  Pin-Priority: -1
  "

echo "$blacklist" > /mnt/etc/apt/preferences.d/ignored-packages

# get root password
echo "Enter the root password:"
read -s root_password

# get user password
echo "Enter the password for the user:"
read -s user_password

# chroot in the installed system
arch-chroot /mnt <<EOF
  export LANG=C
  export DEBIAN_FRONTEND=noninteractive

  # install base system utils
  apt update && apt install -y linux-image-generic grub-efi btrfs-progs neovim nala network-manager

  # configure locale
  echo "en_US.UTF-8 UTF-8" > /etc/locale.gen
  locale-gen
  update-locale LANG=en_US.UTF-8

  # configure keyboard
  echo "KEYMAP=br-abnt2" > /etc/vconsole.conf

  # configure timezone
  ln -sf /usr/share/zoneinfo/America/Belem /etc/localtime
  echo "America/Belem" > etc/timezone

  # set hostname
  echo "ubuntu" > /etc/hostname
  echo "127.0.1.1 ubuntu" >> /etc/hosts

  # set root password
  echo "root:$root_password" | chpasswd

  # create user
  useradd -mG sudo dbrugan
  echo "dbrugan:$user_password" | chpasswd

  # install desktop environment and other userful packages
  apt install -y gnome-session gnome-console gnome-software nautilus flatpak \
    gnome-software-plugin-flatpak gnome-tweaks eog baobab gnome-control-center \
    gnome-disk-utility evince totem
  flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
  flatpak install flathub org.mozilla.firefox -y

  # install bootloader
  grub-install --target=x86_64-efi --efi-directory=/boot/efi bootloader-id=ubuntu --recheck
  update-grub
  
EOF

umount -R /mnt
