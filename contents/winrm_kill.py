"""Remote process-tree termination support for the WinRM node executor.

When a Rundeck job is aborted, the local ``winrm-exec.py`` process receives a
termination signal (SIGTERM/SIGINT). By default the Python process simply dies,
but the command launched over WinRM keeps running on the Windows node together
with any child processes it spawned (this is the root cause of RUN-3009).

This module provides the building blocks to fix that:

* a small *preamble* that makes the remote shell print its own PID using a
  recognizable marker line, so we can learn the root PID of the process tree;
* helpers to parse that PID out of the streamed output and to hide the marker
  line from the user-visible output;
* :func:`terminate_remote`, which on abort sends the WS-Man ``terminate`` signal
  and then force-kills the whole remote process tree with ``taskkill /F /T``.

All of the parsing/wrapping helpers are pure functions so they can be unit
tested without a live Windows node.
"""

import re
import uuid

# Marker emitted by the remote shell so we can capture the root PID of the
# process tree that WinRM started. Kept intentionally unlikely to collide with
# real script output.
PID_MARKER = "RUNDECK:WINRM:REMOTE_PID:"

# Matches a marker line and captures the PID. Tolerates surrounding whitespace
# and Windows CRLF line endings.
_PID_CAPTURE_RE = re.compile(
    r"(?m)^[ \t]*" + re.escape(PID_MARKER) + r"(\d+)[ \t]*\r?$"
)

# Matches a full marker line including its trailing newline, used to strip the
# marker from the user-visible output.
_PID_STRIP_RE = re.compile(
    r"(?m)^[ \t]*" + re.escape(PID_MARKER) + r"\d+[ \t]*\r?\n?"
)


def build_capture_token(seed=None):
    """Return a unique token usable to disambiguate the remote shell process."""
    base = seed if seed else uuid.uuid4().hex
    return "RD_WINRM_KILLTOKEN_%s" % base


def pid_capture_preamble(shell, token=None):
    """Return a shell snippet that prints the current shell PID as a marker.

    For ``powershell`` this uses the automatic ``$PID`` variable. For ``cmd`` we
    resolve the PID of the current ``cmd.exe`` by asking a short-lived child
    PowerShell process for its parent PID (works on all supported Windows
    versions and does not depend on the deprecated ``wmic`` tool).
    """
    if shell == "powershell":
        return 'Write-Output "%s$PID"; ' % PID_MARKER

    # cmd.exe: a child PowerShell reports our (the parent cmd) PID. Single quotes
    # are used inside the -Command argument to avoid nested double quotes.
    # The command is executed via "cmd /c" (a one-liner, not a .bat file), so the
    # FOR variable uses a single '%'.
    ps = (
        "powershell -NoProfile -Command "
        "\"(Get-CimInstance Win32_Process -Filter ('ProcessId='+$PID))"
        ".ParentProcessId\""
    )
    return (
        '@for /f "usebackq tokens=*" %i in (`' + ps + '`) do '
        "@echo " + PID_MARKER + "%i& "
    )


def wrap_command(command, shell, token=None):
    """Wrap ``command`` so the remote shell reports its PID before running it.

    For ``powershell`` the user script is executed inside a ``& { ... }`` script
    block so that a leading ``param()`` block in the user script remains valid
    (PowerShell requires ``param()`` to be the first statement of its block).
    For ``cmd`` the preamble is simply prepended.
    """
    if shell == "powershell":
        return 'Write-Output "%s$PID"; & {\n%s\n}' % (PID_MARKER, command)
    return pid_capture_preamble(shell, token) + command


def parse_remote_pid(text):
    """Return the first remote PID found in ``text`` as a string, or ``None``."""
    if not text:
        return None
    match = _PID_CAPTURE_RE.search(text)
    if match:
        return match.group(1)
    return None


def strip_pid_marker_lines(text):
    """Return ``text`` with any PID marker lines removed."""
    if not text:
        return text
    return _PID_STRIP_RE.sub("", text)


def build_taskkill_command(pid):
    """Return the cmd command that force-kills the process tree rooted at pid."""
    return "taskkill /F /T /PID %s" % pid


class MarkerFilter(object):
    """Streaming filter that captures the remote PID and hides the marker line.

    Output arrives in arbitrary chunks, so a marker line may be split across two
    reads. The filter buffers the trailing (incomplete) line until a newline is
    seen, guaranteeing marker lines are processed whole.
    """

    def __init__(self):
        self.buffer = ""
        self.pid = None

    def feed(self, text):
        """Feed a chunk of decoded output, return text safe to display."""
        if not text:
            return ""
        data = self.buffer + text
        newline_idx = data.rfind("\n")
        if newline_idx == -1:
            # No complete line yet, hold everything back.
            self.buffer = data
            return ""
        complete = data[: newline_idx + 1]
        self.buffer = data[newline_idx + 1:]
        return self._process(complete)

    def flush(self):
        """Return any buffered text (after a final marker check)."""
        remaining = self._process(self.buffer)
        self.buffer = ""
        return remaining

    def _process(self, text):
        if self.pid is None:
            found = parse_remote_pid(text)
            if found:
                self.pid = found
        return strip_pid_marker_lines(text)


def terminate_remote(tracker, log):
    """Abort the remote command and kill its whole process tree.

    ``tracker`` is expected to expose ``protocol``, ``shell_id``, ``command_id``,
    ``session`` and ``remote_pid``. Every step is best-effort: failures are
    logged but never raised, since this runs while the job is being aborted.
    """
    # 1) Ask WinRM to terminate the running command (graceful, unblocks receive).
    try:
        if tracker.protocol and tracker.shell_id and tracker.command_id:
            log.debug("Sending WS-Man terminate signal to the remote command")
            tracker.protocol.cleanup_command(tracker.shell_id, tracker.command_id)
    except Exception as e:
        log.debug("WS-Man terminate signal failed: %s" % e)

    # 2) Force-kill the whole remote process tree from a fresh shell. This is the
    #    step that actually stops orphaned child processes (RUN-3009).
    pid = getattr(tracker, "remote_pid", None)
    if pid:
        try:
            kill_cmd = build_taskkill_command(pid)
            log.warning(
                "Abort requested: killing remote process tree (PID %s) via taskkill"
                % pid
            )
            result = tracker.session.run_cmd(kill_cmd)
            log.debug("taskkill result: %s" % getattr(result, "std_out", b""))
        except Exception as e:
            log.error("Remote taskkill for PID %s failed: %s" % (pid, e))
    else:
        log.warning(
            "Abort requested but no remote PID was captured; only the WS-Man "
            "terminate signal was sent. Child processes on the node may survive."
        )

    # 3) Close the original shell to release server-side resources.
    try:
        if tracker.protocol and tracker.shell_id:
            tracker.protocol.close_shell(tracker.shell_id)
    except Exception as e:
        log.debug("close_shell failed: %s" % e)
