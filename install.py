import subprocess

  # partitioning
subprocess.run(["parted", "/dev/sda", "mklabel", "gpt"])

  # format partitions
subprocess.run(["parted", "/dev/sda", "mkpart", "EFI", "fat32", "1MiB", "512MiB"])
subprocess.run(["parted", "/dev/sda", "mkpart", "Root", "btrfs", "512MiB", "100%"])
subprocess.run(["parted", "/dev/sda", "set", "1", "boot", "on"])

  # encrypt partitions
subprocess.run(["cryptsetup", "luksFormat", "/dev/sda2"])
subprocess.run(["cryptsetup", "open", "--type", "luks", "/dev/sda2", "sda2_crypt"])
subprocess.run(["mkfs.btrfs", "/dev/mapper/sda2_crypt"]) 

  # mount partitions
subprocess.run(["mount", "/dev/mapper/sda2_crypt", "/mnt"])

 # creating btrfs subvolumes
subprocess.run(["btrfs", "subvolume", "create", "/mnt/root"])
subprocess.run(["btrfs", "subvolume", "create", "/mnt/home"])
subprocess.run(["btrfs", "subvolume", "create", "/mnt/snapshots"])
subprocess.run(["umount", "/mnt"])

 # mount subvolumes
subprocess.run(["mount", "-o", "subvol=root", "/dev/mapper/sda2_crypt", "/mnt"])
subprocess.run(["mkdir", "/mnt/home"])
subprocess.run(["mount", "-o", "subvol=home", "/dev/mapper/sda2_crypt", "/mnt/home"])
subprocess.run(["mkdir", "/mnt/.snapshots"])
subprocess.run(["mount", "-o", "subvol=snapshots", "/dev/mapper/sda2_crypt", "/mnt/.snapshots"])

  # install base system
subprocess.run(["debootstrap", "focal", "/mnt"])

  # mount directories
subprocess.run(["mount", "--bind", "/dev", "/mnt/dev"])
subprocess.run(["mount", "--bind", "/dev/pts", "/mnt/dev/pts"])
subprocess.run(["mount", "--bind", "/proc", "/mnt/proc"])
subprocess.run(["mount", "--bind", "/sys", "/mnt/sys"])
subprocess.run(["cp", "/etc/resolv.conf", "/mnt/etc/resolv.conf"])

  # configure system
subprocess.run(["chroot", "/mnt", "apt", "update"])
subprocess.run(["chroot", "/mnt", "apt", "install", "-y", "snapper", "flatpak", "gnome-desktop", "pacinstall", "neovim"])

 # add flathub repository
subprocess.run(["chroot", "/mnt", "flatpak", "remote-add", "--if-not-exists", "flathub", "https://flathub.org/repo/flathub.flatpakrepo"])

  # install bootloader
subprocess.run(["chroot", "/mnt", "grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi", "--bootloader-id=ubuntu", "--recheck"])
subprocess.run(["chroot", "/mnt", "update-grub"])

  # cleaning up
subprocess.run(["umount", "-R", "/mnt"])
subprocess.run(["cryptsetup", "close", "sda2_crypt"])

print("Installation completed.")
