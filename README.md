# Ubuntu Installation Script

Python script for installing Ubuntu with debootstrap, BTRFS, LUKS encryption, and Hyprland.

## Requirements

- Running Ubuntu (or any Linux with apt)
- Root access (script prompts for sudo)

## Usage

```bash
sudo ./install.py
```

## Features

- LUKS encrypted root
- BTRFS with subvolumes (`@`, `@home`, `@cache`, `@log`)
- UEFI boot partition
- Limine bootloader
- Hyprland + SDDM
- NetworkManager
- Flatpak with Flathub
- Optional: Block snaps, cloud-init, landscape-common, popularity-contest, ubuntu-advantage-tools
