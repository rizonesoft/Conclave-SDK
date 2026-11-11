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
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
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
STUB = """import json, os, sys
args = sys.argv[1:]
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": args, "stdin": prompt}) + "\\n")
with open(args[args.index("-o") + 1], "w", encoding="utf-8") as out:
    out.write(os.environ["FAKE_SAY"])
"""


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

    def git(self, *args):
        done = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_script(self, *args, say=None):
        git_dir = str(pathlib.Path(shutil.which("git")).parent)
        env = {"PATH": os.pathsep.join([str(self.bin), str(pathlib.Path(sys.executable).parent), git_dir]),
               "FAKE_LOG": str(self.log), "FAKE_SAY": say or "",
               **({"SYSTEMROOT": os.environ["SYSTEMROOT"], "PATHEXT": ".CMD;.EXE"} if os.name == "nt" else {}),
               **{var: str(self.scratch) for var in ("TMP", "TEMP", "TMPDIR")}}
        return subprocess.run([sys.executable, "-B", *args], capture_output=True, text=True, encoding="utf-8",
                              env=env, timeout=300, cwd=str(self.repo))

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
                               "--record", RECORD, say=say)
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
        receipt = json.loads((self.repo / "docs/reviews/d00-t01-s1.json").read_text(encoding="utf-8"))
        self.assertEqual((receipt["passes_spent"], receipt["pass_cap"]), (4, schedule["pass_cap"]))
        self.assertEqual((receipt["completion"]["verdict"], receipt["completion"]["candidate"]), ("reconciled", repaired))
        self.assertEqual(receipt["schedule_sha"], self.start)
        validate = self.run_script("scripts/todo-graph.py", "validate")
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        listing = self.run_script("scripts/review-dispatch.py", "--list-rounds")
        self.assertIn("Reconciliation review: astra", listing.stdout)


if __name__ == "__main__":
    unittest.main()
