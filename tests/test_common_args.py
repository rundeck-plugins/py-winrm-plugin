"""Unit tests for common.is_set_arg (WinRM Check step script-args handling)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "contents"))

import common  # noqa: E402


class IsSetArgTests(unittest.TestCase):
    def test_real_values_are_set(self):
        self.assertTrue(common.is_set_arg("http://proxy:3128"))
        self.assertTrue(common.is_set_arg("/etc/ssl/certs/ca.pem"))
        self.assertTrue(common.is_set_arg("127.0.0.1,.corp"))

    def test_missing_values_are_not_set(self):
        for value in (None, "", "None"):
            self.assertFalse(common.is_set_arg(value), value)

    def test_unexpanded_rundeck_reference_is_not_set(self):
        for value in ("${config.winrmproxy}", "${config.certpath}", "${config.winrmnoproxy}"):
            self.assertFalse(common.is_set_arg(value), value)


if __name__ == "__main__":
    unittest.main()
