"""Tests for scripts/verify-agent-tiers.mjs: the Claude subagent tier rule, including the narrow Haiku allowance."""
import pathlib
import subprocess
import tempfile
import unittest

FORGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
VERIFIER = FORGE_ROOT / "scripts/verify-agent-tiers.mjs"

HAIKU_OK = {
    "name": "dependency-mapper",
    "description": "List each package's declared dependencies from the manifests and report them as a table.",
    "model": "claude-haiku-5-5",
    "tools": "Read, Glob, Grep",
    "mechanical_share": "95",
    "haiku_replay": "docs/agents/dependency-mapper-replay.md",
}


def agent(**fields):
    lines = ["---", *(f"{key}: {value}" for key, value in fields.items()), "---", "", "Body."]
    return "\n".join(lines) + "\n"


class VerifyAgentTiers(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        (self.root / ".claude/agents").mkdir(parents=True)
        replay = self.root / "docs/agents/dependency-mapper-replay.md"
        replay.parent.mkdir(parents=True)
        replay.write_text("Known-answer replay on 12 manifests: 12/12 identical to the Sonnet run.\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_verifier(self, **fields):
        (self.root / ".claude/agents/subject.md").write_text(agent(**fields), encoding="utf-8")
        return subprocess.run(["node", str(VERIFIER)], cwd=self.root, capture_output=True, text=True, timeout=60)

    def assert_refused(self, fragment, **fields):
        result = self.run_verifier(**fields)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(fragment, result.stderr)

    def test_sonnet_passes(self):
        result = self.run_verifier(name="git-runner", description="git status", model="sonnet", tools="Bash, Read")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opus_needs_a_rationale(self):
        self.assert_refused("model_rationale", name="reviewer", description="review", model="opus")

    def test_a_qualifying_haiku_agent_passes(self):
        result = self.run_verifier(**HAIKU_OK)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 on Haiku", result.stdout)

    def test_haiku_must_be_a_pinned_version_of_5_5_or_later(self):
        for model in ("haiku", "claude-haiku-4-5", "claude-haiku-5-4", "claude-haiku-latest"):
            with self.subTest(model=model):
                self.assert_refused("claude-haiku-5-5 or later", **{**HAIKU_OK, "model": model})
        for model in ("claude-haiku-5-5", "claude-haiku-5-10", "claude-haiku-6-0", "claude-haiku-5-5-20261001"):
            with self.subTest(model=model):
                self.assertEqual(self.run_verifier(**{**HAIKU_OK, "model": model}).returncode, 0)

    def test_haiku_work_must_be_at_least_90_percent_mechanical(self):
        for share in ("89", "50", "ninety", "", "100.5"):
            with self.subTest(share=share):
                fields = {**HAIKU_OK, "mechanical_share": share} if share else {k: v for k, v in HAIKU_OK.items() if k != "mechanical_share"}
                self.assert_refused("mechanical_share", **fields)

    def test_haiku_needs_a_replay_record_on_disk(self):
        self.assert_refused("haiku_replay", **{k: v for k, v in HAIKU_OK.items() if k != "haiku_replay"})
        self.assert_refused("haiku_replay", **{**HAIKU_OK, "haiku_replay": "docs/agents/missing.md"})
        self.assert_refused("haiku_replay", **{**HAIKU_OK, "haiku_replay": "../outside.md"})

    def test_haiku_never_edits(self):
        for tools in ("Read, Edit", "Write", "Read, MultiEdit", "NotebookEdit, Read"):
            with self.subTest(tools=tools):
                self.assert_refused("edit tools", **{**HAIKU_OK, "tools": tools})
        self.assert_refused("explicit \"tools:\"", **{k: v for k, v in HAIKU_OK.items() if k != "tools"})

    def test_haiku_never_does_judgment_work(self):
        for word in ("Review", "audit", "security", "research", "design", "debug", "diagnose", "architecture", "plan", "verdict"):
            with self.subTest(word=word):
                self.assert_refused("judgment", **{**HAIKU_OK, "description": f"Mostly lookups, then {word} the result."})
        self.assert_refused("judgment", **{**HAIKU_OK, "name": "security-scanner"})

    def test_the_kit_copy_matches_the_canonical_script(self):
        kit_copy = FORGE_ROOT / "kits/base/templates/scripts/verify-agent-tiers.mjs"
        self.assertEqual(kit_copy.read_bytes(), VERIFIER.read_bytes())


if __name__ == "__main__":
    unittest.main()
