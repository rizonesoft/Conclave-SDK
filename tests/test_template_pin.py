"""The reviewer kit's template pin as a fresh install gets it (D00 T02 §1): two writers routed to Codex, which has no writer route.

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
    def test_only_claude_and_antigravity_write_with_astra_reviewing(self):
        pin = review_pin.load_pin(TEMPLATE)
        self.assertEqual(pin["routes"], {"claude": ["astra"], "agy": ["astra"]})
        self.assertEqual(set(pin["reviewers"]), {"astra"})
        self.assertEqual(pin["reviewers"]["astra"]["cli"], "codex")
        self.assertEqual(pin["reviewers"]["astra"]["model"], "gpt-6.2-astra")
        for kind, effort in (("plan", "medium"), ("round", "medium"),
                             ("completion", "low"), ("reconciliation", "low")):
            self.assertEqual(review_pin.scheduled(pin["schedule"], kind, [], False)["effort"], effort)


class TemplateDispatch(_kit_tests.Harness):
    REPLY = ("".join(f"LENS {lens}: clean\n" for lens in (
        "adversarial", "integration", "source-defect", "consistency", "quality", "optimization"))
        + "HIGHEST: none\nOVERALL: approve")

    def setUp(self):
        super().setUp()
        (self.repo / ".conclave/reviewers.toml").write_bytes(TEMPLATE.read_bytes())

    def test_both_writers_reach_codex(self):
        for writer in ("claude", "agy"):
            result, summary = self.dispatch("--kind", "round", "--writer", writer,
                "--prompt", str(self.prompt), "--record", str(self.scratch / f"audit-{writer}.md"),
                codex="say", say=self.REPLY)
            self.assertEqual(result.returncode, 0, (result.stderr, summary))
            self.assertEqual((summary["reviewer"], summary["model"], summary["effort"]),
                             ("astra", "gpt-6.2-astra", "medium"))
        self.assertTrue(all(call["cli"] == "codex" for call in self.calls()))

    def test_codex_writer_is_refused_without_invoking_a_reviewer(self):
        result, _ = self.dispatch("--kind", "round", "--writer", "codex",
            "--prompt", str(self.prompt), "--record", str(self.scratch / "audit-codex.md"))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
