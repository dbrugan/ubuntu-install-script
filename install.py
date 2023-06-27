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
  #
  # configure system
  #
  # install bootloader
  #
  # post-install tasks
