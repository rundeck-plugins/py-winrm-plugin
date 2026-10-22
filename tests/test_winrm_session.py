"""Unit tests for RunCommand shell dispatch in contents/winrm_session.py.

An unsupported shell value (e.g. node attribute ``winrm-shell=PowerShell``)
must fail instead of silently running nothing and exiting 0. Run with:

    python -m unittest discover -s tests
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "contents"))

# winrm_session imports ConnectionError from requests at module level. Stub it
# only when requests is not installed so these tests run without plugin deps.
try:
    import requests  # noqa: F401
except ImportError:
    _requests_stub = types.ModuleType("requests")
    _requests_stub.ConnectionError = ConnectionError
    sys.modules["requests"] = _requests_stub

import winrm_session  # noqa: E402


class FakeSession(object):
    """Records which run_* method was called and returns a fixed Response."""

    def __init__(self):
        self.calls = []

    def run_cmd(self, command, **kwargs):
        self.calls.append(("run_cmd", command))
        return winrm_session.Response(("out", "", 0))

    def run_ps(self, command, **kwargs):
        self.calls.append(("run_ps", command))
        return winrm_session.Response(("out", "", 0))


def _run(shell):
    session = FakeSession()
    tsk = winrm_session.RunCommand(session, shell, "whoami", 1, 0)
    tsk.get_response()
    return session, tsk


class RunCommandShellTests(unittest.TestCase):
    def test_cmd_dispatches_to_run_cmd(self):
        session, tsk = _run("cmd")
        self.assertEqual(session.calls, [("run_cmd", "whoami")])
        self.assertEqual(tsk.stat, 0)

    def test_powershell_dispatches_to_run_ps(self):
        session, tsk = _run("powershell")
        self.assertEqual(session.calls, [("run_ps", "whoami")])
        self.assertEqual(tsk.stat, 0)

    def test_unsupported_shell_fails_with_error(self):
        for shell in ("PowerShell", "pwsh", "powershell ", "bash", ""):
            session, tsk = _run(shell)
            self.assertEqual(session.calls, [], shell)
            self.assertIsNotNone(tsk.stat, shell)
            self.assertNotEqual(tsk.stat, 0, shell)
            self.assertIn("Unsupported shell '%s'" % shell, tsk.e_std)
            self.assertIn("cmd, powershell", tsk.e_std)


if __name__ == "__main__":
    unittest.main()
