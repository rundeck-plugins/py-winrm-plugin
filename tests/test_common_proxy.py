"""Unit tests for proxy URL redaction in contents/common.py.

Run with:

    python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "contents"))

import common  # noqa: E402


class RedactProxyUrlTests(unittest.TestCase):
    def test_http_credentials_removed(self):
        redacted = common._redact_proxy_url("http://user:secret@proxy:3128")
        self.assertEqual(redacted, "http://proxy:3128")
        self.assertNotIn("secret", redacted)
        self.assertNotIn("user", redacted)

    def test_socks5_credentials_removed(self):
        redacted = common._redact_proxy_url("socks5://user:secret@proxy.example.com:1080")
        self.assertEqual(redacted, "socks5://proxy.example.com:1080")

    def test_username_only_removed(self):
        self.assertEqual(common._redact_proxy_url("http://user@proxy:3128"), "http://proxy:3128")

    def test_path_kept(self):
        self.assertEqual(
            common._redact_proxy_url("http://user:secret@proxy:3128/path"),
            "http://proxy:3128/path",
        )

    def test_no_port_kept_without_port(self):
        self.assertEqual(common._redact_proxy_url("http://user:secret@proxy"), "http://proxy")

    def test_url_without_credentials_unchanged(self):
        url = "http://proxy.example.com:3128"
        self.assertEqual(common._redact_proxy_url(url), url)

    def test_none_and_empty_unchanged(self):
        self.assertIsNone(common._redact_proxy_url(None))
        self.assertEqual(common._redact_proxy_url(""), "")


if __name__ == "__main__":
    unittest.main()
