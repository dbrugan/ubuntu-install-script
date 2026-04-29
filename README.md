# Ubuntu Installation Script

My personal script for installing Ubuntu with debootstrap.

## Requirements

- Running Ubuntu (or any Linux with apt)
- Root access (script prompts for sudo)

## Usage

### One-liner (live environment)

```bash
curl -sL https://raw.githubusercontent.com/dbrugan/ubuntu-install-script/test/install.sh | sudo bash
```

### Manual

```bash
# Clone repo
git clone https://github.com/dbrugan/ubuntu-install-script.git
cd ubuntu-install-script

# Switch to branch
git checkout test

# Run
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
