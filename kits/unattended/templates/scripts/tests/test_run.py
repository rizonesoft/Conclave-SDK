"""Tests of `scripts/unattended-run.py`: start, resume, status, attach and stop a run held in tmux.

They run real tmux on a private server (TMUX_TMPDIR in a temporary folder), never the operator's own sessions, a
real preflight against a seeded project, and a stub `claude` that records its arguments and starts a child.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

SCRIPTS = Path(__file__).resolve().parents[1]
TEMPLATES = SCRIPTS.parent
IN_KIT = TEMPLATES.name == "templates" and TEMPLATES.parent.name == "unattended"
TODO = TEMPLATES.parent.parent / "todo" / "templates" if IN_KIT else TEMPLATES
HAS_TMUX = os.name == "posix" and shutil.which("tmux") is not None
needs_tmux = unittest.skipUnless(HAS_TMUX, "the run lives in tmux: Linux or WSL with tmux installed")

PROFILE = {"schema_version": 1, "name": "demo", "agent": "claude", "model": "claude-opus-5-5", "effort": "high",
           "prompt_file": "docs/unattended-prompt.md", "branch": "main", "skip_permissions": True, "tools": [],
           "min_disk_gb": 1, "min_ram_gb": 1, "tick_seconds": 300, "idle_minutes": 45, "stall_hours": 6,
           "preflight": []}
PROMPT = "Run the plan to the end.\n"
# The stub agent: records its arguments, starts a child that ignores SIGHUP (as a detached tool would, so only the
# process-group kill ends it), then waits. With STUB_RESUME_FAILS set, a --resume exits at once.
STUB = '''#!/usr/bin/env python3
import json, os, signal, subprocess, sys, time
NAME = os.path.basename(sys.argv[0])
if sys.argv[1:] == ["--version"]:
    print(os.environ.get("STUB_VERSION") or {"claude": "2.1.322 (Claude Code)", "codex": "codex-cli 0.166.0", "agy": "1.5.5"}[NAME])
    sys.exit(0)
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps({"cli": NAME, "argv": sys.argv[1:], "inside": os.environ.get("CONCLAVE_UNATTENDED_RUN"),
                          "tag": os.environ.get("CONCLAVE_UNATTENDED_TAG")}) + "\\n")
RESUMING = any(a in ("--resume", "resume") or a.startswith("--conversation=") for a in sys.argv[1:])
if os.environ.get("STUB_RESUME_FAILS") and RESUMING:
    sys.exit(1)
if os.environ.get("STUB_EXIT"):
    print("stub agent: cannot start", flush=True)
    sys.exit(3)
# The first child scrubs its environment, as some tools do, so it carries no run tag: only the process-group kill
# reaches it. The second leaves the group by starting its own session: only the tag reaches it.
child = subprocess.Popen([sys.executable, "-c",
                          "import signal, time; signal.signal(signal.SIGHUP, signal.SIG_IGN); time.sleep(300)"],
                         env={"PATH": os.environ.get("PATH", "")})
open(os.environ["STUB_CHILD"], "w").write(str(child.pid))
# A second child in its own session, as the review dispatcher detaches its reviewers: outside the agent's group.
detached = subprocess.Popen([sys.executable, "-c",
                             "import signal, time; signal.signal(signal.SIGHUP, signal.SIG_IGN); time.sleep(300)"],
                            start_new_session=True)
open(os.environ["STUB_CHILD"] + ".detached", "w").write(str(detached.pid))
signal.signal(signal.SIGHUP, signal.SIG_IGN)
time.sleep(300)
'''


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=60)


def gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def load_run_module():
    spec = importlib.util.spec_from_file_location("unattended_run", SCRIPTS / "unattended-run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AttachCommandTest(unittest.TestCase):
    def test_each_form(self):
        run = load_run_module()
        self.assertEqual(run.attach_command("demo-run", False), ["tmux", "attach-session", "-t", "=demo-run"])
        self.assertEqual(run.attach_command("demo-run", True), ["tmux", "attach-session", "-r", "-t", "=demo-run"])


class CommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "unattended-prompt.md").write_text(PROMPT, encoding="utf-8")

    def test_the_claude_command_from_the_profile(self):
        run = load_run_module()
        for skip in (True, False):
            with self.subTest(skip_permissions=skip):
                argv = run.agent_command(self.root, {**PROFILE, "skip_permissions": skip}, "sid-1", None)
                expected = ["claude", "--model", "claude-opus-5-5", "--effort", "high", "--session-id", "sid-1",
                            "--disallowedTools", "AskUserQuestion,EnterPlanMode,ExitPlanMode",
                            *(["--dangerously-skip-permissions"] if skip else []), "--", PROMPT]
                self.assertEqual(argv, expected)
        resumed = run.agent_command(self.root, PROFILE, "sid-1", "sid-1")
        self.assertEqual(resumed[:7], ["claude", "--model", "claude-opus-5-5", "--effort", "high", "--resume",
                                       "sid-1"])
        self.assertEqual(resumed[-2:], ["--", run.RESUME_PROMPT])
        self.assertNotIn("--session-id", resumed)

    CLAUDE_ONLY = ("--session-id", "--resume", "--disallowedTools", "--effort", "--dangerously-skip-permissions")

    def test_the_codex_command_from_the_profile(self):
        run = load_run_module()
        codex = {**PROFILE, "agent": "codex", "model": "gpt-6-astra", "effort": "xhigh"}
        for skip in (True, False):
            with self.subTest(skip_permissions=skip):
                profile = {**codex, "skip_permissions": skip}
                bypass = ["--dangerously-bypass-approvals-and-sandbox"] if skip else []
                options = ["-m", "gpt-6-astra", "-c", 'model_reasoning_effort="xhigh"', *bypass]
                self.assertEqual(run.agent_command(self.root, profile, "tag-1", None), ["codex", *options, "--", PROMPT])
                self.assertEqual(run.agent_command(self.root, profile, "tag-1", "thread-9"),
                                 ["codex", "resume", *options, "--", "thread-9", run.RESUME_PROMPT])
                for argv in (run.agent_command(self.root, profile, "tag-1", None),
                             run.agent_command(self.root, profile, "tag-1", "thread-9")):
                    self.assertFalse([a for a in argv if a in self.CLAUDE_ONLY], argv)
                    self.assertNotIn("tag-1", argv, "Codex chooses its own session id")

    def test_the_antigravity_command_from_the_profile(self):
        run = load_run_module()
        agy = {**PROFILE, "agent": "agy", "model": "gemini-4-argon", "effort": "max"}
        for skip in (True, False):
            with self.subTest(skip_permissions=skip):
                profile = {**agy, "skip_permissions": skip}
                bypass = ["--dangerously-skip-permissions"] if skip else []
                self.assertEqual(run.agent_command(self.root, profile, "tag-1", None),
                                 ["agy", "--model=gemini-4-argon", "--effort=max", *bypass,
                                  f"--prompt-interactive={PROMPT}"])
                self.assertEqual(run.agent_command(self.root, profile, "tag-1", "conv-7"),
                                 ["agy", "--model=gemini-4-argon", "--effort=max", "--conversation=conv-7", *bypass,
                                  f"--prompt-interactive={run.RESUME_PROMPT}"])
                argv = run.agent_command(self.root, profile, "tag-1", None)
                self.assertFalse([a for a in argv if a in ("--session-id", "--resume", "--disallowedTools")], argv)


@needs_tmux
class RunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.root = base / "repo"
        self.bin = base / "bin"
        self.bin.mkdir()
        for cli in ("claude", "codex", "agy"):
            stub = self.bin / cli
            stub.write_text(STUB, encoding="utf-8")
            stub.chmod(0o755)
        self.log = base / "stub.jsonl"
        self.child_file = base / "child.pid"
        tmux_dir = base / "tmux"
        tmux_dir.mkdir()
        self.env = {**{k: v for k, v in os.environ.items() if k != "TMUX"},
                    "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "TMUX_TMPDIR": str(tmux_dir),
                    "STUB_LOG": str(self.log), "STUB_CHILD": str(self.child_file), "CONCLAVE_STARTUP_GRACE": "2"}
        patch = unittest.mock.patch.dict(os.environ, self.env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.end_everything)
        for rel in ("scripts/lib/unattended.py", "scripts/unattended-preflight.py", "scripts/unattended-run.py"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TEMPLATES / rel, self.root / rel)
        for rel in ("scripts/campaign_guard.py", "scripts/codex-campaign-hook.py", "scripts/codex-hook-trust.py",
                    ".claude/settings.json"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TODO / rel, self.root / rel)
        (self.root / ".conclave").mkdir()
        self.write_profile()
        (self.root / "docs").mkdir()
        (self.root / "docs" / "unattended-prompt.md").write_text(PROMPT, encoding="utf-8")
        (self.root / ".gitignore").write_text("build/\n", encoding="utf-8")
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                     ["config", "commit.gpgsign", "false"], ["add", "-A"], ["commit", "-qm", "fixture"]):
            git(self.root, *args)

    def write_profile(self, **changes):
        (self.root / ".conclave" / "unattended.json").write_text(json.dumps({**PROFILE, **changes}),
                                                                 encoding="utf-8")

    def end_everything(self):
        subprocess.run(["tmux", "kill-server"], capture_output=True, timeout=30)
        for path in (self.child_file, Path(str(self.child_file) + ".detached")):
            if path.exists():
                try:
                    os.kill(int(path.read_text()), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass  # already gone

    def launcher(self, *args, env=None, heartbeat=False):
        # These tests drive one start at a time; the heartbeat's own tests (HeartbeatRunTest) leave it running.
        if args[:1] == ("start",) and not heartbeat:
            args = (*args, "--no-heartbeat")
        return subprocess.run([sys.executable, str(self.root / "scripts" / "unattended-run.py"), *args],
                              capture_output=True, text=True, timeout=600, env=env or self.env)

    def tmux_has(self, name):
        return subprocess.run(["tmux", "has-session", "-t", f"={name}"], capture_output=True,
                              timeout=30).returncode == 0

    def calls(self, at_least=1):
        """The stub's recorded calls, once it has made `at_least` of them: the agent starts after the launcher returns."""
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            lines = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
            if len(lines) >= at_least:
                break
            time.sleep(0.1)
        return [json.loads(line) for line in lines]

    def acquire(self, session, tag=None):
        (self.root / "docs" / "phase-runs").mkdir(parents=True, exist_ok=True)
        run_file = self.root / "docs" / "phase-runs" / "run.md"
        if not run_file.exists():  # a run file is committed, as process-plan commits it
            run_file.write_text("# Run\n", encoding="utf-8")
            git(self.root, "add", "-A")
            git(self.root, "commit", "-qm", "run file")
        done = subprocess.run([sys.executable, str(self.root / "scripts" / "campaign_guard.py"), "acquire",
                               "--session", session, "--phase", "2", "--run-file", "docs/phase-runs/run.md",
                               "--cron-id", "job-1", "--generation", "g1", "--root", str(self.root)],
                              capture_output=True, text=True, timeout=60,
                              env={**self.env, **({"CONCLAVE_UNATTENDED_TAG": tag} if tag else {})})
        self.assertEqual(done.returncode, 0, done.stderr)

    def guard(self):
        path = self.root / "build" / "claude-campaign-guard.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def run_module(self):
        spec = importlib.util.spec_from_file_location("installed_run", self.root / "scripts" / "unattended-run.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def marker(self):
        return json.loads((self.root / "build" / "unattended-run.json").read_text(encoding="utf-8"))

    def wait_child(self, detached=False):
        path = Path(str(self.child_file) + ".detached") if detached else self.child_file
        deadline = time.monotonic() + 15
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        return int(path.read_text())

    def wait_gone(self, pid, seconds=15):
        deadline = time.monotonic() + seconds
        while not gone(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        return gone(pid)

    def test_start_runs_the_agent_in_tmux_that_outlives_the_launcher(self):
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PASS profile", done.stdout)
        # The launcher has exited; the run is still there.
        self.assertTrue(self.tmux_has("demo-run"))
        marker = self.marker()
        claim = json.loads((self.root / "build" / "unattended-launch.json").read_text(encoding="utf-8"))
        self.assertEqual((marker["tmux_session"], marker["agent"], marker["resumed"]), ("demo-run", "claude", False))
        self.assertEqual((claim["session"], claim["tmux_session"], claim["pid"]),
                         (marker["session"], "demo-run", marker["pgid"]))
        call = self.calls()[0]
        self.assertEqual(call["argv"][call["argv"].index("--session-id") + 1], marker["session"])
        self.assertEqual(call["argv"][-1], PROMPT)
        self.assertEqual(call["inside"], "1")
        limit = subprocess.run(["tmux", "show-options", "-v", "-t", "=demo-run:", "history-limit"],
                               capture_output=True, text=True, timeout=30).stdout.strip()
        self.assertEqual(limit, "50000")
        again = self.launcher("start")
        self.assertEqual(again.returncode, 1)
        self.assertIn("already running", again.stderr)

    def test_an_agent_cli_older_than_the_recorded_flags_starts_nothing(self):
        # Completion review of D02 T02 §6: the version refusal was tested in the preflight alone.
        self.use_codex()
        done = self.launcher("start", env={**self.env, "STUB_VERSION": "codex-cli 0.150.1"})
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("FAIL version codex: 0.150.1, older than 0.166.0", done.stdout)
        self.assertIn("nothing was started", done.stdout)
        self.assertFalse(self.log.exists(), "the agent was started")
        self.assertFalse(self.tmux_has("demo-run"))
        self.assertFalse((self.root / "build" / "unattended-run.json").exists())

    def test_a_failed_preflight_starts_nothing(self):
        (self.root / "dirty.txt").write_text("x", encoding="utf-8")
        done = self.launcher("start")
        self.assertEqual(done.returncode, 1)
        self.assertIn("FAIL git-clean", done.stdout)
        self.assertIn("nothing was started", done.stdout)
        self.assertFalse(self.tmux_has("demo-run"))
        self.assertFalse((self.root / "build" / "unattended-run.json").exists())

    def test_a_dead_run_is_resumed_and_a_resume_that_fails_starts_fresh(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        first = self.marker()["session"]
        self.calls(1)  # the agent has started before its session is killed
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual((self.marker()["session"], self.marker()["resumed"]), (first, True))
        resumed = self.calls(2)[-1]["argv"]
        self.assertEqual(resumed[resumed.index("--resume") + 1], first)
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        env = {**self.env, "STUB_RESUME_FAILS": "1"}
        done = self.launcher("start", env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("did not stay up (the agent exited 1", done.stdout)
        self.assertIn("starting a fresh session", done.stdout)
        fresh = self.marker()
        self.assertNotEqual(fresh["session"], first)
        self.assertFalse(fresh["resumed"])
        calls = self.calls(4)  # the first start, the resume, the failed resume and the fresh start
        self.assertEqual(len(calls), 4, [c["argv"][4:6] for c in calls])
        self.assertIn("--resume", calls[2]["argv"])
        self.assertEqual(calls[3]["argv"][calls[3]["argv"].index("--session-id") + 1], fresh["session"])

    def test_status_for_a_live_and_a_stopped_run(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        lines = dict(line.split(": ", 1) for line in self.launcher("status").stdout.splitlines())
        self.assertTrue(lines["run"].startswith("live"))
        self.assertEqual(lines["session"], self.marker()["session"])
        self.assertEqual(lines["guard"], "none")
        self.assertEqual(lines["health"], "none")
        self.assertEqual(self.launcher("stop").returncode, 0)
        lines = dict(line.split(": ", 1) for line in self.launcher("status").stdout.splitlines())
        self.assertTrue(lines["run"].startswith("stopped"))
        self.assertEqual(lines["session"], "none")

    def test_stop_ends_the_guard_the_sessions_and_the_whole_group(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        session = self.marker()["session"]
        child = self.wait_child()
        detached = self.wait_child(detached=True)
        self.acquire(session)
        subprocess.run(["tmux", "new-session", "-d", "-s", "demo-heartbeat", "sleep 300"], check=True, timeout=30)
        done = self.launcher("stop")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("guard ended", done.stdout)
        self.assertFalse(self.tmux_has("demo-run"))
        self.assertFalse(self.tmux_has("demo-heartbeat"))
        deadline = time.monotonic() + 15
        while not gone(child) and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertTrue(gone(child), "the agent's child outlived the stop")
        self.assertTrue(self.wait_gone(detached), "a child in its own session outlived the stop")
        for rel in ("build/claude-campaign-guard.json", "build/unattended-run.json", "build/unattended-launch.json"):
            self.assertFalse((self.root / rel).exists(), rel)

    def test_a_resume_ends_the_crashed_runs_leftovers_first(self):
        # Round 1 of D02 T02 §5: the old processes survived a lost tmux session and ran beside the resumed agent.
        self.assertEqual(self.launcher("start").returncode, 0)
        old_child, old_detached = self.wait_child(), self.wait_child(detached=True)
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        time.sleep(0.5)
        self.assertFalse(gone(old_child), "the stub's child should outlive the tmux session (it ignores SIGHUP)")
        self.child_file.unlink()
        Path(str(self.child_file) + ".detached").unlink()
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(self.wait_gone(old_child), "the crashed run's child ran on beside the resumed run")
        self.assertTrue(self.wait_gone(old_detached), "the crashed run's detached child ran on")

    def test_a_guard_that_does_not_end_keeps_the_runs_state(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        self.acquire(self.marker()["session"])
        run = self.run_module()
        refused = subprocess.CompletedProcess([], 2, stdout="", stderr="campaign-guard: the guard lock timed out")
        out = __import__("io").StringIO()
        with unittest.mock.patch.object(run, "_end_guard", return_value=refused):
            self.assertEqual(run.stop(self.root, out), 1)
        self.assertIn("guard not ended", out.getvalue())
        self.assertTrue((self.root / "build" / "unattended-run.json").exists(), "the marker was dropped")
        self.assertTrue((self.root / "build" / "unattended-launch.json").exists(), "the claim was dropped")
        done = self.launcher("stop")  # the second stop finds the session again and ends the guard
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIsNone(self.guard())

    def test_a_preflight_that_overruns_is_ended_with_its_children(self):
        # Round 1 of D02 T02 §5: a fixed 900 s limit killed the preflight alone and raised TimeoutExpired.
        run = self.run_module()
        fake = Path(self._tmp.name) / "fake-scripts"
        fake.mkdir()
        pid_file = Path(self._tmp.name) / "preflight-child.pid"
        (fake / "unattended-preflight.py").write_text(
            "import subprocess, sys, time\n"
            "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
            f"open({str(pid_file)!r}, 'w').write(str(c.pid))\n"
            "print('PASS profile: slow', flush=True)\n"
            "time.sleep(120)\n", encoding="utf-8")
        with unittest.mock.patch.object(run, "HERE", fake), \
                unittest.mock.patch.object(run, "PREFLIGHT_SLACK_SECONDS", 2):
            code, report = run.run_preflight(self.root, None, PROFILE)
        self.assertEqual(code, 1)
        self.assertIn("PASS profile: slow", report)
        self.assertIn("FAIL preflight: ran past 2s", report)
        self.assertTrue(self.wait_gone(int(pid_file.read_text())), "the preflight's child outlived it")
        limit_profile = {**PROFILE, "preflight": [{"name": "build", "command": ["true"], "timeout_seconds": 1800}]}
        with unittest.mock.patch.object(run.subprocess, "Popen", side_effect=RuntimeError("stop here")) as popen:
            with self.assertRaises(RuntimeError):
                run.run_preflight(self.root, None, limit_profile)
        self.assertEqual(popen.call_count, 1)

    def test_a_fallback_whose_old_guard_cannot_be_ended_starts_nothing(self):
        # Completion review of D02 T02 §5: the fresh session started anyway and the marker lost its owner.
        self.assertEqual(self.launcher("start").returncode, 0)
        first = self.marker()["session"]
        self.calls(1)
        self.acquire(first)
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        run = self.run_module()
        refused = subprocess.CompletedProcess([], 2, stdout="", stderr="campaign-guard: the guard lock timed out")
        with unittest.mock.patch.dict(os.environ, {"STUB_RESUME_FAILS": "1"}), \
                unittest.mock.patch.object(run, "_end_guard", return_value=refused):
            with self.assertRaises(run.RunError) as caught:
                run.start(self.root, out=open(os.devnull, "w"), supervise=False)
        self.assertIn("could not be ended", str(caught.exception))
        self.assertFalse(self.tmux_has("demo-run"), "a fresh session started beside the crashed run's guard")
        self.assertEqual(self.marker()["session"], first, "the marker lost the crashed session")
        self.assertEqual(self.guard()["session_id"], first)

    def test_a_cancelled_preflight_ends_its_detached_profile_check(self):
        # Completion review of D02 T02 §5: profile checks run in sessions of their own, outside the preflight's group.
        pids = Path(self._tmp.name) / "check.pids"
        check = ("import os, subprocess, sys, time; "
                 "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)']); "
                 f"open({str(pids)!r}, 'w').write(f'{{os.getpid()}} {{c.pid}}'); time.sleep(300)")
        profile = {**PROFILE, "preflight": [{"name": "build", "command": [sys.executable, "-c", check],
                                             "timeout_seconds": 60}]}
        self.write_profile(**profile)
        git(self.root, "commit", "-qam", "a slow check")
        run = self.run_module()
        with unittest.mock.patch.object(run, "PREFLIGHT_SLACK_SECONDS", -50):  # a 10 s limit, under the check's 60
            code, report = run.run_preflight(self.root, None, profile)
        self.assertEqual(code, 1)
        self.assertIn("FAIL preflight: ran past 10s", report)
        check_pid, child_pid = (int(p) for p in pids.read_text().split())
        self.assertTrue(self.wait_gone(check_pid), "the detached profile check outlived its preflight")
        self.assertTrue(self.wait_gone(child_pid), "the profile check's child outlived its preflight")
    def test_an_agent_that_exits_at_once_is_reported_and_leaves_nothing(self):
        done = self.launcher("start", env={**self.env, "STUB_EXIT": "1"})
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("the agent exited 3", done.stderr)
        self.assertIn("stub agent: cannot start", done.stderr)
        self.assertFalse(self.tmux_has("demo-run"))
        for rel in ("build/unattended-run.json", "build/unattended-launch.json"):
            self.assertFalse((self.root / rel).exists(), rel)

    def test_a_state_write_that_fails_ends_the_run_it_started(self):
        run = self.run_module()
        with unittest.mock.patch.object(run.lib, "write_claim", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(run.RunError) as caught:
                run.start(self.root, out=open(os.devnull, "w"), supervise=False)
        self.assertIn("could not be written", str(caught.exception))
        self.assertFalse(self.tmux_has("demo-run"))
        self.assertTrue(gone(self.wait_child()), "the started agent's child outlived the failed start")
        self.assertFalse((self.root / "build" / "unattended-run.json").exists())

    def test_a_tmux_failure_leaves_no_session(self):
        run = self.run_module()
        real = run.tmux

        def failing(*args, check=False):
            if args[0] == "new-window":
                raise run.RunError("tmux new-window failed: injected")
            return real(*args, check=check)
        with unittest.mock.patch.object(run, "tmux", failing):
            with self.assertRaises(run.RunError):
                run.start(self.root, out=open(os.devnull, "w"), supervise=False)
        self.assertFalse(self.tmux_has("demo-run"))
        self.assertFalse((self.root / "build" / "unattended-run.json").exists())

    def test_a_resume_keeps_the_crashed_runs_guard_and_a_fresh_start_ends_it(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        first = self.marker()["session"]
        self.calls(1)
        self.acquire(first)  # the crashed run held its guard
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PASS campaign-guard", done.stdout)
        self.assertEqual(self.guard()["session_id"], first, "the resumed run keeps its guard")
        self.calls(2)
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        done = self.launcher("start", env={**self.env, "STUB_RESUME_FAILS": "1"})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("the crashed run's guard ended", done.stdout)
        self.assertIsNone(self.guard(), "a fresh session cannot take the crashed one's guard, so it was ended")
        self.assertNotEqual(self.marker()["session"], first)

    def test_stop_under_the_lock_once_then_a_no_op(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        holder = subprocess.Popen([sys.executable, "-c", (
            "import importlib.util, time\n"
            f"spec = importlib.util.spec_from_file_location('u', {str(self.root / 'scripts/lib/unattended.py')!r})\n"
            "u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)\n"
            f"with u.launch_lock({str(self.root)!r}):\n"
            "    print('held', flush=True); time.sleep(60)\n")], stdout=subprocess.PIPE, text=True)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        refused = self.launcher("stop")
        holder.kill()
        holder.wait()
        holder.stdout.close()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("unattended-launch.lock", refused.stderr)
        self.assertTrue(self.tmux_has("demo-run"), "a stop beside a launch must change nothing")
        self.assertEqual(self.launcher("stop").returncode, 0)
        again = self.launcher("stop")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("with no marker", again.stdout)

    def test_stop_keeps_another_sessions_guard_and_follows_the_marker_over_a_renamed_profile(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        self.acquire("someone-else")
        self.write_profile(name="renamed")
        git(self.root, "commit", "-qam", "rename")
        done = self.launcher("stop")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("belongs to session someone-else", done.stdout)
        self.assertEqual(self.guard()["session_id"], "someone-else")
        self.assertFalse(self.tmux_has("demo-run"), "stop followed the profile's new name, not the run's")

    def test_status_shows_the_recorded_values_and_an_unknown_state(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        marker = self.marker()
        self.acquire(marker["session"])
        lines = dict(line.split(": ", 1) for line in self.launcher("status").stdout.splitlines())
        self.assertEqual(lines["started"], marker["started"])
        guard = self.guard()
        self.assertEqual(lines["guard"], f"phase 2, run {guard['run_id']}, session {marker['session']}")
        run = self.run_module()
        out = __import__("io").StringIO()
        with unittest.mock.patch.object(run.lib, "tmux_session_exists", return_value=None):
            run.status(self.root, out)
        self.assertIn("run: unknown (tmux could not be asked)", out.getvalue())

    def test_attach_to_an_absent_session_is_refused(self):
        done = self.launcher("attach", "--watch")
        self.assertEqual(done.returncode, 1)
        self.assertIn("is not running", done.stderr)

    def use_codex(self):
        self.write_profile(agent="codex", model="gpt-6-astra", effort="xhigh")
        (self.root / ".codex").mkdir(exist_ok=True)
        shutil.copyfile(TODO / ".codex/hooks.json", self.root / ".codex/hooks.json")
        # Codex's approval of the hook goes through its app-server, which test_codex_hook.py drives against a stub
        # server; here the trust script reports the hook trusted, as it does once Codex has approved it.
        (self.root / "scripts" / "codex-hook-trust.py").write_text(
            "print('codex-hook-trust: trusted: .codex/hooks.json:stop:0:0')\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "a codex run")

    def test_a_codex_run_is_tagged_resumed_by_its_guards_session_and_stopped(self):
        # D02 T02 §6: Codex chooses its own session id; the guard it acquires carries the run's tag.
        self.use_codex()
        self.assertEqual(self.launcher("start").returncode, 0)
        marker = self.marker()
        self.assertIsNone(marker["agent_session"])
        first = self.calls(1)[0]
        self.assertEqual((first["cli"], first["tag"]), ("codex", marker["session"]))
        self.acquire("codex-thread-1", tag=marker["session"])  # the hook inside the run, with Codex's own id
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        resumed = self.calls(2)[-1]["argv"]
        self.assertEqual(resumed[:2], ["resume", "-m"])
        self.assertEqual(resumed[resumed.index("--") + 1], "codex-thread-1")
        self.assertEqual((self.marker()["session"], self.marker()["agent_session"]), (marker["session"],
                                                                                       "codex-thread-1"))
        done = self.launcher("stop")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("guard ended", done.stdout)
        self.assertIsNone(self.guard())

    def test_a_codex_run_without_a_guard_starts_fresh_and_leaves_another_runs_guard(self):
        self.use_codex()
        self.assertEqual(self.launcher("start").returncode, 0)
        tag = self.marker()["session"]
        self.calls(1)
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        done = self.launcher("start")  # the agent died before it took a guard: nothing to resume
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        fresh = self.calls(2)[-1]["argv"]
        self.assertNotEqual(fresh[0], "resume")
        self.assertNotEqual(self.marker()["session"], tag)
        self.acquire("someone-else", tag="another-run")
        done = self.launcher("stop")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.guard()["session_id"], "someone-else", "stop ended another run's guard")

    def test_a_marker_from_before_agent_session_still_stops_its_run(self):
        # Round 1 of D02 T02 §6: a §5 marker (no agent_session) became unreadable, and stop lost the run's group.
        self.assertEqual(self.launcher("start").returncode, 0)
        child = self.wait_child()
        path = self.root / "build" / "unattended-run.json"
        old = json.loads(path.read_text(encoding="utf-8"))
        del old["agent_session"]
        path.write_text(json.dumps(old), encoding="utf-8")
        marker, problem = self.run_module().read_marker(self.root)
        self.assertIsNone(problem)
        self.assertEqual(marker["agent_session"], old["session"])
        done = self.launcher("stop")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(self.wait_gone(child), "stop lost the old marker's process group")

    def test_a_run_whose_profile_changed_agent_starts_that_agent_fresh(self):
        # Round 1 of D02 T02 §6: a crashed Claude Code run was resumed as `codex resume <Claude's session id>`.
        self.assertEqual(self.launcher("start").returncode, 0)
        first = self.marker()["session"]
        self.calls(1)
        self.acquire(first)
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        self.use_codex()
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("the profile now names codex", done.stdout)
        self.assertIn("the crashed run's guard ended", done.stdout)
        call = self.calls(2)[-1]
        self.assertEqual(call["cli"], "codex")
        self.assertNotIn("resume", call["argv"])
        self.assertNotIn(first, call["argv"])
        self.assertIsNone(self.guard())
    def test_an_antigravity_run_starts_with_its_prompt(self):
        self.write_profile(agent="agy", model="gemini-4-argon", effort="high")
        git(self.root, "commit", "-qam", "an antigravity run")
        (self.root / ".agents").mkdir(exist_ok=True)
        shutil.copyfile(TODO / ".agents/hooks.json", self.root / ".agents/hooks.json")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "the antigravity hook")
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        call = self.calls(1)[0]
        self.assertEqual(call["cli"], "agy")
        self.assertEqual(call["argv"][-1], f"--prompt-interactive={PROMPT}")

    def test_start_leaves_one_heartbeat_that_restarts_a_killed_agent_and_stop_removes_it(self):
        # Plan review of D02 T02 §7: an ordinary start must leave a detached heartbeat that recovers the run unaided.
        self.write_profile(tick_seconds=1)
        git(self.root, "commit", "-qam", "a one-second tick")
        done = self.launcher("start", heartbeat=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("heartbeat running in tmux session demo-heartbeat", done.stdout)
        self.calls(1)
        for round_ in (1, 2):
            pgid = self.marker()["pgid"]
            subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and len(self.calls(0)) < round_ + 1:
                time.sleep(0.5)
            self.assertEqual(len(self.calls(round_ + 1)), round_ + 1, "the heartbeat did not restart the run")
            pane = subprocess.run(["tmux", "capture-pane", "-p", "-J", "-S", "-80", "-t", "=demo-heartbeat:"],
                                  capture_output=True, text=True, timeout=30).stdout
            self.assertIn("--resume", self.calls(round_ + 1)[-1]["argv"], pane[-3000:])
            # The restart is done once the marker names the new agent; killing it sooner kills it inside its
            # startup check, which (rightly) reads as a resume that did not stay up.
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and self.marker()["pgid"] == pgid:
                time.sleep(0.2)
        deadline = time.monotonic() + 30
        while not self.tmux_has("demo-run") and time.monotonic() < deadline:
            time.sleep(0.2)
        sessions = subprocess.run(["tmux", "ls", "-F", "#{session_name}"], capture_output=True, text=True,
                                  timeout=30).stdout.split()
        self.assertEqual(sorted(sessions), ["demo-heartbeat", "demo-run"], "exactly one heartbeat, one run")
        self.assertEqual(self.launcher("stop").returncode, 0)
        self.assertFalse(self.tmux_has("demo-heartbeat"))
        self.assertFalse(self.tmux_has("demo-run"))

    def test_a_restart_for_a_run_that_was_stopped_starts_nothing(self):
        # Plan review of D02 T02 §7: a stop during the backoff must not be undone by the restart.
        self.assertEqual(self.launcher("start").returncode, 0)
        tag = self.marker()["session"]
        self.assertEqual(self.launcher("stop").returncode, 0)
        run = self.run_module()
        out = __import__("io").StringIO()
        self.assertEqual(run.start(self.root, out, expect=tag, supervise=False), run.FINISHED)
        self.assertIn("was stopped or replaced", out.getvalue())
        self.assertFalse(self.tmux_has("demo-run"))
        self.assertFalse((self.root / "build" / "unattended-run.json").exists())

    def test_a_crashed_runs_unfinished_edit_survives_its_resume(self):
        # Plan review of D02 T02 §7: the clean-tree check refused to resume a run killed mid-edit.
        self.assertEqual(self.launcher("start").returncode, 0)
        self.calls(1)
        edited = self.root / "docs" / "unattended-prompt.md"
        edited.write_text(PROMPT + "An edit the run had not committed.\n", encoding="utf-8")
        subprocess.run(["tmux", "kill-session", "-t", "=demo-run"], timeout=30)
        done = self.launcher("start")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("kept for the resumed run", done.stdout)
        self.assertTrue(self.marker()["resumed"])
        self.assertIn("An edit the run had not committed.", edited.read_text(encoding="utf-8"))

    def test_a_run_cannot_stop_itself(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        done = self.launcher("stop", env={**self.env, "CONCLAVE_UNATTENDED_RUN": "1"})
        self.assertEqual(done.returncode, 2)
        self.assertIn("refused inside the run", done.stdout)
        self.assertTrue(self.tmux_has("demo-run"))
        self.assertTrue((self.root / "build" / "unattended-run.json").exists())


class HeartbeatTickTest(unittest.TestCase):
    """The heartbeat's decisions, with an injected clock, a fake restart and tmux answers, on any system."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".conclave").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "docs" / "unattended-prompt.md").write_text(PROMPT, encoding="utf-8")
        (self.root / ".conclave" / "unattended.json").write_text(json.dumps(PROFILE), encoding="utf-8")
        self.run = load_run_module()
        self.marker = {"session": "tag-1", "agent_session": "tag-1", "tmux_session": "demo-run",
                       "heartbeat_session": "demo-heartbeat", "agent": "claude", "pgid": 4242,
                       "started": "2026-11-12T00:00:00Z", "resumed": False}
        self.write_marker()
        self.alive = False
        self.restarts = []
        self.out = __import__("io").StringIO()
        patch = unittest.mock.patch.object(self.run, "_alive", lambda name: self.alive)
        patch.start()
        self.addCleanup(patch.stop)

    def write_marker(self):
        (self.root / "build").mkdir(exist_ok=True)
        (self.root / "build" / "unattended-run.json").write_text(json.dumps(self.marker), encoding="utf-8")

    def restart(self, code=0, error=None):
        def go():
            self.restarts.append(1)
            if error:
                raise error
            return code
        return go

    def tick(self, now, state, **kwargs):
        return self.run.tick(self.root, now, state, self.out, **kwargs)

    def test_restarts_wait_300_600_then_1200_seconds(self):
        state = self.run.read_state(self.root)
        waits, now = [], 0.0
        for _ in range(3):
            self.tick(now, state, restart=self.restart())
            waits.append(state["wait_until"] - now)
            self.assertEqual(self.restarts.count(1), len(waits) - 1, "restarted before the wait")
            now = state["wait_until"]
            self.tick(now, state, restart=self.restart())  # the wait is over: restart
            now += 1
        self.assertEqual(waits, [300, 600, 1200])
        self.assertEqual((len(self.restarts), state["deaths"]), (3, 3))

    def test_the_wait_is_capped_at_an_hour(self):
        self.assertEqual([self.run.backoff(PROFILE, d) for d in range(4)], [300, 600, 1200, 2400])
        self.assertEqual(self.run.backoff(PROFILE, 4), 3600, "300 * 16 = 4800 is over the hour, so it is capped")
        self.assertEqual(self.run.backoff(PROFILE, 5), 3600)
        self.assertEqual(self.run.backoff(PROFILE, 9), 3600)

    def test_an_hour_alive_after_a_restart_resets_the_deaths(self):
        self.alive = True
        state = {**self.run.read_state(self.root), "deaths": 3, "last_restart": 1000.0}
        self.tick(1000.0 + 3599, state)
        self.assertEqual(state["deaths"], 3)
        self.tick(1000.0 + 3600, state)
        self.assertEqual(state["deaths"], 0)

    def test_a_failed_restart_counts_as_a_death_keeps_supervising_and_is_recorded(self):
        state = {**self.run.read_state(self.root), "wait_until": 0.0}
        self.assertEqual(self.tick(10.0, state, restart=self.restart(error=self.run.RunError("preflight FAIL"))), 0)
        self.assertEqual(state["deaths"], 1)
        self.assertIn("preflight FAIL", state["last_error"])
        self.assertEqual(state["wait_until"], 10.0 + 600)
        self.assertEqual(self.tick(10.0 + 600, state, restart=self.restart(code=1)), 0)
        self.assertEqual((state["deaths"], state["last_error"]), (2, "start exited 1"))
        self.tick(10.0 + 600 + 1200, state, restart=self.restart())
        self.assertEqual((state["deaths"], state["last_error"], state["wait_until"]), (3, None, None))

    def test_a_run_its_agent_ended_is_finished_and_another_runs_end_is_not(self):
        (self.root / "build" / "claude-campaign-ended.json").write_text(
            json.dumps({"launch_tag": "other-run", "session_id": "other", "reason": "park"}), encoding="utf-8")
        state = self.run.read_state(self.root)
        self.assertEqual(self.tick(0.0, state, restart=self.restart()), 0, "another run's end ended this one")
        (self.root / "build" / "claude-campaign-ended.json").write_text(
            json.dumps({"launch_tag": "tag-1", "session_id": "tag-1", "reason": "closeout"}), encoding="utf-8")
        with unittest.mock.patch.object(self.run.lib, "clear_claim", return_value="cleared"), \
                unittest.mock.patch.object(self.run.lib, "launch_lock", return_value=__import__("contextlib").nullcontext()):
            self.assertEqual(self.tick(1.0, state, restart=self.restart()), self.run.FINISHED)
        self.assertFalse((self.root / "build" / "unattended-run.json").exists(), "a finished run kept its marker")

    def test_a_run_that_never_took_its_guard_is_not_finished(self):
        state = self.run.read_state(self.root)
        self.assertEqual(self.tick(0.0, state, restart=self.restart()), 0)
        self.assertNotIn("ended itself", self.out.getvalue())

    def test_no_marker_ends_the_heartbeat(self):
        (self.root / "build" / "unattended-run.json").unlink()
        self.assertEqual(self.tick(0.0, self.run.read_state(self.root)), self.run.FINISHED)

    def test_the_state_is_read_back_on_every_tick(self):
        clock = iter([0.0, 100.0])
        restart = unittest.mock.patch.object(self.run, "start", side_effect=AssertionError("restarted early"))
        with restart:
            self.run.heartbeat(self.root, once=True, clock=lambda: next(clock), out=self.out)
            saved = json.loads((self.root / "build" / "unattended-heartbeat.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["wait_until"], 300.0)
            self.run.heartbeat(self.root, once=True, clock=lambda: next(clock), out=self.out)  # a new heartbeat
        self.assertEqual(json.loads((self.root / "build" / "unattended-heartbeat.json").read_text())["wait_until"],
                         300.0, "a recreated heartbeat forgot its deadline")

    def test_it_writes_its_state_file_and_nothing_else(self):
        before = set(p.name for p in (self.root / "build").iterdir())
        clock = iter(float(i) for i in range(50))
        for _ in range(50):
            self.run.heartbeat(self.root, once=True, clock=lambda: next(clock), out=self.out)
        after = set(p.name for p in (self.root / "build").iterdir())
        self.assertEqual(after - before, {"unattended-heartbeat.json"})

    def nudge(self, activity_age, clients, state=None, now=10_000.0):
        sent = []

        def tmux(*args, check=False):
            if args[0] == "display-message":
                return subprocess.CompletedProcess(args, 0, stdout=f"{int(now - activity_age)}\n", stderr="")
            if args[0] == "list-clients":
                return subprocess.CompletedProcess(args, 0, stdout="".join(f"{c}\n" for c in clients), stderr="")
            if args[0] == "send-keys":
                sent.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        self.alive = True
        state = state if state is not None else self.run.read_state(self.root)
        with unittest.mock.patch.object(self.run, "tmux", tmux):
            self.tick(now, state)
        return sent, state

    def test_an_idle_run_is_nudged_and_an_active_one_is_not(self):
        idle = PROFILE["idle_minutes"] * 60
        sent, _ = self.nudge(idle, [])
        self.assertEqual(sent[0][-1], self.run.NUDGE_PROMPT)
        self.assertEqual(self.nudge(idle - 1, [])[0], [])

    def test_an_operator_typing_suppresses_the_nudge_and_a_watcher_does_not(self):
        idle = PROFILE["idle_minutes"] * 60
        self.assertEqual(self.nudge(idle, ["0"])[0], [], "a nudge went to a run an operator is attached to")
        self.assertTrue(self.nudge(idle, ["1"])[0], "a read-only watcher suppressed the nudge")

    def test_a_nudge_is_sent_at_most_once_per_idle_minutes(self):
        idle = PROFILE["idle_minutes"] * 60
        sent, state = self.nudge(idle, [], now=10_000.0)
        self.assertTrue(sent)
        self.assertEqual(self.nudge(idle * 3, [], state=state, now=10_000.0 + idle - 1)[0], [])
        self.assertTrue(self.nudge(idle * 3, [], state=state, now=10_000.0 + idle)[0])


class WindowsTest(unittest.TestCase):
    def test_windows_is_told_to_use_wsl(self):
        run = load_run_module()
        with unittest.mock.patch.object(run.os, "name", "nt"), \
                unittest.mock.patch.object(run.sys, "stderr", new_callable=lambda: __import__("io").StringIO()) as err:
            self.assertEqual(run.main(["status"]), 1)
        self.assertIn("run this in WSL", err.getvalue())


if __name__ == "__main__":
    unittest.main()
