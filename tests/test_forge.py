"""Tests for forge.py provisioning modes, 3-agent isolation (agy, claude, codex), and prose hygiene."""
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

    def test_isolated_default_mode_provisions_all_three_agents_without_external_links(self):
        forge.provision(self.target, with_todo=True)
        status = forge.check_repo(self.target)
        self.assertTrue(status["has_agents_md"])
        self.assertTrue(status["has_gemini_md"])
        self.assertTrue(status["has_claude_md"])
        self.assertTrue(status["has_codex_md"])
        self.assertFalse(status["has_agy_skills_json"])
        self.assertFalse(status["has_agy_plugins_json"])
        self.assertTrue(status["has_todo_graph"])
        self.assertEqual(status["agy_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["claude_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["codex_skills"], EXPECTED_SKILLS)
        self.assertTrue((self.target / "todo/README.md").is_file())
        self.assertTrue((self.target / "todo/TODO-00-INDEX.md").is_file())

    def test_hybrid_mode_includes_skills_json_and_all_three_agents(self):
        forge.provision(self.target, mode="hybrid", agent="all")
        status = forge.check_repo(self.target)
        self.assertTrue(status["has_agy_skills_json"])
        self.assertEqual(status["agy_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["claude_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["codex_skills"], EXPECTED_SKILLS)

    def test_inherit_mode_writes_manifests_without_copying_skill_dirs(self):
        forge.provision(self.target, mode="inherit", agent="agy", include_scripts=False)
        status = forge.check_repo(self.target)
        self.assertTrue(status["has_agy_skills_json"])
        self.assertTrue(status["has_agy_plugins_json"])
        self.assertEqual(status["agy_skills"], [])
        self.assertEqual(status["claude_skills"], [])
        self.assertEqual(status["codex_skills"], [])

    def test_single_agent_sync_is_strictly_isolated_and_preserves_agents_md(self):
        custom_agents = "# Custom Project AGENTS.md\n"
        (self.target / "AGENTS.md").write_text(custom_agents, encoding="utf-8")
        forge.provision(
            self.target,
            mode="isolated",
            agent="codex",
            include_scripts=False,
            overwrite_existing_docs=False,
        )
        status = forge.check_repo(self.target)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), custom_agents)
        self.assertFalse(status["has_gemini_md"])
        self.assertFalse(status["has_claude_md"])
        self.assertTrue(status["has_codex_md"])
        self.assertEqual(status["agy_skills"], [])
        self.assertEqual(status["claude_skills"], [])
        self.assertEqual(status["codex_skills"], EXPECTED_SKILLS)

    def test_no_em_or_en_dashes_in_authored_markdown(self):
        for md in FORGE_ROOT.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            self.assertNotIn("\u2014", text, f"em dash found in {md}")
            self.assertNotIn("\u2013", text, f"en dash found in {md}")


if __name__ == "__main__":
    unittest.main()
