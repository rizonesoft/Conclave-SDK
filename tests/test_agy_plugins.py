"""Tests for standalone Antigravity plugins under plugins/agy/ and powertools_hook.py."""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock
import xml.etree.ElementTree as ET
import zipfile

SDK_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGY_PLUGINS = SDK_ROOT / "plugins" / "agy"
POWERTOOLS_DIR = AGY_PLUGINS / "powertools"
CRAFT_DIR = AGY_PLUGINS / "craft"
HOOK_SCRIPT = POWERTOOLS_DIR / "hooks" / "powertools_hook.py"

ALLOWED_MANIFEST_KEYS = {
    "name",
    "displayName",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "logo",
    "suggestedPrompts",
    "disabled",
}

CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def parse_frontmatter(skill_md: pathlib.Path) -> dict[str, str]:
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError(f"{skill_md} missing YAML frontmatter start")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise AssertionError(f"{skill_md} missing YAML frontmatter end")
    data: dict[str, str] = {}
    current_key: str | None = None
    buf: list[str] = []
    for line in lines[1:end]:
        if re.match(r"^[A-Za-z0-9_-]+:", line):
            if current_key is not None:
                data[current_key] = " ".join(buf).strip()
            key, val = line.split(":", 1)
            current_key = key.strip()
            cleaned = val.strip()
            buf = [] if cleaned in (">-", ">", "|", "|-") else [cleaned.strip('"').strip("'")]
        elif current_key is not None and line.strip():
            buf.append(line.strip())
    if current_key is not None:
        data[current_key] = " ".join(buf).strip()
    return data


class AgyPluginStructureTests(unittest.TestCase):
    def test_manifests_assets_and_layout(self):
        expected = {
            POWERTOOLS_DIR: "agy-powertools",
            CRAFT_DIR: "agy-craft",
        }
        for plugin_dir, manifest_name in expected.items():
            manifest_path = plugin_dir / "plugin.json"
            self.assertTrue(manifest_path.is_file(), f"missing {manifest_path}")
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("name"), manifest_name)
            self.assertTrue(set(data).issubset(ALLOWED_MANIFEST_KEYS), set(data) - ALLOWED_MANIFEST_KEYS)
            prompts = data.get("suggestedPrompts", [])
            self.assertLessEqual(len(prompts), 3)
            logo_rel = data.get("logo", "")
            logo_path = plugin_dir / logo_rel
            self.assertTrue(logo_path.is_file(), f"missing logo {logo_path}")
            self.assertIn('viewBox="0 0 128 128"', logo_path.read_text(encoding="utf-8"))
            self.assertFalse((plugin_dir / "agents").exists(), f"{plugin_dir} must not wrap agents/*.md")

        for pat in ("test_*.py", "*_test.py", "*.test.mjs", "*.test.js", "test-*.sh"):
            self.assertEqual(list(AGY_PLUGINS.rglob(pat)), [], f"unowned test pattern {pat} in plugins/agy")

    def test_rules_skills_and_syntax(self):
        rules_md = POWERTOOLS_DIR / "rules" / "AGENTS.md"
        self.assertTrue(rules_md.is_file())
        rules_bytes = rules_md.read_bytes()
        self.assertLess(len(rules_bytes), 24000)
        rules_text = rules_bytes.decode("utf-8")
        self.assertFalse(rules_text.lstrip().startswith("---"), "AGENTS.md must not contain YAML frontmatter")

        expected_powertools_skills = {
            "receiving-code-review",
            "systematic-debugging",
            "verification-before-completion",
            "test-driven-development",
            "parallel-precheck",
            "code-simplifier",
            "improving-agent-configs",
        }
        expected_craft_skills = {"frontend-design", "docx", "xlsx", "pptx", "pdf"}

        for plugin_dir, expected_names in ((POWERTOOLS_DIR, expected_powertools_skills), (CRAFT_DIR, expected_craft_skills)):
            skills_root = plugin_dir / "skills"
            found_names = {p.name for p in skills_root.iterdir() if p.is_dir()}
            self.assertEqual(found_names, expected_names)
            for skill_dir in sorted(skills_root.iterdir()):
                if not skill_dir.is_dir():
                    continue
                fm = parse_frontmatter(skill_dir / "SKILL.md")
                self.assertEqual(fm.get("name"), skill_dir.name)
                self.assertTrue(fm.get("description"), f"{skill_dir} empty description")

        workflow_py = POWERTOOLS_DIR / "skills" / "parallel-precheck" / "scripts" / "precheck_workflow.py"
        compile(workflow_py.read_text(encoding="utf-8"), str(workflow_py), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    def test_no_em_or_en_dashes_in_agy_plugins(self):
        for p in sorted(AGY_PLUGINS.rglob("*")):
            if not p.is_file() or p.suffix not in (".md", ".py", ".json", ".js", ".svg"):
                continue
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("\u2014", text, f"em dash found in {p}")
            self.assertNotIn("\u2013", text, f"en dash found in {p}")

    def test_agy_cli_validate_strict_if_available(self):
        agy = shutil.which("agy")
        if not agy:
            self.skipTest("agy CLI not on PATH")
        for plugin_dir in (POWERTOOLS_DIR, CRAFT_DIR):
            res = subprocess.run(
                [agy, "plugin", "validate", str(plugin_dir), "--strict"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                creationflags=CREATION_FLAGS,
                timeout=30,
            )
            self.assertEqual(res.returncode, 0, f"{plugin_dir.name} failed strict validate:\n{res.stdout}\n{res.stderr}")


class PowertoolsHookBehaviorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name)
        self.plugin_data = self.root / "plugin-data"
        self.workspace = self.root / "repo"
        self.artifacts = self.root / "artifacts"
        self.workspace.mkdir()
        self.artifacts.mkdir()
        self.transcript = self.root / "transcript.jsonl"
        self.transcript_full = self.root / "transcript_full.jsonl"

    def run_hook(self, payload: dict, extra_env: dict[str, str] | None = None) -> dict:
        base = {
            "conversationId": "conv-123",
            "workspacePaths": [str(self.workspace)],
            "transcriptPath": str(self.transcript),
            "artifactDirectoryPath": str(self.artifacts),
            "lastUserInput": "Fix the bug in app.py",
            "cwd": str(self.workspace),
        }
        base.update(payload)
        env = dict(os.environ, PLUGIN_DATA=str(self.plugin_data))
        if extra_env:
            env.update(extra_env)
        res = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(base),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATION_FLAGS,
            timeout=15,
            env=env,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout)

    def test_run_command_catastrophic_only_force_ask(self):
        safe_cmds = [
            "git status",
            "git push origin main",
            "git push --repo origin main",
            "git push --repo=origin main",
            "git push -ofix origin main",
            "git branch -f feature-local",
            'git commit -m "avoid git push -f accidental match"',
            'git push origin -- "--force"',
            "rm -rf build",
            r"Remove-Item R:\scratch\temp -Recurse -Force",
            'bash -lc "git push origin main"',
            'bash -c "git commit -m \\"git push --force\\""',
            'pwsh -File deploy.ps1',
        ]
        for cmd in safe_cmds:
            with self.subTest(cmd=cmd):
                out = self.run_hook({
                    "hookEventName": "PreToolUse",
                    "toolCall": {"id": "c1", "name": "run_command", "args": {"CommandLine": cmd}},
                })
                self.assertEqual(out.get("decision"), "allow", out)

        dangerous_cmds = [
            "git push --force origin main",
            'git push "--force" origin main',
            "git push '--force' origin main",
            'git -C . push "-f"',
            "git push -f",
            "git push --force-with-lease origin main",
            'git -C . push origin "+main"',
            "git push --repo origin +HEAD:main",
            "git push --repo=origin +HEAD:main",
            "git push +HEAD:main",
            "git push -uo opt -f origin main",
            "gh repo delete owner/repo --yes",
            "Format-Volume -DriveLetter E -FileSystem NTFS",
            "rm -rf /",
            'rm "-rf" "/"',
            'bash -lc "git push --force origin main"',
            'bash -lc "git push \\"--force\\" origin main"',
            'wsl -d Ubuntu bash -lc "git push --force origin main"',
            'pwsh -NoProfile -Command "Remove-Item -Recurse C:\\"',
            r'cmd /c "gh repo delete acme/app"',
        ]
        for cmd in dangerous_cmds:
            with self.subTest(cmd=cmd):
                out = self.run_hook({
                    "hookEventName": "PreToolUse",
                    "toolCall": {"id": "c2", "name": "run_command", "args": {"CommandLine": cmd}},
                })
                self.assertEqual(out.get("decision"), "force_ask", f"expected force_ask for {cmd}: {out}")
                self.assertTrue(out.get("reason"))

    def test_drift_notice_fires_once_per_session(self):
        src_root = self.root / "src-agy"
        inst_root = self.root / "inst-agy"
        src_plugin = src_root / "powertools"
        inst_plugin = inst_root / "powertools"
        (src_plugin / "hooks").mkdir(parents=True)
        (inst_plugin / "hooks").mkdir(parents=True)
        (src_plugin / "plugin.json").write_text('{"name": "agy-powertools"}\n', encoding="utf-8")
        (inst_plugin / "plugin.json").write_text('{"name": "agy-powertools"}\n', encoding="utf-8")
        (src_plugin / "hooks.json").write_text('{"powertools-hooks": {"PreInvocation": [{"command": "python3 hooks/powertools_hook.py"}]}}\n', encoding="utf-8")
        (inst_plugin / "hooks.json").write_text('{"powertools-hooks": {"PreInvocation": [{"command": "C:/Py/python.exe hooks/powertools_hook.py"}]}}\n', encoding="utf-8")
        hook_text = HOOK_SCRIPT.read_text(encoding="utf-8")
        (src_plugin / "hooks" / "powertools_hook.py").write_text(hook_text, encoding="utf-8")
        inst_hook = inst_plugin / "hooks" / "powertools_hook.py"
        inst_hook.write_text(
            re.sub(r"^DEPLOYED_FROM = .*$", f"DEPLOYED_FROM = {json.dumps(src_root.as_posix())}", hook_text, count=1, flags=re.M),
            encoding="utf-8",
        )
        for helper in ("article_check.py", "launcher_tests.py"):
            content = (POWERTOOLS_DIR / "hooks" / helper).read_bytes()
            (src_plugin / "hooks" / helper).write_bytes(content)
            (inst_plugin / "hooks" / helper).write_bytes(content)

        def call_installed(payload):
            base = {
                "conversationId": "drift-conv",
                "workspacePaths": [str(self.workspace)],
                "transcriptPath": str(self.transcript),
                "artifactDirectoryPath": str(self.artifacts),
                "lastUserInput": "Check status",
                "cwd": str(self.workspace),
            }
            base.update(payload)
            res = subprocess.run(
                [sys.executable, str(inst_hook)],
                input=json.dumps(base),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATION_FLAGS,
                timeout=15,
                env=dict(os.environ, PLUGIN_DATA=str(self.plugin_data)),
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            return json.loads(res.stdout)

        # In sync initially -> no drift notice
        self.assertEqual(call_installed({"hookEventName": "PreInvocation", "conversationId": "sync-conv"}), {})

        # Modify source file and start a fresh session -> warns once
        (src_plugin / "README.md").write_text("updated\n", encoding="utf-8")
        first = call_installed({"hookEventName": "PreInvocation"})
        msg = first["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("Conclave plugin drift detected", msg)
        self.assertIn("powertools", msg)

        # Second invocation (even on a new prompt in same session) does not repeat
        second = call_installed({"hookEventName": "PreInvocation", "lastUserInput": "Another prompt"})
        self.assertEqual(second, {})

    def test_masking_warning_flushes_once_and_workaround_exempts(self):
        app_py = self.workspace / "app.py"
        bad_code = "def load():\n    try:\n        return 1\n    except Exception:\n        pass\n"

        pre = self.run_hook({
            "hookEventName": "PreToolUse",
            "toolCall": {"id": "w1", "name": "write_file", "args": {"Path": str(app_py), "Content": bad_code, "Overwrite": True}},
        })
        self.assertEqual(pre, {"decision": "allow"})
        app_py.write_text(bad_code, encoding="utf-8")

        post = self.run_hook({
            "hookEventName": "PostToolUse",
            "toolCall": {"id": "w1", "name": "write_file", "args": {"Path": str(app_py), "Content": bad_code, "Overwrite": True}},
        })
        self.assertEqual(post, {})

        inv1 = self.run_hook({"hookEventName": "PreInvocation", "invocationNum": 2})
        injected = inv1["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("swallowed error", injected)

        inv2 = self.run_hook({"hookEventName": "PreInvocation", "invocationNum": 3})
        self.assertEqual(inv2, {})

        # New user turn with WORKAROUND comment exempts the masking pattern
        exempt_code = (
            "def load():\n"
            "    try:\n"
            "        return 1\n"
            "    # WORKAROUND: upstream raises generic ValueError on empty stream\n"
            "    except Exception:\n"
            "        pass\n"
        )
        self.run_hook({
            "hookEventName": "PreToolUse",
            "lastUserInput": "Refactor with documented workaround",
            "toolCall": {"id": "w2", "name": "write_file", "args": {"Path": str(app_py), "Content": exempt_code, "Overwrite": True}},
        })
        self.run_hook({
            "hookEventName": "PostToolUse",
            "lastUserInput": "Refactor with documented workaround",
            "toolCall": {"id": "w2", "name": "write_file", "args": {"Path": str(app_py), "Content": exempt_code, "Overwrite": True}},
        })
        inv3 = self.run_hook({
            "hookEventName": "PreInvocation",
            "lastUserInput": "Refactor with documented workaround",
        })
        self.assertEqual(inv3, {})

    def test_failed_tool_call_and_artifact_edits_do_not_trigger_stop(self):
        app_py = self.workspace / "app.py"
        bad_code = "try:\n    x = 1\nexcept Exception:\n    pass\n"
        self.run_hook({
            "hookEventName": "PreToolUse",
            "toolCall": {"id": "e1", "name": "write_file", "args": {"Path": str(app_py), "Content": bad_code}},
        })
        self.run_hook({
            "hookEventName": "PostToolUse",
            "error": "permission denied",
            "toolCall": {"id": "e1", "name": "write_file", "args": {"Path": str(app_py), "Content": bad_code}},
        })
        scratch_py = self.artifacts / "scratch_probe.py"
        self.run_hook({
            "hookEventName": "PreToolUse",
            "toolCall": {"id": "s1", "name": "write_file", "args": {"Path": str(scratch_py), "Content": "x = 1\n"}},
        })
        self.run_hook({
            "hookEventName": "PostToolUse",
            "toolCall": {"id": "s1", "name": "write_file", "args": {"Path": str(scratch_py), "Content": "x = 1\n"}},
        })
        self.transcript.write_text(
            json.dumps({"type": "USER_INPUT", "content": "Fix the bug"}) + "\n"
            + json.dumps({"type": "PLANNER_RESPONSE", "content": "Nothing changed."}) + "\n",
            encoding="utf-8",
        )
        stop = self.run_hook({"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"})
        self.assertEqual(stop.get("decision"), "stop")

    def test_launcher_test_and_draft_article_checks(self):
        test_file = self.workspace / "test_start_run.py"
        launcher_code = (
            "import subprocess\n"
            "# exercises start-run launcher\n"
            "def run_launcher():\n"
            "    return subprocess.run(['python', 'worker.py'])\n"
        )
        self.run_hook({
            "hookEventName": "PreToolUse",
            "toolCall": {"id": "l1", "name": "write_file", "args": {"Path": str(test_file), "Content": launcher_code}},
        })
        self.run_hook({
            "hookEventName": "PostToolUse",
            "toolCall": {"id": "l1", "name": "write_file", "args": {"Path": str(test_file), "Content": launcher_code}},
        })
        inv = self.run_hook({"hookEventName": "PreInvocation"})
        self.assertIn("CREATE_NO_WINDOW", inv["injectSteps"][0]["systemMessage"]["systemMessage"])

        draft = self.workspace / "drafts" / "post.md"
        draft.parent.mkdir()
        draft_content = "# Title\n\nIn today's digital landscape we delve into email.\n"
        draft.write_text(draft_content, encoding="utf-8")
        self.run_hook({
            "hookEventName": "PreToolUse",
            "lastUserInput": "Write a blog post about email",
            "toolCall": {"id": "d1", "name": "write_file", "args": {"Path": str(draft), "Content": draft_content}},
        })
        self.run_hook({
            "hookEventName": "PostToolUse",
            "lastUserInput": "Write a blog post about email",
            "toolCall": {"id": "d1", "name": "write_file", "args": {"Path": str(draft), "Content": draft_content}},
        })
        inv_draft = self.run_hook({
            "hookEventName": "PreInvocation",
            "lastUserInput": "Write a blog post about email",
        })
        msg = inv_draft["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("article check", msg)
        self.assertIn("Owner writing rules", msg)
        # Prose draft alone does not trigger Stop Layer check
        stop = self.run_hook({
            "hookEventName": "Stop",
            "lastUserInput": "Write a blog post about email",
            "terminationReason": "NO_TOOL_CALL",
        })
        self.assertEqual(stop.get("decision"), "stop")
        # WordPress CLI writes queue the writing reminder once per turn without blocking
        pre_wp = self.run_hook({
            "hookEventName": "PreToolUse",
            "lastUserInput": "Publish page",
            "toolCall": {"id": "wp1", "name": "run_command", "args": {"CommandLine": "wp post update 42 --post_content=hi"}},
        })
        self.assertEqual(pre_wp, {"decision": "allow"})
        inv_wp = self.run_hook({"hookEventName": "PreInvocation", "lastUserInput": "Publish page"})
        self.assertIn("Owner writing rules", inv_wp["injectSteps"][0]["systemMessage"]["systemMessage"])

    def test_stop_requests_layer_once_or_accepts_full_transcript(self):
        app_py = self.workspace / "app.py"
        self.run_hook({
            "hookEventName": "PreToolUse",
            "toolCall": {"id": "c1", "name": "write_file", "args": {"Path": str(app_py), "Content": "x = 1\n"}},
        })
        self.run_hook({
            "hookEventName": "PostToolUse",
            "toolCall": {"id": "c1", "name": "write_file", "args": {"Path": str(app_py), "Content": "x = 1\n"}},
        })
        self.transcript.write_text(
            json.dumps({"type": "USER_INPUT", "content": "Fix"}) + "\n"
            + json.dumps({"type": "PLANNER_RESPONSE", "content": "Updated app.py."}) + "\n",
            encoding="utf-8",
        )
        # Non-NO_TOOL_CALL termination never prompts for Layer:
        canceled = self.run_hook({"hookEventName": "Stop", "terminationReason": "USER_CANCELED"})
        self.assertEqual(canceled.get("decision"), "stop")

        stop1 = self.run_hook({"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"})
        self.assertEqual(stop1.get("decision"), "continue")
        self.assertIn("Layer:", stop1.get("reason", ""))

        # Second Stop never loops even without a Layer line
        stop2 = self.run_hook({"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"})
        self.assertEqual(stop2.get("decision"), "stop")

        # When transcript_full.jsonl carries Layer:, first stop succeeds cleanly
        self.run_hook({
            "hookEventName": "PreToolUse",
            "lastUserInput": "Turn 2 edit",
            "toolCall": {"id": "c2", "name": "edit_file", "args": {"Path": str(app_py), "Target": "x = 1\n", "Replacement": "x = 2\n"}},
        })
        self.run_hook({
            "hookEventName": "PostToolUse",
            "lastUserInput": "Turn 2 edit",
            "toolCall": {"id": "c2", "name": "edit_file", "args": {"Path": str(app_py), "Target": "x = 1\n", "Replacement": "x = 2\n"}},
        })
        self.transcript_full.write_text(
            json.dumps({"type": "USER_INPUT", "content": "Turn 2 edit"}) + "\n"
            + json.dumps({"type": "PLANNER_RESPONSE", "content": "Done.\n\nLayer: app (app.py); no workaround."}) + "\n",
            encoding="utf-8",
        )
        stop3 = self.run_hook({
            "hookEventName": "Stop",
            "lastUserInput": "Turn 2 edit",
            "terminationReason": "NO_TOOL_CALL",
        })
        self.assertEqual(stop3.get("decision"), "stop")

    def test_check_draft_timeout_terminates_process_tree(self):
        hook_mod = _load_module("test_powertools_hook_mod", HOOK_SCRIPT)
        pid_file = self.root / "grandchild.pid"
        child_script = self.root / "slow_checker.py"
        child_script.write_text(
            "import pathlib, subprocess, sys, time\n"
            f"pid_file = pathlib.Path({json.dumps(str(pid_file))})\n"
            "flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n"
            "gc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)\n"
            "pid_file.write_text(str(gc.pid), encoding='utf-8')\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )

        with self.assertRaises(subprocess.TimeoutExpired):
            hook_mod.article_check.run_bounded_command(
                [sys.executable, str(child_script)],
                timeout=1.5,
                cwd=str(self.root),
            )

        self.assertTrue(pid_file.exists(), "child did not spawn grandchild before timeout")
        gc_pid = int(pid_file.read_text(encoding="utf-8").strip())
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x101000, False, gc_pid)
            if handle:
                try:
                    wait_rc = kernel32.WaitForSingleObject(handle, 2000)
                    self.assertEqual(wait_rc, 0, f"grandchild PID {gc_pid} survived timeout")
                finally:
                    kernel32.CloseHandle(handle)
        else:
            alive = False
            for _ in range(20):
                try:
                    os.kill(gc_pid, 0)
                    alive = True
                    import time
                    time.sleep(0.05)
                except ProcessLookupError:
                    alive = False
                    break
            self.assertFalse(alive, f"grandchild PID {gc_pid} survived timeout")

        draft = self.workspace / "drafts" / "post.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("# Post\n", encoding="utf-8")
        with unittest.mock.patch.object(
            hook_mod.article_check,
            "run_bounded_command",
            side_effect=subprocess.TimeoutExpired([sys.executable], 30),
        ):
            notice = hook_mod.check_draft(str(draft))
        self.assertIn("timed out; check the draft by hand.", notice)


def _load_module(name: str, path: pathlib.Path, extra_sys_paths: list[pathlib.Path] | None = None):
    added: list[str] = []
    for p in extra_sys_paths or []:
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
            added.append(sp)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for sp in added:
            if sp in sys.path:
                sys.path.remove(sp)


class CraftScriptHardeningTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name)

    def test_office_helpers_identical_and_safe_extract_bounded(self):
        for rel in (
            "office/helpers/__init__.py",
            "office/soffice.py",
            "office/validators/base.py",
            "office/validators/docx.py",
            "office/validators/redlining.py",
        ):
            blobs = {
                skill: (CRAFT_DIR / "skills" / skill / "scripts" / rel).read_bytes()
                for skill in ("docx", "pptx", "xlsx")
            }
            self.assertEqual(len(set(blobs.values())), 1, f"{rel} differs across docx/pptx/xlsx")

        helpers = _load_module("test_office_helpers", CRAFT_DIR / "skills" / "docx" / "scripts" / "office" / "helpers" / "__init__.py")

        # Entry count limit
        z_many = self.root / "many.zip"
        with zipfile.ZipFile(z_many, "w") as zf:
            for idx in range(4):
                zf.writestr(f"f{idx}.txt", b"a")
        with zipfile.ZipFile(z_many, "r") as zf:
            with self.assertRaises(ValueError):
                helpers.safe_extract(zf, self.root / "out_many", max_entries=3)

        # Declared total byte limit
        z_decl = self.root / "decl.zip"
        with zipfile.ZipFile(z_decl, "w") as zf:
            zf.writestr("a.txt", b"x" * 60)
            zf.writestr("b.txt", b"y" * 60)
        with zipfile.ZipFile(z_decl, "r") as zf:
            with self.assertRaises(ValueError):
                helpers.safe_extract(zf, self.root / "out_decl", max_bytes=100)

        # Streaming byte limit catches oversized stream despite small declared header and removes partial target
        z_stream = self.root / "stream.zip"
        with zipfile.ZipFile(z_stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.txt", b"A" * 100)
        out_stream = self.root / "out_stream"
        with zipfile.ZipFile(z_stream, "r") as zf:
            with unittest.mock.patch.object(zf, "open", return_value=io.BytesIO(b"B" * 1024)):
                with self.assertRaises(ValueError):
                    helpers.safe_extract(zf, out_stream, max_member_bytes=512, max_bytes=4096)
        self.assertFalse((out_stream / "bomb.txt").exists())

    def test_xlsx_recalc_distinguishes_text_from_error_cells(self):
        xlsx_scripts = CRAFT_DIR / "skills" / "xlsx" / "scripts"
        recalc = _load_module("test_xlsx_recalc", xlsx_scripts / "recalc.py", [xlsx_scripts])

        wb_path = self.root / "book.xlsx"
        with zipfile.ZipFile(wb_path, "w") as zf:
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>',
            )
            zf.writestr(
                "xl/sharedStrings.xml",
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<si><t>Use IFERROR to handle #N/A</t></si>'
                '<si><t>No #REF! errors remain</t></si>'
                '</sst>',
            )
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1">'
                '<c r="A1" t="s"><v>0</v></c>'
                '<c r="A2" t="s"><v>1</v></c>'
                '<c r="A3" t="inlineStr"><is><t>No #DIV/0! issue</t></is></c>'
                '<c r="A4" t="str"><f>"#N/A"</f><v>#N/A</v></c>'
                '</row></sheetData></worksheet>',
            )

        fake_defused = types.ModuleType("defusedxml")
        fake_defused.ElementTree = ET
        with unittest.mock.patch.dict(sys.modules, {"defusedxml": fake_defused, "defusedxml.ElementTree": ET}):
            errors, formulas = recalc._scan_xml(str(wb_path))
        self.assertEqual(formulas, 1)
        self.assertEqual(sum(len(v) for v in errors.values()), 0, errors)

        # Add a genuine error cell (t="e")
        wb_err = self.root / "book_err.xlsx"
        with zipfile.ZipFile(wb_path, "r") as zin, zipfile.ZipFile(wb_err, "w") as zout:
            for item in zin.infolist():
                if item.filename == "xl/worksheets/sheet1.xml":
                    zout.writestr(
                        item,
                        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                        '<row r="1">'
                        '<c r="A1" t="s"><v>0</v></c>'
                        '<c r="B1" t="e"><f>1/0</f><v>#DIV/0!</v></c>'
                        '</row></sheetData></worksheet>',
                    )
                else:
                    zout.writestr(item, zin.read(item.filename))

        with unittest.mock.patch.dict(sys.modules, {"defusedxml": fake_defused, "defusedxml.ElementTree": ET}):
            errors2, formulas2 = recalc._scan_xml(str(wb_err))
        self.assertEqual(formulas2, 1)
        self.assertEqual(errors2["#DIV/0!"], ["Sheet1!B1"])

        # Openpyxl fallback path: data_type=="s" ignored, data_type=="e" reported
        class FakeCell:
            def __init__(self, coord, data_type, value):
                self.coordinate = coord
                self.data_type = data_type
                self.value = value

        class FakeSheet:
            def __init__(self, cells):
                self._cells = {i: c for i, c in enumerate(cells)}

            def iter_rows(self):
                return []

        class FakeWorkbook:
            def __init__(self, sheets):
                self._sheets = sheets
                self.sheetnames = list(sheets)

            def __getitem__(self, name):
                return self._sheets[name]

            def close(self):
                pass

        fake_openpyxl = types.ModuleType("openpyxl")
        fake_openpyxl.worksheet = types.ModuleType("openpyxl.worksheet")
        fake_formula = types.ModuleType("openpyxl.worksheet.formula")
        fake_formula.ArrayFormula = type("ArrayFormula", (), {})

        wb_data = FakeWorkbook({
            "S1": FakeSheet([
                FakeCell("A1", "s", "Use IFERROR to handle #N/A"),
                FakeCell("A2", "s", "No #REF! errors remain"),
                FakeCell("B2", "e", "#REF!"),
            ])
        })
        wb_forms = FakeWorkbook({
            "S1": FakeSheet([FakeCell("B2", "f", "=Sheet9!A1")])
        })
        fake_openpyxl.load_workbook = lambda fn, data_only=False: wb_data if data_only else wb_forms
        with unittest.mock.patch.dict(sys.modules, {
            "openpyxl": fake_openpyxl,
            "openpyxl.worksheet": fake_openpyxl.worksheet,
            "openpyxl.worksheet.formula": fake_formula,
        }):
            op_errors, op_formulas = recalc._scan_with_openpyxl("dummy.xlsx")
        self.assertEqual(op_formulas, 1)
        self.assertEqual(op_errors["#REF!"], ["S1!B2"])
        self.assertEqual(sum(len(v) for v in op_errors.values()), 1)

    def test_soffice_timeout_terminates_process_tree_before_reap(self):
        docx_scripts = CRAFT_DIR / "skills" / "docx" / "scripts"
        soffice = _load_module("test_office_soffice", docx_scripts / "office" / "soffice.py", [docx_scripts])

        fake_proc = unittest.mock.MagicMock()
        fake_proc.pid = 42424
        fake_proc.returncode = -9
        fake_proc.poll.return_value = None
        fake_proc.communicate.side_effect = [subprocess.TimeoutExpired(["soffice"], 1), ("", "")]

        with unittest.mock.patch.object(soffice, "get_soffice_env", return_value={}), \
             unittest.mock.patch.object(soffice.subprocess, "Popen", return_value=fake_proc), \
             unittest.mock.patch.object(soffice.subprocess, "run") as mock_run, \
             unittest.mock.patch.object(soffice.os, "killpg", create=True) as mock_killpg:
            with self.assertRaises(subprocess.TimeoutExpired):
                soffice.run_soffice(["--headless", "file.xlsx"], capture_output=True, text=True, timeout=1)

        self.assertEqual(fake_proc.communicate.call_count, 2)
        if os.name == "nt":
            mock_run.assert_called_once()
            self.assertEqual(mock_run.call_args[0][0], ["taskkill", "/T", "/F", "/PID", "42424"])
        else:
            mock_killpg.assert_called_once_with(42424, soffice.signal.SIGKILL)

    def test_fill_fillable_fields_writes_atomically(self):
        existing_pdf = self.root / "out.pdf"
        existing_pdf.write_bytes(b"%PDF-existing")
        fields_json = self.root / "fields.json"
        fields_json.write_text('[{"field_id": "name", "page": 1, "value": "Alice"}]', encoding="utf-8")
        in_pdf = self.root / "in.pdf"
        in_pdf.write_bytes(b"%PDF-input")

        class BrokenWriter:
            def __init__(self, clone_from=None):
                self.pages = [object()]
            def update_page_form_field_values(self, *args, **kwargs):
                pass
            def set_need_appearances_writer(self, val):
                pass
            def write(self, fh):
                fh.write(b"%PDF-partial")
                raise OSError("No space left on device")

        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = lambda p: object()
        fake_pypdf.PdfWriter = BrokenWriter
        fake_extract = types.ModuleType("extract_form_field_info")
        fake_extract.get_field_info = lambda r: [{"field_id": "name", "page": 1, "type": "text"}]

        fill_path = CRAFT_DIR / "skills" / "pdf" / "scripts" / "fill_fillable_fields.py"
        with unittest.mock.patch.dict(sys.modules, {"pypdf": fake_pypdf, "extract_form_field_info": fake_extract}):
            fill_mod = _load_module("test_fill_fillable_fields", fill_path)
            with self.assertRaises(OSError):
                fill_mod.fill_pdf_fields(str(in_pdf), str(fields_json), str(existing_pdf))

        self.assertEqual(existing_pdf.read_bytes(), b"%PDF-existing")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_directory_mode_atomic_writes_preserve_existing_xml(self):
        docx_scripts = CRAFT_DIR / "skills" / "docx" / "scripts"
        helpers = _load_module("test_atomic_helpers", docx_scripts / "office" / "helpers" / "__init__.py")

        target = self.root / "part.xml"
        target.write_bytes(b"<root>original</root>")
        with unittest.mock.patch.object(helpers.os, "fdopen", side_effect=OSError("No space left on device")):
            with self.assertRaises(OSError):
                helpers.atomic_write_bytes(target, b"<root>partial</root>")
        self.assertEqual(target.read_bytes(), b"<root>original</root>")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

        with unittest.mock.patch.object(helpers.os, "replace", side_effect=OSError("No space left on device")):
            with self.assertRaises(OSError):
                helpers.atomic_write_bytes(target, b"<root>replacement</root>")
        self.assertEqual(target.read_bytes(), b"<root>original</root>")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

        unpacked = self.root / "unpacked"
        word_dir = unpacked / "word"
        word_dir.mkdir(parents=True)
        doc_xml = word_dir / "document.xml"
        orig_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:body><w:p><w:r><w:t>Hello</w:t></w:r><w:r><w:t> world</w:t></w:r></w:p></w:body>'
            b'</w:document>'
        )
        doc_xml.write_bytes(orig_xml)

        import xml.dom.minidom as xml_minidom
        fake_defused = types.ModuleType("defusedxml")
        fake_defused.minidom = xml_minidom
        with unittest.mock.patch.dict(sys.modules, {"defusedxml": fake_defused, "defusedxml.minidom": xml_minidom}):
            merge_runs = _load_module("test_merge_runs", docx_scripts / "merge_runs.py", [docx_scripts])
            with unittest.mock.patch("office.helpers.os.replace", side_effect=OSError("No space left on device")):
                count, msg = merge_runs.merge_runs(str(unpacked))

        self.assertEqual(count, 0)
        self.assertIn("No space left on device", msg)
        self.assertEqual(doc_xml.read_bytes(), orig_xml)
        self.assertEqual(list(word_dir.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
