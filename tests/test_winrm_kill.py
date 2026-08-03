"""Unit tests for the abort/kill helpers in contents/winrm_kill.py.

These cover the pure logic (PID capture wrapping, marker parsing/stripping,
streaming filter and the terminate orchestration) without needing a live
Windows node. Run with:

    python -m pytest tests/
    # or
    python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "contents"))

import winrm_kill  # noqa: E402


class PreambleTests(unittest.TestCase):
    def test_powershell_preamble_uses_pid_variable(self):
        preamble = winrm_kill.pid_capture_preamble("powershell")
        self.assertIn(winrm_kill.PID_MARKER, preamble)
        self.assertIn("$PID", preamble)

    def test_cmd_preamble_uses_single_percent_for_loop(self):
        preamble = winrm_kill.pid_capture_preamble("cmd")
        self.assertIn(winrm_kill.PID_MARKER, preamble)
        # cmd /c one-liner must use single '%', never the batch-file '%%'.
        self.assertIn("%i", preamble)
        self.assertNotIn("%%", preamble)
        self.assertIn("ParentProcessId", preamble)

    def test_wrap_command_powershell_uses_script_block(self):
        wrapped = winrm_kill.wrap_command("param($x)\nWrite-Host $x", "powershell")
        self.assertTrue(wrapped.startswith("Write-Output"))
        self.assertIn(winrm_kill.PID_MARKER, wrapped)
        self.assertIn("$PID", wrapped)
        # User script must run inside a script block so a leading param() stays
        # valid (it becomes the first statement of the block).
        self.assertIn("& {", wrapped)
        self.assertIn("param($x)", wrapped)

    def test_wrap_command_cmd_prepends_preamble(self):
        wrapped = winrm_kill.wrap_command("C:\\tmp\\job.bat", "cmd")
        self.assertTrue(wrapped.endswith("C:\\tmp\\job.bat"))
        self.assertIn(winrm_kill.PID_MARKER, wrapped)


class ParseTests(unittest.TestCase):
    def test_parse_remote_pid_basic(self):
        text = "%s4321\r\n" % winrm_kill.PID_MARKER
        self.assertEqual(winrm_kill.parse_remote_pid(text), "4321")

    def test_parse_remote_pid_among_other_lines(self):
        text = "hello\r\n%s99\r\nworld\r\n" % winrm_kill.PID_MARKER
        self.assertEqual(winrm_kill.parse_remote_pid(text), "99")

    def test_parse_remote_pid_none_when_absent(self):
        self.assertIsNone(winrm_kill.parse_remote_pid("nothing here"))
        self.assertIsNone(winrm_kill.parse_remote_pid(""))
        self.assertIsNone(winrm_kill.parse_remote_pid(None))

    def test_parse_does_not_match_substring_in_other_text(self):
        # A non-numeric or embedded occurrence must not be captured.
        text = "see %sNaN for details" % winrm_kill.PID_MARKER
        self.assertIsNone(winrm_kill.parse_remote_pid(text))


class StripTests(unittest.TestCase):
    def test_strip_marker_line(self):
        text = "line1\r\n%s555\r\nline2\r\n" % winrm_kill.PID_MARKER
        self.assertEqual(winrm_kill.strip_pid_marker_lines(text), "line1\r\nline2\r\n")

    def test_strip_is_noop_without_marker(self):
        text = "just\r\nregular\r\noutput\r\n"
        self.assertEqual(winrm_kill.strip_pid_marker_lines(text), text)


class TaskkillTests(unittest.TestCase):
    def test_build_taskkill_command(self):
        self.assertEqual(
            winrm_kill.build_taskkill_command("777"),
            "taskkill /F /T /PID 777",
        )


class MarkerFilterTests(unittest.TestCase):
    def test_captures_pid_and_hides_marker(self):
        f = winrm_kill.MarkerFilter()
        out = f.feed("%s1234\r\nreal output\r\n" % winrm_kill.PID_MARKER)
        self.assertEqual(f.pid, "1234")
        self.assertNotIn(winrm_kill.PID_MARKER, out)
        self.assertIn("real output", out)

    def test_marker_split_across_chunks(self):
        f = winrm_kill.MarkerFilter()
        # Marker line arrives in two pieces; filter must buffer until newline.
        part1 = f.feed("%s56" % winrm_kill.PID_MARKER)
        self.assertEqual(part1, "")  # incomplete line held back
        self.assertIsNone(f.pid)
        part2 = f.feed("78\r\nhello\r\n")
        self.assertEqual(f.pid, "5678")
        self.assertNotIn(winrm_kill.PID_MARKER, part1 + part2)
        self.assertIn("hello", part1 + part2)

    def test_flush_emits_buffered_tail(self):
        f = winrm_kill.MarkerFilter()
        f.feed("trailing without newline")
        self.assertEqual(f.flush(), "trailing without newline")

    def test_regular_output_passes_through_unchanged(self):
        f = winrm_kill.MarkerFilter()
        out = f.feed("alpha\r\nbeta\r\n")
        out += f.flush()
        self.assertEqual(out, "alpha\r\nbeta\r\n")
        self.assertIsNone(f.pid)


class _FakeProtocol(object):
    def __init__(self):
        self.cleaned = None
        self.closed = None

    def cleanup_command(self, shell_id, command_id):
        self.cleaned = (shell_id, command_id)

    def close_shell(self, shell_id):
        self.closed = shell_id


class _FakeSession(object):
    def __init__(self):
        self.killed_with = None

    def run_cmd(self, command):
        self.killed_with = command

        class _R(object):
            std_out = b"SUCCESS"

        return _R()


class _FakeTracker(object):
    def __init__(self, pid):
        self.protocol = _FakeProtocol()
        self.session = _FakeSession()
        self.shell_id = "shell-1"
        self.command_id = "cmd-1"
        self.remote_pid = pid


class _SilentLog(object):
    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


class TerminateRemoteTests(unittest.TestCase):
    def test_terminate_sends_signal_and_taskkill(self):
        tracker = _FakeTracker("9090")
        winrm_kill.terminate_remote(tracker, _SilentLog())
        # WS-Man terminate signal sent for the running command.
        self.assertEqual(tracker.protocol.cleaned, ("shell-1", "cmd-1"))
        # Whole process tree force-killed via a fresh shell.
        self.assertEqual(tracker.session.killed_with, "taskkill /F /T /PID 9090")
        # Original shell closed.
        self.assertEqual(tracker.protocol.closed, "shell-1")

    def test_terminate_without_pid_still_sends_signal(self):
        tracker = _FakeTracker(None)
        winrm_kill.terminate_remote(tracker, _SilentLog())
        self.assertEqual(tracker.protocol.cleaned, ("shell-1", "cmd-1"))
        self.assertIsNone(tracker.session.killed_with)
        self.assertEqual(tracker.protocol.closed, "shell-1")

    def test_terminate_swallows_taskkill_errors(self):
        tracker = _FakeTracker("1")

        def boom(_):
            raise RuntimeError("network down")

        tracker.session.run_cmd = boom
        # Must not raise even though taskkill fails.
        winrm_kill.terminate_remote(tracker, _SilentLog())
        self.assertEqual(tracker.protocol.closed, "shell-1")


if __name__ == "__main__":
    unittest.main()
