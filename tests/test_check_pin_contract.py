"""The `review-dispatch.py --check-pin --json` contract a pin editor or script reads.

Every fixture pin under tests/fixtures/check-pin/pins/ runs through the reviewer kit's dispatcher and must give
the exit code, `ok` value and error text recorded in expected.json, so a dispatcher change that breaks the contract fails
here before it reaches a reader.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "kits/reviewer/templates/scripts/review-dispatch.py"
FIXTURES = ROOT / "tests/fixtures/check-pin"
PINS = FIXTURES / "pins"
EXPECTED = json.loads((PINS / "expected.json").read_text(encoding="utf-8"))


def check_pin(dispatcher, pin, env=None, cwd=None):
    return subprocess.run([sys.executable, str(dispatcher), "--check-pin", "--json", "--pin", str(pin)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60, env=env, cwd=cwd)


def json_object(stdout):
    """The one JSON object with an `ok` key the contract promises, or None (how a reader tells an old dispatcher)."""
    try:
        report = json.loads(stdout)
    except ValueError:
        return None
    return report if isinstance(report, dict) and "ok" in report else None


class CheckPinContract(unittest.TestCase):
    def test_every_fixture_has_an_expectation_and_every_expectation_a_fixture(self):
        fixtures = {p.name for p in PINS.glob("*.toml")}
        self.assertEqual(fixtures, set(EXPECTED), "expected.json and the fixture pins disagree")

    def test_each_fixture_gives_the_recorded_verdict(self):
        for name, want in sorted(EXPECTED.items()):
            with self.subTest(fixture=name):
                run = check_pin(DISPATCHER, PINS / name)
                report = json_object(run.stdout)
                self.assertIsNotNone(report, f"{name}: stdout is not one JSON object with ok: {run.stdout!r} {run.stderr}")
                self.assertEqual(run.returncode, want["exit"], f"{name}: exit code")
                self.assertIs(report["ok"], want["ok"], f"{name}: ok")
                if want["ok"]:
                    pin = tomllib.loads((PINS / name).read_text(encoding="utf-8"))
                    # `schedule` is reported exactly when the pin has one, and is the pin's own table, key for key:
                    # a reader of the earlier contract sees the same five keys for a pin without a schedule.
                    keys = {"ok", "schema_version", "reviewers", "routes", "clis"} | ({"schedule"} & set(pin))
                    self.assertEqual(set(report), keys, name)
                    if "schedule" in pin:
                        self.assertEqual(report["schedule"], pin["schedule"], f"{name}: schedule")
                        self.assertEqual(list(report["schedule"]), list(pin["schedule"]), f"{name}: schedule order")
                    # An int, not JSON true, which Python would also call equal to 1.
                    self.assertIs(type(report["schema_version"]), int, name)
                    self.assertEqual(report["schema_version"], 1, name)
                    # The reviewers and routes are the pin's own, in its order: what a pin editor lists and edits.
                    # Dict equality ignores order, so the keys are compared as lists too.
                    self.assertEqual(report["reviewers"], pin["reviewers"], f"{name}: reviewers")
                    self.assertEqual(list(report["reviewers"]), list(pin["reviewers"]), f"{name}: reviewer order")
                    self.assertEqual(report["routes"], pin["routes"], f"{name}: routes")
                    self.assertEqual(list(report["routes"]), list(pin["routes"]), f"{name}: route order")
                    if "routes" in want:  # a fixture that names its routes: the three-route template pin (D00 T02 §1)
                        self.assertEqual(report["routes"], want["routes"], f"{name}: the routes it promises")
                    self.assertEqual(set(report["clis"]), {"codex", "agy", "claude"}, name)
                    self.assertTrue(all(isinstance(v, bool) for v in report["clis"].values()), name)
                elif "error_prefix" in want:
                    self.assertEqual(set(report), {"ok", "error"}, name)
                    self.assertTrue(report["error"].startswith(want["error_prefix"]), f"{name}: {report['error']!r}")
                else:
                    self.assertEqual(set(report), {"ok", "error"}, name)
                    self.assertEqual(report["error"], want["error"], f"{name}: error text")

    def test_clis_says_which_reviewer_cli_is_on_path(self):
        # A reader's installed-CLI display comes from `clis`, so it must follow PATH. Each CLI alone and none at
        # all, so a dispatcher that looked one CLI up under another's name fails here.
        for present in ("codex", "agy", "claude", None):
            with self.subTest(on_path=present), tempfile.TemporaryDirectory() as tmp:
                if present:
                    launcher = pathlib.Path(tmp) / (present + ".cmd" if os.name == "nt" else present)
                    launcher.write_text("@exit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n", encoding="utf-8")
                    launcher.chmod(0o755)
                # PATHEXT is set, not inherited: the launchers are .cmd files, which a caller's PATHEXT may not list.
                env = {"PATH": tmp, **({"PATHEXT": ".CMD"} if os.name == "nt" else {}),
                       **{k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ}}
                run = check_pin(DISPATCHER, PINS / "valid-shipped.toml", env=env, cwd=tmp)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(json.loads(run.stdout)["clis"], {cli: cli == present for cli in ("codex", "agy", "claude")})

    def test_a_dispatcher_without_check_pin_prints_no_contract_object(self):
        # A dispatcher from before --check-pin (b7c649b) exits 2 like a refusal, so a reader tells them
        # apart by stdout, which holds no JSON object with an `ok` key, never by the exit code.
        run = check_pin(FIXTURES / "dispatchers/review-dispatch-b7c649b.py", PINS / "valid-shipped.toml")
        self.assertEqual(run.returncode, 2)
        self.assertIsNone(json_object(run.stdout), run.stdout)
        self.assertIsNotNone(json_object(check_pin(DISPATCHER, PINS / "valid-shipped.toml").stdout))


class ShippedPinDocumentation(unittest.TestCase):
    """D00 T02 §1: what the kit's README and the three skill copies say about the installed pin is the pin's own:
    every route with its reviewer, and every reviewer with its CLI and model, so a deleted or stale row fails."""

    KIT = ROOT / "kits/reviewer"
    PIN = tomllib.loads((KIT / "templates/.conclave/reviewers.toml").read_text(encoding="utf-8"))

    @staticmethod
    def rows(text):
        return [[c.strip() for c in line.strip("|").split("|")] for line in text.splitlines() if line.startswith("| ")]

    def row_for_writer(self, text, writer, where):
        # A writer row names the agent in words first; the reviewer inventory's rows open with a backticked name.
        found = [r for r in self.rows(text) if len(r) >= 3 and r[1].startswith(f"`{writer}`") and not r[0].startswith("`")]
        self.assertEqual(len(found), 1, f"{where}: one row for the writer {writer}")
        return " | ".join(found[0])

    def test_every_route_and_reviewer_is_named_where_the_kit_documents_them(self):
        # Owner decision 2026-11-14 (dbf6373): Claude Code and Antigravity write, Codex only reviews.
        self.assertEqual(set(self.PIN["routes"]), {"claude", "agy"})
        self.assertEqual(set(self.PIN["reviewers"]), {"astra"})
        readme = (self.KIT / "README.md").read_text(encoding="utf-8")
        skills = {agent: (self.KIT / "templates" / agent / "skills/independent-review/SKILL.md").read_text(encoding="utf-8")
                  for agent in (".claude", ".agents", ".codex")}
        for writer, (name,) in self.PIN["routes"].items():
            reviewer = self.PIN["reviewers"][name]
            with self.subTest(writer=writer):
                row = self.row_for_writer(readme, writer, "README")
                self.assertIn(f"`{name}`", row)
                self.assertIn(f"`{reviewer['cli']}`", row)
                for agent, text in skills.items():
                    row = self.row_for_writer(text, writer, agent)
                    for part in (name, reviewer["model"], reviewer["cli"]):
                        self.assertIn(f"`{part}`", row, f"{agent}: {writer}")
        for name, reviewer in self.PIN["reviewers"].items():
            with self.subTest(reviewer=name):
                (row,) = [r for r in self.rows(readme) if r[0] == f"`{name}`"]
                self.assertIn(f"`{reviewer['model']}`", row[2])
                self.assertIn(reviewer["cli"], row[1])

if __name__ == "__main__":
    unittest.main()
