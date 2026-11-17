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


def attempt_run(n, minute=0, status="completed", conclusion="success", sha=SHA_NEW, attempt=1, day="2026-10-23"):
    """A run with its creation day and minute (so the date ranges can be tested) and its attempt number."""
    return {"databaseId": n, "headSha": sha, "status": status, "conclusion": conclusion if status == "completed" else "",
            "url": f"https://github.com/o/r/actions/runs/{n}",
            "createdAt": f"{day}T{minute // 60 % 24:02d}:{minute % 60:02d}:00Z", "event": "push", "attempt": attempt}


class PagedGh:
    """A gh with pages (the `--limit` newest runs), earlier attempts through `gh api`, reruns, and failures on demand.
    `runs` and `attempts` may be changed between calls to play out what CI did meanwhile."""

    def __init__(self, runs=None, attempts=None, fail_limit=None, rerun_code=0):
        self.runs, self.attempts, self.fail_limit, self.rerun_code = runs or {}, attempts or {}, fail_limit, rerun_code
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["run", "list"] and args[args.index("--workflow") + 1] in getattr(self, "fail_workflows", ()):
            return 1, "", "HTTP 502"
        if args[:2] == ["run", "list"]:
            limit = int(args[args.index("--limit") + 1])
            if self.fail_limit is not None and limit >= self.fail_limit:
                return 1, "", "HTTP 502"
            runs = sorted(self.runs.get(args[args.index("--workflow") + 1], []), key=lambda r: r["createdAt"],
                          reverse=True)
            if "--branch" in args:   # a run without a "branch" key is main's
                runs = [r for r in runs if r.get("branch", "main") == args[args.index("--branch") + 1]]
            if "--status" in args:
                runs = [r for r in runs if r["status"] == args[args.index("--status") + 1]]
            if "--commit" in args:
                runs = [r for r in runs if r["headSha"] == args[args.index("--commit") + 1]]
            if "--created" in args:   # GitHub's own filter: a range of UTC times, both ends included
                first, last = args[args.index("--created") + 1].split("..")
                runs = [r for r in runs if first <= r["createdAt"] <= last]
            return 0, json.dumps(runs[:limit]), ""
        if args[:2] == ["run", "view"] and "jobs" not in args:
            return 0, json.dumps(getattr(self, "views", {})[int(args[2])]), ""
        if args[:2] == ["run", "view"]:
            return 0, json.dumps({"jobs": [{"name": "suite", "status": "completed", "conclusion": "failure",
                                            "url": "job"}]}), ""
        if args[:2] == ["api", "repos/{owner}/{repo}/git/refs"]:
            return (0, "{}", "") if getattr(self, "tag_at", None) is None else (1, "", "Reference already exists")
        if args[0] == "api" and "/git/ref/tags/" in args[1]:
            return 0, json.dumps({"object": {"sha": self.tag_at}}), ""
        if args[:2] == ["workflow", "run"]:
            return (0, "", "") if not getattr(self, "workflow_code", 0) else (1, "", "dispatch refused")
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


class Shards(unittest.TestCase):
    """A sharded full suite (D01 T02 §10): the run's own conclusion folds its jobs in, so one red shard is a red run
    naming that shard, and a cancelled shard leaves the run with no verdict."""

    def setUp(self):
        self._tmp = Scratch()
        self.root = Path(self._tmp.name)
        workspace(self.root, workflows=("tests.yml",))

    def tearDown(self):
        self._tmp.cleanup()

    def test_one_red_shard_is_a_red_run_naming_it_and_a_cancelled_one_no_verdict(self):
        jobs = [{"name": f"full suite (Linux) {k}/3", "status": "completed",
                 "conclusion": "failure" if k == 2 else "success", "url": f"job{k}"} for k in (1, 2, 3)]
        fake = FakeGh({"tests.yml": [run(5, conclusion="failure")]}, jobs={5: jobs})
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--json"], runner=fake, root=self.root)
        report = json.loads(out.getvalue())["workflows"][0]
        self.assertEqual((code, report["verdict"]), (1, "red"))
        self.assertEqual([j["name"] for j in report["failed_jobs"]], ["full suite (Linux) 2/3"])
        fake = FakeGh({"tests.yml": [run(6, conclusion="cancelled")]})
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--json"], runner=fake, root=self.root)
        self.assertEqual((code, json.loads(out.getvalue())["workflows"][0]["verdict"]), (0, "none"))


class SinceLast(unittest.TestCase):
    """`--since-last`: every completed attempt since the last read, once; the state kept per branch and workflow,
    written only after a read that printed everything (D01 T02 §8)."""

    def setUp(self):
        # A fixed clock: the fixture runs are dated, so the tests must not depend on the day they run.
        from datetime import datetime, timezone
        clock = unittest.mock.patch.object(ci, "_now", return_value=datetime(2026, 11, 1, tzinfo=timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
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

    def test_every_run_since_the_reach_is_listed_whatever_their_number(self):
        # No page cap: a failure among more than a thousand new runs is reported; each list is a day range.
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        fake.runs["build.yml"] += [attempt_run(2, 2, conclusion="failure")] + \
            [attempt_run(n, n, day=f"2026-10-{20 + n % 5:02d}") for n in range(3, 1010)]
        code, report = self.read(fake)
        self.assertEqual(code, 1)
        self.assertIn((2, 1, "red"), self.new(report))
        dated = [c for c in fake.calls if c[:2] == ["run", "list"] and "--created" in c]
        self.assertTrue(dated and all(".." in c[c.index("--created") + 1] for c in dated))

    def test_a_full_range_is_split_until_each_list_fits(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1, day="2026-10-20")]})
        with unittest.mock.patch.object(ci, "LIST_LIMIT", 5), unittest.mock.patch.object(ci, "SINCE_PAGES", ()):
            self.read(fake)
            fake.runs["build.yml"] += [attempt_run(n, n, day=f"2026-10-{20 + n % 4:02d}",
                                                   conclusion="failure" if n == 9 else "success") for n in range(2, 14)]
            code, report = self.read(fake)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(i[0] for i in self.new(report)), list(range(2, 14)))

    def test_a_full_day_is_split_down_to_the_second(self):
        # Reconciliation 3 P2: a day with more runs than one list holds is split by the hour, the minute, the second.
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        with unittest.mock.patch.object(ci, "LIST_LIMIT", 5), unittest.mock.patch.object(ci, "SINCE_PAGES", ()):
            self.read(fake)
            fake.runs["build.yml"] += [attempt_run(n, n, conclusion="failure" if n == 7 else "success")
                                       for n in range(2, 12)]
            code, report = self.read(fake)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(i[0] for i in self.new(report)), list(range(2, 12)))

    def test_more_runs_in_one_second_than_a_list_holds_leave_the_state_and_say_so(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        before = self.cursor()
        fake.runs["build.yml"] += [attempt_run(n, 5) for n in range(2, 9)]   # seven runs created in one second
        out = io.StringIO()
        with unittest.mock.patch.object(ci, "LIST_LIMIT", 5), unittest.mock.patch.object(ci, "SINCE_PAGES", ()), redirect_stdout(out):
            code = ci.main(["--since-last"], runner=fake, root=self.root)
        self.assertEqual(code, 3)
        self.assertIn("the cursor is left where it was", out.getvalue())
        self.assertEqual(self.cursor(), before)

    def test_a_first_read_after_a_long_idle_reports_the_latest_run(self):
        # Reconciliation 3 P1: the latest completed run is older than the reach.
        fake = PagedGh({"build.yml": [attempt_run(1, 1, day="2026-09-01", conclusion="failure")]})
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(1, 1, "red")]))

    def test_a_cursor_of_the_earlier_format_keeps_what_it_had_not_read(self):
        # Reconciliation 4 P1: a cursor with only a horizon (September 1) and an unread failure after it.
        from datetime import datetime, timezone
        (self.root / ci.CURSOR).parent.mkdir(parents=True)
        (self.root / ci.CURSOR).write_text(json.dumps({"main|build.yml": {"horizon": "2026-09-01T00:00:00Z",
                                                                          "seen": []}}), encoding="utf-8")
        fake = PagedGh({"build.yml": [attempt_run(1, 1, day="2026-08-31"),
                                      attempt_run(2, 1, day="2026-09-02", conclusion="failure")]})
        with unittest.mock.patch.object(ci, "_now", return_value=datetime(2026, 11, 17, tzinfo=timezone.utc)):
            code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(2, 1, "red")]))

    def test_the_lists_page_ten_fifty_and_two_hundred_before_a_full_list(self):
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        fake.runs["build.yml"] += [attempt_run(n, n) for n in range(2, 80)]
        fake.calls.clear()
        self.read(fake)
        limits = [c[c.index("--limit") + 1] for c in fake.calls if c[:2] == ["run", "list"]]
        self.assertEqual(limits, ["10", "50", "200"])

    def test_a_rerun_of_a_run_created_long_before_the_read_is_reported(self):
        # Reconciliation 2 P1, the reviewer's case moved earlier: run 1 created October 10 and reported green on November 1;
        # rerun November 8 (within GitHub's 30 days) and failed; read November 17, 38 days after it was created.
        from datetime import datetime, timezone
        fake = PagedGh({"build.yml": [attempt_run(1, 1, day="2026-10-10")]})
        with unittest.mock.patch.object(ci, "_now", return_value=datetime(2026, 11, 1, tzinfo=timezone.utc)):
            self.read(fake)
        fake.runs["build.yml"] = [attempt_run(1, 1, day="2026-10-10", conclusion="failure", attempt=2)]
        with unittest.mock.patch.object(ci, "_now", return_value=datetime(2026, 11, 17, tzinfo=timezone.utc)):
            code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(1, 2, "red")]))

    def test_a_rerun_of_an_older_run_far_down_the_list_is_reported_once(self):
        # Reconciliation 1 P1, the reviewer's own case: run 1 reported green, 58 newer runs reported, then run 1 is
        # rerun outside this tool and fails.
        fake = PagedGh({"build.yml": [attempt_run(1, 1)]})
        self.read(fake)
        fake.runs["build.yml"] += [attempt_run(n, n) for n in range(2, 60)]
        self.read(fake)
        fake.runs["build.yml"][0] = attempt_run(1, 1, conclusion="failure", attempt=2)
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(1, 2, "red")]))
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (0, []), "reported once")

    def test_a_rerun_of_an_older_run_is_reported(self):
        # Round 1 P1: run 1 and a newer run 2 were read; run 1 is rerun (its creation time stays old) and fails.
        fake = PagedGh({"build.yml": [attempt_run(1, 1), attempt_run(2, 2)]})
        self.read(fake)
        fake.runs["build.yml"][0] = attempt_run(1, 1, conclusion="failure", attempt=2)
        code, report = self.read(fake)
        self.assertEqual((code, self.new(report)), (1, [(1, 2, "red")]))

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
    """`--rerun <commit>`: the candidate's own cancelled run, never the tip's, on an idle queue; a red goes to red first."""

    def setUp(self):
        from datetime import datetime, timezone
        clock = unittest.mock.patch.object(ci, "_now", return_value=datetime(2026, 11, 1, tzinfo=timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
        self._tmp = Scratch()
        self.root = Path(self._tmp.name)
        workspace(self.root, workflows=("build.yml",))

    def tearDown(self):
        self._tmp.cleanup()

    def rerun(self, fake, *flags, commit=SHA_OLD):
        out = io.StringIO()
        with redirect_stdout(out):
            code = ci.main(["--rerun", commit, *flags], runner=fake, root=self.root)
        return code, out.getvalue()

    def test_an_infrastructure_red_is_rerun_or_run_afresh(self):
        # The stamp-evidence review, round 8: the red-first rule's infrastructure rerun, inside and past the window.
        from datetime import datetime, timezone
        fake = PagedGh({"build.yml": [attempt_run(7, 7, conclusion="failure", sha=SHA_OLD)]})
        code, said = self.rerun(fake, "--infrastructure")
        self.assertEqual(code, 0, said)
        self.assertIn(["run", "rerun", "7", "--failed"], fake.calls)

    def test_a_candidate_with_no_run_of_its_own_is_written_as_open(self):
        fake = PagedGh({"build.yml": [attempt_run(8, 8)]})
        code, said = self.rerun(fake)
        self.assertEqual((code, fake.reruns()), (1, []))
        self.assertIn("write it in the run file as open", said)

    def test_a_red_candidate_is_repaired_not_rerun(self):
        # The stamp-evidence review, round 4: a red has its verdict; reruns for infrastructure belong to red first.
        fake = PagedGh({"build.yml": [attempt_run(7, 7, conclusion="failure", sha=SHA_OLD)]})
        code, said = self.rerun(fake)
        self.assertEqual((code, fake.reruns()), (1, []))
        self.assertIn("repair it red first", said)

    def test_a_rerun_a_push_dropped_is_started_again_uncounted(self):
        fake = PagedGh({"build.yml": [attempt_run(7, 7, conclusion="cancelled", sha=SHA_OLD)]})
        for _ in range(5):
            code, said = self.rerun(fake)
            self.assertEqual(code, 0, said)
            self.assertIn("(a run a push cancelled)", said)
            run = fake.runs["build.yml"][0]
            fake.runs["build.yml"][0] = attempt_run(7, 7, conclusion="cancelled", sha=SHA_OLD, attempt=run["attempt"] + 1)
        self.assertEqual(len(fake.reruns()), 5)

    def test_an_older_running_run_keeps_the_queue_busy(self):
        # The stamp-evidence review: a running build older than the newest ten runs still holds the queue.
        fake = PagedGh({"build.yml": [attempt_run(7, 1, conclusion="cancelled", sha=SHA_OLD),
                                      attempt_run(8, 2, status="in_progress")] +
                                     [attempt_run(n, n) for n in range(9, 30)]})
        code, said = self.rerun(fake)
        self.assertEqual((code, fake.reruns()), (5, []))

    def test_the_candidate_is_found_however_many_runs_came_after_it(self):
        # Reconciliation 5 P2: a cancelled candidate followed by 60 newer runs.
        fake = PagedGh({"build.yml": [attempt_run(7, 1, conclusion="cancelled", sha=SHA_OLD)] +
                                     [attempt_run(n, n) for n in range(8, 68)]})
        code, said = self.rerun(fake)
        self.assertEqual(code, 0, said)
        self.assertEqual(fake.reruns(), ["7"])

    def test_a_busy_queue_is_try_again_and_not_counted(self):
        # The stamp-evidence review: a rerun queued behind another run could be dropped by the next push, so one is
        # started only on an idle queue, where it runs to its verdict.
        fake = PagedGh({"build.yml": [attempt_run(7, 1, conclusion="cancelled", sha=SHA_OLD),
                                      attempt_run(8, 2, status="in_progress")]})
        for _ in range(4):
            code, said = self.rerun(fake)
            self.assertEqual(code, 5, said)
            self.assertIn("when the queue is idle", said)
        self.assertEqual(fake.reruns(), [])
        fake.runs["build.yml"][1] = attempt_run(8, 2)
        code, said = self.rerun(fake)
        self.assertEqual((code, fake.reruns()), (0, ["7"]))
        self.assertIn("(a run a push cancelled)", said)

    def test_a_green_or_running_candidate_is_left_and_a_refused_rerun_is_reported(self):
        self.assertIn("nothing to rerun", self.rerun(PagedGh({"build.yml": [attempt_run(7, 7, sha=SHA_OLD)]}))[1])
        refused = PagedGh({"build.yml": [attempt_run(7, 7, conclusion="cancelled", sha=SHA_OLD)]}, rerun_code=1)
        code, said = self.rerun(refused)
        self.assertEqual(code, 1, said)   # GitHub's refusal is said, and the candidate is written as open
        self.assertIn("was refused (the run cannot be rerun); write aaaaaaaaaaaa in the run file as open", said)

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
