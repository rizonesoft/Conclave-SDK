"""The `review-dispatch.py --check-pin --json` contract the VS Code extension reads (D01 T01 §3).

Every fixture pin under extensions/vscode/test/fixtures/pins/ runs through the reviewer kit's dispatcher and must give
the exit code, `ok` value and error text recorded in expected.json, so a dispatcher change that breaks the contract fails
here before it reaches the extension. The extension's own tests reuse the same fixtures.
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
FIXTURES = ROOT / "extensions/vscode/test/fixtures"
PINS = FIXTURES / "pins"
EXPECTED = json.loads((PINS / "expected.json").read_text(encoding="utf-8"))


def check_pin(dispatcher, pin, env=None):
    return subprocess.run([sys.executable, str(dispatcher), "--check-pin", "--json", "--pin", str(pin)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)


def json_object(stdout):
    """The one JSON object with an `ok` key the contract promises, or None (the extension's old-dispatcher rule)."""
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
                    self.assertEqual(set(report), {"ok", "schema_version", "reviewers", "routes", "clis"}, name)
                    # An int, not JSON true, which Python would also call equal to 1.
                    self.assertIs(type(report["schema_version"]), int, name)
                    self.assertEqual(report["schema_version"], 1, name)
                    # The reviewers and routes are the pin's own, in its order: what the extension lists and edits.
                    # Dict equality ignores order, so the keys are compared as lists too.
                    pin = tomllib.loads((PINS / name).read_text(encoding="utf-8"))
                    self.assertEqual(report["reviewers"], pin["reviewers"], f"{name}: reviewers")
                    self.assertEqual(list(report["reviewers"]), list(pin["reviewers"]), f"{name}: reviewer order")
                    self.assertEqual(report["routes"], pin["routes"], f"{name}: routes")
                    self.assertEqual(list(report["routes"]), list(pin["routes"]), f"{name}: route order")
                    self.assertEqual(set(report["clis"]), {"codex", "agy", "claude"}, name)
                    self.assertTrue(all(isinstance(v, bool) for v in report["clis"].values()), name)
                elif "error_prefix" in want:
                    self.assertEqual(set(report), {"ok", "error"}, name)
                    self.assertTrue(report["error"].startswith(want["error_prefix"]), f"{name}: {report['error']!r}")
                else:
                    self.assertEqual(set(report), {"ok", "error"}, name)
                    self.assertEqual(report["error"], want["error"], f"{name}: error text")

    def test_clis_says_which_reviewer_cli_is_on_path(self):
        # plan R10: the extension's PATH badges come from `clis`, so it must follow PATH. Each CLI alone and none at
        # all, so a dispatcher that looked one CLI up under another's name fails here (D01 T01 §4).
        for present in ("codex", "agy", "claude", None):
            with self.subTest(on_path=present), tempfile.TemporaryDirectory() as tmp:
                if present:
                    launcher = pathlib.Path(tmp) / (present + ".cmd" if os.name == "nt" else present)
                    launcher.write_text("@exit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n", encoding="utf-8")
                    launcher.chmod(0o755)
                # PATHEXT is set, not inherited: the launchers are .cmd files, which a caller's PATHEXT may not list.
                env = {"PATH": tmp, **({"PATHEXT": ".CMD"} if os.name == "nt" else {}),
                       **{k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ}}
                run = check_pin(DISPATCHER, PINS / "valid-shipped.toml", env=env)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(json.loads(run.stdout)["clis"], {cli: cli == present for cli in ("codex", "agy", "claude")})

    def test_a_dispatcher_without_check_pin_prints_no_contract_object(self):
        # plan R18: a dispatcher from before --check-pin (b7c649b) exits 2 like a refusal, so the extension tells them
        # apart by stdout, which holds no JSON object with an `ok` key, never by the exit code.
        run = check_pin(FIXTURES / "dispatchers/review-dispatch-b7c649b.py", PINS / "valid-shipped.toml")
        self.assertEqual(run.returncode, 2)
        self.assertIsNone(json_object(run.stdout), run.stdout)
        self.assertIsNotNone(json_object(check_pin(DISPATCHER, PINS / "valid-shipped.toml").stdout))


if __name__ == "__main__":
    unittest.main()
