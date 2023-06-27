import subprocess

  # step 1: partitioning
subprocess.run(["parted", "/dev/sda", "mklabel", "gpt"])
subprocess.run(["parted", "/dev/sda", "mkpart", "EFI", "fat32", "1MiB", "512MiB"])
subprocess.run(["parted", "/dev/sda", "mkpart", "Root", "ext4", "512MiB", "100%"])
subprocess.run(["parted", "/dev/sda", "set", "1", "boot", "on"])
  # step 2: format partitions
  #
  # step 3: mount partitions
  #
  # step 4: install base system
  #
  # step 5: configure system
  #
  # step 6: install bootloader
  #
  # step 7: post-install tasks
