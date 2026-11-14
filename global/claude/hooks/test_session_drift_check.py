"""Tests for session_drift_check.py. Every run uses a temporary home and marker folder, never the real ones."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import session_drift_check as drift  # noqa: E402

sys.path.insert(0, os.path.join(drift.SDK, "global"))
sys.path.insert(0, drift.PLUGIN_SCRIPTS)
import deploy  # noqa: E402
import register_claude  # noqa: E402

SETTINGS = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": 'python "Q:/old/layer_rules.py"'}]}]}}


class DriftTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.markers = Path(self._tmp.name) / "markers"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(deploy.main(["--home", str(self.home), "--agent", "claude"]), 0)
        self.servers = {name: {"type": "stdio", "command": register_claude.node_command(),
                               "args": [str(register_claude.ROOT / name / "dist" / "server.mjs")], "env": {}}
                        for name in register_claude.PLUGINS}
        self.write_servers()

    def write_servers(self):
        (self.home / ".claude.json").write_text(json.dumps({"mcpServers": self.servers}), encoding="utf-8")

    def hook(self, session):
        """Run the hook as Claude Code does, with the temporary home as the user's home."""
        env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home), CLAUDE_DRIFT_DIR=str(self.markers))
        done = subprocess.run([sys.executable, os.path.join(HERE, "session_drift_check.py")],
                              input=json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": session}),
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done

    def test_a_clean_setup_is_silent(self):
        self.assertEqual(drift.check(self.home), [])
        done = self.hook("clean")
        self.assertEqual((done.stdout, done.stderr), ("", ""))

    def test_a_changed_deployed_file_is_reported(self):
        (self.home / ".claude" / "CLAUDE.md").write_text("edited by hand\n", encoding="utf-8")
        self.assertEqual(drift.check(self.home), ["deployed files differ from global/claude: ~/.claude/CLAUDE.md"])

    def test_an_unwired_drift_hook_is_reported(self):
        (self.home / ".claude" / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
        self.assertEqual(drift.check(self.home),
                         ["deployed files differ from global/claude: ~/.claude/settings.json (hook paths)"])

    def test_a_plugin_on_the_retired_checkout_or_unregistered_is_reported(self):
        self.servers["bunny-net"]["args"] = ["R:\\Bin\\claude\\connections\\bunny-net\\dist\\server.mjs"]
        del self.servers["domains-co-za"]
        self.write_servers()
        self.assertEqual(drift.check(self.home),
                         ["domains-co-za is not registered in %s" % (self.home / ".claude.json"),
                          "bunny-net still runs from R:\\Bin\\claude"])

    def test_drift_is_reported_once_per_session(self):
        self.servers["bunny-net"]["args"] = ["/mnt/r/Bin/claude/connections/bunny-net/dist/server.mjs"]
        self.write_servers()
        first = self.hook("session-a")
        context = json.loads(first.stdout)["hookSpecificOutput"]
        self.assertEqual(context["hookEventName"], "UserPromptSubmit")
        self.assertIn("bunny-net still runs from R:\\Bin\\claude", context["additionalContext"])
        self.assertIn("bunny-net still runs from", first.stderr)
        again = self.hook("session-a")
        self.assertEqual((again.stdout, again.stderr), ("", ""))
        self.assertTrue(self.hook("session-b").stdout)
        self.assertEqual(sorted(p.name for p in self.markers.iterdir()), ["session-a", "session-b"])

    def test_a_deploy_check_past_the_budget_is_reported_not_awaited(self):
        with unittest.mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("deploy", 3)) as run:
            found = drift.deploy_drift(time.monotonic() + 1.5, self.home)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 1.5)
        self.assertEqual(found, ["the deploy check did not finish inside 3 seconds: run it by hand"])

    def test_checks_that_overrun_the_budget_are_abandoned_and_reported(self):
        started = time.monotonic()
        found = drift.bounded_check(0.2, run=lambda deadline: time.sleep(5) or [])
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(found, ["the drift check did not finish inside 0.2 seconds: run it by hand"])
        self.assertEqual(drift.bounded_check(5, run=lambda deadline: ["x"]), ["x"])
        self.assertEqual(drift.bounded_check(5, run=lambda deadline: {}["absent"]),
                         ["the drift check failed: KeyError: 'absent'"])

    def test_a_refused_deploy_check_is_reported(self):
        (self.home / ".claude" / "settings.json").write_text("{ not json", encoding="utf-8")
        found = drift.deploy_drift(time.monotonic() + 30, self.home)
        self.assertEqual(len(found), 1)
        self.assertIn("the deploy check failed: refused:", found[0])

    def test_the_marker_folder_falls_back_when_the_first_cannot_be_made(self):
        blocked = Path(self._tmp.name) / "a-file"
        blocked.write_text("", encoding="utf-8")
        with unittest.mock.patch.object(drift, "marker_dirs", return_value=[str(blocked / "x"), str(self.markers)]):
            self.assertTrue(drift.first_prompt("s/1"))
            self.assertFalse(drift.first_prompt("s/1"))
        self.assertEqual([p.name for p in self.markers.iterdir()], ["s_1"])


if __name__ == "__main__":
    unittest.main()
