"""Tests for scripts/start-run.ps1, the launcher of the SDK's own unattended run."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "start-run.ps1"
PWSH = shutil.which("pwsh")
SENTINEL = "sentinel-token-that-must-never-be-printed"


def run(*arguments, environment=None):
    """Run the launcher with PowerShell 7 and a time limit; -DryRun and -InstallShortcut start no other process."""
    env = dict(os.environ, CLAUDE_CODE_OAUTH_TOKEN=SENTINEL, **(environment or {}))
    return subprocess.run([PWSH or "pwsh", "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), *arguments],
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(PWSH, "PowerShell 7 (pwsh) is not installed")
class StartRunTests(unittest.TestCase):
    def test_a_dry_run_prints_the_command_and_starts_nothing(self):
        proc = run("-DryRun")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        first, command = proc.stdout.strip().splitlines()
        self.assertEqual(pathlib.Path(first.removeprefix("in ")).resolve(), ROOT)
        self.assertRegex(command, r"^claude --session-id [0-9a-f-]{36} --dangerously-skip-permissions --model opus \"/goal ")
        self.assertIn("process-plan skill", command)
        self.assertIn("python scripts/todo-graph.py query stats", command)
        self.assertNotIn(SENTINEL, proc.stdout + proc.stderr)

    def test_the_goal_is_one_argument_claude_code_accepts(self):
        command = run("-DryRun").stdout.strip().splitlines()[1]
        goal = command[command.index('"/goal ') + 1:-1]
        self.assertTrue(command.endswith('"'))
        self.assertNotIn('"', goal)
        self.assertLessEqual(len(goal), 4000 + len("/goal "))

    def test_another_model_and_goal_can_be_named(self):
        command = run("-DryRun", "-Model", "sonnet", "-Goal", "ship the importer").stdout.strip().splitlines()[1]
        self.assertIn("--model sonnet", command)
        self.assertTrue(command.endswith('"/goal ship the importer"'), command)

    def test_a_goal_claude_code_would_refuse_is_refused_here(self):
        for goal, message in (('say "hello"', "no double quote"), ("x" * 4001, "allows 4,000")):
            with self.subTest(goal=goal[:12]):
                proc = run("-DryRun", "-Goal", goal)
                self.assertEqual(proc.returncode, 1)
                self.assertIn(message, proc.stdout)

    @unittest.skipUnless(os.name == "nt", "a .lnk shortcut is a Windows file")
    def test_the_shortcut_starts_this_script_with_the_sdk_icon(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = run("-InstallShortcut", "-ShortcutDir", folder)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            link = pathlib.Path(folder) / "Conclave-SDK unattended run.lnk"
            self.assertTrue(link.is_file(), proc.stdout)
            quoted = str(link).replace("'", "''")
            read = subprocess.run(
                [PWSH or "pwsh", "-NoProfile", "-NonInteractive", "-Command",
                 f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{quoted}'); "
                 "$s.TargetPath; $s.Arguments; $s.WorkingDirectory; $s.IconLocation"],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(read.returncode, 0, read.stderr)
            target, arguments, folder_set, icon = read.stdout.strip().splitlines()
            self.assertEqual(pathlib.Path(target).name.lower(), "pwsh.exe")
            self.assertEqual(arguments, f'-NoExit -NoProfile -File "{SCRIPT}"')
            self.assertEqual(pathlib.Path(folder_set).resolve(), ROOT)
            self.assertEqual(pathlib.Path(icon.rsplit(",", 1)[0]).resolve(), ROOT / "assets/brand/conclave-sdk.ico")
            self.assertTrue((ROOT / "assets/brand/conclave-sdk.ico").is_file())


if __name__ == "__main__":
    unittest.main()
