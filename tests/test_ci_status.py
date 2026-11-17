"""kits/todo scripts/ci_status.py: the CI state of main read through a fake gh, and never green when gh cannot answer."""
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "kits" / "todo" / "templates" / "scripts" / "ci_status.py"
spec = importlib.util.spec_from_file_location("ci_status_under_test", SCRIPT)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

SHA_OLD, SHA_NEW = "a" * 40, "b" * 40

class Scratch:
    """A throwaway folder that can still be removed after git marks its objects read-only."""

    def __init__(self):
        self.name = tempfile.mkdtemp()

    def cleanup(self):
        for path in Path(self.name).rglob("*"):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        shutil.rmtree(self.name, ignore_errors=True)



def run(n, status="completed", conclusion="success", sha=SHA_NEW):
    return {"databaseId": n, "headSha": sha, "status": status, "conclusion": conclusion if status == "completed" else "",
            "url": f"https://github.com/o/r/actions/runs/{n}", "createdAt": f"2026-10-23T00:00:{n:02d}Z", "event": "push"}


def workspace(root, workflows=("build.yml", "plan.yml"), config=None):
    """A checkout with the given workflow files and, when config is not None, a .conclave/ci.json holding it."""
    folder = Path(root) / ".github" / "workflows"
    folder.mkdir(parents=True, exist_ok=True)
    for name in workflows:
        (folder / name).write_text("name: x\non: push\n", encoding="utf-8")
    if config is not None:
        (Path(root) / ".conclave").mkdir(exist_ok=True)
        text = config if isinstance(config, str) else json.dumps(config)
        (Path(root) / ".conclave" / "ci.json").write_text(text, encoding="utf-8")


class FakeGh:
    """An in-process gh: runs per workflow, jobs per run id, or a failure for every call."""

    def __init__(self, runs=None, jobs=None, fail=None, missing=False):
        self.runs, self.jobs, self.fail, self.missing, self.calls = runs or {}, jobs or {}, fail, missing, []

    def __call__(self, args):
        self.calls.append(args)
        if self.missing:
            raise FileNotFoundError("gh")
        if self.fail:
            return self.fail
        if args[:2] == ["run", "list"]:
            assert args[args.index("--json") + 1] == ci.FIELDS and args[args.index("--limit") + 1] == "10"
            assert args[args.index("--branch") + 1] == "main"
            return 0, json.dumps(self.runs.get(args[args.index("--workflow") + 1], [])), ""
        if args[:2] == ["run", "view"]:
            return 0, json.dumps({"jobs": self.jobs.get(int(args[2]), [])}), ""
        raise AssertionError(args)

    def workflows(self):
        return [c[c.index("--workflow") + 1] for c in self.calls if c[:2] == ["run", "list"]]


class CiStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = Scratch()
        self.root = Path(self._tmp.name)
        workspace(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def status(self, fake, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--json", *argv], runner=fake, root=self.root)
        return code, json.loads(out.getvalue())

    def usage_error(self, argv, fake=None):
        with self.assertRaises(SystemExit) as ctx, redirect_stdout(io.StringIO()):
            with unittest.mock.patch("sys.stderr", io.StringIO()) as err:
                ci.main(argv, runner=fake or FakeGh(), root=self.root)
        return ctx.exception.code, err.getvalue()

    def test_green(self):
        code, report = self.status(FakeGh({"build.yml": [run(2), run(1, sha=SHA_OLD)], "plan.yml": [run(3)]}))
        self.assertEqual(code, 0)
        self.assertEqual([(w["workflow"], w["verdict"], w["in_progress"]) for w in report["workflows"]],
                         [("build.yml", "green", 0), ("plan.yml", "green", 0)])
        self.assertEqual(report["workflows"][0]["verdict_run"]["headSha"], SHA_NEW)

    def test_red_names_the_workflow_commit_url_and_failed_jobs(self):
        fake = FakeGh({"build.yml": [run(5, conclusion="failure"), run(4)], "plan.yml": [run(3)]},
                      jobs={5: [{"name": "x64 Release", "status": "completed", "conclusion": "failure", "url": "u1"},
                                {"name": "ARM64 Debug", "status": "completed", "conclusion": "success", "url": "u2"},
                                {"name": "asan", "status": "completed", "conclusion": "timed_out", "url": "u3"}]})
        code, report = self.status(fake)
        self.assertEqual(code, 1)
        build = report["workflows"][0]
        self.assertEqual((build["verdict"], build["verdict_run"]["headSha"], build["verdict_run"]["url"]),
                         ("red", SHA_NEW, "https://github.com/o/r/actions/runs/5"))
        self.assertEqual([j["name"] for j in build["failed_jobs"]], ["x64 Release", "asan"])
        self.assertIn(["run", "view", "5", "--json", "jobs"], fake.calls)
        out = io.StringIO()
        with redirect_stdout(out):
            ci.main([], runner=fake, root=self.root)
        text = out.getvalue()
        for expected in ("build.yml: red at bbbbbbbbbbbb (https://github.com/o/r/actions/runs/5)",
                         "failed job: x64 Release (failure) u1", "failed job: asan (timed_out) u3"):
            self.assertIn(expected, text)

    def test_in_progress_runs_are_reported_and_do_not_decide(self):
        fake = FakeGh({"build.yml": [run(9, status="in_progress"), run(8, status="queued"), run(7, conclusion="failure")],
                       "plan.yml": [run(6, status="in_progress"), run(5)]}, jobs={7: []})
        code, report = self.status(fake)
        self.assertEqual(code, 1, "a newer run still in progress does not make an older red run green")
        self.assertEqual([(w["verdict"], w["in_progress"]) for w in report["workflows"]], [("red", 2), ("green", 1)])

    def test_a_cancelled_run_carries_no_verdict(self):
        code, report = self.status(FakeGh({"build.yml": [run(3, conclusion="cancelled"), run(2)],
                                           "plan.yml": [run(4, conclusion="cancelled"), run(1, conclusion="failure")]}))
        self.assertEqual(code, 1)
        build, plan = report["workflows"]
        self.assertEqual((build["latest_completed_state"], build["verdict"]), ("cancelled", "green"))
        self.assertEqual((plan["latest_completed_state"], plan["verdict"]), ("cancelled", "red"))
        code, report = self.status(FakeGh({"build.yml": [run(3, conclusion="cancelled")], "plan.yml": [run(1)]}))
        self.assertEqual((code, report["workflows"][0]["verdict"]), (0, "none"))

    def test_no_runs(self):
        code, report = self.status(FakeGh({}))
        self.assertEqual(code, 0)
        self.assertEqual([(w["verdict"], w["latest_completed"], w["in_progress"]) for w in report["workflows"]],
                         [("none", None, 0), ("none", None, 0)])

    def test_gh_missing_unauthenticated_or_failing_is_never_green(self):
        cases = {"missing": FakeGh(missing=True),
                 "unauthenticated": FakeGh(fail=(4, "", "To get started with GitHub CLI, please run:  gh auth login")),
                 "not json": FakeGh(fail=(0, "<html>", ""))}
        for name, fake in cases.items():
            with self.subTest(name):
                code, report = self.status(fake)
                self.assertEqual(code, 3)
                self.assertEqual(report["exit"], 3)
                self.assertNotIn("workflows", report)
        self.assertIn("gh auth login", self.status(cases["unauthenticated"])[1]["error"])

    def test_bad_usage(self):
        for argv in (["--workflow", "nightly.yml"], ["--workflow", "../build.yml"], ["--branch", " "], ["--nope"]):
            with self.subTest(argv=argv):
                self.assertEqual(self.usage_error(argv)[0], 2)

    def test_without_ci_json_every_workflow_file_is_watched(self):
        workspace(self.root, workflows=("nightly.yaml", "deploy.yml"))
        (self.root / ".github" / "workflows" / "README.md").write_text("not a workflow\n", encoding="utf-8")
        self.assertEqual(ci.watched(self.root), ["build.yml", "deploy.yml", "nightly.yaml", "plan.yml"])
        fake = FakeGh({})
        self.assertEqual(self.status(fake)[0], 0)
        self.assertEqual(fake.workflows(), ["build.yml", "deploy.yml", "nightly.yaml", "plan.yml"])

    def test_ci_json_names_the_watched_workflows(self):
        workspace(self.root, workflows=("lint.yml",), config={"workflows": ["plan.yml", "build.yml"]})
        self.assertEqual(ci.watched(self.root), ["plan.yml", "build.yml"])
        fake = FakeGh({"plan.yml": [run(1)], "build.yml": [run(2)]})
        code, report = self.status(fake)
        self.assertEqual(code, 0)
        self.assertEqual([w["workflow"] for w in report["workflows"]], ["plan.yml", "build.yml"])
        self.assertEqual(fake.workflows(), ["plan.yml", "build.yml"], "lint.yml is not watched")

    def test_ci_json_without_a_workflows_list_falls_back_to_every_file(self):
        workspace(self.root, config={"merge": {}})
        self.assertEqual(ci.watched(self.root), ["build.yml", "plan.yml"])

    def test_a_malformed_ci_json_is_a_usage_error(self):
        for config in ("{not json", {"workflows": "build.yml"}, {"workflows": ["build.yml", ""]},
                       {"workflows": ["build.yml", 3]}):
            with self.subTest(config=config):
                workspace(self.root, config=config)
                fake = FakeGh({})
                code, err = self.usage_error(["--json"], fake)
                self.assertEqual(code, 2)
                self.assertIn(".conclave/ci.json", err)
                self.assertEqual(fake.calls, [], "gh is never asked on a malformed config")

    def test_an_explicit_workflow_overrides_ci_json(self):
        workspace(self.root, config={"workflows": ["build.yml", "plan.yml"]})
        fake = FakeGh({"plan.yml": [run(1)]})
        code, report = self.status(fake, "--workflow", "plan.yml")
        self.assertEqual(code, 0)
        self.assertEqual([w["workflow"] for w in report["workflows"]], ["plan.yml"])
        self.assertEqual(fake.workflows(), ["plan.yml"])

    def test_a_ci_json_naming_a_missing_workflow_is_a_usage_error(self):
        workspace(self.root, config={"workflows": ["nightly.yml"]})
        code, err = self.usage_error(["--json"])
        self.assertEqual(code, 2)
        self.assertIn("nightly.yml", err)

    def test_no_workflow_at_all_is_a_usage_error(self):
        shutil.rmtree(self.root / ".github")
        self.assertEqual(ci.watched(self.root), [])
        self.assertEqual(self.usage_error(["--json"])[0], 2)


FAKE_GH = textwrap.dedent('''\
    import json, os, sys
    args = sys.argv[1:]
    if os.environ.get("FAKE_GH") == "unauth":
        sys.stderr.write("To get started with GitHub CLI, please run:  gh auth login\\n")
        sys.exit(4)
    if args[:2] == ["run", "list"]:
        print(json.dumps([{"databaseId": 1, "headSha": "c" * 40, "status": "completed", "conclusion": "success",
                           "url": "https://example.invalid/1", "createdAt": "2026-10-23T00:00:00Z", "event": "push"}]))
''')


class RealProcess(unittest.TestCase):
    """The default runner against a fake gh executable on PATH, and with no gh at all, from an installed copy."""

    def setUp(self):
        self._tmp = Scratch()
        self.project = Path(self._tmp.name) / "project"
        (self.project / "scripts").mkdir(parents=True)
        self.script_path = self.project / "scripts" / "ci_status.py"
        shutil.copyfile(SCRIPT, self.script_path)
        workspace(self.project)
        self.bin = Path(self._tmp.name) / "bin"
        self.bin.mkdir()
        fake = Path(self._tmp.name) / "fake_gh.py"
        fake.write_text(FAKE_GH, encoding="utf-8")
        if os.name == "nt":
            (self.bin / "gh.cmd").write_text(f'@"{sys.executable}" "{fake}" %*\r\n', encoding="utf-8")
        else:
            launcher = self.bin / "gh"
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)

    def tearDown(self):
        self._tmp.cleanup()

    def script(self, path, **env):
        system = {"SYSTEMROOT": os.environ["SYSTEMROOT"]} if os.name == "nt" else {}
        return subprocess.run([sys.executable, str(self.script_path), "--json"], capture_output=True, text=True,
                              timeout=120, env={"PATH": path, **system, **env}, cwd=self._tmp.name)

    def test_green_through_a_fake_gh(self):
        result = self.script(str(self.bin))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([w["verdict"] for w in json.loads(result.stdout)["workflows"]], ["green", "green"])

    def test_unauthenticated_gh_exits_3(self):
        result = self.script(str(self.bin), FAKE_GH="unauth")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("gh auth login", json.loads(result.stdout)["error"])

    def test_no_gh_on_path_exits_3(self):
        empty = Path(self._tmp.name) / "empty"
        empty.mkdir()
        result = self.script(str(empty))
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["error"], "gh is not installed or not on PATH")


def attempt_run(n, minute=0, status="completed", conclusion="success", sha=SHA_NEW, attempt=1):
    """A run with its creation minute (so pages and horizons can be tested) and its attempt number."""
    return {"databaseId": n, "headSha": sha, "status": status, "conclusion": conclusion if status == "completed" else "",
            "url": f"https://github.com/o/r/actions/runs/{n}", "createdAt": f"2026-10-23T{minute // 60:02d}:{minute % 60:02d}:00Z",
            "event": "push", "attempt": attempt}


class PagedGh:
    """A gh with pages (the `--limit` newest runs), earlier attempts through `gh api`, reruns, and failures on demand.
    `runs` and `attempts` may be changed between calls to play out what CI did meanwhile."""

    def __init__(self, runs=None, attempts=None, fail_limit=None, rerun_code=0):
        self.runs, self.attempts, self.fail_limit, self.rerun_code = runs or {}, attempts or {}, fail_limit, rerun_code
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["run", "list"]:
            limit = int(args[args.index("--limit") + 1])
            if self.fail_limit is not None and limit >= self.fail_limit:
                return 1, "", "HTTP 502"
            runs = sorted(self.runs.get(args[args.index("--workflow") + 1], []), key=lambda r: r["createdAt"],
                          reverse=True)
            return 0, json.dumps(runs[:limit]), ""
        if args[:2] == ["run", "view"] and "jobs" not in args:
            return 0, json.dumps(getattr(self, "views", {})[int(args[2])]), ""
        if args[:2] == ["run", "view"]:
            return 0, json.dumps({"jobs": [{"name": "suite", "status": "completed", "conclusion": "failure",
                                            "url": "job"}]}), ""
        if args[0] == "api":
            run_id, attempt = args[1].split("/runs/")[1].split("/attempts/")
            status, conclusion = self.attempts[(int(run_id), int(attempt))]
            return 0, json.dumps({"status": status, "conclusion": conclusion,
                                  "html_url": f"https://github.com/o/r/actions/runs/{run_id}/attempts/{attempt}"}), ""
        if args[:2] == ["run", "rerun"]:
            return (0, "", "") if self.rerun_code == 0 else (self.rerun_code, "", "the run cannot be rerun")
        raise AssertionError(args)

    def reruns(self):
        return [c[2] for c in self.calls if c[:2] == ["run", "rerun"]]


class SinceLast(unittest.TestCase):
    """`--since-last`: every completed attempt since the last read, once; the state kept per branch and workflow,
    written only after a read that printed everything (D01 T02 §8)."""

    def setUp(self):
        self._tmp = Scratch()
        self.root = Path(self._tmp.name)
        workspace(self.root, workflows=("build.yml",))

    def tearDown(self):
        self._tmp.cleanup()

    def read(self, fake, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--json", "--since-last", *argv], runner=fake, root=self.root)
        return code, json.loads(out.getvalue().split("\nci-status:")[0])

    def new(self, report, workflow="build.yml"):
        entry = next(e for e in report["workflows"] if e["workflow"] == workflow)
        return [(i["run"], i["attempt"], i["verdict"]) for i in entry["new"]]

    def cursor(self):
        return (self.root / ci.CURSOR).read_bytes()

    def test_a_run_that_finishes_after_a_newer_one_is_reported_when_it_finishes(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1, status="in_progress"), attempt_run(2, 2)]})
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (0, [(2, 1, "green")]))
        self.assertEqual([r["databaseId"] for r in report["workflows"][0]["pending"]], [1])
        fake.runs["build.yml"][0] = attempt_run(1, 1, conclusion="failure")
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(1, 1, "red")]))
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (0, []))

    def test_a_failure_followed_by_a_green_before_the_read_is_still_reported(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        fake.runs["build.yml"] += [attempt_run(2, 2, conclusion="failure"), attempt_run(3, 3)]
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(2, 1, "red"), (3, 1, "green")]))

    def test_every_attempt_of_a_rerun_is_reported_once(self):
        fake = PagedGh({"build.yml": [attempt_run(5, 5)]})
        self.read(fake)
        # A later rerun of a run already reported green failed.
        fake.runs["build.yml"] = [attempt_run(5, 5, conclusion="failure", attempt=2)]
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(5, 2, "red")]))
        # A run whose first attempt failed and whose rerun went green, both unseen: the failure is read through the API.
        fake.runs["build.yml"].append(attempt_run(6, 6, attempt=2))
        fake.attempts[(6, 1)] = ("completed", "failure")
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(6, 1, "red"), (6, 2, "green")]))

    def test_a_failure_on_the_second_page_is_reported(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        fake.runs["build.yml"] += [attempt_run(2, 2, conclusion="failure")] + [attempt_run(n, n) for n in range(3, 60)]
        code, report = self.read(fake)
        self.assertEqual(code, 1)
        self.assertIn((2, 1, "red"), self.new(report))
        self.assertIn(["run", "list", "--branch", "main", "--workflow", "build.yml", "--limit", "200", "--json",
                       ci.FIELDS], fake.calls)

    def test_more_unread_runs_than_the_last_page_leave_the_state_and_say_so(self):
        # Round 1 P1: a failure beyond the last page must never be skipped with the cursor moved past it.
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        before = self.cursor()
        fake.runs["build.yml"] += [attempt_run(2, 2, conclusion="failure")] + [attempt_run(n, n) for n in range(3, 1010)]
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--since-last"], runner=fake, root=self.root)
        self.assertEqual(code, 3)
        self.assertIn("more than 1000 runs", out.getvalue())
        self.assertEqual(self.cursor(), before)

    def test_a_rerun_of_an_older_run_is_reported(self):
        # Round 1 P1: run 1 and a newer run 2 were read; run 1 is rerun (its creation time stays old) and fails.
        fake = PagedGh({"build.yml": [attempt_run(1, 1), attempt_run(2, 2)]})
        self.read(fake)
        fake.runs["build.yml"][0] = attempt_run(1, 1, conclusion="failure", attempt=2)
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(1, 2, "red")]))

    def test_a_rerun_of_a_red_run_started_elsewhere_is_read_off_the_list(self):
        # Completion review P1: someone reruns an older red run through GitHub after newer runs pushed it off the list.
        fake = PagedGh({"build.yml": [attempt_run(1, 1, conclusion="failure")]})
        self.assertEqual(self.read(fake)[0], 1)
        fake.runs["build.yml"] = [attempt_run(n, n) for n in range(2, 60)]
        fake.views = {1: attempt_run(1, 1, conclusion="failure", attempt=2)}
        code, report = self.read(fake)
        self.assertEqual(code, 1)
        self.assertIn((1, 2, "red"), self.new(report))
        code, report = self.read(fake)
        self.assertNotIn((1, 2, "red"), self.new(report), "reported once")
        fake.views = {1: attempt_run(1, 1, attempt=3)}
        code, report = self.read(fake)
        self.assertIn((1, 3, "green"), self.new(report))
        self.assertNotIn("1", json.loads(self.cursor())["main|build.yml"]["watching"], "a green rerun ends the watch")

    def test_a_run_the_rerun_command_started_is_read_off_the_list(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1, conclusion="cancelled", sha=SHA_OLD)]})
        self.read(fake)
        out = io.StringIO()
        with redirect_stdout(out):
            ci.main(["--rerun", SHA_OLD], runner=fake, root=self.root)
        # Many newer runs push it off the first page; its rerun failed.
        fake.runs["build.yml"] = [attempt_run(n, n) for n in range(2, 60)]
        fake.views = {1: attempt_run(1, 1, conclusion="failure", sha=SHA_OLD, attempt=2)}
        code, report = self.read(fake)
        self.assertEqual(code, 1)
        self.assertIn((1, 2, "red"), self.new(report))

    def test_each_workflow_and_branch_keeps_its_own_state(self):
        workspace(self.root, workflows=("build.yml", "plan.yml"))
        fake = PagedGh({"build.yml": [attempt_run(1, 1)], "plan.yml": [attempt_run(2, 2, conclusion="failure")]})
        code, report = self.read(fake, "--workflow", "build.yml")
        self.assertEqual(code, 0)
        code, report = self.read(fake, "--workflow", "plan.yml")
        self.assertEqual((code, self.new(report, "plan.yml")), (1, [(2, 1, "red")]))
        state = json.loads(self.cursor())
        self.assertEqual(sorted(state), ["main|build.yml", "main|plan.yml"])

    def test_an_unreadable_state_is_said_and_read_as_a_first_read(self):
        (self.root / ci.CURSOR).parent.mkdir(parents=True)
        (self.root / ci.CURSOR).write_text("{not json", encoding="utf-8")
        fake = PagedGh({"build.yml": [attempt_run(1, 1, conclusion="failure"), attempt_run(2, 2)]})
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--since-last"], runner=fake, root=self.root)
        self.assertIn("could not be read", out.getvalue())
        self.assertIn("read as a first read", out.getvalue())
        self.assertEqual(code, 0, "a first read reports the latest completed run and what follows it")
        self.assertEqual(sorted(json.loads(self.cursor())), ["main|build.yml"])

    def test_a_page_that_fails_leaves_the_state_as_it_was(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        before = self.cursor()
        fake.runs["build.yml"] += [attempt_run(n, n) for n in range(2, 14)]
        fake.fail_limit = 50
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--since-last"], runner=fake, root=self.root)
        self.assertEqual(code, 3)
        self.assertEqual(self.cursor(), before)

    def test_a_cursor_that_cannot_be_written_is_said_and_the_runs_come_again(self):
        (self.root / ci.CURSOR).mkdir(parents=True)   # a folder where the file goes
        fake = PagedGh({"build.yml": [attempt_run(1, 1, conclusion="failure")]})
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--since-last"], runner=fake, root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("the cursor could not be written", out.getvalue())
        self.assertTrue((self.root / ci.CURSOR).is_dir())

    def test_pending_runs_are_named_with_their_commit_and_url(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1, status="queued", sha=SHA_OLD), attempt_run(2, 2)]})
        out = io.StringIO()
        with redirect_stdout(out):
            ci.main([], runner=fake, root=self.root)
        self.assertIn(f"still running: {SHA_OLD[:12]} queued https://github.com/o/r/actions/runs/1", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            ci.main(["--json"], runner=fake, root=self.root)
        pending = json.loads(out.getvalue())["workflows"][0]["pending"]
        self.assertEqual([(r["databaseId"], r["headSha"], r["url"]) for r in pending],
                         [(1, SHA_OLD, "https://github.com/o/r/actions/runs/1")])


class Rerun(unittest.TestCase):
    """`--rerun <commit>`: the candidate's own run, never the tip's; three at most, the count kept across calls."""

    def setUp(self):
        self._tmp = Scratch()
        self.root = Path(self._tmp.name)
        workspace(self.root, workflows=("build.yml",))

    def tearDown(self):
        self._tmp.cleanup()

    def rerun(self, fake, commit=SHA_OLD):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--rerun", commit], runner=fake, root=self.root)
        return code, out.getvalue()

    def test_the_candidates_own_run_is_rerun_three_times_at_most(self):
        fake = PagedGh({"build.yml": [attempt_run(7, 7, conclusion="cancelled", sha=SHA_OLD), attempt_run(8, 8)]})
        for n in (1, 2, 3):
            code, said = self.rerun(fake)
            self.assertEqual(code, 0, said)
            self.assertIn(f"rerun {n} of 3", said)
        self.assertEqual(fake.reruns(), ["7", "7", "7"], "only the candidate's own run, never the tip's")
        code, said = self.rerun(fake)
        self.assertEqual(code, 4)
        self.assertIn("write it as open in the run file", said)
        self.assertEqual(fake.reruns(), ["7", "7", "7"])

    def test_a_green_or_running_candidate_is_left_and_a_refused_rerun_is_reported(self):
        self.assertIn("nothing to rerun", self.rerun(PagedGh({"build.yml": [attempt_run(7, 7, sha=SHA_OLD)]}))[1])
        refused = PagedGh({"build.yml": [attempt_run(7, 7, conclusion="failure", sha=SHA_OLD)]}, rerun_code=1)
        code, said = self.rerun(refused)
        self.assertEqual(code, 1)
        self.assertIn("was refused: the run cannot be rerun", said)
        self.assertFalse((self.root / ci.RERUNS).exists() and "reruns" in (self.root / ci.RERUNS).read_text())

    def test_a_short_commit_is_a_usage_error(self):
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), \
                unittest.mock.patch("sys.stderr", io.StringIO()):
            ci.main(["--rerun", "abc"], runner=PagedGh(), root=self.root)


class Placement(unittest.TestCase):
    """The read sits in the step that pushes and in the closeout, in each runner skill and the heartbeat prompt, and
    nothing in them holds a commit or a push back for CI (D01 T02 §8)."""
    SKILLS = REPO / "kits" / "todo" / "templates" / ".claude" / "skills"
    WHERE = {"process-todo-section": ["Push each commit as it lands"],
             "review-todo-section": ["Push each commit as it lands", "--rerun <stamped commit>"],
             "process-phase": ["Then check CI, red first", "## Closeout run=<run id>", "the phase parks: write a column-0"],
             "process-plan": ["after each stamp is pushed", "7. Run `<python> scripts/ci_status.py --since-last`.",
                             "then end with `--reason park` the same way"]}

    def test_each_read_sits_in_its_push_or_closeout_paragraph(self):
        for skill, anchors in self.WHERE.items():
            text = (self.SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            paragraphs = text.split("\n\n")
            for anchor in anchors:
                with self.subTest(skill=skill, anchor=anchor):
                    (holder,) = [p for p in paragraphs if anchor in p]
                    self.assertIn("ci_status.py --since-last", holder)

    def test_each_park_and_closeout_reads_after_its_push(self):
        # Completion review P2: a read before the final push does not see the run that push starts.
        for skill, anchor in (("process-plan", "then end with `--reason park` the same way"),
                              ("process-phase", "the phase parks: write a column-0"),
                              ("process-phase", "## Closeout run=<run id>")):
            text = (self.SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            (holder,) = [p for p in text.split("\n\n") if anchor in p]
            push = holder.index("push", holder.index("--since-last"))
            with self.subTest(skill=skill, anchor=anchor):
                self.assertGreater(holder.index("ci_status.py --since-last` once more", push), push)

    def test_no_skill_holds_a_commit_or_a_push_for_ci(self):
        import re
        for skill in self.WHERE:
            text = (self.SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertIsNone(re.search(r"(?i)\b(?:do not|don't) push\b|\bwait for (?:ci|the run) before "
                                            r"(?:pushing|committing)|\bhold(?:ing)? (?:back )?(?:a|the|each) "
                                            r"(?:commit|push)", text))


if __name__ == "__main__":
    unittest.main()
