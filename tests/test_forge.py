"""Tests for forge.py provisioning modes, 3-agent isolation, stack kits, and prose hygiene."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

FORGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FORGE_ROOT))
import forge  # noqa: E402


def repository_files():
    """The SDK's own files: those git tracks or would track, so ignored output (an extension's node_modules, a build)
    is never held to the SDK's writing rules. Outside a git checkout, every file under the root but .git."""
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=FORGE_ROOT,
                            capture_output=True)
    if listed.returncode != 0:
        return [p for p in FORGE_ROOT.rglob("*") if ".git" not in p.parts and "__pycache__" not in p.parts]
    return [FORGE_ROOT / name for name in listed.stdout.decode("utf-8").split("\0") if name]


def provisioned_mode(posix_mode):
    """The mode atomic_write leaves on a file: exact on POSIX. Windows has no execute or group bits and keeps only
    the read-only flag, so a file forge wrote (always owner-writable) reads back as 0o666 there."""
    return posix_mode if os.name != "nt" else 0o666


BASE_SKILLS = ["adopt-conclave", "authoring-skills", "local-tool-safety"]
EXPECTED_SKILLS = [
    "add-todo",
    "adopt-conclave",
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

    def _link(self, target, link):
        # A junction on Windows (no rights needed, and it may dangle), a symlink elsewhere. Both stay under self.target.
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link)

    def test_init_refuses_a_target_inside_a_git_folder_even_through_a_dangling_link(self):
        git = self.target / "repo" / ".git"
        git.mkdir(parents=True)
        for path in (git / "new", self.target / "repo" / ".GIT" / "x" if os.name == "nt" else git / "x"):
            with self.assertRaisesRegex(ValueError, "inside a .git folder"):
                forge.provision(path)
        # The link's destination does not exist (made, linked, then removed, since Windows only links to a folder that
        # exists): resolving it is forge's own job, and the refusal follows it.
        (git / "not-created-yet").mkdir()
        self._link(git / "not-created-yet", self.target / "alias")
        (git / "not-created-yet").rmdir()
        with self.assertRaisesRegex(ValueError, "inside a .git folder"):
            forge.provision(self.target / "alias")
        with self.assertRaisesRegex(ValueError, "inside a .git folder"):
            forge.provision(self.target / "alias", refresh=True)
        self.assertEqual(sorted(p.name for p in git.iterdir()), [], "something was written inside .git")

    def test_init_refuses_the_sdk_source_folder_itself_but_sync_may_refresh_it(self):
        stand_in = self.target / "sdk"
        stand_in.mkdir()
        self._link(stand_in, self.target / "sdk-alias")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", stand_in.resolve()):
            for path in (stand_in, self.target / "sdk-alias"):
                with self.assertRaisesRegex(ValueError, "source folder itself"):
                    forge.provision(path)
            self.assertEqual(list(stand_in.iterdir()), [], "init wrote into the SDK folder")
            # The SDK refreshes its own installed copy with sync (AGENTS.md), so sync of the SDK folder itself, here a
            # stand-in carrying the base kit, is not refused.
            shutil.copytree(FORGE_ROOT / "kits" / "base", stand_in / "kits" / "base")
            res = forge.provision(stand_in, refresh=True)
            self.assertEqual([k["kit"] for k in res["kits"]], ["base"])
            self.assertTrue((stand_in / "AGENTS.md").is_file())

    def test_init_from_the_command_line_refuses_a_git_target_with_exit_2(self):
        (self.target / ".git").mkdir()
        proc = subprocess.run(
            [sys.executable, str(pathlib.Path(forge.__file__)), "init", str(self.target / ".git" / "new")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("forge.py: error: Target is inside a .git folder", proc.stderr)
        self.assertFalse((self.target / ".git" / "new").exists())

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
        # Only the kits the repo has: no reviewer pin, and the kit stamp (plan R38) names base and todo alone.
        self.assertFalse((self.target / ".conclave/reviewers.toml").exists())
        self.assertEqual(sorted(forge.read_kit_stamp(self.target)["kits"]), ["base", "todo"])

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
        self.assertEqual(forge.list_kits(), ["automations", "base", "laravel", "reviewer", "todo", "wordpress"])
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
        self.assertEqual((wp_site / "bin/wp-remote").stat().st_mode & 0o777, provisioned_mode(0o755))
        self.assertEqual((wp_site / "phpcs.xml.dist").stat().st_mode & 0o777, provisioned_mode(0o644))

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
        self.assertEqual((project / "scripts/todo-graph.py").stat().st_mode & 0o777, provisioned_mode(0o755))
        doc = forge.doctor_repo(project, "todo")
        self.assertEqual(doc["missing_or_setup_required"], 0, [c for c in doc["checks"] if c["status"] != "ok"])
        res = forge.apply_kit(project, "todo", agent="claude")
        self.assertEqual(res["installed"], [])

    def test_the_todo_kit_wires_the_stop_hook_and_never_overwrites_a_projects_settings(self):
        project = self.target / "guarded"
        (project / ".claude").mkdir(parents=True)
        own = '{"permissions": {"allow": ["Bash(git status)"]}}\n'
        (project / ".claude/settings.json").write_text(own, encoding="utf-8")
        res = forge.apply_kit(project, "todo")
        self.assertIn(".claude/settings.json", res["preserved"])
        self.assertIn("scripts/campaign_guard.py", res["installed"])
        self.assertEqual((project / ".claude/settings.json").read_text(encoding="utf-8"), own)
        checks = {c["name"]: c for c in forge.doctor_repo(project, "todo")["checks"]}
        self.assertEqual(checks["stop-hook"]["status"], "setup_required")
        self.assertIn("kits/todo/templates/.claude/settings.json", checks["stop-hook"]["detail"])
        for malformed in ('{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": null}]}]}}',
                          '{"hooks": {"Stop": "nope"}}', "[]", "{not json"):
            with self.subTest(malformed=malformed):
                (project / ".claude/settings.json").write_text(malformed, encoding="utf-8")
                checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "todo")["checks"]}
                self.assertEqual(checks["stop-hook"], "setup_required")
        (project / ".claude/settings.json").unlink()
        forge.apply_kit(project, "todo")
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "todo")["checks"]}
        self.assertEqual(checks["stop-hook"], "ok")
        self.assertNotIn(".claude/settings.json", forge.apply_kit(project, "todo", agent="codex")["installed"])

    def test_the_sdk_runs_the_stop_hook_its_todo_kit_ships(self):
        self.assertEqual(forge._stop_hook_wiring(FORGE_ROOT)[0], "ok")

    def test_the_sdk_uses_the_agent_setup_its_kits_ship(self):
        # The kits are the only source. The SDK's own .agents/.claude/.codex and scripts/ are an installed copy of
        # base, todo, reviewer and automations (the SDK plans, reviews and schedules its own work with them; the
        # owner chose on 2026-10-17 to keep base's scripts too, design/decisions.md), refreshed from the kits, so
        # they must match them.
        def text(path):
            return path.read_bytes().replace(b"\r\n", b"\n")

        for kit in ("base", "todo", "reviewer", "automations"):
            templates = FORGE_ROOT / "kits" / kit / "templates"
            prefixes = forge.SDK_MANAGED_PREFIXES + forge.SDK_MANAGED_SCRIPT_PREFIXES
            for source in sorted(templates.rglob("*")):
                rel = source.relative_to(templates).as_posix()
                if not source.is_file() or not rel.startswith(prefixes) or not forge._rel_allowed_for_agent(rel, "all"):
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
        self.assertEqual((project / "scripts/review-dispatch.py").stat().st_mode & 0o777, provisioned_mode(0o755))
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual(checks["reviewer-pin"], "ok")
        self.assertEqual(checks["skill:independent-review:.claude"], "ok")
        self.assertEqual({k for k in checks if k.startswith("reviewer:")}, {"reviewer:sol", "reviewer:sonnet"})
        self.assertIn("reviewer", forge.installed_kits(project))

        (project / ".conclave/reviewers.toml").write_text("schema_version = 1\n", encoding="utf-8")
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual(checks["reviewer-pin"], "missing")

    def test_reviewer_kit_dispatcher_tests_pass(self):
        tests = FORGE_ROOT / "kits/reviewer/templates/scripts/tests"
        result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests)],
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_automations_kit_install_doctor_and_sync_detection(self):
        project = self.target / "scheduled"
        project.mkdir()
        res = forge.apply_kit(project, "automations")
        for rel in (".conclave/automations/tasks.json", ".conclave/automations/run.py",
                    ".claude/skills/scheduled-automations/SKILL.md", "scripts/tests/test_automations.py"):
            self.assertIn(rel, res["installed"])
        self.assertEqual((project / ".conclave/automations/install.sh").stat().st_mode & 0o777, provisioned_mode(0o755))
        self.assertIn("automations", forge.installed_kits(project))
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "automations")["checks"]}
        self.assertEqual(checks["automations-tasks"], "ok")
        self.assertEqual(checks["automations-folder"], "setup_required")
        self.assertEqual(checks["skill:scheduled-automations:.codex"], "ok")

        tasks = project / ".conclave/automations/tasks.json"
        tasks.write_text(json.dumps({"schema_version": 1, "folder": "\\Demo\\", "tasks": [
            {"name": "demo-gone", "description": "a check whose script is missing",
             "command": ["python", "scripts/check-gone.py"], "trigger": {"weekly": "Monday", "at": "07:00"},
             "timeout_minutes": 5}]}), encoding="utf-8")
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "automations")["checks"]}
        self.assertEqual((checks["automations-folder"], checks["task:demo-gone"]), ("ok", "missing"))
        for malformed in ("[]", '{"schema_version": 1, "folder": "\\\\Demo\\\\", "tasks": [null]}', "{not json"):
            with self.subTest(malformed=malformed):
                tasks.write_text(malformed, encoding="utf-8")
                checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "automations")["checks"]}
                self.assertEqual(checks["automations-tasks"], "missing")
        tasks.write_text('{"schema_version": 1, "folder": "Demo", "tasks": []}', encoding="utf-8")
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "automations")["checks"]}
        self.assertEqual(checks["automations-tasks"], "missing")
        self.assertNotIn("automations-folder", checks)

        # sync keeps the project's task list and README, and refreshes the runner only with --include-scripts.
        runner = project / ".conclave/automations/run.py"
        runner.write_text("old runner\n", encoding="utf-8")
        forge.provision(project, refresh=True)
        self.assertEqual(runner.read_text(encoding="utf-8"), "old runner\n")
        forge.provision(project, refresh=True, refresh_scripts=True)
        self.assertNotEqual(runner.read_text(encoding="utf-8"), "old runner\n")
        self.assertEqual(tasks.read_text(encoding="utf-8"), '{"schema_version": 1, "folder": "Demo", "tasks": []}')

    def test_the_doctor_needs_a_systemd_user_manager_that_answers_not_just_systemctl(self):
        def answers(code, err=""):
            return lambda *a, **kw: subprocess.CompletedProcess(a, code, stdout="", stderr=err)

        with unittest.mock.patch.object(forge.shutil, "which", return_value="/usr/bin/systemctl"):
            self.assertEqual(forge._systemd_user_manager(answers(0))[0], "ok")
            status, detail = forge._systemd_user_manager(answers(1, "Failed to connect to bus: No medium found\n"))
            self.assertEqual(status, "setup_required")
            self.assertIn("No medium found", detail)
        with unittest.mock.patch.object(forge.shutil, "which", return_value=None):
            self.assertEqual(forge._systemd_user_manager(answers(0))[0], "setup_required")

    def test_automations_kit_tests_pass_in_the_kit_and_in_the_sdks_own_copy(self):
        for root in (FORGE_ROOT / "kits/automations/templates", FORGE_ROOT):
            with self.subTest(root=root):
                result = subprocess.run([sys.executable, "-B", str(root / "scripts/tests/test_automations.py")],
                                        capture_output=True, text=True, timeout=300)
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_no_em_or_en_dashes_anywhere(self):
        # Every text file the SDK ships or provisions: prose, code, comments, templates and config alike.
        for path in repository_files():
            if not path.is_file():
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
        for md in repository_files():
            if md.suffix != ".md" or not md.is_file():
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
                    # AGENTS.md: every table row at or under 100 characters, so rows never wrap in raw view.
                    self.assertLessEqual(
                        len(line),
                        100,
                        f"Table row wraps raw md ({len(line)} > 100 chars) at {md}:{lineno}",
                    )


class ForgeKitStampTests(unittest.TestCase):
    """The kit stamp (plan R38): which SDK commit and kit digests set a folder up, so a reader can tell older or newer
    kits from partly installed ones."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = pathlib.Path(self.tmp.name) / "project"
        self.target.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def stamp(self):
        path = self.target / ".conclave" / "kits.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def test_kit_digest_changes_with_any_template_file_but_not_with_crlf_endings(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        templates = sdk / "kits" / "demo" / "templates"
        templates.mkdir(parents=True)
        (templates / "a.md").write_bytes(b"one\ntwo\n")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            first = forge.kit_digest("demo")
            self.assertRegex(first, r"^[0-9a-f]{64}$")
            (templates / "a.md").write_bytes(b"one\r\ntwo\r\n")
            self.assertEqual(forge.kit_digest("demo"), first, "CRLF endings changed the digest")
            (templates / "a.md").write_bytes(b"one\ntwo!\n")
            changed = forge.kit_digest("demo")
            self.assertNotEqual(changed, first)
            (templates / "b.md").write_bytes(b"new\n")
            added = forge.kit_digest("demo")
            self.assertNotEqual(added, changed)
            (templates / "b.md").rename(templates / "c.md")
            self.assertNotEqual(forge.kit_digest("demo"), added, "a rename kept the digest")

    def test_digest_names_every_kit_and_the_sdk_commit_from_git_or_the_bundle_files(self):
        res = subprocess.run([sys.executable, str(FORGE_ROOT / "forge.py"), "digest"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        digest = json.loads(res.stdout)
        self.assertEqual(sorted(digest["kits"]), forge.list_kits())
        self.assertRegex(digest["sdk"]["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(digest["sdk"]["date"], r"^\d{4}-\d\d-\d\dT")
        # A bundled copy has no .git: the commit and date come from SDK_COMMIT and SDK_DATE next to forge.py.
        bundle = pathlib.Path(self.tmp.name) / "bundle"
        (bundle / "kits").mkdir(parents=True)
        (bundle / "SDK_COMMIT").write_text("a" * 40 + "\n", encoding="utf-8")
        (bundle / "SDK_DATE").write_text("2026-10-20T12:00:00+02:00\n", encoding="utf-8")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", bundle):
            self.assertEqual(forge.sdk_info(), {"commit": "a" * 40, "date": "2026-10-20T12:00:00+02:00"})

    def test_init_kit_and_sync_write_the_stamp_and_a_dry_run_writes_nothing(self):
        forge.apply_kit(self.target, "todo", dry_run=True)
        self.assertIsNone(self.stamp(), "a dry run wrote the stamp")
        forge.provision(self.target)
        stamp = self.stamp()
        self.assertEqual(stamp["schema_version"], 1)
        sdk = forge.sdk_info()
        self.assertEqual(stamp["kits"], {"base": {"digest": forge.kit_digest("base"), "commit": sdk["commit"], "date": sdk["date"]}})
        forge.apply_kit(self.target, "reviewer")
        self.assertEqual(sorted(self.stamp()["kits"]), ["base", "reviewer"], "a second kit dropped the first one's entry")
        # sync refreshes every kit the folder has, so each is stamped with this SDK.
        old = {"digest": "old", "commit": "b" * 40, "date": "2020-01-01T00:00:00Z"}
        (self.target / ".conclave" / "kits.json").write_text(json.dumps({"schema_version": 1, "kits": {"base": old, "reviewer": old}}), encoding="utf-8")
        forge.provision(self.target, refresh=True)
        for kit in ("base", "reviewer"):
            self.assertEqual(self.stamp()["kits"][kit], {"digest": forge.kit_digest(kit), "commit": sdk["commit"], "date": sdk["date"]})

    def _stale_stamp(self, kit):
        old = {"digest": "old", "commit": "b" * 40, "date": "2020-01-01T00:00:00Z"}
        (self.target / ".conclave" / "kits.json").write_text(json.dumps({"schema_version": 1, "kits": {kit: old}}), encoding="utf-8")
        return old

    def test_a_kit_whose_files_all_match_this_sdk_is_stamped_and_one_with_a_stale_file_keeps_its_old_entry(self):
        forge.apply_kit(self.target, "todo")
        old = self._stale_stamp("todo")
        # Every SDK-managed file already matches this SDK, so a re-run truthfully stamps it.
        forge.apply_kit(self.target, "todo")
        self.assertEqual(self.stamp()["kits"]["todo"]["digest"], forge.kit_digest("todo"))
        # A skill kept from an earlier install is not this SDK's: kit keeps it, so the old entry stands.
        self._stale_stamp("todo")
        (self.target / ".claude/skills/create-todo/SKILL.md").write_text("from an older SDK\n", encoding="utf-8")
        res = forge.apply_kit(self.target, "todo")
        self.assertIn(".claude/skills/create-todo/SKILL.md", res["preserved"])
        self.assertEqual(self.stamp()["kits"]["todo"], old)

    def test_sync_without_scripts_keeps_the_old_entry_while_a_script_is_stale(self):
        forge.provision(self.target, with_todo=True)
        old = self._stale_stamp("todo")
        (self.target / "scripts/todo-graph.py").write_text("old script\n", encoding="utf-8")
        forge.provision(self.target, refresh=True)
        self.assertEqual(self.stamp()["kits"]["todo"], old, "sync stamped a kit whose script it kept")
        forge.provision(self.target, refresh=True, refresh_scripts=True)
        self.assertEqual(self.stamp()["kits"]["todo"]["digest"], forge.kit_digest("todo"))

    def test_sync_for_one_agent_keeps_the_old_entry_while_another_agents_files_are_stale(self):
        forge.provision(self.target, with_todo=True)
        old = self._stale_stamp("todo")
        (self.target / ".codex/skills/create-todo/SKILL.md").write_text("from an older SDK\n", encoding="utf-8")
        forge.provision(self.target, refresh=True, agent="claude")
        self.assertEqual(self.stamp()["kits"]["todo"], old, "a claude-only sync stamped stale codex files as current")

    def test_a_managed_file_that_differs_only_in_crlf_endings_still_matches(self):
        forge.apply_kit(self.target, "todo")
        old = self._stale_stamp("todo")
        skill = self.target / ".claude/skills/create-todo/SKILL.md"
        skill.write_bytes(skill.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        forge.apply_kit(self.target, "todo")
        self.assertNotEqual(self.stamp()["kits"]["todo"], old, "the same content with CRLF endings was taken for an older file")
        self.assertEqual(self.stamp()["kits"]["todo"]["digest"], forge.kit_digest("todo"))

    def test_kit_digest_ignores_bytecode_the_installer_never_copies(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        templates = sdk / "kits" / "demo" / "templates"
        (templates / "scripts" / "__pycache__").mkdir(parents=True)
        (templates / "scripts" / "tool.py").write_bytes(b"print(1)\n")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            before = forge.kit_digest("demo")
            (templates / "scripts" / "__pycache__" / "tool.cpython-314.pyc").write_bytes(b"\x00bytecode")
            self.assertEqual(forge.kit_digest("demo"), before)

    def test_the_sdk_folder_itself_gets_no_stamp(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits" / "base", sdk / "kits" / "base")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk.resolve()):
            forge.provision(sdk, refresh=True)
        self.assertFalse((sdk / ".conclave" / "kits.json").exists(), "the SDK stamped itself")

    def _newer_reviewer(self):
        """A folder whose reviewer kit a later SDK set up: its stamp entry is dated after this SDK, and one of its
        skills holds that SDK's newer text."""
        forge.provision(self.target, kits=["todo", "reviewer"])
        stamp = forge.read_kit_stamp(self.target)
        stamp["kits"]["reviewer"] = {"digest": "later", "commit": "c" * 40, "date": "2099-01-01T00:00:00+00:00"}
        (self.target / ".conclave" / "kits.json").write_text(json.dumps(stamp), encoding="utf-8")
        skill = self.target / ".claude/skills/independent-review/SKILL.md"
        skill.write_text("from a newer SDK\n", encoding="utf-8")
        return stamp["kits"]["reviewer"], skill

    def test_sync_from_an_older_sdk_leaves_a_kit_stamped_newer_and_refreshes_the_rest(self):
        entry, skill = self._newer_reviewer()
        todo_skill = self.target / ".claude/skills/create-todo/SKILL.md"
        todo_skill.write_text("stale\n", encoding="utf-8")
        res = forge.provision(self.target, refresh=True)
        self.assertEqual(skill.read_text(encoding="utf-8"), "from a newer SDK\n", "sync replaced a kit stamped newer")
        self.assertEqual(forge.read_kit_stamp(self.target)["kits"]["reviewer"], entry)
        self.assertEqual([r["kit"] for r in res["refused_newer"]], ["reviewer"])
        self.assertIn("2099-01-01", res["refused_newer"][0]["reason"])
        self.assertNotIn("reviewer", [k["kit"] for k in res["kits"]])
        self.assertNotEqual(todo_skill.read_text(encoding="utf-8"), "stale\n", "the older kit was not refreshed")

    def test_kit_refuses_a_kit_stamped_newer_but_a_dry_run_still_reads_it(self):
        _entry, skill = self._newer_reviewer()
        with self.assertRaisesRegex(ValueError, "newer"):
            forge.apply_kit(self.target, "reviewer")
        self.assertEqual(skill.read_text(encoding="utf-8"), "from a newer SDK\n")
        forge.apply_kit(self.target, "reviewer", dry_run=True)
        res = subprocess.run([sys.executable, str(FORGE_ROOT / "forge.py"), "kit", str(self.target), "reviewer"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("newer", res.stderr)

    def test_an_unknown_date_on_either_side_is_never_taken_as_older(self):
        forge.provision(self.target, kits=["reviewer"])
        with unittest.mock.patch.object(forge, "sdk_info", return_value={"commit": None, "date": None}):
            res = forge.provision(self.target, refresh=True)
        # Every stamped kit: base and reviewer, so no kit result at all, and sync still answers.
        self.assertEqual([r["kit"] for r in res["refused_newer"]], ["base", "reviewer"])
        self.assertEqual(res["kits"], [])
        self.assertIn("unknown", res["refused_newer"][0]["reason"])

    def _stamp_reviewer(self, entry):
        if forge.read_kit_stamp(self.target) is None:
            forge.provision(self.target, kits=["reviewer"])
        stamp = forge.read_kit_stamp(self.target)
        stamp["kits"]["reviewer"] = entry
        (self.target / ".conclave" / "kits.json").write_text(json.dumps(stamp), encoding="utf-8")

    def test_a_date_without_a_time_zone_or_a_malformed_entry_is_refused_not_crashed_or_ignored(self):
        for entry in ({"digest": "x", "commit": "c" * 40, "date": "2099-01-01"},
                      {"digest": "x", "commit": "c" * 40, "date": "2099-01-01T00:00:00"},
                      "malformed", {"digest": "x", "commit": "c" * 40, "date": 2099}):
            self._stamp_reviewer(entry)
            res = forge.provision(self.target, refresh=True)
            self.assertIn("reviewer", [r["kit"] for r in res["refused_newer"]], repr(entry))
            self.assertEqual(forge.read_kit_stamp(self.target)["kits"]["reviewer"], entry, "a refused kit's entry was rewritten")

    def test_sync_that_refuses_a_kit_leaves_the_agent_manifests_as_they_are(self):
        forge.provision(self.target, kits=["reviewer"], mode="inherit", agent="all")
        stamp = forge.read_kit_stamp(self.target)
        stamp["kits"]["reviewer"] = {"digest": "later", "commit": "c" * 40, "date": "2099-01-01T00:00:00+00:00"}
        (self.target / ".conclave" / "kits.json").write_text(json.dumps(stamp), encoding="utf-8")
        manifests = {name: (self.target / ".agents" / name).read_bytes() for name in ("skills.json", "plugins.json")
                     if (self.target / ".agents" / name).is_file()}
        self.assertIn("skills.json", manifests)
        for mode in ("inherit", "isolated"):
            res = forge.provision(self.target, refresh=True, mode=mode, agent="all")
            self.assertEqual([r["kit"] for r in res["refused_newer"]], ["reviewer"])
            for name, before in manifests.items():
                # The same entries: the refused kit's as they were, the synced base kit's from this SDK as before.
                entries = lambda raw: sorted(e["path"] for e in json.loads(raw)["entries"])
                self.assertEqual(entries((self.target / ".agents" / name).read_bytes()), entries(before), f"{mode} sync changed {name}")

    def test_a_refusing_sync_keeps_the_refused_kits_manifest_entries_and_adds_the_others(self):
        forge.provision(self.target, kits=["reviewer"], mode="inherit", agent="all")
        stamp = forge.read_kit_stamp(self.target)
        stamp["kits"]["reviewer"] = {"digest": "later", "commit": "c" * 40, "date": "2099-01-01T00:00:00+00:00"}
        (self.target / ".conclave" / "kits.json").write_text(json.dumps(stamp), encoding="utf-8")
        skills = self.target / ".agents" / "skills.json"
        manifest = json.loads(skills.read_text(encoding="utf-8"))
        # The newer SDK's own path for the reviewer's skills, which this older SDK must not rewrite.
        newer_path = "/newer-sdk/kits/reviewer/templates/.agents/skills"
        manifest["entries"] = [e if "/kits/reviewer/" not in e["path"] else {"path": newer_path} for e in manifest["entries"]]
        skills.write_text(json.dumps(manifest), encoding="utf-8")
        res = forge.provision(self.target, refresh=True, kits=["todo"], mode="inherit", agent="all")
        self.assertEqual([r["kit"] for r in res["refused_newer"]], ["reviewer"])
        paths = [e["path"] for e in json.loads(skills.read_text(encoding="utf-8"))["entries"]]
        self.assertIn(newer_path, paths, "the refused kit's entry was dropped or rewritten")
        self.assertTrue(any("/kits/todo/" in p for p in paths), "the newly synced todo kit has no entry")
        self.assertTrue(any("/kits/base/" in p for p in paths))
        self.assertFalse(any("/kits/reviewer/" in p and p != newer_path for p in paths), "this SDK's reviewer path was added")

    def test_an_inherited_newer_kit_with_no_local_files_is_refused_and_keeps_its_entry(self):
        forge.provision(self.target, kits=["todo"], mode="inherit", agent="agy", include_scripts=False)
        self.assertNotIn("todo", forge.installed_kits(self.target), "the inherited kit must be invisible to installed_kits")
        stamp = forge.read_kit_stamp(self.target)
        stamp["kits"]["todo"] = {"digest": "later", "commit": "c" * 40, "date": "2099-01-01T00:00:00+00:00"}
        (self.target / ".conclave" / "kits.json").write_text(json.dumps(stamp), encoding="utf-8")
        skills = self.target / ".agents" / "skills.json"
        todo_entries = [e for e in json.loads(skills.read_text(encoding="utf-8"))["entries"] if "/kits/todo/" in e["path"]]
        self.assertTrue(todo_entries)
        res = forge.provision(self.target, refresh=True, mode="inherit", agent="agy", include_scripts=False)
        self.assertIn("todo", [r["kit"] for r in res["refused_newer"]])
        after = json.loads(skills.read_text(encoding="utf-8"))["entries"]
        for entry in todo_entries:
            self.assertIn(entry, after, "the newer inherited kit's entry was dropped")

    def test_a_malformed_manifest_is_read_as_no_entries(self):
        forge.provision(self.target, kits=["todo"], mode="inherit", agent="all")
        skills = self.target / ".agents" / "skills.json"
        for broken in ('{"entries": null}', '{"entries": "x"}', '[]', 'not json'):
            skills.write_text(broken, encoding="utf-8")
            forge.provision(self.target, refresh=True, mode="inherit", agent="all")
            self.assertIsInstance(json.loads(skills.read_text(encoding="utf-8"))["entries"], list, broken)

    def test_check_reports_the_stamp(self):
        self.assertIsNone(forge.check_repo(self.target)["kit_stamp"])
        forge.provision(self.target)
        self.assertEqual(forge.check_repo(self.target)["kit_stamp"], self.stamp())


class ProcessPlanAuditTests(unittest.TestCase):
    """process-plan's audit runs the kits' tests and the project's own: neither replaces the other (a project such as
    Recto keeps its script tests in tests/scripts, where kits install theirs under scripts/tests)."""

    def test_the_audit_runs_both_test_folders_in_every_agent_copy(self):
        for agent in (".agents", ".claude", ".codex"):
            text = (FORGE_ROOT / "kits/todo/templates" / agent / "skills/process-plan/SKILL.md").read_text(encoding="utf-8")
            audit = text.split("## 1. Audit the whole plan", 1)[1].split("## ", 1)[0]
            self.assertIn("python -m unittest discover -s scripts/tests", audit, agent)
            self.assertIn("python -m unittest discover -s tests/scripts", audit, agent)


class ForgeCliErrorTests(unittest.TestCase):
    """A refusal from forge's own checks is a one-line error and exit 2, never a traceback a caller must parse."""

    def test_kit_refusal_is_one_line_error_with_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(FORGE_ROOT / "forge.py"), "kit", tmp, "laravel", "--dry-run"],
                capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertTrue(result.stderr.startswith("forge.py: error: No artisan found under "), result.stderr)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)


if __name__ == "__main__":
    unittest.main()
