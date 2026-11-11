"""Codex and the run guard: the Stop hook wrapper, the hook file's commands, and hook approval through Codex's own
app-server (stubbed here; the live run is D02 T01 §7)."""
import importlib.util
import itertools
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
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "kits" / "todo" / "templates"
STUB = REPO / "tests" / "fixtures" / "codex_app_server_stub.py"
SESSION = "11111111-2222-3333-4444-555555555555"
OTHER = "99999999-8888-7777-6666-555555555555"
RUN_FILE = "docs/phase-runs/2099-01-01-phase-0.md"
sys.path.insert(0, str(REPO))
import forge  # noqa: E402

FAKE_GRAPH = """import json, os, sys
if sys.argv[2:3] == ["stats"]:
    print(json.dumps({"total": 1, "verified": 0})); sys.exit(0)
n = int(open(os.path.join(os.path.dirname(__file__), 'ready.txt')).read())
print(json.dumps([{"ref": "D00 T01 \\u00a73", "title": "Probe row", "phase": 0}] * n))
"""


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_tree(args, *, input, cwd, shell=False, timeout=120, env=None):
    """Run a command whose own children (the hook, its graph call) must not outlive it: a new process group or
    session, and on a timeout the whole tree is ended (taskkill /T on Windows, the process group elsewhere)."""
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(args, shell=shell, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, **group)
    try:
        out, err = proc.communicate(input, timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    return subprocess.CompletedProcess(args, proc.returncode, out, err)


def alive(pid):
    """Whether a process id is still running, from the OS itself: OpenProcess and GetExitCodeProcess on Windows,
    signal 0 elsewhere. A process the call cannot inspect raises rather than reading as gone."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            error = ctypes.get_last_error()
            if error == 87:  # ERROR_INVALID_PARAMETER: no process has this id
                return False
            raise OSError(error, f"cannot inspect process {pid}")
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise OSError(ctypes.get_last_error(), f"cannot read the exit code of process {pid}")
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def end(pid):
    """Stop a process the test started, whatever its state (cleanup after a failed assertion)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


guard = load("codex_test_guard", TEMPLATES / "scripts" / "campaign_guard.py")
trust_tool = load("codex_test_trust", TEMPLATES / "scripts" / "codex-hook-trust.py")


class Project(unittest.TestCase):
    """A git repository holding the todo kit's Codex wiring, a stub graph and a run file."""

    folder = "codex project"  # a space in the path, as Windows user folders often have

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / self.folder
        for rel in ("scripts/campaign_guard.py", "scripts/codex-campaign-hook.py", "scripts/codex-hook-trust.py",
                    ".codex/hooks.json"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TEMPLATES / rel, self.root / rel)
        (self.root / "scripts/todo-graph.py").write_text(FAKE_GRAPH, encoding="utf-8")
        self.ready(1)
        (self.root / RUN_FILE).parent.mkdir(parents=True)
        (self.root / RUN_FILE).write_text("# Phase run\n\n## Critical events\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("build/\nscripts/ready.txt\n", encoding="utf-8")
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                     ["config", "commit.gpgsign", "false"], ["add", "-A"], ["commit", "-qm", "seed"]):
            subprocess.run(["git", *args], cwd=self.root, capture_output=True, check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def ready(self, n):
        (self.root / "scripts/ready.txt").write_text(str(n), encoding="utf-8")

    def acquire(self, session=SESSION):
        guard.acquire(str(self.root), session, 0, RUN_FILE, "job-1")

    def state(self):
        return guard._read_state(str(self.root))

    def payload(self, session=SESSION, **extra):
        return json.dumps({"session_id": session, "cwd": str(self.root), "hook_event_name": "Stop",
                           "stop_hook_active": False, **extra})


class Wrapper(Project):
    """`scripts/codex-campaign-hook.py` run as Codex runs it: a process with the payload on stdin."""

    def run_hook(self, payload, script=None, cwd=None):
        proc = run_tree([sys.executable, str(script or self.root / "scripts/codex-campaign-hook.py")],
                        input=payload, cwd=cwd or self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        return json.loads(proc.stdout)

    def test_a_guarded_session_is_held_with_block(self):
        self.acquire()
        decision = self.run_hook(self.payload())
        self.assertEqual(decision["decision"], "block")
        self.assertEqual(self.state()["blocks"], 1)
        # Antigravity's field never changes Codex's answer format.
        self.assertEqual(self.run_hook(self.payload(conversationId=SESSION))["decision"], "block")
        self.assertEqual(self.state()["blocks"], 2)

    def test_the_guards_lifecycle_holds_through_the_wrapper(self):
        self.assertEqual(self.run_hook(self.payload()), {}, "no guard held the stop")
        self.acquire()
        self.assertEqual(self.run_hook(self.payload(OTHER)), {}, "another session was held")
        for push in (1, 2, 3):
            self.assertEqual(self.run_hook(self.payload())["decision"], "block", push)
            self.assertEqual(self.state()["blocks"], push)
        self.assertEqual(self.run_hook(self.payload()), {}, "the breaker did not let the fourth stop through")
        self.assertEqual(self.state()["trips"], 1)
        self.ready(0)
        self.assertEqual(self.run_hook(self.payload()), {}, "a run with nothing ready was held")
        self.ready(1)
        (self.root / "notes.txt").write_text("progress\n", encoding="utf-8")
        self.assertEqual(self.run_hook(self.payload())["decision"], "block")
        run_id = guard.read_guard(str(self.root))["run_id"]
        with open(self.root / RUN_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"PARKED 2099-01-02T00:00:00Z run={run_id} blocked\n")
        self.assertEqual(self.run_hook(self.payload()), {}, "a parked run was held")

    def test_this_runs_closeout_releases_the_session(self):
        self.acquire()
        run_id = guard.read_guard(str(self.root))["run_id"]
        with open(self.root / RUN_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"\n## Closeout run={run_id}\n")
        self.assertEqual(self.run_hook(self.payload()), {})

    def test_every_failure_answers_empty_and_exits_zero(self):
        self.acquire()
        self.assertEqual(self.run_hook("x" * 2_000_001), {}, "an oversize payload")
        self.assertIn("over 2,000,000", guard.hook_error(str(self.root), SESSION))
        self.assertEqual(self.run_hook("{not json"), {}, "bytes that are not JSON")
        (self.root / "scripts/campaign_guard.py").write_text("raise RuntimeError('broken guard')\n", encoding="utf-8")
        self.assertEqual(self.run_hook(self.payload()), {}, "a guard that raises")
        (self.root / "scripts/campaign_guard.py").unlink()
        self.assertEqual(self.run_hook(self.payload()), {}, "a missing guard")

    def test_the_guard_is_loaded_by_its_path_from_any_folder(self):
        self.acquire()
        elsewhere = Path(self._tmp.name) / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "campaign_guard.py").write_text("raise SystemExit('the wrong guard')\n", encoding="utf-8")
        self.assertEqual(self.run_hook(self.payload(), cwd=elsewhere)["decision"], "block")


class HookFile(Project):
    """`.codex/hooks.json`: each command run through the shell, from the root and a subfolder, and where it must
    answer `{}`."""

    def command(self):
        hook = json.loads((self.root / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]
        return hook["commandWindows"] if os.name == "nt" else hook["command"]

    def shell(self, cwd, payload=None):
        proc = run_tree(self.command(), shell=True, input=payload or self.payload(), cwd=cwd)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_both_keys_name_the_wrapper(self):
        hook = json.loads((self.root / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]
        for key in ("command", "commandWindows"):
            self.assertIn("scripts/codex-campaign-hook.py", hook[key], key)
        self.assertEqual(hook["timeout"], 60)

    def test_the_command_holds_a_run_from_the_root_and_a_subfolder(self):
        self.acquire()
        sub = self.root / "sub folder"
        sub.mkdir()
        self.assertEqual(self.shell(self.root)["decision"], "block")
        self.assertEqual(self.shell(sub)["decision"], "block")

    def test_outside_git_or_without_the_wrapper_it_answers_empty(self):
        self.acquire()
        outside = Path(self._tmp.name) / "not a repository"
        outside.mkdir()
        self.assertEqual(self.shell(outside), {})
        (self.root / "scripts/codex-campaign-hook.py").unlink()
        self.assertEqual(self.shell(self.root), {})


def hook_entry(root, status="untrusted", index="0:0", source="project", command=None, event="stop"):
    path = str(root / ".codex" / "hooks.json")
    return {"key": f"{path}:{event}:{index}", "eventName": event, "source": source, "sourcePath": path,
            "command": command or "python -c \"... scripts/codex-campaign-hook.py ...\"",
            "currentHash": f"sha256:{'a' * 64}", "trustStatus": status}


class Trust(Project):
    """`scripts/codex-hook-trust.py` against a stub app-server answering recorded `hooks/list` results."""

    _scenarios = itertools.count()

    def scenario(self, *listings, silent=False):
        path = Path(self._tmp.name) / f"scenario-{next(self._scenarios)}.json"
        path.write_text(json.dumps({"listings": [{"data": [{"cwd": str(self.root), "hooks": hooks,
                                                            "errors": [], "warnings": []}]} for hooks in listings],
                                    "silent": silent}), encoding="utf-8")
        env = {"CODEX_HOOK_TRUST_SERVER": json.dumps([sys.executable, str(STUB)]), "CODEX_STUB_SCENARIO": str(path)}
        return path, mock.patch.dict(os.environ, env)

    def writes(self, path):
        log = path.with_name(path.name + ".writes.jsonl")
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []

    def test_only_the_campaign_stop_hook_is_approved(self):
        other_project = hook_entry(self.root, index="0:1", command="python scripts/lint.py")
        user = {**hook_entry(self.root), "source": "user", "sourcePath": "C:/Users/x/.codex/hooks.json"}
        path, env = self.scenario([hook_entry(self.root), other_project, user])
        with env:
            results = trust_tool.trust(self.root)
        self.assertEqual([r["approved"] for r in results], [True])
        writes = self.writes(path)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["keyPath"], "hooks.state")
        self.assertEqual(writes[0]["mergeStrategy"], "upsert")
        self.assertEqual(writes[0]["value"], {hook_entry(self.root)["key"]: {"trusted_hash": f"sha256:{'a' * 64}"}})

    def test_a_trusted_hook_is_not_rewritten_and_check_never_writes(self):
        path, env = self.scenario([hook_entry(self.root, "trusted")])
        with env:
            self.assertEqual(trust_tool.trust(self.root)[0]["approved"], False)
        path, env = self.scenario([hook_entry(self.root, "modified")])
        with env:
            self.assertEqual(trust_tool.trust(self.root, check=True)[0], {
                "key": hook_entry(self.root)["key"], "status": "modified", "enabled": True, "approved": False})
        self.assertEqual(self.writes(path), [])

    def test_a_project_codex_does_not_list_yet_is_trusted_then_its_hook(self):
        path, env = self.scenario([], [hook_entry(self.root)])
        with env:
            results = trust_tool.trust(self.root)
        self.assertEqual(results[0]["approved"], True)
        writes = self.writes(path)
        self.assertEqual(writes[0]["keyPath"], "projects")
        self.assertEqual(writes[0]["value"], {trust_tool.project_key(self.root): {"trust_level": "trusted"}})
        self.assertEqual(writes[1]["keyPath"], "hooks.state")
        path, env = self.scenario([])
        with env, self.assertRaisesRegex(trust_tool.TrustError, "no campaign Stop hook"):
            trust_tool.trust(self.root, check=True)
        self.assertEqual(self.writes(path), [], "a check trusted the project")

    def test_no_codex_or_no_answer_refuses(self):
        with mock.patch.dict(os.environ, {"CODEX_HOOK_TRUST_SERVER": ""}), \
                mock.patch.object(trust_tool.shutil, "which", return_value=None), \
                self.assertRaisesRegex(trust_tool.TrustError, "not installed"):
            trust_tool.trust(self.root)
        path, env = self.scenario([hook_entry(self.root)], silent=True)
        with env, mock.patch.object(trust_tool, "TIMEOUT", 2.0), \
                self.assertRaisesRegex(trust_tool.TrustError, "did not answer"):
            trust_tool.trust(self.root)

    def test_a_server_whose_launcher_exits_leaves_no_descendant_running(self):
        path = Path(self._tmp.name) / f"scenario-{next(self._scenarios)}.json"
        path.write_text(json.dumps({"spawn_and_exit": True}), encoding="utf-8")
        env = {"CODEX_HOOK_TRUST_SERVER": json.dumps([sys.executable, str(STUB)]), "CODEX_STUB_SCENARIO": str(path)}
        with mock.patch.dict(os.environ, env), mock.patch.object(trust_tool, "TIMEOUT", 3.0), \
                self.assertRaisesRegex(trust_tool.TrustError, "did not answer"):
            trust_tool.trust(self.root)
        child = int((path.parent / (path.name + ".child")).read_text())
        self.addCleanup(end, child)
        self.assertFalse(alive(child), f"the server's grandchild {child} outlived close()")

    @unittest.skipUnless(os.name == "nt", "the job object and the suspended start are Windows-only")
    def test_a_launcher_cannot_run_before_it_is_in_the_job(self):
        """The job is assigned a second late: a launcher started running would spawn and exit in that second."""
        real = trust_tool._kill_on_close_job

        def late(proc):
            time.sleep(1.0)
            return real(proc)

        with mock.patch.object(trust_tool, "_kill_on_close_job", late):
            self.test_a_server_whose_launcher_exits_leaves_no_descendant_running()

    @unittest.skipUnless(os.name == "nt", "the job object and the suspended start are Windows-only")
    def test_a_server_that_cannot_be_contained_or_resumed_is_never_left_running(self):
        started = []
        real_popen = trust_tool.subprocess.Popen

        def recording_popen(*args, **kwargs):
            proc = real_popen(*args, **kwargs)
            if str(STUB) in [str(part) for part in (args[0] if args else [])]:  # the server, not a taskkill
                started.append(proc)
                self.addCleanup(end, proc.pid)  # at once, so a failed assertion later still ends every server
            return proc

        path, env = self.scenario([hook_entry(self.root)])
        with env, mock.patch.object(trust_tool.subprocess, "Popen", recording_popen):
            with mock.patch.object(trust_tool, "_kill_on_close_job", return_value=None), \
                    self.assertRaisesRegex(trust_tool.TrustError, "job object"):
                trust_tool.trust(self.root)
            with mock.patch.object(trust_tool, "_resume", side_effect=OSError(5, "Access is denied")), \
                    self.assertRaisesRegex(OSError, "Access is denied"):
                trust_tool.trust(self.root)
        self.assertEqual(len(started), 2)
        for proc in started:
            self.assertIsNotNone(proc.poll(), f"server {proc.pid} was left running after a failed start")
            self.assertFalse(alive(proc.pid))
        self.assertEqual(self.writes(path), [])

    def test_the_command_line_prints_one_line_and_exits_2_on_a_refusal(self):
        path, env = self.scenario([hook_entry(self.root)], silent=True)
        script = self.root / "scripts/codex-hook-trust.py"
        environ = {**os.environ, "CODEX_HOOK_TRUST_SERVER": json.dumps([sys.executable, str(STUB)]),
                   "CODEX_STUB_SCENARIO": str(path)}
        path.write_text(json.dumps({"listings": [{"data": []}]}), encoding="utf-8")
        proc = run_tree([sys.executable, str(script), "--check"], input="", cwd=self.root, env=environ)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


class Doctor(Trust):
    """`forge.py doctor <project> todo`: the Codex wiring and its approval, as Codex reports it."""

    def checks(self):
        return {c["name"]: c for c in forge.doctor_repo(self.root, "todo")["checks"]}

    def test_approval_is_read_against_the_current_hash_at_any_index(self):
        for status, expected in (("trusted", "ok"), ("untrusted", "setup_required"), ("modified", "setup_required")):
            with self.subTest(status):
                _path, env = self.scenario([hook_entry(self.root, status)])
                with env:
                    check = self.checks()["stop-hook-approved:.codex"]
                self.assertEqual(check["status"], expected, check)
                if expected != "ok":
                    self.assertIn("codex-hook-trust.py", check["detail"])
        _path, env = self.scenario([hook_entry(self.root, "trusted", index="0:1")])
        with env:
            self.assertEqual(self.checks()["stop-hook-approved:.codex"]["status"], "ok")
        self.assertEqual(self.checks()["stop-hook:.codex"]["status"], "ok")

    def test_a_disabled_hook_is_reported_and_never_re_enabled_or_approved(self):
        path, env = self.scenario([{**hook_entry(self.root, "trusted"), "enabled": False}])
        with env:
            check = self.checks()["stop-hook-approved:.codex"]
        self.assertEqual(check["status"], "setup_required")
        self.assertIn("disabled in Codex", check["detail"])
        path, env = self.scenario([{**hook_entry(self.root, "untrusted"), "enabled": False}])
        with env:
            results = trust_tool.trust(self.root)
        self.assertEqual((results[0]["enabled"], results[0]["approved"]), (False, False))
        self.assertEqual(self.writes(path), [])

    def test_no_codex_folder_means_no_codex_check(self):
        shutil.rmtree(self.root / ".codex")
        names = set(self.checks())
        self.assertNotIn("stop-hook:.codex", names)
        self.assertNotIn("stop-hook-approved:.codex", names)


if __name__ == "__main__":
    unittest.main()
