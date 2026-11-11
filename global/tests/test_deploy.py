"""Tests for global/deploy.py. Every run targets a temporary --home, never the real one."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

GLOBAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLOBAL))
import deploy  # noqa: E402

OLD_SETTINGS = {
    "model": "opus",
    "hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": 'python "Q:/old/hooks/article_rules.py"', "timeout": 40}]}],
        "Stop": [{"hooks": [
            {"type": "command", "command": 'python "Q:/old/hooks/layer_rules.py" --x', "timeout": 10},
            {"type": "command", "command": "echo unrelated"}]}],
    },
    "permissions": {"allow": ["Bash(ls)"]},
}


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = deploy.main(list(args))
    return code, out.getvalue(), err.getvalue()


def snapshot(home):
    return {p.relative_to(home).as_posix(): p.read_bytes() for p in Path(home).rglob("*") if p.is_file()}


class PathFormsTest(unittest.TestCase):
    def test_windows_checkout(self):
        self.assertEqual(deploy.path_forms("D:\\Conclave-SDK\\global\\codex\\hooks"),
                         ("/mnt/d/Conclave-SDK/global/codex/hooks", "D:/Conclave-SDK/global/codex/hooks"))

    def test_wsl_mnt_checkout(self):
        self.assertEqual(deploy.path_forms("/mnt/d/Conclave-SDK/global/codex/hooks"),
                         ("/mnt/d/Conclave-SDK/global/codex/hooks", "D:/Conclave-SDK/global/codex/hooks"))

    def test_pure_linux_checkout(self):
        posix = "/home/me/sdk/global/codex/hooks"
        self.assertEqual(deploy.path_forms(posix), (posix, posix))

    def render(self, hooks_dir):
        template = (GLOBAL / "codex" / "rules" / "hooks.json").read_text(encoding="utf-8")
        return deploy.render_codex_hooks(template, hooks_dir, "Z:/Py/python.exe")

    def test_render_windows_checkout(self):
        text = self.render("D:\\Conclave-SDK\\global\\codex\\hooks")
        self.assertNotIn("{HOOKS", text)
        self.assertNotIn("{PYTHON", text)
        hook = json.loads(text)["hooks"]["Stop"][0]["hooks"][0]
        self.assertEqual(hook["command"], 'python3 "/mnt/d/Conclave-SDK/global/codex/hooks/layer_rules.py"')
        self.assertEqual(hook["commandWindows"],
                         'Z:/Py/python.exe "D:/Conclave-SDK/global/codex/hooks/layer_rules.py"')

    def test_render_mnt_checkout(self):
        text = self.render("/mnt/e/work/sdk/global/codex/hooks")
        hook = json.loads(text)["hooks"]["UserPromptSubmit"][0]["hooks"][0]
        self.assertEqual(hook["command"], 'python3 "/mnt/e/work/sdk/global/codex/hooks/article_rules.py"')
        self.assertEqual(hook["commandWindows"],
                         'Z:/Py/python.exe "E:/work/sdk/global/codex/hooks/article_rules.py"')

    def test_existing_windows_python(self):
        text = json.dumps({"hooks": {"Stop": [{"hooks": [{"commandWindows": 'C:/Py/python.exe "x.py"'}]}]}})
        self.assertEqual(deploy.existing_windows_python(text), "C:/Py/python.exe")
        self.assertIsNone(deploy.existing_windows_python("not json"))


class DeployTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)

    def write_settings(self, data):
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_fresh_home(self):
        code, out, _ = run("--home", str(self.home))
        self.assertEqual(code, 0)
        self.assertEqual((self.home / ".claude" / "CLAUDE.md").read_bytes(),
                         (GLOBAL / "claude" / "rules" / "claude-code.md").read_bytes())
        self.assertEqual((self.home / ".codex" / "AGENTS.md").read_bytes(),
                         (GLOBAL / "codex" / "rules" / "codex.md").read_bytes())
        self.assertTrue((self.home / ".claude" / "skills" / "process-email" / "SKILL.md").is_file())
        self.assertTrue((self.home / ".agents" / "skills" / "file-to-ticktick" / "SKILL.md").is_file())
        self.assertFalse((self.home / ".claude" / "settings.json").exists())
        self.assertIn("skipped: ~/.claude/settings.json", out)
        self.assertFalse((self.home / ".conclave").exists())

    def test_generated_hooks_json_has_no_placeholder(self):
        run("--home", str(self.home), "--agent", "codex")
        text = (self.home / ".codex" / "hooks.json").read_text(encoding="utf-8")
        self.assertNotIn("{HOOKS", text)
        self.assertNotIn("{PYTHON", text)
        json.loads(text)
        self.assertNotIn("R:/", text)

    def test_second_run_is_unchanged_and_writes_nothing(self):
        self.write_settings(OLD_SETTINGS)
        run("--home", str(self.home))
        before = snapshot(self.home)
        code, out, _ = run("--home", str(self.home))
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(self.home), before)
        self.assertNotIn("created:", out)
        self.assertNotIn("updated:", out)
        self.assertIn("0 created, 0 updated", out)

    def test_changed_destination_is_backed_up_then_updated(self):
        target = self.home / ".claude" / "CLAUDE.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"old rules\r\n")
        code, out, _ = run("--home", str(self.home), "--agent", "claude")
        self.assertEqual(code, 0)
        self.assertIn("updated: ~/.claude/CLAUDE.md", out)
        self.assertEqual(target.read_bytes(), (GLOBAL / "claude" / "rules" / "claude-code.md").read_bytes())
        backups = list((self.home / ".conclave" / "global-backups").glob("*/.claude/CLAUDE.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"old rules\r\n")

    def test_dry_run_writes_nothing(self):
        settings = self.write_settings(OLD_SETTINGS)
        (self.home / ".codex").mkdir()
        (self.home / ".codex" / "AGENTS.md").write_bytes(b"old")
        before = snapshot(self.home)
        code, out, _ = run("--home", str(self.home), "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(self.home), before)
        self.assertIn("created:", out)
        self.assertIn("updated: ~/.codex/AGENTS.md", out)
        self.assertIn("updated: ~/.claude/settings.json", out)
        self.assertEqual(json.loads(settings.read_text(encoding="utf-8")), OLD_SETTINGS)

    def test_settings_rewrite_touches_only_hook_script_paths(self):
        self.write_settings(OLD_SETTINGS)
        run("--home", str(self.home), "--agent", "claude")
        new = json.loads((self.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
        hooks = (GLOBAL / "claude" / "hooks").as_posix()
        self.assertEqual(list(new), list(OLD_SETTINGS))
        self.assertEqual(new["model"], "opus")
        self.assertEqual(new["permissions"], OLD_SETTINGS["permissions"])
        self.assertEqual(new["hooks"]["UserPromptSubmit"][0]["hooks"][0],
                         {"type": "command", "command": 'python "%s/article_rules.py"' % hooks, "timeout": 40})
        stop = new["hooks"]["Stop"][0]["hooks"]
        self.assertEqual(stop[0]["command"], 'python "%s/layer_rules.py" --x' % hooks)
        self.assertEqual(stop[0]["timeout"], 10)
        self.assertEqual(stop[1], {"type": "command", "command": "echo unrelated"})
        text = (self.home / ".claude" / "settings.json").read_text(encoding="utf-8")
        self.assertIn('\n  "model"', text)

    def test_settings_without_hook_commands_is_left_alone(self):
        path = self.write_settings({"model": "opus", "hooks": {"Stop": [{"hooks": [{"command": "echo hi"}]}]}})
        before = path.read_bytes()
        code, out, _ = run("--home", str(self.home), "--agent", "claude")
        self.assertEqual(code, 0)
        self.assertEqual(path.read_bytes(), before)
        self.assertIn("skipped: ~/.claude/settings.json", out)

    def test_invalid_settings_refuses_and_writes_nothing(self):
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True)
        path.write_text("{ not json", encoding="utf-8")
        before = snapshot(self.home)
        code, _, err = run("--home", str(self.home))
        self.assertNotEqual(code, 0)
        self.assertIn("not valid JSON", err)
        self.assertEqual(snapshot(self.home), before)

    def test_skills_keep_destination_only_files(self):
        extra = self.home / ".claude" / "skills" / "process-email" / "local-notes.txt"
        other = self.home / ".claude" / "skills" / "someone-elses" / "SKILL.md"
        for path in (extra, other):
            path.parent.mkdir(parents=True)
            path.write_bytes(b"mine")
        run("--home", str(self.home), "--agent", "claude")
        self.assertEqual(extra.read_bytes(), b"mine")
        self.assertEqual(other.read_bytes(), b"mine")
        self.assertTrue((extra.parent / "SKILL.md").is_file())

    def test_agent_filter(self):
        run("--home", str(self.home), "--agent", "codex")
        self.assertFalse((self.home / ".claude").exists())
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())


if __name__ == "__main__":
    unittest.main()
