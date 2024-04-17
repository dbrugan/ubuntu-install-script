sudo parted /dev/sda mklabel gpt
sudo parted /dev/sda mkpart EFI fat32 1MiB 512MiB
sudo parted /dev/sda mkpart Root btrfs 512MiB 100%
sudo parted /dev/sda set 1 boot on

sudo cryptsetup luksFormat /dev/sda2
sudo cryptsetup open --type luks /dev/sda2 sda2_crypt
sudo mkfs.btrfs /dev/mapper/sda2_crypt 

mount /dev/mapper/sda2_crypt /mnt

btrfs subvolume create /mnt/root
btrfs subvolume create /mnt/home
btrfs subvolume create /mnt/snapshots
umount /mnt

mount -o subvol=root /dev/mapper/sda2_crypt /mnt
mkdir /mnt/home
mount -o subvol=home /dev/mapper/sda2_crypt /mnt/home
mkdir /mnt/.snapshots
mount -o subvol=snapshots /dev/mapper/sda2_crypt /mnt/.snapshots

debootstrap jammy /mnt

mount --bind /dev /mnt/dev
mount --bind /dev/pts /mnt/dev/pts
mount --bind /proc /mnt/proc
mount --bind /sys /mnt/sys
cp /etc/resolv.conf /mnt/etc/resolv.conf

chroot /mnt /bin/bash <<EOF
export LANG=C
export DEBIAN_FRONTEND=noninteractive

apt update && apt install -y linux-image-generic grub-efi btrfs-progs cryptsetup flatpak pacstall neovim
EOF
# chroot /mnt apt install -y snapper flatpak gnome-desktop pacinstall neovim zsh

# chroot /mnt flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# chroot /mnt grub-install --target=x86_64-efi --efi-directory=/boot/efi bootloader-id=ubuntu --recheck
# chroot /mnt update-grub

umount -R /mnt
cryptsetup close sda2_crypt
