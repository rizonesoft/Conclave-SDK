"""Tests for forge.py provisioning modes, 3-agent isolation, stack kits, and prose hygiene."""
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
    "authoring-skills",
    "create-todo",
    "groom-plan",
    "local-tool-safety",
    "process-phase",
    "process-plan",
    "process-todo-file",
    "process-todo-section",
    "review-todo-section",
]

EXPECTED_CLAUDE_AGENTS = [
    "code-explorer",
    "debug-evidence",
    "git-runner",
    "mutation-tester",
    "section-implementer",
    "test-runner",
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
        self.assertTrue(status["has_verify_agent_tiers"])
        self.assertEqual(status["agy_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["claude_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["codex_skills"], EXPECTED_SKILLS)
        self.assertEqual(status["claude_agents"], EXPECTED_CLAUDE_AGENTS)
        self.assertTrue((self.target / "todo/README.md").is_file())
        self.assertTrue((self.target / "todo/TODO-00-INDEX.md").is_file())
        for skill in EXPECTED_SKILLS:
            self.assertTrue((self.target / ".codex/skills" / skill / "agents/openai.yaml").is_file())
            self.assertFalse((self.target / ".claude/skills" / skill / "agents/openai.yaml").exists())
            self.assertFalse((self.target / ".agents/skills" / skill / "agents/openai.yaml").exists())

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

    def test_list_kits_and_base_kit_additive_preservation(self):
        self.assertEqual(forge.list_kits(), ["base", "laravel", "wordpress"])
        (self.target / "AGENTS.md").write_text("locally tuned\n", encoding="utf-8")
        dry = forge.apply_kit(self.target, "base", dry_run=True)
        self.assertTrue(dry["dry_run"])
        self.assertIn("AGENTS.md", dry["preserved"])
        self.assertFalse((self.target / ".claude/skills/authoring-skills/SKILL.md").exists())

        res = forge.apply_kit(self.target, "base", dry_run=False)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "locally tuned\n")
        self.assertIn("AGENTS.md", res["preserved"])
        self.assertTrue((self.target / ".agents/skills/authoring-skills/SKILL.md").is_file())
        self.assertTrue((self.target / ".claude/skills/authoring-skills/SKILL.md").is_file())
        self.assertTrue((self.target / ".codex/skills/authoring-skills/SKILL.md").is_file())
        self.assertTrue((self.target / "scripts/verify-agent-tiers.mjs").is_file())

    def test_laravel_kit_root_and_nested_platform_discovery(self):
        with self.assertRaises(ValueError):
            forge.apply_kit(self.target, "laravel")

        nested = self.target / "monorepo"
        (nested / "platform").mkdir(parents=True)
        (nested / "platform/artisan").write_text("<?php\n", encoding="utf-8")
        res = forge.apply_kit(nested, "laravel")
        self.assertEqual(res["artisan"], "platform/artisan")
        self.assertTrue((nested / "platform/boost.json").is_file())
        self.assertTrue((nested / "scripts/lsp-diagnostics.py").is_file())
        self.assertTrue((nested / ".agents/skills/laravel-boost/SKILL.md").is_file())
        self.assertTrue((nested / ".claude/skills/laravel-boost/SKILL.md").is_file())
        self.assertTrue((nested / ".codex/skills/laravel-boost/SKILL.md").is_file())
        mcp = json.loads((nested / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp["mcpServers"]["laravel-boost"]["args"], ["platform/artisan", "boost:mcp"])

    def test_wordpress_kit_discovery_and_additive_install(self):
        with self.assertRaises(ValueError):
            forge.apply_kit(self.target, "wordpress")

        wp_site = self.target / "wpsite"
        (wp_site / "website").mkdir(parents=True)
        (wp_site / "website/wp-load.php").write_text("<?php\n", encoding="utf-8")
        res = forge.apply_kit(wp_site, "wordpress")
        self.assertEqual(res["wordpress"], "website")
        self.assertTrue((wp_site / "phpcs.xml.dist").is_file())
        self.assertTrue((wp_site / "tools/phpcs/composer.json").is_file())
        self.assertTrue((wp_site / ".agents/skills/wordpress-site-safety/SKILL.md").is_file())
        self.assertTrue((wp_site / ".claude/skills/wordpress-site-safety/SKILL.md").is_file())
        self.assertTrue((wp_site / ".codex/skills/wordpress-site-safety/SKILL.md").is_file())
        self.assertTrue((wp_site / "mcp.wordpress.example.json").is_file())

    def test_no_em_or_en_dashes_in_authored_markdown(self):
        for md in FORGE_ROOT.rglob("*.md"):
            if ".git" in md.parts:
                continue
            text = md.read_text(encoding="utf-8")
            self.assertNotIn("\u2014", text, f"em dash found in {md}")
            self.assertNotIn("\u2013", text, f"en dash found in {md}")

    def test_micro_todo_and_complete_plan_rules_present_across_all_agents(self):
        forge.provision(self.target, mode="isolated", agent="all", with_todo=True, overwrite_existing_docs=True)
        agents_text = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Small, single-responsibility sections", agents_text)
        self.assertIn("Granular micro-step checklist items", agents_text)
        self.assertIn("100% complete development plan", agents_text)
        self.assertIn("Commits follow logical steps", agents_text)
        todo_readme = (self.target / "todo/README.md").read_text(encoding="utf-8")
        self.assertIn("five-part rule", todo_readme)
        self.assertIn("100% complete development plan", todo_readme)
        for agent_dir in (".agents", ".claude", ".codex"):
            for skill in ("add-todo", "create-todo", "groom-plan", "process-todo-section", "review-todo-section"):
                skill_text = (self.target / agent_dir / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertNotIn("One section is one logical commit", skill_text)
            pts_text = (self.target / agent_dir / "skills/process-todo-section/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("Commits follow logical steps", pts_text)
            self.assertIn("five-part micro-steps", pts_text)
            groom_text = (self.target / agent_dir / "skills/groom-plan/SKILL.md").read_text(encoding="utf-8")
            self.assertIn("100% complete, shippable product", groom_text)
            self.assertIn("five-part rule", groom_text)

    def test_markdown_table_rows_do_not_wrap(self):
        for md in FORGE_ROOT.rglob("*.md"):
            if ".git" in md.parts:
                continue
            for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("|") and stripped.endswith("|"):
                    self.assertLessEqual(
                        len(line),
                        100,
                        f"Table row wraps raw md ({len(line)} > 100 chars) at {md}:{lineno}",
                    )


if __name__ == "__main__":
    unittest.main()
