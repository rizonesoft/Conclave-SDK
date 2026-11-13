"""The base kit's Antigravity subagents (D00 T02 §3): one definition per Claude subagent under `.agents/agents/`,
pinned to `gemini-4-hydrogen-medium` and checked and invoked through `scripts/agy-subagent.py`, with read-only tools
and no write or edit tool. A live test (CONCLAVE_LIVE_AGY=1, the installed and signed-in CLI) proves that a fresh
`--agent agy` install loads all five in `<subagents>` and that each completes its known-answer task on
`gemini-4-hydrogen-medium`."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "kits/base/templates"
AGY_AGENTS = BASE / ".agents/agents"
CLAUDE_AGENTS = BASE / ".claude/agents"
RUNNER = BASE / "scripts/agy-subagent.py"
TOOLS = ["read_file", "run_command", "manage_task"]
EXPECTED_NAMES = ["code-explorer", "debug-evidence", "git-runner", "mutation-tester", "test-runner"]

_spec = importlib.util.spec_from_file_location("agy_subagent", RUNNER)
assert _spec is not None and _spec.loader is not None
agy_subagent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agy_subagent)


def problems(filename: str, text: str, claude_text: str) -> list[str]:
    """Every way one Antigravity definition fails its base-kit contract; empty when it holds."""
    return agy_subagent.definition_problems(
        filename,
        text,
        expected_tools=TOOLS,
        claude_text=claude_text,
    )


def lf_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        probe = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return str(pid) in probe.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class Definitions(unittest.TestCase):
    def test_there_is_one_definition_per_claude_subagent_and_no_other(self):
        self.assertEqual(
            sorted(p.name for p in AGY_AGENTS.iterdir()),
            sorted(p.name for p in CLAUDE_AGENTS.glob("*.md")),
        )
        self.assertEqual([p.stem for p in sorted(AGY_AGENTS.glob("*.md"))], EXPECTED_NAMES)

    def test_each_definition_holds_its_contract(self):
        for path in sorted(AGY_AGENTS.glob("*.md")):
            with self.subTest(path.name):
                self.assertEqual(
                    problems(
                        path.name,
                        path.read_text(encoding="utf-8"),
                        (CLAUDE_AGENTS / path.name).read_text(encoding="utf-8"),
                    ),
                    [],
                )
        checked = subprocess.run(
            [sys.executable, str(RUNNER), "--check", "--root", str(BASE)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("5 definition(s) checked, all pinned to gemini-4-hydrogen-medium", checked.stdout)

    def test_a_definition_that_breaks_the_contract_fails_the_check(self):
        path = AGY_AGENTS / "test-runner.md"
        good = path.read_text(encoding="utf-8")
        claude = (CLAUDE_AGENTS / path.name).read_text(encoding="utf-8")
        tools_line = "tools: [read_file, run_command, manage_task]\n"
        pin_line = "conclave_model: gemini-4-hydrogen-medium\n"
        model_line = "model: flash\n"
        self.assertIn(tools_line, good)
        self.assertIn(pin_line, good)
        self.assertIn(model_line, good)

        runner_and_kit_cases = {
            "a write tool": good.replace(tools_line, "tools: [read_file, run_command, manage_task, write_file]\n"),
            "an edit tool": good.replace(tools_line, "tools: [read_file, run_command, manage_task, edit_file]\n"),
            "wildcard tool": good.replace(tools_line, "tools: [*]\n"),
            "run_command removed": good.replace(tools_line, "tools: [read_file, manage_task]\n"),
            "read_file removed": good.replace(tools_line, "tools: [run_command, manage_task]\n"),
            "extra search_web tool": good.replace(tools_line, "tools: [read_file, run_command, manage_task, search_web]\n"),
            "tools left out": good.replace(tools_line, ""),
            "model inherit": good.replace(model_line, "model: inherit\n"),
            "model concrete id": good.replace(model_line, "model: gemini-4-hydrogen-medium\n"),
            "conclave_model omitted": good.replace(pin_line, ""),
            "conclave_model low effort": good.replace(pin_line, "conclave_model: gemini-4-hydrogen-low\n"),
            "conclave_model high effort": good.replace(pin_line, "conclave_model: gemini-4-hydrogen-high\n"),
            "conclave_model xhigh effort": good.replace(pin_line, "conclave_model: gemini-4-hydrogen-xhigh\n"),
            "conclave_model carbon": good.replace(pin_line, "conclave_model: gemini-4-carbon-medium\n"),
            "conclave_model claude": good.replace(pin_line, "conclave_model: claude-sonnet-5-5-medium\n"),
            "conclave_model gpt": good.replace(pin_line, "conclave_model: gpt-6-astra\n"),
            "subagent false": good.replace("subagent: true\n", "subagent: false\n"),
            "mainAgent false": good.replace("mainAgent: true\n", "mainAgent: false\n"),
            "inheritMcp true": good.replace("inheritMcp: false\n", "inheritMcp: true\n"),
            "another name": good.replace("name: test-runner\n", "name: runner\n"),
            "duplicate pin": good.replace(pin_line, pin_line + "conclave_model: gemini-4-carbon-medium\n"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            agents_dir = Path(tmp) / ".agents/agents"
            agents_dir.mkdir(parents=True)
            subject = agents_dir / path.name
            for name, text in runner_and_kit_cases.items():
                with self.subTest(name=name):
                    self.assertNotEqual(text, good)
                    self.assertTrue(agy_subagent.definition_problems(path.name, text), name)
                    self.assertTrue(problems(path.name, text, claude), name)
                    subject.write_text(text, encoding="utf-8")
                    res = subprocess.run(
                        [sys.executable, str(RUNNER), "--check", "--root", tmp],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(res.returncode, 1, f"{name}: {res.stdout}{res.stderr}")
            # Invocation refuses a role missing run_command before starting the CLI.
            subject.write_text(runner_and_kit_cases["run_command removed"], encoding="utf-8")
            invoked = subprocess.run(
                [sys.executable, str(RUNNER), "test-runner", "--root", tmp, "-p=hi"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(invoked.returncode, 2, invoked.stdout + invoked.stderr)

        kit_only_cases = {
            "another body": (good + "Also edit files.\n", claude),
            "another description": (good.replace("description: Run test suites", "description: Different"), claude),
            "broken claude counterpart": (good, "no frontmatter\n"),
        }
        for name, (text, claude_variant) in kit_only_cases.items():
            with self.subTest(name=name):
                self.assertTrue(problems(path.name, text, claude_variant), name)

    def test_a_fresh_agy_install_has_all_five_and_runner_and_no_claude_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            subprocess.run(
                [sys.executable, str(ROOT / "forge.py"), "init", str(project), "--kit", "base", "--agent", "agy"],
                check=True,
                capture_output=True,
            )
            self.assertEqual(
                sorted(p.name for p in (project / ".agents/agents").glob("*.md")),
                sorted(p.name for p in AGY_AGENTS.glob("*.md")),
            )
            self.assertTrue((project / "scripts/agy-subagent.py").is_file())
            self.assertFalse((project / ".claude").exists())
            checked = subprocess.run(
                [sys.executable, str(project / "scripts/agy-subagent.py"), "--check", "--root", str(project)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

    def test_the_sdk_s_own_copy_equals_the_kit(self):
        installed_dir = ROOT / ".agents/agents"
        self.assertEqual(
            sorted(p.name for p in installed_dir.iterdir()),
            sorted(p.name for p in AGY_AGENTS.iterdir()),
        )
        for path in sorted(AGY_AGENTS.glob("*.md")):
            self.assertEqual(lf_bytes(installed_dir / path.name), lf_bytes(path), path.name)
        self.assertEqual(lf_bytes(ROOT / "scripts/agy-subagent.py"), lf_bytes(RUNNER))

    def test_documentation_records_agy_subagents_model_and_codex_limit(self):
        readme = (ROOT / "kits/base/README.md").read_text(encoding="utf-8")
        agents_md = (BASE / "AGENTS.md").read_text(encoding="utf-8")
        gemini_md = (BASE / "GEMINI.md").read_text(encoding="utf-8")
        codex_md = (BASE / "CODEX.md").read_text(encoding="utf-8")
        for needle in (
            "1.5.8",
            ".agents/agents/",
            "migrate-agent-settings",
            "gemini-4-hydrogen-medium",
            "scripts/agy-subagent.py",
            "Codex has no",
            *EXPECTED_NAMES,
        ):
            self.assertIn(needle, readme)
        for needle in (".agents/agents/", "gemini-4-hydrogen-medium", "scripts/agy-subagent.py", "Codex has no subagent"):
            self.assertIn(needle, agents_md)
        self.assertIn("gemini-4-hydrogen-medium", gemini_md)
        self.assertIn("scripts/agy-subagent.py", gemini_md)
        self.assertIn("no project subagent definitions", codex_md)

    def test_mutation_task_requires_independent_execution_evidence(self):
        prompt, check = TASKS["mutation-tester"]
        self.assertNotIn("test_add_sums", prompt)
        self.assertFalse(check("I could not run test_add_sums"))
        self.assertFalse(check("| calc.py | NOT APPLIED (0) | test_add_sums | - |"))
        self.assertFalse(check("| calc.py | yes | test_add_sums | SURVIVED |"))
        self.assertFalse(check("| calc.py | yes | none | killed |"))
        self.assertTrue(check("| calc.py | yes (1 occurrence) | test_add_sums | killed |"))

        live_project = Path(tempfile.gettempdir()) / "live-proj"
        wt_project = Path(tempfile.gettempdir()) / "mt-wt"
        base_entry = {
            "cwd": str(wt_project),
            "calc_file": str(wt_project / "calc.py"),
            "calc_sha256": CALC_SHA256,
            "add_2_3": 5,
            "passed": True,
        }
        mut_entry = {
            "cwd": str(wt_project),
            "calc_file": str(wt_project / "calc.py"),
            "calc_sha256": MUTATED_CALC_SHA256,
            "add_2_3": -1,
            "passed": False,
        }
        # Inspection-only (no test execution), baseline-only, mutated-only, unmutated repeat, reversed order,
        # wrong mutation, and mutating the live checkout instead of a throwaway worktree all fail.
        self.assertTrue(mutation_trace_problems([], live_project))
        self.assertTrue(mutation_trace_problems([base_entry], live_project))
        self.assertTrue(mutation_trace_problems([mut_entry], live_project))
        self.assertTrue(mutation_trace_problems([base_entry, base_entry], live_project))
        self.assertTrue(mutation_trace_problems([mut_entry, base_entry], live_project))
        self.assertTrue(
            mutation_trace_problems(
                [base_entry, {**mut_entry, "calc_sha256": "deadbeef", "add_2_3": 0}],
                live_project,
            )
        )
        self.assertTrue(
            mutation_trace_problems(
                [
                    {**base_entry, "cwd": str(live_project), "calc_file": str(live_project / "calc.py")},
                    {**mut_entry, "cwd": str(live_project), "calc_file": str(live_project / "calc.py")},
                ],
                live_project,
            )
        )
        self.assertEqual(mutation_trace_problems([base_entry, mut_entry], live_project), [])


class SubagentRunner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "project"
        (self.root / ".agents/agents").mkdir(parents=True)
        shutil.copyfile(AGY_AGENTS / "git-runner.md", self.root / ".agents/agents/git-runner.md")

    def tearDown(self):
        self._tmp.cleanup()

    def _make_stub(self, body: str) -> Path:
        stub_dir = Path(self._tmp.name) / "bin with space"
        stub_dir.mkdir(exist_ok=True)
        stub_py = stub_dir / "stub_agy.py"
        stub_py.write_text(body, encoding="utf-8")
        if os.name == "nt":
            wrapper = stub_dir / "stub_agy.cmd"
            wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{stub_py}" %*\r\n', encoding="utf-8")
            return wrapper
        stub_py.write_text("#!" + sys.executable + "\n" + body, encoding="utf-8")
        stub_py.chmod(0o755)
        return stub_py

    def test_runner_builds_command_verifies_model_and_cleans_up_temp_settings(self):
        record_file = Path(self._tmp.name) / "recorded.json"
        stub = self._make_stub(
            "import json, pathlib, sys\n"
            "args = sys.argv[1:]\n"
            "stdin_text = sys.stdin.read()\n"
            "settings_path = args[args.index('--settings') + 1]\n"
            "settings = json.loads(pathlib.Path(settings_path).read_text(encoding='utf-8'))\n"
            f"pathlib.Path({str(record_file)!r}).write_text(\n"
            "    json.dumps({'args': args, 'stdin': stdin_text, 'settings_path': settings_path, 'settings': settings}),\n"
            "    encoding='utf-8',\n"
            ")\n"
            "print(json.dumps({'event': 'init', 'conversation_id': 'cid-9', 'init': {'model': 'gemini-4-hydrogen-medium', 'agent': 'git-runner'}}))\n"
            "print(json.dumps({'event': 'tool_call', 'tool_call': {'tool_name': 'run_command', 'state': 'DONE'}}))\n"
            "print(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'HEAD is abc123'}}))\n"
        )
        env = {**os.environ, "AGY_BIN": str(stub)}
        res = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "git-runner",
                "--root",
                str(self.root),
                "--allow-command",
                "command(git)",
                "--json",
                "-p=--status",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(out["model"], "gemini-4-hydrogen-medium")
        self.assertEqual(out["agent"], "git-runner")
        self.assertEqual(out["conversation_id"], "cid-9")
        self.assertEqual(out["tool_calls"], ["run_command"])
        self.assertEqual(out["response"], "HEAD is abc123")
        recorded = json.loads(record_file.read_text(encoding="utf-8"))
        self.assertEqual(recorded["stdin"], "--status")
        self.assertNotIn("-p", recorded["args"])
        self.assertFalse(any(a.startswith("-p=") for a in recorded["args"]))
        self.assertIn("--input-format", recorded["args"])
        self.assertEqual(recorded["args"][recorded["args"].index("--input-format") + 1], "text")
        self.assertEqual(recorded["args"][:4], ["--model", "gemini-4-hydrogen-medium", "--agent", "git-runner"])
        self.assertEqual(
            recorded["settings"],
            {
                "agentMode": "",
                "permissions": {
                    "deny": ["write_file(*)", "edit_file(*)", "mcp(*)"],
                    "allow": ["command(git)"],
                },
            },
        )
        self.assertFalse(Path(recorded["settings_path"]).exists())

    def test_runner_delivers_large_stdin_prompt_past_windows_argv_limit(self):
        large_prompt = "trace line: ValueError('boom')\n" * 1600  # ~49,600 chars (> 32,767 Win32 argv limit)
        expected_sha = hashlib.sha256(large_prompt.encode("utf-8")).hexdigest()
        stub = self._make_stub(
            "import hashlib, json, sys\n"
            "raw = sys.stdin.buffer.read()\n"
            "digest = hashlib.sha256(raw).hexdigest()\n"
            "print(json.dumps({'event': 'init', 'init': {'session_id': 's', 'model': 'gemini-4-hydrogen-medium', 'agent': 'git-runner'}}))\n"
            "print(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': f'{len(raw)}:{digest}'}}))\n"
        )
        res = subprocess.run(
            [sys.executable, str(RUNNER), "git-runner", "--root", str(self.root)],
            input=large_prompt,
            env={**os.environ, "AGY_BIN": str(stub)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(res.stdout.strip(), f"{len(large_prompt.encode('utf-8'))}:{expected_sha}")

    def test_runner_refuses_wrong_runtime_model_or_forbidden_tool_or_bad_name(self):
        wrong_model_stub = self._make_stub(
            "import json\n"
            "print(json.dumps({'event': 'init', 'init': {'session_id': 's', 'model': 'gemini-3.8-flash-tiered', 'agent': 'git-runner'}}))\n"
            "print(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'ok'}}))\n"
        )
        res = subprocess.run(
            [sys.executable, str(RUNNER), "git-runner", "--root", str(self.root), "-p", "hi"],
            env={**os.environ, "AGY_BIN": str(wrong_model_stub)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("gemini-3.8-flash-tiered", res.stderr)

        write_tool_stub = self._make_stub(
            "import json\n"
            "print(json.dumps({'event': 'init', 'init': {'session_id': 's', 'model': 'gemini-4-hydrogen-medium', 'agent': 'git-runner'}}))\n"
            "print(json.dumps({'event': 'tool_call', 'tool_call': {'tool_name': 'write_file', 'state': 'DONE'}}))\n"
            "print(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'ok'}}))\n"
        )
        res_write = subprocess.run(
            [sys.executable, str(RUNNER), "git-runner", "--root", str(self.root), "-p", "hi"],
            env={**os.environ, "AGY_BIN": str(write_tool_stub)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res_write.returncode, 1)
        self.assertIn("write_file", res_write.stderr)

        for bad_agent in ("../git-runner", "missing-agent"):
            res_bad = subprocess.run(
                [sys.executable, str(RUNNER), bad_agent, "--root", str(self.root), "-p", "hi"],
                env={**os.environ, "AGY_BIN": str(wrong_model_stub)},
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(res_bad.returncode, 2)

    def test_runner_kills_process_tree_on_timeout(self):
        pid_file = Path(self._tmp.name) / "child.pid"
        hang_stub = self._make_stub(
            "import pathlib, subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid), encoding='utf-8')\n"
            "time.sleep(60)\n"
        )
        res = subprocess.run(
            [sys.executable, str(RUNNER), "git-runner", "--root", str(self.root), "--timeout", "1", "-p", "hi"],
            env={**os.environ, "AGY_BIN": str(hang_stub)},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("timed out", res.stderr)
        child_pid = int(pid_file.read_text(encoding="utf-8").strip())
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and _pid_alive(child_pid):
            time.sleep(0.1)
        self.assertFalse(_pid_alive(child_pid), f"child pid {child_pid} survived timeout cleanup")

    def test_runner_kills_surviving_descendant_even_when_leader_exits_early(self):
        pid_file = Path(self._tmp.name) / "orphan.pid"
        early_exit_stub = self._make_stub(
            "import json, pathlib, subprocess, sys\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid), encoding='utf-8')\n"
            "print(json.dumps({'event': 'init', 'init': {'session_id': 's', 'model': 'gemini-4-hydrogen-medium', 'agent': 'git-runner'}}), flush=True)\n"
            "print(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'done early'}}), flush=True)\n"
            "sys.exit(0)\n"
        )
        t0 = time.monotonic()
        res = subprocess.run(
            [sys.executable, str(RUNNER), "git-runner", "--root", str(self.root), "--timeout", "30", "-p", "hi"],
            env={**os.environ, "AGY_BIN": str(early_exit_stub)},
            capture_output=True,
            text=True,
            timeout=15,
        )
        elapsed = time.monotonic() - t0
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertLess(elapsed, 10.0, "runner waited on an inherited pipe instead of returning on leader exit")
        child_pid = int(pid_file.read_text(encoding="utf-8").strip())
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and _pid_alive(child_pid):
            time.sleep(0.1)
        self.assertFalse(_pid_alive(child_pid), f"descendant pid {child_pid} survived after leader exited")


# The known-answer fixture: one module, one passing and one failing test, one commit.
CALC = "def add(a, b):\n    return a + b\n\n\ndef halve(n):\n    return n / 2\n"
MUTATED_CALC = CALC.replace("return a + b", "return a - b", 1)
CALC_SHA256 = hashlib.sha256(CALC.encode("utf-8")).hexdigest()
MUTATED_CALC_SHA256 = hashlib.sha256(MUTATED_CALC.encode("utf-8")).hexdigest()


def build_tests_source(trace_path: Path) -> str:
    return (
        "import hashlib\nimport json\nimport os\nimport pathlib\nimport unittest\nimport calc\n\n"
        f"TRACE = pathlib.Path({str(trace_path)!r})\n\n\n"
        "class CalcTest(unittest.TestCase):\n"
        "    def test_add_sums(self):\n"
        "        got = calc.add(2, 3)\n"
        "        calc_path = pathlib.Path(calc.__file__).resolve()\n"
        "        entry = {\n"
        "            'cwd': str(pathlib.Path.cwd().resolve()),\n"
        "            'calc_file': str(calc_path),\n"
        "            'calc_sha256': hashlib.sha256(calc_path.read_bytes()).hexdigest(),\n"
        "            'add_2_3': got,\n"
        "            'passed': got == 5,\n"
        "        }\n"
        "        with TRACE.open('a', encoding='utf-8') as handle:\n"
        "            handle.write(json.dumps(entry) + '\\n')\n"
        "        self.assertEqual(got, 5)\n\n"
        "    def test_halve_keeps_whole_numbers(self):\n"
        "        self.assertEqual(calc.halve(7), 3, 'halve must floor odd numbers')\n"
    )


def mutation_trace_problems(entries: list[dict[str, object]], live_project: Path) -> list[str]:
    """Verify independent runtime execution evidence for mutation-tester: a passing baseline run of `test_add_sums` on
    unmutated `calc.py` inside a throwaway worktree, followed by a failing run on the requested `return a - b` mutation
    inside a throwaway worktree, with zero mutated runs against the live checkout."""
    live_root = live_project.resolve()
    live_calc = (live_root / "calc.py").resolve()
    found: list[str] = []
    if not entries:
        return ["test_add_sums never executed (inspection-only run)"]

    for entry in entries:
        calc_file = Path(str(entry.get("calc_file") or "")).resolve()
        if calc_file == live_calc and entry.get("calc_sha256") != CALC_SHA256:
            found.append("live checkout calc.py was mutated instead of an isolated worktree")

    baseline_indices = [
        idx
        for idx, entry in enumerate(entries)
        if Path(str(entry.get("cwd") or "")).resolve() != live_root
        and Path(str(entry.get("calc_file") or "")).resolve() != live_calc
        and entry.get("calc_sha256") == CALC_SHA256
        and entry.get("add_2_3") == 5
        and entry.get("passed") is True
    ]
    if not baseline_indices:
        found.append("no passing baseline execution of test_add_sums observed in an isolated worktree")
        return found

    first_baseline = baseline_indices[0]
    mutated_after = [
        idx
        for idx, entry in enumerate(entries)
        if idx > first_baseline
        and Path(str(entry.get("cwd") or "")).resolve() != live_root
        and Path(str(entry.get("calc_file") or "")).resolve() != live_calc
        and entry.get("calc_sha256") == MUTATED_CALC_SHA256
        and entry.get("add_2_3") == -1
        and entry.get("passed") is False
    ]
    if not mutated_after:
        found.append(
            "no failing mutated execution of test_add_sums (add(2, 3) == -1 on mutated calc.py) observed after baseline"
        )
    return found


SUBJECT = "calc: the known-answer fixture"
TASKS = {
    "code-explorer": (
        "find where the function halve is defined and report its file and line number.",
        lambda r: "calc.py" in r and re.search(r"(?:calc\.py[:#]L?|line )5\b", r) is not None,
    ),
    "git-runner": (
        "report the subject line of the most recent commit.",
        lambda r: SUBJECT in r,
    ),
    "test-runner": (
        "run python -m unittest discover -s tests and report the name of the failing test.",
        lambda r: "test_halve_keeps_whole_numbers" in r,
    ),
    "debug-evidence": (
        "gather the evidence for why python -m unittest discover -s tests fails: report the exact "
        "assertion message and the two values it compared.",
        lambda r: "halve must floor odd numbers" in r and "3.5" in r,
    ),
    "mutation-tester": (
        "in calc.py change 'return a + b' to 'return a - b', run python -m unittest discover -s tests "
        "-k add (its baseline passes), then restore calc.py byte for byte, and report which "
        "test failed under the mutation and the outcome.",
        lambda r: (
            "test_add_sums" in r
            and re.search(r"\bkilled\b", r, re.I) is not None
            and re.search(r"\b(?:not applied|survived|could not)\b", r, re.I) is None
        ),
    ),
}


@unittest.skipUnless(
    os.environ.get("CONCLAVE_LIVE_AGY") and shutil.which("agy"),
    "live: set CONCLAVE_LIVE_AGY=1 on a machine with the signed-in Antigravity CLI",
)
class LiveAgents(unittest.TestCase):
    """Each agent, in a fresh `--agent agy` install, proven on `gemini-4-hydrogen-medium` against the fixture."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.project = Path(cls._tmp.name) / "project"
        subprocess.run(
            [sys.executable, str(ROOT / "forge.py"), "init", str(cls.project), "--kit", "base", "--agent", "agy"],
            check=True,
            capture_output=True,
        )
        cls.trace_path = Path(cls._tmp.name) / "calc-trace.jsonl"
        (cls.project / "tests").mkdir()
        (cls.project / ".gitignore").write_bytes(b"__pycache__/\n*.pyc\n")
        (cls.project / "calc.py").write_bytes(CALC.encode("utf-8"))
        (cls.project / "tests/test_calc.py").write_bytes(build_tests_source(cls.trace_path).encode("utf-8"))
        for args in (
            ["init", "-q"],
            ["config", "user.email", "t@example.com"],
            ["config", "user.name", "T"],
            ["config", "core.autocrlf", "false"],
            ["add", "-A"],
            ["commit", "-qm", SUBJECT],
        ):
            subprocess.run(["git", "-C", str(cls.project), *args], check=True, capture_output=True)
        cls.results: dict[str, object] = {}

    @classmethod
    def tearDownClass(cls):
        print("\nlive agy results:", json.dumps(cls.results, indent=1))
        cls._tmp.cleanup()

    def test_00_install_validates_and_live_session_lists_all_five_subagents(self):
        plugin_dir = Path(self._tmp.name) / "validate-plugin"
        (plugin_dir / "agents").mkdir(parents=True)
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"name": "conclave-base-agents", "version": "1.0.0"}),
            encoding="utf-8",
        )
        for md in (self.project / ".agents/agents").glob("*.md"):
            shutil.copyfile(md, plugin_dir / "agents" / md.name)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        validated = subprocess.run(
            [str(shutil.which("agy")), "plugin", "validate", "--strict", str(plugin_dir)],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

        settings_path = Path(self._tmp.name) / "list-settings.json"
        settings_path.write_text(
            json.dumps({"agentMode": "", "permissions": {"deny": ["write_file(*)", "edit_file(*)", "mcp(*)"]}}),
            encoding="utf-8",
        )
        listed = subprocess.run(
            [
                str(shutil.which("agy")),
                "--model",
                "gemini-4-hydrogen-medium",
                "--settings",
                str(settings_path),
                "--output-format",
                "json",
                "--print-timeout",
                "90s",
                "-p=List the exact names of all available subagents in your <subagents> block, one per line. Call no tools.",
            ],
            cwd=self.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        self.assertEqual(listed.returncode, 0, listed.stdout + listed.stderr)
        response = json.loads(listed.stdout).get("response", "")
        self.results["_session_subagents"] = [name for name in EXPECTED_NAMES if name in response]
        for name in EXPECTED_NAMES:
            self.assertIn(name, response, f"live session omitted {name!r} from <subagents>: {response}")

    def known_answer(self, agent: str):
        task, right = TASKS[agent]
        if agent == "mutation-tester":
            self.trace_path.unlink(missing_ok=True)
        before = hashlib.sha256((self.project / "calc.py").read_bytes()).hexdigest()
        worktrees_before = subprocess.run(
            ["git", "-C", str(self.project), "worktree", "list", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        t0 = time.monotonic()
        res = subprocess.run(
            [
                sys.executable,
                str(self.project / "scripts/agy-subagent.py"),
                agent,
                "--root",
                str(self.project),
                "--allow-command",
                "command(*)",
                "--timeout",
                "240",
                "--json",
            ],
            input=task,
            cwd=self.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=280,
        )
        elapsed = round(time.monotonic() - t0, 1)
        self.assertEqual(res.returncode, 0, f"{agent} failed:\nstdout={res.stdout}\nstderr={res.stderr}")
        payload = json.loads(res.stdout)
        reply = payload["response"]
        tool_calls = payload["tool_calls"]
        trace_entries: list[dict[str, object]] = []
        if agent == "mutation-tester" and self.trace_path.is_file():
            trace_entries = [
                json.loads(line)
                for line in self.trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        record: dict[str, object] = {
            "model": payload["model"],
            "agent": payload["agent"],
            "elapsed_s": elapsed,
            "right": bool(right(reply)),
            "tool_calls": tool_calls,
            "reply": reply[:240],
        }
        if agent == "mutation-tester":
            record["observed_runs"] = [
                {
                    "isolated_worktree": Path(str(e["cwd"])).resolve() != self.project.resolve(),
                    "calc_sha256": str(e["calc_sha256"])[:12],
                    "add_2_3": e["add_2_3"],
                    "passed": e["passed"],
                }
                for e in trace_entries
            ]
        self.results[agent] = record
        self.assertEqual(payload["model"], "gemini-4-hydrogen-medium")
        self.assertEqual(payload["agent"], agent)
        self.assertTrue(tool_calls, f"{agent} executed no tools")
        if agent != "code-explorer":
            self.assertIn("run_command", tool_calls, f"{agent} never called run_command: {tool_calls}")
        self.assertTrue(right(reply), f"{agent} wrong answer: {reply}")
        if agent == "mutation-tester":
            self.assertEqual(
                mutation_trace_problems(trace_entries, self.project),
                [],
                f"mutation-tester execution trace failed verification: {trace_entries}",
            )
        self.assertEqual(
            hashlib.sha256((self.project / "calc.py").read_bytes()).hexdigest(),
            before,
            f"{agent} left calc.py changed",
        )
        status = subprocess.run(
            ["git", "-C", str(self.project), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(status.stdout.strip(), "", f"{agent} left the tree changed: {status.stdout}")
        worktrees_after = subprocess.run(
            ["git", "-C", str(self.project), "worktree", "list", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(worktrees_after, worktrees_before, f"{agent} left an extra git worktree behind")

    def test_code_explorer_finds_the_function(self):
        self.known_answer("code-explorer")

    def test_git_runner_reads_the_last_commit(self):
        self.known_answer("git-runner")

    def test_test_runner_names_the_failing_test(self):
        self.known_answer("test-runner")

    def test_debug_evidence_quotes_the_assertion(self):
        self.known_answer("debug-evidence")

    def test_mutation_tester_mutates_reports_and_restores(self):
        self.known_answer("mutation-tester")


if __name__ == "__main__":
    unittest.main()
