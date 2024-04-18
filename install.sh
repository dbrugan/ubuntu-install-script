sudo parted /dev/sda mklabel gpt
sudo parted /dev/sda mkpart EFI fat32 1MiB 512MiB
sudo parted /dev/sda mkpart Root btrfs 512MiB 100%
sudo parted /dev/sda set 1 boot on

sudo cryptsetup luksFormat /dev/sda2
sudo cryptsetup open --type luks /dev/sda2 sda2_crypt
sudo mkfs.btrfs /dev/mapper/sda2_crypt 

sudo mount /dev/mapper/sda2_crypt /mnt

sudo btrfs subvolume create /mnt/root
sudo btrfs subvolume create /mnt/home
sudo btrfs subvolume create /mnt/snapshots
sudo btrfs subvolume create /mnt/cache
sudo btrfs subvolume create /mnt/log
sudo umount /mnt

sudo mount -o subvol=root /dev/mapper/sda2_crypt /mnt
sudo mkdir /mnt/home
sudo mount -o subvol=home /dev/mapper/sda2_crypt /mnt/home
sudo mkdir /mnt/.snapshots
sudo mount -o subvol=snapshots /dev/mapper/sda2_crypt /mnt/.snapshots
sudo mkdir -p /mnt/var/cache
sudo mount -o subvol=cache /dev/mapper/sda2_crypt /mnt/var/cache
sudo mkdir /mnt/var/log
sudo mount -o subvol=log /dev/mapper/sda2_crypt /mnt/var/log

sudo apt install debootstrap
sudo debootstrap jammy /mnt

sudo mount --bind /dev /mnt/dev
sudo mount --bind /dev/pts /mnt/dev/pts
sudo mount --bind /proc /mnt/proc
sudo mount --bind /sys /mnt/sys
sudo cp /etc/resolv.conf /mnt/etc/resolv.conf

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
