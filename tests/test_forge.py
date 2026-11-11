"""Tests for forge.py template provisioning, 3-agent isolation, stack kits, and prose hygiene."""
import contextlib
import importlib.util
import io
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
    """The SDK's own files: those git tracks or would track, so ignored output (a build, a cache)
    is never held to the SDK's writing rules. Outside a git checkout, every file under the root but .git."""
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=FORGE_ROOT,
                            capture_output=True)
    if listed.returncode != 0:
        return [p for p in FORGE_ROOT.rglob("*") if ".git" not in p.parts and "__pycache__" not in p.parts]
    return [FORGE_ROOT / name for name in listed.stdout.decode("utf-8").split("\0") if name]


# Imported material, copied byte for byte from the owner's retired configuration repositories: account-bound
# plugins and machine-level rules, hooks and skills. forge.py never installs it, and it is not held to the SDK's
# writing rules (its rules files quote the very characters those rules forbid).
IMPORTED = ("global/", "plugins/")
# Captured content: a reviewer's reply is recorded byte for byte under a digest, so its own punctuation stays.
CAPTURED = ("docs/reviews/",)


def written_files():
    """`repository_files` without the imported folders and the recorded reviews: what the SDK's writing rules
    apply to."""
    return [path for path in repository_files()
            if not path.relative_to(FORGE_ROOT).as_posix().startswith(IMPORTED + CAPTURED)
            or path.relative_to(FORGE_ROOT).as_posix() in ("global/README.md", "plugins/README.md")]


def provisioned_mode(posix_mode):
    """The mode atomic_write leaves on a file: exact on POSIX. Windows has no execute or group bits and keeps only
    the read-only flag, so a file forge wrote (always owner-writable) reads back as 0o666 there."""
    return posix_mode if os.name != "nt" else 0o666


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
    "test-runner",
]


def make_link(target, link):
    # A junction on Windows (no rights needed, and it may dangle), a symlink elsewhere.
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link)


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
        self.assertFalse((self.target / ".agents/skills.json").exists())
        self.assertFalse((self.target / ".agents/plugins.json").exists())
        self.assertEqual(sorted((forge.load_record(self.target) or {})["kits"]), ["base", "todo"])
        self.assertEqual(status["kits"], ["base", "todo"])
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
        make_link(target, link)

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
        self.assertEqual(sorted(p.name for p in git.iterdir()), [], "something was written inside .git")

    def test_init_refuses_the_sdk_source_folder_itself(self):
        stand_in = self.target / "sdk"
        stand_in.mkdir()
        self._link(stand_in, self.target / "sdk-alias")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", stand_in.resolve()):
            for path in (stand_in, self.target / "sdk-alias"):
                with self.assertRaisesRegex(ValueError, "source folder itself"):
                    forge.provision(path)
            self.assertEqual(list(stand_in.iterdir()), [], "init wrote into the SDK folder")

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

    def test_init_and_kit_copy_once_and_never_overwrite_the_projects_copy(self):
        # The SDK is a template: a second init or kit run adds only what is missing and leaves every file the project
        # already has, skills and scripts included, exactly as the project left it.
        forge.provision(self.target, with_todo=True)
        skill = self.target / ".claude/skills/create-todo/SKILL.md"
        skill.write_text("adapted\n", encoding="utf-8")
        graph = self.target / "scripts/todo-graph.py"
        graph.write_text("our script\n", encoding="utf-8")
        (self.target / ".codex/skills/create-todo/SKILL.md").unlink()

        res = forge.provision(self.target, with_todo=True)
        self.assertEqual(res["written"], [".codex/skills/create-todo/SKILL.md"])
        self.assertIn(".claude/skills/create-todo/SKILL.md", res["skipped"])
        self.assertEqual(skill.read_text(encoding="utf-8"), "adapted\n")
        self.assertEqual(graph.read_text(encoding="utf-8"), "our script\n")
        self.assertEqual(forge.apply_kit(self.target, "todo")["installed"], [])
        # The record names only files forge wrote, each as its template: never the project's own edit or script.
        record = forge.load_record(self.target) or {}
        templates = FORGE_ROOT / "kits/todo/templates"
        for rel in (".codex/skills/create-todo/SKILL.md", ".claude/skills/create-todo/SKILL.md", "scripts/todo-graph.py"):
            self.assertEqual(record["files"][rel],
                             {"kit": "todo", "sha256": forge.file_digest((templates / rel).read_bytes())}, rel)
        on_disk = {p.relative_to(self.target).as_posix() for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(set(record["files"]), on_disk - {forge.RECORD})

    def test_the_cli_has_no_sync_or_mode_that_links_a_project_to_the_sdk(self):
        for argv in (["sync", str(self.target)], ["digest"], ["init", str(self.target), "--mode", "inherit"]):
            with self.subTest(argv=argv):
                proc = subprocess.run([sys.executable, str(pathlib.Path(forge.__file__)), *argv],
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(list(self.target.iterdir()), [])

    def record_strings(self, value):
        if isinstance(value, dict):
            for key, inner in value.items():
                yield key
                yield from self.record_strings(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from self.record_strings(inner)
        elif isinstance(value, str):
            yield value

    def paths_to_the_sdk(self, record):
        """Every string in a record that is an absolute path or names the SDK's folder."""
        sdk = FORGE_ROOT.as_posix().lower()
        return [text for text in self.record_strings(record)
                if sdk in text.replace("\\", "/").lower()
                or pathlib.PurePosixPath(text).is_absolute() or pathlib.PureWindowsPath(text).is_absolute()]

    def test_the_install_record_holds_no_path_to_the_sdk(self):
        forge.provision(self.target, kits=["todo", "reviewer", "automations"])
        record = json.loads((self.target / forge.RECORD).read_text(encoding="utf-8"))
        self.assertEqual(self.paths_to_the_sdk(record), [])
        # A record that did name the SDK is caught by the same check, and refused by the loader as an unknown key.
        self.assertEqual(self.paths_to_the_sdk({**record, "source": str(FORGE_ROOT)}), [str(FORGE_ROOT)])
        (self.target / forge.RECORD).write_text(json.dumps({**record, "source": str(FORGE_ROOT)}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "kits.json"):
            forge.load_record(self.target)

    def test_self_sync_refreshes_only_the_sdks_own_installed_copy(self):
        stand_in = self.target / "sdk"
        for kit in forge.SELF_KITS:
            shutil.copytree(FORGE_ROOT / "kits" / kit, stand_in / "kits" / kit)
        (stand_in / "AGENTS.md").write_text("sdk rules\n", encoding="utf-8")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", stand_in.resolve()):
            first = forge.self_sync()
            self.assertIn(".claude/skills/create-todo/SKILL.md", first["updated"])
            self.assertIn("scripts/todo-graph.py", first["updated"])
            self.assertIn(".conclave/automations/run.py", first["updated"])
            self.assertNotIn(".conclave/automations/tasks.json", first["updated"])
            self.assertNotIn(".conclave/reviewers.toml", first["updated"])
            self.assertIn("docs/todo-workflow.md", first["updated"])
            self.assertFalse(any(rel.startswith("todo/") for rel in first["updated"]))
            self.assertEqual((stand_in / "AGENTS.md").read_text(encoding="utf-8"), "sdk rules\n")
            (stand_in / ".claude/skills/create-todo/SKILL.md").write_text("drifted\n", encoding="utf-8")
            self.assertEqual(forge.self_sync(dry_run=True)["updated"], [".claude/skills/create-todo/SKILL.md"])
            self.assertEqual(forge.self_sync()["updated"], [".claude/skills/create-todo/SKILL.md"])
            self.assertEqual(forge.self_sync()["updated"], [])

    def test_single_agent_init_and_gemini_alias_preserve_existing_docs(self):
        custom_agents = "# Custom Project AGENTS.md\n"
        (self.target / "AGENTS.md").write_text(custom_agents, encoding="utf-8")
        forge.provision(
            self.target,
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

    # What each agent choice leaves out, written here and not read from forge: the other agents' folders and entry docs.
    AGENT_FILES = {"agy": (".agents/", "GEMINI.md"), "claude": (".claude/", "CLAUDE.md"), "codex": (".codex/", "CODEX.md")}
    LARAVEL_FILES = (
        "scripts/lsp-diagnostics.py", "scripts/hooks/laravel-lsp-pre-push.sh", "docs/laravel-agent-tooling.md",
        ".agents/skills/laravel-boost/SKILL.md", ".claude/skills/laravel-boost/SKILL.md",
        ".codex/skills/laravel-boost/SKILL.md", ".codex/skills/laravel-boost/agents/openai.yaml",
    )

    def kept_for(self, rel, agent):
        """The test's own agent rule: a path in another agent's folder, or another agent's entry doc, is left out."""
        if agent == "all":
            return True
        return not any(rel == doc or rel.startswith(folder)
                       for other, (folder, doc) in self.AGENT_FILES.items() if other != agent)

    def expected_plan(self, kit, agent, host=None):
        """relative path -> template file, derived by walking the kit's folders: never from forge's own list."""
        kits = FORGE_ROOT / "kits"
        if kit == "laravel":
            expected: dict[str, pathlib.Path | None] = {
                rel: kits / "laravel/templates" / rel for rel in self.LARAVEL_FILES if self.kept_for(rel, agent)}
            expected["platform/boost.json"] = kits / "laravel/templates/boost.json"
            expected[".mcp.json"] = None
            return expected
        roots = [kits / kit / "templates"] + ([kits / kit / "hosts" / host / "templates"] if host else [])
        expected = {}
        for root in roots:
            for path in root.rglob("*"):
                rel = path.relative_to(root).as_posix()
                if path.is_file() and "__pycache__" not in path.parts and self.kept_for(rel, agent):
                    expected[rel] = path
        return expected

    def kit_fixtures(self):
        """(kit, host, an empty project the kit can be planned for) for every kit and every WordPress host."""
        cases = [(kit, None) for kit in forge.list_kits() if kit != "wordpress"]
        cases += [("wordpress", host) for host in forge.WORDPRESS_HOSTS]
        for index, (kit, host) in enumerate(cases):
            project = self.target / f"project-{index}"
            project.mkdir()
            if kit == "laravel":
                (project / "platform").mkdir()
                (project / "platform/artisan").write_text("<?php\n", encoding="utf-8")
            yield kit, host, project.resolve()

    def test_kit_plan_lists_each_kits_files_for_each_agent(self):
        for kit, host, project in self.kit_fixtures():
            for agent in ("all", "claude", "codex", "agy"):
                with self.subTest(kit=kit, host=host, agent=agent):
                    entries, _extra = forge.kit_plan(project, kit, agent=agent, host=host)
                    expected = self.expected_plan(kit, agent, host)
                    self.assertEqual(sorted(rel for _src, _dst, rel, _generated in entries), sorted(expected))
                    for src, dst, rel, generated in entries:
                        self.assertEqual(dst, project / rel)
                        self.assertEqual(generated, expected[rel] is None, rel)
                        if generated:
                            self.assertIsNone(src)
                        else:
                            self.assertEqual(src, expected[rel])
                            self.assertTrue(src.is_file(), src)
                        for other, (folder, doc) in self.AGENT_FILES.items():
                            if agent not in ("all", other):
                                self.assertFalse(rel.startswith(folder) or rel == doc, rel)

    def test_kit_plan_refuses_what_the_kit_cannot_be_planned_for(self):
        with self.assertRaisesRegex(ValueError, "No artisan"):
            forge.kit_plan(self.target, "laravel")
        with self.assertRaisesRegex(ValueError, "Unknown WordPress host"):
            forge.kit_plan(self.target, "wordpress", host="kinsta")
        with self.assertRaisesRegex(ValueError, "Unknown kit"):
            forge.kit_plan(self.target, "nope")
        forge.apply_kit(self.target, "wordpress", host="wpcom")
        with self.assertRaisesRegex(ValueError, "pins host 'wpcom'"):
            forge.kit_plan(self.target, "wordpress", host="pressable")

    def test_a_fresh_install_writes_exactly_the_planned_files(self):
        for kit, host, project in self.kit_fixtures():
            with self.subTest(kit=kit, host=host):
                entries, _extra = forge.kit_plan(project, kit, host=host)
                before = {p for p in project.rglob("*") if p.is_file()}
                res = forge.apply_kit(project, kit, host=host)
                self.assertEqual(sorted(res["installed"]), sorted(rel for _src, _dst, rel, _generated in entries))
                written = {p for p in project.rglob("*") if p.is_file()} - before - {project / forge.RECORD}
                self.assertEqual(written, {dst for _src, dst, _rel, _generated in entries})
                for src, dst, rel, generated in entries:
                    if not generated:
                        self.assertEqual(dst.read_bytes(), src.read_bytes(), rel)

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
        by_name = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(by_name["site-identity"], "ok")
        self.assertEqual(by_name["site-ssh"], "setup_required")

        # An Atomic site has SSH, so it may opt into the pull-only mirror: the doctor then checks it like Pressable's.
        (site / ".ddev").mkdir()
        by_name = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}
        self.assertNotIn("no-ddev", by_name)
        self.assertEqual(by_name["ddev-config"], "setup_required")
        self.assertEqual(by_name["production-sync"], "setup_required")
        self.assertEqual(by_name["helper:.ddev/providers/production.yaml"], "missing")

        # The site's own MCP servers may sit beside the connector; each must be registered in .mcp.json.
        own = {"item": "abcdefghijklmnopqrstuvwxyz", "scheme": "basic", "url": pin["url"] + "/wp-json/elementor/mcp",
               "username": "example", "wordpress_user_id": 1, "application_password_uuid": None}
        pin_path.write_text(json.dumps({**pin, "mcp": {"example-elementor": own}}))
        checks = {c["name"]: c for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(checks["site-pin"]["status"], "ok")
        self.assertIn("application_password_uuid", checks["mcp:example-elementor"]["detail"])
        self.assertIn(".mcp.json", checks["mcp:example-elementor"]["detail"])
        self.assertEqual(checks["helper:scripts/mcp-headers.py"]["status"], "missing")
        self.assertNotIn("mcp-pinned", checks)

        # A registration must be an http server whose credential comes from this checkout's helper for this connection.
        full = {**own, "application_password_uuid": "62a010d2-6cf8-4200-abb0-d80117954d9c"}
        pin_path.write_text(json.dumps({**pin, "mcp": {"example-elementor": full}}))
        helper = f"python3 {(site / 'scripts/mcp-headers.py').as_posix()} example-elementor"
        good = {"type": "http", "url": full["url"], "headersHelper": helper}
        for bad, reason in (({**good, "type": None}, "type must be http"),
                            ({"type": "http", "url": full["url"]}, "headersHelper"),
                            ({**good, "headersHelper": helper.replace("example-elementor", "other")}, "headersHelper"),
                            ({**good, "headersHelper": "python3 /elsewhere/scripts/mcp-headers.py example-elementor"},
                             "headersHelper")):
            with self.subTest(registration=bad):
                (site / ".mcp.json").write_text(json.dumps({"mcpServers": {"example-elementor": bad}}))
                check = {c["name"]: c for c in forge.doctor_repo(site)["checks"]}["mcp:example-elementor"]
                self.assertEqual(check["status"], "setup_required")
                self.assertIn(reason, check["detail"])
        quoted = {**good, "headersHelper": f'python3 "{(site / "scripts/mcp-headers.py").as_posix()}" example-elementor'}
        for registration in (good, quoted):
            with self.subTest(registration=registration):
                (site / ".mcp.json").write_text(json.dumps({"mcpServers": {"example-elementor": registration}}))
                status = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}["mcp:example-elementor"]
                self.assertEqual(status, "ok")
        (site / ".mcp.json").write_text(json.dumps({"mcpServers": {"example-elementor": {**good, "headersHelper": 'python3 "x'}}}))
        status = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}["mcp:example-elementor"]
        self.assertEqual(status, "setup_required")
        (site / ".mcp.json").unlink()

        # A Simple site has no SSH: with ssh.ssh_host null the doctor asks for nothing SSH-related, and a mirror is wrong.
        pin_path.write_text(json.dumps({**pin, "ssh": {**pin["ssh"], "ssh_host": None}}))
        by_name = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(by_name["site-ssh"], "ok")
        self.assertNotIn("sshpass", by_name)
        self.assertEqual(by_name["no-ddev"], "unexpected")
        self.assertNotIn("ddev-config", by_name)
        (site / ".ddev").rmdir()
        by_name = {c["name"]: c["status"] for c in forge.doctor_repo(site)["checks"]}
        self.assertEqual(by_name["no-ddev"], "ok")

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
            "example-pressable": {"type": "http", "url": "https://mcp.pressable.com",
                                  # Quoted, as a shell takes it: the doctor splits the command the same way.
                                  "headersHelper": f'python3 "{(site / "scripts/mcp-headers.py").as_posix()}" example-pressable'},
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
        # owner chose on 2026-10-17 to keep base's scripts too), refreshed from the kits by
        # `forge.py self-sync`, so they must match them.
        def text(path):
            return path.read_bytes().replace(b"\r\n", b"\n")

        for kit in ("base", "todo", "reviewer", "automations"):
            templates = FORGE_ROOT / "kits" / kit / "templates"
            prefixes = forge.SELF_PREFIXES
            for source in sorted(templates.rglob("*")):
                rel = source.relative_to(templates).as_posix()
                if not source.is_file() or not rel.startswith(prefixes) or not forge._rel_allowed_for_agent(rel, "all"):
                    continue
                with self.subTest(path=rel):
                    installed = FORGE_ROOT / rel
                    self.assertTrue(installed.is_file(), "missing from the SDK's own agent setup")
                    self.assertEqual(text(installed), text(source), "the SDK's own copy drifted from its kit")

    def test_reviewer_kit_install_doctor_and_detection(self):
        project = self.target / "reviewed"
        project.mkdir()
        res = forge.apply_kit(project, "reviewer")
        self.assertIn(".conclave/reviewers.toml", res["installed"])
        self.assertEqual((project / "scripts/review-dispatch.py").stat().st_mode & 0o777, provisioned_mode(0o755))
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual(checks["reviewer-pin"], "ok")
        self.assertEqual(checks["skill:independent-review:.claude"], "ok")
        self.assertEqual({k for k in checks if k.startswith("reviewer:")}, {"reviewer:astra"})
        self.assertIn("reviewer", forge.installed_kits(project))

        (project / ".conclave/reviewers.toml").write_text("schema_version = 1\n", encoding="utf-8")
        checks = {c["name"]: c["status"] for c in forge.doctor_repo(project, "reviewer")["checks"]}
        self.assertEqual(checks["reviewer-pin"], "missing")

    @unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "slow: set CONCLAVE_FULL_TESTS=1 for the full suite")
    def test_reviewer_kit_dispatcher_tests_pass(self):
        tests = FORGE_ROOT / "kits/reviewer/templates/scripts/tests"
        # The suite drives a fake reviewer through real git repositories for the three-pass order (about five
        # minutes on Windows, where each reviewer process tree is ended with taskkill); the limit only catches a hang.
        result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests)],
                                capture_output=True, text=True, timeout=900)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_automations_kit_install_doctor_and_detection(self):
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
        for path in written_files():
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.assertNotIn("\u2014", text, f"em dash found in {path}")
            self.assertNotIn("\u2013", text, f"en dash found in {path}")

    def test_micro_todo_and_complete_plan_rules_present_across_all_agents(self):
        forge.provision(self.target, agent="all", with_todo=True, overwrite_existing_docs=True)
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
        for md in written_files():
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
                    # AGENTS.md: every table row at or under 120 characters, so rows never wrap in raw view.
                    self.assertLessEqual(
                        len(line),
                        120,
                        f"Table row wraps raw md ({len(line)} > 120 chars) at {md}:{lineno}",
                    )


class InstallRecordTests(unittest.TestCase):
    """`.conclave/kits.json`: what forge installed, as a note the project owns."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = pathlib.Path(self.tmp.name) / "project"
        self.target.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, target=None):
        record = forge.load_record(target or self.target)
        self.assertIsNotNone(record)
        return record or {}

    def files_under(self, root):
        return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())

    def template_digest(self, kit, rel):
        return forge.file_digest((FORGE_ROOT / "kits" / kit / "templates" / rel).read_bytes())

    def valid_record(self):
        return {"schema_version": 1,
                "kits": {"todo": {"sdk_commit": "a" * 40, "agents": ["claude", "codex"], "host": None}},
                "files": {"scripts/todo-graph.py": {"kit": "todo", "sha256": "b" * 64}}}

    def write_raw(self, data):
        path = self.target / forge.RECORD
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else json.dumps(data).encode("utf-8"))

    def test_the_digest_reads_crlf_as_lf(self):
        self.assertEqual(forge.file_digest(b"one\ntwo\n"), forge.file_digest(b"one\r\ntwo\r\n"))
        self.assertNotEqual(forge.file_digest(b"one\ntwo\n"), forge.file_digest(b"one\ntwo!\n"))
        self.assertRegex(forge.file_digest(b""), r"^[0-9a-f]{64}$")

    def test_a_missing_record_is_none_and_a_valid_one_reads_back(self):
        self.assertIsNone(forge.load_record(self.target))
        forge.write_record(self.target, self.valid_record())
        self.assertEqual(forge.load_record(self.target), self.valid_record())
        text = (self.target / forge.RECORD).read_text(encoding="utf-8")
        self.assertEqual(text, json.dumps(self.valid_record(), indent=2, sort_keys=True) + "\n")

    def test_every_malformed_record_refuses_by_name(self):
        def changed(**parts):
            record = self.valid_record()
            for dotted, value in parts.items():
                at = record
                *path, last = dotted.split("__")
                for key in path:
                    at = at[key]
                if value is KeyError:
                    del at[last]
                else:
                    at[last] = value
            return record

        file_entry = {"kit": "todo", "sha256": "b" * 64}
        faults = {
            "not UTF-8": b"\xff\xfe{",
            "not JSON": b"{nope",
            "not an object": [1],
            "a key twice": b'{"schema_version": 1, "kits": {}, "files": {"a": {"kit": "todo", "sha256": "'
                           + b"b" * 64 + b'"}}, "files": {}}',
            "a nested key twice": json.dumps(self.valid_record()).replace(
                '"host": null', '"host": null, "host": null').encode("utf-8"),
            "nested too deeply": b"[" * 20000 + b"0" + b"]" * 20000,
            "missing top key": changed(files=KeyError),
            "unknown top key": changed(source="x"),
            "another schema_version": changed(schema_version=2),
            "boolean schema_version": changed(schema_version=True),
            "kits not an object": changed(kits=[]),
            "files not an object": {**self.valid_record(), "files": []},
            "unknown kit": {"schema_version": 1, "kits": {"nope": self.valid_record()["kits"]["todo"]}, "files": {}},
            "kit missing key": changed(kits__todo__host=KeyError),
            "kit unknown key": changed(kits__todo__path="x"),
            "commit not hex": changed(kits__todo__sdk_commit="HEAD"),
            "commit upper case": changed(kits__todo__sdk_commit="A" * 40),
            "agents empty": changed(kits__todo__agents=[]),
            "agents unsorted": changed(kits__todo__agents=["codex", "claude"]),
            "agents repeated": changed(kits__todo__agents=["claude", "claude"]),
            "agents unknown": changed(kits__todo__agents=["all"]),
            "agents not a list": changed(kits__todo__agents="claude"),
            "host unknown": changed(kits__todo__host="kinsta"),
            "absolute path": changed(files={"/etc/passwd": file_entry}),
            "drive path": changed(files={"C:/x": file_entry}),
            "backslash path": changed(files={"scripts\\x.py": file_entry}),
            "parent path": changed(files={"scripts/../x": file_entry}),
            "empty segment": changed(files={"scripts//x": file_entry}),
            "file not an object": changed(files={"a": "b"}),
            "file unknown key": changed(files={"a": {**file_entry, "size": 1}}),
            "digest short": changed(files={"a": {"kit": "todo", "sha256": "b" * 63}}),
            "digest upper case": changed(files={"a": {"kit": "todo", "sha256": "B" * 64}}),
            "file of an unrecorded kit": changed(files={"a": {"kit": "base", "sha256": "b" * 64}}),
        }
        for name, data in faults.items():
            with self.subTest(fault=name):
                self.write_raw(data)
                with self.assertRaisesRegex(ValueError, r"\.conclave/kits\.json: .+"):
                    forge.load_record(self.target)
        # The command line reports it as forge's other refusals are: one line, exit 2, nothing written.
        self.write_raw(changed(kits__todo__agents=["all"]))
        before = self.files_under(self.target)
        proc = subprocess.run([sys.executable, str(pathlib.Path(forge.__file__)), "kit", str(self.target), "todo"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1, proc.stderr)
        self.assertIn(".conclave/kits.json: kits.todo.agents", proc.stderr)
        self.assertEqual(self.files_under(self.target), before)

    def test_two_identical_installs_leave_identical_records(self):
        other = pathlib.Path(self.tmp.name) / "other"
        other.mkdir()
        for project in (self.target, other):
            forge.apply_kit(project, "todo")
        self.assertEqual((self.target / forge.RECORD).read_bytes(), (other / forge.RECORD).read_bytes())

    def test_the_sdk_commit_is_exact_or_null(self):
        head = subprocess.run(["git", "-C", str(FORGE_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
        if head.returncode == 0:
            self.assertEqual(forge.sdk_commit(), head.stdout.strip())
            forge.apply_kit(self.target, "base")
            self.assertEqual(self.record()["kits"]["base"]["sdk_commit"], head.stdout.strip())

        def missing(*_args, **_kwargs):
            raise FileNotFoundError("git")

        def slow(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

        def failed(*args, **_kwargs):
            return subprocess.CompletedProcess(args[0], 128, "", "fatal: not a git repository")

        for name, run in (("no git", missing), ("timeout", slow), ("git fails", failed)):
            with self.subTest(case=name):
                self.assertIsNone(forge.sdk_commit(run=run))
        outside = pathlib.Path(self.tmp.name) / "copy"
        outside.mkdir()
        with unittest.mock.patch.object(forge, "FORGE_ROOT", outside):
            self.assertIsNone(forge.sdk_commit())
        # In the record an unknown commit is JSON null, not a string.
        fresh = pathlib.Path(self.tmp.name) / "fresh"
        fresh.mkdir()
        with unittest.mock.patch.object(forge, "sdk_commit", lambda: None):
            forge.apply_kit(fresh, "base")
        self.assertIn('"sdk_commit": null', (fresh / forge.RECORD).read_text(encoding="utf-8"))
        self.assertIsNone(self.record(fresh)["kits"]["base"]["sdk_commit"])

    def test_a_record_that_cannot_be_used_refuses_before_any_file_is_written(self):
        def refused(prepare, label):
            project = pathlib.Path(self.tmp.name) / label
            project.mkdir()
            prepare(project)
            before = self.files_under(project)
            with self.assertRaisesRegex(ValueError, r"\.conclave/kits\.json"):
                forge.apply_kit(project, "todo")
            self.assertEqual(self.files_under(project), before)

        def malformed(project):
            (project / ".conclave").mkdir()
            (project / forge.RECORD).write_text("{nope", encoding="utf-8")

        def conclave_is_a_file(project):
            (project / ".conclave").write_text("not a folder\n", encoding="utf-8")

        def record_is_a_folder(project):
            (project / forge.RECORD).mkdir(parents=True)

        def conclave_is_a_link(project):
            elsewhere = pathlib.Path(self.tmp.name) / f"elsewhere-{project.name}"
            elsewhere.mkdir()
            if os.name == "nt":
                import _winapi

                _winapi.CreateJunction(str(elsewhere), str(project / ".conclave"))
            else:
                os.symlink(elsewhere, project / ".conclave")

        refused(malformed, "malformed")
        refused(conclave_is_a_file, "file")
        refused(record_is_a_folder, "folder")
        refused(conclave_is_a_link, "link")

        def record_is_a_link(project):
            (project / ".conclave").mkdir()
            real = pathlib.Path(self.tmp.name) / "real.json"
            real.write_text(json.dumps(self.valid_record()), encoding="utf-8")
            os.symlink(real, project / forge.RECORD)

        try:
            refused(record_is_a_link, "record-link")
        except OSError as error:  # Windows without the right to create a file symlink
            self.skipTest(f"cannot create a file symlink here: {error}")

    def test_only_files_forge_wrote_are_recorded_as_their_templates(self):
        own = self.target / "scripts/todo-graph.py"
        own.parent.mkdir()
        own.write_text("the project's own graph\n", encoding="utf-8")
        forge.apply_kit(self.target, "todo")
        edited = ".claude/skills/create-todo/SKILL.md"
        removed = ".codex/skills/create-todo/SKILL.md"
        as_installed = self.record()["files"][edited]
        (self.target / edited).write_text("adapted\n", encoding="utf-8")
        (self.target / removed).unlink()

        before_dry = (self.target / forge.RECORD).read_bytes()
        dry = forge.apply_kit(self.target, "todo", dry_run=True)
        self.assertEqual(dry["installed"], [removed])
        self.assertFalse((self.target / removed).exists())
        self.assertEqual((self.target / forge.RECORD).read_bytes(), before_dry)

        forge.apply_kit(self.target, "todo")
        forge.apply_kit(self.target, "reviewer")
        files = self.record()["files"]
        self.assertEqual(files[edited], as_installed)
        self.assertEqual(files[edited]["sha256"], self.template_digest("todo", edited))
        self.assertNotEqual(files[edited]["sha256"], forge.file_digest(b"adapted\n"))
        self.assertEqual(files[removed], {"kit": "todo", "sha256": self.template_digest("todo", removed)})
        self.assertEqual(files["scripts/review-dispatch.py"]["kit"], "reviewer")
        self.assertNotIn("scripts/todo-graph.py", files)
        self.assertEqual(own.read_text(encoding="utf-8"), "the project's own graph\n")
        self.assertEqual(sorted(self.record()["kits"]), ["reviewer", "todo"])

    def test_a_dry_run_writes_no_record(self):
        forge.apply_kit(self.target, "todo", dry_run=True)
        self.assertEqual(self.files_under(self.target), [])

    def test_generated_files_are_not_recorded(self):
        (self.target / "artisan").write_text("<?php\n", encoding="utf-8")
        forge.apply_kit(self.target, "laravel")
        files = self.record()["files"]
        self.assertTrue((self.target / ".mcp.json").is_file())
        self.assertNotIn(".mcp.json", files)
        self.assertEqual(files["boost.json"]["kit"], "laravel")

    def kit_path(self, path):
        """The project file a write is for: a staged `<name>.forge-new` file counts as its destination."""
        path = pathlib.Path(path)
        name = path.name
        for suffix in (forge.STAGED, forge.STAGED_REPLACE):
            name = name[:-len(suffix)] if name.endswith(suffix) else name
        return path.with_name(name).resolve().relative_to(self.target.resolve()).as_posix()

    def staged_files(self):
        return [rel for rel in self.files_under(self.target) if rel.endswith((forge.STAGED, forge.STAGED_REPLACE))]

    def test_a_copy_that_fails_part_way_leaves_a_true_record(self):
        real = forge.atomic_write
        calls = []

        def failing(path, data):
            rel = self.kit_path(path)
            if rel != forge.RECORD:
                calls.append(rel)
                if len(calls) == 3:
                    raise OSError("disk full")
            real(path, data)

        with unittest.mock.patch.object(forge, "atomic_write", failing):
            with self.assertRaisesRegex(OSError, "disk full"):
                forge.apply_kit(self.target, "todo")
        first, second, third = calls[:3]
        self.assertEqual(sorted(self.record()["files"]), sorted([first, second]))
        self.assertEqual(sorted(set(self.files_under(self.target)) - {forge.RECORD}), sorted([first, second]))
        self.assertFalse((self.target / third).exists())
        # A later run finishes the install and records the rest.
        forge.apply_kit(self.target, "todo")
        self.assertIn(third, self.record()["files"])

    def test_a_disk_that_fills_leaves_no_file_without_its_record_and_heals_on_the_next_run(self):
        # The third file fails, and so does every write after it, the record included.
        real = forge.atomic_write
        state = {"files": 0, "full": False}

        def filling(path, data):
            if self.kit_path(path) != forge.RECORD:
                state["files"] += 1
                state["full"] = state["full"] or state["files"] == 3
            if state["full"]:
                raise OSError("disk full")
            real(path, data)

        with unittest.mock.patch.object(forge, "atomic_write", filling):
            with self.assertRaisesRegex(OSError, "disk full"):
                forge.apply_kit(self.target, "todo")
        on_disk = sorted(set(self.files_under(self.target)) - {forge.RECORD})
        self.assertEqual(len(on_disk), 2)
        self.assertEqual(sorted(self.record()["files"]), on_disk)
        # With space again, the same command writes what is missing and the record is exact.
        forge.apply_kit(self.target, "todo")
        entries, _extra = forge.kit_plan(self.target.resolve(), "todo")
        planned = sorted(rel for _src, _dst, rel, _generated in entries)
        self.assertEqual(sorted(self.record()["files"]), planned)
        self.assertEqual(sorted(set(self.files_under(self.target)) - {forge.RECORD}), planned)
        for rel in planned:
            self.assertEqual(self.record()["files"][rel]["sha256"], self.template_digest("todo", rel), rel)

    def test_a_record_write_that_fails_leaves_the_file_unwritten(self):
        # The file's bytes are staged, then the record cannot be written: the file must not appear without its entry.
        real = forge.atomic_write
        seen = []

        def failing(path, data):
            rel = self.kit_path(path)
            if rel == forge.RECORD and len(seen) == 2:
                raise OSError("disk full")
            if rel != forge.RECORD:
                seen.append(rel)
            real(path, data)

        with unittest.mock.patch.object(forge, "atomic_write", failing):
            with self.assertRaisesRegex(OSError, "disk full"):
                forge.apply_kit(self.target, "todo")
        first, second = seen
        self.assertEqual(sorted(self.record()["files"]), [first])
        self.assertEqual(sorted(set(self.files_under(self.target)) - {forge.RECORD}), [first])
        self.assertEqual(self.staged_files(), [])

    def test_a_restored_file_that_fails_keeps_the_digest_it_was_installed_with(self):
        # Installed from an earlier kit version (another digest), deleted by the project, and the reinstall fails:
        # the record must still say what was installed then, not what this run meant to write.
        forge.apply_kit(self.target, "todo")
        rel = ".claude/skills/create-todo/SKILL.md"
        record = self.record()
        record["files"][rel]["sha256"] = "c" * 64
        forge.write_record(self.target, record)
        (self.target / rel).unlink()
        real = forge.atomic_write

        def failing(path, data):
            if self.kit_path(path) == rel:
                raise OSError("read-only")
            real(path, data)

        with unittest.mock.patch.object(forge, "atomic_write", failing):
            with self.assertRaisesRegex(OSError, "read-only"):
                forge.apply_kit(self.target, "todo")
        self.assertEqual(self.record()["files"][rel]["sha256"], "c" * 64)
        self.assertFalse((self.target / rel).exists())

    def earlier_agents_md(self):
        """A project whose AGENTS.md was installed from an earlier kit version and is still that version on disk."""
        forge.provision(self.target)
        record = self.record()
        record["files"]["AGENTS.md"]["sha256"] = "c" * 64
        forge.write_record(self.target, record)
        (self.target / "AGENTS.md").write_text("the earlier template\n", encoding="utf-8")

    def assert_agents_md_is_the_kits(self):
        template = FORGE_ROOT / "kits/base/templates/AGENTS.md"
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), template.read_bytes())
        self.assertEqual(self.record()["files"]["AGENTS.md"]["sha256"], self.template_digest("base", "AGENTS.md"))
        self.assertEqual(self.staged_files(), [])

    def test_a_forced_replacement_on_a_full_disk_keeps_the_doc_and_its_baseline(self):
        # --force with the disk full from the record write on: the new bytes were staged, the record could not be
        # written, so the doc must still be the earlier one under the digest it was installed with.
        self.earlier_agents_md()
        real = forge.atomic_write
        state = {"record_writes_refused": 0}

        def filling(path, data):
            if self.kit_path(path) == forge.RECORD:
                state["record_writes_refused"] += 1
                raise OSError("disk full")
            real(path, data)

        with unittest.mock.patch.object(forge, "atomic_write", filling):
            with self.assertRaisesRegex(OSError, "disk full"):
                forge.provision(self.target, overwrite_existing_docs=True)
        self.assertEqual(state["record_writes_refused"], 1)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "the earlier template\n")
        self.assertEqual(self.record()["files"]["AGENTS.md"]["sha256"], "c" * 64)
        self.assertEqual(self.staged_files(), [])
        # An ordinary init afterwards is not destructive: the doc and its baseline stay as they were.
        before = (self.target / forge.RECORD).read_bytes()
        forge.provision(self.target)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "the earlier template\n")
        self.assertEqual((self.target / forge.RECORD).read_bytes(), before)
        # With space again, --force replaces the doc and the record follows it.
        forge.provision(self.target, overwrite_existing_docs=True)
        self.assert_agents_md_is_the_kits()

    def test_a_forced_replacement_that_cannot_stage_keeps_the_doc_and_its_baseline(self):
        self.earlier_agents_md()
        real = forge.atomic_write

        def failing(path, data):
            if self.kit_path(path) == "AGENTS.md":
                raise OSError("read-only")
            real(path, data)

        with unittest.mock.patch.object(forge, "atomic_write", failing):
            with self.assertRaisesRegex(OSError, "read-only"):
                forge.provision(self.target, overwrite_existing_docs=True)
        self.assertEqual(self.record()["files"]["AGENTS.md"]["sha256"], "c" * 64)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "the earlier template\n")
        self.assertEqual(self.staged_files(), [])

    def test_a_replacement_recorded_but_not_renamed_is_finished_by_the_next_run(self):
        # The record was written with the new digest and the rename then failed (the doc was held open): the staged
        # bytes are what the record names, so any later run moves them into place.
        self.earlier_agents_md()
        real = os.replace

        def held_open(source, destination):
            if pathlib.Path(destination).name == "AGENTS.md":
                raise PermissionError("the file is in use")
            real(source, destination)

        with unittest.mock.patch.object(forge.os, "replace", held_open):
            with self.assertRaisesRegex(PermissionError, "in use"):
                forge.provision(self.target, overwrite_existing_docs=True)
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "the earlier template\n")
        self.assertEqual(self.record()["files"]["AGENTS.md"]["sha256"], self.template_digest("base", "AGENTS.md"))
        self.assertEqual(self.staged_files(), ["AGENTS.md" + forge.STAGED_REPLACE])
        self.assertTrue((self.target / forge.PENDING).is_file())
        # An ordinary init, with no --force, finishes it: nothing moved since.
        forge.provision(self.target)
        self.assert_agents_md_is_the_kits()
        self.assertFalse((self.target / forge.PENDING).exists())

    def held_open(self, name):
        """os.replace that fails for a destination called `name`, as when another program holds the file open."""
        real = os.replace

        def replace(source, destination):
            if pathlib.Path(destination).name == name:
                raise PermissionError("the file is in use")
            real(source, destination)

        return unittest.mock.patch.object(forge.os, "replace", replace)

    def test_a_replacement_the_project_edited_since_is_rolled_back_not_applied(self):
        # The rename failed, and before any retry the project saved its own edits to the doc. A later run, of any
        # kit, must keep those edits and put the record entry back to what the doc was installed with.
        self.earlier_agents_md()
        with self.held_open("AGENTS.md"):
            with self.assertRaises(PermissionError):
                forge.provision(self.target, overwrite_existing_docs=True)
        (self.target / "AGENTS.md").write_text("the project's edits, saved since\n", encoding="utf-8")
        forge.apply_kit(self.target, "reviewer")
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "the project's edits, saved since\n")
        self.assertEqual(self.record()["files"]["AGENTS.md"], {"kit": "base", "sha256": "c" * 64})
        self.assertEqual(self.staged_files(), [])
        self.assertFalse((self.target / forge.PENDING).exists())
        self.assertIn("scripts/review-dispatch.py", self.record()["files"])

    def test_a_replacement_of_a_doc_that_was_never_recorded_rolls_back_to_no_entry(self):
        own = self.target / "CLAUDE.md"
        own.write_text("the project's own entry doc\n", encoding="utf-8")
        forge.provision(self.target)
        self.assertNotIn("CLAUDE.md", self.record()["files"])
        with self.held_open("CLAUDE.md"):
            with self.assertRaises(PermissionError):
                forge.provision(self.target, overwrite_existing_docs=True)
        own.write_text("edited again by the project\n", encoding="utf-8")
        forge.provision(self.target)
        self.assertEqual(own.read_text(encoding="utf-8"), "edited again by the project\n")
        self.assertNotIn("CLAUDE.md", self.record()["files"])
        self.assertEqual(self.staged_files(), [])
        self.assertFalse((self.target / forge.PENDING).exists())

    def test_a_journal_left_after_the_rename_happened_is_only_removed(self):
        self.earlier_agents_md()
        real_remove = forge._remove

        def cannot_remove_the_journal(path):
            if pathlib.Path(path).name == pathlib.Path(forge.PENDING).name:
                raise OSError("read-only")
            real_remove(path)

        with unittest.mock.patch.object(forge, "_remove", cannot_remove_the_journal):
            with self.assertRaisesRegex(OSError, "read-only"):
                forge.provision(self.target, overwrite_existing_docs=True)
        self.assertTrue((self.target / forge.PENDING).is_file())
        forge.provision(self.target)
        self.assert_agents_md_is_the_kits()
        self.assertFalse((self.target / forge.PENDING).exists())

    def journal_that_cannot_be_removed(self, doc="AGENTS.md"):
        """Removing the journal fails while it is the journal of `doc`; every other removal works."""
        real_remove = forge._remove

        def remove(path):
            path = pathlib.Path(path)
            if path.name == pathlib.Path(forge.PENDING).name and path.is_file():
                if json.loads(path.read_text(encoding="utf-8"))["path"] == doc:
                    raise OSError("read-only")
            real_remove(path)

        return unittest.mock.patch.object(forge, "_remove", remove)

    def test_an_installed_replacement_keeps_its_new_baseline_when_the_project_edits_it_before_cleanup(self):
        # The doc was replaced, the journal could not be removed, and the project then edited the doc. The doc was
        # installed, so its entry is the kit's digest: the edit must read as the project's change to those bytes.
        self.earlier_agents_md()
        with self.journal_that_cannot_be_removed():
            with self.assertRaisesRegex(OSError, "read-only"):
                forge.provision(self.target, overwrite_existing_docs=True)
        self.assertTrue((self.target / forge.PENDING).is_file())
        self.assertEqual(self.staged_files(), [])
        (self.target / "AGENTS.md").write_text("edited after the install\n", encoding="utf-8")
        forge.apply_kit(self.target, "reviewer")
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "edited after the install\n")
        self.assertEqual(self.record()["files"]["AGENTS.md"],
                         {"kit": "base", "sha256": self.template_digest("base", "AGENTS.md")})
        self.assertFalse((self.target / forge.PENDING).exists())

    def test_a_doc_never_recorded_keeps_its_entry_when_edited_before_cleanup(self):
        own = self.target / "CLAUDE.md"
        own.write_text("the project's own entry doc\n", encoding="utf-8")
        forge.provision(self.target)
        with self.journal_that_cannot_be_removed("CLAUDE.md"):
            with self.assertRaisesRegex(OSError, "read-only"):
                forge.provision(self.target, overwrite_existing_docs=True)
        own.write_text("edited after the install\n", encoding="utf-8")
        forge.provision(self.target)
        self.assertEqual(own.read_text(encoding="utf-8"), "edited after the install\n")
        self.assertEqual(self.record()["files"]["CLAUDE.md"],
                         {"kit": "base", "sha256": self.template_digest("base", "CLAUDE.md")})
        self.assertFalse((self.target / forge.PENDING).exists())

    def test_a_failed_record_write_whose_journal_cannot_be_removed_is_settled_by_the_next_run(self):
        # The record write fails and so does removing the journal: the journal and its staged file stay together,
        # never the journal alone, and the next run settles the pair by what the destination holds.
        for label, edit in (("unchanged", None), ("edited", "the project's edits, saved since\n")):
            with self.subTest(case=label):
                project = pathlib.Path(self.tmp.name) / label
                project.mkdir()
                forge.provision(project)
                record = self.record(project)
                record["files"]["AGENTS.md"]["sha256"] = "c" * 64
                forge.write_record(project, record)
                (project / "AGENTS.md").write_text("the earlier template\n", encoding="utf-8")
                real = forge.atomic_write

                def failing(path, data, project=project, real=real):
                    if pathlib.Path(path).resolve() == (project / forge.RECORD).resolve():
                        raise OSError("disk full")
                    real(path, data)

                with unittest.mock.patch.object(forge, "atomic_write", failing), self.journal_that_cannot_be_removed():
                    with self.assertRaises(OSError):
                        forge.provision(project, overwrite_existing_docs=True)
                self.assertTrue((project / forge.PENDING).is_file())
                self.assertTrue((project / ("AGENTS.md" + forge.STAGED_REPLACE)).is_file())
                self.assertEqual(self.record(project)["files"]["AGENTS.md"]["sha256"], "c" * 64)
                if edit:
                    (project / "AGENTS.md").write_bytes(edit.encode("utf-8"))
                forge.provision(project)
                doc = (project / "AGENTS.md").read_bytes()
                entry = self.record(project)["files"]["AGENTS.md"]["sha256"]
                if edit:
                    self.assertEqual(doc, edit.encode("utf-8"))
                    self.assertEqual(entry, "c" * 64)
                else:
                    self.assertEqual(doc, (FORGE_ROOT / "kits/base/templates/AGENTS.md").read_bytes())
                    self.assertEqual(entry, self.template_digest("base", "AGENTS.md"))
                self.assertFalse((project / forge.PENDING).exists())
                self.assertFalse((project / ("AGENTS.md" + forge.STAGED_REPLACE)).exists())

    def test_a_replacements_staged_file_with_no_journal_is_removed_not_applied(self):
        forge.provision(self.target)
        template = (FORGE_ROOT / "kits/base/templates/AGENTS.md").read_bytes()
        (self.target / "AGENTS.md").write_text("the project's edits\n", encoding="utf-8")
        for doc in ("AGENTS.md", "CLAUDE.md"):
            (self.target / (doc + forge.STAGED_REPLACE)).write_bytes(template)
        forge.apply_kit(self.target, "reviewer")
        self.assertEqual(self.staged_files(), [])
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), "the project's edits\n")
        self.assertEqual(self.record()["files"]["AGENTS.md"]["sha256"], self.template_digest("base", "AGENTS.md"))

    def test_a_new_file_recorded_but_not_renamed_is_finished_or_given_up(self):
        rel = ".claude/skills/create-todo/SKILL.md"
        for label, project_made_its_own in (("finished", False), ("given-up", True)):
            with self.subTest(case=label):
                project = pathlib.Path(self.tmp.name) / label
                project.mkdir()
                with self.held_open("SKILL.md"):
                    with self.assertRaises(PermissionError):
                        forge.apply_kit(project, "todo", agent="claude")
                failed = sorted(self.record(project)["files"])[-1]
                self.assertFalse((project / failed).exists())
                self.assertTrue((project / (failed + forge.STAGED)).is_file())
                self.assertFalse((project / forge.PENDING).exists(), "a new file needs no journal")
                if project_made_its_own:
                    (project / failed).write_text("the project's own skill\n", encoding="utf-8")
                forge.apply_kit(project, "todo", agent="claude")
                self.assertEqual([r for r in self.files_under(project) if r.endswith(forge.STAGED)], [])
                if project_made_its_own:
                    self.assertEqual((project / failed).read_text(encoding="utf-8"), "the project's own skill\n")
                    self.assertNotIn(failed, self.record(project)["files"])
                else:
                    self.assertEqual(self.record(project)["files"][failed]["sha256"], self.template_digest("todo", failed))
                    self.assertEqual(forge.file_digest((project / failed).read_bytes()), self.template_digest("todo", failed))
                self.assertIn(rel, self.record(project)["files"])

    def test_a_journal_that_cannot_be_read_refuses_before_any_file_is_written(self):
        forge.provision(self.target)
        valid = {"schema_version": 1, "path": "AGENTS.md", "kit": "base", "new": "a" * 64, "earlier": None,
                 "destination": None}
        faults = {
            "not JSON": "{nope",
            "not an object": "[1]",
            "missing key": json.dumps({k: v for k, v in valid.items() if k != "kit"}),
            "unknown key": json.dumps({**valid, "extra": 1}),
            "bad digest": json.dumps({**valid, "new": "xyz"}),
            "bad earlier": json.dumps({**valid, "earlier": {"kit": "base"}}),
        }
        for name, text in faults.items():
            with self.subTest(fault=name):
                (self.target / forge.PENDING).write_text(text, encoding="utf-8")
                before = {rel: (self.target / rel).read_bytes() for rel in self.files_under(self.target)}
                with self.assertRaisesRegex(ValueError, r"\.conclave/kits\.pending\.json"):
                    forge.apply_kit(self.target, "todo")
                self.assertEqual({rel: (self.target / rel).read_bytes() for rel in self.files_under(self.target)}, before)
        (self.target / forge.PENDING).unlink()
        (self.target / forge.PENDING).mkdir()
        with self.assertRaisesRegex(ValueError, r"\.conclave/kits\.pending\.json"):
            forge.apply_kit(self.target, "todo")

    def test_a_staged_file_the_record_does_not_name_is_removed_not_applied(self):
        forge.provision(self.target)
        before = (self.target / "AGENTS.md").read_bytes()
        stale = self.target / ("AGENTS.md" + forge.STAGED)
        stale.write_text("left by a run that never recorded it\n", encoding="utf-8")
        forge.provision(self.target)
        self.assertFalse(stale.exists())
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), before)
        # A dry run changes nothing, a staged file included.
        stale.write_text("left again\n", encoding="utf-8")
        forge.apply_kit(self.target, "base", dry_run=True)
        self.assertTrue(stale.exists())

    def test_agents_accumulate_per_kit(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        self.assertEqual(self.record()["kits"]["todo"]["agents"], ["claude"])
        forge.apply_kit(self.target, "todo", agent="codex")
        self.assertEqual(self.record()["kits"]["todo"]["agents"], ["claude", "codex"])
        forge.apply_kit(self.target, "reviewer", agent="gemini")
        self.assertEqual(self.record()["kits"]["reviewer"]["agents"], ["agy"])
        self.assertEqual(self.record()["kits"]["todo"]["agents"], ["claude", "codex"])

        other = pathlib.Path(self.tmp.name) / "other"
        other.mkdir()
        forge.apply_kit(other, "todo")
        self.assertEqual(self.record(other)["kits"]["todo"]["agents"], ["agy", "claude", "codex"])
        (other / ".claude/skills/add-todo/SKILL.md").unlink()
        forge.apply_kit(other, "todo", agent="claude")
        self.assertEqual(self.record(other)["kits"]["todo"]["agents"], ["agy", "claude", "codex"])

    def test_the_wordpress_host_is_recorded(self):
        forge.apply_kit(self.target, "wordpress", host="wpcom")
        self.assertEqual(self.record()["kits"]["wordpress"]["host"], "wpcom")

    def test_entry_docs_are_recorded_as_the_kits_bytes(self):
        own = self.target / "CLAUDE.md"
        own.write_text("the project's own entry doc\n", encoding="utf-8")
        forge.provision(self.target, with_todo=True)
        files = self.record()["files"]
        agents_md = (self.target / "AGENTS.md").read_bytes()
        self.assertIn(b"TODO workflow", agents_md)
        self.assertEqual(files["AGENTS.md"], {"kit": "base", "sha256": self.template_digest("base", "AGENTS.md")})
        self.assertNotEqual(files["AGENTS.md"]["sha256"], forge.file_digest(agents_md))
        self.assertNotIn("CLAUDE.md", files)

        # A second init writes nothing, so nothing in the record moves.
        before = (self.target / forge.RECORD).read_bytes()
        forge.provision(self.target, with_todo=True)
        self.assertEqual((self.target / forge.RECORD).read_bytes(), before)

        # --force replaces the four docs: each now holds the kit's bytes and is recorded so, the one never recorded too.
        (self.target / "GEMINI.md").write_text("edited\n", encoding="utf-8")
        forge.provision(self.target, with_todo=True, overwrite_existing_docs=True)
        files = self.record()["files"]
        for doc in ("AGENTS.md", "GEMINI.md", "CLAUDE.md", "CODEX.md"):
            self.assertEqual(files[doc], {"kit": "base", "sha256": self.template_digest("base", doc)}, doc)
        self.assertEqual(own.read_bytes(), (FORGE_ROOT / "kits/base/templates/CLAUDE.md").read_bytes())


class KitFixture:
    """A scratch project and the six recorded states, shared by the diff and update tests."""

    target: pathlib.Path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = pathlib.Path(self.tmp.name) / "project"
        self.target.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def states(self, result, kit="todo"):
        return {item["path"]: item["state"] for item in result["kits"][kit]["files"]}

    def loaded(self):
        record = forge.load_record(self.target)
        assert record is not None
        return record

    def set_recorded(self, rel, data):
        record = self.loaded()
        record["files"][rel]["sha256"] = forge.file_digest(data)
        forge.write_record(self.target, record)

    SIX = {
        "identical": ".claude/skills/add-todo/SKILL.md",
        "missing": ".claude/skills/create-todo/SKILL.md",
        "project-removed": ".claude/skills/groom-plan/SKILL.md",
        "kit-newer": ".claude/skills/process-phase/SKILL.md",
        "project-changed": ".claude/skills/process-plan/SKILL.md",
        "both-changed": ".claude/skills/process-todo-file/SKILL.md",
    }

    def six_state_fixture(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        six = self.SIX
        (self.target / six["missing"]).unlink()
        record = self.loaded()
        del record["files"][six["missing"]]
        forge.write_record(self.target, record)
        (self.target / six["project-removed"]).unlink()
        (self.target / six["kit-newer"]).write_bytes(b"what the project was given by an older kit\n")
        self.set_recorded(six["kit-newer"], b"what the project was given by an older kit\n")
        (self.target / six["project-changed"]).write_bytes(b"the project's own edit\n")
        (self.target / six["both-changed"]).write_bytes(b"the project's own edit\n")
        self.set_recorded(six["both-changed"], b"what an older kit installed\n")

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): forge.file_digest(p.read_bytes())
                for p in sorted(root.rglob("*")) if p.is_file()}


class DiffTests(KitFixture, unittest.TestCase):
    """`forge.py diff`: each kit file's state from the project's bytes, the kit's and the record's, written nowhere."""

    def cli(self, *args):
        return subprocess.run([sys.executable, str(FORGE_ROOT / "forge.py"), "diff", *map(str, args)],
                              capture_output=True, text=True)

    def test_every_recorded_state_is_told_apart(self):
        self.six_state_fixture()
        result = forge.diff_project(self.target)
        self.assertTrue(result["record"])
        self.assertTrue(result["kits"]["todo"]["record"])
        states = self.states(result)
        for state, rel in self.SIX.items():
            self.assertEqual(states[rel], state, rel)
        self.assertTrue(set(states.values()) <= set(forge.DIFF_STATES))

    def test_without_a_record_only_missing_identical_and_differs_are_known(self):
        self.six_state_fixture()
        (self.target / forge.RECORD).unlink()
        result = forge.diff_project(self.target)
        self.assertFalse(result["record"])
        self.assertFalse(result["kits"]["todo"]["record"])
        states = self.states(result)
        self.assertEqual(set(states.values()), {"missing", "identical", "differs"})
        self.assertEqual(states[self.SIX["kit-newer"]], "differs")
        self.assertEqual(states[self.SIX["project-removed"]], "missing")

    def test_a_kit_installed_before_the_record_is_still_reported(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        forge.apply_kit(self.target, "reviewer", agent="claude")
        record = self.loaded()
        del record["kits"]["todo"]
        record["files"] = {rel: e for rel, e in record["files"].items() if e["kit"] != "todo"}
        forge.write_record(self.target, record)
        result = forge.diff_project(self.target)
        self.assertEqual(list(result["kits"]), ["todo", "reviewer"])
        self.assertFalse(result["kits"]["todo"]["record"])
        self.assertTrue(result["kits"]["reviewer"]["record"])
        self.assertEqual(set(self.states(result).values()), {"identical"})

    def test_a_file_the_project_had_before_the_install_has_no_recorded_state(self):
        own = self.target / ".claude/skills/add-todo/SKILL.md"
        own.parent.mkdir(parents=True)
        own.write_bytes(b"the project's own skill\n")
        forge.apply_kit(self.target, "todo", agent="claude")
        self.assertEqual(self.states(forge.diff_project(self.target))[".claude/skills/add-todo/SKILL.md"], "differs")

    def test_a_path_the_kit_no_longer_ships_is_project_only(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits/todo", sdk / "kits/todo")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            forge.apply_kit(self.target, "todo", agent="claude")
            (sdk / "kits/todo/templates/.claude/skills/groom-plan/SKILL.md").unlink()
            states = self.states(forge.diff_project(self.target))
        self.assertEqual(states[".claude/skills/groom-plan/SKILL.md"], "project-only")

    def test_only_the_agents_the_project_has_are_compared(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        for drop_record in (False, True):
            if drop_record:
                (self.target / forge.RECORD).unlink()
            result = forge.diff_project(self.target)
            self.assertEqual(result["kits"]["todo"]["agents"], ["claude"])
            paths = list(self.states(result))
            self.assertTrue(paths)
            self.assertFalse([p for p in paths if p.startswith((".agents/", ".codex/", "GEMINI", "CODEX"))], paths)
        empty = pathlib.Path(self.tmp.name) / "bare"
        (empty / "scripts").mkdir(parents=True)
        (empty / "scripts/todo-graph.py").write_bytes(b"# the project's own\n")
        self.assertEqual(forge.diff_project(empty)["kits"]["todo"]["agents"], ["agy", "claude", "codex"])

    def test_a_kit_the_project_does_not_have_or_no_kit_at_all(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        for kit in ("reviewer", "nope"):
            result = self.cli(self.target, kit)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(result.stderr.startswith("forge.py: error: "), result.stderr)
            self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(list(forge.diff_project(self.target, "todo")["kits"]), ["todo"])
        a_file = pathlib.Path(self.tmp.name) / "a-file"
        a_file.write_bytes(b"x")
        for target in (pathlib.Path(self.tmp.name) / "absent", a_file):
            result = self.cli(target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("existing non-symlink directory", result.stderr)
        empty = pathlib.Path(self.tmp.name) / "empty"
        empty.mkdir()
        result = self.cli(empty)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["kits"], {})

    def test_the_wordpress_host_comes_from_the_record(self):
        forge.apply_kit(self.target, "wordpress", host="wpcom")
        (self.target / forge.WORDPRESS_PIN).unlink()
        states = self.states(forge.diff_project(self.target), "wordpress")
        self.assertEqual(states[forge.WORDPRESS_PIN], "project-removed")
        self.assertNotIn("bin/ddev", states)
        shutil.copyfile(FORGE_ROOT / "kits/wordpress/hosts/pressable/templates" / forge.WORDPRESS_PIN,
                        self.target / forge.WORDPRESS_PIN)
        result = self.cli(self.target)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("'pressable'", result.stderr)
        self.assertIn("'wpcom'", result.stderr)

    def _link(self, target, link):
        make_link(target, link)

    def test_a_site_pin_behind_a_link_is_never_read(self):
        outside = pathlib.Path(self.tmp.name) / "outside"
        (outside / ".conclave").mkdir(parents=True)
        shutil.copyfile(FORGE_ROOT / "kits/wordpress/hosts/wpcom/templates" / forge.WORDPRESS_PIN,
                        outside / forge.WORDPRESS_PIN)
        if os.name == "nt":
            make_link(outside / ".conclave", self.target / ".conclave")  # a junction links folders only
        else:
            (self.target / ".conclave").mkdir()
            os.symlink(outside / forge.WORDPRESS_PIN, self.target / forge.WORDPRESS_PIN)
        with unittest.mock.patch.object(forge, "_load_wordpress_pin", side_effect=AssertionError("pin read")):
            with self.assertRaisesRegex(ValueError, "refusing to read a site pin from outside the project"):
                forge.kit_plan(self.target, "wordpress")
            with self.assertRaisesRegex(ValueError, "link"):
                forge.diff_project(self.target, "wordpress")

    def test_a_bad_pin_under_a_recorded_host_is_reported_not_fatal(self):
        forge.apply_kit(self.target, "wordpress", host="wpcom")
        pin = self.target / forge.WORDPRESS_PIN
        clean = self.states(forge.diff_project(self.target), "wordpress")

        pin.write_bytes(b"{ not json\n")
        states = self.states(forge.diff_project(self.target), "wordpress")
        self.assertEqual(states.pop(forge.WORDPRESS_PIN), "project-changed")
        self.assertEqual(states, {k: v for k, v in clean.items() if k != forge.WORDPRESS_PIN})

        pin.unlink()
        pin.mkdir()
        with unittest.mock.patch.object(forge, "_load_wordpress_pin", side_effect=AssertionError("pin read")):
            states = self.states(forge.diff_project(self.target), "wordpress")
        self.assertEqual(states.pop(forge.WORDPRESS_PIN), "unsafe")
        self.assertEqual(states, {k: v for k, v in clean.items() if k != forge.WORDPRESS_PIN})

        pin.rmdir()
        shutil.copyfile(FORGE_ROOT / "kits/wordpress/hosts/wpcom/templates" / forge.WORDPRESS_PIN, pin)
        real_read = pathlib.Path.read_bytes

        def deny(path):
            if pathlib.Path(path).resolve() == pin.resolve():
                raise PermissionError(13, "Permission denied", str(path))
            return real_read(path)

        with unittest.mock.patch.object(pathlib.Path, "read_bytes", deny), \
                unittest.mock.patch.object(forge, "_load_wordpress_pin", return_value=(None, "invalid: denied")):
            states = self.states(forge.diff_project(self.target), "wordpress")
        self.assertEqual(states.pop(forge.WORDPRESS_PIN), "unreadable")
        self.assertEqual(states, {k: v for k, v in clean.items() if k != forge.WORDPRESS_PIN})

    def test_a_patch_marks_a_last_line_with_no_newline(self):
        patch = forge._text_patch("SKILL.md", b"project edit", b"kit text\n")
        self.assertEqual(patch.splitlines()[2:], [
            "@@ -1 +1 @@", "-project edit", "\\ No newline at end of file", "+kit text"])
        self.assertTrue(patch.endswith("\n"))

    def test_an_unsafe_destination_is_never_read(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        outside = pathlib.Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_bytes(b"outside the project\n")
        skill = self.target / ".claude/skills/add-todo"
        shutil.rmtree(skill)
        self._link(outside, skill)
        (self.target / ".claude/skills/create-todo/SKILL.md").unlink()
        (self.target / ".claude/skills/create-todo/SKILL.md").mkdir()
        real_read = pathlib.Path.read_bytes

        def guarded(path):
            self.assertNotEqual(path.resolve().parent, outside.resolve(), f"read through a link: {path}")
            return real_read(path)

        with unittest.mock.patch.object(pathlib.Path, "read_bytes", guarded):
            states = self.states(forge.diff_project(self.target))
        self.assertEqual(states[".claude/skills/add-todo/SKILL.md"], "unsafe")
        self.assertEqual(states[".claude/skills/create-todo/SKILL.md"], "unsafe")

    def test_the_generated_mcp_json_is_reported_not_compared(self):
        (self.target / "artisan").write_text("<?php\n", encoding="utf-8")
        forge.apply_kit(self.target, "laravel", agent="claude")
        mcp = self.target / ".mcp.json"
        self.assertEqual(self.states(forge.diff_project(self.target), "laravel")[".mcp.json"], "generated")
        mcp.unlink()
        self.assertEqual(self.states(forge.diff_project(self.target), "laravel")[".mcp.json"], "missing")
        mcp.mkdir()
        self.assertEqual(self.states(forge.diff_project(self.target), "laravel")[".mcp.json"], "unsafe")
        mcp.rmdir()
        elsewhere = pathlib.Path(self.tmp.name) / "elsewhere"
        elsewhere.mkdir()
        self._link(elsewhere, mcp)
        self.assertEqual(self.states(forge.diff_project(self.target), "laravel")[".mcp.json"], "unsafe")
        elsewhere.rmdir()
        self.assertEqual(self.states(forge.diff_project(self.target), "laravel")[".mcp.json"], "unsafe")

    def test_an_unreadable_file_is_reported_and_the_rest_still_classified(self):
        self.six_state_fixture()
        blocked = (self.target / self.SIX["project-changed"]).resolve()
        real_read = pathlib.Path.read_bytes

        def deny(path):
            if pathlib.Path(path).resolve() == blocked:
                raise PermissionError(13, "Permission denied", str(path))
            return real_read(path)

        clean = self.states(forge.diff_project(self.target))
        before = self.snapshot(self.target)
        out, err = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(pathlib.Path, "read_bytes", deny), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main(["diff", str(self.target)])
        self.assertEqual(code, 0, err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        items = {item["path"]: item for item in json.loads(out.getvalue())["kits"]["todo"]["files"]}
        self.assertEqual(items[self.SIX["project-changed"]]["state"], "unreadable")
        self.assertIn("Permission denied", items[self.SIX["project-changed"]]["reason"])
        rest = {rel: item["state"] for rel, item in items.items() if rel != self.SIX["project-changed"]}
        self.assertEqual(rest, {rel: s for rel, s in clean.items() if rel != self.SIX["project-changed"]})
        self.assertEqual(self.snapshot(self.target), before)

    def test_patch_shows_the_project_side_then_the_kits(self):
        self.six_state_fixture()
        own = self.target / ".claude/skills/review-todo-section/SKILL.md"
        own.write_bytes(own.read_bytes() + b"\x00binary tail\n")
        (self.target / forge.RECORD).unlink()  # leaves every differing file as `differs`
        forge.apply_kit(self.target, "todo", agent="claude")  # restores the record for the deleted files only
        result = self.cli(self.target, "--patch")
        self.assertEqual(result.returncode, 0, result.stderr)
        items = {item["path"]: item for item in json.loads(result.stdout)["kits"]["todo"]["files"]}
        self.assertEqual(items[own.relative_to(self.target).as_posix()]["patch"], "binary")
        rel = self.SIX["project-changed"]
        patch = items[rel]["patch"]
        self.assertEqual(items[rel]["state"], "differs")
        self.assertIn(f"--- project/{rel}\n+++ kit/{rel}\n", patch)
        self.assertIn("\n-the project's own edit\n", patch)
        kit_first = (FORGE_ROOT / "kits/todo/templates" / rel).read_text(encoding="utf-8").splitlines()[0]
        self.assertIn(f"\n+{kit_first}\n", patch)

        # With the record back, the recorded states carry the same patch.
        self.six_state_fixture_again()
        items = {i["path"]: i for i in forge.diff_project(self.target, patch=True)["kits"]["todo"]["files"]}
        for state in ("project-changed", "both-changed"):
            rel = self.SIX[state]
            self.assertEqual(items[rel]["state"], state)
            self.assertIn(f"--- project/{rel}\n+++ kit/{rel}\n", items[rel]["patch"])
            self.assertIn("\n-the project's own edit\n", items[rel]["patch"])
        self.assertNotIn("patch", items[self.SIX["identical"]])
        self.assertNotIn("patch", items[self.SIX["kit-newer"]])

    def six_state_fixture_again(self):
        shutil.rmtree(self.target)
        self.target.mkdir()
        self.six_state_fixture()

    def test_diff_writes_nothing(self):
        self.six_state_fixture()
        # An interrupted run's staged file stays for the next install to settle: diff must not settle it.
        # The record names this file and it is gone, so the next install would move the staged copy into place.
        staged = self.target / (self.SIX["project-removed"] + forge.STAGED)
        staged.write_bytes((FORGE_ROOT / "kits/todo/templates" / self.SIX["project-removed"]).read_bytes())
        before = self.snapshot(self.target)
        dirs = sorted(p for p in self.target.rglob("*") if p.is_dir())
        self.assertEqual(self.cli(self.target, "--patch").returncode, 0)
        forge.diff_project(self.target, patch=True)
        self.assertEqual(self.snapshot(self.target), before)
        self.assertEqual(sorted(p for p in self.target.rglob("*") if p.is_dir()), dirs)

    def test_the_readme_names_every_state(self):
        readme = (FORGE_ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("### `diff`", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
        for state in forge.DIFF_STATES:
            self.assertIn(f"| `{state}` |", section, state)


class UpdateTests(KitFixture, unittest.TestCase):
    """`forge.py update`: only `missing` and `kit-newer` files are written; every other file stays the project's."""


    def kit_bytes(self, rel, kit="todo"):
        return (FORGE_ROOT / "kits" / kit / "templates" / rel).read_bytes()

    def cli(self, *args):
        result = subprocess.run([sys.executable, str(FORGE_ROOT / "forge.py"), "update", *map(str, args)],
                                capture_output=True, text=True)
        return result

    def test_only_missing_and_kit_newer_files_are_written(self):
        self.six_state_fixture()
        before = self.snapshot(self.target)
        result = forge.update_project(self.target)
        self.assertEqual(sorted(result["written"]), sorted([self.SIX["missing"], self.SIX["kit-newer"]]))
        for state in ("missing", "kit-newer"):
            self.assertEqual((self.target / self.SIX[state]).read_bytes(), self.kit_bytes(self.SIX[state]))
        after = self.snapshot(self.target)
        for state in ("project-changed", "both-changed", "identical"):
            self.assertEqual(after[self.SIX[state]], before[self.SIX[state]], state)
        self.assertNotIn(self.SIX["project-removed"], after)
        left = {item["path"]: item for item in result["left"]}
        self.assertEqual({rel: item["state"] for rel, item in left.items()},
                         {self.SIX[s]: s for s in ("project-changed", "both-changed", "project-removed")})
        self.assertIn("\n-the project's own edit\n", left[self.SIX["project-changed"]]["patch"])

    def test_a_path_the_kit_no_longer_ships_is_left(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits/todo", sdk / "kits/todo")
        rel = ".claude/skills/groom-plan/SKILL.md"
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            forge.apply_kit(self.target, "todo", agent="claude")
            (sdk / "kits/todo/templates" / rel).unlink()
            before = (self.target / rel).read_bytes()
            result = forge.update_project(self.target)
        self.assertEqual(result["left"], [{"path": rel, "state": "project-only"}])
        self.assertEqual((self.target / rel).read_bytes(), before)
        # A selection holding only retired files names nothing a kit ships, and refuses before any write.
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            snapshot = self.snapshot(self.target)
            for only in (rel, ".claude/skills/groom-plan"):
                with self.assertRaisesRegex(ValueError, "no file a kit ships"):
                    forge.update_project(self.target, only=[only])
                self.assertEqual(self.snapshot(self.target), snapshot, only)

    def test_only_narrows_to_a_file_or_a_folder(self):
        self.six_state_fixture()
        result = forge.update_project(self.target, only=[self.SIX["missing"]])
        self.assertEqual(result["written"], [self.SIX["missing"]])
        self.assertNotEqual((self.target / self.SIX["kit-newer"]).read_bytes(), self.kit_bytes(self.SIX["kit-newer"]))
        folder = str(pathlib.PurePosixPath(self.SIX["kit-newer"]).parent).replace("/", "\\")  # a Windows spelling
        self.assertEqual(forge.update_project(self.target, only=[folder])["written"], [self.SIX["kit-newer"]])
        # A removed file comes back only when named.
        self.assertFalse((self.target / self.SIX["project-removed"]).exists())
        self.assertEqual(forge.update_project(self.target)["written"], [])
        restored = forge.update_project(self.target, only=[self.SIX["project-removed"]])
        self.assertEqual(restored["written"], [self.SIX["project-removed"]])
        self.assertEqual((self.target / self.SIX["project-removed"]).read_bytes(),
                         self.kit_bytes(self.SIX["project-removed"]))
        self.assertEqual(self.loaded()["files"][self.SIX["project-removed"]]["sha256"],
                         forge.file_digest(self.kit_bytes(self.SIX["project-removed"])))
        for bad in ("../outside", str(pathlib.Path(self.tmp.name) / "x"), "/etc/passwd", "C:/x", "", "docs/nothing-here"):
            before = self.snapshot(self.target)
            with self.assertRaises(ValueError, msg=bad):
                forge.update_project(self.target, only=[bad])
            self.assertEqual(self.snapshot(self.target), before, bad)

    def test_each_failure_point_leaves_a_state_the_next_run_settles(self):
        three = [self.SIX["missing"], self.SIX["kit-newer"], ".claude/skills/review-todo-section/SKILL.md"]
        for point in ("stage", "record", "rename"):
            with self.subTest(point=point):
                shutil.rmtree(self.target)
                self.target.mkdir()
                self.six_state_fixture()
                third = self.target / three[2]
                third.write_bytes(b"older\n")
                self.set_recorded(three[2], b"older\n")
                second = self.target / three[1]
                second_before = second.read_bytes()
                second_entry = self.loaded()["files"][three[1]]
                real_write, real_replace = forge.atomic_write, os.replace
                record_writes = []

                def failing_write(path, data, real=real_write):
                    path = pathlib.Path(path)
                    if point == "stage" and path.parent == second.parent and path.name.startswith(second.name + "."):
                        raise OSError(28, "No space left on device")
                    if path.name == "kits.json":
                        record_writes.append(path)
                        if point == "record" and len(record_writes) == 2:  # the second file's record write
                            raise OSError(28, "No space left on device")
                    return real(path, data)

                def failing_replace(src, dst, real=real_replace):
                    if point == "rename" and pathlib.Path(dst) == second:
                        raise OSError(13, "Permission denied")
                    return real(src, dst)

                with unittest.mock.patch.object(forge, "atomic_write", failing_write), \
                        unittest.mock.patch.object(forge.os, "replace", failing_replace):
                    with self.assertRaises(OSError):
                        forge.update_project(self.target, only=three)
                files = self.loaded()["files"]
                self.assertEqual((self.target / three[0]).read_bytes(), self.kit_bytes(three[0]), point)
                self.assertEqual(files[three[0]]["sha256"], forge.file_digest(self.kit_bytes(three[0])), point)
                self.assertEqual(second.read_bytes(), second_before, point)
                self.assertEqual(third.read_bytes(), b"older\n", point)
                if point == "rename":
                    self.assertEqual(files[three[1]]["sha256"], forge.file_digest(self.kit_bytes(three[1])))
                    self.assertTrue((self.target / forge.PENDING).is_file())
                else:
                    self.assertEqual(files[three[1]], second_entry, point)
                # The next run settles what was left and finishes the work.
                forge.update_project(self.target, only=three)
                for rel in three:
                    self.assertEqual((self.target / rel).read_bytes(), self.kit_bytes(rel), (point, rel))
                self.assertFalse((self.target / forge.PENDING).exists())
                self.assertEqual([p for p in self.snapshot(self.target) if p.endswith((forge.STAGED, forge.STAGED_REPLACE))], [])

    def test_an_interrupt_after_the_record_is_written_is_finished_by_the_next_run(self):
        for state in ("kit-newer", "missing"):
            with self.subTest(state=state):
                shutil.rmtree(self.target)
                self.target.mkdir()
                self.six_state_fixture()
                rel = self.SIX[state]
                real = forge.write_record

                def write_then_interrupt(target_root, record):
                    real(target_root, record)
                    raise KeyboardInterrupt

                with unittest.mock.patch.object(forge, "write_record", write_then_interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        forge.update_project(self.target, only=[rel])
                self.assertEqual(self.loaded()["files"][rel]["sha256"], forge.file_digest(self.kit_bytes(rel)))
                result = forge.update_project(self.target)
                self.assertEqual((self.target / rel).read_bytes(), self.kit_bytes(rel), state)
                self.assertEqual(self.states(forge.diff_project(self.target))[rel], "identical", state)
                self.assertNotIn(rel, [i["path"] for i in result["left"]])
                self.assertFalse((self.target / forge.PENDING).exists())
                self.assertEqual([p for p in self.snapshot(self.target)
                                  if p.endswith((forge.STAGED, forge.STAGED_REPLACE))], [])

    def test_an_edit_made_after_a_failed_rename_is_kept(self):
        self.six_state_fixture()
        second = self.target / self.SIX["kit-newer"]
        real_replace = os.replace

        def failing_replace(src, dst):
            if pathlib.Path(dst) == second:
                raise OSError(13, "Permission denied")
            return real_replace(src, dst)

        with unittest.mock.patch.object(forge.os, "replace", failing_replace):
            with self.assertRaises(OSError):
                forge.update_project(self.target, only=[self.SIX["kit-newer"]])
        second.write_bytes(b"edited in between\n")
        forge.update_project(self.target)
        self.assertEqual(second.read_bytes(), b"edited in between\n")
        # Rolled back to the entry it had (an older kit's bytes), so both sides now differ from it.
        self.assertEqual(self.states(forge.diff_project(self.target))[self.SIX["kit-newer"]], "both-changed")

    def interrupted(self):
        """A six-state project an earlier run left part way: a staged new file for a recorded, deleted file."""
        self.six_state_fixture()
        staged = self.target / (self.SIX["project-removed"] + forge.STAGED)
        staged.write_bytes(self.kit_bytes(self.SIX["project-removed"]))
        return staged

    def test_every_refusal_comes_before_any_write(self):
        staged = self.interrupted()
        skill = self.target / ".claude/skills/add-todo"
        outside = pathlib.Path(self.tmp.name) / "outside"
        outside.mkdir()
        shutil.rmtree(skill)
        make_link(outside, skill)
        before = self.snapshot(self.target)
        for only in (["docs/nothing-here"], [".claude/skills/add-todo"], []):
            result = self.cli(self.target, *[a for o in only for a in ("--only", o)])
            self.assertEqual(result.returncode, 2, (only, result.stderr))
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(self.snapshot(self.target), before, only)
        self.assertTrue(staged.is_file())
        # Outside the linked folder the update runs, and settles the interrupted file first.
        result = forge.update_project(self.target, only=[".claude/skills/process-phase", ".claude/skills/groom-plan"])
        self.assertFalse(staged.exists())
        self.assertEqual((self.target / self.SIX["project-removed"]).read_bytes(),
                         self.kit_bytes(self.SIX["project-removed"]))
        self.assertEqual(result["written"], [self.SIX["kit-newer"]])

    def test_a_file_edited_between_the_diff_and_its_write_is_kept(self):
        self.six_state_fixture()
        rel = self.SIX["kit-newer"]
        real = forge._write_recorded

        def edit_first(target_root, record, kit_name, agent, host, copies, expect=None):
            (self.target / rel).write_bytes(b"edited during the update\n")
            return real(target_root, record, kit_name, agent, host, copies, expect)

        with unittest.mock.patch.object(forge, "_write_recorded", edit_first):
            result = forge.update_project(self.target)
        self.assertEqual((self.target / rel).read_bytes(), b"edited during the update\n")
        self.assertIn({"path": rel, "state": "changed-since-diff"}, result["left"])
        self.assertNotIn(rel, result["written"])
        self.assertIn(self.SIX["missing"], result["written"])

    def test_a_dry_run_writes_nothing_and_settles_nothing(self):
        for fixture in (self.six_state_fixture, self.interrupted):
            with self.subTest(fixture=fixture.__name__):
                shutil.rmtree(self.target)
                self.target.mkdir()
                fixture()
                before = self.snapshot(self.target)
                result = forge.update_project(self.target, dry_run=True)
                self.assertEqual(self.snapshot(self.target), before)
                self.assertEqual(sorted(result["written"]), sorted([self.SIX["missing"], self.SIX["kit-newer"]]))
                self.assertTrue(result["dry_run"])

    def test_agents_compared_without_a_record_are_all_recorded(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        forge.apply_kit(self.target, "todo", agent="codex")
        (self.target / forge.RECORD).unlink()
        (self.target / ".codex/skills/add-todo/SKILL.md").unlink()
        result = forge.update_project(self.target)
        self.assertEqual(result["written"], [".codex/skills/add-todo/SKILL.md"])
        self.assertEqual(self.loaded()["kits"]["todo"]["agents"], ["claude", "codex"])

    def test_no_scripts_leaves_scripts_out(self):
        forge.provision(self.target, with_todo=True, include_scripts=False)
        self.assertFalse((self.target / "scripts").exists())
        result = self.cli(self.target, "--no-scripts")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["written"], [])
        self.assertFalse((self.target / "scripts").exists())
        self.assertTrue([p for p in forge.update_project(self.target, dry_run=True)["written"] if p.startswith("scripts/")])

    def test_without_a_record_only_missing_files_are_written(self):
        self.six_state_fixture()
        (self.target / forge.RECORD).unlink()
        changed = (self.target / self.SIX["kit-newer"]).read_bytes()
        result = forge.update_project(self.target)
        self.assertEqual(sorted(result["written"]), sorted([self.SIX["missing"], self.SIX["project-removed"]]))
        self.assertEqual((self.target / self.SIX["kit-newer"]).read_bytes(), changed)
        self.assertIn({"path": self.SIX["kit-newer"], "state": "differs"},
                      [{k: i[k] for k in ("path", "state")} for i in result["left"]])
        self.assertIn("forge.py record", result["hint"])
        self.assertIn("--kit-new", result["hint"])

    def test_the_generated_mcp_json_is_never_copied(self):
        (self.target / "artisan").write_text("<?php\n", encoding="utf-8")
        forge.apply_kit(self.target, "laravel", agent="claude")
        mcp = self.target / ".mcp.json"
        mcp.write_text('{"mcpServers": {}}\n', encoding="utf-8")
        result = forge.update_project(self.target)
        self.assertEqual(mcp.read_text(encoding="utf-8"), '{"mcpServers": {}}\n')
        self.assertIn({"path": ".mcp.json", "state": "generated", "hint": forge.UPDATE_HINT_GENERATED}, result["left"])
        mcp.unlink()
        result = forge.update_project(self.target)
        self.assertFalse(mcp.exists())
        self.assertIn({"path": ".mcp.json", "state": "missing", "hint": forge.UPDATE_HINT_GENERATED}, result["left"])

    def test_the_command_line_updates_once_then_has_nothing_to_do(self):
        self.six_state_fixture()
        first = self.cli(self.target)
        self.assertEqual(first.returncode, 0, first.stderr)
        out = json.loads(first.stdout)
        self.assertEqual(sorted(out["written"]), sorted([self.SIX["missing"], self.SIX["kit-newer"]]))
        self.assertTrue(out["record"])
        files = self.loaded()["files"]
        for state in ("missing", "kit-newer"):
            self.assertEqual(files[self.SIX[state]]["sha256"], forge.file_digest(self.kit_bytes(self.SIX[state])))
        second = self.cli(self.target)
        self.assertEqual(json.loads(second.stdout)["written"], [])
        states = self.states(forge.diff_project(self.target))
        self.assertEqual(states[self.SIX["missing"]], "identical")
        self.assertEqual(states[self.SIX["kit-newer"]], "identical")
        both = self.cli(self.target, "--only", self.SIX["project-removed"], "--only", self.SIX["both-changed"])
        self.assertEqual(json.loads(both.stdout)["written"], [self.SIX["project-removed"]])
        dry = self.cli(self.target, "--dry-run")
        self.assertTrue(json.loads(dry.stdout)["dry_run"])

    def test_the_readme_describes_update(self):
        readme = (FORGE_ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("### `update`", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
        for flag in ("--only", "--dry-run", "--no-scripts"):
            self.assertIn(f"python forge.py update ..\\ExistingRepo {flag}", section, flag)
        self.assertIn("never writes over", section)


class RecordTests(KitFixture, unittest.TestCase):
    """`forge.py record`: an install made before the record gains entries for the files still as the kit ships them."""

    def legacy(self, kit="todo", **kw):
        """An install made before the record existed: the kit's files, and no `.conclave/kits.json`."""
        forge.apply_kit(self.target, kit, **kw)
        (self.target / forge.RECORD).unlink()

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()

    def test_only_files_identical_to_the_kit_are_recorded(self):
        self.legacy(agent="claude")
        edited = ".claude/skills/process-plan/SKILL.md"
        (self.target / edited).write_bytes(b"the project's own edit\n")
        result = forge.record_project(self.target)
        files = self.loaded()["files"]
        self.assertNotIn(edited, files)
        self.assertIn({"path": edited, "reason": "differs"}, result["skipped"])
        planned = [e[2] for e in forge.kit_plan(self.target, "todo", agent="claude")[0]]
        self.assertEqual(sorted(files), sorted(p for p in planned if p != edited))
        for rel in files:
            self.assertEqual(files[rel]["sha256"], forge.file_digest((self.target / rel).read_bytes()))
        kit = self.loaded()["kits"]["todo"]
        self.assertEqual(kit["agents"], ["claude"])
        self.assertEqual(kit["sdk_commit"], forge.sdk_commit())
        self.assertEqual(forge.diff_project(self.target)["kits"]["todo"]["agents"], ["claude"])
        self.assertEqual(self.states(forge.diff_project(self.target))[edited], "differs")

    def test_a_wordpress_host_is_adopted_and_a_recorded_kit_is_left_alone(self):
        self.legacy("wordpress", host="wpcom")
        forge.record_project(self.target)
        self.assertEqual(self.loaded()["kits"]["wordpress"]["host"], "wpcom")
        (self.target / forge.WORDPRESS_PIN).unlink()
        self.assertEqual(self.states(forge.diff_project(self.target), "wordpress")[forge.WORDPRESS_PIN],
                         "project-removed")
        # Adopting a further file under the recorded wpcom kit leaves its whole entry, host included, as it was.
        record = self.loaded()
        dropped = next(rel for rel in record["files"] if rel != forge.WORDPRESS_PIN)
        del record["files"][dropped]
        record["kits"]["wordpress"]["sdk_commit"] = "b" * 40
        forge.write_record(self.target, record)
        kit_before = dict(record["kits"]["wordpress"])
        self.assertIn(dropped, forge.record_project(self.target)["recorded"])
        self.assertEqual(self.loaded()["kits"]["wordpress"], kit_before)
        self.assertEqual(kit_before["host"], "wpcom")

        other = pathlib.Path(self.tmp.name) / "other"
        other.mkdir()
        forge.apply_kit(other, "todo", agent="claude")
        record = forge.load_record(other)
        assert record is not None
        record["kits"]["todo"]["sdk_commit"] = "a" * 40
        dropped = ".claude/skills/add-todo/SKILL.md"
        del record["files"][dropped]
        forge.write_record(other, record)
        forge.record_project(other)
        after = forge.load_record(other)
        assert after is not None
        self.assertEqual(after["kits"]["todo"], record["kits"]["todo"])
        self.assertIn(dropped, after["files"])

    def test_an_entry_already_recorded_is_never_replaced(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits/todo", sdk / "kits/todo")
        rel = ".claude/skills/add-todo/SKILL.md"
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            self.legacy(agent="claude")
            forge.record_project(self.target)
            first = self.loaded()["files"][rel]
            template = sdk / "kits/todo/templates" / rel
            template.write_bytes(template.read_bytes() + b"\nA later kit's line.\n")
            result = forge.record_project(self.target)
            self.assertEqual(self.loaded()["files"][rel], first)
            self.assertIn({"path": rel, "reason": "recorded"}, result["skipped"])
            self.assertEqual(self.states(forge.diff_project(self.target))[rel], "kit-newer")

    def test_refusals_come_before_settling_an_interrupted_run(self):
        self.six_state_fixture()
        staged = self.target / (self.SIX["project-removed"] + forge.STAGED)
        staged.write_bytes((FORGE_ROOT / "kits/todo/templates" / self.SIX["project-removed"]).read_bytes())
        before = self.snapshot(self.target)
        for args in (["record", self.target, "nope"], ["record", self.target, "reviewer"]):
            code, _out, err = self.run_main(*args)
            self.assertEqual(code, 2, err)
            self.assertEqual(self.snapshot(self.target), before, args)
        result = forge.record_project(self.target, dry_run=True)
        self.assertEqual(self.snapshot(self.target), before)
        self.assertTrue(result["dry_run"])
        forge.record_project(self.target)
        self.assertFalse(staged.exists())
        self.assertTrue((self.target / self.SIX["project-removed"]).is_file())

    def test_a_dry_run_lists_what_it_would_record(self):
        self.legacy(agent="claude")
        before = self.snapshot(self.target)
        result = forge.record_project(self.target, dry_run=True)
        self.assertEqual(self.snapshot(self.target), before)
        self.assertFalse((self.target / forge.RECORD).exists())
        self.assertTrue(result["recorded"])

    def test_a_failed_record_write_keeps_the_earlier_record_and_fails(self):
        self.legacy(agent="claude")
        forge.record_project(self.target, "todo")
        record_bytes = (self.target / forge.RECORD).read_bytes()
        record = self.loaded()
        del record["files"][".claude/skills/add-todo/SKILL.md"]
        forge.write_record(self.target, record)
        record_bytes = (self.target / forge.RECORD).read_bytes()
        before = self.snapshot(self.target)
        with unittest.mock.patch.object(forge, "atomic_write", side_effect=OSError(28, "No space left on device")):
            code, out, err = self.run_main("record", self.target)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("Traceback", err)
        self.assertIn("No space left on device", err)
        self.assertEqual((self.target / forge.RECORD).read_bytes(), record_bytes)
        self.assertEqual(self.snapshot(self.target), before)

    def test_every_skip_reason_is_named(self):
        (self.target / "artisan").write_text("<?php\n", encoding="utf-8")
        forge.apply_kit(self.target, "laravel", agent="claude")
        forge.apply_kit(self.target, "todo", agent="claude")
        (self.target / forge.RECORD).unlink()
        (self.target / ".claude/skills/process-plan/SKILL.md").write_bytes(b"edited\n")
        (self.target / ".claude/skills/groom-plan/SKILL.md").unlink()
        skill = self.target / ".claude/skills/add-todo"
        shutil.rmtree(skill)
        outside = pathlib.Path(self.tmp.name) / "outside"
        outside.mkdir()
        make_link(outside, skill)
        blocked = (self.target / ".claude/skills/create-todo/SKILL.md").resolve()
        real_read = pathlib.Path.read_bytes

        def deny(path):
            if pathlib.Path(path).resolve() == blocked:
                raise PermissionError(13, "Permission denied", str(path))
            return real_read(path)

        with unittest.mock.patch.object(pathlib.Path, "read_bytes", deny):
            code, out, err = self.run_main("record", self.target)
        self.assertEqual(code, 0, err)
        reasons = {item["reason"] for item in json.loads(out)["skipped"]}
        self.assertEqual(reasons, {"differs", "missing", "unsafe", "unreadable", "generated"})
        code, out, err = self.run_main("record", self.target)
        self.assertIn("recorded", {item["reason"] for item in json.loads(out)["skipped"]})

    def test_the_readme_orders_record_diff_update(self):
        readme = (FORGE_ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("### 2. Existing Project", 1)[1].split("\n### ", 1)[0]
        steps = [section.index(f"python forge.py {cmd} ..\\ExistingRepo") for cmd in ("record", "diff", "update")]
        self.assertEqual(steps, sorted(steps))


class KitNewTests(KitFixture, unittest.TestCase):
    """`update --kit-new` and `record --merged`: a hand merge of a file both sides changed, never written over it."""

    def kit_bytes(self, rel, kit="todo"):
        return (FORGE_ROOT / "kits" / kit / "templates" / rel).read_bytes()

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main([str(a) for a in args])
        return code, (json.loads(out.getvalue()) if code == 0 else {}), err.getvalue()

    def differs_fixture(self):
        """The six states, plus a `differs` file (one with no record entry) and a changed script."""
        self.six_state_fixture()
        differs = ".claude/skills/review-todo-section/SKILL.md"
        (self.target / differs).write_bytes(b"the project's own, never recorded\n")
        record = self.loaded()
        del record["files"][differs]
        record["files"]["scripts/todo-graph.py"]["sha256"] = "c" * 64
        (self.target / "scripts/todo-graph.py").write_bytes(b"# the project's own script\n")
        forge.write_record(self.target, record)
        return differs

    def test_kit_new_writes_the_kits_version_beside_each_file_both_sides_changed(self):
        differs = self.differs_fixture()
        both = self.SIX["both-changed"]
        before = self.snapshot(self.target)
        code, dry, err = self.run_main("update", self.target, "--kit-new", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.snapshot(self.target), before)
        self.assertIn(both + forge.KIT_NEW, dry["kit_new"])

        code, out, err = self.run_main("update", self.target, "--kit-new", "--no-scripts")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(out["kit_new"]), sorted([both + forge.KIT_NEW, differs + forge.KIT_NEW]))
        for rel in (both, differs):
            self.assertEqual((self.target / (rel + forge.KIT_NEW)).read_bytes(), self.kit_bytes(rel))
            self.assertEqual(forge.file_digest((self.target / rel).read_bytes()), before[rel], rel)
        files = self.loaded()["files"]
        self.assertFalse([p for p in files if p.endswith(forge.KIT_NEW)])
        # project-changed has nothing new to merge, and --no-scripts kept scripts/ out.
        self.assertFalse((self.target / (self.SIX["project-changed"] + forge.KIT_NEW)).exists())
        self.assertFalse((self.target / ("scripts/todo-graph.py" + forge.KIT_NEW)).exists())
        merge = forge.diff_project(self.target)["kits"]["todo"]["merge_pending"]
        self.assertEqual(sorted(merge), sorted([both + forge.KIT_NEW, differs + forge.KIT_NEW]))
        (self.target / (differs + forge.KIT_NEW)).unlink()
        self.assertEqual(forge.diff_project(self.target)["kits"]["todo"]["merge_pending"], [both + forge.KIT_NEW])

    def test_only_narrows_the_copies(self):
        self.differs_fixture()
        both = self.SIX["both-changed"]
        code, out, err = self.run_main("update", self.target, "--kit-new", "--only", both)
        self.assertEqual(code, 0, err)
        self.assertEqual(out["kit_new"], [both + forge.KIT_NEW])
        self.assertFalse((self.target / ("scripts/todo-graph.py" + forge.KIT_NEW)).exists())

    def test_an_existing_sibling_is_never_replaced(self):
        differs = self.differs_fixture()
        both = self.SIX["both-changed"]
        forge.update_project(self.target, kit_new=True)
        edited = self.target / (both + forge.KIT_NEW)
        edited.write_bytes(b"mid-merge\n")
        folder = self.target / (differs + forge.KIT_NEW)
        folder.unlink()
        folder.mkdir()
        dangling_target = pathlib.Path(self.tmp.name) / "gone"
        script = self.target / ("scripts/todo-graph.py" + forge.KIT_NEW)
        script.unlink()
        dangling_target.mkdir()
        make_link(dangling_target, script)
        dangling_target.rmdir()
        entries = self.loaded()["files"]
        result = forge.update_project(self.target, kit_new=True)
        self.assertEqual(edited.read_bytes(), b"mid-merge\n")
        self.assertTrue(folder.is_dir())
        self.assertFalse(dangling_target.exists())
        pending = {i["path"] for i in result["left"] if i["state"] == "merge-pending"}
        self.assertEqual(pending, {both + forge.KIT_NEW, differs + forge.KIT_NEW, "scripts/todo-graph.py" + forge.KIT_NEW})
        self.assertEqual(result["kit_new"], [])
        self.assertEqual(self.loaded()["files"], entries)

    def test_forges_own_leftovers_are_never_planned(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits/todo", sdk / "kits/todo")
        for suffix in (forge.KIT_NEW, forge.STAGED, forge.STAGED_REPLACE):
            (sdk / "kits/todo/templates/scripts" / ("todo-graph.py" + suffix)).write_bytes(b"left by mistake\n")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            rels = [e[2] for e in forge.kit_plan(self.target, "todo")[0]]
        self.assertIn("scripts/todo-graph.py", rels)
        self.assertFalse([r for r in rels if r.endswith(forge.FORGE_SUFFIXES)])

    def test_record_merged_marks_the_merge_and_removes_the_copy(self):
        differs = self.differs_fixture()
        both = self.SIX["both-changed"]
        forge.update_project(self.target, kit_new=True)
        (self.target / both).write_bytes(self.kit_bytes(both) + b"\nThe project's line, kept in the merge.\n")
        before = self.snapshot(self.target)
        code, out, err = self.run_main("record", self.target, "--merged", both, "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["recorded"], [both])
        self.assertEqual(self.snapshot(self.target), before)

        code, out, err = self.run_main("record", self.target, "--merged", both, "--merged", both)
        self.assertEqual(code, 0, err)
        self.assertEqual(out["recorded"], [both])
        self.assertFalse((self.target / (both + forge.KIT_NEW)).exists())
        self.assertEqual(self.loaded()["files"][both]["sha256"], forge.file_digest(self.kit_bytes(both)))
        self.assertEqual(self.states(forge.diff_project(self.target))[both], "project-changed")

        # A merge that took the kit's version whole is accepted.
        (self.target / differs).write_bytes(self.kit_bytes(differs))
        code, out, err = self.run_main("record", self.target, "--merged", differs)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.loaded()["files"][differs], {"kit": "todo", "sha256": forge.file_digest(self.kit_bytes(differs))})
        self.assertEqual(self.states(forge.diff_project(self.target))[differs], "identical")

    def test_a_merge_that_took_the_kit_whole_then_reads_kit_newer_on_the_next_kit_change(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits/todo", sdk / "kits/todo")
        rel = ".claude/skills/add-todo/SKILL.md"
        template = sdk / "kits/todo/templates" / rel
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            forge.apply_kit(self.target, "todo", agent="claude")
            (self.target / rel).write_bytes(b"own\n")
            template.write_bytes(template.read_bytes() + b"\nkit change one\n")
            forge.update_project(self.target, kit_new=True, only=[rel])
            (self.target / rel).write_bytes(template.read_bytes())
            self.assertEqual(self.run_main("record", self.target, "--merged", rel)[0], 0)
            self.assertEqual(self.states(forge.diff_project(self.target))[rel], "identical")
            template.write_bytes(template.read_bytes() + b"\nkit change two\n")
            self.assertEqual(self.states(forge.diff_project(self.target))[rel], "kit-newer")

    def test_a_differs_file_with_no_kit_entry_gains_both(self):
        forge.apply_kit(self.target, "todo", agent="claude")
        (self.target / forge.RECORD).unlink()
        rel = ".claude/skills/add-todo/SKILL.md"
        (self.target / rel).write_bytes(b"own\n")
        forge.update_project(self.target, kit_new=True, only=[rel])
        forge.record_project(self.target, merged=[rel])
        record = self.loaded()
        self.assertEqual(record["kits"]["todo"]["agents"], ["claude"])
        self.assertEqual(record["files"], {rel: {"kit": "todo", "sha256": forge.file_digest(self.kit_bytes(rel))}})

    def test_a_merge_the_kit_has_moved_past_refuses(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits/todo", sdk / "kits/todo")
        rel = ".claude/skills/add-todo/SKILL.md"
        with unittest.mock.patch.object(forge, "FORGE_ROOT", sdk):
            forge.apply_kit(self.target, "todo", agent="claude")
            (self.target / rel).write_bytes(b"own\n")
            template = sdk / "kits/todo/templates" / rel
            template.write_bytes(template.read_bytes() + b"\nkit change one\n")
            forge.update_project(self.target, kit_new=True)
            template.write_bytes(template.read_bytes() + b"\nkit change two\n")
            record_bytes = (self.target / forge.RECORD).read_bytes()
            code, _out, err = self.run_main("record", self.target, "--merged", rel)
            self.assertEqual(code, 2)
            self.assertIn("no longer the kit's version", err)
            self.assertEqual((self.target / forge.RECORD).read_bytes(), record_bytes)
            # The copy the project edited mid-merge refuses the same way.
            (self.target / (rel + forge.KIT_NEW)).write_bytes(template.read_bytes() + b"edited\n")
            self.assertEqual(self.run_main("record", self.target, "--merged", rel)[0], 2)

    def test_one_bad_argument_refuses_the_batch_before_any_write(self):
        self.differs_fixture()
        both = self.SIX["both-changed"]
        forge.update_project(self.target, kit_new=True)
        staged = self.target / (self.SIX["project-removed"] + forge.STAGED)
        staged.write_bytes(self.kit_bytes(self.SIX["project-removed"]))
        before = self.snapshot(self.target)
        for bad in (self.SIX["identical"], self.SIX["project-removed"], "docs/nothing-here", "../x"):
            code, _out, err = self.run_main("record", self.target, "--merged", both, "--merged", bad)
            self.assertEqual(code, 2, (bad, err))
            self.assertEqual(self.snapshot(self.target), before, bad)
        self.assertTrue(staged.is_file())

    def test_the_readme_documents_the_merge(self):
        readme = (FORGE_ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("### `update`", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
        self.assertIn("python forge.py update ..\\ExistingRepo --kit-new", section)
        documented = "python forge.py record ..\\ExistingRepo --merged .claude/skills/process-plan/SKILL.md"
        self.assertIn(documented, section)
        # The documented file, made both-changed, merged and recorded by that exact command on a scratch project.
        forge.apply_kit(self.target, "todo", agent="claude")
        rel = ".claude/skills/process-plan/SKILL.md"
        (self.target / rel).write_bytes(b"own\n")
        self.set_recorded(rel, b"an older kit's version\n")
        forge.update_project(self.target, kit_new=True)
        (self.target / rel).write_bytes(self.kit_bytes(rel) + b"\nThe project's line.\n")
        args: list[str] = [str(part) for part in documented.split()[2:]]
        args[1] = str(self.target)
        self.assertEqual(self.run_main(*args)[0], 0)
        self.assertEqual(self.states(forge.diff_project(self.target))[rel], "project-changed")


class DriftTests(KitFixture, unittest.TestCase):
    """`forge.py drift`: the weekly report of which listed projects have kit files to update, merge or adopt."""

    def projects_file(self, projects):
        path = pathlib.Path(self.tmp.name) / "projects.json"
        path.write_text(json.dumps({"schema_version": 1, "projects": projects}), encoding="utf-8")
        return path

    def entry(self, name, path):
        return {"name": name, "windows": str(path) if path else None, "posix": str(path) if path else None}

    def run_drift(self, projects_path):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main(["drift", "--projects", str(projects_path)])
        return code, out.getvalue(), err.getvalue()

    def test_a_valid_list_reads_back_and_every_fault_refuses_by_name(self):
        good = [self.entry("One", self.target), {"name": "Two", "windows": None, "posix": "~/two"}]
        self.assertEqual(forge.load_projects(self.projects_file(good)), good)
        bad = {
            "a missing name": [{"windows": "x", "posix": None}],
            "the name appears twice": [self.entry("One", "a"), self.entry("One", "b")],
            "needs a windows or a posix path": [{"name": "One", "windows": None, "posix": None}],
            "needs exactly the keys name": [{"name": "One", "windows": "a", "posix": None, "extra": 1}],
            "name must be a non-empty string": [{"name": 7, "windows": "a", "posix": None}],
            "posix must be null or a non-empty path": [{"name": "One", "windows": None, "posix": 3}],
        }
        for why, projects in bad.items():
            with self.assertRaises(ValueError, msg=why) as caught:
                forge.load_projects(self.projects_file(projects))
            self.assertIn("projects.json", str(caught.exception), why)
        path = pathlib.Path(self.tmp.name) / "projects.json"
        path.write_text(json.dumps({"schema_version": 2, "projects": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "schema_version must be 1"):
            forge.load_projects(path)
        with self.assertRaisesRegex(ValueError, r"projects\[0\] \(One\)\.windows"):
            forge.load_projects(self.projects_file([{"name": "One", "windows": "", "posix": "a"}]))

    def test_the_path_for_this_system_is_used_with_home_expanded(self):
        home = pathlib.Path(self.tmp.name) / "home"
        (home / "proj").mkdir(parents=True)
        projects = [{"name": "Posix", "windows": None, "posix": "~/proj"},
                    {"name": "Windows", "windows": str(home / "proj"), "posix": None}]
        with unittest.mock.patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            posix = {r["name"]: r for r in forge.drift_report(projects, system="posix")}
            nt = {r["name"]: r for r in forge.drift_report(projects, system="nt")}
        self.assertEqual(posix["Posix"]["path"], str(home / "proj"))
        self.assertEqual(posix["Posix"]["state"], "checked")
        self.assertEqual(posix["Windows"]["state"], "not on this machine")
        self.assertEqual(nt["Windows"]["state"], "checked")
        self.assertEqual(nt["Posix"]["state"], "not on this machine")

    def fake_diff(self, states):
        files = [{"path": f"{state}/{i}", "state": state, **({"reason": "denied"} if state == "unreadable" else {})}
                 for state, n in states.items() for i in range(n)]
        return {"kits": {"todo": {"files": files}}}

    def test_each_state_is_counted_exactly(self):
        known = {"kit-newer": 2, "both-changed": 3, "differs": 4, "missing": 5, "project-only": 6, "unsafe": 1,
                 "unreadable": 1, "identical": 9, "project-changed": 7, "project-removed": 2, "generated": 1}
        with unittest.mock.patch.object(forge, "diff_project", return_value=self.fake_diff(known)):
            row = forge.drift_report([self.entry("P", self.target)])[0]
        counts = {label: len(paths) for label, paths in row["counts"].items()}
        self.assertEqual(counts, {"can update": 2, "need a merge": 3, "unrecorded": 4, "missing": 5, "retired": 6,
                                  "incomplete": 2})
        self.assertIn("unreadable/0 (denied)", row["counts"]["incomplete"])
        lines, drifted = forge.drift_lines([row])
        self.assertTrue(drifted)
        self.assertEqual(lines[-1], "P: 2 can update, 3 need a merge, 4 unrecorded, 5 missing, 6 retired, 2 incomplete")

    def test_a_count_past_twenty_shows_twenty_paths_and_the_rest_as_a_number(self):
        with unittest.mock.patch.object(forge, "diff_project", return_value=self.fake_diff({"missing": 25})):
            lines, _ = forge.drift_lines(forge.drift_report([self.entry("P", self.target)]))
        self.assertEqual(len([l for l in lines if l.startswith("  missing: missing/")]), 20)
        self.assertIn("  missing: ... and 5 more", lines)

    def test_only_unrecorded_or_only_unreadable_still_fails_the_report(self):
        for state in ("differs", "unreadable", "unsafe", "project-only"):
            with unittest.mock.patch.object(forge, "diff_project", return_value=self.fake_diff({state: 1})):
                code, out, err = self.run_drift(self.projects_file([self.entry("P", self.target)]))
            self.assertEqual(code, 3, (state, out, err))

    def test_drifted_current_absent_and_refused_projects_are_all_reported(self):
        self.six_state_fixture()  # drifted: one kit-newer, one both-changed, one missing
        current = pathlib.Path(self.tmp.name) / "current"
        current.mkdir()
        forge.apply_kit(current, "todo", agent="claude")
        broken = pathlib.Path(self.tmp.name) / "broken"
        (broken / ".conclave").mkdir(parents=True)
        (broken / forge.RECORD).write_text("{ not json", encoding="utf-8")
        projects = [self.entry("Broken", broken), self.entry("Drifted", self.target),
                    self.entry("Current", current), self.entry("Absent", pathlib.Path(self.tmp.name) / "nowhere"),
                    # A path only for the other system.
                    {"name": "Elsewhere", "windows": None if os.name == "nt" else "C:/x",
                     "posix": "/x" if os.name == "nt" else None}]
        code, out, err = self.run_drift(self.projects_file(projects))
        self.assertEqual(code, 3, err)
        lines = out.splitlines()
        summary = lines[lines.index("Summary:") + 1:]
        self.assertEqual([line.split(":")[0] for line in summary], ["Broken", "Drifted", "Current", "Absent", "Elsewhere"])
        self.assertTrue(summary[0].startswith("Broken: diff refused: "), summary[0])
        self.assertIn("Drifted: 1 can update, 1 need a merge, 0 unrecorded, 1 missing, 0 retired, 0 incomplete", lines)
        self.assertIn("Current: 0 can update, 0 need a merge, 0 unrecorded, 0 missing, 0 retired, 0 incomplete", lines)
        self.assertIn("Absent: not on this machine", lines)
        self.assertIn("Elsewhere: not on this machine", lines)
        self.assertIn(f"  can update: {self.SIX['kit-newer']}", lines)

        code, out, _ = self.run_drift(self.projects_file([self.entry("Current", current),
                                                          self.entry("Absent", pathlib.Path(self.tmp.name) / "no")]))
        self.assertEqual(code, 0, out)

    def test_a_scheduled_run_reaches_the_alert_with_the_report(self):
        sdk = pathlib.Path(self.tmp.name) / "sdk"
        shutil.copytree(FORGE_ROOT / "kits", sdk / "kits", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(FORGE_ROOT / "forge.py", sdk / "forge.py")
        shutil.copytree(FORGE_ROOT / ".conclave/automations", sdk / ".conclave/automations",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.six_state_fixture()
        (sdk / forge.PROJECTS).write_text(json.dumps({"schema_version": 1, "projects": [
            self.entry("Drifted", self.target)]}), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("sdk_run", sdk / ".conclave/automations/run.py")
        assert spec is not None and spec.loader is not None
        run = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run)
        alerts = []
        code = run.main(["conclave-sdk-drift"], root=str(sdk), alerter=lambda *a: alerts.append(a))
        self.assertEqual(code, 3)
        self.assertEqual(len(alerts), 1)
        name, task, outcome, tail, folder = alerts[0]
        self.assertEqual((name, task["command"], outcome["exit"], folder),
                         ("conclave-sdk-drift", ["python", "forge.py", "drift"], 3, "\\Conclave-SDK\\"))
        self.assertIn("Drifted: 1 can update, 1 need a merge", tail)

    def test_every_summary_survives_the_alerts_tail(self):
        (self.target.parent / "RasterFold").mkdir()
        (self.target.parent / "Impossible OS").mkdir()
        """The failure email carries the last lines of the output; with the real projects first counts (2026-11-11)
        the summaries must still all be in it."""
        spec = importlib.util.spec_from_file_location("sdk_alert", FORGE_ROOT / ".conclave/automations/alert.py")
        assert spec is not None and spec.loader is not None
        alert = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(alert)
        diffs = {"RasterFold": self.fake_diff({"differs": 45, "missing": 50}),
                 "Impossible OS": self.fake_diff({"differs": 8, "missing": 27})}
        log = pathlib.Path(self.tmp.name) / "run.log"
        with unittest.mock.patch.object(forge, "diff_project", side_effect=lambda path: diffs[pathlib.Path(path).name]):
            lines, drifted = forge.drift_lines(forge.drift_report(
                [self.entry("RasterFold", self.target.parent / "RasterFold"),
                 self.entry("Impossible OS", self.target.parent / "Impossible OS")]))
        self.assertTrue(drifted)
        log.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tail = alert.tail_of(str(log))
        self.assertIn("RasterFold: 0 can update, 0 need a merge, 45 unrecorded, 50 missing", tail)
        self.assertIn("Impossible OS: 0 can update, 0 need a merge, 8 unrecorded, 27 missing", tail)

    def test_the_sdks_own_list_and_task_are_in_place(self):
        projects = forge.load_projects(FORGE_ROOT / forge.PROJECTS)
        self.assertEqual([p["name"] for p in projects], ["RasterFold", "Impossible OS"])
        tasks = json.loads((FORGE_ROOT / ".conclave/automations/tasks.json").read_text(encoding="utf-8"))["tasks"]
        drift = next(t for t in tasks if t["name"] == "conclave-sdk-drift")
        self.assertEqual((drift["command"], drift["trigger"], drift["timeout_minutes"]),
                         (["python", "forge.py", "drift"], {"weekly": "Monday", "at": "07:30"}, 10))
        for readme in ("README.md", ".conclave/automations/README.md"):
            self.assertIn(".conclave/projects.json", (FORGE_ROOT / readme).read_text(encoding="utf-8"), readme)


class InitPlanningTests(KitFixture, unittest.TestCase):
    """`init` plans every chosen kit, and checks every destination, before it writes a file."""

    def init(self, target, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = forge.main(["init", str(target), *args])
        return code, err.getvalue()

    def test_a_kit_that_refuses_leaves_the_folder_empty(self):
        code, err = self.init(self.target, "--kit", "todo", "--kit", "laravel")
        self.assertEqual(code, 2, err)
        self.assertIn("artisan", err)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_an_unknown_kit_refuses_naming_the_kits(self):
        code, err = self.init(self.target, "--kit", "nope")
        self.assertEqual(code, 2, err)
        self.assertIn("Available kits: ", err)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_a_path_only_a_later_kit_writes_refuses_before_the_first_kit(self):
        forge.apply_kit(self.target, "reviewer", agent="claude")
        (self.target / ".claude/skills").mkdir(parents=True, exist_ok=True)
        (self.target / ".claude/skills/add-todo").write_bytes(b"a file where the todo kit needs a folder\n")
        before = self.snapshot(self.target)
        code, err = self.init(self.target, "--kit", "todo")
        self.assertEqual(code, 2, err)
        self.assertIn(".claude/skills/add-todo", err)
        self.assertEqual(self.snapshot(self.target), before)

    def test_a_new_path_is_created_only_when_every_kit_plans(self):
        new = pathlib.Path(self.tmp.name) / "new" / "project"
        code, err = self.init(new, "--kit", "laravel")
        self.assertEqual(code, 2, err)
        self.assertFalse(new.exists())
        self.assertFalse(new.parent.exists())
        self.assertEqual(self.init(new, "--kit", "todo")[0], 0)
        self.assertTrue((new / "scripts/todo-graph.py").is_file())
        site = pathlib.Path(self.tmp.name) / "site"
        code, err = self.init(site, "--kit", "wordpress", "--wp-host", "wpcom")
        self.assertEqual(code, 0, err)
        self.assertTrue((site / forge.WORDPRESS_PIN).is_file())
        record = forge.load_record(site)
        assert record is not None
        self.assertEqual(record["kits"]["wordpress"]["host"], "wpcom")

    def test_no_scripts_is_applied_to_the_preflight(self):
        (self.target / "scripts").write_bytes(b"a file where scripts/ would go\n")
        before = self.snapshot(self.target)
        code, err = self.init(self.target, "--kit", "todo")
        self.assertEqual(code, 2, err)
        self.assertEqual(self.snapshot(self.target), before)
        code, err = self.init(self.target, "--kit", "todo", "--no-scripts")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.target / ".claude/skills/add-todo/SKILL.md").is_file())


class ProcessPlanAuditTests(unittest.TestCase):
    """process-plan's audit runs the kits' tests and the project's own: neither replaces the other (a project such as
    a project may keep its script tests in tests/scripts, where kits install theirs under scripts/tests)."""

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
