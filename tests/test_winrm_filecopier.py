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

    def __init__(self, exists=False, test_path_code=0, claim_code=0,
                 claim_out=None):
        self.exists = exists
        self.test_path_code = test_path_code
        self.claim_code = claim_code
        self.claim_out = claim_out
        self.scripts = []
        self.written = b""
        # Called with the script just before a command runs, to let a test
        # simulate another copy acting at that moment.
        self.before_run = None

    def run_ps(self, script, retry=1, retry_delay=0):
        if self.before_run:
            self.before_run(script)
        self.scripts.append(script)
        if script.startswith("Test-Path"):
            out = b"True\r\n" if self.exists else b"False\r\n"
            return _Response(self.test_path_code, out)
        if "'CreateNew'" in script:
            if self.claim_out is not None:
                return _Response(self.claim_code, self.claim_out)
            out = b"EXISTS\r\n" if self.exists else b"CREATED\r\n"
            self.exists = True
            return _Response(self.claim_code, out)
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

    def _upload(self, session, override=False, if_exists=None):
        out = io.StringIO()
        with redirect_stdout(out):
            CopyFiles(session, 1, 0).winrm_upload(
                remote_path="C:\\tmp", remote_filename="file.txt",
                local_path=self.local, step=4, override=override,
                if_exists=if_exists)
        return out.getvalue()

    def _existing(self, **kwargs):
        session = _FakeSession(exists=True, **kwargs)
        session.written = b"original"
        return session

    @staticmethod
    def _wrote(session):
        return any(s.startswith("add-content") for s in session.scripts)

    @staticmethod
    def _claimed(session):
        return any("'CreateNew'" in s for s in session.scripts)

    # Not set: "Override?" decides, as before the setting existed.

    def test_default_new_file_is_written(self):
        session = _FakeSession(exists=False)
        out = self._upload(session)
        self.assertEqual(session.written, b"hello world")
        self.assertNotIn("WARNING", out)

    def test_default_appends_to_existing_file_and_warns(self):
        session = self._existing()
        out = self._upload(session)
        self.assertEqual(session.written, b"originalhello world")
        self.assertIn("WARNING", out)
        self.assertIn("C:\\tmp\\file.txt", out)
        self.assertIn("If destination exists", out)

    def test_default_failed_existence_check_still_copies(self):
        session = _FakeSession(exists=False, test_path_code=1)
        self._upload(session)
        self.assertEqual(session.written, b"hello world")

    def test_override_replaces_existing_file(self):
        session = self._existing()
        out = self._upload(session, override=True)
        self.assertEqual(session.written, b"hello world")
        self.assertFalse(any(s.startswith("Test-Path")
                             for s in session.scripts))
        self.assertNotIn("WARNING", out)

    # Explicit "If destination exists" values.

    def test_fail_new_file_is_written(self):
        session = _FakeSession(exists=False)
        self._upload(session, if_exists="fail")
        self.assertEqual(session.written, b"hello world")
        # The file is claimed with CreateNew, not checked with Test-Path.
        self.assertTrue(self._claimed(session))
        self.assertFalse(any(s.startswith("Test-Path")
                             for s in session.scripts))

    def test_fail_existing_file_raises_and_is_untouched(self):
        session = self._existing()
        with self.assertRaises(RemoteFileExistsError) as ctx:
            self._upload(session, if_exists="fail")
        self.assertIn("C:\\tmp\\file.txt", str(ctx.exception))
        self.assertEqual(session.written, b"original")
        self.assertFalse(self._wrote(session))

    def test_fail_second_copy_does_not_append(self):
        session = _FakeSession(exists=False)
        self._upload(session, if_exists="fail")
        with self.assertRaises(RemoteFileExistsError):
            self._upload(session, if_exists="fail")
        self.assertEqual(session.written, b"hello world")

    def test_fail_takes_precedence_over_override(self):
        session = self._existing()
        with self.assertRaises(RemoteFileExistsError):
            self._upload(session, override=True, if_exists="fail")
        self.assertEqual(session.written, b"original")

    def test_fail_failed_claim_raises(self):
        session = _FakeSession(exists=False, claim_code=1)
        with self.assertRaises(WinRmError):
            self._upload(session, if_exists="fail")
        self.assertFalse(self._wrote(session))

    def test_fail_unexpected_claim_output_raises(self):
        session = _FakeSession(exists=False, claim_out=b"")
        with self.assertRaises(WinRmError):
            self._upload(session, if_exists="fail")
        self.assertFalse(self._wrote(session))

    def test_fail_loses_to_writer_that_created_file_first(self):
        # Another copy creates the file after this one started but before
        # it claims the destination.
        session = _FakeSession(exists=False)

        def other_writer(script):
            if "'CreateNew'" in script and not session.exists:
                session.exists = True
                session.written = b"other"
        session.before_run = other_writer
        with self.assertRaises(RemoteFileExistsError):
            self._upload(session, if_exists="fail")
        self.assertEqual(session.written, b"other")
        self.assertFalse(self._wrote(session))

    def test_fail_overlapping_copies_write_once(self):
        # A second copy starts while the first is writing its first chunk.
        # With a separate exists check it saw no file yet and appended too.
        session = _FakeSession(exists=False)
        second = []

        def start_second(script):
            if script.startswith("add-content") and not second:
                second.append(True)
                with self.assertRaises(RemoteFileExistsError):
                    self._upload(session, if_exists="fail")
        session.before_run = start_second
        self._upload(session, if_exists="fail")
        self.assertTrue(second)
        self.assertEqual(session.written, b"hello world")

    def test_overwrite_replaces_existing_file(self):
        session = self._existing()
        self._upload(session, if_exists="overwrite")
        self.assertEqual(session.written, b"hello world")

    def test_append_appends_without_warning(self):
        session = self._existing()
        out = self._upload(session, override=True, if_exists="append")
        self.assertEqual(session.written, b"originalhello world")
        self.assertNotIn("WARNING", out)
        self.assertFalse(any(s.startswith("Test-Path")
                             for s in session.scripts))

    def test_invalid_value_raises_before_any_remote_call(self):
        session = self._existing()
        with self.assertRaises(ValueError) as ctx:
            self._upload(session, if_exists="replace")
        self.assertIn("replace", str(ctx.exception))
        self.assertEqual(session.scripts, [])


if __name__ == "__main__":
    unittest.main()
