"""`forge.py doctor <project> reviewer` checks the flags and settings the dispatcher passes to the Antigravity CLI
against the installed CLI (D00 T02 §2), with a stub `agy` standing in for it."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge  # noqa: E402  the SDK's own CLI, imported after the path insert as tests/test_forge.py does

DISPATCHER = ROOT / "kits/reviewer/templates/scripts/review-dispatch.py"
spec = importlib.util.spec_from_file_location("dispatch_for_flags", DISPATCHER)
assert spec is not None and spec.loader is not None
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)

# What `agy --help` printed for these flags on 1.5.8 (2026-11-13), with a neighbour (`--print`) that is not one of them.
HELP = """Usage of agy.exe:
  --model                         Model for the current CLI session
  -p                              Short alias for --print
  --print                         Run a single prompt non-interactively and print the response
  --print-timeout                 Optional time limit for print mode; 0 waits until the turn completes (default 0s)
  --sandbox                       Run in a sandbox with terminal restrictions enabled
  --settings                      Settings for this session only, never saved: a JSON object of settings.json keys
"""

# The stub CLI: its behaviour comes from the file `mode` beside it.
STUB = r'''import os, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__))
mode = open(os.path.join(here, "mode")).read().strip()
args = sys.argv[1:]
HELP = open(os.path.join(here, "help.txt")).read()
if mode == "stray":
    # A grandchild whose parent has gone: `taskkill /T` no longer reaches it, and it holds this stub's output pipe.
    mid = subprocess.Popen([sys.executable, "-c", "import subprocess, sys; print(subprocess.Popen([sys.executable, "
                            "'-c', 'import time; time.sleep(120)']).pid, flush=True)"], stdout=subprocess.PIPE)
    stray = mid.stdout.readline().decode().strip()
    mid.wait()
    open(os.path.join(here, "pids"), "w").write(stray)
    time.sleep(60)
if mode == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    open(os.path.join(here, "pids"), "w").write(f"{os.getpid()} {child.pid}")
    time.sleep(60)
if "--version" in args:
    if mode == "version-fails":
        sys.exit(4)
    if mode == "version-hangs":
        time.sleep(60)
    print("9.9.9")
elif "--help" in args:
    print(HELP.replace("  --print-timeout", "  --print-limit") if mode == "renamed" else HELP)
    sys.exit(3 if mode == "help-fails" else 0)
elif "--settings" in args:
    assert os.path.isfile(args[args.index("--settings") + 1])
    open(os.path.join(here, "settings-seen"), "w").write(open(args[args.index("--settings") + 1]).read())
    if mode == "rejects-settings":
        sys.stderr.write('Error: --settings: unknown setting "permissions"\n')
        sys.exit(1)
    if mode == "agents-fails":
        sys.stderr.write("Failed to start: open installation_id: Access is denied.\n")
        sys.exit(1)
    print("No agents.")
'''


def alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class FlagList(unittest.TestCase):
    def test_the_captured_help_lists_every_flag(self):
        self.assertEqual(dispatch.agy_flags_missing(HELP), [])

    def test_a_renamed_flag_is_missing_and_a_longer_neighbour_does_not_stand_in(self):
        self.assertEqual(dispatch.agy_flags_missing(HELP.replace("  --print-timeout", "  --print-limit")),
                         ["--print-timeout"])
        # `--print` is listed, `--print-timeout` is not: a prefix is not the flag.
        self.assertEqual(dispatch.agy_flags_missing("\n".join(l for l in HELP.splitlines() if "--print-timeout" not in l)),
                         ["--print-timeout"])
        self.assertEqual(dispatch.agy_flags_missing(HELP.replace("  -p  ", "  -q  ")), ["-p"])

    def test_a_flag_the_help_lacks_is_reported_when_the_dispatcher_starts_passing_it(self):
        with mock.patch.object(dispatch, "AGY_FLAGS", (*dispatch.AGY_FLAGS, "--read-only")):
            self.assertEqual(dispatch.agy_flags_missing(HELP), ["--read-only"])

    def test_the_command_is_built_from_the_flags(self):
        argv, stdin = dispatch.command({"cli": "agy", "model": "gemini-4-carbon-medium"}, "/usr/bin/agy", "short",
                                       Path("/p.md"), Path("/tmp/x/last-message.md"), 60)
        self.assertIsNone(stdin)
        self.assertEqual(argv, ["/usr/bin/agy", "--model", "gemini-4-carbon-medium", "--sandbox", "--settings",
                                str(Path("/tmp/x/agy-settings.json")), "--print-timeout", "60s", "-p=short"])
        self.assertEqual([a.split("=")[0] for a in argv if a.startswith("-")], list(dispatch.AGY_FLAGS))


class DoctorCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # A folder with a space in its name, as "C:\\Program Files" has: the wrapper's own path needs quoting.
        self.dir = Path(self._tmp.name) / "agy home"
        self.dir.mkdir()
        (self.dir / "stub.py").write_text(STUB, encoding="utf-8")
        (self.dir / "help.txt").write_text(HELP, encoding="utf-8")
        if os.name == "nt":
            self.agy = self.dir / "agy.cmd"
            self.agy.write_text(f'@"{sys.executable}" "{self.dir / "stub.py"}" %*\r\n', encoding="utf-8")
        else:
            self.agy = self.dir / "agy"
            self.agy.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{self.dir / "stub.py"}" "$@"\n', encoding="utf-8")
            self.agy.chmod(0o755)
        self.mode("ok")

    def tearDown(self):
        for attempt in range(50):  # a killed process releases its files a moment after it is reaped (Windows)
            try:
                self._tmp.cleanup()
                return
            except PermissionError:
                if attempt == 49:
                    raise
                time.sleep(0.1)

    def mode(self, name):
        (self.dir / "mode").write_text(name, encoding="utf-8")

    def check(self):
        return forge._agy_flags_check(dispatch, str(self.agy))

    def test_a_cli_with_every_flag_that_accepts_the_settings_is_ok_with_its_version(self):
        status, detail = self.check()
        self.assertEqual(status, "ok", detail)
        self.assertIn("9.9.9", detail)
        self.assertEqual((self.dir / "settings-seen").read_text(),
                         '{"permissions": {"deny": ["write_file(*)", "edit_file(*)", "mcp(*)"]}}')
        self.assertEqual(list(Path(tempfile.gettempdir()).glob("forge-agy-settings-*")), [], "the scratch file is gone")

    def test_a_renamed_flag_is_unexpected_and_names_it(self):
        self.mode("renamed")
        status, detail = self.check()
        self.assertEqual(status, "unexpected")
        self.assertIn("no longer lists --print-timeout", detail)

    def test_a_cli_that_lists_every_flag_but_rejects_the_settings_is_unexpected(self):
        self.mode("rejects-settings")
        status, detail = self.check()
        self.assertEqual(status, "unexpected")
        self.assertIn('Error: --settings: unknown setting "permissions"', detail)
        self.assertEqual(list(Path(tempfile.gettempdir()).glob("forge-agy-settings-*")), [])

    def test_a_help_that_exits_non_zero_is_never_ok_though_it_lists_every_flag(self):
        self.mode("help-fails")
        self.assertEqual(self.check(), ("unexpected", f"{self.agy} --help exited 3"))

    def test_a_cli_that_cannot_start_is_setup_required_with_the_reason(self):
        status, detail = forge._agy_flags_check(dispatch, str(self.dir / "no-such-agy.exe"))
        self.assertEqual(status, "setup_required")
        self.assertIn("could not start", detail)

    def test_a_wrapper_and_a_settings_file_under_paths_with_spaces_both_work(self):
        spaced = self.dir / "temp files"
        spaced.mkdir()
        with mock.patch.object(tempfile, "tempdir", str(spaced)):
            status, detail = self.check()
        self.assertEqual(status, "ok", detail)
        self.assertIn(" ", str(self.agy))
        self.assertEqual((self.dir / "settings-seen").read_text(),
                         '{"permissions": {"deny": ["write_file(*)", "edit_file(*)", "mcp(*)"]}}')

    def test_a_version_probe_that_fails_is_never_ok(self):
        self.mode("version-fails")
        self.assertEqual(self.check(), ("unexpected", f"{self.agy} --version exited 4 and named no version"))
        self.mode("version-hangs")
        with mock.patch.object(forge, "PROBE_SECONDS", 3):
            status, detail = self.check()
        self.assertEqual((status, detail), ("setup_required", f"{self.agy} --version: no answer within 3 seconds"))

    def test_an_interrupted_probe_ends_its_tree_before_the_interrupt_passes_on(self):
        self.mode("hang")
        real = subprocess.Popen.communicate
        calls = []

        def interrupted(proc, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:  # the wait for the answer: Ctrl+C arrives here
                for _ in range(100):
                    if (self.dir / "pids").exists():
                        break
                    time.sleep(0.1)
                raise KeyboardInterrupt
            return real(proc, *args, **kwargs)

        with mock.patch.object(subprocess.Popen, "communicate", interrupted), self.assertRaises(KeyboardInterrupt):
            forge._probe([str(self.agy), "--help"])
        pids = [int(p) for p in (self.dir / "pids").read_text().split()]
        for _ in range(50):
            if not any(alive(p) for p in pids):
                break
            time.sleep(0.1)
        self.assertEqual([p for p in pids if alive(p)], [], "the probe outlived the interrupt")

    def test_a_cli_that_hangs_is_setup_required_and_its_whole_tree_is_ended(self):
        self.mode("hang")
        with mock.patch.object(forge, "PROBE_SECONDS", 4):
            started = time.monotonic()
            status, detail = self.check()
        self.assertEqual(status, "setup_required")
        self.assertIn("no answer within 4 seconds", detail)
        self.assertLess(time.monotonic() - started, 30)
        pids = [int(p) for p in (self.dir / "pids").read_text().split()]
        for _ in range(50):
            if not any(alive(p) for p in pids):
                break
            time.sleep(0.1)
        self.assertEqual([p for p in pids if alive(p)], [], "the stub or its child outlived the probe")

    def path_with_only_the_stub(self):
        extra = {"PATHEXT": ".CMD;.EXE"} if os.name == "nt" else {}
        return mock.patch.dict(os.environ, {"PATH": str(self.dir), **extra})

    def test_doctor_shows_the_check_for_an_antigravity_reviewer_only(self):
        project = self.dir / "project"
        project.mkdir()
        forge.apply_kit(project, "reviewer")
        with self.path_with_only_the_stub():
            checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual(checks["reviewer-flags:carbon"], "ok")
        self.assertNotIn("reviewer-flags:astra", checks)
        self.assertEqual(checks["reviewer:astra"], "setup_required")  # codex not on this PATH: no flags check for it

    def test_doctor_probes_the_cli_on_path_not_one_in_the_working_directory(self):
        # Found by Antigravity's review of D00 T02 §2: shutil.which looks in the working directory first on Windows.
        project = self.dir / "project"
        project.mkdir()
        forge.apply_kit(project, "reviewer")
        name = "agy.cmd" if os.name == "nt" else "agy"
        decoy = project / name
        decoy.write_text("@exit 9\r\n" if os.name == "nt" else "#!/bin/sh\nexit 9\n", encoding="utf-8")
        decoy.chmod(0o755)
        cwd = os.getcwd()
        try:
            os.chdir(project)
            # Whatever this Python's shutil.which would answer (it differs by version and by environment), doctor
            # must not ask it: here it names the decoy, as it does on Windows from the working directory.
            real = forge.shutil.which

            def which(cli, mode=os.F_OK | os.X_OK, path=None):
                # A search of the caller's own choosing is the real one (the dispatcher's lookup on POSIX);
                # the default search is the one that finds the decoy.
                return str(decoy) if path is None else real(cli, mode, path)

            with self.path_with_only_the_stub(), mock.patch.object(forge.shutil, "which", which):
                checks = {c["name"]: c for c in forge.doctor_repo(project, "reviewer")["checks"]}
        finally:
            os.chdir(cwd)
        self.assertEqual(checks["reviewer-flags:carbon"]["status"], "ok", checks["reviewer-flags:carbon"])

    def test_two_antigravity_reviewers_on_one_cli_are_probed_once(self):
        project = self.dir / "project"
        project.mkdir()
        forge.apply_kit(project, "reviewer")
        pin = project / ".conclave/reviewers.toml"
        pin.write_text(pin.read_text(encoding="utf-8").replace(
            "[routes]", '[reviewers.argon]\ncli = "agy"\nmodel = "gemini-4-argon-medium"\n\n[routes]', 1), encoding="utf-8")
        calls = []
        real = forge._agy_flags_check
        with self.path_with_only_the_stub(), \
                mock.patch.object(forge, "_agy_flags_check", lambda *a: calls.append(a[1]) or real(*a)):
            checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual((checks["reviewer-flags:carbon"], checks["reviewer-flags:argon"]), ("ok", "ok"))
        self.assertEqual(len(calls), 1)

    def test_a_settings_probe_that_fails_for_another_reason_is_not_called_a_refusal(self):
        self.mode("agents-fails")
        status, detail = self.check()
        self.assertEqual(status, "unexpected")
        self.assertIn("agents exited 1: Failed to start: open installation_id: Access is denied.", detail)
        self.assertNotIn("refuses", detail)

    def test_a_stray_process_holding_the_pipe_does_not_hold_the_probe(self):
        self.mode("stray")

        def end_stray():
            pids = self.dir / "pids"
            for pid in (pids.read_text().split() if pids.exists() else []):  # the stub's own record of what it started
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    try:
                        os.kill(int(pid), 9)
                    except ProcessLookupError:
                        pass

        self.addCleanup(end_stray)
        started = time.monotonic()
        code, _, problem = forge._probe([str(self.agy), "--help"], timeout=3)
        self.assertEqual((code, problem), (None, "no answer within 3 seconds"))
        self.assertLess(time.monotonic() - started, 30, "the cleanup wait is bounded")

    def test_cleanup_does_not_wait_forever_on_a_pipe_a_stray_process_holds(self):
        self.mode("hang")
        real = subprocess.Popen.communicate
        waits = []

        def communicate(proc, *args, **kwargs):
            if "taskkill" in str(proc.args):
                return real(proc, *args, **kwargs)
            waits.append(kwargs.get("timeout"))
            if len(waits) == 2:  # the wait after the tree is ended: a stray holder keeps the pipe open
                raise subprocess.TimeoutExpired(proc.args, kwargs.get("timeout"))
            return real(proc, *args, **kwargs)

        with mock.patch.object(subprocess.Popen, "communicate", communicate):
            code, _, problem = forge._probe([str(self.agy), "--help"], timeout=3)
        self.assertEqual((code, problem), (None, "no answer within 3 seconds"))
        self.assertEqual(waits[1], 5, "the cleanup wait is bounded")


if __name__ == "__main__":
    unittest.main()
