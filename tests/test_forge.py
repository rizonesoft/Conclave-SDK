"""Tests for forge.py provisioning modes, agent isolation, and repository prose hygiene."""
import json
import pathlib
import sys
import tempfile
import unittest

FORGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FORGE_ROOT))
import forge  # noqa: E402

EXPECTED_SKILLS = [
    "add-todo",
    "create-todo",
    "groom-plan",
    "process-phase",
    "process-plan",
    "process-todo-file",
    "process-todo-section",
    "review-todo-section",
]


class ForgeProvisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hybrid_mode_provisions_both_agents_and_inheritance(self):
        forge.provision(self.target, mode="hybrid", agent="all", with_todo=True)
        status = forge.check_repo(self.target)
        self.assertTrue(status["has_agents_md"])
        self.assertTrue(status["has_gemini_md"])
        self.assertTrue(status["has_claude_md"])
        self.assertTrue(status["has_agy_skills_json"])
        self.assertTrue(status["has_todo_graph"])
        self.assertEqual(status["agy_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["claude_skills"], EXPECTED_SKILLS)
        self.assertTrue((self.target / "todo/README.md").is_file())
        self.assertTrue((self.target / "todo/TODO-00-INDEX.md").is_file())

    def test_copy_mode_is_self_contained_without_external_skills_json(self):
        forge.provision(self.target, mode="copy", agent="all")
        status = forge.check_repo(self.target)
        self.assertFalse(status["has_agy_skills_json"])
        self.assertEqual(status["agy_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["claude_skills"], EXPECTED_SKILLS)

    def test_inherit_mode_writes_manifests_without_copying_skill_dirs(self):
        forge.provision(self.target, mode="inherit", agent="agy", include_scripts=False)
        status = forge.check_repo(self.target)
        self.assertTrue(status["has_agy_skills_json"])
        self.assertTrue(status["has_agy_plugins_json"])
        self.assertEqual(status["agy_skills"], [])
        self.assertEqual(status["claude_skills"], [])

    def test_agy_only_sync_does_not_touch_claude_or_overwrite_existing_agents_md(self):
        custom_agents = "# Custom Project AGENTS.md\n"
        (self.target / "AGENTS.md").write_text(custom_agents, encoding="utf-8")
        forge.provision(
            self.target,
            mode="hybrid",
            agent="agy",
            include_scripts=False,
            overwrite_existing_docs=False,
        )
        status = forge.check_repo(self.target)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), custom_agents)
        self.assertTrue(status["has_gemini_md"])
        self.assertFalse(status["has_claude_md"])
        self.assertEqual(status["agy_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["claude_skills"], [])

    def test_no_em_or_en_dashes_in_authored_markdown(self):
        for md in FORGE_ROOT.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            self.assertNotIn("\u2014", text, f"em dash found in {md}")
            self.assertNotIn("\u2013", text, f"en dash found in {md}")


if __name__ == "__main__":
    unittest.main()
