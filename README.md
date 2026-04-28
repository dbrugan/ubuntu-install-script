# Ubuntu Installation Script

My personal script for installing Ubuntu with debootstrap.

## Usage

Run with sudo:

```bash
sudo ./install.sh
# or
sudo ./install.py
```

Enter the disk device when prompted (e.g., `/dev/sda`).

## Features

- LUKS encrypted root
- BTRFS with subvolumes (@, @home, @cache, @log)
- Limine bootloader
- Hyprland desktop
- SDDM with Xorg
- NetworkManager
- Blocks: snapd, cloud-init, landscape-common, popularity-contest, ubuntu-advantage-tools