"""Unit tests for common.split_destination, used by winrm-filecopier.py to
split the remote destination into directory and filename. Run with:

    python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "contents"))

import common  # noqa: E402


class SplitDestinationTests(unittest.TestCase):
    SOURCE = "/tmp/rundeck/local-file.txt"

    def split(self, destination):
        return common.split_destination(destination, self.SOURCE)

    def test_normal_dispatch_path(self):
        self.assertEqual(
            self.split("C:\\Windows\\TEMP\\123-dispatch.ps1"),
            ("C:\\Windows\\TEMP\\", "123-dispatch.ps1"),
        )

    def test_filename_also_in_parent_directory(self):
        self.assertEqual(
            self.split("C:\\deploy\\app\\app"),
            ("C:\\deploy\\app\\", "app"),
        )

    def test_single_character_filename(self):
        self.assertEqual(
            self.split("C:\\Users\\admin\\Desktop\\a"),
            ("C:\\Users\\admin\\Desktop\\", "a"),
        )

    def test_trailing_backslash_uses_source_filename(self):
        self.assertEqual(
            self.split("C:\\Users\\admin\\Desktop\\"),
            ("C:\\Users\\admin\\Desktop\\", "local-file.txt"),
        )

    def test_trailing_forward_slash_uses_source_filename(self):
        self.assertEqual(
            self.split("C:/Users/admin/Desktop/"),
            ("C:/Users/admin/Desktop/", "local-file.txt"),
        )

    def test_forward_slashes(self):
        self.assertEqual(
            self.split("C:/Users/admin/Desktop/report.csv"),
            ("C:/Users/admin/Desktop/", "report.csv"),
        )

    def test_mixed_separators(self):
        self.assertEqual(
            self.split("C:\\Users/admin\\file.txt"),
            ("C:\\Users/admin\\", "file.txt"),
        )

    def test_file_in_drive_root(self):
        self.assertEqual(self.split("C:\\file.txt"), ("C:\\", "file.txt"))


if __name__ == "__main__":
    unittest.main()
