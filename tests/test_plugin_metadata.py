"""Tests for the node executor's generic remote-shell metadata."""

from pathlib import Path
import unittest


class PluginMetadataTests(unittest.TestCase):
    def test_winrm_executor_resolves_remote_shell_from_config(self):
        plugin_yaml = (Path(__file__).parent.parent / "plugin.yaml").read_text()
        executor = plugin_yaml.split("- name: WinRMPython", 1)[1].split(
            "- name: WinRMcpPython", 1
        )[0]

        self.assertIn("plugin-meta:", executor)
        self.assertIn("remote-command-shell: '${config.shell}'", executor)


if __name__ == "__main__":
    unittest.main()
