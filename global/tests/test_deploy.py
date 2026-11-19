"""Tests for global/deploy.py. Every run targets a temporary --home, never the real one."""
import contextlib
import io
import itertools
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

GLOBAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLOBAL))
import deploy  # noqa: E402

STUB = GLOBAL.parent / "tests" / "fixtures" / "codex_app_server_stub.py"
# A deploy approves the Codex hooks it wrote through Codex's app-server; tests answer from a stub (an empty listing
# unless a test sets a scenario), never the machine's real Codex.
os.environ["CODEX_HOOK_TRUST_SERVER"] = json.dumps([sys.executable, str(STUB)])

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


class PluginRegistrationTest(unittest.TestCase):
    """deploy re-registers the Claude connection plugins only for the real home; register_claude is faked, so no CLI
    runs and no real ~/.claude.json is read."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        sys.path.insert(0, str(deploy.PLUGIN_SCRIPTS))
        import register_claude
        self.rc = register_claude

    def deploy(self, dry_run=False, real_home=None, fixable=(), left=()):
        dep = deploy.Deployer(self.home, dry_run)
        out = io.StringIO()
        with unittest.mock.patch.object(self.rc, "fixable", return_value=list(fixable)), \
                unittest.mock.patch.object(self.rc, "problems", return_value=list(left)), \
                unittest.mock.patch.object(self.rc, "blocker", return_value=None), \
                unittest.mock.patch.object(self.rc, "config_path", return_value=self.home / ".claude.json"), \
                unittest.mock.patch.object(self.rc, "register") as register, contextlib.redirect_stdout(out):
            deploy.register_plugins(dep, real_home=self.home if real_home is None else real_home)
        return dep.results, out.getvalue(), register

    def test_a_plugin_failure_is_reported_and_the_other_agents_still_deploy(self):
        with unittest.mock.patch.object(deploy, "register_plugins", side_effect=lambda dep: dep.fail("plugins", "bad")):
            code, out, _ = run("--home", str(self.home))
        self.assertEqual(code, 1)
        self.assertIn("failed: plugins: bad", out)
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())
        self.assertIn("1 failed", out)
        dep = deploy.Deployer(self.home, False)
        with unittest.mock.patch.object(self.rc, "fixable", side_effect=ValueError("Expecting value")), \
                unittest.mock.patch.object(self.rc, "config_path", return_value=self.home / ".claude.json"), \
                contextlib.redirect_stdout(io.StringIO()):
            deploy.register_plugins(dep, real_home=self.home)
        self.assertEqual(dep.results, [("~/.claude.json (connection plugins)", "failed")])

    def test_a_moved_checkout_is_re_registered_by_a_deploy(self):
        results, out, register = self.deploy(fixable=["bunny-net", "domains-co-za"])
        register.assert_called_once_with(self.home / ".claude.json", names=["bunny-net", "domains-co-za"],
                                         only_wrong=True)
        self.assertEqual(results, [("~/.claude.json (connection plugins): bunny-net, domains-co-za re-registered",
                                    "updated")])

    def test_correct_registrations_are_unchanged(self):
        results, _, register = self.deploy()
        register.assert_not_called()
        self.assertEqual(results, [("~/.claude.json (connection plugins)", "unchanged")])

    def test_what_a_deploy_cannot_fix_is_reported(self):
        results, out, _ = self.deploy(left=["bunny-net: dist/server.mjs is missing"])
        self.assertEqual([status for _, status in results], ["skipped"])
        self.assertIn("bunny-net: dist/server.mjs is missing", out)

    def test_another_home_or_a_dry_run_registers_nothing(self):
        for kwargs, reason in (({"real_home": self.home / "elsewhere"}, "--home is not this user's home"),
                               ({"dry_run": True}, "dry run")):
            results, out, register = self.deploy(fixable=["bunny-net"], **kwargs)
            register.assert_not_called()
            self.assertEqual([status for _, status in results], ["skipped"])
            self.assertIn(reason, out)


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
        self.assertTrue((self.home / ".gemini" / "config" / "plugins" / "powertools" / "plugin.json").is_file())
        self.assertTrue((self.home / ".gemini" / "config" / "plugins" / "craft" / "plugin.json").is_file())
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

    def test_settings_gain_the_session_drift_hook_with_the_interpreter_in_use(self):
        hooks = (GLOBAL / "claude" / "hooks").as_posix()
        for interpreter in ("python", "python3", '"C:/Program Files/Py/python.exe" -X utf8', "uv run python"):
            data = json.loads(json.dumps(OLD_SETTINGS).replace('python \\"Q:', interpreter.replace('"', '\\"') + ' \\"Q:'))
            path = self.write_settings(data)
            code, out, _ = run("--home", str(self.home), "--agent", "claude", "--check")
            self.assertEqual(code, 1, out)
            self.assertIn("updated: ~/.claude/settings.json", out)
            run("--home", str(self.home), "--agent", "claude")
            prompt = json.loads(path.read_text(encoding="utf-8"))["hooks"]["UserPromptSubmit"]
            self.assertEqual(prompt[-1], {"hooks": [{"type": "command", "timeout": 10,
                                                     "command": '%s "%s/session_drift_check.py"' % (interpreter, hooks)}]})
            self.assertEqual(len(prompt), 2)
            run("--home", str(self.home), "--agent", "claude")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["hooks"]["UserPromptSubmit"], prompt)
            self.assertEqual(run("--home", str(self.home), "--agent", "claude", "--check")[0], 0)

    def test_a_moved_session_drift_hook_is_repointed_not_duplicated(self):
        data = json.loads(json.dumps(OLD_SETTINGS))
        data["hooks"]["UserPromptSubmit"].append(
            {"hooks": [{"type": "command", "command": 'python "Q:/old/hooks/session_drift_check.py"', "timeout": 10}]})
        path = self.write_settings(data)
        run("--home", str(self.home), "--agent", "claude")
        prompt = json.loads(path.read_text(encoding="utf-8"))["hooks"]["UserPromptSubmit"]
        self.assertEqual([g["hooks"][0]["command"].rsplit("/", 1)[1] for g in prompt],
                         ['article_rules.py"', 'session_drift_check.py"'])
        self.assertNotIn("Q:/old", json.dumps(prompt))

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
        self.assertFalse((self.home / ".gemini").exists())
        self.assertTrue((self.home / ".codex" / "AGENTS.md").is_file())

    def test_agy_deploy_renders_hooks_and_backs_up_changes(self):
        code, out, _ = run("--home", str(self.home), "--agent", "agy")
        self.assertEqual(code, 0, out)
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.home / ".codex").exists())
        powertools_dest = self.home / ".gemini" / "config" / "plugins" / "powertools"
        craft_dest = self.home / ".gemini" / "config" / "plugins" / "craft"
        self.assertTrue((powertools_dest / "plugin.json").is_file())
        self.assertTrue((craft_dest / "plugin.json").is_file())

        expected_py = deploy.python_token(sys.executable) if os.name == "nt" else "python3"
        hooks_data = json.loads((powertools_dest / "hooks.json").read_text(encoding="utf-8"))
        pre_cmd = hooks_data["powertools-hooks"]["PreInvocation"][0]["command"]
        self.assertEqual(pre_cmd, "%s hooks/powertools_hook.py" % expected_py)
        self.assertNotIn("||", pre_cmd)

        before = snapshot(self.home)
        code2, out2, _ = run("--home", str(self.home), "--agent", "agy")
        self.assertEqual(code2, 0)
        self.assertEqual(snapshot(self.home), before)
        self.assertIn("0 created, 0 updated", out2)

        readme = powertools_dest / "README.md"
        readme.write_bytes(b"custom note\n")
        stale = powertools_dest / "stale" / "orphan.txt"
        stale.parent.mkdir()
        stale.write_bytes(b"orphan\n")
        pycache_file = powertools_dest / "hooks" / "__pycache__" / "x.pyc"
        pycache_file.parent.mkdir()
        pycache_file.write_bytes(b"cache")
        third_party = self.home / ".gemini" / "config" / "plugins" / "third-party" / "plugin.json"
        third_party.parent.mkdir(parents=True)
        third_party.write_bytes(b"{}")

        # --check detects drift without modifying anything on disk
        before_check = snapshot(self.home)
        code_chk_bad, out_chk_bad, _ = run("--home", str(self.home), "--agent", "agy", "--check")
        self.assertEqual(code_chk_bad, 1, out_chk_bad)
        self.assertIn("drift detected", out_chk_bad)
        self.assertEqual(snapshot(self.home), before_check)

        # Normal deploy backs up and updates modified file + prunes orphan, keeping pycache and third-party plugins
        code3, out3, _ = run("--home", str(self.home), "--agent", "agy")
        self.assertEqual(code3, 0, out3)
        self.assertFalse(stale.exists())
        self.assertFalse(stale.parent.exists())
        self.assertTrue(pycache_file.exists())
        self.assertEqual(third_party.read_bytes(), b"{}")

        backups = list((self.home / ".conclave" / "global-backups").glob("*/.gemini/config/plugins/powertools/README.md"))
        orphan_backups = list((self.home / ".conclave" / "global-backups").glob("*/.gemini/config/plugins/powertools/stale/orphan.txt"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"custom note\n")
        self.assertEqual(len(orphan_backups), 1)
        self.assertEqual(orphan_backups[0].read_bytes(), b"orphan\n")

        # --check reports in sync (exit 0) once repaired
        code_chk_ok, out_chk_ok, _ = run("--home", str(self.home), "--agent", "agy", "--check")
        self.assertEqual(code_chk_ok, 0, out_chk_ok)
        self.assertIn("in sync", out_chk_ok)



class CodexHookApprovalTest(unittest.TestCase):
    """A deploy approves in Codex the hooks it wrote, through Codex's app-server, against the deploy's own home."""

    _scenarios = itertools.count()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()
        self.hooks = self.home / ".codex" / "hooks.json"

    def hook(self, event, index, status="modified", source="user", path=None, command=None, enabled=True):
        path = str(path or self.hooks)
        return {"key": "%s:%s:0:%d" % (path, event, index), "eventName": event, "source": source, "sourcePath": path,
                "command": command or 'python "D:/Conclave-SDK/global/codex/hooks/layer_rules.py"',
                "currentHash": "sha256:" + str(index) * 64, "trustStatus": status, "enabled": enabled}

    def scenario(self, hooks, **options):
        path = Path(self._tmp.name) / ("scenario-%d.json" % next(self._scenarios))
        path.write_text(json.dumps({"listings": [{"data": [{"hooks": hooks}]}], "apply_writes": True, **options}),
                        encoding="utf-8")
        self.env = unittest.mock.patch.dict(os.environ, {"CODEX_STUB_SCENARIO": str(path)})
        self.env.start()
        self.addCleanup(self.env.stop)
        return path

    def writes(self, path):
        log = path.with_name(path.name + ".writes.jsonl")
        return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []

    def relisted(self, path):
        """A fresh listing from the stub after the deploy: what Codex would now report."""
        trust = deploy._trust_module()
        return {h["key"]: h["trustStatus"] for h in trust.list_hooks(self.home, self.hooks.parent)}

    def test_each_deployed_hook_is_approved_with_codexs_own_hash_and_reads_trusted(self):
        ours = [self.hook("stop", 0), self.hook("user_prompt_submit", 1)]
        plugin = self.hook("stop", 2, source="plugin")
        other_file = self.hook("stop", 3, path=self.home / "elsewhere.json")
        not_global = self.hook("pre_tool_use", 4, command="python other/tool.py")
        path = self.scenario(ours + [plugin, other_file, not_global])
        code, out, _ = run("--home", str(self.home), "--agent", "codex")
        self.assertEqual(code, 0)
        writes = self.writes(path)
        self.assertEqual([w["value"] for w in writes],
                         [{h["key"]: {"trusted_hash": h["currentHash"]}} for h in ours])
        self.assertTrue(all(w["keyPath"] == "hooks.state" and w["mergeStrategy"] == "upsert" for w in writes))
        statuses = self.relisted(path)
        self.assertEqual([statuses[h["key"]] for h in ours], ["trusted", "trusted"])
        self.assertEqual(statuses[plugin["key"]], "modified")
        self.assertEqual(out.count("(approved)"), 2, out)

    def test_a_trusted_or_disabled_hook_is_not_written(self):
        path = self.scenario([self.hook("stop", 0, status="trusted"),
                              self.hook("user_prompt_submit", 1, enabled=False)])
        code, out, _ = run("--home", str(self.home), "--agent", "codex")
        self.assertEqual(code, 0)
        self.assertEqual(self.writes(path), [])
        self.assertIn("disabled in Codex, left disabled", out)
        self.assertIn("unchanged: codex hook", out)

    def test_a_refusal_or_a_silent_server_reports_and_a_rerun_finishes(self):
        ours = [self.hook("stop", 0), self.hook("user_prompt_submit", 1)]
        path = self.scenario(ours, refuse_after=1)
        code, out, _ = run("--home", str(self.home), "--agent", "codex")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.writes(path)), 1)
        self.assertIn("not approved: ", out)
        self.assertIn("run the deploy again to retry", out)
        statuses = self.relisted(path)
        self.assertEqual(sorted(statuses.values()), ["modified", "trusted"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("refuse_after")
        path.write_text(json.dumps(data), encoding="utf-8")
        run("--home", str(self.home), "--agent", "codex")
        self.assertEqual(len(self.writes(path)), 2, "the rerun did not approve only what was left")
        self.assertEqual(set(self.relisted(path).values()), {"trusted"})

    def test_a_server_that_stops_answering_after_one_approval_reports_and_a_rerun_finishes(self):
        ours = [self.hook("stop", 0), self.hook("user_prompt_submit", 1)]
        path = self.scenario(ours, silent_after=1)
        with unittest.mock.patch.dict(os.environ, {"CODEX_HOOK_TRUST_TIMEOUT": "2"}):
            code, out, _ = run("--home", str(self.home), "--agent", "codex")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.writes(path)), 1)
        self.assertIn("did not answer", out)
        self.assertEqual(sorted(self.relisted(path).values()), ["modified", "trusted"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("silent_after")
        path.write_text(json.dumps(data), encoding="utf-8")
        run("--home", str(self.home), "--agent", "codex")
        self.assertEqual(set(self.relisted(path).values()), {"trusted"})

    def test_no_listed_hook_dry_run_and_missing_codex_each_report(self):
        self.scenario([])
        code, out, _ = run("--home", str(self.home), "--agent", "codex")
        self.assertIn("skipped: codex hook approval: Codex lists none of the deployed hooks", out)
        path = self.scenario([self.hook("stop", 0)])
        code, out, _ = run("--home", str(self.home), "--agent", "codex", "--dry-run")
        self.assertIn("skipped: codex hook approval: dry run", out)
        self.assertEqual(self.writes(path), [])
        with unittest.mock.patch.dict(os.environ, {"CODEX_HOOK_TRUST_SERVER": ""}), \
                unittest.mock.patch("shutil.which", return_value=None):
            code, out, _ = run("--home", str(self.home), "--agent", "codex")
        self.assertEqual(code, 0)
        self.assertIn("skipped: codex hook approval: codex is not installed", out)

    def test_a_relative_home_is_used_and_the_ambient_codex_home_is_untouched(self):
        ambient = Path(self._tmp.name) / "ambient-codex"
        ambient.mkdir()
        (ambient / "config.toml").write_text("# the operator's own\n", encoding="utf-8")
        path = self.scenario([self.hook("stop", 0)])
        cwd = os.getcwd()
        os.chdir(self._tmp.name)
        try:
            with unittest.mock.patch.dict(os.environ, {"CODEX_HOME": str(ambient)}):
                code, out, _ = run("--home", "home", "--agent", "codex")
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0, out)
        homes = path.with_name(path.name + ".homes").read_text(encoding="utf-8").split()
        self.assertTrue(homes)
        for home in homes:
            self.assertEqual(os.path.normcase(os.path.realpath(home)),
                             os.path.normcase(os.path.realpath(str(self.hooks.parent))), homes)
        self.assertEqual((ambient / "config.toml").read_text(encoding="utf-8"), "# the operator's own\n")


# The bullets both agents' global rules must hold in section 11, byte for byte: the Codex rules lacked them until
# 2026-11-12 while Claude Code's had them (D06 T02 section 2).
QUEUE_BULLETS = ("- **Heavy jobs queue.**", "- **A child process never outlives its test.**")
RULE_FILES = {"Claude Code": GLOBAL / "claude/rules/claude-code.md", "Codex": GLOBAL / "codex/rules/codex.md"}


def section_11(text):
    """The text of section 11 of a rules file (`## 11. ...` up to the next `## `)."""
    parts = text.split("\n## 11. ", 1)
    return "" if len(parts) == 1 else parts[1].split("\n## ", 1)[0]


def queue_rule_faults(texts):
    """What keeps the queue bullets from matching across the rules files ({agent: text}): each one missing from or
    repeated in an agent's section 11, and each that differs between the agents."""
    faults, found = [], {}
    for agent, text in texts.items():
        lines = section_11(text).splitlines()
        for bullet in QUEUE_BULLETS:
            matching = [line for line in lines if line.startswith(bullet)]
            if len(matching) != 1:
                faults.append(f"{agent}: section 11 holds {bullet} {len(matching)} times, not once")
            else:
                found.setdefault(bullet, {})[agent] = matching[0]
    for bullet, by_agent in found.items():
        if len(by_agent) == len(texts) and len(set(by_agent.values())) > 1:
            faults.append(f"{bullet} differs between {' and '.join(by_agent)}")
    return faults


class QueueRuleParityTest(unittest.TestCase):
    def test_queue_rules_match(self):
        texts = {agent: path.read_text(encoding="utf-8") for agent, path in RULE_FILES.items()}
        self.assertEqual(queue_rule_faults(texts), [])

    def test_queue_rules_that_drift_are_named(self):
        texts = {agent: path.read_text(encoding="utf-8") for agent, path in RULE_FILES.items()}
        codex = texts["Codex"]
        heavy = next(line for line in section_11(codex).splitlines() if line.startswith(QUEUE_BULLETS[0]))
        child = next(line for line in section_11(codex).splitlines() if line.startswith(QUEUE_BULLETS[1]))
        cases = [
            (codex.replace(heavy + "\n", ""), ["Codex: section 11 holds - **Heavy jobs queue.** 0 times, not once"]),
            (codex.replace(child + "\n", ""),
             ["Codex: section 11 holds - **A child process never outlives its test.** 0 times, not once"]),
            (codex.replace(heavy, heavy + " Also in WSL."), ["- **Heavy jobs queue.** differs between Claude Code and Codex"]),
            (codex.replace(heavy + "\n", heavy + "\n" + heavy + "\n"),
             ["Codex: section 11 holds - **Heavy jobs queue.** 2 times, not once"]),
            (codex.replace("\n## 11. ", "\n## 12. "),
             ["Codex: section 11 holds - **Heavy jobs queue.** 0 times, not once",
              "Codex: section 11 holds - **A child process never outlives its test.** 0 times, not once"]),
        ]
        for changed, faults in cases:
            with self.subTest(faults=faults):
                self.assertNotEqual(changed, codex)
                self.assertEqual(queue_rule_faults(dict(texts, Codex=changed)), faults)


if __name__ == "__main__":
    unittest.main()
