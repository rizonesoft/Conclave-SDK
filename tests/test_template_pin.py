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

    def test_thread_and_memory_safety_lenses_declared_word_for_word_and_opt_in_by_path(self):
        # D00 T03 §2: exact owner wording in [schedule.lenses], not built-in LENSES, default schedules unchanged until
        # the commented C++ conditional entry (or the README snippet) is enabled.
        want_thread = (
            "Which state is reached from two threads (UI, worker, callback, timer) without one lock or atomic owning "
            "it, and which lock order, wait, cancellation or teardown can deadlock or run after its owner is gone?"
        )
        want_memory = (
            "Which pointer, reference, view, handle or iterator can outlive what it refers to, and which size, index "
            "or cast is trusted unchecked?"
        )
        self.assertNotIn("thread-safety", review_pin.LENSES)
        self.assertNotIn("memory-safety", review_pin.LENSES)

        raw = TEMPLATE.read_text(encoding="utf-8")
        pin = review_pin.load_pin(data=raw.encode("utf-8"))
        sched = pin["schedule"]
        table = review_pin.lens_table(sched)
        self.assertEqual(table["thread-safety"], want_thread)
        self.assertEqual(table["memory-safety"], want_memory)

        # Default schedules (with C++ conditional block commented out) are unchanged on all four pass kinds.
        default_round = ["adversarial", "integration", "source-defect", "consistency", "quality", "optimization"]
        default_rec = ["adversarial", "integration", "plan-delivery", "record"]
        for paths in ([], ["src/app.cpp"], ["docs/readme.md"]):
            self.assertEqual(review_pin.lenses_for(sched, "plan", paths, False), ["plan"])
            self.assertEqual(review_pin.lenses_for(sched, "round", paths, False), default_round)
            self.assertEqual(review_pin.lenses_for(sched, "completion", paths, False), ["plan-delivery", "record"])
            self.assertEqual(review_pin.lenses_for(sched, "reconciliation", paths, False), default_rec)

        # Uncommenting the existing `# concurrency = ...` custom-lens example inside [schedule.lenses] loads cleanly.
        with_conc = raw.replace('# concurrency = ', 'concurrency = ', 1)
        conc_pin = review_pin.load_pin(data=with_conc.encode("utf-8"))
        self.assertIn("concurrency", review_pin.lens_table(conc_pin["schedule"]))

        # Uncommenting the C++ conditional example adds both lenses once to round and reconciliation on matching paths.
        cpp_block = (
            '# [[schedule.conditional]]\n'
            '# lenses = ["thread-safety", "memory-safety"]\n'
            '# passes = ["round", "reconciliation"]\n'
            '# paths = ["src/", "include/"]'
        )
        self.assertIn(cpp_block, raw)
        enabled_raw = raw.replace(cpp_block, cpp_block.replace("# ", ""), 1)
        enabled_sched = review_pin.load_pin(data=enabled_raw.encode("utf-8"))["schedule"]
        for matching in (["src/app.cpp"], ["include/core.hpp"]):
            self.assertEqual(review_pin.lenses_for(enabled_sched, "plan", matching, False), ["plan"])
            self.assertEqual(review_pin.lenses_for(enabled_sched, "round", matching, False),
                             default_round + ["thread-safety", "memory-safety"])
            self.assertEqual(review_pin.lenses_for(enabled_sched, "completion", matching, False),
                             ["plan-delivery", "record"])
            self.assertEqual(review_pin.lenses_for(enabled_sched, "reconciliation", matching, False),
                             default_rec + ["thread-safety", "memory-safety"])
        outside = ["docs/readme.md"]
        self.assertEqual(review_pin.lenses_for(enabled_sched, "plan", outside, False), ["plan"])
        self.assertEqual(review_pin.lenses_for(enabled_sched, "round", outside, False), default_round)
        self.assertEqual(review_pin.lenses_for(enabled_sched, "completion", outside, False), ["plan-delivery", "record"])
        self.assertEqual(review_pin.lenses_for(enabled_sched, "reconciliation", outside, False), default_rec)

        # README documents both opt-in lenses, placeholder prefixes, and a working [[schedule.conditional]] snippet.
        readme = (ROOT / "kits/reviewer/README.md").read_text(encoding="utf-8")
        for clause in ("C++ projects", "`thread-safety`", "`memory-safety`", "add no pass",
                       "placeholder repository-relative prefixes"):
            self.assertIn(clause, readme)
        snippet = cpp_block.replace("# ", "")
        self.assertIn(snippet, readme)
        readme_sched = review_pin.load_pin(data=(raw + "\n" + snippet + "\n").encode("utf-8"))["schedule"]
        self.assertEqual(review_pin.lenses_for(readme_sched, "round", ["src/app.cpp"], False),
                         default_round + ["thread-safety", "memory-safety"])
        self.assertEqual(review_pin.lenses_for(readme_sched, "reconciliation", ["src/app.cpp"], False),
                         default_rec + ["thread-safety", "memory-safety"])
        self.assertEqual(review_pin.lenses_for(readme_sched, "plan", ["src/app.cpp"], False), ["plan"])
        self.assertEqual(review_pin.lenses_for(readme_sched, "completion", ["src/app.cpp"], False),
                         ["plan-delivery", "record"])


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
