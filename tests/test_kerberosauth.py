"""
Tests for kerberosauth.py — specifically the per-execution KRB5CCNAME isolation
that prevents concurrent job executions from sharing and corrupting the same
Kerberos credential cache (RUN-2869).
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Allow importing from contents/ without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'contents'))

import kerberosauth


def _make_mock_pexpect_process(exitstatus=0):
    """Return a mock pexpect process that behaves like a successful kinit."""
    proc = MagicMock()
    proc.exitstatus = exitstatus
    proc.read.return_value = b""
    proc.wait.return_value = None
    return proc


def _make_auth(exec_id="12345"):
    """Return a KerberosAuth instance with the given RD_JOB_EXECID."""
    log = MagicMock()
    return kerberosauth.KerberosAuth(
        krb5config=None,
        kinit_command="kinit",
        log=log,
        username="testuser@EXAMPLE.COM",
        password="secret",
    )


class TestKerberosAuthCacheIsolation(unittest.TestCase):
    """
    RUN-2869: Verify that each KerberosAuth instance gets its own
    Kerberos credential cache path, preventing concurrent executions
    from colliding on the shared default cache.
    """

    def test_instance_has_ccache_path_attribute(self):
        """Each KerberosAuth instance must expose a ccache_path attribute."""
        auth = _make_auth()
        # Fails before fix: AttributeError because ccache_path doesn't exist
        self.assertTrue(hasattr(auth, 'ccache_path'),
                        "KerberosAuth must have a ccache_path attribute set in __init__")

    def test_ccache_path_contains_rundeck_prefix(self):
        """The cache path must use a recognisable prefix so stale files are identifiable."""
        auth = _make_auth()
        self.assertIn("rundeck", auth.ccache_path,
                      "ccache_path should contain 'rundeck' to be distinguishable from system caches")

    def test_two_instances_with_different_exec_ids_use_different_caches(self):
        """
        Concurrent executions (different RD_JOB_EXECID values) must receive
        different cache paths so they cannot overwrite each other's tickets.
        This is the core regression test for the race condition in RUN-2869.
        """
        with patch.dict(os.environ, {"RD_JOB_EXECID": "111"}):
            auth1 = _make_auth()

        with patch.dict(os.environ, {"RD_JOB_EXECID": "222"}):
            auth2 = _make_auth()

        self.assertNotEqual(
            auth1.ccache_path, auth2.ccache_path,
            "Different execution IDs must produce different cache paths — "
            "sharing a path is the root cause of RUN-2869"
        )

    def test_get_ticket_sets_KRB5CCNAME_in_process_env(self):
        """
        After get_ticket() the process-level KRB5CCNAME must point to the
        instance's own ccache so that requests_kerberos reads from the right cache.
        """
        mock_proc = _make_mock_pexpect_process()

        with patch.dict(os.environ, {"RD_JOB_EXECID": "42"}, clear=False):
            with patch('pexpect.spawn', return_value=mock_proc):
                auth = _make_auth()
                auth.get_ticket()

            # After get_ticket the process env must contain the isolated path
            self.assertIn("KRB5CCNAME", os.environ,
                          "KRB5CCNAME must be set in os.environ after get_ticket()")
            self.assertEqual(
                os.environ["KRB5CCNAME"], auth.ccache_env,
                "os.environ['KRB5CCNAME'] must match the instance's ccache_env"
            )

    def test_get_ticket_passes_KRB5CCNAME_to_pexpect_subprocess(self):
        """
        kinit itself must also be launched with KRB5CCNAME in its environment,
        not just the parent process.
        """
        mock_proc = _make_mock_pexpect_process()

        with patch.dict(os.environ, {"RD_JOB_EXECID": "99"}, clear=False):
            with patch('pexpect.spawn', return_value=mock_proc) as mock_spawn:
                auth = _make_auth()
                auth.get_ticket()

        spawn_env = mock_spawn.call_args.kwargs.get('env', {})
        self.assertIn("KRB5CCNAME", spawn_env,
                      "KRB5CCNAME must be present in the env dict passed to pexpect.spawn")
        self.assertEqual(spawn_env["KRB5CCNAME"], auth.ccache_env)

    def test_cleanup_removes_ccache_file(self):
        """cleanup() must delete the temporary credential cache file if it exists."""
        auth = _make_auth()
        # create a dummy file at the ccache path
        with open(auth.ccache_path, 'w') as f:
            f.write("dummy")

        try:
            auth.cleanup()
            self.assertFalse(os.path.exists(auth.ccache_path),
                             "cleanup() must remove the ccache temp file")
        finally:
            # safety: remove if cleanup didn't (only relevant if test itself fails)
            if os.path.exists(auth.ccache_path):
                os.remove(auth.ccache_path)

    def test_cleanup_is_safe_when_file_does_not_exist(self):
        """cleanup() must not raise if the cache file was already removed."""
        auth = _make_auth()
        # Ensure the file does NOT exist
        if os.path.exists(auth.ccache_path):
            os.remove(auth.ccache_path)
        # Must not raise
        auth.cleanup()

    def test_concurrent_executions_do_not_collide(self):
        """
        Simulate 10 concurrent executions: each must get a unique cache path.
        This reproduces the scenario described in RUN-2869 (40 concurrent jobs).

        In production each winrm-exec.py invocation is a separate OS process, so
        RD_JOB_EXECID is always unique and os.environ is never shared across
        executions.  We verify the uniqueness property here sequentially to avoid
        the os.environ process-global race that would occur with threads.
        """
        results = []
        for i in range(10):
            with patch.dict(os.environ, {"RD_JOB_EXECID": str(i)}, clear=False):
                auth = _make_auth()
                results.append(auth.ccache_path)

        self.assertEqual(
            len(set(results)), len(results),
            f"Different RD_JOB_EXECID values produced duplicate cache paths: {results}"
        )


if __name__ == '__main__':
    unittest.main()
