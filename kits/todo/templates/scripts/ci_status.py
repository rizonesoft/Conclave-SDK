#!/usr/bin/env python3
"""Report the CI state of main: the latest completed run of each watched workflow, and runs still in progress.

    python scripts/ci_status.py                  # the watched workflows on main
    python scripts/ci_status.py --json           # the same report as one JSON object
    python scripts/ci_status.py --workflow build.yml --branch main
    python scripts/ci_status.py --since-last     # every run that finished since the last read, each failure named
    python scripts/ci_status.py --rerun <commit> # rerun a stamp candidate's own cancelled or failed run, at most 3 times

For each watched workflow it reads the last 10 runs with `gh run list` and reports the latest completed run (green, red or cancelled), its verdict,
and how many newer runs are still queued or in progress. A cancelled run carries no verdict (a newer push usually
superseded it), so the verdict is the latest completed run that was not cancelled; with none in the last 10 runs the
verdict is `none`. For a red verdict it names the failed jobs from `gh run view <id> --json jobs`.

The watched workflows are the `--workflow` arguments, else the `workflows` list in `.conclave/ci.json` (the ones whose
results gate main), else every `.yml` and `.yaml` file in `.github/workflows/`.

Runs still queued or in progress are named with their commit and URL, older ones included.

`--since-last` reads every run created since a horizon kept in `build/ci-status-cursor.json` (per branch and
workflow): the creation time of the oldest run still unfinished at the last read, else the newest run then listed.
It reports each completed attempt it has not reported before, by run ID and attempt (a rerun's earlier attempts are
read too), so a failure followed by a green, a run that finishes after a newer one, or a failed rerun of a run already
reported are each seen once; the runs `--rerun` started, and every run whose last attempt was red or cancelled
(for seven days), are read by ID, so a rerun of them is seen wherever it is on the list. It pages (50, 200, 1000 runs) until it passes the horizon, and with more than 1000 unread runs it says so and
leaves the state as it was (exit 3) rather than skip any. The state is written after the
read printed everything, and never when a read failed; an unreadable state is said and read as a first read, which
reports the latest completed run and everything after it. The process-phase skill reads it after every push; nothing
in it refuses or holds back a commit or a push.

`--rerun <commit>` reruns, with `gh run rerun`, the latest run of each watched workflow on that commit when a newer
push cancelled it or it failed, so a stamp candidate gets a verdict of its own; the count is kept per commit in
`build/ci-status-reruns.json`, and a fourth rerun is refused (exit 4). Evidence never moves to another commit.

Exit 0: no watched workflow is red. Exit 1: at least one is red (the workflow, the commit, the run's URL and its
failed jobs are printed). Exit 2: bad usage. Exit 3: `gh` is missing, not authenticated, or failed, so the state is
unknown; that is never treated as green. The red-first policy that consumes this is in the `process-phase` skill.
Stdlib only; the `gh` runner is injectable for tests.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(".conclave") / "ci.json"
FIELDS = "databaseId,headSha,status,conclusion,url,createdAt,event,attempt"
CURSOR = Path("build") / "ci-status-cursor.json"
RERUNS = Path("build") / "ci-status-reruns.json"
PAGES = (50, 200, 1000)
MAX_RERUNS = 3
WATCH_DAYS = 7   # how long a red or cancelled run is read by ID for a rerun
LIMIT = 10
GREEN = {"success", "neutral", "skipped"}
# A run that was stopped before it judged the commit: no verdict either way.
NO_VERDICT = {"cancelled", "stale"}
MAX_JOBS = 20
MAX_MESSAGE = 300


class Unavailable(Exception):
    """gh is missing, unauthenticated or failed: the CI state is unknown (exit 3)."""


def run_gh(args):
    """Run gh with args; returns (exit code, stdout, stderr). Raises Unavailable when gh is not installed."""
    # An explicit path: on Windows a bare which() also searches the working directory, where a planted gh could sit.
    executable = shutil.which("gh", path=os.environ.get("PATH", ""))
    if executable is None:
        raise Unavailable("gh is not installed or not on PATH")
    try:
        done = subprocess.run([executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unavailable(f"gh could not run: {exc}") from None
    return done.returncode, done.stdout, done.stderr


def gh_json(runner, args):
    try:
        code, out, err = runner(args)
    except FileNotFoundError:
        raise Unavailable("gh is not installed or not on PATH") from None
    if code != 0:
        reason = (err or out or "").strip().splitlines()
        raise Unavailable(f"gh {' '.join(args[:2])} exited {code}: {(reason[0] if reason else 'no output')[:MAX_MESSAGE]}")
    try:
        return json.loads(out)
    except ValueError:
        raise Unavailable(f"gh {' '.join(args[:2])} did not return JSON") from None


def watched(root):
    """The workflows .conclave/ci.json names, else every workflow file; a malformed config is a usage error."""
    path = Path(root) / CONFIG
    if path.is_file():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            raise ValueError(f"{CONFIG.as_posix()} is not JSON") from None
        names = doc.get("workflows") if isinstance(doc, dict) else None
        if names is not None:
            if not (isinstance(names, list) and all(isinstance(n, str) and n for n in names)):
                raise ValueError(f"{CONFIG.as_posix()} workflows must be a list of workflow file names")
            return list(names)
    directory = Path(root) / ".github" / "workflows"
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml"))


def verdict_of(run):
    if run is None:
        return "none"
    conclusion = (run.get("conclusion") or "").lower()
    if conclusion in GREEN:
        return "green"
    if conclusion in NO_VERDICT:
        return "cancelled"
    return "red"


def brief(run):
    return None if run is None else {k: run.get(k) for k in ("databaseId", "headSha", "status", "conclusion", "url",
                                                              "createdAt", "event", "attempt")}


def list_runs(runner, workflow, branch, limit=LIMIT):
    runs = gh_json(runner, ["run", "list", "--branch", branch, "--workflow", workflow, "--limit", str(limit),
                            "--json", FIELDS])
    if not isinstance(runs, list) or not all(isinstance(r, dict) for r in runs):
        raise Unavailable(f"gh run list for {workflow} did not return a list of runs")
    return sorted(runs, key=lambda r: str(r.get("createdAt") or ""), reverse=True)


def pending_of(runs):
    """Every run still queued or in progress, newest first, with its commit and URL."""
    return [brief(r) for r in runs if r.get("status") != "completed"]


def workflow_status(runner, workflow, branch):
    runs = list_runs(runner, workflow, branch)
    completed = [r for r in runs if r.get("status") == "completed"]
    latest = completed[0] if completed else None
    decisive = next((r for r in completed if verdict_of(r) != "cancelled"), None)
    newer = [r for r in runs if r.get("status") != "completed"
             and (latest is None or str(r.get("createdAt") or "") > str(latest.get("createdAt") or ""))]
    entry = {"workflow": workflow, "verdict": verdict_of(decisive), "latest_completed": brief(latest),
             "latest_completed_state": verdict_of(latest), "verdict_run": brief(decisive), "in_progress": len(newer),
             "pending": pending_of(runs)}
    if entry["verdict"] == "red":
        entry["failed_jobs"] = failed_jobs(runner, decisive.get("databaseId"))
    return entry


def failed_jobs(runner, run_id):
    """The failed jobs of one run, or a one-line note when they cannot be read (the run is still red)."""
    try:
        view = gh_json(runner, ["run", "view", str(run_id), "--json", "jobs"])
    except Unavailable as exc:
        return [{"name": f"jobs unavailable: {exc}", "conclusion": None, "url": None}]
    jobs = view.get("jobs") if isinstance(view, dict) else None
    if not isinstance(jobs, list):
        return [{"name": "jobs unavailable: gh run view returned no job list", "conclusion": None, "url": None}]
    failed = [j for j in jobs if isinstance(j, dict) and verdict_of(j) == "red" and j.get("status") == "completed"]
    return [{"name": j.get("name"), "conclusion": j.get("conclusion"), "url": j.get("url")} for j in failed[:MAX_JOBS]]


def report(runner, workflows, branch):
    """The report dict and its exit code; Unavailable propagates (exit 3)."""
    entries = [workflow_status(runner, w, branch) for w in workflows]
    code = 1 if any(e["verdict"] == "red" for e in entries) else 0
    return {"branch": branch, "workflows": entries, "exit": code}, code


def describe(entry):
    run = entry["verdict_run"]
    where = f" at {run['headSha'][:12]} ({run['url']})" if run and run.get("headSha") and run.get("url") else ""
    lines = [f"{entry['workflow']}: {entry['verdict']}{where}"]
    if entry["latest_completed_state"] == "cancelled":
        lines.append(f"  latest completed run was cancelled: {entry['latest_completed']['url']}")
    if entry["in_progress"]:
        lines.append(f"  {entry['in_progress']} newer run(s) still queued or in progress")
    for run in entry.get("pending", []):
        lines.append(f"  still running: {(run.get('headSha') or '')[:12]} {run.get('status')} {run.get('url')}")
    for job in entry.get("failed_jobs", []):
        lines.append(f"  failed job: {job['name']} ({job['conclusion']}) {job['url'] or ''}".rstrip())
    return lines


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _load_state(path):
    """(state, note): the saved state, or {} with why when there is none or it cannot be read."""
    if not path.exists():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
            raise ValueError("not an object of objects")
        return data, None
    except (OSError, ValueError) as exc:
        return {}, f"{path.name} could not be read ({exc}); read as a first read, and replaced after this read"


def _attempt_conclusion(runner, run_id, attempt):
    view = gh_json(runner, ["api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/attempts/{attempt}"])
    if not isinstance(view, dict):
        raise Unavailable(f"gh api for run {run_id} attempt {attempt} did not return an object")
    return view.get("status"), view.get("conclusion"), view.get("html_url") or view.get("url")


def since_last(runner, workflows, branch, root):
    """The new completed attempts since the last read, the pending runs, the new state and the exit code.

    Per branch and workflow the state keeps a horizon (the creation time of the oldest run still unfinished at the
    last read, else the newest run then listed) and, for each run it has seen, the highest attempt it reported. A run
    is read again whenever its attempt number is above that, so a rerun of an older run is reported too, and the runs
    `--rerun` started are read by ID even when newer runs push them off the list. Reading pages until it passes the
    horizon, it raises Unavailable (exit 3, state untouched) rather than skip runs it could not reach."""
    path = Path(root) / CURSOR
    state, note = _load_state(path)
    new_state = dict(state)
    reruns, _ = _load_state(Path(root) / RERUNS)
    report = {"branch": branch, "workflows": [], "note": note}
    failed = False
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for workflow in workflows:
        key = f"{branch}|{workflow}"
        saved = state.get(key)
        horizon = saved.get("horizon") if saved else None
        reported = {str(k): int(v) for k, v in (saved.get("reported", {}) if saved else {}).items()}
        # Runs whose last reported attempt was red or cancelled, by ID with when that was reported: the ones someone
        # reruns. They are read by ID for WATCH_DAYS, so a rerun is seen even after newer runs push them off the list.
        watching = dict(saved.get("watching", {})) if saved else {}
        runs = []
        for limit in PAGES:
            runs = list_runs(runner, workflow, branch, limit)
            if horizon is None or len(runs) < limit or str(runs[-1].get("createdAt") or "") < horizon:
                break
        else:
            if runs and str(runs[-1].get("createdAt") or "") >= horizon:
                raise Unavailable(f"more than {PAGES[-1]} runs of {workflow} since the last read; the cursor is left "
                                  f"where it was, so nothing is skipped (read them with gh run list)")
        listed = {str(r.get("databaseId")) for r in runs}
        # The runs --rerun started and the red or cancelled runs being watched, read by ID when they are not on the
        # list any more.
        off_list = [str(e.get("run")) for k, e in reruns.items() if k.endswith(f"|{workflow}") and e.get("run")]
        off_list += list(watching)
        for run_id in dict.fromkeys(off_list):
            if run_id not in listed:
                view = gh_json(runner, ["run", "view", run_id, "--json", FIELDS])
                if isinstance(view, dict):
                    runs.append(view)
                    listed.add(str(view.get("databaseId")))
        if horizon is None:
            # A first read: the latest completed run and everything after it; what came before counts as reported.
            completed = sorted((r for r in runs if r.get("status") == "completed"),
                               key=lambda r: str(r.get("createdAt") or ""), reverse=True)
            first = str(completed[0].get("createdAt") or "") if completed else ""
            for r in runs:
                if str(r.get("createdAt") or "") < first and r.get("status") == "completed":
                    reported[str(r.get("databaseId"))] = int(r.get("attempt") or 1)
        new = []
        for run in sorted(runs, key=lambda r: str(r.get("createdAt") or "")):
            run_id = str(run.get("databaseId"))
            attempts = int(run.get("attempt") or 1)
            done = reported.get(run_id, 0)
            if horizon is not None and run_id not in reported and str(run.get("createdAt") or "") < horizon:
                continue   # older than the last read and never listed then: read before this state began
            for n in range(done + 1, attempts + 1):
                if n == attempts:
                    if run.get("status") != "completed":
                        break
                    conclusion, url = run.get("conclusion"), run.get("url")
                else:
                    status, conclusion, url = _attempt_conclusion(runner, run_id, n)
                    if status != "completed":
                        break
                verdict = verdict_of({"conclusion": conclusion})
                item = {"run": run.get("databaseId"), "attempt": n, "headSha": run.get("headSha"), "url": url,
                        "verdict": verdict}
                if verdict == "red":
                    failed = True
                    if n == attempts:
                        item["failed_jobs"] = failed_jobs(runner, run_id)
                new.append(item)
                reported[run_id] = n
                if verdict in ("red", "cancelled"):
                    watching[run_id] = now   # watched for WATCH_DAYS from when it was reported
                else:
                    watching.pop(run_id, None)
        # Every run still unfinished: the next read starts at the oldest of them, so each is read until it finishes.
        unfinished = [str(r.get("createdAt") or "") for r in runs if r.get("status") != "completed"]
        newest = max((str(r.get("createdAt") or "") for r in runs), default=horizon or "")
        next_horizon = min(unfinished) if unfinished else newest
        cutoff = (datetime.now(timezone.utc) - timedelta(days=WATCH_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        watching = {k: v for k, v in sorted(watching.items()) if v >= cutoff}
        new_state[key] = {"horizon": next_horizon, "watching": watching,
                          "reported": {k: v for k, v in sorted(reported.items()) if k in listed or k in watching}}
        report["workflows"].append({"workflow": workflow, "new": new, "pending": pending_of(runs)})
    code = 1 if failed else 0
    report["exit"] = code
    return report, new_state, code


def describe_since(report):
    lines = [f"ci-status: {report['note']}"] if report.get("note") else []
    for entry in report["workflows"]:
        if not entry["new"] and not entry["pending"]:
            lines.append(f"{entry['workflow']}: nothing new since the last read")
        for item in entry["new"]:
            again = f" (attempt {item['attempt']})" if item["attempt"] > 1 else ""
            lines.append(f"{entry['workflow']}: {item['verdict']}{again} at {(item['headSha'] or '')[:12]} {item['url']}")
            for job in item.get("failed_jobs", []):
                lines.append(f"  failed job: {job['name']} ({job['conclusion']}) {job['url'] or ''}".rstrip())
        for run in entry["pending"]:
            lines.append(f"{entry['workflow']}: still running at {(run.get('headSha') or '')[:12]} {run.get('url')}")
    return lines


def rerun(runner, workflows, branch, commit, root):
    """Rerun the candidate's own latest run per workflow when it was cancelled or red. Returns (lines, exit code)."""
    path = Path(root) / RERUNS
    counts, note = _load_state(path)
    lines = [f"ci-status: {note}"] if note else []
    code = 0
    for workflow in workflows:
        runs = [r for r in list_runs(runner, workflow, branch, PAGES[1]) if r.get("headSha") == commit]
        if not runs:
            lines.append(f"{workflow}: no run of {commit[:12]} in the last {PAGES[1]} runs")
            code = max(code, 1)
            continue
        run = runs[0]
        state = verdict_of(run) if run.get("status") == "completed" else "running"
        if state in ("green", "running"):
            lines.append(f"{workflow}: {commit[:12]} is {state} ({run.get('url')}); nothing to rerun")
            continue
        key = f"{commit}|{workflow}"
        done = int(counts.get(key, {}).get("reruns", 0))
        if done >= MAX_RERUNS:
            lines.append(f"{workflow}: {commit[:12]} was rerun {done} times already ({run.get('url')}); not again: "
                         f"write it as open in the run file")
            code = 4
            continue
        result, out, err = runner(["run", "rerun", str(run.get("databaseId"))])
        if result != 0:
            reason = (err or out or "").strip().splitlines()
            lines.append(f"{workflow}: gh run rerun {run.get('databaseId')} was refused: "
                         f"{(reason[0] if reason else 'no output')[:MAX_MESSAGE]}")
            code = max(code, 1) if code != 4 else code
            continue
        counts[key] = {"reruns": done + 1, "run": run.get("databaseId")}
        lines.append(f"{workflow}: reran {run.get('url')} on {commit[:12]} (rerun {done + 1} of {MAX_RERUNS})")
    _write_atomic(path, counts)
    return lines, code


def main(argv=None, runner=run_gh, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="print the report as one JSON object")
    parser.add_argument("--branch", default="main", help="the branch whose runs are read (default main)")
    parser.add_argument("--workflow", action="append", dest="workflows",
                        help="a workflow file in .github/workflows/ (repeatable; default: .conclave/ci.json, else all)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--since-last", action="store_true", help="every run that finished since the last read")
    mode.add_argument("--rerun", metavar="COMMIT", help="rerun this commit's own cancelled or failed runs")
    args = parser.parse_args(argv)
    directory = Path(root) / ".github" / "workflows"
    try:
        workflows = args.workflows or watched(root)
    except ValueError as exc:
        parser.error(str(exc))
    missing = [w for w in workflows if "/" in w or "\\" in w or not (directory / w).is_file()]
    if missing or not workflows or not args.branch.strip():
        parser.error(f"no such workflow in .github/workflows/: {', '.join(missing)}" if missing
                     else "no workflow to watch, or an empty --branch")
    if args.rerun is not None and not (len(args.rerun) == 40 and all(c in "0123456789abcdef" for c in args.rerun)):
        parser.error("--rerun takes a full 40-character commit")
    try:
        if args.rerun is not None:
            lines, code = rerun(runner, workflows, args.branch, args.rerun, root)
            print("\n".join(lines))
            return code
        if args.since_last:
            result, new_state, code = since_last(runner, workflows, args.branch, root)
            print(json.dumps(result, indent=2) if args.json else "\n".join(describe_since(result)))
            sys.stdout.flush()
            try:
                _write_atomic(Path(root) / CURSOR, new_state)   # only after everything was printed
            except OSError as exc:
                print(f"ci-status: the cursor could not be written ({exc}); the next read reports these runs again")
            return code
        result, code = report(runner, workflows, args.branch)
    except Unavailable as exc:
        if args.json:
            print(json.dumps({"branch": args.branch, "error": str(exc), "exit": 3}))
        else:
            print(f"ci-status unknown: {exc}")
        return 3
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for entry in result["workflows"]:
            print("\n".join(describe(entry)))
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
