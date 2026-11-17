"""`forge.py check-all` runs every suite the repository holds (D01 T02 §1), proven here on stub suites."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
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
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)

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
        kwargs.setdefault("excluded", {})
        return forge.check_all(suites=suites, root=self.dir, **kwargs)

    def main(self, table, *argv, excluded=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(forge, "SUITES", table), mock.patch.object(forge, "FORGE_ROOT", self.dir), \
                mock.patch.object(forge, "EXCLUDED_TESTS", {} if excluded is None else excluded), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main(["check-all", *argv])
        return code, out.getvalue(), err.getvalue()

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

    def test_a_python_suites_summary_stays_after_what_it_printed_before(self):
        # Python buffers a piped stdout and would write it at exit, after the summary unittest sends to stderr: the
        # kept tail was then 40 lines of a test's own printing with the failure pushed out (found 2026-11-14).
        chatty = self.command("chatty", 'import sys\nfor i in range(200):\n    print("chatter", i)\n'
                                        'sys.stderr.write("FAILED (failures=1)\\n")\nsys.exit(1)\n')
        with mock.patch.dict(os.environ):
            os.environ.pop("PYTHONUNBUFFERED", None)
            (result,) = self.run_all([chatty])
        self.assertEqual(result["tail"].splitlines()[-1], "FAILED (failures=1)")
        self.assertIn("chatter 199", result["tail"])

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
        shutil.rmtree(self.dir / "zero_exit5")

        quiet = self.unittest_folder("quiet", GATED)
        quiet["argv"] = [sys.executable, "-c", "pass"]  # exits 0 and reports no test
        (result,) = self.run_all([quiet])
        self.assertEqual((result["passed"], result["exit"], result["reason"]), (False, 0, "no tests ran"))
        shutil.rmtree(self.dir / "quiet")

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
        orig_start = threading.Thread.start

        def interrupted_start(thread_self):
            if getattr(thread_self._target, "__name__", "") == "drain":
                self.pids("startup")  # the suite and its child are running before _wait is entered
                raise KeyboardInterrupt
            return orig_start(thread_self)

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
    def test_a_failure_first_then_a_pass_prints_both_lines_and_exits_1(self):
        code, out, _ = self.main([self.failing("bad"), self.passing("good")])
        lines = out.splitlines()
        self.assertEqual(code, 1)
        self.assertRegex(lines[0], r"^FAIL  bad  \d+\.\ds  \(exit 1\)$")
        self.assertRegex(lines[1], r"^PASS  good  \d+\.\ds$")
        self.assertIn("AssertionError: 2 != 3", out)
        self.assertIn("check-all: 1 of 2 suites passed", out)

    def test_a_failed_suites_output_is_shown_whatever_the_console_can_encode(self):
        # Found 2026-11-15: a failing suite printed a byte that is not UTF-8, the tail held U+FFFD, and a stdout
        # redirected on Windows (cp1252) refused it, so check-all ended without saying which test failed.
        body = ("import sys, unittest\nclass Bad(unittest.TestCase):\n    def test_fail(self):\n"
                "        sys.stdout.buffer.write(b'odd byte \\xff here\\n')\n        sys.stdout.flush()\n"
                "        self.fail('boom')\n")
        table = [self.unittest_folder("odd", body)]
        raw = io.BytesIO()
        out = io.TextIOWrapper(raw, encoding="cp1252", newline="")
        with mock.patch.object(forge, "SUITES", table), mock.patch.object(forge, "FORGE_ROOT", self.dir), \
                mock.patch.object(forge, "EXCLUDED_TESTS", {}), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            code = forge.main(["check-all"])
        out.flush()
        text = raw.getvalue().decode("cp1252")
        self.assertEqual(code, 1)
        self.assertIn("the end of its output", text)
        self.assertIn("odd byte \\ufffd here", text)
        self.assertIn("AssertionError: boom", text)
        self.assertIn("check-all: 0 of 1 suites passed", text)

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


# A test module that records each test it runs, by id, in the file RAN_LOG names (D01 T02 §10).
RECORDING = r"""import os, unittest


class {cls}(unittest.TestCase):
    def setUp(self):
        with open(os.environ["RAN_LOG"], "a", encoding="utf-8") as log:
            log.write(self.id() + "\n")

    def test_one(self):
        pass

    def test_two(self):
        pass

    @unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "the full run only")
    def test_full_only(self):
        pass
"""


class Shard(Stubs):
    """`check-all --shard K/N`: each unittest suite's test files split into N shards that together run exactly what
    the whole suite runs (D01 T02 §10)."""

    def suite_of(self, name, modules, sizes=None):
        folder = self.dir / name
        folder.mkdir()
        for i, module in enumerate(modules):
            body = RECORDING.replace("{cls}", module.title().replace("_", ""))
            (folder / f"{module}.py").write_text(body + "\n" * ((sizes or {}).get(module, i)), encoding="utf-8")
        return {"name": name, "kind": "unittest", "path": name, "timeout": 120,
                "argv": [sys.executable, "-B", "-m", "unittest", "discover", "-s", name]}

    def ran_ids(self, log):
        return sorted(log.read_text(encoding="utf-8").split()) if log.exists() else []

    def test_every_file_is_in_exactly_one_shard(self):
        suite = self.suite_of("suite", [f"test_m{i}" for i in range(7)])
        folder = self.dir / suite["path"]
        for n in (1, 2, 3, 7, 9):
            shards = [forge.shard_modules(folder, k, n) for k in range(1, n + 1)]
            flat = [m for s in shards for m in s]
            self.assertEqual(sorted(flat), sorted(f"test_m{i}" for i in range(7)), n)
            self.assertEqual(len(flat), len(set(flat)), n)
            self.assertEqual(shards, [forge.shard_modules(folder, k, n) for k in range(1, n + 1)], "deterministic")

    def test_a_malformed_shard_is_refused(self):
        for text in ("0/2", "3/2", "1", "a/b", "1/0", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                forge.parse_shard(text)
        code, out, err = self.main([self.suite_of("suite", ["test_a"])], "--shard", "3/2")
        self.assertEqual(code, 2)
        self.assertIn("--shard takes K/N", err)

    def test_the_shards_run_exactly_the_tests_discovery_runs_gated_ones_included(self):
        suite = self.suite_of("suite", ["test_a", "test_b", "test_c", "test_d", "test_e"])
        whole, parts = self.dir / "whole.log", self.dir / "parts.log"
        with mock.patch.dict(os.environ, {"RAN_LOG": str(whole)}):
            [result] = self.run_all([suite], full=True)
        self.assertTrue(result["passed"], result)
        with mock.patch.dict(os.environ, {"RAN_LOG": str(parts)}):
            for k in (1, 2, 3):
                [result] = self.run_all([suite], full=True, shard=(k, 3))
                self.assertTrue(result["passed"], result)
                self.assertTrue(result["modules"])
        self.assertEqual(self.ran_ids(parts), self.ran_ids(whole))
        self.assertIn("test_a.TestA.test_full_only", self.ran_ids(parts))

    def test_a_failure_or_an_import_error_fails_its_shard(self):
        suites = []
        for name, body in (("assertion", "import unittest\n\nclass T(unittest.TestCase):\n"
                                         "    def test_x(self):\n        self.assertEqual(2, 3)\n"),
                           ("importing", "import no_such_module_here\n")):
            folder = self.dir / name
            folder.mkdir()
            (folder / "test_only.py").write_text(body, encoding="utf-8")
            suites.append({"name": name, "kind": "unittest", "path": name, "timeout": 60,
                           "argv": [sys.executable, "-B", "-m", "unittest", "discover", "-s", name]})
        for result in self.run_all(suites, shard=(1, 1)):
            with self.subTest(suite=result["name"]):
                self.assertFalse(result["passed"], result)
                self.assertFalse(result["skipped"])

    def test_an_empty_shard_is_skipped_and_a_shard_that_runs_nothing_fails(self):
        suite = self.suite_of("suite", ["test_a"])
        folder = self.dir / "empty"
        folder.mkdir()
        (folder / "test_nothing.py").write_text("x = 1\n", encoding="utf-8")
        empty = {"name": "empty", "kind": "unittest", "path": "empty", "timeout": 60,
                 "argv": [sys.executable, "-B", "-m", "unittest", "discover", "-s", "empty"]}
        [result] = self.run_all([suite, empty], shard=(2, 2), only=["suite"])
        self.assertEqual((result["passed"], result["skipped"]), (False, True))
        self.assertIn("holds no test file", result["reason"])
        [result] = self.run_all([suite, empty], shard=(1, 1), only=["empty"])
        self.assertEqual((result["passed"], result["skipped"], result["reason"]), (False, False, "no tests ran"))

    def test_a_suite_of_another_kind_runs_whole_in_shard_one_only(self):
        command = self.passing("cmd")
        self.assertEqual([r["name"] for r in self.run_all([command], shard=(1, 3))], ["cmd"])
        self.assertEqual(self.run_all([command], shard=(2, 3)), [])

    def test_the_shards_cover_every_file_the_inventory_gives_the_suite(self):
        # Inventory and shards agree: a module left out of every shard would be a test file no CI job runs.
        folder = ROOT / "tests"
        n = 3
        union = {m for k in range(1, n + 1) for m in forge.shard_modules(folder, k, n)}
        self.assertEqual(union, {f.stem for f in folder.glob("test*.py")})


class Workflow(unittest.TestCase):
    """The Linux full suite runs in three parallel shards (D01 T02 §10)."""

    def test_the_full_suite_is_a_matrix_of_three_shards_each_with_its_own_part(self):
        text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        job = text[text.index("  full-linux:"):text.index("  kits-linux:")]
        self.assertIn("fail-fast: false", job)
        self.assertRegex(job, r'shard: \["1/3", "2/3", "3/3"\]')
        self.assertIn("name: full suite (Linux) ${{ matrix.shard }}", job)
        self.assertIn("run: python forge.py check-all --full --only tests --shard ${{ matrix.shard }}", job)
        self.assertNotIn("run: python forge.py check-all --full --only tests\n", job)


class Inventory(Stubs):
    def _write(self, rel, text=""):
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_unowned_tests_finds_tracked_and_untracked_files_across_all_patterns(self):
        expected = [
            "alt_test.py",
            "hooks/test-epsilon.sh",
            "tests/extra/test_stray.py",
            "unit/delta.test.js",
            "unit/gamma.test.mjs",
        ]
        for rel in expected:
            self._write(rel)
        self._write("README.md", "# note\n")
        self._write("notes/helper.py", "x = 1\n")
        self._write("scripts/helper.test.txt", "ignored\n")
        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[], excluded={}), expected)

        subprocess.run(["git", "add", "tests/extra/test_stray.py"], cwd=self.dir, check=True)
        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[], excluded={}), expected)

        upkg = self.unittest_folder("upkg", GATED)
        self._write("upkg/alpha_test.py")
        self._write("upkg/beta.test.js")
        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[upkg], excluded={}),
                         sorted([*expected, "upkg/alpha_test.py", "upkg/beta.test.js"]))

    def test_unittest_ownership_respects_package_init_chain(self):
        passing_test = "import unittest\nclass Ok(unittest.TestCase):\n    def test_ok(self): pass\n"
        suite = self.unittest_folder("pkgsuite", GATED)
        self._write("pkgsuite/subpkg/__init__.py")
        self._write("pkgsuite/subpkg/test_ok.py", passing_test)
        self._write("pkgsuite/subpkg/deep/__init__.py")
        self._write("pkgsuite/subpkg/deep/test_nested.py", passing_test)
        self._write("pkgsuite/plaindir/test_missing_init.py", passing_test)
        self._write("pkgsuite/noparent/nested/__init__.py")
        self._write("pkgsuite/noparent/nested/test_orphan.py", passing_test)

        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[suite], excluded={}),
                         ["pkgsuite/noparent/nested/test_orphan.py", "pkgsuite/plaindir/test_missing_init.py"])
        code, out, _ = self.main([suite])
        self.assertEqual(code, 1)
        self.assertIn("pkgsuite/noparent/nested/test_orphan.py", out)
        self.assertIn("pkgsuite/plaindir/test_missing_init.py", out)

        (self.dir / "pkgsuite/plaindir/test_missing_init.py").unlink()
        (self.dir / "pkgsuite/noparent/nested/test_orphan.py").unlink()
        code, out, _ = self.main([suite])
        self.assertEqual(code, 0, out)
        self.assertIn("4 tests", out)

    def test_unittest_ownership_refuses_invalid_module_filenames(self):
        suite = self.unittest_folder("modsuite", GATED)
        self._write("modsuite/test_sync-conflicts.py",
                    "import unittest\nclass Bad(unittest.TestCase):\n    def test_fail(self): self.fail('boom')\n")
        self._write("modsuite/test_bad.name.py",
                    "import unittest\nclass Bad(unittest.TestCase):\n    def test_fail(self): self.fail('boom')\n")

        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[suite], excluded={}),
                         ["modsuite/test_bad.name.py", "modsuite/test_sync-conflicts.py"])
        code, out, _ = self.main([suite])
        self.assertEqual(code, 1)
        self.assertIn("modsuite/test_sync-conflicts.py", out)
        self.assertIn("modsuite/test_bad.name.py", out)

    def test_command_suite_owns_only_explicit_argv_files_not_folder_prefix(self):
        self._write("plug/tests/one.test.js")
        self._write("plug/tests/two.test.js")
        suite = {"name": "plug", "kind": "command", "path": "plug/tests", "timeout": 30,
                 "argv": [sys.executable, "-c", "pass", "plug/tests/one.test.js"]}
        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[suite], excluded={}), ["plug/tests/two.test.js"])
        code, out, _ = self.main([suite])
        self.assertEqual(code, 1)
        self.assertIn("plug/tests/two.test.js", out)

        suite["argv"].append("plug/tests/two.test.js")
        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[suite], excluded={}), [])
        code, out, _ = self.main([suite])
        self.assertEqual(code, 0, out)

    def test_exclusions_require_existing_unowned_file_with_reason(self):
        good = self.unittest_folder("good", GATED)
        self._write("plug/need_dep.test.js")

        self.assertEqual(forge.unowned_tests(root=self.dir, suites=[good],
                                             excluded={"plug/need_dep.test.js": "needs external package"}), [])
        code, out, _ = self.main([good], excluded={"plug/need_dep.test.js": "needs external package"})
        self.assertEqual(code, 0, out)

        for empty_reason in ("", "   "):
            self.assertEqual(forge.unowned_tests(root=self.dir, suites=[good],
                                                 excluded={"plug/need_dep.test.js": empty_reason}),
                             ["plug/need_dep.test.js"])
            code, out, _ = self.main([good], excluded={"plug/need_dep.test.js": empty_reason})
            self.assertEqual(code, 1)
            self.assertIn("plug/need_dep.test.js", out)

        for bad_excluded in (
            {"plug/need_dep.test.js": "ok", "plug/missing.test.js": "stale"},
            {"plug/need_dep.test.js": "ok", "plug/": "directory prefix is not allowed"},
            {"plug/need_dep.test.js": "ok", "good/test_stub.py": "already owned"},
        ):
            code, out, _ = self.main([good], excluded=bad_excluded)
            self.assertEqual(code, 1)
            bad_key = next(k for k in bad_excluded if k != "plug/need_dep.test.js")
            self.assertIn(bad_key.rstrip("/"), out)

    def test_inventory_failure_refuses_to_run_any_suite_even_with_only_or_skip(self):
        sentinel = self.passing("sentinel")
        owned = self.unittest_folder("owned", GATED)
        table = [sentinel, owned]
        stray = self._write("tests/extra/test_stray.py", "x = 1\n")

        for argv in ((), ("--only", "sentinel"), ("--skip", "owned")):
            code, out, _ = self.main(table, *argv)
            self.assertEqual(code, 1)
            self.assertIn("tests/extra/test_stray.py", out)
            self.assertFalse(self.ran("sentinel"))

        stray.unlink()
        code, out, _ = self.main(table, "--only", "sentinel", excluded={"stale.test.js": "missing"})
        self.assertEqual(code, 1)
        self.assertIn("stale.test.js", out)
        self.assertFalse(self.ran("sentinel"))

        code, out, _ = self.main(table, "--only", "sentinel")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.ran("sentinel"))

    def test_git_ls_files_failure_or_missing_binary_exits_1_before_any_suite_starts(self):
        sentinel = self.passing("sentinel")
        with tempfile.TemporaryDirectory() as raw_dir:
            nongit = Path(raw_dir).resolve()
            (nongit / "sentinel.py").write_text((self.dir / "sentinel.py").read_text(encoding="utf-8"), encoding="utf-8")
            with self.assertRaises(forge.UnownedTestsError) as ctx:
                forge.check_all(suites=[sentinel], root=nongit, excluded={})
            self.assertIn("git ls-files", str(ctx.exception))
            self.assertFalse((nongit / "sentinel.ran").exists())

        real_run = subprocess.run

        def raise_missing(cmd, *args, **kwargs):
            if cmd[:2] == ["git", "ls-files"]:
                raise FileNotFoundError("git not found")
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(forge.subprocess, "run", raise_missing):
            code, out, _ = self.main([sentinel])
        self.assertEqual(code, 1)
        self.assertIn("git ls-files", out)
        self.assertFalse(self.ran("sentinel"))

        def fail_exit(cmd, *args, **kwargs):
            if cmd[:2] == ["git", "ls-files"]:
                return subprocess.CompletedProcess(cmd, 128, b"", b"fatal: index error")
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(forge.subprocess, "run", fail_exit):
            code, out, _ = self.main([sentinel])
        self.assertEqual(code, 1)
        self.assertIn("git ls-files failed (exit 128)", out)
        self.assertFalse(self.ran("sentinel"))


class RealTable(unittest.TestCase):
    def test_every_suite_stands_on_something_that_exists(self):
        names = [suite["name"] for suite in forge.SUITES]
        self.assertEqual(len(names), len(set(names)))
        for suite in forge.SUITES:
            path = ROOT / suite["path"]
            self.assertTrue(path.exists(), suite["name"])
            self.assertTrue(any(arg == suite["path"] or arg.startswith(suite["path"] + "/")
                                for arg in suite["argv"]), suite["name"])
            if suite["kind"] == "unittest":
                self.assertTrue(list(path.glob("test_*.py")), f"{suite['name']} holds no test file")
            else:
                for arg in suite["argv"]:
                    if arg.startswith(suite["path"] + "/"):
                        self.assertTrue((ROOT / arg).is_file(), f"{suite['name']}: missing {arg}")

    def test_every_folder_of_script_tests_in_the_repository_is_a_suite(self):
        listed = subprocess.run(["git", "ls-files", "tests", "scripts/tests", "kits", "global", "plugins/claude"],
                                cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        folders = {str(Path(name).parent.as_posix()) for name in listed
                   if Path(name).name.startswith("test_") and name.endswith(".py")
                   and (name.startswith(("tests/", "scripts/tests/", "global/", "plugins/claude/"))
                        or "/templates/scripts/tests/" in name)}
        top = {folder for folder in folders if not any(folder.startswith(other + "/") for other in folders)}
        self.assertEqual(top, {suite["path"] for suite in forge.SUITES if suite["kind"] == "unittest"})

    def test_every_repository_test_file_is_owned_or_explicitly_excluded(self):
        self.assertEqual(forge.unowned_tests(), [])
        self.assertEqual(forge._inventory_problems(ROOT, forge.SUITES, forge.EXCLUDED_TESTS), [])
        self.assertEqual(len(forge.EXCLUDED_TESTS), 20)
        for path, reason in forge.EXCLUDED_TESTS.items():
            self.assertTrue((ROOT / path).is_file(), path)
            self.assertIn("requires npm package '", reason, path)

    @staticmethod
    def kit_shell_scripts(root):
        """Tracked `kits/<kit>/scripts/*.sh` files: a `:(glob)` pathspec, whose `*` stays inside one folder, so the
        hooks a kit installs from `kits/<kit>/templates/scripts/hooks/` are not among them."""
        return subprocess.run(["git", "ls-files", ":(glob)kits/*/scripts/*.sh"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.split()

    def test_no_kit_keeps_a_shell_script_beside_its_templates(self):
        # D01 T02 §4 retired the bash installers, their tests and the doctor scripts: `forge.py` is the only installer
        # and the only doctor, because it alone writes the install record. One coming back is refused here and,
        # for an install test, by the inventory as a test no suite runs.
        self.assertEqual(self.kit_shell_scripts(ROOT), [])
        self.assertEqual([suite["name"] for suite in forge.SUITES if suite["path"].endswith(".sh")], [])
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp).resolve()
            subprocess.run(["git", "init", "-q"], cwd=scratch, check=True)
            for rel in ("kits/base/scripts/test-install.sh", "kits/base/templates/scripts/hooks/pre-push.sh"):
                (scratch / rel).parent.mkdir(parents=True)
                (scratch / rel).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            subprocess.run(["git", "add", "kits"], cwd=scratch, check=True)
            self.assertEqual(self.kit_shell_scripts(scratch), ["kits/base/scripts/test-install.sh"])
            self.assertIn("kits/base/scripts/test-install.sh: unowned test file (add to SUITES or EXCLUDED_TESTS)",
                          forge._inventory_problems(scratch, forge.SUITES, {}))

    def test_a_real_suite_passes_through_the_command_line(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = forge.main(["check-all", "--only", "agent-tiers"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertRegex(out.getvalue().splitlines()[0], r"^PASS  agent-tiers  ")

    def test_the_workflow_runs_its_suites_through_check_all(self):
        text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        runs = [line.split("run:", 1)[1].strip() for line in text.splitlines() if "run:" in line and "forge.py check-all" in line]
        # The full suite runs as three shards of one matrix job (D01 T02 §10).
        self.assertEqual(runs, ["python forge.py check-all --only tests",
                                "python forge.py check-all --full --only tests --shard ${{ matrix.shard }}",
                                "python forge.py check-all --full --skip tests"])
        self.assertNotIn("unittest discover", text)
        self.assertNotIn("CONCLAVE_FULL_TESTS", text, "--full is the one place the full run is asked for")


if __name__ == "__main__":
    unittest.main()
