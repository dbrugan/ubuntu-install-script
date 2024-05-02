#!/bin/bash

disk="/dev/sda"

# get root password
echo "Choose the root password:"
read -s root_password

# get user password
echo "Choose the password for the user:"
read -s user_password

# Erase previous disk info
wipefs -af "$disk"
sgdisk -Zo "$disk"

# creating partitions
parted --script "$disk" mklabel gpt
parted --script "$disk" mkpart ESP fat32 1MiB 513MiB
parted --script "$disk" set 1 esp on
parted --script "$disk" mkpart primary ext4 513MiB 1.5GiB
parted --script "$disk" mkpart CRYPTROOT btrfs 1.5GiB 100%

# formatting partitions
mkfs.fat -F 32 "${disk}1"
mkfs.ext4 "${disk}2"
cryptsetup luksFormat "${disk}3"
cryptsetup open "${disk}3" cryptroot
mkfs.btrfs --force /dev/mapper/cryptroot

# configure btrfs subvolumes
mount /dev/mapper/cryptroot /mnt

btrfs subvolume create /mnt/@
btrfs subvolume create /mnt/@home
btrfs subvolume create /mnt/@snapshots
btrfs subvolume create /mnt/@cache
btrfs subvolume create /mnt/@log

umount /mnt

# mounting system partitions
mount_options="noatime,discard,compress=zstd,ssd,space_cache=v2,commit=120,autodefrag"
mount -o "subvol=@,$mount_options" /dev/mapper/cryptroot /mnt
mkdir -p /mnt/{home,.snapshots,var/{cache,log}} # creating directories for mounting the subvolumes
mount -o "subvol=@home,$mount_options" /dev/mapper/cryptroot /mnt/home
mount -o "subvol=@snapshots,$mount_options" /dev/mapper/cryptroot /mnt/.snapshots
mount -o "subvol=@cache,$mount_options" /dev/mapper/cryptroot /mnt/var/cache
mount -o "subvol=@log,$mount_options" /dev/mapper/cryptroot /mnt/var/log
mkdir /mnt/boot # creating boot mounting directory
mount "${disk}2" /mnt/boot
mkdir /mnt/boot/efi # creating esp mounting directory
mount "${disk}1" /mnt/boot/efi

# enable universe repository and install necessary tools
add-apt-repository universe && apt update && apt install -y debootstrap arch-install-scripts

# installing base system
debootstrap noble /mnt

# create new mounting table
genfstab -U /mnt >> /mnt/etc/fstab

# enabling repositories
sources="\
deb http://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-security main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu noble-backports main restricted universe multiverse
"

echo "$sources" > /mnt/etc/apt/sources.list

# configure apt to not install certain packages

blacklist="\
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
"

echo "$blacklist" > /mnt/etc/apt/preferences.d/ignored-packages.pref

# Get the UUID of the encrypted partition
root_uuid=$(blkid -s UUID -o value ${disk}3)

# Set Bash as the default shell for new users
echo 'SHELL=/bin/bash' >> /mnt/etc/default/useradd

# define zram config file
zram_config="\
[zram0]
zram-size = min(ram, 8192)
"

# chroot in the installed system
arch-chroot /mnt <<EOF
  export LANG=C
  export DEBIAN_FRONTEND=noninteractive

  # install base system utils
  apt update && apt install -y --no-install-recommends \
    linux-image-generic linux-firmware grub-efi btrfs-progs bash \
    neovim initramfs-tools cryptsetup cryptsetup-initramfs efibootmgr \
    systemd-zram-generator systemd-oomd

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

  # configure crypttab
  echo "cryptroot UUID=$root_uuid none luks,discard" >> /etc/crypttab

  # configure bootloader
  sed -i "/^GRUB_CMDLINE_LINUX=/ s/\"$/ cryptdevice=UUID=${root_uuid}:cryptroot\"/" /etc/default/grub
  grub-install --target=x86_64-efi --efi-directory=/boot/efi bootloader-id=ubuntu --recheck
  update-grub
  
  # update initramfs
  update-initramfs -u
  update-grub

  # configure zram
  echo "$zram_config" >> /etc/systemd/zram-generator.conf

  # cleaning unwanted files
  rm /etc/apt/preferences.d/ubuntu-pro-esm-apps
  rm /etc/apt/preferences.d/ubuntu-pro-esm-infra

  # install desktop environment and other userful packages
  apt install -y --no-install-recommends \
    gnome-session gnome-shell gdm3 gnome-console gnome-software \
    gnome-menus nautilus libgdk-pixbuf2.0-bin librsvg2-common \
    flatpak gnome-software-plugin-flatpak power-profiles-daemon \
    gnome-tweaks eog baobab gjs gnome-control-center gnome-disk-utility \
    gnome-bluetooth gnome-sushi gvfs gvfs-backends evince totem \
    bluez btop cups dosfstools e2fsprogs exfatprogs mtools ntfs-3g \
    fwupd fwupd-signed fonts-noto-color-emoji gamemode nala network-manager \
    packagekit udisks2 yaru-theme-gtk yaru-theme-sound yaru-theme-icon \
    timeshift wpasupplicant xdg-utils xdg-user-dirs-gtk xdg-user-dirs
  flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
  flatpak install -y flathub \
    org.mozilla.firefox
    com.mattjakeman.ExtensionManager
    org.gnome.FileRoller

EOF

umount -R /mnt
