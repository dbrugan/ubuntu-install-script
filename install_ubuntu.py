import os
import subprocess

# run a shell command, capture the output and print it. if the command fails, raise an exception.
def run_command(command):
    """Run a command in a shell, wait for it to complete."""
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(f"Error: {stderr.decode('utf-8')}")
        raise Exception(f"Command failed: {command}")
    print(f"Output: {stdout.decode('utf-8')}")

def install_ubuntu(debootstrap_dir, mirror_url, release):
    """Install Ubuntu using debootstrap."""
    print(f"Installing Ubuntu {release} in {debootstrap_dir} using {mirror_url}...")

    # Create directory if it doesn't exist
    debootstrap_command = f"sudo debootstrap {release} {debootstrap_dir} {mirror_url}"
    run_command(debootstrap_command)

    print(f"Ubuntu installation complete.")

if __name__ == "__main__":
    # Usage: python install_ubuntu.py <directory> <mirror_url> <release>

    # Configuration
    debootstrap_dir = "/mnt/ubuntu"
    mirror_url = "http://archive.ubuntu.com/ubuntu"
    release = "noble" # Change this to the release you want to install (e.g. "focal")

    # Install Ubuntu
    install_ubuntu(debootstrap_dir, mirror_url, release)
