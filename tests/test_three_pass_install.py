"""A fresh install of the reviewer and todo kits reviews a TODO section three-pass, end to end.

`forge.py` installs both kits into a scratch git repository. The installed pin must be the three-pass one, and the
installed scripts and prompt templates must carry a section through its plan review, its one round, a completion
review that returns gaps and a reconciliation that closes them, with a stub Codex on PATH, and then stamp it. Nothing
here reads the SDK's own scripts: every command runs the copy forge installed.
"""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Installing the todo kit approves its Codex Stop hook through Codex's app-server; tests answer from a stub, never the
# machine's real Codex (which would record approvals for scratch folders in the user's config).
os.environ["CODEX_HOOK_TRUST_SERVER"] = json.dumps([sys.executable, str(ROOT / "tests/fixtures/codex_app_server_stub.py")])
_spec = importlib.util.spec_from_file_location("forge_for_install_test", ROOT / "forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)

RECORD = "docs/reviews/00-core/D00-T01-s1.md"
TODO = """---
schema_version: 1
id: alpha
domain: 00-core
status: active
title: "TODO-01 -- A"
---

# TODO-01 -- A

> **Goal:** g.

> **Current state:** c.

## Inputs

- i

## Outcome

- o

**Adjacency:** all=not-applicable (a fixture with nothing a user lists, exports or reverses)

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | The thing | -- | [ ] |
| 2 | §2 | The later thing | §1 | [ ] |

## 1. The thing

> **Started:** 2026-11-11T00:00:00Z

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Do it in `src/thing.py`. Done when: it shows.

- [ ] Write `src/thing.py`. Done when: it holds the thing. Cheaper substitute: an empty file must fail.
- [ ] Commit: `x: the thing`

**Test checkpoint:** `true` exits 0.

## 2. The later thing

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Do it in `src/later.py`. Done when: it shows.

- [ ] Write `src/later.py`. Done when: it holds the later thing. Cheaper substitute: an empty file must fail.
- [ ] Commit: `x: the later thing`

**Test checkpoint:** `true` exits 0.

## Verification

- v
"""
# The stub reviewer: it logs the prompt it was given and replies with FAKE_SAY, as `codex exec -o <file> -` would.
STUB = """import json, os, sys, time
args = sys.argv[1:]
prompt = sys.stdin.read()
gate = os.environ.get("FAKE_GATE")
if gate:  # a review in flight: say it started, then answer only once the test opens the gate (at most 60 s)
    open(gate + ".started", "w").close()
    for _ in range(600):
        if os.path.exists(gate):
            break
        time.sleep(0.1)
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": args, "stdin": prompt}) + "\\n")
with open(args[args.index("-o") + 1], "w", encoding="utf-8") as out:
    out.write(os.environ["FAKE_SAY"])
"""



def own_group():
    """Popen arguments for a child in a process group of its own with no console window, so end_tree can end it."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def end_tree(proc):
    """End a child started with own_group() and every process it started: taskkill /T while it still lives on
    Windows, its process group elsewhere."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:  # the group has ended already
            pass

def reply(kind, lenses, top="none", gaps=False):
    lines = [f"LENS {name}: {'findings' if gaps else 'clean'}" for name in lenses] + [f"HIGHEST: {top}"]
    if kind == "plan":
        lines.append("PLAN: gaps" if gaps else "PLAN: complete")
    lines.append(f"OVERALL: {'needs-attention' if gaps else 'approve'}" if kind in ("plan", "round")
                 else f"{kind.upper()}: {'gaps' if gaps else 'complete'}")
    return "\n".join(["1. [P2] `src/thing.py:1` is thin." if gaps else "Nothing found.", *lines])


class FreshInstall(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = pathlib.Path(self._tmp.name)
        self.repo = base / "project"
        self.repo.mkdir()
        for kit in ("base", "reviewer", "todo"):
            forge.apply_kit(self.repo, kit)
        self.bin = base / "bin"
        self.bin.mkdir()
        stub = base / "stub_codex.py"
        stub.write_text(STUB, encoding="utf-8")
        if os.name == "nt":
            (self.bin / "codex.cmd").write_text(f'@"{sys.executable}" "{stub}" %*\r\n', encoding="utf-8")
        else:
            launcher = self.bin / "codex"
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        self.log = base / "calls.jsonl"
        self.scratch = base / "scratch"
        self.scratch.mkdir()
        domain = self.repo / "todo/00-core"
        domain.mkdir(parents=True)
        (domain / "TODO-01-a.md").write_text(TODO, encoding="utf-8")
        (domain / "INDEX.md").write_text("# Index\n- TODO-01-a.md\n", encoding="utf-8")
        index = self.repo / "todo/TODO-00-INDEX.md"
        index.write_text(index.read_text(encoding="utf-8") + "- 00-core/TODO-01-a.md\n", encoding="utf-8")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        self.git("config", "core.autocrlf", "false")
        self.start = self.commit("the kits, the pin and the section")
        self.record = RECORD  # the section's findings file, in the receipts folder

    def git(self, *args):
        done = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def test_the_installed_guard_passes_its_self_test_through_every_wired_hook(self):
        done = subprocess.run([sys.executable, "-B", "scripts/campaign_guard.py", "--self-test"], cwd=str(self.repo),
                              capture_output=True, text=True, encoding="utf-8", timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for hook_file, decision in ((".claude/settings.json", "block"), (".agents/hooks.json", "continue"),
                                    (".codex/hooks.json", "block")):
            self.assertIn(f"self-test: {hook_file}: ok ({decision})", done.stdout)

    def script_env(self, say=None, gate=None, tag=None):
        git_dir = str(pathlib.Path(shutil.which("git")).parent)
        # A tag of its own, with every outer suite's kept (check-all's), so a sweep ends a reviewer the dispatcher
        # started in a session of its own, and ending an outer suite ends it too.
        outer = [t for t in os.environ.get("CONCLAVE_CHECK_ALL_OUTER", "").split(",")
                 + [os.environ.get("CONCLAVE_CHECK_ALL_TAG", "")] if t]
        tagged = {"CONCLAVE_CHECK_ALL_TAG": tag, **({"CONCLAVE_CHECK_ALL_OUTER": ",".join(outer)} if outer else {})} \
            if tag else {}
        return {"PATH": os.pathsep.join([str(self.bin), str(pathlib.Path(sys.executable).parent), git_dir]),
                "FAKE_LOG": str(self.log), "FAKE_SAY": say or "", **({"FAKE_GATE": gate} if gate else {}), **tagged,
                **({"SYSTEMROOT": os.environ["SYSTEMROOT"], "PATHEXT": ".CMD;.EXE"} if os.name == "nt" else {}),
                **{var: str(self.scratch) for var in ("TMP", "TEMP", "TMPDIR")}}

    def run_script(self, *args, say=None):
        return subprocess.run([sys.executable, "-B", *args], capture_output=True, text=True, encoding="utf-8",
                              env=self.script_env(say), timeout=300, cwd=str(self.repo))

    def fill(self, template, candidate, **values):
        """A prompt filled from the installed template: the text after its `---` line with its placeholders named."""
        body = (self.repo / "docs" / template).read_text(encoding="utf-8").split("\n---\n", 1)[1]
        for old, new in {"<FULL_SHA>": candidate, "<DNN TNN §N>": "D00 T01 §1", **values}.items():
            body = body.replace(old, new)
        path = self.scratch / template
        path.write_text(body, encoding="utf-8")
        return str(path)

    def review(self, kind, candidate, template, say, **values):
        done = self.run_script("scripts/review-dispatch.py", "--kind", kind, "--candidate", candidate,
                               "--writer", "claude", "--prompt", self.fill(template, candidate, **values),
                               "--record", self.record, say=say)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return json.loads(done.stdout)

    def test_the_installed_pin_is_the_three_pass_one(self):
        schedule = tomllib.loads((self.repo / ".conclave/reviewers.toml").read_text(encoding="utf-8"))["schedule"]
        self.assertEqual(schedule["policy"], "three-pass")
        self.assertEqual((schedule["pass_cap"], schedule["blocking"]), (33, ["P1", "P2"]))
        self.assertEqual(schedule["completion"]["lenses"], ["plan-delivery", "record"])
        self.assertEqual(len(schedule["rounds"]), 1)
        owned = schedule["plan"]["lenses"] + schedule["rounds"][0]["lenses"] + schedule["completion"]["lenses"]
        self.assertEqual(len(owned), len(set(owned)), "a lens has one owner among plan, the round and completion")
        check = self.run_script("scripts/review_pin.py", "--check")
        self.assertEqual((check.returncode, check.stdout.strip()), (0, "ok"), check.stderr)

    def test_a_section_runs_three_pass_to_its_stamp(self):
        self.three_pass_to_stamp("docs/reviews")

    @unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "slow: set CONCLAVE_FULL_TESTS=1 for the full suite")
    def test_a_section_stamps_and_unstamps_in_a_configured_receipts_folder(self):
        # D03 T01 §4: todo/plan.json's layout.receipts moves every receipt and findings file the kits write.
        # D03 T01 §7: the plan moves too, to docs/plan.md.
        (self.repo / "todo/plan.json").write_text('{"layout": {"receipts": ".claude/overnight/reviews", "plan": "docs/plan.md"}}\n',
                                                  encoding="utf-8")
        sync = self.run_script("scripts/todo-graph.py", "plan", "--sync")
        self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
        self.git("add", "-A")  # into the first commit, the one whose Started line the build began at
        self.git("commit", "-q", "--amend", "--no-edit")
        self.start = self.git("rev-parse", "HEAD")
        self.record = ".claude/overnight/reviews/00-core/D00-T01-s1.md"  # Impossible OS's folder
        self.three_pass_to_stamp(".claude/overnight/reviews")
        self.assertFalse((self.repo / "docs/reviews").exists(), "nothing is written to the default folder")
        plan = self.repo / "docs/plan.md"
        self.assertRegex(plan.read_text(encoding="utf-8"), r"\| \[x\] +\| D00 T01 §1 ", "the configured plan shows it verified")
        self.commit("the stamp")
        unstamp = self.run_script("scripts/todo-graph.py", "unstamp", "D00 T01 §1", "--reason", "an audit",
                                  "--date", "2026-11-13")
        self.assertEqual(unstamp.returncode, 0, unstamp.stdout + unstamp.stderr)
        self.assertIn("receipt kept as .claude/overnight/reviews/d00-t01-s1.revoked-2026-11-13.json", unstamp.stdout)
        self.assertTrue((self.repo / ".claude/overnight/reviews/d00-t01-s1.revoked-2026-11-13.json").is_file())
        self.assertFalse((self.repo / ".claude/overnight/reviews/d00-t01-s1.json").exists())
        self.assertIn("| 1 | §1 |", (self.repo / "todo/00-core/TODO-01-a.md").read_text(encoding="utf-8"))
        self.assertRegex((self.repo / "todo/00-core/TODO-01-a.md").read_text(encoding="utf-8"),
                         r"\| 1 \| §1 \|[^\n]*\[ \] \|", "the section is reopened")
        self.assertRegex(plan.read_text(encoding="utf-8"), r"\| \[ \] +\| D00 T01 §1 ", "and then reopened")
        validate = self.run_script("scripts/todo-graph.py", "validate")
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        self.assertFalse((self.repo / "docs/reviews").exists())
        check = self.run_script("scripts/todo-graph.py", "plan", "--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    @unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "slow: set CONCLAVE_FULL_TESTS=1 for the full suite")
    def test_a_section_stamps_under_every_plan_json_key(self):
        # D03 T01's Verification: a project's own phases, Needs, waiting Needs, caps and layout, all at once.
        needs = ["windows-host", "arm64-host", "display-session", "office", "libreoffice", "store-account",
                 "attended", "owner-decision", "third-party", "operator", "gpu"]
        config = {"title": "A project of its own", "phases": {"0": "Core", "12": "Later"}, "phase_list": [0, 12, 99],
                  "needs": needs, "waiting": ["owner-decision", "third-party", "operator"],
                  "caps": {"sections_per_file": 40, "items_per_section": 20, "deliverable_len": 80, "table_row": 160},
                  "layout": {"receipts": ".claude/overnight/reviews", "plan": "docs/plan.md", "root_index": "files"}}
        (self.repo / "todo/plan.json").write_text(json.dumps(config) + "\n", encoding="utf-8")
        validate = self.run_script("scripts/todo-graph.py", "validate")
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        sync = self.run_script("scripts/todo-graph.py", "plan", "--sync")
        self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
        self.git("add", "-A")
        self.git("commit", "-q", "--amend", "--no-edit")
        self.start = self.git("rev-parse", "HEAD")
        self.record = ".claude/overnight/reviews/00-core/D00-T01-s1.md"
        self.three_pass_to_stamp(".claude/overnight/reviews")
        plan = (self.repo / "docs/plan.md").read_text(encoding="utf-8")
        self.assertIn("# A project of its own", plan)
        self.assertRegex(plan, r"\| \[x\] +\| D00 T01 §1 ")
        for args in (("validate",), ("plan", "--check")):
            done = self.run_script("scripts/todo-graph.py", *args)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_chain_that_cannot_settle_is_replanned_and_the_new_chain_stamps(self):
        # D00 T01 §9, through the installed commands: a chain whose completion left gaps is re-planned with
        # todo-graph.py replan, the item is corrected and committed with the new Started, and the dispatcher (its stub
        # Codex) runs a fresh plan review, round and completion that stamp. The kept chain is closed and listed.
        RECORD = self.record
        schedule = tomllib.loads((self.repo / ".conclave/reviewers.toml").read_text(encoding="utf-8"))["schedule"]
        lenses = {kind: schedule[kind]["lenses"] for kind in ("plan", "completion", "reconciliation")}
        lenses["round"] = [name for name in schedule["rounds"][0]["lenses"] if name != "design"]
        self.review("plan", self.start, "plan-review-prompt.md", reply("plan", lenses["plan"]))
        todo = self.repo / "todo/00-core/TODO-01-a.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("- [ ] Write", "- [x] Write"), encoding="utf-8")
        (self.repo / "src").mkdir()
        (self.repo / "src/thing.py").write_text("THING = 1\n", encoding="utf-8")
        built = self.commit("x: the thing")
        self.review("round", built, "review-round-prompt.md", reply("round", lenses["round"]))
        self.review("completion", built, "completion-review-prompt.md",
                    reply("completion", lenses["completion"], "P2", True))
        kept_bytes = (self.repo / RECORD).read_bytes()

        replanned = self.run_script("scripts/todo-graph.py", "replan", "D00 T01 §1", "--date", "2026-11-19")
        self.assertEqual(replanned.returncode, 0, replanned.stdout + replanned.stderr)
        kept = RECORD.replace(".md", "-chain1.md")
        self.assertIn(f"review chain kept as {kept}", replanned.stdout)
        self.assertEqual(((self.repo / kept).read_bytes(), (self.repo / RECORD).exists()), (kept_bytes, False))
        # The item is corrected (a dated note) and committed with the new Started: the new chain's plan candidate.
        text = todo.read_text(encoding="utf-8")
        todo.write_text(text.replace("- [x] Write", "- [ ] Write the thing in full", 1).replace(
            "**Test checkpoint:**", "**Corrected 2026-11-19:** the item said only 'Write'.\n\n**Test checkpoint:**", 1),
            encoding="utf-8")
        self.start = self.commit("todo: re-plan D00 T01 §1")
        closed = self.run_script("scripts/review-dispatch.py", "--kind", "plan", "--candidate", self.start, "--writer",
                                 "claude", "--prompt", self.fill("plan-review-prompt.md", self.start),
                                 "--record", kept, say=reply("plan", lenses["plan"]))
        self.assertEqual(closed.returncode, 2, closed.stdout + closed.stderr)
        self.assertIn("is a kept earlier review chain", closed.stderr)

        self.review("plan", self.start, "plan-review-prompt.md", reply("plan", lenses["plan"]))
        todo.write_text(todo.read_text(encoding="utf-8").replace("- [ ] Write the thing in full",
                                                                 "- [x] Write the thing in full"), encoding="utf-8")
        (self.repo / "src/thing.py").write_text("THING = 2\n", encoding="utf-8")
        rebuilt = self.commit("x: the thing in full")
        self.review("round", rebuilt, "review-round-prompt.md", reply("round", lenses["round"]))
        self.review("completion", rebuilt, "completion-review-prompt.md", reply("completion", lenses["completion"]))
        self.commit("the findings file")
        stamp = self.run_script("scripts/todo-graph.py", "stamp", "D00 T01 §1", "--sha", rebuilt, "--plan", RECORD,
                                "--completion", f"{RECORD}:complete", "--review", f"1:{RECORD}:clean",
                                "--check", "true -> exit 0")
        self.assertEqual(stamp.returncode, 0, stamp.stdout + stamp.stderr)
        self.assertEqual((self.repo / kept).read_bytes(), kept_bytes, "the new chain touched the kept one")
        rounds = self.run_script("scripts/todo-graph.py", "query", "rounds")
        self.assertEqual(rounds.returncode, 0, rounds.stdout + rounds.stderr)
        (row,) = [r for r in json.loads(rounds.stdout)["sections"] if r["ref"] == "D00 T01 §1"]
        self.assertEqual(row["kept_chains"], [{"file": kept, "passes_returned": 3}])

    def test_a_pass_in_flight_under_a_rotation_pin_holds_replan_off_and_lands_in_the_kept_chain(self):
        # The completion review of D00 T01 §9: under a rotation pin a pass took no section lock, so replan could move
        # the findings file under it and its result land in the chain that replaces it. Here the stub reviewer is
        # paused mid-pass: replan is refused and moves nothing, and once the pass returns and replan runs, the round
        # is in the kept chain and the replacement chain holds no pass.
        (self.repo / ".conclave/reviewers.toml").write_text(
            'schema_version = 1\n\n[reviewers.astra]\ncli = "codex"\nmodel = "m"\neffort = "medium"\n\n'
            '[routes]\nclaude = ["astra"]\n', encoding="utf-8")
        self.start = self.commit("a rotation pin")
        gate = str(self.scratch / "gate")
        tag = uuid.uuid4().hex
        say = "1. Nothing found.\n\nHIGHEST: none\n\nOVERALL: approve"
        in_flight = subprocess.Popen(
            [sys.executable, "-B", "scripts/review-dispatch.py", "--writer", "claude", "--prompt",
             self.fill("review-round-prompt.md", self.start), "--record", self.record],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            env=self.script_env(say, gate, tag), cwd=str(self.repo), **own_group())

        def end_in_flight():
            # A failed assertion leaves the reviewer paused: the gate is opened and the whole tree ended and waited
            # for before the fixture goes, so no reviewer outlives the test.
            pathlib.Path(gate).touch()
            if in_flight.poll() is None:
                end_tree(in_flight)
            in_flight.wait(timeout=30)
            # On Linux the dispatcher starts the reviewer in a session of its own, which its group does not reach:
            # the tag finds it there (a no-op on Windows, where taskkill /T ends the whole tree).
            forge._kill_tagged(tag)
        self.addCleanup(end_in_flight)
        for _ in range(600):
            if os.path.exists(gate + ".started"):
                break
            time.sleep(0.1)
        self.assertTrue(os.path.exists(gate + ".started"), "the stub reviewer never started")
        refused = self.run_script("scripts/todo-graph.py", "replan", "D00 T01 §1", "--date", "2026-11-19")
        self.assertNotEqual(refused.returncode, 0, refused.stdout + refused.stderr)
        self.assertIn("replan waits for it", refused.stdout + refused.stderr)
        own = self.repo / self.record
        self.assertEqual(list(own.parent.glob("*-chain*.md")), [], "replan moved something under a pass in flight")
        pathlib.Path(gate).touch()
        out, err = in_flight.communicate(timeout=120)
        self.assertEqual(in_flight.returncode, 0, out + err)
        self.assertIn("## Round 1", own.read_text(encoding="utf-8"))
        replanned = self.run_script("scripts/todo-graph.py", "replan", "D00 T01 §1", "--date", "2026-11-19")
        self.assertEqual(replanned.returncode, 0, replanned.stdout + replanned.stderr)
        kept = own.with_name(own.stem + "-chain1.md")
        self.assertIn("## Round 1", kept.read_text(encoding="utf-8"), "the pass is not in the kept chain")
        self.assertFalse(own.exists(), "the replacement chain holds a pass from the old one")

    def three_pass_to_stamp(self, receipts):
        """Plan review, round, a completion with gaps, a reconciliation and the stamp, with every findings file and
        receipt in `receipts`."""
        RECORD = self.record
        schedule = tomllib.loads((self.repo / ".conclave/reviewers.toml").read_text(encoding="utf-8"))["schedule"]
        lenses = {kind: schedule[kind]["lenses"] for kind in ("plan", "completion", "reconciliation")}
        # The round's design lens is for a section with a surface; this one has none.
        lenses["round"] = [name for name in schedule["rounds"][0]["lenses"] if name != "design"]
        plan = self.review("plan", self.start, "plan-review-prompt.md", reply("plan", lenses["plan"]))
        self.assertEqual((plan["lenses"], plan["effort"]), (lenses["plan"], "medium"))

        todo = self.repo / "todo/00-core/TODO-01-a.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("- [ ] Write", "- [x] Write"), encoding="utf-8")
        (self.repo / "src").mkdir()
        (self.repo / "src/thing.py").write_text("THING = 1\n", encoding="utf-8")
        built = self.commit("x: the thing")
        rnd = self.review("round", built, "review-round-prompt.md", reply("round", lenses["round"]))
        self.assertEqual((rnd["lenses"], rnd["round"]), (lenses["round"], 1))
        completion = self.review("completion", built, "completion-review-prompt.md",
                                 reply("completion", lenses["completion"], "P2", True))
        self.assertEqual((completion["highest"], completion["blocking"]), ("P2", True))

        # The completion review raised two gaps: one in scope, repaired in a new commit, and one out of scope, filed
        # as §2. Both are noted under the review, and the reconciliation prompt tells the reviewer how each closes.
        (self.repo / "src/thing.py").write_text("THING = 2\n", encoding="utf-8")
        record = self.repo / RECORD
        with open(record, "a", encoding="utf-8", newline="") as handle:
            handle.write("\n- Implemented: gap 1, the thing is thicker, in the repair commit\n"
                         "- Filed: D00 T01 §2 (gap 2, the later thing)\n")
        repaired = self.commit("x: repair the completion gap")
        reconciliation = self.review(
            "reconciliation", repaired, "reconciliation-review-prompt.md",
            reply("reconciliation", lenses["reconciliation"]),
            **{"<COMPLETION_SHA>": built, "<LAST_SHA>": built, "<quoted output>": "true -> exit 0",
               "<docs/reviews/<NN-domain>/D<NN>-T<NN>-s<N>.md>": RECORD,
               "<the spec or plan that applies>": "todo/00-core/TODO-01-a.md"})
        self.assertEqual((reconciliation["kind"], reconciliation["recorded"]), ("reconciliation", True))
        # The filled reconciliation prompt reached the reviewer with its context, its checks and the lens request.
        sent = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])["stdin"]
        for needle in (built, repaired, RECORD, "true -> exit 0", "are its promises the same",
                       "is closed only by the repair", "is closed when it is filed",
                       "LENS plan-delivery: <clean|findings>", "RECONCILIATION: complete"):
            self.assertIn(needle, sent)
        self.assertNotIn("<COMPLETION_SHA>", sent)
        self.assertNotIn("<LAST_SHA>", sent)

        tip = self.commit("the findings file")
        del tip  # the stamped commit is the one the last pass reviewed
        stamp = self.run_script("scripts/todo-graph.py", "stamp", "D00 T01 §1", "--sha", repaired, "--plan", RECORD,
                                "--completion", f"{RECORD}:reconciled", "--review", f"1:{RECORD}:clean",
                                "--check", "true -> exit 0")
        self.assertEqual(stamp.returncode, 0, stamp.stdout + stamp.stderr)
        receipt = json.loads((self.repo / receipts / "d00-t01-s1.json").read_text(encoding="utf-8"))
        self.assertEqual((receipt["passes_spent"], receipt["pass_cap"]), (4, schedule["pass_cap"]))
        self.assertEqual((receipt["completion"]["verdict"], receipt["completion"]["candidate"]), ("reconciled", repaired))
        self.assertEqual(receipt["schedule_sha"], self.start)
        validate = self.run_script("scripts/todo-graph.py", "validate")
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        listing = self.run_script("scripts/review-dispatch.py", "--list-rounds")
        self.assertIn("Reconciliation review: astra", listing.stdout)


if __name__ == "__main__":
    unittest.main()
