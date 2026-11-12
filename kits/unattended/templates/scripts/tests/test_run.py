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
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "inside": os.environ.get("CONCLAVE_UNATTENDED_RUN")}) + "\\n")
if os.environ.get("STUB_RESUME_FAILS") and "--resume" in sys.argv:
    sys.exit(1)
if os.environ.get("STUB_EXIT"):
    print("stub agent: cannot start", flush=True)
    sys.exit(3)
child = subprocess.Popen([sys.executable, "-c",
                          "import signal, time; signal.signal(signal.SIGHUP, signal.SIG_IGN); time.sleep(300)"])
open(os.environ["STUB_CHILD"], "w").write(str(child.pid))
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
                argv = run.agent_command(self.root, {**PROFILE, "skip_permissions": skip}, "sid-1", resume=False)
                expected = ["claude", "--model", "claude-opus-5-5", "--effort", "high", "--session-id", "sid-1",
                            "--disallowedTools", "AskUserQuestion,EnterPlanMode,ExitPlanMode",
                            *(["--dangerously-skip-permissions"] if skip else []), "--", PROMPT]
                self.assertEqual(argv, expected)
        resumed = run.agent_command(self.root, PROFILE, "sid-1", resume=True)
        self.assertEqual(resumed[:7], ["claude", "--model", "claude-opus-5-5", "--effort", "high", "--resume",
                                       "sid-1"])
        self.assertEqual(resumed[-2:], ["--", run.RESUME_PROMPT])
        self.assertNotIn("--session-id", resumed)

    def test_another_agent_is_refused_until_its_command_exists(self):
        run = load_run_module()
        with self.assertRaises(run.RunError) as caught:
            run.agent_command(self.root, {**PROFILE, "agent": "codex"}, "sid", resume=False)
        self.assertIn("§6", str(caught.exception))


@needs_tmux
class RunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.root = base / "repo"
        self.bin = base / "bin"
        self.bin.mkdir()
        stub = self.bin / "claude"
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
        if self.child_file.exists():
            try:
                os.kill(int(self.child_file.read_text()), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass  # already gone

    def launcher(self, *args, env=None):
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

    def acquire(self, session):
        (self.root / "docs" / "phase-runs").mkdir(parents=True, exist_ok=True)
        run_file = self.root / "docs" / "phase-runs" / "run.md"
        if not run_file.exists():  # a run file is committed, as process-plan commits it
            run_file.write_text("# Run\n", encoding="utf-8")
            git(self.root, "add", "-A")
            git(self.root, "commit", "-qm", "run file")
        done = subprocess.run([sys.executable, str(self.root / "scripts" / "campaign_guard.py"), "acquire",
                               "--session", session, "--phase", "2", "--run-file", "docs/phase-runs/run.md",
                               "--cron-id", "job-1", "--generation", "g1", "--root", str(self.root)],
                              capture_output=True, text=True, timeout=60)
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

    def wait_child(self):
        deadline = time.monotonic() + 15
        while not self.child_file.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        return int(self.child_file.read_text())

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
        for rel in ("build/claude-campaign-guard.json", "build/unattended-run.json", "build/unattended-launch.json"):
            self.assertFalse((self.root / rel).exists(), rel)

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
                run.start(self.root, out=open(os.devnull, "w"))
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
                run.start(self.root, out=open(os.devnull, "w"))
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
        self.assertIn("the crashed session's guard ended", done.stdout)
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

    def test_a_run_cannot_stop_itself(self):
        self.assertEqual(self.launcher("start").returncode, 0)
        done = self.launcher("stop", env={**self.env, "CONCLAVE_UNATTENDED_RUN": "1"})
        self.assertEqual(done.returncode, 2)
        self.assertIn("refused inside the run", done.stdout)
        self.assertTrue(self.tmux_has("demo-run"))
        self.assertTrue((self.root / "build" / "unattended-run.json").exists())


class WindowsTest(unittest.TestCase):
    def test_windows_is_told_to_use_wsl(self):
        run = load_run_module()
        with unittest.mock.patch.object(run.os, "name", "nt"), \
                unittest.mock.patch.object(run.sys, "stderr", new_callable=lambda: __import__("io").StringIO()) as err:
            self.assertEqual(run.main(["status"]), 1)
        self.assertIn("run this in WSL", err.getvalue())


if __name__ == "__main__":
    unittest.main()
