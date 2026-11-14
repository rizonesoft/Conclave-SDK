"""Tests for standalone Antigravity plugins under plugins/agy/ and powertools_hook.py."""
from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

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

    def run_hook(self, payload: dict) -> dict:
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
            "git branch -f feature-local",
            'git commit -m "avoid git push -f accidental match"',
            "rm -rf build",
            r"Remove-Item R:\scratch\temp -Recurse -Force",
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
            "git push -f",
            "git push --force-with-lease origin main",
            "git -C . push origin +main",
            "gh repo delete owner/repo --yes",
            "Format-Volume -DriveLetter E -FileSystem NTFS",
            "rm -rf /",
        ]
        for cmd in dangerous_cmds:
            with self.subTest(cmd=cmd):
                out = self.run_hook({
                    "hookEventName": "PreToolUse",
                    "toolCall": {"id": "c2", "name": "run_command", "args": {"CommandLine": cmd}},
                })
                self.assertEqual(out.get("decision"), "force_ask", f"expected force_ask for {cmd}: {out}")
                self.assertTrue(out.get("reason"))

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


if __name__ == "__main__":
    unittest.main()
