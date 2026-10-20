#!/usr/bin/env python3
"""Run one independent review round with the reviewers pinned in .conclave/reviewers.toml, failing over in order.

    python3 scripts/review-dispatch.py --writer claude --prompt review-prompt.md --record docs/reviews/x.md
    python3 scripts/review-dispatch.py --check-pin [--json] [--pin <path>]     the pin's verdict; runs no reviewer
    python3 scripts/review-dispatch.py --list-rounds [--json] [--records <dir>]  recorded rounds; runs no reviewer

`--writer` is the agent whose work is under review (claude, codex or gemini); its route in the pin lists one reviewer
of a different model family and at most one fallback, also of a different family. The first reviewer that runs and
returns a review is the round. One that is not installed, exits non-zero, times out, returns nothing, or ends its
reply `OVERALL: blocked` (it could not reach the candidate, for example a sandbox that cannot read the repository) is
skipped and the reason recorded. When every reviewer fails there is no review: exit 1, which never counts as approval.
A review that finds problems is still a review (exit 0).

`--check-pin` loads the pin with `load_pin`, the only place the rules live, and reports without running anything:
with `--json`, `{"ok": true, "schema_version", "reviewers", "routes", "clis": {cli: on PATH}}` and exit 0, or
`{"ok": false, "error": "<the Refused message>"}` and exit 2; without `--json`, `ok` or `refused: <message>`.

Reviewers run read-only in the repository root: Codex in its read-only sandbox, Antigravity in plan mode inside its
sandbox, Claude Code in plan mode. The script prints a JSON summary; `--record` also appends a `## Round N` section to
the findings file with an atomic write. Works the same from PowerShell and from WSL. Stdlib only.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / ".conclave" / "reviewers.toml"
WRITERS = ("claude", "codex", "gemini")
CLIS = ("codex", "agy", "claude")
# A reviewer is never of the writer's own model family: its CLI names the family, and so does the writer.
FAMILY = {"codex": "openai", "agy": "google", "claude": "anthropic"}
WRITER_FAMILY = {"claude": "anthropic", "codex": "openai", "gemini": "google"}
EFFORTS = {"codex": ("low", "medium", "high", "xhigh"), "claude": ("low", "medium", "high", "xhigh", "max")}
MODEL = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# Antigravity takes the prompt only as the -p value. Past this size it gets a pointer to the prompt file instead.
# Windows caps a whole command line at 32,767 characters; Linux caps one argument at 128 KiB.
ARGV_PROMPT_LIMIT = 24_000 if os.name == "nt" else 100_000
# A review is prose. Output past this size is a runaway reviewer, not a review.
MAX_OUTPUT_BYTES = 2_000_000
# The prompt's reply format ends with an OVERALL line; `blocked` means the reviewer never saw the work.
BLOCKED = re.compile(r"^\s*OVERALL:\s*blocked\b", re.IGNORECASE)
POLL_SECONDS = 0.2
CLEANUP_SECONDS = 10


class Refused(Exception):
    """The pin or the arguments are wrong; nothing ran."""


def load_pin(path=PIN):
    try:
        with open(path, "rb") as handle:
            pin = tomllib.load(handle)
    except FileNotFoundError:
        raise Refused(f"no reviewer pin at {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise Refused(f"unreadable reviewer pin: {exc}") from None
    # A directory, a file it may not read, bytes that are not UTF-8, an integer past Python's digit limit, or nesting
    # deep enough to exhaust the parser's recursion: each is a pin that cannot be read, so it is a refusal (exit 2,
    # one JSON object), never a traceback. ValueError comes after its subclasses TOMLDecodeError and UnicodeDecodeError.
    except OSError as exc:
        raise Refused(f"unreadable reviewer pin: {exc.strerror or exc}: {path}") from None
    except UnicodeDecodeError:
        raise Refused("unreadable reviewer pin: not UTF-8 text") from None
    except ValueError as exc:
        raise Refused(f"unreadable reviewer pin: {exc}") from None
    except RecursionError:
        raise Refused("unreadable reviewer pin: nested too deeply to read") from None
    # `type(...) is int`: TOML true is Python True (an int subclass) and 1.0 == 1, so `!= 1` alone let both load.
    if set(pin) != {"schema_version", "reviewers", "routes"} or type(pin["schema_version"]) is not int \
            or pin["schema_version"] != 1:
        raise Refused("the reviewer pin needs exactly schema_version = 1, [reviewers.*] and [routes]")
    reviewers = pin["reviewers"]
    if not isinstance(reviewers, dict) or not reviewers:
        raise Refused("the reviewer pin defines no reviewers")
    for name, entry in reviewers.items():
        if not NAME.match(name) or not isinstance(entry, dict):
            raise Refused(f"invalid reviewer {name!r}")
        unknown = set(entry) - {"cli", "model", "effort"}
        if unknown:
            raise Refused(f"reviewer {name!r} has unknown keys: {', '.join(sorted(unknown))}")
        cli, model, effort = entry.get("cli"), entry.get("model"), entry.get("effort")
        if cli not in CLIS:
            raise Refused(f"reviewer {name!r} needs cli = one of {', '.join(CLIS)}")
        if not isinstance(model, str) or not MODEL.match(model):
            raise Refused(f"reviewer {name!r} has a malformed model")
        if cli == "agy":
            if effort is not None:
                raise Refused(f"reviewer {name!r}: Antigravity carries the effort in the model name, so set no effort")
        elif effort not in EFFORTS[cli]:
            raise Refused(f"reviewer {name!r} needs effort = one of {', '.join(EFFORTS[cli])}")
    routes = pin["routes"]
    if not isinstance(routes, dict) or set(routes) - set(WRITERS):
        raise Refused(f"[routes] may only name the writers {', '.join(WRITERS)}")
    for writer, chain in routes.items():
        if not isinstance(chain, list) or not 1 <= len(chain) <= 2 or not all(isinstance(r, str) for r in chain):
            raise Refused(f"route {writer!r} must list one reviewer and at most one fallback")
        if any(r not in reviewers for r in chain) or len(set(chain)) != len(chain):
            raise Refused(f"route {writer!r} must list defined reviewers, each once")
        same = [r for r in chain if FAMILY[reviewers[r]["cli"]] == WRITER_FAMILY[writer]]
        if same:
            raise Refused(f"route {writer!r} names {', '.join(same)}, of the writer's own family; "
                          f"a review comes from a different family")
        if len({FAMILY[reviewers[r]["cli"]] for r in chain}) != len(chain):
            raise Refused(f"route {writer!r}: the fallback must be of a third family, not the reviewer's own")
    return pin


def command(reviewer, executable, prompt, prompt_path, output_path, timeout):
    """The argv and stdin for one read-only review. The model and effort come only from the pin."""
    cli, model, effort = reviewer["cli"], reviewer["model"], reviewer.get("effort")
    if cli == "codex":
        return [executable, "exec", "-m", model, "-c", f"model_reasoning_effort={effort}", "--sandbox", "read-only",
                "--ephemeral", "--skip-git-repo-check", "-o", str(output_path), "-"], prompt
    if cli == "claude":
        return [executable, "-p", "--model", model, "--effort", effort, "--permission-mode", "plan"], prompt
    text = prompt
    # A Windows .cmd or .bat shim re-parses its arguments through cmd.exe, so prose there could become commands:
    # it only ever gets a pointer to the prompt file. So does a prompt too long for a command line.
    shim = Path(executable).suffix.lower() in (".cmd", ".bat")
    if shim or len(prompt.encode()) > ARGV_PROMPT_LIMIT or len(prompt) > ARGV_PROMPT_LIMIT:
        text = f"Follow the review instructions in the file {prompt_path} exactly. Do not modify any file."
    return [executable, "--model", model, "--mode", "plan", "--sandbox", "--print-timeout", f"{timeout}s", f"-p={text}"], None


def kill_tree(process):
    """End a reviewer and everything it started, whether it is still running or has already exited."""
    if os.name == "nt":
        # WORKAROUND: Windows offers no process-group kill without job objects, so taskkill /T reaches the reviewer's
        # children only while the reviewer itself is alive. A child that outlives a reviewer which exited by itself
        # is not reached on Windows; on Linux and WSL the whole session is killed below.
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # nothing in the group is left to kill


def remove_scratch(path):
    """Remove a reviewer's scratch directory. On Windows a file stays locked until every process holding it has
    exited, and a reviewer's helper can outlive the reviewer (see kill_tree) and keep writing into it, so a failed
    removal is retried for a bounded time. A directory that still cannot be removed is left behind with a note: the
    round's outcome is already decided."""
    deadline = time.monotonic() + CLEANUP_SECONDS
    while True:
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            if time.monotonic() > deadline:
                print(f"review-dispatch: left {path} behind ({exc.strerror or type(exc).__name__})", file=sys.stderr)
                return
            time.sleep(POLL_SECONDS)


def feed(pipe, text):
    try:
        pipe.write(text.encode("utf-8"))
        pipe.close()
    except (BrokenPipeError, OSError):
        pass  # the reviewer stopped reading or exited; its exit code and output decide the round


def run(argv, stdin_text, timeout, watched):
    """Run one reviewer in its own process group, watching the size of every file it writes while it runs, so neither
    a hang nor a flood of output can take the dispatcher or the disk down. The group is ended afterwards whatever
    happened. Returns (exit code, None) or (None, reason to fail over)."""
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    stdout_path = watched[0]
    with open(stdout_path, "wb") as output:
        try:
            process = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.DEVNULL, **group)
        except (OSError, ValueError) as exc:
            return None, f"could not start: {getattr(exc, 'strerror', None) or type(exc).__name__}"
        try:
            if stdin_text is not None:
                # Fed from a thread: a reviewer that never reads would otherwise block this write past any timeout.
                threading.Thread(target=feed, args=(process.stdin, stdin_text), daemon=True).start()
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if any(path.is_file() and path.stat().st_size > MAX_OUTPUT_BYTES for path in watched):
                    return None, f"returned more than {MAX_OUTPUT_BYTES} bytes"
                if time.monotonic() > deadline:
                    return None, "timed out"
                time.sleep(POLL_SECONDS)
        finally:
            kill_tree(process)
            process.wait()
    if process.returncode != 0:
        return None, f"exited {process.returncode}"
    if any(path.is_file() and path.stat().st_size > MAX_OUTPUT_BYTES for path in watched):
        return None, f"returned more than {MAX_OUTPUT_BYTES} bytes"
    return process.returncode, None


def review(pin, writer, prompt_path, timeout):
    """Walk the writer's route until one reviewer returns a review. Returns the summary dict."""
    if writer not in pin["routes"]:
        raise Refused(f"the reviewer pin has no route for writer {writer!r}")
    prompt = Path(prompt_path).read_text(encoding="utf-8")
    if not prompt.strip():
        raise Refused("the review prompt is empty")
    if "\0" in prompt:
        raise Refused("the review prompt contains a NUL byte; no command line can carry it")
    failover = []
    for name in pin["routes"][writer]:
        reviewer = pin["reviewers"][name]
        # The resolved path, not the bare name: on Windows a CLI is often a .cmd shim that Popen cannot find by name.
        executable = shutil.which(reviewer["cli"])
        if executable is None:
            failover.append({"reviewer": name, "reason": f"{reviewer['cli']} is not installed"})
            continue
        stdout = None
        tmp = Path(tempfile.mkdtemp())
        try:
            stdout_path, message_path = tmp / "stdout.txt", tmp / "last-message.md"
            argv, stdin_text = command(reviewer, executable, prompt, Path(prompt_path).resolve(), message_path, timeout)
            _, problem = run(argv, stdin_text, timeout, [stdout_path, message_path])
            if problem is None:
                source = message_path if reviewer["cli"] == "codex" else stdout_path
                stdout = source.read_text(encoding="utf-8", errors="replace") if source.is_file() else ""
        finally:
            remove_scratch(tmp)
        if problem is None and not (stdout or "").strip():
            problem = "returned no review"
        if problem is None:
            problem = blocked(stdout)
        if problem:
            failover.append({"reviewer": name, "reason": problem})
            continue
        return {"writer": writer, "reviewer": name, "cli": reviewer["cli"], "model": reviewer["model"],
                "effort": reviewer.get("effort"), "failover": failover, "review": stdout.strip()}
    return {"writer": writer, "reviewer": None, "failover": failover, "review": None}


def blocked(text):
    """Why a reply is not a review, when its last line is `OVERALL: blocked`; None for a review."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines or not BLOCKED.match(lines[-1]):
        return None
    reason = next((line.strip() for line in lines[:-1] if not line.lstrip().startswith("#")), "no reason given")
    return f"could not review: {reason[:300]}"


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


# A findings file is read back by `list_rounds`, so the envelope `record` writes around each review is unambiguous:
# the metadata states how many lines the review has (`- Lines: N`, lines split on "\n" only), the reader skips exactly
# that many without reading them, and the review is stored byte for byte, whatever headings or fences it holds.
# Rounds recorded before the count existed have no Lines field and run to the next round heading.
ROUND_HEADING = re.compile(r"^## Round (\d+): (none|([a-z0-9][a-z0-9-]*) \(`([^`]+)` via `([a-z]+)`\))$")
ROUND_LINE = re.compile(r"^- (Writer|Run|Effort|Lines|Skipped): (\S.*)$")
SKIPPED = re.compile(r"^([a-z0-9][a-z0-9-]*) \((.*)\)$")


def text_lines(text):
    """Lines split on "\n" alone, the one boundary both `record` and the reader use, with a CRLF checkout's "\r"
    dropped. `str.splitlines` also splits on U+2028, U+0085 and others, which a review may contain."""
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def read_rounds(text):
    """The rounds `record` wrote in one findings file, or None when anything `record` writes is not as it writes it.

    A round is a `## Round` heading, a blank line, and a metadata block to the next blank line in which every line is
    one of `record`'s fields (Writer and Run exactly once, Effort and Lines at most once, any number of Skipped). With
    Lines, the next N lines are the review, skipped unread, and a blank line or the end of the file must follow them,
    so a hand edit that changes the count shows as unreadable. Without Lines (a round recorded before the count), the
    round runs to the next `## Round` line. Anything else makes the file unreadable rather than losing a field."""
    rounds = []
    lines = text_lines(text)
    i = 0
    while i < len(lines):
        if not lines[i].startswith("## Round"):
            i += 1
            continue
        heading = ROUND_HEADING.match(lines[i])
        if not heading or i + 1 >= len(lines) or lines[i + 1] != "":
            return None
        entry = {"number": int(heading.group(1)), "reviewer": heading.group(3), "model": heading.group(4),
                 "cli": heading.group(5), "writer": None, "run": None, "effort": None, "skipped": []}
        count = None
        i += 2
        while i < len(lines) and lines[i] != "":
            field = ROUND_LINE.match(lines[i])
            if not field:
                return None
            key, value = field.group(1).lower(), field.group(2)
            if key == "skipped":
                skipped = SKIPPED.match(value)
                if not skipped:
                    return None
                entry["skipped"].append({"reviewer": skipped.group(1), "reason": skipped.group(2)})
            elif key == "lines":
                if count is not None or not value.isdigit():
                    return None
                count = int(value)
            elif entry[key] is not None:
                return None
            else:
                entry[key] = value
            i += 1
        if entry["writer"] is None or entry["run"] is None:
            return None
        if count is not None:
            i += 1 + count  # the blank line after the metadata, then the review, unread
            if i > len(lines) or (i < len(lines) and lines[i] != ""):
                return None
        rounds.append(entry)
    return rounds


def record(path, result, when):
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    # Numbered from the rounds actually recorded; a file the reader refuses falls back to counting headings, so a
    # round is still recorded (and the listing names the file as unreadable).
    known = read_rounds(existing)
    number = (len(known) if known is not None else len(re.findall(r"^## Round \d+", existing, flags=re.M))) + 1
    who = f"{result['reviewer']} (`{result['model']}` via `{result['cli']}`)" if result["reviewer"] else "none"
    review = text_lines(result["review"] or "No reviewer returned a review. This round is not an approval.")
    lines = [f"## Round {number}: {who}", "", f"- Writer: {result['writer']}", f"- Run: {when}"]
    if result.get("effort"):
        lines.append(f"- Effort: {result['effort']}")
    lines += [f"- Skipped: {f['reviewer']} ({f['reason']})" for f in result["failover"]]
    lines += [f"- Lines: {len(review)}", "", *review, ""]
    separator = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    atomic_write(path, existing + separator + "\n".join(lines))
    return number


def list_rounds(records_dir):
    """Every findings file under records_dir that holds rounds, with each round as `record` wrote it. A file
    whose round headings or lines are not `record`'s is named in `unreadable`, never dropped."""
    records_dir = Path(records_dir)
    records, unreadable = [], []

    def shown(path):
        # Never resolve: a path being reported as unreadable may be a symlink loop, which resolve() raises on.
        path = Path(os.path.abspath(path))
        return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()

    try:
        paths = sorted(records_dir.rglob("*.md")) if records_dir.is_dir() else []
    except OSError:  # a folder that cannot be walked is reported, like a file that cannot be read
        return {"records": [], "unreadable": [shown(records_dir)]}
    for path in paths:
        # One file that cannot be read, or is not UTF-8, is named in `unreadable`; the others are still listed.
        try:
            rounds = read_rounds(path.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, RuntimeError):  # RuntimeError: a symlink loop on older Pythons
            rounds = None
        if rounds is None:
            unreadable.append(shown(path))
        elif rounds:
            records.append({"path": shown(path), "rounds": rounds})
    return {"records": records, **({"unreadable": unreadable} if unreadable else {})}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--writer", choices=WRITERS, help="The agent whose work is under review")
    parser.add_argument("--prompt", help="File holding the review prompt")
    parser.add_argument("--record", help="Findings file to append this round to")
    parser.add_argument("--timeout", type=int, default=1800, help="Seconds per reviewer before failing over")
    parser.add_argument("--pin", default=str(PIN), help=argparse.SUPPRESS)
    parser.add_argument("--check-pin", action="store_true",
                        help="Report whether the pin loads, and each CLI's presence, instead of running a review; "
                             "no reviewer runs (exit 0 loads, 2 refused)")
    parser.add_argument("--list-rounds", action="store_true",
                        help="List the recorded review rounds instead of running one; no reviewer runs")
    parser.add_argument("--json", action="store_true", help="With --list-rounds, print the listing as JSON")
    parser.add_argument("--records", default=str(ROOT / "docs" / "reviews"),
                        help="With --list-rounds, the folder of findings files (default docs/reviews)")
    args = parser.parse_args(argv)
    if args.check_pin:
        # load_pin stays the only place the rules live: this reports its verdict and runs nothing.
        try:
            pin = load_pin(args.pin)
        except Refused as exc:
            print(json.dumps({"ok": False, "error": str(exc)}) if args.json else f"refused: {exc}")
            return 2
        clis = {cli: shutil.which(cli) is not None for cli in CLIS}
        print(json.dumps({"ok": True, "schema_version": pin["schema_version"], "reviewers": pin["reviewers"],
                          "routes": pin["routes"], "clis": clis}) if args.json else "ok")
        return 0
    if args.list_rounds:
        listing = list_rounds(args.records)
        if args.json:
            print(json.dumps(listing, indent=2))
        else:
            for entry in listing["records"]:
                for r in entry["rounds"]:
                    who = f"{r['reviewer']} ({r['model']} via {r['cli']})" if r["reviewer"] else "no review"
                    print(f"{entry['path']}  Round {r['number']}: {who}, writer {r['writer']}, {r['run']}")
            for path in listing.get("unreadable", []):
                print(f"{path}  unreadable: a round heading or line is not in the record format")
        return 0
    if not args.writer or not args.prompt:
        parser.error("--writer and --prompt are required unless --check-pin or --list-rounds is given")
    try:
        result = review(load_pin(args.pin), args.writer, args.prompt, args.timeout)
    except (Refused, OSError) as exc:
        print("review-dispatch refused: " + str(exc), file=sys.stderr)
        return 2
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.record:
        result["round"] = record(Path(args.record), result, when)
    print(json.dumps({**result, "run": when}, indent=2))
    return 0 if result["reviewer"] else 1


if __name__ == "__main__":
    sys.exit(main())
