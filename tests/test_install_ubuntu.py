import unittest
import os
import subprocess
from unittest.mock import patch, call
from install_ubuntu import install_ubuntu, run_command

class TestInstallUbuntu(unittest.TestCase):
    def setUp(self):
        self.debootstrap_dir = "/tmp/test_ubuntu"
        self.mirror_url = "http://archive.ubuntu.com/ubuntu"
        self.release = "noble"

    def tearDown(self):
        if os.path.exists(self.debootstrap_dir):
            os.rmdir(self.debootstrap_dir)

    @patch('subprocess.Popen')
    def test_directory_creation(self, mock_popen):
        # Mock the popen to avoid actual execution
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = (b", b")

        install_ubuntu(self.debootstrap_dir, self.mirror_url, self.release)

        # Check if the directory was created
        self.assertTrue(os.path.exists(self.debootstrap_dir))

if __name__ == '__main__':
    unittest.main()
