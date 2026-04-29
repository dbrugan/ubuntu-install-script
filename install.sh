#!/bin/bash
set -e

sudo apt update && sudo apt install -y git

REPO="dbrugan/ubuntu-install-script"
REF="test"
INSTALL_DIR="${HOME}/.local/share/ubuntu-install-script"

echo -e "\nCloning from: https://github.com/${REPO}.git"
rm -rf "$INSTALL_DIR"
git clone "https://github.com/${REPO}.git" "$INSTALL_DIR" >/dev/null

echo -e "\e[32mUsing branch: $REF\e[0m"
cd "$INSTALL_DIR"
git checkout "${REF}"
cd -

echo -e "\nInstallation starting..."
sudo "$INSTALL_DIR/install.py"