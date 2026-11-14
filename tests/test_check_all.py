"""`forge.py check-all` runs every suite the repository holds (D01 T02 §1), proven here on stub suites."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge  # noqa: E402  the SDK's own CLI, imported after the path insert as tests/test_forge.py does

# A stub suite that starts a child (detached when --detach is given), records both PIDs and sleeps past any timeout a test gives it.
HANG = r'''import os, subprocess, sys, time
extra = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {"start_new_session": True}
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"], **(extra if "--detach" in sys.argv else {}))
open(sys.argv[1], "w").write(f"{os.getpid()} {child.pid}")
if "--leave" in sys.argv:
    sys.exit(0)  # the suite ends and its child lives on, holding the output pipe
time.sleep(600)
'''
# A unittest folder with one plain test and one that runs only under CONCLAVE_FULL_TESTS.
GATED = r'''import os, unittest


class Gated(unittest.TestCase):
    def test_plain(self):
        pass

    @unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "the full run only")
    def test_full_only(self):
        open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "full-ran"), "w").close()
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


class Stubs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name).resolve()

    def command(self, name, code, timeout=30):
        """A command suite whose script is `code`; `{marker}` in it is a file the script can write."""
        script = self.dir / f"{name}.py"
        script.write_text(code.replace("{marker}", (self.dir / f"{name}.ran").as_posix()), encoding="utf-8")
        return {"name": name, "kind": "command", "path": script.name, "timeout": timeout,
                "argv": [sys.executable, "-B", script.name]}

    def passing(self, name):
        return self.command(name, 'open("{marker}", "w").close()\nprint("fine")\n')

    def failing(self, name):
        return self.command(name, 'import sys\nopen("{marker}", "w").close()\nprint("AssertionError: 2 != 3")\nsys.exit(1)\n')

    def hanging(self, name, timeout=3):
        suite = self.command(name, HANG, timeout)
        suite["argv"].append(str(self.dir / f"{name}.pids"))
        self.addCleanup(self.end_recorded, self.dir / f"{name}.pids")
        return suite

    @staticmethod
    def end_recorded(path):
        """Whatever the test found, nothing a stub started is left running: the PIDs are the stub's own record."""
        if not path.exists():
            return
        for pid in path.read_text().split():
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                try:
                    os.kill(int(pid), 9)
                except ProcessLookupError:
                    pass

    def unittest_folder(self, name, body):
        folder = self.dir / name
        folder.mkdir()
        if body is not None:
            (folder / "test_stub.py").write_text(body, encoding="utf-8")
        return {"name": name, "kind": "unittest", "path": name, "timeout": 60,
                "argv": [sys.executable, "-B", "-m", "unittest", "discover", "-s", name]}

    def ran(self, name):
        return (self.dir / f"{name}.ran").exists()

    def run_all(self, suites, **kwargs):
        return forge.check_all(suites=suites, root=self.dir, **kwargs)

    def pids(self, name):
        deadline = time.monotonic() + 20
        path = self.dir / f"{name}.pids"
        while time.monotonic() < deadline:
            if path.exists() and len(path.read_text().split()) == 2:
                return [int(pid) for pid in path.read_text().split()]
            time.sleep(0.1)
        self.fail("the stub suite never recorded its PIDs")

    def assert_gone(self, pids):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and any(alive(pid) for pid in pids):
            time.sleep(0.2)
        self.assertEqual([pid for pid in pids if alive(pid)], [])


class Runner(Stubs):
    def test_a_passing_suite_and_a_failing_one_whose_last_lines_are_kept(self):
        good, bad = self.run_all([self.passing("good"), self.failing("bad")])
        self.assertEqual((good["passed"], good["exit"], good["reason"]), (True, 0, ""))
        self.assertEqual((bad["passed"], bad["exit"], bad["reason"]), (False, 1, "exit 1"))
        self.assertIn("AssertionError: 2 != 3", bad["tail"])
        self.assertGreaterEqual(bad["seconds"], 0)

    def test_a_noisy_suite_keeps_only_the_end_of_its_output(self):
        noisy = self.command("noisy", 'import sys\nfor i in range(60000):\n    print("line", i, "x" * 60)\n'
                                      'print("THE FAILURE")\nsys.exit(1)\n')
        (result,) = self.run_all([noisy])
        lines = result["tail"].splitlines()
        self.assertLessEqual(len(lines), forge.TAIL_LINES)
        self.assertLessEqual(len(result["tail"].encode()), forge.TAIL_BYTES)
        self.assertEqual(lines[-1], "THE FAILURE")
        self.assertIn("line 59999", result["tail"])
        self.assertNotIn("line 100 ", result["tail"])

    def test_one_very_long_line_is_cut_to_the_byte_limit(self):
        long = self.command("long", 'import sys\nsys.stdout.write("y" * 500000 + "END")\nsys.exit(1)\n')
        (result,) = self.run_all([long])
        self.assertLessEqual(len(result["tail"].encode()), forge.TAIL_BYTES)
        self.assertTrue(result["tail"].endswith("END"))

    def test_streaming_output_without_newlines_stays_bounded_in_memory(self):
        stream = self.command("stream",
                              'import sys\nchunk = b"y" * 65536\n'
                              'for _ in range(256):\n    sys.stdout.buffer.write(chunk)\n'
                              'sys.stdout.buffer.write(b"END")\nsys.stdout.buffer.flush()\nsys.exit(1)\n')
        was_tracing = tracemalloc.is_tracing()
        if not was_tracing:
            tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            (result,) = self.run_all([stream])
            _, peak = tracemalloc.get_traced_memory()
        finally:
            if not was_tracing:
                tracemalloc.stop()
        self.assertEqual(result["exit"], 1)
        self.assertLessEqual(len(result["tail"].encode()), forge.TAIL_BYTES)
        self.assertTrue(result["tail"].endswith("END"))
        self.assertLess(peak, 2 * 1024 * 1024, f"streaming 16 MB peaked at {peak} bytes instead of bounded tail storage")

    def test_a_suite_that_cannot_start_fails_by_name_and_the_next_still_runs(self):
        missing = {"name": "missing", "kind": "command", "path": "x", "timeout": 30,
                   "argv": [str(self.dir / "no-such-program"), "x"]}
        first, second = self.run_all([missing, self.passing("after")])
        self.assertFalse(first["passed"])
        self.assertTrue(first["reason"].startswith("could not start: "), first["reason"])
        self.assertIsNone(first["exit"])
        self.assertTrue(second["passed"] and self.ran("after"))

    def test_a_unittest_suite_that_ran_no_test_fails(self):
        empty, after = self.run_all([self.unittest_folder("empty", None), self.passing("after")])
        self.assertEqual((empty["passed"], empty["reason"], empty["tests"]), (False, "no tests ran", 0))
        self.assertIn(empty["exit"], (0, 5))  # Python 3.12+ exits 5; older Pythons exit 0
        self.assertTrue(after["passed"] and self.ran("after"))

        zero_exit5 = self.unittest_folder("zero_exit5", GATED)
        zero_exit5["argv"] = [sys.executable, "-c", 'import sys; print("Ran 0 tests in 0.000s"); sys.exit(5)']
        r5, after5 = self.run_all([zero_exit5, self.passing("after5")])
        self.assertEqual((r5["passed"], r5["exit"], r5["tests"], r5["reason"]), (False, 5, 0, "no tests ran"))
        self.assertTrue(after5["passed"] and self.ran("after5"))

        quiet = self.unittest_folder("quiet", GATED)
        quiet["argv"] = [sys.executable, "-c", "pass"]  # exits 0 and reports no test
        (result,) = self.run_all([quiet])
        self.assertEqual((result["passed"], result["exit"], result["reason"]), (False, 0, "no tests ran"))

        crash = self.unittest_folder("crash", GATED)
        crash["argv"] = [sys.executable, "-c", "import sys; sys.exit(2)"]  # nonzero exit without Ran count stays exit 2
        (result,) = self.run_all([crash])
        self.assertEqual((result["passed"], result["exit"], result["tests"], result["reason"]),
                         (False, 2, None, "exit 2"))

    def test_a_failure_and_a_timeout_are_each_followed_by_the_next_suite(self):
        results = self.run_all([self.failing("bad"), self.passing("second"), self.hanging("slow"), self.passing("last")])
        self.assertEqual([r["passed"] for r in results], [False, True, False, True])
        self.assertEqual(results[2]["reason"], "timed out after 3 seconds")
        self.assertTrue(self.ran("second") and self.ran("last"))

    def test_a_timeout_ends_the_suite_and_the_child_it_started(self):
        (result,) = self.run_all([self.hanging("slow")])
        self.assertEqual((result["passed"], result["exit"]), (False, None))
        self.assert_gone(self.pids("slow"))

    def test_a_child_that_outlives_its_suite_does_not_hold_the_run(self):
        leaver = self.hanging("leaver", timeout=60)
        leaver["argv"].append("--leave")
        started = time.monotonic()
        first, second = self.run_all([leaver, self.passing("after")])
        self.assertLess(time.monotonic() - started, 30, "the wait for the held pipe is bounded")
        self.assertEqual((first["passed"], first["exit"], second["passed"]), (True, 0, True))
        self.assert_gone(self.pids("leaver"))

    def test_an_interruption_ends_the_tree_and_passes_on(self):
        def interrupted(proc, timeout):
            self.pids("slow")  # the suite and its child are running
            raise KeyboardInterrupt

        with mock.patch.object(forge, "_wait", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.run_all([self.hanging("slow", timeout=60), self.passing("never")])
        self.assert_gone(self.pids("slow"))
        self.assertFalse(self.ran("never"))

    def test_an_interruption_during_reader_startup_ends_the_tree_and_passes_on(self):
        def interrupted_start(thread_self):
            self.pids("startup")  # the suite and its child are running before _wait is entered
            raise KeyboardInterrupt

        with mock.patch("threading.Thread.start", interrupted_start):
            with self.assertRaises(KeyboardInterrupt):
                self.run_all([self.hanging("startup", timeout=60), self.passing("never")])
        self.assert_gone(self.pids("startup"))
        self.assertFalse(self.ran("never"))

    def test_a_detached_session_descendant_is_ended_on_suite_exit_and_timeout(self):
        detached = self.hanging("detached", timeout=60)
        detached["argv"].extend(["--detach", "--leave"])
        (result,) = self.run_all([detached])
        self.assertEqual((result["passed"], result["exit"]), (True, 0))
        self.assert_gone(self.pids("detached"))

        timed = self.hanging("detached_timeout", timeout=3)
        timed["argv"].append("--detach")
        (result,) = self.run_all([timed])
        self.assertEqual((result["passed"], result["exit"]), (False, None))
        self.assert_gone(self.pids("detached_timeout"))


class FullRun(Stubs):
    def gated(self):
        return self.unittest_folder("gated", GATED)

    def test_the_gated_test_runs_only_with_full(self):
        suite = self.gated()
        (quick,) = self.run_all([suite])
        self.assertEqual((quick["passed"], quick["tests"]), (True, 2))
        self.assertIn("skipped=1", quick["tail"])
        self.assertFalse((self.dir / "gated/full-ran").exists(), "the gated test was skipped")
        (full,) = self.run_all([suite], full=True)
        self.assertEqual((full["passed"], full["tests"]), (True, 2))
        self.assertNotIn("skipped", full["tail"])
        self.assertTrue((self.dir / "gated/full-ran").exists(), "the gated test ran")

    def test_the_caller_s_own_variable_does_not_leak_into_a_quick_run(self):
        with mock.patch.dict(os.environ, {"CONCLAVE_FULL_TESTS": "1"}):
            (quick,) = self.run_all([self.gated()])
        self.assertEqual((quick["passed"], quick["tests"]), (True, 2))
        self.assertIn("skipped=1", quick["tail"])
        self.assertFalse((self.dir / "gated/full-ran").exists())


class CommandLine(Stubs):
    def main(self, table, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(forge, "SUITES", table), mock.patch.object(forge, "FORGE_ROOT", self.dir), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main(["check-all", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_a_failure_first_then_a_pass_prints_both_lines_and_exits_1(self):
        code, out, _ = self.main([self.failing("bad"), self.passing("good")])
        lines = out.splitlines()
        self.assertEqual(code, 1)
        self.assertRegex(lines[0], r"^FAIL  bad  \d+\.\ds  \(exit 1\)$")
        self.assertRegex(lines[1], r"^PASS  good  \d+\.\ds$")
        self.assertIn("AssertionError: 2 != 3", out)
        self.assertIn("check-all: 1 of 2 suites passed", out)

    def test_all_passing_exits_0_and_shows_the_test_count(self):
        code, out, _ = self.main([self.unittest_folder("gated", GATED), self.passing("good")])
        self.assertEqual(code, 0)
        self.assertRegex(out.splitlines()[0], r"^PASS  gated  \d+\.\ds  2 tests$")

    def test_only_twice_runs_exactly_those_two(self):
        table = [self.passing("a"), self.passing("sentinel"), self.passing("b")]
        code, out, _ = self.main(table, "--only", "a", "--only", "b")
        self.assertEqual(code, 0)
        self.assertEqual([line.split()[1] for line in out.splitlines() if line.startswith("PASS")], ["a", "b"])
        self.assertEqual((self.ran("a"), self.ran("sentinel"), self.ran("b")), (True, False, True))

    def test_skip_leaves_its_suite_out(self):
        code, _, _ = self.main([self.passing("a"), self.passing("b")], "--skip", "a")
        self.assertEqual((code, self.ran("a"), self.ran("b")), (0, False, True))

    def test_a_suite_this_host_cannot_run_is_shown_as_skipped_and_never_as_passed(self):
        table = [dict(self.passing("shell"), os="posix"), self.passing("good")]
        with mock.patch.object(forge, "_runs_here", lambda suite: suite.get("os") != "posix"):
            code, out, _ = self.main(table)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "SKIP  shell  0.0s  (runs on POSIX only; CI's Linux job runs it)")
        self.assertIn("check-all: 1 of 1 suites passed, 1 not run on this host", out)
        self.assertNotIn("the end of its output", out)
        self.assertFalse(self.ran("shell"))
        with mock.patch.object(forge, "_runs_here", lambda suite: True):
            code, out, _ = self.main(table)
        self.assertRegex(out.splitlines()[0], r"^PASS  shell  ")
        self.assertTrue(self.ran("shell"))

    def test_a_posix_only_suite_runs_everywhere_but_windows(self):
        self.assertEqual(forge._runs_here({"os": "posix"}), os.name != "nt")
        self.assertTrue(forge._runs_here({}))

    def test_an_unknown_name_exits_2_before_any_suite_starts(self):
        for flag in ("--only", "--skip"):
            code, _, err = self.main([self.passing("a")], "--only", "a", flag, "nope")
            self.assertEqual(code, 2)
            self.assertIn("unknown suite nope", err)
            self.assertFalse(self.ran("a"))


class RealTable(unittest.TestCase):
    def test_every_suite_stands_on_something_that_exists(self):
        names = [suite["name"] for suite in forge.SUITES]
        self.assertEqual(len(names), len(set(names)))
        for suite in forge.SUITES:
            path = ROOT / suite["path"]
            self.assertTrue(path.exists(), suite["name"])
            self.assertIn(suite["path"], suite["argv"], suite["name"])
            if suite["kind"] == "unittest":
                self.assertTrue(list(path.glob("test_*.py")), f"{suite['name']} holds no test file")

    def test_every_folder_of_script_tests_in_the_repository_is_a_suite(self):
        listed = subprocess.run(["git", "ls-files", "tests", "scripts/tests", "kits"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.split()
        folders = {str(Path(name).parent.as_posix()) for name in listed
                   if Path(name).name.startswith("test_") and name.endswith(".py")
                   and (name.startswith(("tests/", "scripts/tests/")) or "/templates/scripts/tests/" in name)}
        top = {folder for folder in folders if not any(folder.startswith(other + "/") for other in folders)}
        self.assertEqual(top, {suite["path"] for suite in forge.SUITES if suite["kind"] == "unittest"})

    def test_every_install_test_in_the_repository_is_a_suite(self):
        # Found by the round of D01 T02 §1: the six bash install tests ran in no suite.
        listed = subprocess.run(["git", "ls-files", "kits"], cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.split()
        scripts = {name for name in listed if Path(name).name.startswith("test-") and name.endswith(".sh")}
        self.assertEqual(len(scripts), 6)
        suites = {suite["path"]: suite for suite in forge.SUITES if suite["path"].endswith(".sh")}
        self.assertEqual(set(suites), scripts)
        for suite in suites.values():
            self.assertEqual((suite["os"], suite["argv"]), ("posix", ["bash", suite["path"]]))

    def test_every_kit_shell_script_is_committed_executable(self):
        # Found by CI's first run of the install suites: five installers were committed without the executable bit,
        # which a checkout on a Windows drive hides (every file is executable there) and a Linux checkout does not.
        listed = subprocess.run(["git", "ls-files", "-s", "kits/*/scripts/*.sh"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.splitlines()
        scripts = [line for line in listed if line.split("	")[1].count("/") == 3]  # kits/<kit>/scripts/<name>.sh
        self.assertEqual(len(scripts), 14)
        self.assertEqual([line.split("	")[1] for line in scripts if not line.startswith("100755 ")], [])

    def test_a_real_suite_passes_through_the_command_line(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = forge.main(["check-all", "--only", "agent-tiers"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertRegex(out.getvalue().splitlines()[0], r"^PASS  agent-tiers  ")

    def test_the_workflow_runs_its_suites_through_check_all(self):
        text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        runs = [line.split("run:", 1)[1].strip() for line in text.splitlines() if "run:" in line and "forge.py check-all" in line]
        self.assertEqual(runs, ["python forge.py check-all --only tests", "python forge.py check-all --full --only tests",
                                "python forge.py check-all --full --skip tests"])
        self.assertNotIn("unittest discover", text)
        self.assertNotIn("CONCLAVE_FULL_TESTS", text, "--full is the one place the full run is asked for")


if __name__ == "__main__":
    unittest.main()
