"""scripts/review-dispatch.py: routing, failover, read-only invocations and records, with fake reviewer CLIs."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
REPO_PIN = SCRIPTS.parent / ".conclave" / "reviewers.toml"

# The kit's shipped reviewers and routes. The suite exercises the dispatcher against this fixture, never against the
# repository's own pin, which a project may narrow (one reviewer, no failover) without changing what is tested here.
FIXTURE_PIN = textwrap.dedent('''    schema_version = 1

    [reviewers.astra]
    cli = "codex"
    model = "gpt-6-astra"
    effort = "medium"

    [reviewers.gemini]
    cli = "agy"
    model = "gemini-4-argon-high"

    [reviewers.sonnet]
    cli = "claude"
    model = "claude-sonnet-5-5"
    effort = "high"

    [routes]
    claude = ["astra", "gemini"]
    codex = ["gemini", "sonnet"]
    gemini = ["astra", "sonnet"]
''')

# One fake reviewer for every CLI; a per-CLI launcher passes its name first. Launchers are a shell script on Linux and
# a .cmd file on Windows, so the suite runs natively on both.
FAKE_CLI = textwrap.dedent('''\
    import json, os, subprocess, sys, time
    name, args = sys.argv[1], sys.argv[2:]
    mode = os.environ.get("FAKE_" + name.upper(), "ok")
    if mode == "noread":
        time.sleep(30)
    stdin = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
    pointer = "-p=Follow the review instructions in the file "
    from_file = None
    if args and args[-1].startswith(pointer):
        path = args[-1][len(pointer):].split(" exactly.")[0]
        from_file = open(path).read() if os.path.isfile(path) else None
    with open(os.environ["FAKE_LOG"], "a") as log:
        log.write(json.dumps({"cli": name, "argv": args, "stdin": stdin, "cwd": os.getcwd(), "from_file": from_file}) + "\\n")
    if mode == "fail":
        sys.exit(3)
    if mode == "sleep":
        time.sleep(30)
    if mode == "flood":
        while True:
            sys.stdout.write("x" * 65536)
            sys.stdout.flush()
            time.sleep(0.01)
    if mode == "floodfile":
        with open(args[args.index("-o") + 1], "w") as out:
            while True:
                out.write("x" * 65536)
                out.flush()
                time.sleep(0.01)
    if mode == "orphan":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        open(os.environ["FAKE_CHILD_PID"], "w").write(str(child.pid))
    text = "" if mode == "empty" else "VERDICT: needs-attention, calc.py:2 subtracts. (" + name + ")"
    if mode == "headings":
        text = "## Round trip serialization\\n\\nFine.\\n\\n```\\n## Round 9: none\\n\\n- Writer: claude\\n- Run: 2026-01-01T00:00:00Z\\n```\\n\\nOVERALL: approve"
    if mode == "blocked":
        text = "## record: needs-attention\\n\\nI could not read the repository: setup refresh had errors.\\n\\nOVERALL: blocked"
    if name == "codex":
        open(args[args.index("-o") + 1], "w").write(text)
    else:
        print(text)
    if mode == "linger":
        # A process the reviewer started outlives it and holds the message file open for a moment, as a CLI's helper
        # process can; the reviewer exits first, so no tree kill reaches the helper.
        ready = os.environ["FAKE_CHILD_PID"] + ".ready"
        holder = "import sys, time; f = open(sys.argv[1], 'a'); open(sys.argv[2], 'w').close(); time.sleep(3)"
        subprocess.Popen([sys.executable, "-c", holder, args[args.index("-o") + 1], ready], cwd=os.path.dirname(sys.executable))
        while not os.path.exists(ready):
            time.sleep(0.05)
''')


def write_launcher(directory, name, fake):
    if os.name == "nt":
        path = directory / f"{name}.cmd"
        path.write_text(f'@"{sys.executable}" "{fake}" {name} %*\r\n', encoding="utf-8")
    else:
        path = directory / name
        path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" {name} "$@"\n', encoding="utf-8")
        path.chmod(0o755)
    return path


class Dispatch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / ".conclave").mkdir()
        shutil.copy(SCRIPTS / "review-dispatch.py", self.repo / "scripts/review-dispatch.py")
        (self.repo / ".conclave/reviewers.toml").write_text(FIXTURE_PIN, encoding="utf-8")
        self.bin = Path(self._tmp.name) / "bin"
        self.bin.mkdir()
        fake = Path(self._tmp.name) / "fake_cli.py"
        fake.write_text(FAKE_CLI, encoding="utf-8")
        self.launchers = {cli: write_launcher(self.bin, cli, fake) for cli in ("codex", "agy", "claude")}
        self.log = Path(self._tmp.name) / "calls.jsonl"
        self.scratch = Path(self._tmp.name) / "scratch"
        self.scratch.mkdir()
        self.prompt = self.repo / "prompt.md"
        self.prompt.write_text("Review calc.py. Do not modify any file.\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def dispatch(self, *args, **modes):
        system_root = {"SYSTEMROOT": os.environ["SYSTEMROOT"]} if os.name == "nt" else {}
        env = {"PATH": f"{self.bin}{os.pathsep}{Path(sys.executable).parent}", "FAKE_LOG": str(self.log),
               "FAKE_CHILD_PID": str(Path(self._tmp.name) / "child.pid"), **system_root,
               **{var: str(self.scratch) for var in ("TMP", "TEMP", "TMPDIR")},
               **{f"FAKE_{k.upper()}": v for k, v in modes.items()}}
        result = subprocess.run([sys.executable, "-B", str(self.repo / "scripts/review-dispatch.py"), *args],
                                capture_output=True, text=True, env=env, timeout=60)
        summary = json.loads(result.stdout) if result.stdout.strip().startswith("{") else None
        return result, summary

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_astra_reviews_claude_work_read_only(self):
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((summary["reviewer"], summary["model"]), ("astra", "gpt-6-astra"))
        self.assertIn("(codex)", summary["review"])
        call = self.calls()[0]
        self.assertEqual(call["argv"][:3], ["exec", "-m", "gpt-6-astra"])
        for flag in ("--sandbox", "read-only", "--ephemeral", "model_reasoning_effort=medium"):
            self.assertIn(flag, call["argv"])
        self.assertEqual(call["stdin"], self.prompt.read_text())
        self.assertEqual(Path(call["cwd"]).resolve(), self.repo.resolve())

    def test_astra_never_reviews_astra(self):
        result, summary = self.dispatch("--writer", "codex", "--prompt", str(self.prompt))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["reviewer"], "gemini")
        self.assertEqual([c["cli"] for c in self.calls()], ["agy"])

    def test_gemini_runs_in_plan_mode_with_the_prompt_as_the_p_value(self):
        _, summary = self.dispatch("--writer", "codex", "--prompt", str(self.prompt))
        call = self.calls()[0]
        self.assertEqual(summary["model"], "gemini-4-argon-high")
        self.assertIn("--sandbox", call["argv"])
        self.assertEqual(call["argv"][call["argv"].index("--mode") + 1], "plan")
        if os.name == "nt":
            # The fake is a .cmd shim on Windows, so the prompt must arrive by file, never as argument text.
            self.assertTrue(call["argv"][-1].startswith("-p=Follow the review instructions in the file "))
            self.assertEqual(call["from_file"], self.prompt.read_text())
        else:
            self.assertEqual(call["argv"][-1], "-p=" + self.prompt.read_text())

    def test_a_route_is_one_reviewer_and_one_fallback_never_the_writers_family(self):
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), codex="fail")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["reviewer"], "gemini")
        self.log.unlink()
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), codex="fail", agy="empty")
        self.assertEqual(result.returncode, 1, "a third reviewer ran after the fallback")
        self.assertEqual([f["reason"] for f in summary["failover"]], ["exited 3", "returned no review"])
        self.assertEqual([c["cli"] for c in self.calls()], ["codex", "agy"], "Sonnet must never review Claude's work")

    def test_the_fallback_for_codex_work_is_sonnet_in_plan_mode(self):
        result, summary = self.dispatch("--writer", "codex", "--prompt", str(self.prompt), agy="fail")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["reviewer"], "sonnet")
        sonnet = self.calls()[-1]
        self.assertEqual(sonnet["argv"][sonnet["argv"].index("--permission-mode") + 1], "plan")
        self.assertEqual(sonnet["argv"][sonnet["argv"].index("--model") + 1], "claude-sonnet-5-5")

    def test_a_reviewer_that_could_not_reach_the_candidate_fails_over(self):
        # A reply ending OVERALL: blocked says the reviewer never saw the work (a sandbox that cannot read the
        # repository): it is not a review, so the next reviewer runs.
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), codex="blocked")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["reviewer"], "gemini")
        self.assertEqual(summary["failover"][0]["reviewer"], "astra")
        self.assertIn("could not review: ", summary["failover"][0]["reason"])
        self.assertIn("setup refresh had errors", summary["failover"][0]["reason"])
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt),
                                        codex="blocked", agy="blocked", claude="blocked")
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(summary["review"])

    def test_a_missing_cli_fails_over(self):
        self.launchers["codex"].unlink()
        _, summary = self.dispatch("--writer", "gemini", "--prompt", str(self.prompt))
        self.assertEqual(summary["reviewer"], "sonnet")
        self.assertEqual(summary["failover"], [{"reviewer": "astra", "reason": "codex is not installed"}])

    def test_a_timeout_fails_over(self):
        _, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--timeout", "2", codex="sleep")
        self.assertEqual(summary["reviewer"], "gemini")
        self.assertEqual(summary["failover"][0]["reason"], "timed out")

    def test_no_review_is_never_an_approval(self):
        record = self.repo / "docs/reviews/round.md"
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(record),
                                        codex="fail", agy="fail", claude="fail")
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(summary["reviewer"])
        self.assertIn("not an approval", record.read_text())

    def test_rounds_are_numbered_and_appended(self):
        record = self.repo / "docs/reviews/round.md"
        record.parent.mkdir(parents=True)
        record.write_text("# Findings\n", encoding="utf-8")
        self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(record))
        _, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(record), codex="fail")
        text = record.read_text()
        self.assertEqual(summary["round"], 2)
        self.assertTrue(text.startswith("# Findings\n"))
        self.assertIn("## Round 1: astra (`gpt-6-astra` via `codex`)", text)
        self.assertIn("## Round 2: gemini (`gemini-4-argon-high` via `agy`)", text)
        self.assertIn("- Skipped: astra (exited 3)", text)

    def test_list_rounds_reads_back_what_record_wrote(self):
        # Two rounds written by record itself: one reviewed, one where every reviewer was skipped.
        record = self.repo / "docs/reviews/00-design/D00-T01-s1.md"
        self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(record))
        self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(record),
                      codex="fail", agy="fail")
        result, listing = self.dispatch("--list-rounds", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        (only,) = listing["records"]
        self.assertEqual(only["path"], "docs/reviews/00-design/D00-T01-s1.md")
        reviewed, skipped = only["rounds"]
        self.assertEqual({k: reviewed[k] for k in ("number", "reviewer", "model", "cli", "writer", "effort", "skipped")},
                         {"number": 1, "reviewer": "astra", "model": "gpt-6-astra", "cli": "codex", "writer": "claude",
                          "effort": "medium", "skipped": []})
        self.assertRegex(reviewed["run"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual({k: skipped[k] for k in ("number", "reviewer", "model", "cli", "effort", "skipped")},
                         {"number": 2, "reviewer": None, "model": None, "cli": None, "effort": None,
                          "skipped": [{"reviewer": "astra", "reason": "exited 3"},
                                      {"reviewer": "gemini", "reason": "exited 3"}]})
        self.assertNotIn("unreadable", listing)

    def test_list_rounds_with_no_records_and_with_an_unreadable_heading(self):
        result, listing = self.dispatch("--list-rounds", "--json")
        self.assertEqual((result.returncode, listing), (0, {"records": []}))
        good = self.repo / "docs/reviews/a.md"
        self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(good))
        bad = self.repo / "docs/reviews/b.md"
        bad.write_text("# Findings\n\n## Round two: astra\n\n- Writer: claude\n", encoding="utf-8")
        result, listing = self.dispatch("--list-rounds", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["path"] for r in listing["records"]], ["docs/reviews/a.md"])
        self.assertEqual(listing["unreadable"], ["docs/reviews/b.md"])
        self.assertEqual(self.calls()[-1:], self.calls()[:1], "listing ran a reviewer")
        result, _ = self.dispatch("--prompt", str(self.prompt))
        self.assertEqual(result.returncode, 2, "a review without --writer must still be refused")

    def test_review_text_that_looks_like_a_round_is_neither_counted_nor_listed(self):
        # A review quoting `## Round ...` lines, one a whole fake round in a fence, round-trips through record.
        record = self.repo / "docs/reviews/r.md"
        self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(record), codex="headings")
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(record))
        self.assertEqual(summary["round"], 2, "record counted review text as a round")
        text = record.read_text(encoding="utf-8")
        self.assertIn("\\## Round trip serialization", text)
        self.assertIn("\\## Round 9: none", text)
        _, listing = self.dispatch("--list-rounds", "--json")
        self.assertEqual([r["number"] for r in listing["records"][0]["rounds"]], [1, 2])
        self.assertNotIn("unreadable", listing)

    def test_a_malformed_or_unreadable_record_is_named_and_the_rest_still_listed(self):
        good = self.repo / "docs/reviews/good.md"
        self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--record", str(good))
        recorded = good.read_text(encoding="utf-8")
        cases = {
            "empty-effort.md": recorded.replace("- Effort: medium", "- Effort:\n- Skipped: x (y)"),
            "two-writers.md": recorded.replace("- Writer: claude", "- Writer: claude\n- Writer: codex"),
            "no-blank.md": recorded.replace("via `codex`)\n\n", "via `codex`)\n"),
        }
        for name, body in cases.items():
            self.assertNotEqual(body, recorded, name)
            (self.repo / "docs/reviews" / name).write_text(body, encoding="utf-8")
        (self.repo / "docs/reviews/not-utf8.md").write_bytes(recorded.replace("claude", "claud\udcff", 1)
                                                              .encode("utf-8", "surrogateescape"))
        (self.repo / "docs/reviews/folder.md").mkdir()  # a path that cannot be read as a file
        result, listing = self.dispatch("--list-rounds", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["path"] for r in listing["records"]], ["docs/reviews/good.md"])
        self.assertEqual(sorted(listing["unreadable"]), sorted(
            f"docs/reviews/{n}" for n in (*cases, "not-utf8.md", "folder.md")))

    def test_a_large_prompt_reaches_gemini_by_file(self):
        self.prompt.write_text("x" * 150_000, encoding="utf-8")
        self.dispatch("--writer", "codex", "--prompt", str(self.prompt))
        call = self.calls()[0]
        self.assertTrue(call["argv"][-1].startswith("-p=Follow the review instructions in the file "))
        self.assertEqual(call["from_file"], "x" * 150_000)

    def test_a_runaway_reviewer_is_stopped_while_it_runs(self):
        started = time.monotonic()
        _, summary = self.dispatch("--writer", "codex", "--prompt", str(self.prompt), "--timeout", "40", agy="flood")
        self.assertLess(time.monotonic() - started, 30, "the cap was only applied at the timeout")
        self.assertEqual(summary["reviewer"], "sonnet")
        self.assertEqual(summary["failover"][0]["reason"], "returned more than 2000000 bytes")

    def test_codex_flooding_its_message_file_is_stopped_while_it_runs(self):
        started = time.monotonic()
        _, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--timeout", "40", codex="floodfile")
        self.assertLess(time.monotonic() - started, 30, "the cap was only applied at the timeout")
        self.assertEqual(summary["reviewer"], "gemini")
        self.assertEqual(summary["failover"][0]["reason"], "returned more than 2000000 bytes")

    def test_a_file_still_held_after_the_reviewer_exits_does_not_cost_the_round(self):
        result, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), codex="linger")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["reviewer"], "astra")
        self.assertIn("(codex)", summary["review"])
        self.assertNotIn("left", result.stderr)
        self.assertEqual(list(self.scratch.iterdir()), [], "the reviewer's scratch directory was not removed")

    def test_a_reviewer_that_never_reads_a_large_prompt_still_times_out(self):
        # Larger than any pipe buffer: a blocking write here would hang past the timeout.
        self.prompt.write_text("Review this.\n" + "x" * 1_000_000, encoding="utf-8")
        started = time.monotonic()
        _, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), "--timeout", "3", codex="noread")
        self.assertLess(time.monotonic() - started, 20)
        self.assertEqual(summary["failover"][0], {"reviewer": "astra", "reason": "timed out"})

    def test_a_prompt_with_a_nul_byte_is_refused_before_any_reviewer_runs(self):
        self.prompt.write_text("Review this.\x00", encoding="utf-8")
        result, _ = self.dispatch("--writer", "codex", "--prompt", str(self.prompt))
        self.assertEqual(result.returncode, 2)
        self.assertIn("NUL byte", result.stderr)
        self.assertEqual(self.calls(), [])

    @unittest.skipIf(os.name == "nt", "Windows cannot reach a child once its reviewer has exited (see kill_tree)")
    def test_a_reviewers_children_do_not_outlive_it(self):
        _, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt), codex="orphan")
        self.assertEqual(summary["reviewer"], "astra")
        pid = int((Path(self._tmp.name) / "child.pid").read_text())
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
        os.kill(pid, 9)
        self.fail("the reviewer's child process was still running")

    def test_a_windows_shim_never_gets_prompt_text_in_its_arguments(self):
        spec = importlib.util.spec_from_file_location("dispatch_under_test", self.repo / "scripts/review-dispatch.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        reviewer = {"cli": "agy", "model": "gemini-4-argon-high"}
        argv, stdin = module.command(reviewer, "C:/tools/agy.cmd", "x & del *", Path("C:/p.md"), Path("o"), 60)
        self.assertEqual(argv[-1], f"-p=Follow the review instructions in the file {Path('C:/p.md')} exactly. Do not modify any file.")
        self.assertIsNone(stdin)
        argv, _ = module.command(reviewer, "/usr/bin/agy", "short prompt", Path("/p.md"), Path("o"), 60)
        self.assertEqual(argv[-1], "-p=short prompt")

    def test_a_reviewer_that_cannot_start_fails_over(self):
        # Installed, but not a program the system can start, so the launch itself fails.
        self.launchers["codex"].unlink()
        if os.name == "nt":
            (self.bin / "codex.exe").write_bytes(b"not a program")
        else:
            write_launcher(self.bin, "codex", "unused").write_text("#!/nonexistent/interpreter\n", encoding="utf-8")
        _, summary = self.dispatch("--writer", "claude", "--prompt", str(self.prompt))
        self.assertEqual(summary["reviewer"], "gemini")
        self.assertTrue(summary["failover"][0]["reason"].startswith("could not start"), summary["failover"])

    def test_a_non_integer_schema_version_is_refused(self):
        # TOML true is Python True and 1.0 == 1, so both passed a `!= 1` check and loaded.
        pin = self.repo / ".conclave/reviewers.toml"
        good = pin.read_text()
        for bad in ("schema_version = true", "schema_version = 1.0"):
            with self.subTest(bad=bad):
                pin.write_text(good.replace("schema_version = 1", bad), encoding="utf-8")
                result, _ = self.dispatch("--writer", "claude", "--prompt", str(self.prompt))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("needs exactly schema_version = 1, [reviewers.*] and [routes]", result.stderr)
                self.assertEqual(self.calls(), [])

    def test_a_bad_pin_refuses_before_any_reviewer_runs(self):
        pin = self.repo / ".conclave/reviewers.toml"
        good = pin.read_text()
        for bad in (good.replace('effort = "medium"', 'effort = "extreme"'),
                    good.replace('cli = "codex"', 'cli = "bash"'),
                    good.replace('codex = ["gemini", "sonnet"]', 'codex = ["gemini", "opus"]'),
                    good.replace('model = "gpt-6-astra"', 'model = "gpt-6-astra; rm -rf ~"'),
                    good + '\n[extra]\nkey = 1\n',
                    good.replace('codex = ["gemini", "sonnet"]', 'codex = [["gemini"], "sonnet"]'),
                    good.replace('model = "gemini-4-argon-high"', 'model = "gemini-4-argon-high"\neffort = "high"'),
                    # A reviewer of the writer's own family, and a second fallback.
                    good.replace('claude = ["astra", "gemini"]', 'claude = ["astra", "sonnet"]'),
                    good.replace('gemini = ["astra", "sonnet"]', 'gemini = ["gemini", "sonnet"]'),
                    good.replace('claude = ["astra", "gemini"]', 'claude = ["astra", "gemini", "mini"]')
                    + '\n[reviewers.mini]\ncli = "codex"\nmodel = "gpt-6-mini"\neffort = "low"\n',
                    # A fallback of the reviewer's own family is not the third family the route promises.
                    good.replace('claude = ["astra", "gemini"]', 'claude = ["astra", "mini"]')
                    + '\n[reviewers.mini]\ncli = "codex"\nmodel = "gpt-6-mini"\neffort = "low"\n'):
            with self.subTest(bad=bad[-60:]):
                self.assertNotEqual(bad, good, "the replacement must match the fixture, or the case tests nothing")
                pin.write_text(bad, encoding="utf-8")
                result, _ = self.dispatch("--writer", "claude", "--prompt", str(self.prompt))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.calls(), [])
        pin.unlink()
        result, _ = self.dispatch("--writer", "claude", "--prompt", str(self.prompt))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no reviewer pin", result.stderr)


class RepositoryPin(unittest.TestCase):
    def test_the_repository_pin_loads_under_the_dispatchers_rules(self):
        spec = importlib.util.spec_from_file_location("dispatch_pin_check", SCRIPTS / "review-dispatch.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        pin = module.load_pin(REPO_PIN)
        self.assertTrue(pin["routes"], "the repository pin routes no writer")


if __name__ == "__main__":
    unittest.main()
