"""The reviewer kit's template pin as a fresh install gets it (D00 T02 §1): all three writers routed, each to a
reviewer of another family, and Codex's work reaching the Antigravity reviewer through the dispatcher.

These live in the SDK's tests, not the kit's: the kit's tests are installed into projects, which own their pin and
may change its routes, so a test of the shipped pin beside a project's own would fail there for no fault.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "kits/reviewer/templates"
TEMPLATE = KIT / ".conclave/reviewers.toml"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review_pin = load("review_pin_for_template", KIT / "scripts/review_pin.py")
_kit_tests = load("kit_dispatch_tests_for_template", KIT / "scripts/tests/test_review_dispatch.py")


class TemplateRoutes(unittest.TestCase):
    def test_every_writer_is_routed_to_a_reviewer_of_another_family(self):
        pin = review_pin.load_pin(TEMPLATE)
        self.assertEqual(set(pin["routes"]), {"claude", "agy", "codex"})
        for writer, (reviewer,) in pin["routes"].items():
            with self.subTest(writer):
                entry = pin["reviewers"][reviewer]
                self.assertNotEqual(review_pin.FAMILY[entry["cli"]], review_pin.WRITER_FAMILY[writer])
                self.assertNotEqual(entry["cli"], "claude", "Claude writes and never reviews")
                if entry["cli"] == "agy":
                    self.assertTrue(entry["model"].startswith("gemini-"))

    def test_the_check_pin_fixture_is_the_template(self):
        fixture = ROOT / "tests/fixtures/check-pin/pins/valid-three-routes.toml"
        self.assertEqual(fixture.read_bytes(), TEMPLATE.read_bytes())


class TemplateDispatch(_kit_tests.Harness):
    """The kit's dispatcher harness (a scratch repository and stub CLIs on PATH) under the template pin."""

    REPLY = ("1. Nothing wrong.\n\n" + "".join(f"LENS {lens}: clean\n" for lens in (
        "adversarial", "integration", "source-defect", "consistency", "quality", "optimization"))
        + "HIGHEST: none\nOVERALL: approve")

    def setUp(self):
        super().setUp()
        self.pin = TEMPLATE.read_text(encoding="utf-8")
        (self.repo / ".conclave/reviewers.toml").write_text(self.pin, encoding="utf-8")

    def round(self):
        record = self.scratch / "audit-codex-work.md"
        result, summary = self.dispatch("--kind", "round", "--candidate", "a" * 40, "--writer", "codex", "--prompt",
                                        str(self.prompt), "--record", str(record), agy="say", say=self.REPLY)
        return result, summary, record

    def test_codex_work_reaches_the_antigravity_reviewer_and_its_review_is_recorded(self):
        result, summary, record = self.round()
        self.assertEqual(result.returncode, 0, (result.stderr, summary))
        self.assertEqual((summary["reviewer"], summary["model"]), ("carbon", "gemini-4-carbon-medium"))
        (call,) = self.calls()
        self.assertEqual(call["cli"], "agy")
        self.assertEqual(call["argv"][call["argv"].index("--model") + 1], "gemini-4-carbon-medium")
        self.assertIn("## Round 1: carbon (`gemini-4-carbon-medium` via `agy`)", record.read_text(encoding="utf-8"))

    def test_without_the_codex_route_codex_work_has_no_reviewer(self):
        (self.repo / ".conclave/reviewers.toml").write_text(self.pin.replace('codex = ["carbon"]\n', ""),
                                                            encoding="utf-8")
        result, _, _ = self.round()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
