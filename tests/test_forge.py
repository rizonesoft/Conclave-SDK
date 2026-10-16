"""Tests for forge.py provisioning modes, 3-agent isolation, stack kits, and prose hygiene."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

FORGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FORGE_ROOT))
import forge  # noqa: E402

BASE_SKILLS = ["authoring-skills", "local-tool-safety"]
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

    def test_init_installs_only_the_base_kit_unless_more_are_chosen(self):
        res = forge.provision(self.target)
        self.assertEqual([k["kit"] for k in res["kits"]], ["base"])
        status = forge.check_repo(self.target)
        self.assertEqual(status["claude_skills"], BASE_SKILLS)
        self.assertEqual(status["agy_skills"], BASE_SKILLS)
        self.assertEqual(status["codex_skills"], BASE_SKILLS)
        self.assertEqual(status["claude_agents"], EXPECTED_CLAUDE_AGENTS)
        self.assertTrue(status["has_verify_agent_tiers"])
        self.assertFalse(status["has_todo_graph"])
        self.assertFalse((self.target / "todo").exists())
        self.assertNotIn("todo-workflow", (self.target / "AGENTS.md").read_text(encoding="utf-8"))

    def test_init_with_todo_links_the_workflow_from_agents_md(self):
        res = forge.provision(self.target, kits=["todo"])
        self.assertEqual([k["kit"] for k in res["kits"]], ["base", "todo"])
        self.assertIn("docs/todo-workflow.md", (self.target / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual(forge.check_repo(self.target)["claude_skills"], EXPECTED_SKILLS)

    def test_sync_refreshes_only_the_kits_a_repo_has_and_never_project_files(self):
        forge.provision(self.target, with_todo=True)
        skill = self.target / ".claude/skills/create-todo/SKILL.md"
        skill.write_text("stale\n", encoding="utf-8")
        (self.target / "AGENTS.md").write_text("project rules\n", encoding="utf-8")
        (self.target / "todo/TODO-00-INDEX.md").write_text("our plan\n", encoding="utf-8")
        graph = self.target / "scripts/todo-graph.py"
        graph.write_text("old script\n", encoding="utf-8")

        res = forge.provision(self.target, refresh=True)
        self.assertEqual([k["kit"] for k in res["kits"]], ["base", "todo"])
        self.assertIn(".claude/skills/create-todo/SKILL.md", res["written"])
        self.assertEqual(skill.read_bytes(), (FORGE_ROOT / "kits/todo/templates/.claude/skills/create-todo/SKILL.md").read_bytes().replace(b"\r\n", b"\n"))
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "project rules\n")
        self.assertEqual((self.target / "todo/TODO-00-INDEX.md").read_text(encoding="utf-8"), "our plan\n")
        self.assertEqual(graph.read_text(encoding="utf-8"), "old script\n")
        self.assertFalse((self.target / ".conclave").exists())

        forge.provision(self.target, refresh=True, refresh_scripts=True)
        self.assertNotEqual(graph.read_text(encoding="utf-8"), "old script\n")

    def test_sync_never_writes_through_a_symlinked_skill_directory(self):
        forge.provision(self.target)
        outside = self.target.parent / (self.target.name + "-outside")
        outside.mkdir()
        try:
            (outside / "SKILL.md").write_text("theirs\n", encoding="utf-8")
            skill_dir = self.target / ".claude/skills/local-tool-safety"
            shutil.rmtree(skill_dir)
            skill_dir.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                forge.provision(self.target, refresh=True)
            self.assertEqual((outside / "SKILL.md").read_text(encoding="utf-8"), "theirs\n")
            self.assertEqual(sorted(f.name for f in outside.iterdir()), ["SKILL.md"])
        finally:
            shutil.rmtree(outside)

    def test_hybrid_mode_includes_skills_json_and_all_three_agents(self):
        forge.provision(self.target, mode="hybrid", agent="all")
        status = forge.check_repo(self.target)
        self.assertTrue(status["has_agy_skills_json"])
        self.assertEqual(status["agy_skills"], BASE_SKILLS)
        self.assertEqual(status["claude_skills"], BASE_SKILLS)
        self.assertEqual(status["codex_skills"], BASE_SKILLS)

    def test_inherit_mode_writes_manifests_without_copying_skill_dirs(self):
        forge.provision(self.target, mode="inherit", agent="agy", include_scripts=False)
        status = forge.check_repo(self.target)
        self.assertTrue(status["has_agy_skills_json"])
        self.assertTrue(status["has_agy_plugins_json"])
        self.assertEqual(status["agy_skills"], [])
        self.assertEqual(status["claude_skills"], [])
        self.assertEqual(status["codex_skills"], [])

    def test_single_agent_sync_and_gemini_alias_preserve_existing_docs(self):
        custom_agents = "# Custom Project AGENTS.md\n"
        (self.target / "AGENTS.md").write_text(custom_agents, encoding="utf-8")
        forge.provision(
            self.target,
            mode="isolated",
            agent="gemini",
            include_scripts=False,
            overwrite_existing_docs=False,
        )
        status = forge.check_repo(self.target)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), custom_agents)
        self.assertTrue(status["has_gemini_md"])
        self.assertFalse(status["has_claude_md"])
        self.assertFalse(status["has_codex_md"])
        self.assertEqual(status["agy_skills"], BASE_SKILLS)
        self.assertEqual(status["claude_skills"], [])
        self.assertEqual(status["codex_skills"], [])

    def test_list_kits_and_base_kit_additive_preservation_and_per_agent_import(self):
        self.assertEqual(forge.list_kits(), ["base", "laravel", "reviewer", "todo", "wordpress"])
        (self.target / "AGENTS.md").write_text("locally tuned\n", encoding="utf-8")
        dry = forge.apply_kit(self.target, "base", dry_run=True)
        self.assertTrue(dry["dry_run"])
        self.assertIn("AGENTS.md", dry["preserved"])
        self.assertFalse((self.target / ".claude/skills/authoring-skills/SKILL.md").exists())

        # Import base kit for codex only first, then claude, then gemini
        forge.apply_kit(self.target, "base", agent="codex")
        self.assertTrue((self.target / ".codex/skills/authoring-skills/SKILL.md").is_file())
        self.assertFalse((self.target / ".claude/skills/authoring-skills/SKILL.md").exists())
        self.assertFalse((self.target / ".agents/skills/authoring-skills/SKILL.md").exists())

        res = forge.apply_kit(self.target, "base", agent="all")
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "locally tuned\n")
        self.assertIn("AGENTS.md", res["preserved"])
        self.assertTrue((self.target / ".agents/skills/authoring-skills/SKILL.md").is_file())
        self.assertTrue((self.target / ".claude/skills/authoring-skills/SKILL.md").is_file())
        self.assertTrue((self.target / ".codex/skills/authoring-skills/SKILL.md").is_file())
        self.assertTrue((self.target / "scripts/verify-agent-tiers.mjs").is_file())

    def test_laravel_kit_root_and_nested_platform_discovery_and_doctor(self):
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

        doc = forge.doctor_repo(nested)
        self.assertEqual(doc["kit"], "laravel")
        by_name = {c["name"]: c["status"] for c in doc["checks"]}
        self.assertEqual(by_name["artisan"], "ok")
        self.assertEqual(by_name["boost.json"], "ok")
        self.assertEqual(by_name["skill:.agents"], "ok")
        self.assertEqual(by_name["skill:.claude"], "ok")
        self.assertEqual(by_name["skill:.codex"], "ok")

    def test_wordpress_kit_discovery_additive_install_and_doctor(self):
        with self.assertRaises(ValueError):
            forge.apply_kit(self.target, "wordpress", host="kinsta")

        wp_site = self.target / "wpsite"
        (wp_site / "website").mkdir(parents=True)
        (wp_site / "website/wp-load.php").write_text("<?php\n", encoding="utf-8")
        res = forge.apply_kit(wp_site, "wordpress")
        self.assertEqual(res["wordpress"], "website")
        self.assertEqual(res["host"], "pressable")
        self.assertTrue((wp_site / "phpcs.xml.dist").is_file())
        self.assertTrue((wp_site / "tools/phpcs/composer.json").is_file())
        for agent_dir in (".agents", ".claude", ".codex"):
            for skill in ("wordpress-site-safety", "wordpress-connect"):
                self.assertTrue((wp_site / agent_dir / "skills" / skill / "SKILL.md").is_file())
        self.assertTrue((wp_site / "mcp.wordpress.example.json").is_file())
        self.assertTrue((wp_site / ".ddev/providers/production.yaml").is_file())
        self.assertEqual(json.loads((wp_site / ".conclave/wordpress-site.json").read_text())["host"], "pressable")
        # Scripts are executable and nothing is world-writable, whatever the kit checkout's own modes are.
        self.assertEqual((wp_site / "bin/wp-remote").stat().st_mode & 0o777, 0o755)
        self.assertEqual((wp_site / "phpcs.xml.dist").stat().st_mode & 0o777, 0o644)

        doc = forge.doctor_repo(wp_site)
        self.assertEqual(doc["kit"], "wordpress")
        by_name = {c["name"]: c["status"] for c in doc["checks"]}
        self.assertEqual(by_name["site-pin"], "ok")
        self.assertEqual(by_name["site-identity"], "setup_required")
        self.assertEqual(by_name["wordpress-root"], "ok")
        self.assertEqual(by_name["phpcs.xml.dist"], "ok")
        self.assertEqual(by_name["helper:scripts/mcp-headers.py"], "ok")
        self.assertEqual(by_name["production-sync"], "setup_required")
        self.assertEqual(by_name["skill:wordpress-connect:.codex"], "ok")

    def test_wordpress_kit_for_a_wordpress_com_site(self):
        site = self.target / "wpcom"
        site.mkdir()
        res = forge.apply_kit(site, "wordpress", host="wpcom")
        self.assertIsNone(res["wordpress"])
        self.assertEqual(json.loads((site / ".conclave/wordpress-site.json").read_text())["host"], "wpcom")
        self.assertTrue((site / "bin/wp-remote").is_file())
        self.assertFalse((site / ".ddev").exists())
        self.assertFalse((site / "mcp.wordpress.example.json").exists())
        self.assertFalse((site / "scripts/mcp-headers.py").exists())

        doc = forge.doctor_repo(site)
        self.assertEqual(doc["kit"], "wordpress")
        by_name = {c["name"]: c["status"] for c in doc["checks"]}
        self.assertEqual(by_name["no-ddev"], "ok")
        self.assertNotIn("wordpress-root", by_name)
        self.assertNotIn("helper:scripts/mcp-headers.py", by_name)

        pin_path = site / ".conclave/wordpress-site.json"
        pin = json.loads(pin_path.read_text())
        pin.update(site_id=257780254, url="https://example.wpcomstaging.com")
        pin_path.write_text(json.dumps(pin))
        (site / ".ddev").mkdir()
        by_name = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(by_name["site-identity"], "ok")
        self.assertEqual(by_name["site-ssh"], "setup_required")
        self.assertEqual(by_name["no-ddev"], "unexpected")

        # A Simple site has no SSH: with ssh.ssh_host null the doctor asks for nothing SSH-related.
        (site / ".ddev").rmdir()
        pin_path.write_text(json.dumps({**pin, "ssh": {**pin["ssh"], "ssh_host": None}}))
        by_name = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(by_name["site-ssh"], "ok")
        self.assertNotIn("sshpass", by_name)

        # Re-applying the kit follows the pin, never adding Pressable files; a conflicting host is refused.
        pin_path.write_text(json.dumps(pin))
        res = forge.apply_kit(site, "wordpress")
        self.assertEqual(res["host"], "wpcom")
        self.assertFalse((site / ".ddev").exists())
        self.assertFalse((site / "scripts/mcp-headers.py").exists())
        with self.assertRaises(ValueError):
            forge.apply_kit(site, "wordpress", host="pressable")

        pin_path.write_text(json.dumps({**pin, "url": "http://example.com"}))
        by_name = {c["name"]: c["status"] for c in forge.doctor_repo(site, "wordpress")["checks"]}
        self.assertEqual(by_name["site-pin"], "missing")
        with self.assertRaises(ValueError):
            forge.apply_kit(site, "wordpress")

    def test_wordpress_doctor_checks_pressable_identity_and_mcp_registration(self):
        site = self.target / "pressable"
        site.mkdir()
        forge.apply_kit(site, "wordpress", host="pressable")
        pin_path = site / ".conclave/wordpress-site.json"
        pin = json.loads(pin_path.read_text())
        pin.update(site_id=1813618, url="https://example.com")
        pin["mcp"] = {
            "example-pressable": {"item": "abcdefghijklmnopqrstuvwxyz", "scheme": "bearer", "url": "https://mcp.pressable.com"},
            "example-wordpress": {"item": "zyxwvutsrqponmlkjihgfedcba", "scheme": "basic",
                                  "url": "https://example.com/wp-json/mcp/mcp-adapter-default-server",
                                  "username": "example", "wordpress_user_id": 1},
        }
        pin_path.write_text(json.dumps(pin))
        (site / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "example-pressable": {"type": "http", "url": "https://elsewhere.example.com"},
        }}))
        checks = {c["name"]: c for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(checks["site-identity"]["status"], "setup_required")
        self.assertIn("pressable.account_id", checks["site-identity"]["detail"])
        self.assertIn("url differs", checks["mcp:example-pressable"]["detail"])
        self.assertIn("application_password_uuid", checks["mcp:example-wordpress"]["detail"])
        self.assertIn(".mcp.json", checks["mcp:example-wordpress"]["detail"])

        pin["pressable"]["account_id"] = 1432766
        pin_path.write_text(json.dumps(pin))
        (site / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "example-pressable": {"type": "http", "url": "https://mcp.pressable.com"},
        }}))
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(checks["site-identity"], "ok")
        self.assertEqual(checks["mcp:example-pressable"], "ok")

    def test_wordpress_kit_helper_tests_pass(self):
        kit = FORGE_ROOT / "kits/wordpress"
        with tempfile.TemporaryDirectory() as tmp:
            scripts = pathlib.Path(tmp) / "scripts"
            shutil.copytree(kit / "templates/scripts", scripts)
            shutil.copytree(kit / "hosts/pressable/templates/scripts", scripts, dirs_exist_ok=True)
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(scripts / "tests")],
                                    capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_todo_kit_install_and_doctor(self):
        project = self.target / "planned"
        project.mkdir()
        res = forge.apply_kit(project, "todo")
        self.assertIn("scripts/todo-graph.py", res["installed"])
        self.assertIn("todo/README.md", res["installed"])
        self.assertEqual((project / "scripts/todo-graph.py").stat().st_mode & 0o777, 0o755)
        doc = forge.doctor_repo(project, "todo")
        self.assertEqual(doc["missing_or_setup_required"], 0, [c for c in doc["checks"] if c["status"] != "ok"])
        res = forge.apply_kit(project, "todo", agent="claude")
        self.assertEqual(res["installed"], [])

    def test_the_sdk_uses_the_agent_setup_its_kits_ship(self):
        # The kits are the only source. The SDK's own .agents/.claude/.codex are an installed copy of base and todo,
        # refreshed from the kits, so they must match them.
        def text(path):
            return path.read_bytes().replace(b"\r\n", b"\n")

        for kit in ("base", "todo"):
            templates = FORGE_ROOT / "kits" / kit / "templates"
            for source in sorted(templates.rglob("*")):
                rel = source.relative_to(templates).as_posix()
                if not source.is_file() or not rel.startswith(forge.SDK_MANAGED_PREFIXES):
                    continue
                with self.subTest(path=rel):
                    installed = FORGE_ROOT / rel
                    self.assertTrue(installed.is_file(), "missing from the SDK's own agent setup")
                    self.assertEqual(text(installed), text(source), "the SDK's own copy drifted from its kit")

    def test_reviewer_kit_install_doctor_and_sync_detection(self):
        project = self.target / "reviewed"
        project.mkdir()
        res = forge.apply_kit(project, "reviewer")
        self.assertIn(".conclave/reviewers.toml", res["installed"])
        self.assertEqual((project / "scripts/review-dispatch.py").stat().st_mode & 0o777, 0o755)
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual(checks["reviewer-pin"], "ok")
        self.assertEqual(checks["skill:independent-review:.claude"], "ok")
        self.assertEqual({k for k in checks if k.startswith("reviewer:")}, {"reviewer:astra", "reviewer:gemini", "reviewer:sonnet"})
        self.assertIn("reviewer", forge.installed_kits(project))

        (project / ".conclave/reviewers.toml").write_text("schema_version = 1\n", encoding="utf-8")
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual(checks["reviewer-pin"], "missing")

    def test_reviewer_kit_dispatcher_tests_pass(self):
        tests = FORGE_ROOT / "kits/reviewer/templates/scripts/tests"
        result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests)],
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_no_em_or_en_dashes_anywhere(self):
        # Every text file the SDK ships or provisions: prose, code, comments, templates and config alike.
        for path in FORGE_ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.assertNotIn("\u2014", text, f"em dash found in {path}")
            self.assertNotIn("\u2013", text, f"en dash found in {path}")

    def test_micro_todo_and_complete_plan_rules_present_across_all_agents(self):
        forge.provision(self.target, mode="isolated", agent="all", with_todo=True, overwrite_existing_docs=True)
        self.assertIn("docs/todo-workflow.md", (self.target / "AGENTS.md").read_text(encoding="utf-8"))
        agents_text = (self.target / "docs/todo-workflow.md").read_text(encoding="utf-8")
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

    def test_markdown_table_descriptions_within_88_chars_and_rows_do_not_wrap(self):
        for md in FORGE_ROOT.rglob("*.md"):
            if ".git" in md.parts:
                continue
            for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("|") and stripped.endswith("|"):
                    cells = [c.strip() for c in stripped.strip("|").split("|")]
                    for cell in cells:
                        if set(cell) <= {"-"}:
                            continue
                        self.assertLessEqual(
                            len(cell),
                            88,
                            f"Table cell exceeds 88 chars ({len(cell)} > 88) at {md}:{lineno}: {cell!r}",
                        )
                    self.assertLessEqual(
                        len(line),
                        140,
                        f"Table row wraps raw md ({len(line)} > 140 chars) at {md}:{lineno}",
                    )


if __name__ == "__main__":
    unittest.main()
