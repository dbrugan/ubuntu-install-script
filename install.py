import subprocess

  # partitioning
subprocess.run(["parted", "/dev/sda", "mklabel", "gpt"])

  # format partitions
subprocess.run(["parted", "/dev/sda", "mkpart", "EFI", "fat32", "1MiB", "512MiB"])
subprocess.run(["parted", "/dev/sda", "mkpart", "Root", "ext4", "512MiB", "100%"])
subprocess.run(["parted", "/dev/sda", "set", "1", "boot", "on"])

  # encrypt partitions
subprocess.run(["cryptsetup", "luksFormat", "/dev/sda2"])
subprocess.run(["cryptsetup", "open", "--type", "luks", "/dev/sda2", "sda2_crypt"])
subprocess.run(["mkfs.ext4", "/dev/mapper/sda2_crypt"]) 

  # mount partitions
  #
  # step 4: install base system
  #
  # step 5: configure system
  #
  # step 6: install bootloader
  #
  # step 7: post-install tasks
