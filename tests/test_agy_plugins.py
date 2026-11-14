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

        for p in sorted(CRAFT_DIR.rglob("*")):
            if p.name == "SKILL.md" or p.suffix == ".py":
                txt = p.read_text(encoding="utf-8")
                self.assertNotIn(".extractall(", txt, f"unbounded extractall in {p}")
                self.assertNotIn("unzip -q", txt, f"unbounded unzip in {p}")

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
            "git push --no-mirror origin main",
            "git push --no-mir origin main",
            "git push --recurse-submodules check origin main",
            "git push --tags origin",
            "git branch -f feature-local",
            'git commit -m "avoid git push -f accidental match"',
            'git push origin -- "--force"',
            "rm -rf build",
            "rm -rf ./build/..",
            r"Remove-Item R:\scratch\temp -Recurse -Force",
            r"Remove-Item R:\scratch\.\temp -Recurse -Force",
            r"Remove-Item C:\ -Recurse:$false",
            r"Remove-Item R:\scratch\temp -Recur -Force",
            r"Remove-Item -Filter *.tmp C:",
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
            "git push --mirror origin",
            "git push --mir origin",
            "git push --m origin",
            "git push --repo=origin --mirror",
            "git -c remote.origin.mirror=true push origin",
            "git -c remote.origin.mirror push origin",
            "git --config-env=remote.origin.mirror=MIR push origin",
            "git push --delete origin old-branch",
            "git push --del origin old-branch",
            "git push -d origin old-branch",
            "git push --prune origin",
            "git push --pru origin",
            "git push --force-w origin main",
            "git push --force-i origin main",
            "git push --rep origin +HEAD:main",
            "git push --rep origin :old-branch",
            "git push origin :old-branch",
            "gh repo delete owner/repo --yes",
            "gh -R owner/repo repo delete",
            "Format-Volume -DriveLetter E -FileSystem NTFS",
            "rm -rf /",
            'rm "-rf" "/"',
            "rm --rec /",
            "rm -rf /./*",
            "rm -rf /.",
            "rm -rf /foo/..",
            "rm -rf /foo/../*",
            "rm --no-preserve /tmp/x",
            r"rm C:\ -Recur -Force",
            r"Remove-Item C:\ -Recur -Force",
            r"Remove-Item -Recurse -Force C:\.\*",
            r"Remove-Item -Recurse C:\foo\..\*",
            r"Remove-Item C:\ -R",
            r"Remove-Item -LiteralPath C:\ -Rec",
            "Remove-Item / -Recur",
            r"ri -LP D:\ -Recurse",
            r"del C:\* -Recur",
            r"del /s /q C:\.\*.*",
            'bash -lc "git push --force origin main"',
            'bash -lc "git push \\"--force\\" origin main"',
            'wsl -d Ubuntu bash -lc "git push --force origin main"',
            'pwsh -NoProfile -Command "Remove-Item -Recurse C:\\"',
            'pwsh -NoP -Com "Remove-Item C:\\ -Recur -Force"',
            "pwsh -EncodedCommand ZwBpAHQAIABwAHUAcwBoACAALQAtAGYAbwByAGMAZQAgAG8AcgBpAGcAaQBuACAAbQBhAGkAbgA=",
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
        self.assertIn("Claude researches, writes and rewrites", msg)
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

        # Exited parent whose pipe-inheriting grandchild outlives it must still terminate grandchild on timeout
        gc_pid_file = self.root / "exited_parent_gc.pid"
        exited_parent = self.root / "exited_parent.py"
        exited_parent.write_text(
            "import pathlib, subprocess, sys\n"
            f"pid_file = pathlib.Path({json.dumps(str(gc_pid_file))})\n"
            "flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n"
            "gc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], stdin=subprocess.DEVNULL, creationflags=flags)\n"
            "pid_file.write_text(str(gc.pid), encoding='utf-8')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        with self.assertRaises(subprocess.TimeoutExpired):
            hook_mod.article_check.run_bounded_command(
                [sys.executable, str(exited_parent)],
                timeout=1.5,
                cwd=str(self.root),
            )
        self.assertTrue(gc_pid_file.exists(), "exited parent did not spawn grandchild before timeout")
        exited_gc_pid = int(gc_pid_file.read_text(encoding="utf-8").strip())
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x101000, False, exited_gc_pid)
            if handle:
                try:
                    self.assertEqual(kernel32.WaitForSingleObject(handle, 2000), 0, f"grandchild PID {exited_gc_pid} survived")
                finally:
                    kernel32.CloseHandle(handle)
        else:
            alive = False
            for _ in range(20):
                try:
                    os.kill(exited_gc_pid, 0)
                    alive = True
                    import time
                    time.sleep(0.05)
                except ProcessLookupError:
                    alive = False
                    break
            self.assertFalse(alive, f"grandchild PID {exited_gc_pid} survived")


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
            "office/helpers/pptx_chart.py",
            "office/helpers/pptx_slide.py",
            "office/helpers/pptx_theme.py",
            "office/pack.py",
            "office/soffice.py",
            "office/unpack.py",
            "office/validate.py",
            "office/validators/__init__.py",
            "office/validators/base.py",
            "office/validators/docx.py",
            "office/validators/pptx.py",
            "office/validators/redlining.py",
        ):
            blobs = {
                skill: (CRAFT_DIR / "skills" / skill / "scripts" / rel).read_bytes()
                for skill in ("docx", "pptx", "xlsx")
            }
            self.assertEqual(len(set(blobs.values())), 1, f"{rel} differs across docx/pptx/xlsx")

        helpers = _load_module("test_office_helpers", CRAFT_DIR / "skills" / "docx" / "scripts" / "office" / "helpers" / "__init__.py")

        self.assertEqual(helpers.opc_target(" ../media/image1.png ", "ppt/slides/slide1.xml"), "ppt/media/image1.png")
        self.assertEqual(helpers.opc_target("\t../media/two%20%20spaces.png\n", "ppt/slides/slide1.xml"), "ppt/media/two  spaces.png")
        self.assertIsNone(helpers.opc_target("https://example.com/x", "ppt/slides/slide1.xml", "External"))
        self.assertIsNone(helpers.opc_target("http://[::1]:8080/a", "ppt/slides/slide1.xml", "External"))
        self.assertIsNone(helpers.opc_target("http://[v1.a]/a", "ppt/slides/slide1.xml", "External"))
        self.assertIsNone(helpers.opc_target("http://@host:80/a", "ppt/slides/slide1.xml", "External"))
        self.assertTrue(helpers.is_valid_any_uri("http://[v1.a]/a"))
        self.assertFalse(helpers.is_valid_any_uri("1bad:type"))
        self.assertFalse(helpers.is_valid_any_uri("http://host:abc/a"))
        self.assertEqual(helpers.opc_target("slide1.xml#anchor", "ppt/slides/slide2.xml", "Internal"), "ppt/slides/slide1.xml")
        self.assertEqual(helpers.opc_target("#bookmark", "word/document.xml"), "word/document.xml")
        for bad_target, src_part, tmode in (
            ("ftp://example.com/missing.png", "ppt/slides/slide1.xml", "Internal"),
            ("http://example.com/missing.png", "ppt/slides/slide1.xml", ""),
            ("//example.com/ppt/slides/slide1.xml", "ppt/slides/slide1.xml", "Internal"),
            ("", "ppt/slides/slide1.xml", "Internal"),
            ("slides/slide1.xml", "ppt/presentation.xml", "external"),
            ("/ppt//slides/slide1.xml", "ppt/presentation.xml", "Internal"),
            ("slides/slide1.xml/", "ppt/presentation.xml", "Internal"),
            ("slides/.", "ppt/presentation.xml", "Internal"),
            ("slides%2fslide1.xml", "ppt/presentation.xml", "Internal"),
            ("slides/slide1.xml#bad%GG", "ppt/presentation.xml", "Internal"),
            ("slides/slide%GG.xml", "ppt/presentation.xml", "Internal"),
            ("slides/slide%FF.xml", "ppt/presentation.xml", "Internal"),
            ("slides/slide1.xml#bad%FF", "ppt/presentation.xml", "Internal"),
            ("slides/slide1.xml#a#b", "ppt/presentation.xml", "Internal"),
            ("slides/slide[1].xml", "ppt/presentation.xml", "Internal"),
            ("slides/slide1.xml#[bad]", "ppt/presentation.xml", "Internal"),
            ("1bad:slide1.xml", "ppt/presentation.xml", "Internal"),
            ("https://example.com/bad%GG", "ppt/slides/slide1.xml", "External"),
            ("http://host:abc/a", "ppt/slides/slide1.xml", "External"),
            ("http://host:/a", "ppt/slides/slide1.xml", "External"),
            ("1bad:type", "ppt/slides/slide1.xml", "External"),
            (":bad", "ppt/slides/slide1.xml", "External"),
            ("bad_scheme:foo", "ppt/slides/slide1.xml", "External"),
            ("http://u@v@host/a", "ppt/slides/slide1.xml", "External"),
            ("http://[not-ipv6]/a", "ppt/slides/slide1.xml", "External"),
            ("http://[::1]:abc/a", "ppt/slides/slide1.xml", "External"),
        ):
            with self.assertRaises(ValueError, msg=(bad_target, src_part, tmode)):
                helpers.opc_target(bad_target, src_part, tmode)

        self.assertEqual(helpers.normalize_part_name(" /ppt/slides/slide%201.xml "), "ppt/slides/slide 1.xml")
        self.assertEqual(helpers.normalize_part_name("/ppt/slides/slid%C3%A91.xml"), "ppt/slides/slid\u00e91.xml")
        self.assertIsNone(helpers.normalize_part_name("ppt/slides/slide1.xml"))
        self.assertIsNone(helpers.normalize_part_name("/../outside.xml"))
        for bad_part in (
            "/ppt//slides/slide1.xml",
            "/ppt/slides/slide1.xml/",
            "/",
            "/ppt/./slides/slide1.xml",
            "/ppt/slides/../slides/slide1.xml",
            "/ppt%2Fslides/slide1.xml",
            "/ppt/slides/slide1.xml#frag",
            "/ppt/slides/slide1.xml?q=1",
            "/ppt/slides/%73lide1.xml",
            "/ppt/slides/slide%31.xml",
            "/ppt/slides/slide%2d1.xml",
            "/ppt/slides/slide%2e1.xml",
            "/ppt/slides/slide%5f1.xml",
            "/ppt/slides/slide%7e1.xml",
            "/ppt/slides/slide%GG.xml",
            "/ppt/slides/slide%FF.xml",
            "/ppt/slides/slide[1].xml",
        ):
            self.assertIsNone(helpers.normalize_part_name(bad_part), bad_part)
        rel_el = ET.Element("Relationship", Id=" rId\u00e9 ", Type=" http://example.com/t ", Target=" ../media/a\tb.png ", TargetMode="Internal")
        self.assertEqual(
            helpers.read_relationship(rel_el),
            ("rId\u00e9", "http://example.com/t", "../media/a b.png", "Internal"),
        )

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

        # Archive validation failure must propagate to recalc() and refuse LibreOffice
        with (
            unittest.mock.patch.object(
                recalc,
                "validate_archive",
                side_effect=ValueError("archive entry count 10001 exceeds limit 10000"),
            ),
            unittest.mock.patch.object(recalc, "get_soffice_env", return_value={}),
            unittest.mock.patch.object(recalc, "run_soffice", side_effect=AssertionError("soffice must not run")),
        ):
            with self.assertRaises(ValueError):
                recalc.external_links_at_risk(str(wb_path))
            res_default = recalc.recalc(str(wb_path))
            self.assertIn("Could not inspect", res_default.get("error", ""))
            res_force = recalc.recalc(str(wb_path), force=True)
            self.assertIn("Could not validate", res_force.get("error", ""))

        # External links inspection uses bounded pure-XML without calling openpyxl.load_workbook
        wb_ext = self.root / "book_ext.xlsx"
        with zipfile.ZipFile(wb_ext, "w") as zf:
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                '<definedNames>'
                '<definedName name="GlobalExt">[1]Ext!A1</definedName>'
                '<definedName name="DerivedExt">GlobalExt+1</definedName>'
                '<definedName name="LocalExt" localSheetId="0">[1]Ext!A2</definedName>'
                '<definedName name="ExternalValue">[1]Sheet1!$A$1</definedName>'
                '<definedName name="DerivedLower">externalvalue+1</definedName>'
                '</definedNames></workbook>',
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1">'
                '<c r="A1"><f>[1]Ext!B1</f><v></v></c>'
                '<c r="A2"><f>[1]Ext!B2</f><v>42</v></c>'
                '<c r="A3"><f>DerivedExt</f></c>'
                '<c r="A4"><f>LocalExt</f></c>'
                '<c r="A5"><f>externalvalue</f></c>'
                '<c r="A6"><f>DERIVEDLOWER</f></c>'
                '<c r="B1"><f t="array" ref="B1:B2">[1]Ext!C1:C2</f><v></v></c>'
                '<c r="C1"><f>"ExternalValue"</f></c>'
                '<c r="C2"><f>IF(1,"ExternalValue","ok")</f></c>'
                '<c r="C3"><f>"[1]Ext!Z9"</f></c>'
                '</row></sheetData></worksheet>',
            )

        fake_openpyxl.load_workbook = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("openpyxl must not be called"))
        with unittest.mock.patch.dict(sys.modules, {
            "openpyxl": fake_openpyxl,
            "openpyxl.worksheet": fake_openpyxl.worksheet,
            "openpyxl.worksheet.formula": fake_formula,
        }):
            self.assertEqual(
                recalc.external_links_at_risk(str(wb_ext)),
                ["Sheet1!A1", "Sheet1!A3", "Sheet1!A4", "Sheet1!A5", "Sheet1!A6", "Sheet1!B1"],
            )
            # Merged-cell bomb with unused externalLink or single-quoted ref is rejected immediately
            for idx_bomb, merge_attr in enumerate(('ref="A1:XFD1048576"', "ref='A1:XFD1048576'")):
                wb_bomb = self.root / f"book_merge_bomb_{idx_bomb}.xlsx"
                with zipfile.ZipFile(wb_bomb, "w") as zf:
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
                    zf.writestr("xl/externalLinks/unused.xml", "<externalLink/>")
                    zf.writestr(
                        "xl/worksheets/sheet1.xml",
                        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                        '<sheetData/><mergeCells count="1">'
                        f'<mergeCell {merge_attr}/>'
                        '</mergeCells></worksheet>',
                    )
                with self.assertRaisesRegex(ValueError, "merged cell count exceeds limit"):
                    recalc.external_links_at_risk(str(wb_bomb))
                with self.assertRaisesRegex(ValueError, "merged cell count exceeds limit"):
                    recalc._scan_xml(str(wb_bomb))
                rep = recalc._report(str(wb_bomb))
                self.assertIn("merged cell count exceeds limit", rep.get("error", ""))
                with unittest.mock.patch.object(recalc, "get_soffice_env", return_value={}), \
                     unittest.mock.patch.object(recalc, "run_soffice", side_effect=AssertionError("soffice must not run")):
                    r_def = recalc.recalc(str(wb_bomb))
                    self.assertIn("merged cell count exceeds limit", r_def.get("error", ""))
                    r_force = recalc.recalc(str(wb_bomb), force=True)
                    self.assertIn("merged cell count exceeds limit", r_force.get("error", ""))

            # Even without defusedxml installed, stdlib Expat guard rejects DOCTYPE/ENTITY
            wb_dtd = self.root / "book_dtd.xlsx"
            with zipfile.ZipFile(wb_dtd, "w") as zf:
                zf.writestr("xl/workbook.xml", '<!DOCTYPE wb [<!ENTITY x "1">]><wb/>')
                zf.writestr("xl/_rels/workbook.xml.rels", "<Relationships/>")
                zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            with unittest.mock.patch.dict(sys.modules, {"defusedxml": None, "defusedxml.ElementTree": None}):
                with self.assertRaisesRegex(ValueError, "DTD and entity declarations are forbidden"):
                    recalc.external_links_at_risk(str(wb_dtd))

            # UTF-16 worksheet XML without external links must still enforce merged-cell budget
            wb_utf16 = self.root / "book_utf16_bomb.xlsx"
            with zipfile.ZipFile(wb_utf16, "w") as zf:
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
                    "xl/worksheets/sheet1.xml",
                    (
                        '<?xml version="1.0" encoding="UTF-16"?>'
                        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                        '<sheetData/><mergeCells count="1"><mergeCell ref="A1:XFD1048576"/></mergeCells>'
                        '</worksheet>'
                    ).encode("utf-16"),
                )
            with self.assertRaisesRegex(ValueError, "merged cell count exceeds limit"):
                recalc.external_links_at_risk(str(wb_utf16))
            with self.assertRaisesRegex(ValueError, "merged cell count exceeds limit"):
                recalc._scan_xml(str(wb_utf16))
            with unittest.mock.patch.object(recalc, "get_soffice_env", return_value={}), \
                 unittest.mock.patch.object(recalc, "run_soffice", side_effect=AssertionError("soffice must not run")):
                self.assertIn("merged cell count exceeds limit", recalc.recalc(str(wb_utf16)).get("error", ""))
                self.assertIn("merged cell count exceeds limit", recalc.recalc(str(wb_utf16), force=True).get("error", ""))

            # localSheetId scoping and shadowing between workbook-global and sheet-local names
            wb_scoped = self.root / "book_scoped.xlsx"
            with zipfile.ZipFile(wb_scoped, "w") as zf:
                zf.writestr(
                    "xl/workbook.xml",
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    '<sheets>'
                    '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
                    '<sheet name="Sheet2" sheetId="2" r:id="rId2"/>'
                    '</sheets>'
                    '<definedNames>'
                    '<definedName name="ExternalValue">[1]Sheet1!$A$1</definedName>'
                    '<definedName name="ExternalValue" localSheetId="0">42</definedName>'
                    '<definedName name="Sheet2OnlyExt" localSheetId="1">[1]Sheet1!$B$2</definedName>'
                    '</definedNames></workbook>',
                )
                zf.writestr(
                    "xl/_rels/workbook.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
                    '</Relationships>',
                )
                zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
                zf.writestr(
                    "xl/worksheets/sheet1.xml",
                    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                    '<row r="1">'
                    '<c r="A1"><f>ExternalValue</f></c>'
                    '<c r="A2"><f>Sheet2!Sheet2OnlyExt</f></c>'
                    '</row></sheetData></worksheet>',
                )
                zf.writestr(
                    "xl/worksheets/sheet2.xml",
                    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                    '<row r="1">'
                    '<c r="A1"><f>ExternalValue</f></c>'
                    '<c r="A2"><f>Sheet1!ExternalValue</f></c>'
                    '</row></sheetData></worksheet>',
                )
            self.assertEqual(recalc.external_links_at_risk(str(wb_scoped)), ["Sheet1!A2", "Sheet2!A1"])

            # Streaming sibling <c/> flood must stay within O(1) memory bound
            wb_flood = self.root / "book_flood.xlsx"
            flood_xml = (
                b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                b'<sheetData><row r="1">' + (b"<c/>" * 100_000) + b"</row></sheetData></worksheet>"
            )
            with zipfile.ZipFile(wb_flood, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(
                    "xl/workbook.xml",
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
                )
                zf.writestr(
                    "xl/_rels/workbook.xml.rels",
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                    '</Relationships>',
                )
                zf.writestr("xl/worksheets/sheet1.xml", flood_xml)
            del flood_xml

            import tracemalloc
            tracemalloc.start()
            try:
                self.assertEqual(recalc.external_links_at_risk(str(wb_flood)), [])
                _, peak_bytes = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertLess(peak_bytes, 4 * 1024 * 1024, f"streaming peak exceeded 4 MiB: {peak_bytes}")

    def test_soffice_timeout_terminates_process_tree_before_reap(self):
        docx_scripts = CRAFT_DIR / "skills" / "docx" / "scripts"
        soffice = _load_module("test_office_soffice", docx_scripts / "office" / "soffice.py", [docx_scripts])

        fake_proc = unittest.mock.MagicMock()
        fake_proc.pid = 42424
        fake_proc.returncode = -9
        fake_proc.poll.return_value = 0
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
            self.assertGreaterEqual(mock_killpg.call_count, 1)
            mock_killpg.assert_any_call(42424, soffice.signal.SIGKILL)

        gc_pid_file = self.root / "soffice_exited_gc.pid"
        exited_parent = self.root / "soffice_exited_parent.py"
        exited_parent.write_text(
            "import pathlib, subprocess, sys\n"
            f"pid_file = pathlib.Path({json.dumps(str(gc_pid_file))})\n"
            "flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)\n"
            "gc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], stdin=subprocess.DEVNULL, creationflags=flags)\n"
            "pid_file.write_text(str(gc.pid), encoding='utf-8')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        with self.assertRaises(subprocess.TimeoutExpired):
            soffice.run_process_tree(
                [sys.executable, str(exited_parent)],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
        self.assertTrue(gc_pid_file.exists())
        gc_pid = int(gc_pid_file.read_text(encoding="utf-8").strip())
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x101000, False, gc_pid)
            if handle:
                try:
                    self.assertEqual(kernel32.WaitForSingleObject(handle, 2000), 0, f"grandchild PID {gc_pid} survived")
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
            self.assertFalse(alive, f"grandchild PID {gc_pid} survived")

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

    def test_unpack_and_pack_cli_enforce_budgets_and_atomicity(self):
        office_dir = CRAFT_DIR / "skills" / "docx" / "scripts" / "office"
        unpack_mod = _load_module("test_office_unpack", office_dir / "unpack.py", [office_dir])
        pack_mod = _load_module("test_office_pack", office_dir / "pack.py", [office_dir])

        pkg_in = self.root / "sample.docx"
        with zipfile.ZipFile(pkg_in, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
            zf.writestr("word/document.xml", "<w:document/>")

        unpacked_dir = self.root / "unpacked"
        unpack_mod.unpack_package(pkg_in, unpacked_dir)
        self.assertEqual((unpacked_dir / "word" / "document.xml").read_text(encoding="utf-8"), "<w:document/>")

        pkg_out = self.root / "repacked.docx"
        pack_mod.pack_package(unpacked_dir, pkg_out)
        with zipfile.ZipFile(pkg_out, "r") as zf:
            self.assertEqual([i.filename for i in zf.infolist() if i.is_dir()], [])
            self.assertEqual(zf.read("word/document.xml"), b"<w:document/>")

        # Existing non-empty destination is refused without modification
        keep_marker = unpacked_dir / "marker.txt"
        keep_marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            unpack_mod.unpack_package(pkg_in, unpacked_dir)
        self.assertEqual(keep_marker.read_text(encoding="utf-8"), "keep")

        # Overflow during unpack fails atomically and leaves no destination or staging dir
        oversized_dest = self.root / "oversized_dest"
        with unittest.mock.patch.object(unpack_mod, "safe_extract", side_effect=ValueError("archive exceeds unpacked byte budget")):
            with self.assertRaises(ValueError):
                unpack_mod.unpack_package(pkg_in, oversized_dest)
        self.assertFalse(oversized_dest.exists())
        self.assertEqual(list(self.root.glob("oversized_dest.*.tmp")), [])

    def test_thumbnail_and_helpers_enforce_member_and_aggregate_limits(self):
        import xml.dom.minidom as xml_minidom

        helpers = _load_module(
            "test_office_helpers_stream",
            CRAFT_DIR / "skills" / "pptx" / "scripts" / "office" / "helpers" / "__init__.py",
        )
        pptx_scripts = CRAFT_DIR / "skills" / "pptx" / "scripts"

        extra_mods: dict[str, types.ModuleType] = {}
        if importlib.util.find_spec("defusedxml") is None:
            fake_defused = types.ModuleType("defusedxml")
            fake_defused.minidom = xml_minidom
            fake_defused.ElementTree = ET
            extra_mods["defusedxml"] = fake_defused
            extra_mods["defusedxml.minidom"] = xml_minidom
            extra_mods["defusedxml.ElementTree"] = ET
        if importlib.util.find_spec("PIL") is None:
            fake_pil = types.ModuleType("PIL")
            fake_pil.Image = types.SimpleNamespace()
            fake_pil.ImageDraw = types.SimpleNamespace()
            fake_pil.ImageFont = types.SimpleNamespace()
            extra_mods["PIL"] = fake_pil

        with unittest.mock.patch.dict(sys.modules, extra_mods):
            thumbnail = _load_module("test_pptx_thumbnail", pptx_scripts / "thumbnail.py", [pptx_scripts])
            thumbnail.validate_archive = helpers.validate_archive
            thumbnail.open_zip_member = helpers.open_zip_member
            thumbnail.read_zip_member = helpers.read_zip_member

            rels_xml = (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide2.xml"/>'
                "</Relationships>"
            )
            pres_xml = (
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<p:sldIdLst><p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst>'
                "</p:presentation>"
            )

            valid_pptx = self.root / "valid.pptx"
            with zipfile.ZipFile(valid_pptx, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("ppt/_rels/presentation.xml.rels", rels_xml)
                zf.writestr("ppt/presentation.xml", pres_xml)
                zf.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')
                zf.writestr("ppt/slides/slide2.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" show="0"/>')

            self.assertEqual(
                thumbnail.get_slide_info(valid_pptx),
                [{"name": "slide1.xml", "hidden": False}, {"name": "slide2.xml", "hidden": True}],
            )

            # Single member XML exceeding MAX_THUMBNAIL_XML_BYTES is rejected (both honest and spoofed header)
            bomb_pptx = self.root / "bomb.pptx"
            with zipfile.ZipFile(bomb_pptx, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("ppt/_rels/presentation.xml.rels", rels_xml + (" " * 4096))
                zf.writestr("ppt/presentation.xml", pres_xml)
                zf.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')

            with unittest.mock.patch.object(thumbnail, "MAX_THUMBNAIL_XML_BYTES", 1024):
                with self.assertRaises(ValueError):
                    thumbnail.get_slide_info(bomb_pptx)

            with (
                unittest.mock.patch.object(thumbnail, "MAX_THUMBNAIL_XML_BYTES", 1024),
                unittest.mock.patch.object(thumbnail, "validate_archive", lambda *a, **kw: None),
            ):
                small_info = zipfile.ZipInfo("ppt/_rels/presentation.xml.rels")
                small_info.file_size = 10
                orig_getinfo = zipfile.ZipFile.getinfo
                orig_open = zipfile.ZipFile.open

                def spoofed_getinfo(self_zf, name):
                    if name == "ppt/_rels/presentation.xml.rels":
                        return small_info
                    return orig_getinfo(self_zf, name)

                def spoofed_open(self_zf, name_or_info, mode="r", *args, **kwargs):
                    target_name = name_or_info.filename if isinstance(name_or_info, zipfile.ZipInfo) else name_or_info
                    if target_name == "ppt/_rels/presentation.xml.rels":
                        return io.BytesIO((rels_xml + (" " * 4096)).encode("utf-8"))
                    return orig_open(self_zf, name_or_info, mode, *args, **kwargs)

                with (
                    unittest.mock.patch.object(zipfile.ZipFile, "getinfo", spoofed_getinfo),
                    unittest.mock.patch.object(zipfile.ZipFile, "open", spoofed_open),
                ):
                    with self.assertRaises(ValueError):
                        thumbnail.get_slide_info(valid_pptx)

            # Aggregate budget catches combined rels + presentation exceeding MAX_ARCHIVE_BYTES
            agg_pptx = self.root / "agg.pptx"
            with zipfile.ZipFile(agg_pptx, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("ppt/_rels/presentation.xml.rels", rels_xml + (" " * 1400))
                zf.writestr("ppt/presentation.xml", pres_xml + (" " * 1400))
                zf.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')

            with (
                unittest.mock.patch.object(thumbnail, "MAX_THUMBNAIL_XML_BYTES", 2048),
                unittest.mock.patch.object(thumbnail, "MAX_ARCHIVE_BYTES", 2500),
            ):
                with self.assertRaises(ValueError):
                    thumbnail.get_slide_info(agg_pptx)

            # Same aggregate limit enforced by streaming budget even if validate_archive and headers are bypassed
            small_rels_info = zipfile.ZipInfo("ppt/_rels/presentation.xml.rels")
            small_rels_info.file_size = 10
            small_pres_info = zipfile.ZipInfo("ppt/presentation.xml")
            small_pres_info.file_size = 10
            orig_getinfo = zipfile.ZipFile.getinfo
            orig_open = zipfile.ZipFile.open

            def spoof_agg_getinfo(self_zf, name):
                if name == "ppt/_rels/presentation.xml.rels":
                    return small_rels_info
                if name == "ppt/presentation.xml":
                    return small_pres_info
                return orig_getinfo(self_zf, name)

            def spoof_agg_open(self_zf, name_or_info, mode="r", *args, **kwargs):
                target_name = name_or_info.filename if isinstance(name_or_info, zipfile.ZipInfo) else name_or_info
                if target_name == "ppt/_rels/presentation.xml.rels":
                    return io.BytesIO((rels_xml + (" " * 1400)).encode("utf-8"))
                if target_name == "ppt/presentation.xml":
                    return io.BytesIO((pres_xml + (" " * 1400)).encode("utf-8"))
                return orig_open(self_zf, name_or_info, mode, *args, **kwargs)

            with (
                unittest.mock.patch.object(thumbnail, "MAX_THUMBNAIL_XML_BYTES", 2048),
                unittest.mock.patch.object(thumbnail, "MAX_ARCHIVE_BYTES", 2500),
                unittest.mock.patch.object(thumbnail, "validate_archive", lambda *a, **kw: None),
                unittest.mock.patch.object(zipfile.ZipFile, "getinfo", spoof_agg_getinfo),
                unittest.mock.patch.object(zipfile.ZipFile, "open", spoof_agg_open),
            ):
                with self.assertRaises(ValueError):
                    thumbnail.get_slide_info(valid_pptx)

    def test_pdf_image_scripts_create_dirs_and_batch_bounded(self):
        pdf_scripts = CRAFT_DIR / "skills" / "pdf" / "scripts"
        calls: list[tuple[int, int, int | None]] = []
        created_images: list[object] = []

        class FakePdfImage:
            def __init__(self, size=(800, 1000)):
                self.size = size
                self.closed = False

            def resize(self, new_size):
                return FakePdfImage(new_size)

            def save(self, path, format=None):
                pathlib.Path(path).write_bytes(b"PNG")

            def close(self):
                self.closed = True

        fake_pdf2image = types.ModuleType("pdf2image")
        fake_pdf2image.pdfinfo_from_path = lambda path: {"Pages": 25}

        def fake_convert_from_path(pdf_path, dpi=200, first_page=None, last_page=None, size=None):
            calls.append((first_page, last_page, size))
            batch = [FakePdfImage() for _ in range(first_page, last_page + 1)]
            created_images.extend(batch)
            return batch

        fake_pdf2image.convert_from_path = fake_convert_from_path

        in_pdf = self.root / "input.pdf"
        in_pdf.write_bytes(b"%PDF-1.4")
        missing_dir = self.root / "nested" / "images"

        with unittest.mock.patch.dict(sys.modules, {"pdf2image": fake_pdf2image}):
            conv_mod = _load_module("test_convert_pdf_to_images", pdf_scripts / "convert_pdf_to_images.py")
            conv_mod.convert(str(in_pdf), str(missing_dir), max_dim=1000)

        self.assertTrue(missing_dir.is_dir())
        self.assertEqual(calls, [(1, 10, 1000), (11, 20, 1000), (21, 25, 1000)])
        self.assertEqual(len(created_images), 25)
        self.assertTrue(all(img.closed for img in created_images))
        for page_num in range(1, 26):
            self.assertTrue((missing_dir / f"page_{page_num}.png").is_file())
        self.assertEqual(list(missing_dir.glob("*.tmp")), [])

        fields_json = self.root / "fields.json"
        fields_json.write_text(
            json.dumps({
                "form_fields": [{
                    "page_number": 1,
                    "entry_bounding_box": [10, 10, 40, 30],
                    "label_bounding_box": [10, 35, 40, 55],
                }]
            }),
            encoding="utf-8",
        )
        out_png = self.root / "nested_val" / "out.png"

        if importlib.util.find_spec("PIL") is not None:
            from PIL import Image as RealImage

            in_png = self.root / "page_1.png"
            RealImage.new("RGB", (100, 100), "white").save(in_png)
            val_mod = _load_module("test_create_validation_image", pdf_scripts / "create_validation_image.py")
            val_mod.create_validation_image(1, str(fields_json), str(in_png), str(out_png))
        else:
            in_png = self.root / "page_1.png"
            in_png.write_bytes(b"PNG")

            class FakeValImg:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def copy(self):
                    return FakeValImg()

                def save(self, path):
                    pathlib.Path(path).write_bytes(b"PNG-VAL")

                def close(self):
                    pass

            class FakeDraw:
                def rectangle(self, *args, **kwargs):
                    pass

            fake_pil = types.ModuleType("PIL")
            fake_pil.Image = types.SimpleNamespace(open=lambda p: FakeValImg())
            fake_pil.ImageDraw = types.SimpleNamespace(Draw=lambda img: FakeDraw())
            with unittest.mock.patch.dict(
                sys.modules,
                {"PIL": fake_pil, "PIL.Image": fake_pil.Image, "PIL.ImageDraw": fake_pil.ImageDraw},
            ):
                val_mod = _load_module("test_create_validation_image", pdf_scripts / "create_validation_image.py")
                val_mod.create_validation_image(1, str(fields_json), str(in_png), str(out_png))

        self.assertTrue(out_png.is_file())
        self.assertEqual([p.name for p in out_png.parent.iterdir()], ["out.png"])

    def test_pdf_choice_field_options_handle_strings_and_pairs(self):
        pdf_scripts = CRAFT_DIR / "skills" / "pdf" / "scripts"

        class FakeDictionaryObject(dict):
            def get_inherited(self, key, default=None):
                return self.get(key, default)

        fake_pypdf = types.ModuleType("pypdf")
        fake_pypdf.PdfReader = lambda p: object()
        fake_pypdf.PdfWriter = lambda *a, **kw: object()
        fake_pypdf_generic = types.ModuleType("pypdf.generic")
        fake_pypdf_generic.DictionaryObject = FakeDictionaryObject
        fake_pypdf_constants = types.ModuleType("pypdf.constants")
        fake_pypdf_constants.FieldDictionaryAttributes = types.SimpleNamespace(Opt="/Opt")

        with unittest.mock.patch.dict(
            sys.modules,
            {
                "pypdf": fake_pypdf,
                "pypdf.generic": fake_pypdf_generic,
                "pypdf.constants": fake_pypdf_constants,
            },
        ):
            extract_mod = _load_module("test_extract_form_field_info", pdf_scripts / "extract_form_field_info.py")
            with unittest.mock.patch.dict(sys.modules, {"extract_form_field_info": extract_mod}):
                fill_mod = _load_module("test_fill_fillable_choice", pdf_scripts / "fill_fillable_fields.py")
                fill_mod.monkeypatch_pydpf_method()
                fill_mod.monkeypatch_pydpf_method()

        str_choice = extract_mod.make_field_dict({"/FT": "/Ch", "/_States_": ["Yes", "No", "X"]}, "status")
        self.assertEqual(str_choice["type"], "choice")
        self.assertEqual(
            str_choice["choice_options"],
            [
                {"value": "Yes", "text": "Yes"},
                {"value": "No", "text": "No"},
                {"value": "X", "text": "X"},
            ],
        )

        mixed_choice = extract_mod.make_field_dict(
            {"/FT": "/Ch", "/_States_": [["CA", "California"], ["NY", "New York"], "Other"]},
            "state",
        )
        self.assertEqual(
            mixed_choice["choice_options"],
            [
                {"value": "CA", "text": "California"},
                {"value": "NY", "text": "New York"},
                {"value": "Other", "text": "Other"},
            ],
        )

        str_choice["page"] = 1
        mixed_choice["page"] = 1
        self.assertIsNone(fill_mod.validation_error_for_field_value(str_choice, "Yes"))
        self.assertIsNone(fill_mod.validation_error_for_field_value(str_choice, "X"))
        self.assertIsNone(fill_mod.validation_error_for_field_value(mixed_choice, "CA"))
        self.assertIsNone(fill_mod.validation_error_for_field_value(mixed_choice, "Other"))
        self.assertIn("ERROR:", fill_mod.validation_error_for_field_value(str_choice, "Invalid"))

        d = FakeDictionaryObject({"/Opt": [["CA", "California"], "Other"]})
        self.assertEqual(d.get_inherited("/Opt"), ["CA", "Other"])

    def test_recalc_opc_targets_xlfn_lambda_and_linear_propagation(self):
        import time

        xlsx_scripts = CRAFT_DIR / "skills" / "xlsx" / "scripts"
        recalc = _load_module("test_xlsx_recalc_opc_lambda", xlsx_scripts / "recalc.py", [xlsx_scripts])

        # 1. Saved OOXML _xlfn.LAMBDA / _xlfn._xlws.LAMBDA / alias invocation detection
        wb_lambda = self.root / "book_xlfn_lambda.xlsx"
        with zipfile.ZipFile(wb_lambda, "w") as zf:
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                '<definedNames>'
                '<definedName name="LinkedFn">_xlfn.LAMBDA(_xlpm.x,[1]Sheet1!A1+_xlpm.x)</definedName>'
                '<definedName name="WsLambda">_xlfn._xlws.LAMBDA(_xlpm.y,[1]Sheet1!A2+_xlpm.y)</definedName>'
                '<definedName name="AliasFn">LinkedFn</definedName>'
                '<definedName name="SUM">[1]Sheet1!A3</definedName>'
                '</definedNames></workbook>',
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1">'
                '<c r="A1"><f>LinkedFn(1)</f></c>'
                '<c r="A2"><f>WsLambda(1)</f></c>'
                '<c r="A3"><f>AliasFn(1)</f></c>'
                '<c r="A4"><f>LinkedFn(1)</f><v>5</v></c>'
                '<c r="A5"><f>SUM(1,2)</f></c>'
                '</row></sheetData></worksheet>',
            )
        self.assertEqual(
            recalc.external_links_at_risk(str(wb_lambda)),
            ["Sheet1!A1", "Sheet1!A2", "Sheet1!A3"],
        )

        # 2. OPC dot-segment / percent-encoded targets and sharedStrings resolution
        wb_opc = self.root / "book_opc_targets.xlsx"
        with zipfile.ZipFile(wb_opc, "w") as zf:
            zf.writestr(
                "_rels/.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id=" rId1 " Type=" http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument " '
                'Target=" /xl/./workbook.xml "/></Relationships>',
            )
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets>'
                '<sheet name="Sheet1" sheetId="1" r:id=" rId1 "/>'
                '<sheet name="Sheet2" sheetId="2" r:id="rId2"/>'
                '</sheets></workbook>',
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id=" rId1 " Type=" http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet " '
                'Target=" /xl/worksheets/./sheet1.xml "/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="../xl/worksheets/sheet%202.xml"/>'
                '<Relationship Id=" rId3 " Type=" http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings " '
                'Target=" /xl/./sharedStrings.xml "/>'
                '</Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            zf.writestr(
                "xl/sharedStrings.xml",
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>=1+1</t></si></sst>',
            )
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1"><c r="A1"><f>[1]Ext!A1</f></c></row>'
                '</sheetData></worksheet>',
            )
            zf.writestr(
                "xl/worksheets/sheet 2.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1">'
                '<c r="A1"><f>[1]Ext!B1</f></c>'
                '<c r="B1" t="s"><v>0</v></c>'
                '<c r="C1" t="e"><f>1/0</f><v>#DIV/0!</v></c>'
                '</row></sheetData></worksheet>',
            )
        self.assertEqual(recalc.external_links_at_risk(str(wb_opc)), ["Sheet1!A1", "Sheet2!A1"])
        errors_opc, formulas_opc = recalc._scan_xml(str(wb_opc))
        self.assertEqual(formulas_opc, 4)
        self.assertEqual(errors_opc["#DIV/0!"], ["Sheet2!C1"])

        # Escaping OPC relationship target raises ValueError and fails recalc/_report cleanly
        wb_escape = self.root / "book_opc_escape.xlsx"
        with zipfile.ZipFile(wb_escape, "w") as zf:
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
                'Target="../../outside.xml"/></Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
        with self.assertRaisesRegex(ValueError, "escapes the package"):
            recalc.external_links_at_risk(str(wb_escape))
        with self.assertRaisesRegex(ValueError, "escapes the package"):
            recalc._scan_xml(str(wb_escape))
        self.assertIn("escapes the package", recalc._report(str(wb_escape)).get("error", ""))
        with (
            unittest.mock.patch.object(recalc, "get_soffice_env", return_value={}),
            unittest.mock.patch.object(recalc, "run_soffice", side_effect=AssertionError("soffice must not run")),
        ):
            self.assertIn("escapes the package", recalc.recalc(str(wb_escape)).get("error", ""))
            self.assertIn("escapes the package", recalc.recalc(str(wb_escape), force=True).get("error", ""))

        # 3. Linear-time O(V+E) defined-name chain propagation across 4,001 names
        wb_chain = self.root / "book_name_chain.xlsx"
        dn_xml = "".join(
            f'<definedName name="Name_{idx}">Name_{idx + 1}</definedName>'
            for idx in range(4000)
        ) + '<definedName name="Name_4000">[1]Sheet1!A1</definedName>'
        with zipfile.ZipFile(wb_chain, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                f'<definedNames>{dn_xml}</definedNames></workbook>',
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1"><c r="A1"><f>Name_0</f></c></row>'
                '</sheetData></worksheet>',
            )
        t0 = time.perf_counter()
        chain_risk = recalc.external_links_at_risk(str(wb_chain))
        elapsed = time.perf_counter() - t0
        self.assertEqual(chain_risk, ["Sheet1!A1"])
        self.assertLess(elapsed, 1.0, f"4001-name chain took {elapsed:.3f}s")

    def test_recalc_coordinate_bounds_and_let_lambda_local_scopes(self):
        import time

        xlsx_scripts = CRAFT_DIR / "skills" / "xlsx" / "scripts"
        recalc = _load_module("test_xlsx_recalc_bounds_let", xlsx_scripts / "recalc.py", [xlsx_scripts])

        # 1. Excel grid limits and O(1) rejection of oversized coordinate strings
        self.assertEqual(recalc._row_major("$XFD$1048576"), (1048576, 16384))
        for bad_coord in ("XFE1", "ZZZ1", "A1048577", "A0", "A$B1"):
            with self.assertRaises(ValueError):
                recalc._row_major(bad_coord)

        wb_long_col = self.root / "book_long_col.xlsx"
        long_ref = ("A" * 160_000) + "1"
        with zipfile.ZipFile(wb_long_col, "w", compression=zipfile.ZIP_DEFLATED) as zf:
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
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData/><mergeCells count="1"><mergeCell ref="{long_ref}"/></mergeCells>'
                '</worksheet>',
            )
        t0 = time.perf_counter()
        with self.assertRaises(ValueError):
            recalc.external_links_at_risk(str(wb_long_col))
        with self.assertRaises(ValueError):
            recalc._scan_xml(str(wb_long_col))
        self.assertIn("error", recalc._report(str(wb_long_col)))
        with (
            unittest.mock.patch.object(recalc, "get_soffice_env", return_value={}),
            unittest.mock.patch.object(recalc, "run_soffice", side_effect=AssertionError("soffice must not run")),
        ):
            self.assertIn("error", recalc.recalc(str(wb_long_col)))
            self.assertIn("error", recalc.recalc(str(wb_long_col), force=True))
        self.assertLess(time.perf_counter() - t0, 0.5)

        # 2. Formula-local LET and LAMBDA bindings shadow workbook defined names cleanly
        wb_let = self.root / "book_let_scopes.xlsx"
        with zipfile.ZipFile(wb_let, "w") as zf:
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                '<definedNames>'
                '<definedName name="Rate">[1]Sheet1!$A$1</definedName>'
                '<definedName name="SafeDef">LET(Rate, 10, Rate * 2)</definedName>'
                '<definedName name="LeakyDef">LET(Rate, Rate + 1, Rate * 2)</definedName>'
                '<definedName name="SafeLambda">_xlfn.LAMBDA(Rate, Rate + 1)</definedName>'
                '<definedName name="UnsafeLambda">_xlfn.LAMBDA(_xlpm.x, Rate + _xlpm.x)</definedName>'
                '</definedNames></workbook>',
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                '<row r="1">'
                '<c r="A1"><f>LET(Rate,1,Rate+1)</f></c>'
                '<c r="A2"><f>_xlfn.LET(_xlpm.Rate,1,_xlpm.Rate+1)</f></c>'
                '<c r="A3"><f>LET(Arr,{1,2},Rate,3,Bonus,Rate+1,Bonus)</f></c>'
                '<c r="A4"><f>SafeDef+1</f></c>'
                '<c r="A5"><f>SafeLambda(5)</f></c>'
                '<c r="B1"><f>LET(Rate,Rate+1,Rate*2)</f></c>'
                '<c r="B2"><f>LET(Unused,1,Rate)</f></c>'
                '<c r="B3"><f>LET(Rate,1,Rate)+Rate</f></c>'
                '<c r="B4"><f>LET(Rate,1,Sheet1!Rate+Rate)</f></c>'
                '<c r="B5"><f>LeakyDef</f></c>'
                '<c r="B6"><f>UnsafeLambda(5)</f></c>'
                '</row></sheetData></worksheet>',
            )
        self.assertEqual(
            recalc.external_links_at_risk(str(wb_let)),
            ["Sheet1!B1", "Sheet1!B2", "Sheet1!B3", "Sheet1!B4", "Sheet1!B5", "Sheet1!B6"],
        )

    def test_recalc_formula_and_token_budgets_prevent_memory_amplification(self):
        import time
        import tracemalloc

        xlsx_scripts = CRAFT_DIR / "skills" / "xlsx" / "scripts"
        recalc = _load_module("test_xlsx_recalc_formula_budget", xlsx_scripts / "recalc.py", [xlsx_scripts])

        self.assertGreater(len(recalc._lex_formula_tokens("=SUM(1,2,3)+Rate")), 0)
        with self.assertRaises(ValueError):
            recalc._lex_formula_tokens("Rate+" * 7000 + "1")
        with self.assertRaises(ValueError):
            recalc._lex_formula_tokens("x+" * 9000 + "x")

        wb_big_f = self.root / "book_big_formula.xlsx"
        big_expr = "Rate+" * 100_000 + "1"
        with zipfile.ZipFile(wb_big_f, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                '<definedNames><definedName name="Rate">[1]Sheet1!$A$1</definedName></definedNames>'
                "</workbook>",
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                f'<row r="1"><c r="A1"><f>{big_expr}</f></c></row>'
                "</sheetData></worksheet>",
            )

        t0 = time.perf_counter()
        tracemalloc.start()
        try:
            with self.assertRaises(ValueError):
                recalc.external_links_at_risk(str(wb_big_f))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 0.5, f"oversized formula check took {elapsed:.3f}s")
        self.assertLess(peak, 2 * 1024 * 1024, f"tracemalloc peak {peak} bytes exceeded 2 MiB")

        with self.assertRaises(ValueError):
            recalc._scan_xml(str(wb_big_f))
        self.assertIn("error", recalc._report(str(wb_big_f)))
        with (
            unittest.mock.patch.object(recalc, "get_soffice_env", return_value={}),
            unittest.mock.patch.object(recalc, "run_soffice", side_effect=AssertionError("soffice must not run")),
        ):
            self.assertIn("error", recalc.recalc(str(wb_big_f)))
            self.assertIn("error", recalc.recalc(str(wb_big_f), force=True))

        wb_big_dn = self.root / "book_big_dn.xlsx"
        big_dn = "1+" * 20_000 + "1"
        with zipfile.ZipFile(wb_big_dn, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                f'<definedNames><definedName name="Huge">{big_dn}</definedName></definedNames>'
                "</workbook>",
            )
            zf.writestr(
                "xl/_rels/workbook.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>',
            )
            zf.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
            zf.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>',
            )
        with self.assertRaises(ValueError):
            recalc.external_links_at_risk(str(wb_big_dn))

    def test_pptx_and_docx_scripts_handle_namespace_prefixed_opc_xml(self):
        ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        ct_root = ET.Element(f"{{{ct_ns}}}Types")
        ET.SubElement(ct_root, f"{{{ct_ns}}}Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
        ET.SubElement(ct_root, f"{{{ct_ns}}}Default", Extension="xml", ContentType="application/xml")
        ET.SubElement(
            ct_root,
            f"{{{ct_ns}}}Override",
            PartName="/ppt/presentation.xml",
            ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        )
        ET.SubElement(
            ct_root,
            f"{{{ct_ns}}}Override",
            PartName="/ppt/slides/slide1.xml",
            ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        )
        ET.SubElement(
            ct_root,
            f"{{{ct_ns}}}Override",
            PartName=" /ppt/tags/tag1.xml ",
            ContentType="application/vnd.openxmlformats-officedocument.presentationml.tags+xml",
        )

        pkg_rels = ET.Element(f"{{{rels_ns}}}Relationships")
        ET.SubElement(pkg_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/officeDocument", Target="ppt/presentation.xml")

        pres_rels = ET.Element(f"{{{rels_ns}}}Relationships")
        ET.SubElement(pres_rels, f"{{{rels_ns}}}Relationship", Id=" rId1 ", Type=f" {r_ns}/slide ", Target=" slides/slide1.xml ")
        ET.SubElement(pres_rels, f"{{{rels_ns}}}Relationship", Id="rId2", Type=f"{r_ns}/slideLayout", Target="slideLayouts/slideLayout1.xml")

        slide1_rels = ET.Element(f"{{{rels_ns}}}Relationships")
        ET.SubElement(slide1_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/slideLayout", Target="../slideLayouts/slideLayout1.xml")
        ET.SubElement(slide1_rels, f"{{{rels_ns}}}Relationship", Id=" rId2 ", Type=f" {r_ns}/notesSlide ", Target=" ../notesSlides/notesSlide1.xml ")
        ET.SubElement(slide1_rels, f"{{{rels_ns}}}Relationship", Id=" rId3 ", Type=f" {r_ns}/tags ", Target=" ../tags/tag1.xml ")

        pres_root = ET.Element(f"{{{p_ns}}}presentation")
        ET.SubElement(pres_root, f"{{{p_ns}}}sldMasterIdLst")
        sld_lst = ET.SubElement(pres_root, f"{{{p_ns}}}sldIdLst")
        ET.SubElement(sld_lst, f"{{{p_ns}}}sldId", id="256", **{f"{{{r_ns}}}id": " rId1 "})

        slide1_root = ET.Element(f"{{{p_ns}}}sld")
        layout1_root = ET.Element(f"{{{p_ns}}}sldLayout")
        notes1_root = ET.Element(f"{{{p_ns}}}notes")
        tag1_root = ET.Element(f"{{{p_ns}}}tagLst")

        deck = self.root / "prefixed.pptx"
        with zipfile.ZipFile(deck, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", ET.tostring(ct_root, encoding="utf-8", xml_declaration=True))
            zf.writestr("_rels/.rels", ET.tostring(pkg_rels, encoding="utf-8", xml_declaration=True))
            zf.writestr("ppt/_rels/presentation.xml.rels", ET.tostring(pres_rels, encoding="utf-8", xml_declaration=True))
            zf.writestr("ppt/slides/_rels/slide1.xml.rels", ET.tostring(slide1_rels, encoding="utf-8", xml_declaration=True))
            zf.writestr("ppt/presentation.xml", ET.tostring(pres_root, encoding="utf-8", xml_declaration=True))
            zf.writestr("ppt/slides/slide1.xml", ET.tostring(slide1_root, encoding="utf-8", xml_declaration=True))
            zf.writestr("ppt/slideLayouts/slideLayout1.xml", ET.tostring(layout1_root, encoding="utf-8", xml_declaration=True))
            zf.writestr("ppt/notesSlides/notesSlide1.xml", ET.tostring(notes1_root, encoding="utf-8", xml_declaration=True))
            zf.writestr("ppt/tags/tag1.xml", ET.tostring(tag1_root, encoding="utf-8", xml_declaration=True))

        pptx_scripts = CRAFT_DIR / "skills" / "pptx" / "scripts"
        docx_scripts = CRAFT_DIR / "skills" / "docx" / "scripts"

        extra_mods: dict[str, types.ModuleType] = {}
        if importlib.util.find_spec("PIL") is None:
            fake_pil = types.ModuleType("PIL")
            fake_pil.Image = types.SimpleNamespace()
            fake_pil.ImageDraw = types.SimpleNamespace()
            fake_pil.ImageFont = types.SimpleNamespace()
            extra_mods["PIL"] = fake_pil

        with unittest.mock.patch.dict(sys.modules, extra_mods):
            for mod_name in list(sys.modules):
                if mod_name == "office" or mod_name.startswith("office."):
                    sys.modules.pop(mod_name, None)
            add_slide = _load_module("test_pptx_add_slide_ns", pptx_scripts / "add_slide.py", [pptx_scripts])
            thumbnail = _load_module("test_pptx_thumbnail_ns", pptx_scripts / "thumbnail.py", [pptx_scripts])
            clean = _load_module("test_pptx_clean_ns", pptx_scripts / "clean.py", [pptx_scripts])

            self.assertEqual(add_slide.add_slide_to_package(deck, "slide1.xml"), "slide2.xml")
            self.assertEqual(add_slide.add_slide_to_package(deck, "slideLayout1.xml", after="slide1.xml"), "slide3.xml")

            with zipfile.ZipFile(deck, "r") as zf:
                out_ct = ET.fromstring(zf.read("[Content_Types].xml"))
                out_pres_rels = ET.fromstring(zf.read("ppt/_rels/presentation.xml.rels"))
                out_pres = ET.fromstring(zf.read("ppt/presentation.xml"))
                out_slide2_rels = ET.fromstring(zf.read("ppt/slides/_rels/slide2.xml.rels"))
                self.assertIn("ppt/tags/tag2.xml", zf.namelist())

            rel_targets = {
                el.get("Id").strip(): el.get("Target").strip()
                for el in out_pres_rels.findall(f"{{{rels_ns}}}Relationship")
            }
            ordered_targets = [
                rel_targets[el.get(f"{{{r_ns}}}id").strip()]
                for el in out_pres.findall(f".//{{{p_ns}}}sldId")
            ]
            self.assertEqual(ordered_targets, ["slides/slide1.xml", "slides/slide3.xml", "slides/slide2.xml"])
            self.assertEqual(len(rel_targets), 4)

            overrides = {
                el.get("PartName").strip()
                for el in out_ct.findall(f"{{{ct_ns}}}Override")
            }
            self.assertTrue({"/ppt/slides/slide2.xml", "/ppt/slides/slide3.xml", "/ppt/tags/tag2.xml"}.issubset(overrides))

            slide2_rel_types = {el.get("Type").strip(): el.get("Target").strip() for el in out_slide2_rels.findall(f"{{{rels_ns}}}Relationship")}
            self.assertNotIn(f"{r_ns}/notesSlide", slide2_rel_types)
            self.assertEqual(slide2_rel_types.get(f"{r_ns}/tags"), "../tags/tag2.xml")

            self.assertEqual(
                [s["name"] for s in thumbnail.get_slide_info(deck)],
                ["slide1.xml", "slide3.xml", "slide2.xml"],
            )

            unpacked_pptx = self.root / "unpacked_pptx"
            with zipfile.ZipFile(deck, "r") as zf:
                zf.extractall(unpacked_pptx)
            orphan = unpacked_pptx / "ppt" / "slides" / "slide99.xml"
            orphan.write_bytes(ET.tostring(slide1_root, encoding="utf-8", xml_declaration=True))
            removed = clean.clean_unused_files(unpacked_pptx)
            self.assertFalse(orphan.exists())
            self.assertTrue(any("slide99.xml" in item for item in removed))
            for keep in ("slide1.xml", "slide2.xml", "slide3.xml"):
                self.assertTrue((unpacked_pptx / "ppt" / "slides" / keep).exists())

        with unittest.mock.patch.dict(sys.modules):
            for mod_name in list(sys.modules):
                if mod_name == "office" or mod_name.startswith("office."):
                    sys.modules.pop(mod_name, None)
            comment = _load_module("test_docx_comment_ns", docx_scripts / "comment.py", [docx_scripts])

            unpacked_docx = self.root / "unpacked_docx"
            (unpacked_docx / "word" / "_rels").mkdir(parents=True)
            doc_ct = ET.Element(f"{{{ct_ns}}}Types")
            ET.SubElement(doc_ct, f"{{{ct_ns}}}Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
            ET.SubElement(doc_ct, f"{{{ct_ns}}}Override", PartName=" /word/document.xml ", ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
            ET.SubElement(doc_ct, f"{{{ct_ns}}}Override", PartName=" /word/commentsExtended.xml ", ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml")
            (unpacked_docx / "[Content_Types].xml").write_bytes(ET.tostring(doc_ct, encoding="utf-8", xml_declaration=True))

            doc_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(doc_rels, f"{{{rels_ns}}}Relationship", Id=" rId1 ", Type=f" {r_ns}/styles ", Target=" ./styles.xml ")
            ET.SubElement(doc_rels, f"{{{rels_ns}}}Relationship", Id=" rId2 ", Type=" http://schemas.microsoft.com/office/2011/relationships/commentsExtended ", Target=" ./commentsExtended.xml ")
            (unpacked_docx / "word" / "_rels" / "document.xml.rels").write_bytes(ET.tostring(doc_rels, encoding="utf-8", xml_declaration=True))

            self.assertEqual(comment._get_next_rid(unpacked_docx / "word" / "_rels" / "document.xml.rels"), 3)
            self.assertTrue(comment._has_relationship(unpacked_docx / "word" / "_rels" / "document.xml.rels", "styles.xml"))
            self.assertTrue(comment._has_content_type(unpacked_docx / "[Content_Types].xml", "/word/document.xml"))

            comment._ensure_comment_relationships(unpacked_docx)
            comment._ensure_comment_content_types(unpacked_docx)

            out_doc_rels = ET.fromstring((unpacked_docx / "word" / "_rels" / "document.xml.rels").read_bytes())
            out_doc_ct = ET.fromstring((unpacked_docx / "[Content_Types].xml").read_bytes())
            doc_targets = [el.get("Target").strip() for el in out_doc_rels.findall(f"{{{rels_ns}}}Relationship")]
            self.assertEqual(len(doc_targets), 5)
            self.assertTrue({"comments.xml", "./commentsExtended.xml", "commentsIds.xml", "commentsExtensible.xml"}.issubset(set(doc_targets)))
            doc_overrides = [el.get("PartName").strip() for el in out_doc_ct.findall(f"{{{ct_ns}}}Override")]
            self.assertEqual(len(doc_overrides), 5)
            self.assertTrue({"/word/comments.xml", "/word/commentsExtended.xml", "/word/commentsIds.xml", "/word/commentsExtensible.xml"}.issubset(set(doc_overrides)))
            self.assertTrue(comment._has_relationship(unpacked_docx / "word" / "_rels" / "document.xml.rels", "comments.xml"))
            self.assertTrue(comment._has_content_type(unpacked_docx / "[Content_Types].xml", "/word/comments.xml"))

    def test_pptx_clean_refuses_missing_presentation_and_prunes_content_types_posix(self):
        pptx_scripts = CRAFT_DIR / "skills" / "pptx" / "scripts"
        ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        with unittest.mock.patch.dict(sys.modules):
            for mod_name in list(sys.modules):
                if mod_name == "office" or mod_name.startswith(("office.", "helpers.", "validators.")) or mod_name in ("helpers", "validators"):
                    sys.modules.pop(mod_name, None)
            clean = _load_module("test_pptx_clean_refusal", pptx_scripts / "clean.py", [pptx_scripts])

            # Case A: missing ppt/presentation.xml must refuse rather than deleting slide1.xml
            case_a = self.root / "clean_missing_pres"
            (case_a / "_rels").mkdir(parents=True)
            (case_a / "ppt" / "slides").mkdir(parents=True)
            pkg_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(pkg_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/officeDocument", Target="ppt/presentation.xml")
            (case_a / "_rels" / ".rels").write_bytes(ET.tostring(pkg_rels, encoding="utf-8", xml_declaration=True))
            slide_bytes = ET.tostring(ET.Element(f"{{{p_ns}}}sld"), encoding="utf-8", xml_declaration=True)
            slide_a = case_a / "ppt" / "slides" / "slide1.xml"
            slide_a.write_bytes(slide_bytes)
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(case_a)
            with self.assertRaises(clean.RefusedToClean):
                clean.remove_orphaned_slides(case_a)
            self.assertTrue(slide_a.exists())

            # Case B: ppt/presentation.xml exists but ppt/_rels/presentation.xml.rels is missing
            case_b = self.root / "clean_missing_pres_rels"
            (case_b / "_rels").mkdir(parents=True)
            (case_b / "ppt" / "slides").mkdir(parents=True)
            (case_b / "ppt" / "theme").mkdir(parents=True)
            (case_b / "_rels" / ".rels").write_bytes(ET.tostring(pkg_rels, encoding="utf-8", xml_declaration=True))
            pres_b = ET.Element(f"{{{p_ns}}}presentation")
            ET.SubElement(pres_b, f"{{{p_ns}}}sldMasterIdLst")
            (case_b / "ppt" / "presentation.xml").write_bytes(ET.tostring(pres_b, encoding="utf-8", xml_declaration=True))
            slide_b = case_b / "ppt" / "slides" / "slide1.xml"
            theme_b = case_b / "ppt" / "theme" / "theme1.xml"
            slide_b.write_bytes(slide_bytes)
            theme_b.write_bytes(b"<theme/>")
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(case_b)
            with self.assertRaises(clean.RefusedToClean):
                clean.remove_orphaned_slides(case_b)
            self.assertTrue(slide_b.exists())
            self.assertTrue(theme_b.exists())

            # Case C: orphaned slide, media, nested [trash], and [Content_Types].xml pruning use POSIX paths
            case_c = self.root / "clean_posix_ct"
            (case_c / "_rels").mkdir(parents=True)
            (case_c / "ppt" / "_rels").mkdir(parents=True)
            (case_c / "ppt" / "slides").mkdir(parents=True)
            (case_c / "ppt" / "media").mkdir(parents=True)
            (case_c / "[trash]" / "sub").mkdir(parents=True)
            (case_c / "_rels" / ".rels").write_bytes(ET.tostring(pkg_rels, encoding="utf-8", xml_declaration=True))

            pres_c = ET.Element(f"{{{p_ns}}}presentation")
            ET.SubElement(pres_c, f"{{{p_ns}}}sldMasterIdLst")
            sld_lst = ET.SubElement(pres_c, f"{{{p_ns}}}sldIdLst")
            ET.SubElement(sld_lst, f"{{{p_ns}}}sldId", id="256", **{f"{{{r_ns}}}id": "rId1"})
            (case_c / "ppt" / "presentation.xml").write_bytes(ET.tostring(pres_c, encoding="utf-8", xml_declaration=True))

            pres_rels_c = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(pres_rels_c, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/slide", Target="slides/slide1.xml")
            (case_c / "ppt" / "_rels" / "presentation.xml.rels").write_bytes(ET.tostring(pres_rels_c, encoding="utf-8", xml_declaration=True))

            ct_c = ET.Element(f"{{{ct_ns}}}Types")
            ET.SubElement(ct_c, f"{{{ct_ns}}}Override", PartName="/ppt/presentation.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml")
            ET.SubElement(ct_c, f"{{{ct_ns}}}Override", PartName="/ppt/slides/slide1.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
            ET.SubElement(ct_c, f"{{{ct_ns}}}Override", PartName="/ppt/slides/slide2.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
            (case_c / "[Content_Types].xml").write_bytes(ET.tostring(ct_c, encoding="utf-8", xml_declaration=True))

            (case_c / "ppt" / "slides" / "slide1.xml").write_bytes(slide_bytes)
            (case_c / "ppt" / "slides" / "slide2.xml").write_bytes(slide_bytes)
            (case_c / "ppt" / "media" / "orphan.png").write_bytes(b"png")
            (case_c / "[trash]" / "sub" / "old.xml").write_bytes(b"<old/>")

            removed = clean.clean_unused_files(case_c)
            self.assertTrue(all("\\" not in item for item in removed), f"non-POSIX path in {removed!r}")
            self.assertTrue({"ppt/slides/slide2.xml", "ppt/media/orphan.png", "[trash]/sub/old.xml"}.issubset(set(removed)))
            self.assertTrue((case_c / "ppt" / "slides" / "slide1.xml").exists())
            self.assertFalse((case_c / "ppt" / "slides" / "slide2.xml").exists())
            self.assertFalse((case_c / "ppt" / "media" / "orphan.png").exists())
            self.assertFalse((case_c / "[trash]").exists())

            out_ct = ET.fromstring((case_c / "[Content_Types].xml").read_bytes())
            remaining_parts = {el.get("PartName") for el in out_ct.findall(f"{{{ct_ns}}}Override")}
            self.assertIn("/ppt/slides/slide1.xml", remaining_parts)
            self.assertNotIn("/ppt/slides/slide2.xml", remaining_parts)

    def test_office_validators_and_merge_runs_work_without_defusedxml(self):
        docx_scripts = CRAFT_DIR / "skills" / "docx" / "scripts"
        w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        c_ns = "http://schemas.openxmlformats.org/drawingml/2006/chart"
        a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        with unittest.mock.patch.dict(
            sys.modules,
            {
                "defusedxml": None,
                "defusedxml.minidom": None,
                "defusedxml.ElementTree": None,
                "defusedxml.common": None,
            },
        ):
            for mod_name in list(sys.modules):
                if mod_name == "office" or mod_name.startswith(("office.", "helpers.", "validators.")) or mod_name in ("helpers", "validators"):
                    sys.modules.pop(mod_name, None)

            merge_runs = _load_module("test_docx_merge_runs_no_defusedxml", docx_scripts / "merge_runs.py", [docx_scripts])
            unpacked_doc = self.root / "docx_no_defused"
            (unpacked_doc / "word").mkdir(parents=True)
            doc_xml = (
                f'<w:document xmlns:w="{w_ns}"><w:body><w:p>'
                "<w:r><w:t xml:space=\"preserve\">Hello </w:t></w:r>"
                "<w:r><w:t>world</w:t></w:r>"
                "</w:p></w:body></w:document>"
            ).encode("utf-8")
            (unpacked_doc / "word" / "document.xml").write_bytes(doc_xml)
            count, msg = merge_runs.merge_runs(str(unpacked_doc))
            self.assertEqual(count, 1, msg)
            merged_root = ET.fromstring((unpacked_doc / "word" / "document.xml").read_bytes())
            texts = [el.text for el in merged_root.findall(f".//{{{w_ns}}}t")]
            self.assertEqual(texts, ["Hello world"])

            pptx_chart = _load_module(
                "office.helpers.pptx_chart_no_defusedxml",
                docx_scripts / "office" / "helpers" / "pptx_chart.py",
                [docx_scripts],
            )
            chart_xml = (
                f'<c:chartSpace xmlns:c="{c_ns}" xmlns:a="{a_ns}">'
                "<c:chart><c:plotArea><c:barChart>"
                '<c:ser><c:idx val="0"/><c:order val="0"/></c:ser>'
                '<c:ser><c:idx val="1"/><c:order val="0"/></c:ser>'
                '<c:axId val="1"/><c:axId val="2"/>'
                "</c:barChart>"
                '<c:catAx><c:axId val="1"/></c:catAx>'
                '<c:valAx><c:axId val="2"/></c:valAx>'
                "</c:plotArea></c:chart></c:chartSpace>"
            ).encode("utf-8")
            problems = pptx_chart.find_chart_problems({"ppt/charts/chart1.xml": chart_xml})
            self.assertEqual(len(problems), 1)
            self.assertIn("share the <c:order> value 0", problems[0])

            if importlib.util.find_spec("lxml") is not None:
                added_path = str(docx_scripts)
                sys.path.insert(0, added_path)
                try:
                    import office.validators.base as val_base
                    import office.validators.pptx as val_pptx
                finally:
                    if added_path in sys.path:
                        sys.path.remove(added_path)

                unpacked_pptx = self.root / "pptx_val_sec"
                (unpacked_pptx / "_rels").mkdir(parents=True)
                (unpacked_pptx / "ppt" / "theme").mkdir(parents=True)
                (unpacked_pptx / "ppt" / "charts").mkdir(parents=True)
                (unpacked_pptx / "ppt" / "tags").mkdir(parents=True)

                (self.root / "secret.txt").write_text("outside", encoding="utf-8")
                bad_rels = ET.Element(f"{{{rels_ns}}}Relationships")
                ET.SubElement(bad_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/officeDocument", Target="../../secret.txt")
                (unpacked_pptx / "_rels" / ".rels").write_bytes(ET.tostring(bad_rels, encoding="utf-8", xml_declaration=True))
                theme_path = unpacked_pptx / "ppt" / "theme" / "theme1.xml"
                chart_path = unpacked_pptx / "ppt" / "charts" / "chart1.xml"
                tag_path = unpacked_pptx / "ppt" / "tags" / "tag1.xml"
                theme_path.write_bytes(b"<theme/>")
                chart_path.write_bytes(chart_xml)
                tag_path.write_bytes(b'<!DOCTYPE x [<!ENTITY a "1">]><x/>')

                validator = val_pptx.PPTXSchemaValidator(unpacked_pptx)
                self.assertIsNotNone(validator._get_schema_path(theme_path))
                self.assertIsNotNone(val_base.BaseSchemaValidator._get_schema_path(validator, chart_path))
                self.assertFalse(validator.validate_xml())
                self.assertFalse(validator.validate_file_references())

    def test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion(self):
        from xml.parsers.expat import ExpatError

        pptx_scripts = CRAFT_DIR / "skills" / "pptx" / "scripts"
        clean_py = pptx_scripts / "clean.py"
        ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        p_ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
        r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        def _build_deck(name: str, *, include_rid_attr: bool = True, sld_id_rid: str = "rId1", ct_bytes: bytes | None = None) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
            unpacked = self.root / name
            (unpacked / "_rels").mkdir(parents=True)
            (unpacked / "ppt" / "_rels").mkdir(parents=True)
            (unpacked / "ppt" / "slides").mkdir(parents=True)

            pkg_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(pkg_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/officeDocument", Target="ppt/presentation.xml")
            (unpacked / "_rels" / ".rels").write_bytes(ET.tostring(pkg_rels, encoding="utf-8", xml_declaration=True))

            pres = ET.Element(f"{{{p_ns}}}presentation")
            ET.SubElement(pres, f"{{{p_ns}}}sldMasterIdLst")
            sld_lst = ET.SubElement(pres, f"{{{p_ns}}}sldIdLst")
            attrs = {"id": "256"}
            if include_rid_attr:
                attrs[f"{{{r_ns}}}id"] = sld_id_rid
            ET.SubElement(sld_lst, f"{{{p_ns}}}sldId", attrs)
            (unpacked / "ppt" / "presentation.xml").write_bytes(ET.tostring(pres, encoding="utf-8", xml_declaration=True))

            pres_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(pres_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/slide", Target="slides/slide1.xml")
            (unpacked / "ppt" / "_rels" / "presentation.xml.rels").write_bytes(ET.tostring(pres_rels, encoding="utf-8", xml_declaration=True))

            if ct_bytes is None:
                ct = ET.Element(f"{{{ct_ns}}}Types")
                ET.SubElement(ct, f"{{{ct_ns}}}Override", PartName="/ppt/presentation.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml")
                ET.SubElement(ct, f"{{{ct_ns}}}Override", PartName="/ppt/slides/slide1.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
                ET.SubElement(ct, f"{{{ct_ns}}}Override", PartName="/ppt/slides/slide2.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
                ct_bytes = ET.tostring(ct, encoding="utf-8", xml_declaration=True)
            (unpacked / "[Content_Types].xml").write_bytes(ct_bytes)

            slide_bytes = ET.tostring(ET.Element(f"{{{p_ns}}}sld"), encoding="utf-8", xml_declaration=True)
            s1 = unpacked / "ppt" / "slides" / "slide1.xml"
            s2 = unpacked / "ppt" / "slides" / "slide2.xml"
            s1.write_bytes(slide_bytes)
            s2.write_bytes(slide_bytes)
            return unpacked, s1, s2

        with unittest.mock.patch.dict(sys.modules):
            for mod_name in list(sys.modules):
                if mod_name == "office" or mod_name.startswith(("office.", "helpers.", "validators.")) or mod_name in ("helpers", "validators"):
                    sys.modules.pop(mod_name, None)
            clean = _load_module("test_pptx_clean_precheck", clean_py, [pptx_scripts])
            add_slide_case7 = _load_module("test_pptx_add_slide_case7", pptx_scripts / "add_slide.py", [pptx_scripts])

            # Case 1: <p:sldId id="256"/> missing r:id must refuse rather than deleting slides
            no_rid_dir, s1, s2 = _build_deck("clean_missing_rid", include_rid_attr=False)
            with self.assertRaises(clean.RefusedToClean):
                clean.remove_orphaned_slides(no_rid_dir)
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(no_rid_dir)
            self.assertTrue(s1.exists())
            self.assertTrue(s2.exists())

            # Case 2: <p:sldId> pointing to unknown relationship id must refuse
            dangling_dir, d1, d2 = _build_deck("clean_dangling_rid", sld_id_rid="rId99")
            with self.assertRaises(clean.RefusedToClean):
                clean.remove_orphaned_slides(dangling_dir)
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(dangling_dir)
            self.assertTrue(d1.exists())
            self.assertTrue(d2.exists())

            # Case 3: malformed [Content_Types].xml must fail before deleting orphan slide2.xml
            bad_ct_dir, b1, b2 = _build_deck("clean_bad_ct", ct_bytes=b"<Types><broken")
            with self.assertRaises(ExpatError):
                clean.remove_orphaned_slides(bad_ct_dir)
            with self.assertRaises(ExpatError):
                clean.clean_unused_files(bad_ct_dir)
            self.assertTrue(b1.exists())
            self.assertTrue(b2.exists())

            proc = subprocess.run(
                [sys.executable, str(clean_py), str(bad_ct_dir)],
                capture_output=True,
                text=True,
                creationflags=CREATION_FLAGS,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Nothing was deleted.", proc.stderr)
            self.assertTrue(b2.exists())

            # Case 4: missing or non-<Types> [Content_Types].xml must refuse before deletion
            wrong_root_dir, w1, w2 = _build_deck("clean_wrong_ct_root", ct_bytes=b"<NotTypes/>")
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(wrong_root_dir)
            (wrong_root_dir / "[Content_Types].xml").unlink()
            with self.assertRaises(clean.RefusedToClean):
                clean.remove_orphaned_slides(wrong_root_dir)
            self.assertTrue(w1.exists())
            self.assertTrue(w2.exists())

            # Case 5: duplicate relationship Id targeting slide1.xml and slide2.xml must refuse
            dup_dir, dup_s1, dup_s2 = _build_deck("clean_dup_rid")
            dup_pres_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(dup_pres_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/slide", Target="slides/slide1.xml")
            ET.SubElement(dup_pres_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/slide", Target="slides/slide2.xml")
            (dup_dir / "ppt" / "_rels" / "presentation.xml.rels").write_bytes(
                ET.tostring(dup_pres_rels, encoding="utf-8", xml_declaration=True)
            )
            with self.assertRaises(clean.RefusedToClean):
                clean.remove_orphaned_slides(dup_dir)
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(dup_dir)
            self.assertTrue(dup_s1.exists())
            self.assertTrue(dup_s2.exists())

            # Case 6: wrong [Content_Types].xml namespace, unexpected children, missing attrs, or invalid PartName syntax must refuse
            bad_ct_variants = [
                ("clean_ct_wrong_ns", b'<Types xmlns="urn:wrong"><Garbage/></Types>', False),
                (
                    "clean_ct_bad_child",
                    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Garbage/></Types>',
                    False,
                ),
                (
                    "clean_ct_missing_attr",
                    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    b'<Override ContentType="application/xml"/></Types>',
                    False,
                ),
                (
                    "clean_ct_empty_segment",
                    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    b'<Override PartName="/ppt//slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>',
                    True,
                ),
                (
                    "clean_ct_trailing_slash",
                    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    b'<Override PartName="/ppt/slides/slide1.xml/" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>',
                    True,
                ),
            ]
            val_pptx_case = None
            if importlib.util.find_spec("lxml") is not None:
                added_path = str(pptx_scripts)
                sys.path.insert(0, added_path)
                try:
                    import office.validators.pptx as val_pptx_case
                finally:
                    if added_path in sys.path:
                        sys.path.remove(added_path)
            for label, raw_ct, check_validator in bad_ct_variants:
                bad_dir, bs1, bs2 = _build_deck(label, ct_bytes=raw_ct)
                with self.assertRaises(clean.RefusedToClean):
                    clean.remove_orphaned_slides(bad_dir)
                with self.assertRaises(clean.RefusedToClean):
                    clean.clean_unused_files(bad_dir)
                if check_validator and val_pptx_case is not None:
                    self.assertFalse(val_pptx_case.PPTXSchemaValidator(bad_dir).validate_content_types())
                self.assertTrue(bs1.exists())
                self.assertTrue(bs2.exists())

            # Case 7: valid Unicode xsd:ID, quoted ST_ContentType escapes/Latin-1, space-bearing parts, and whitespace-padded xs:anyURI Targets
            valid_dir = self.root / "clean_valid_opc_unicode"
            (valid_dir / "_rels").mkdir(parents=True)
            (valid_dir / "ppt" / "_rels").mkdir(parents=True)
            (valid_dir / "ppt" / "slides" / "_rels").mkdir(parents=True)
            (valid_dir / "ppt" / "media").mkdir(parents=True)

            pkg_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(pkg_rels, f"{{{rels_ns}}}Relationship", Id="rId1", Type=f"{r_ns}/officeDocument", Target="ppt/presentation.xml")
            (valid_dir / "_rels" / ".rels").write_bytes(ET.tostring(pkg_rels, encoding="utf-8", xml_declaration=True))

            pres_valid = ET.Element(f"{{{p_ns}}}presentation")
            ET.SubElement(pres_valid, f"{{{p_ns}}}sldMasterIdLst")
            sld_lst_valid = ET.SubElement(pres_valid, f"{{{p_ns}}}sldIdLst")
            ET.SubElement(sld_lst_valid, f"{{{p_ns}}}sldId", {"id": "256", f"{{{r_ns}}}id": "rId\u00e9"})
            ET.SubElement(pres_valid, f"{{{p_ns}}}notesSz", {"cx": "6858000", "cy": "9144000"})
            (valid_dir / "ppt" / "presentation.xml").write_bytes(ET.tostring(pres_valid, encoding="utf-8", xml_declaration=True))

            pres_rels_valid = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(
                pres_rels_valid,
                f"{{{rels_ns}}}Relationship",
                Id=" rId\u00e9 ",
                Type=f" {r_ns}/slide ",
                Target=" slides/slide 1.xml ",
            )
            ET.SubElement(
                pres_rels_valid,
                f"{{{rels_ns}}}Relationship",
                Id="rId2",
                Type=f"{r_ns}/slide",
                Target="slides/slide 2.xml",
            )
            (valid_dir / "ppt" / "_rels" / "presentation.xml.rels").write_bytes(
                ET.tostring(pres_rels_valid, encoding="utf-8", xml_declaration=True)
            )

            valid_slide_bytes = add_slide_case7.MINIMAL_SLIDE_XML.encode("utf-8")
            vs1 = valid_dir / "ppt" / "slides" / "slide 1.xml"
            vs2 = valid_dir / "ppt" / "slides" / "slide 2.xml"
            vs1.write_bytes(valid_slide_bytes)
            vs2.write_bytes(valid_slide_bytes)

            slide1_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(
                slide1_rels,
                f"{{{rels_ns}}}Relationship",
                Id=" rIdImg1 ",
                Type=f" {r_ns}/image ",
                Target="../media/image1.png ",
            )
            (valid_dir / "ppt" / "slides" / "_rels" / "slide 1.xml.rels").write_bytes(
                ET.tostring(slide1_rels, encoding="utf-8", xml_declaration=True)
            )

            img_kept = valid_dir / "ppt" / "media" / "image1.png"
            img_orphan = valid_dir / "ppt" / "media" / "orphan.png"
            img_kept.write_bytes(b"PNG-KEPT")
            img_orphan.write_bytes(b"PNG-ORPHAN")

            ct_valid = ET.Element(f"{{{ct_ns}}}Types")
            ET.SubElement(
                ct_valid,
                f"{{{ct_ns}}}Default",
                Extension="rels",
                ContentType="application/vnd.openxmlformats-package.relationships+xml",
            )
            ET.SubElement(ct_valid, f"{{{ct_ns}}}Default", Extension="png", ContentType="image/png")
            ET.SubElement(
                ct_valid,
                f"{{{ct_ns}}}Default",
                Extension="xml",
                ContentType='application/xml;p="a\\"b";q="caf\u00e9";r="a\\\\"',
            )
            ET.SubElement(
                ct_valid,
                f"{{{ct_ns}}}Override",
                PartName="/ppt/presentation.xml",
                ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
            )
            ET.SubElement(
                ct_valid,
                f"{{{ct_ns}}}Override",
                PartName=" /ppt/slides/slide 1.xml ",
                ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
            )
            ET.SubElement(
                ct_valid,
                f"{{{ct_ns}}}Override",
                PartName=" /ppt/slides/slide 2.xml ",
                ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
            )
            (valid_dir / "[Content_Types].xml").write_bytes(ET.tostring(ct_valid, encoding="utf-8", xml_declaration=True))

            removed = clean.clean_unused_files(valid_dir)
            self.assertIn("ppt/slides/slide 2.xml", removed)
            self.assertIn("ppt/media/orphan.png", removed)
            self.assertNotIn("ppt/slides/slide 1.xml", removed)
            self.assertNotIn("ppt/media/image1.png", removed)
            self.assertTrue(vs1.is_file())
            self.assertTrue(img_kept.is_file())
            self.assertFalse(vs2.exists())
            self.assertFalse(img_orphan.exists())
            ct_after = (valid_dir / "[Content_Types].xml").read_text(encoding="utf-8")
            self.assertIn("/ppt/slides/slide 1.xml", ct_after)
            self.assertNotIn("slide 2.xml", ct_after)

            if importlib.util.find_spec("lxml") is not None:
                added_path = str(pptx_scripts)
                sys.path.insert(0, added_path)
                try:
                    import office.validators.pptx as val_pptx_case7
                finally:
                    if added_path in sys.path:
                        sys.path.remove(added_path)
                self.assertTrue(val_pptx_case7.PPTXSchemaValidator(valid_dir).validate())

            new_slide = add_slide_case7.add_slide(valid_dir, "slide 1.xml", after="slide 1.xml")
            self.assertEqual(new_slide, "slide1.xml")
            self.assertTrue((valid_dir / "ppt" / "slides" / "slide1.xml").is_file())
            if importlib.util.find_spec("lxml") is not None:
                self.assertTrue(val_pptx_case7.PPTXSchemaValidator(valid_dir).validate())

            # Internal scheme-prefixed Target with TargetMode="Internal" must fail both clean and validators
            ftp_dir = self.root / "clean_ftp_internal_rel"
            shutil.copytree(valid_dir, ftp_dir)
            ftp_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(
                ftp_rels,
                f"{{{rels_ns}}}Relationship",
                Id="rIdImg1",
                Type=f"{r_ns}/image",
                Target="../media/image1.png",
            )
            ET.SubElement(
                ftp_rels,
                f"{{{rels_ns}}}Relationship",
                Id="rIdFtp",
                Type=f"{r_ns}/image",
                Target="ftp://example.com/missing.png",
                TargetMode="Internal",
            )
            (ftp_dir / "ppt" / "slides" / "_rels" / "slide 1.xml.rels").write_bytes(
                ET.tostring(ftp_rels, encoding="utf-8", xml_declaration=True)
            )
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(ftp_dir)
            if importlib.util.find_spec("lxml") is not None:
                val_ftp = val_pptx_case7.PPTXSchemaValidator(ftp_dir)
                self.assertFalse(val_ftp.validate_file_references())
                self.assertFalse(val_ftp.validate())

            # Malformed fragment percent-escape in internal Target must fail both clean and validators
            bad_frag_dir = self.root / "clean_bad_frag_rel"
            shutil.copytree(valid_dir, bad_frag_dir)
            frag_rels = ET.Element(f"{{{rels_ns}}}Relationships")
            ET.SubElement(
                frag_rels,
                f"{{{rels_ns}}}Relationship",
                Id="rId1",
                Type=f"{r_ns}/slide",
                Target="slides/slide 1.xml#bad%GG",
            )
            (bad_frag_dir / "ppt" / "_rels" / "presentation.xml.rels").write_bytes(
                ET.tostring(frag_rels, encoding="utf-8", xml_declaration=True)
            )
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(bad_frag_dir)
            if importlib.util.find_spec("lxml") is not None:
                val_frag = val_pptx_case7.PPTXSchemaValidator(bad_frag_dir)
                self.assertFalse(val_frag.validate_file_references())
                self.assertFalse(val_frag.validate())

            # Percent-encoded unreserved characters in PartName (ECMA-376 M1.8) must fail both clean and validators
            bad_m18_dir = self.root / "clean_bad_m18_ct"
            shutil.copytree(valid_dir, bad_m18_dir)
            ct_m18_path = bad_m18_dir / "[Content_Types].xml"
            ct_m18_text = ct_m18_path.read_text(encoding="utf-8")
            self.assertIn("/ppt/slides/slide 1.xml", ct_m18_text)
            ct_m18_path.write_text(
                ct_m18_text.replace("/ppt/slides/slide 1.xml", "/ppt/slides/%73lide%201.xml"),
                encoding="utf-8",
            )
            with self.assertRaises(clean.RefusedToClean):
                clean.clean_unused_files(bad_m18_dir)
            if importlib.util.find_spec("lxml") is not None:
                val_m18 = val_pptx_case7.PPTXSchemaValidator(bad_m18_dir)
                self.assertFalse(val_m18.validate_content_types())
                self.assertFalse(val_m18.validate())

            # Malformed External Target port, malformed Type scheme, and valid IPvFuture host
            for case_name, rel_id, rel_type, rel_target, rel_mode, should_pass in (
                ("bad_ext_port", "rIdBadExt", f"{r_ns}/hyperlink", "http://host:abc/a", "External", False),
                ("bad_type_scheme", "rIdBadType", "1bad:type", "https://example.com/ok", "External", False),
                ("ipvfuture_ext", "rIdIpvf", f"{r_ns}/hyperlink", "http://[v1.a]/a", "External", True),
            ):
                case_dir = self.root / f"clean_{case_name}"
                shutil.copytree(valid_dir, case_dir)
                case_rels = ET.Element(f"{{{rels_ns}}}Relationships")
                ET.SubElement(
                    case_rels,
                    f"{{{rels_ns}}}Relationship",
                    Id="rIdImg1",
                    Type=f"{r_ns}/image",
                    Target="../media/image1.png",
                )
                ET.SubElement(
                    case_rels,
                    f"{{{rels_ns}}}Relationship",
                    Id=rel_id,
                    Type=rel_type,
                    Target=rel_target,
                    TargetMode=rel_mode,
                )
                (case_dir / "ppt" / "slides" / "_rels" / "slide 1.xml.rels").write_bytes(
                    ET.tostring(case_rels, encoding="utf-8", xml_declaration=True)
                )
                if should_pass:
                    self.assertEqual(clean.clean_unused_files(case_dir), [])
                    if importlib.util.find_spec("lxml") is not None:
                        val_case = val_pptx_case7.PPTXSchemaValidator(case_dir)
                        self.assertTrue(val_case.validate())
                else:
                    with self.assertRaises(clean.RefusedToClean):
                        clean.clean_unused_files(case_dir)
                    if importlib.util.find_spec("lxml") is not None:
                        val_case = val_pptx_case7.PPTXSchemaValidator(case_dir)
                        self.assertFalse(val_case.validate_file_references())
                        self.assertFalse(val_case.validate())

            for good_ct in (
                "application/xml",
                'application/xml;p="a\\"b"',
                'application/xml;p="a\\\\"',
                'application/xml;p="a\\"',
                'application/xml;p="caf\u00e9"',
                'application/xml ; p="a\tb"',
                'application/xml;p="a\\x"',
            ):
                self.assertTrue(clean._is_valid_content_type(good_ct), good_ct)
            for bad_ct in (
                "not-a-type",
                "application/xml;",
                "application/xml; p = token",
                'application/xml;p="bad"tail',
                'application/xml;p="unterminated',
                'application/xml;p="\x80"',
                'application/xml;p="\u0100"',
            ):
                self.assertFalse(clean._is_valid_content_type(bad_ct), bad_ct)

    def test_pptx_apply_theme_resolves_project_local_deps_and_writes_atomically(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node executable not available")

        apply_theme_js = CRAFT_DIR / "skills" / "pptx" / "scripts" / "apply_theme.js"
        proj = self.root / "apply_theme_proj"
        nm_jszip = proj / "node_modules" / "jszip"
        nm_pptx = proj / "node_modules" / "pptxgenjs"
        nm_jszip.mkdir(parents=True)
        nm_pptx.mkdir(parents=True)

        (nm_pptx / "package.json").write_text(json.dumps({"name": "pptxgenjs", "main": "index.js"}), encoding="utf-8")
        (nm_pptx / "index.js").write_text("module.exports = function FakePptxGenJS() {};\n", encoding="utf-8")
        (nm_jszip / "package.json").write_text(json.dumps({"name": "jszip", "main": "index.js"}), encoding="utf-8")
        (nm_jszip / "index.js").write_text(
            """const zlib = require("zlib");
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
  }
  return (c ^ 0xffffffff) >>> 0;
}
class FakeZip {
  constructor() { this.files = {}; }
  static async loadAsync(buf) {
    const zip = new FakeZip();
    let eocd = -1;
    for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
      if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error("Bad zip");
    const total = buf.readUInt16LE(eocd + 10);
    let ptr = buf.readUInt32LE(eocd + 16);
    for (let idx = 0; idx < total; idx++) {
      if (buf.readUInt32LE(ptr) !== 0x02014b50) throw new Error("Bad CD");
      const compMethod = buf.readUInt16LE(ptr + 10);
      const compSize = buf.readUInt32LE(ptr + 20);
      const uncompSize = buf.readUInt32LE(ptr + 24);
      const nameLen = buf.readUInt16LE(ptr + 28);
      const extraLen = buf.readUInt16LE(ptr + 30);
      const commLen = buf.readUInt16LE(ptr + 32);
      const lfhOff = buf.readUInt32LE(ptr + 42);
      const name = buf.toString("utf8", ptr + 46, ptr + 46 + nameLen);
      const lfhNameLen = buf.readUInt16LE(lfhOff + 26);
      const lfhExtraLen = buf.readUInt16LE(lfhOff + 28);
      const dataStart = lfhOff + 30 + lfhNameLen + lfhExtraLen;
      const raw = buf.subarray(dataStart, dataStart + compSize);
      const payload = compMethod === 8 ? zlib.inflateRawSync(raw) : Buffer.from(raw);
      zip.files[name] = {
        name,
        dir: name.endsWith("/"),
        _data: { uncompressedSize: uncompSize },
        _buf: payload,
        async async(kind) {
          return kind === "string" ? this._buf.toString("utf8") : Buffer.from(this._buf);
        },
      };
      ptr += 46 + nameLen + extraLen + commLen;
    }
    return zip;
  }
  file(name, data) {
    if (arguments.length === 1) return this.files[name] || null;
    const payload = Buffer.isBuffer(data) ? Buffer.from(data) : Buffer.from(String(data), "utf8");
    this.files[name] = {
      name,
      dir: false,
      _data: { uncompressedSize: payload.length },
      _buf: payload,
      async async(kind) {
        return kind === "string" ? this._buf.toString("utf8") : Buffer.from(this._buf);
      },
    };
    return this;
  }
  async generateAsync() {
    const locals = [];
    const centrals = [];
    let offset = 0;
    for (const entry of Object.values(this.files)) {
      const nameBuf = Buffer.from(entry.name, "utf8");
      const dataBuf = entry.dir ? Buffer.alloc(0) : (entry._buf || Buffer.alloc(0));
      const crc = crc32(dataBuf);
      const lfh = Buffer.alloc(30);
      lfh.writeUInt32LE(0x04034b50, 0);
      lfh.writeUInt16LE(20, 4);
      lfh.writeUInt16LE(0x0800, 6);
      lfh.writeUInt16LE(0, 8);
      lfh.writeUInt32LE(crc, 14);
      lfh.writeUInt32LE(dataBuf.length, 18);
      lfh.writeUInt32LE(dataBuf.length, 22);
      lfh.writeUInt16LE(nameBuf.length, 26);
      locals.push(lfh, nameBuf, dataBuf);

      const cdh = Buffer.alloc(46);
      cdh.writeUInt32LE(0x02014b50, 0);
      cdh.writeUInt16LE(20, 4);
      cdh.writeUInt16LE(20, 6);
      cdh.writeUInt16LE(0x0800, 8);
      cdh.writeUInt16LE(0, 10);
      cdh.writeUInt32LE(crc, 16);
      cdh.writeUInt32LE(dataBuf.length, 20);
      cdh.writeUInt32LE(dataBuf.length, 24);
      cdh.writeUInt16LE(nameBuf.length, 28);
      cdh.writeUInt32LE(offset, 42);
      centrals.push(cdh, nameBuf);
      offset += lfh.length + nameBuf.length + dataBuf.length;
    }
    const cdBuf = Buffer.concat(centrals);
    const eocd = Buffer.alloc(22);
    eocd.writeUInt32LE(0x06054b50, 0);
    const count = Object.keys(this.files).length;
    eocd.writeUInt16LE(count, 8);
    eocd.writeUInt16LE(count, 10);
    eocd.writeUInt32LE(cdBuf.length, 12);
    eocd.writeUInt32LE(offset, 16);
    return Buffer.concat([...locals, cdBuf, eocd]);
  }
}
module.exports = FakeZip;
""",
            encoding="utf-8",
        )

        theme_obj = {
            "name": 'Northwind & "Co" <1>',
            "colors": {
                "dk1": "111111",
                "lt1": "ffffff",
                "dk2": "222222",
                "lt2": "eeeeee",
                "accent1": "aa1122",
                "accent2": "bb2233",
                "accent3": "cc3344",
                "accent4": "dd4455",
                "accent5": "ee5566",
                "accent6": "ff6677",
                "hlink": "0000ff",
                "folHlink": "800080",
            },
        }
        theme_xml_src = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">'
            '<a:themeElements>'
            '<a:clrScheme name="Office">'
            '<a:dk1><a:srgbClr val="000000"/></a:dk1>'
            "</a:clrScheme>"
            '<a:fontScheme name="Office"/>'
            "</a:themeElements>"
            "</a:theme>"
        )
        chart_xml_src = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<c:valAx><c:crossesAt val="autoZero"/></c:valAx>'
            '<a:ln><a:prstDash val="solid"/></a:ln>'
            "</c:chartSpace>"
        )

        def _write_sample_deck(dest: pathlib.Path) -> bytes:
            with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr(zipfile.ZipInfo("ppt/slides/"), b"")
                zf.writestr("ppt/theme/theme1.xml", theme_xml_src.encode("utf-8"))
                zf.writestr("ppt/charts/chart1.xml", chart_xml_src.encode("utf-8"))
                zf.writestr("ppt/slides/slide1.xml", b'<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:srgbClr val="112233"/></p:sld>')
            return dest.read_bytes()

        deck_prog = proj / "deck_prog.pptx"
        deck_cli = proj / "deck_cli.pptx"
        deck_fail = proj / "deck_fail.pptx"
        many_deck = proj / "many_entries.pptx"
        gap_deck = proj / "gap_crafted.pptx"
        _write_sample_deck(deck_prog)
        _write_sample_deck(deck_cli)
        orig_fail_bytes = _write_sample_deck(deck_fail)
        with zipfile.ZipFile(many_deck, "w", compression=zipfile.ZIP_STORED) as zf:
            for idx in range(10001):
                zf.writestr(f"e{idx}.txt", b"")

        # Crafted dual-directory gap archive: benign CD at offset 31, real LFH at 78, hostile symlink CD at 109,
        # EOCD declaring cdOffset=31, cdSize=47 (leaving a gap JSZip would use as extraBytes to read offset 109).
        import struct

        padding = b"\x00" * 31
        lfh_crafted = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, 0, 0, 0, 0, 0, 0, 1, 0) + b"a"
        cd_benign = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 78) + b"a"
        cd_hostile = struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50,
            (3 << 8) | 20,
            20,
            0,
            0,
            0,
            0,
            0,
            0,
            200 * 1024 * 1024,
            1,
            0,
            0,
            0,
            0,
            0o120777 << 16,
            78,
        ) + b"a"
        eocd_crafted = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(cd_benign), 31, 0)
        gap_deck.write_bytes(padding + cd_benign + lfh_crafted + cd_hostile + eocd_crafted)

        theme_json = proj / "theme.json"
        theme_json.write_text(json.dumps(theme_obj), encoding="utf-8")

        runner = proj / "runner.js"
        runner.write_text(
            f"""const assert = require("assert");
const fs = require("fs");
const path = require("path");
const {{ applyTheme }} = require({json.dumps(str(apply_theme_js))});

async function main() {{
  const projDir = {json.dumps(str(proj))};
  const theme = JSON.parse(fs.readFileSync(path.join(projDir, "theme.json"), "utf8"));
  await applyTheme(path.join(projDir, "deck_prog.pptx"), theme);

  const failingFs = Object.assign({{}}, fs, {{
    writeSync(fd, buf, offset, len) {{
      throw Object.assign(new Error("ENOSPC: no space left on device"), {{ code: "ENOSPC" }});
    }},
  }});
  let enospcCaught = false;
  try {{
    await applyTheme(path.join(projDir, "deck_fail.pptx"), theme, {{ fs: failingFs }});
  }} catch (err) {{
    if (err && err.code === "ENOSPC") enospcCaught = true;
    else throw err;
  }}
  assert.strictEqual(enospcCaught, true);

  let preZipEntryLimitCaught = false;
  try {{
    await applyTheme(path.join(projDir, "many_entries.pptx"), theme, {{
      jszip: {{
        loadAsync: async () => {{
          throw new Error("JSZip.loadAsync should not have been called");
        }},
      }},
    }});
  }} catch (err) {{
    if (err && /exceeding limit 10000/i.test(err.message)) preZipEntryLimitCaught = true;
    else throw err;
  }}
  assert.strictEqual(preZipEntryLimitCaught, true);

  let gapCdCaught = false;
  try {{
    await applyTheme(path.join(projDir, "gap_crafted.pptx"), theme, {{
      jszip: {{
        loadAsync: async () => {{
          throw new Error("JSZip.loadAsync should not have been called for gap_crafted");
        }},
      }},
    }});
  }} catch (err) {{
    if (err && /central directory/i.test(err.message)) gapCdCaught = true;
    else throw err;
  }}
  assert.strictEqual(gapCdCaught, true);

  const fakeZip = {{
    files: Object.fromEntries(Array.from({{ length: 10001 }}, (_, i) => [`f${{i}}.xml`, {{ dir: false }}])),
  }};
  let entryLimitCaught = false;
  try {{
    await applyTheme(path.join(projDir, "deck_fail.pptx"), theme, {{
      jszip: {{ loadAsync: async () => fakeZip }},
    }});
  }} catch (err) {{
    if (err && /exceeding limit 10000/i.test(err.message)) entryLimitCaught = true;
    else throw err;
  }}
  assert.strictEqual(entryLimitCaught, true);
}}

main().catch((err) => {{ console.error(err); process.exit(1); }});
""",
            encoding="utf-8",
        )

        # Ensure NODE_PATH is not relied upon; run programmatic test outside proj so cwd cannot mask caller resolution
        clean_env = {k: v for k, v in os.environ.items() if k != "NODE_PATH"}
        proc_prog = subprocess.run(
            [node, str(runner)],
            cwd=str(self.root),
            env=clean_env,
            capture_output=True,
            text=True,
            creationflags=CREATION_FLAGS,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc_prog.returncode, 0, f"stderr={proc_prog.stderr}\nstdout={proc_prog.stdout}")
        self.assertEqual(deck_fail.read_bytes(), orig_fail_bytes)
        self.assertEqual(list(proj.glob("*.tmp")), [])

        # Run CLI without NODE_PATH from proj directory so process.cwd() finds project-local pptxgenjs
        proc_cli = subprocess.run(
            [node, str(apply_theme_js), "deck_cli.pptx", "theme.json"],
            cwd=str(proj),
            env=clean_env,
            capture_output=True,
            text=True,
            creationflags=CREATION_FLAGS,
            timeout=30,
            check=False,
        )
        self.assertEqual(proc_cli.returncode, 0, f"stderr={proc_cli.stderr}\nstdout={proc_cli.stdout}")

        proc_many = subprocess.run(
            [node, str(apply_theme_js), "many_entries.pptx", "theme.json"],
            cwd=str(proj),
            env=clean_env,
            capture_output=True,
            text=True,
            creationflags=CREATION_FLAGS,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(proc_many.returncode, 0)
        self.assertIn("exceeding limit 10000", proc_many.stderr)

        proc_gap = subprocess.run(
            [node, str(apply_theme_js), "gap_crafted.pptx", "theme.json"],
            cwd=str(proj),
            env=clean_env,
            capture_output=True,
            text=True,
            creationflags=CREATION_FLAGS,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(proc_gap.returncode, 0)
        self.assertIn("central directory", proc_gap.stderr.lower())

        for out_deck in (deck_prog, deck_cli):
            with zipfile.ZipFile(out_deck, "r") as zf:
                self.assertNotIn("ppt/slides/", zf.namelist())
                theme_out = zf.read("ppt/theme/theme1.xml").decode("utf-8")
                self.assertIn('name="Northwind &amp; &quot;Co&quot; &lt;1&gt;"', theme_out)
                self.assertIn('<a:srgbClr val="AA1122"/>', theme_out)
                chart_out = zf.read("ppt/charts/chart1.xml").decode("utf-8")
                self.assertIn('<c:crosses val="autoZero"/>', chart_out)
                self.assertNotIn('<c:crossesAt val="autoZero"/>', chart_out)


if __name__ == "__main__":
    unittest.main()
