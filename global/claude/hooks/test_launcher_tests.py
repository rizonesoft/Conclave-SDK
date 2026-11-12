"""Tests of launcher_tests.py and its wiring into layer_rules.py: a launcher test never opens a window."""
import json
import os
import subprocess
import sys
import tempfile
import unittest



def _sibling(name):
    """A module beside this file, loaded by path: this folder is not a package."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher_tests = _sibling("launcher_tests")

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layer_rules.py")
LAUNCHER_TEST = '''import subprocess
SCRIPT = "scripts/start-campaign.ps1"
def run(*args):
    return subprocess.run(["pwsh", "-NoProfile", "-File", SCRIPT, *args],
                          capture_output=True, text=True)
'''


def every_line(text):
    return set(range(len(text.splitlines())))


class CheckTest(unittest.TestCase):
    def test_a_console_start_in_a_launcher_test_is_flagged(self):
        flags = launcher_tests.check("tests/test_start_campaign.py", LAUNCHER_TEST, every_line(LAUNCHER_TEST))
        self.assertEqual([line for line, _ in flags], [4])

    def test_a_windowless_start_is_not_flagged(self):
        text = LAUNCHER_TEST.replace("text=True)", "text=True, creationflags=windowless())")
        self.assertEqual(launcher_tests.check("tests/test_start_campaign.py", text, every_line(text)), [])

    def test_an_application_launch_inside_a_launcher_test_is_not_flagged(self):
        text = LAUNCHER_TEST + 'subprocess.Popen(["C:/Program Files/Office/WINWORD.EXE", "report.docx"])\n'
        flags = launcher_tests.check("tests/test_start_campaign.py", text, every_line(text))
        self.assertEqual([line for line, _ in flags], [4], "the application launch was flagged")

    def test_an_interface_test_is_never_flagged(self):
        text = 'import subprocess\nsubprocess.Popen(["python", "capture-ui.py"])\n'
        self.assertEqual(launcher_tests.check("tests/test_ui_app.py", text, every_line(text)), [])
        self.assertEqual(launcher_tests.check("scripts/start-campaign.py", LAUNCHER_TEST, every_line(LAUNCHER_TEST)),
                         [], "a launcher script itself is not a test")

    def test_a_commented_exemption_is_accepted(self):
        text = LAUNCHER_TEST.replace("text=True)", "text=True)  # window-exempt: the test reads the window title")
        self.assertEqual(launcher_tests.check("tests/test_start_campaign.py", text, every_line(text)), [])

    def test_start_process_needs_no_new_window_unless_it_starts_an_application(self):
        text = ('Describe "start-run" {\n'
                '  Start-Process pwsh -ArgumentList "-File start-run.ps1"\n'
                '  Start-Process pwsh -NoNewWindow -ArgumentList "-File start-run.ps1"\n'
                '  Start-Process -FilePath "C:/Program Files/Google/Chrome/Application/chrome.exe"\n'
                '}\n')
        flags = launcher_tests.check("tests/StartRun.Tests.ps1", text, every_line(text))
        self.assertEqual([line for line, _ in flags], [2])

    def test_a_comment_is_not_a_start(self):
        text = '# start-campaign\n# subprocess.run(["pwsh"])\n'
        self.assertEqual(launcher_tests.check("tests/test_campaign.py", text, every_line(text)), [])

    def test_creationflags_zero_still_opens_a_window(self):
        text = LAUNCHER_TEST.replace("text=True)", "text=True, creationflags=0)")
        self.assertEqual(len(launcher_tests.check("tests/test_start_campaign.py", text, every_line(text))), 1)

    def test_an_edit_fragment_is_judged_with_its_file(self):
        fragment = '    return subprocess.run(["pwsh", "-File", SCRIPT])\n'
        whole = 'import subprocess\nSCRIPT = "scripts/start-campaign.ps1"\ndef run():\n    pass\n'
        self.assertEqual(launcher_tests.check("tests/test_start_campaign.py", fragment, {0}), [], "no file context")
        self.assertEqual(len(launcher_tests.check("tests/test_start_campaign.py", fragment, {0}, whole)), 1)
    def test_only_added_lines_count(self):
        self.assertEqual(launcher_tests.check("tests/test_start_campaign.py", LAUNCHER_TEST, {0, 1}), [])


class HookTest(unittest.TestCase):
    def hook(self, path, content):
        payload = {"hook_event_name": "PreToolUse", "session_id": "launcher-test-session", "tool_name": "Write",
                   "tool_input": {"file_path": path, "content": content}, "cwd": os.path.dirname(path)}
        done = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True,
                              timeout=60, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_the_layer_hook_carries_the_advisory_in_one_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.hook(os.path.join(tmp, "test_start_campaign.py"), LAUNCHER_TEST)
            answer = json.loads(out)
            self.assertIn("a launcher test never opens a window", answer["hookSpecificOutput"]["additionalContext"])
            self.assertEqual(self.hook(os.path.join(tmp, "test_ui_app.py"), LAUNCHER_TEST.replace("start-campaign", "app")),
                             "")


if __name__ == "__main__":
    unittest.main()
