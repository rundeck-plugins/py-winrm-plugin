"""Unit tests for CopyFiles.winrm_upload() in contents/winrm-filecopier.py.

winrm-filecopier.py parses argv and opens a WinRM session at import time, so
only the exception classes and CopyFiles are loaded from it (via ast) and
exercised against a fake session. No live Windows node is needed.
"""

import ast
import base64
import io
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "contents",
                       "winrm-filecopier.py")
_CLASSES = ("RemoteCommandError", "WinRmError", "RemoteFileExistsError",
            "CopyFiles")


def _load_classes():
    with open(_SCRIPT) as f:
        tree = ast.parse(f.read(), _SCRIPT)
    body = [n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name in _CLASSES]
    namespace = {"os": os, "sys": sys, "base64": base64, "time": time}
    exec(compile(ast.Module(body=body, type_ignores=[]), _SCRIPT, "exec"),
         namespace)
    return namespace


_ns = _load_classes()
CopyFiles = _ns["CopyFiles"]
WinRmError = _ns["WinRmError"]
RemoteFileExistsError = _ns["RemoteFileExistsError"]


class _Response(object):
    def __init__(self, status_code=0, std_out=b"", std_err=""):
        self.status_code = status_code
        self.std_out = std_out
        self.std_err = std_err


class _FakeSession(object):
    """Records scripts and simulates a single remote file."""

    def __init__(self, exists=False, test_path_code=0):
        self.exists = exists
        self.test_path_code = test_path_code
        self.scripts = []
        self.written = b""

    def run_ps(self, script, retry=1, retry_delay=0):
        self.scripts.append(script)
        if script.startswith("Test-Path"):
            out = b"True\r\n" if self.exists else b"False\r\n"
            return _Response(self.test_path_code, out)
        if " rm " in script:
            self.exists = False
            self.written = b""
        elif script.startswith("add-content"):
            chunk = script.split('FromBase64String("')[1].split('")')[0]
            self.written += base64.b64decode(chunk)
            self.exists = True
        return _Response()


class WinrmUploadTests(unittest.TestCase):
    def setUp(self):
        fd, self.local = tempfile.mkstemp()
        with os.fdopen(fd, "wb") as f:
            f.write(b"hello world")

    def tearDown(self):
        os.remove(self.local)

    def _upload(self, session, override):
        with redirect_stdout(io.StringIO()):
            CopyFiles(session, 1, 0).winrm_upload(
                remote_path="C:\\tmp", remote_filename="file.txt",
                local_path=self.local, step=4, override=override)

    def test_new_file_is_written(self):
        session = _FakeSession(exists=False)
        self._upload(session, override=False)
        self.assertEqual(session.written, b"hello world")

    def test_existing_file_without_override_fails_and_is_untouched(self):
        session = _FakeSession(exists=True)
        session.written = b"original"
        with self.assertRaises(RemoteFileExistsError) as ctx:
            self._upload(session, override=False)
        self.assertIn("C:\\tmp\\file.txt", str(ctx.exception))
        self.assertIn("Override", str(ctx.exception))
        self.assertEqual(session.written, b"original")
        self.assertFalse(any(s.startswith("add-content")
                             for s in session.scripts))

    def test_second_copy_without_override_does_not_append(self):
        session = _FakeSession(exists=False)
        self._upload(session, override=False)
        with self.assertRaises(RemoteFileExistsError):
            self._upload(session, override=False)
        self.assertEqual(session.written, b"hello world")

    def test_override_replaces_existing_file(self):
        session = _FakeSession(exists=True)
        session.written = b"original"
        self._upload(session, override=True)
        self.assertEqual(session.written, b"hello world")
        self.assertFalse(any(s.startswith("Test-Path")
                             for s in session.scripts))

    def test_failed_existence_check_raises(self):
        session = _FakeSession(exists=False, test_path_code=1)
        with self.assertRaises(WinRmError):
            self._upload(session, override=False)
        self.assertFalse(any(s.startswith("add-content")
                             for s in session.scripts))


if __name__ == "__main__":
    unittest.main()
