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
sudo umount /mnt

sudo mount -o subvol=root /dev/mapper/sda2_crypt /mnt
sudo mkdir /mnt/home
sudo mount -o subvol=home /dev/mapper/sda2_crypt /mnt/home
sudo mkdir /mnt/.snapshots
sudo mount -o subvol=snapshots /dev/mapper/sda2_crypt /mnt/.snapshots

sudo apt install debootstrap
sudo debootstrap jammy /mnt

sudo mount --bind /dev /mnt/dev
sudo mount --bind /dev/pts /mnt/dev/pts
sudo mount --bind /proc /mnt/proc
sudo mount --bind /sys /mnt/sys
sudo cp /etc/resolv.conf /mnt/etc/resolv.conf

chroot /mnt /bin/bash <<EOF
export LANG=C
export DEBIAN_FRONTEND=noninteractive

apt update && apt install -y linux-image-generic grub-efi btrfs-progs cryptsetup flatpak pacstall neovim

flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

grub-install --target=x86_64-efi --efi-directory=/boot/efi bootloader-id=ubuntu --recheck
update-grub
EOF
# chroot /mnt apt install -y snapper flatpak gnome-desktop pacinstall neovim zsh



umount -R /mnt
cryptsetup close sda2_crypt
