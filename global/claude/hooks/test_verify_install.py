"""Tests for verify_install.py. Run on Windows and WSL: python -m unittest discover -s rules/hooks"""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_install  # noqa: E402


def wired(py="python"):
    """Settings that run both hooks from this folder on every required event."""
    article = {"type": "command", "command": f'{py} "{HERE}/article_rules.py"'}
    layer = {"type": "command", "command": f'{py} "{HERE}/layer_rules.py"'}
    drift = {"type": "command", "command": f'{py} "{HERE}/session_drift_check.py"'}
    return {"hooks": {
        "UserPromptSubmit": [{"hooks": [article]}, {"hooks": [layer]}, {"hooks": [drift]}],
        "PreToolUse": [{"matcher": "Bash|PowerShell", "hooks": [article]}, {"matcher": "Write|Edit|MultiEdit", "hooks": [layer]}],
        "PostToolUse": [{"matcher": "Write|Edit|MultiEdit", "hooks": [article, layer]}],
        "Stop": [{"hooks": [layer]}],
    }}


class VerifyInstallTest(unittest.TestCase):
    def test_full_wiring_passes(self):
        self.assertEqual(verify_install.check_wiring(wired()), [])

    def test_missing_event_is_reported(self):
        settings = wired()
        del settings["hooks"]["Stop"]
        self.assertEqual(verify_install.check_wiring(settings), [f"Stop * does not run layer_rules.py from {HERE}"])

    def test_missing_drift_hook_is_reported(self):
        settings = wired()
        settings["hooks"]["UserPromptSubmit"].pop()
        self.assertEqual(verify_install.check_wiring(settings),
                         [f"UserPromptSubmit * does not run session_drift_check.py from {HERE}"])

    def test_narrow_matcher_is_reported(self):
        settings = wired()
        settings["hooks"]["PreToolUse"][1]["matcher"] = "Write|Edit"
        self.assertIn(f"PreToolUse MultiEdit does not run layer_rules.py from {HERE}", verify_install.check_wiring(settings))

    def test_hook_from_another_folder_does_not_count(self):
        settings = json.loads(json.dumps(wired()).replace(HERE.replace("\\", "\\\\"), "/elsewhere"))
        self.assertEqual(len(verify_install.check_wiring(settings)), len(verify_install.REQUIRED))

    def test_settings_that_switch_hooks_off_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"disableAllHooks": True}, f)
            self.assertEqual(verify_install.check_switches([path, os.path.join(d, "absent.json")], ("disableAllHooks",)),
                             [f"{path} sets disableAllHooks"])

    def test_replay_in_a_plain_repository_passes(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".git"))
            self.assertEqual(verify_install.replay(d), [])


if __name__ == "__main__":
    unittest.main()
