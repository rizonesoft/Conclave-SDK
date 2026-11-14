"""Kit install tests: what the six bash `kits/<kit>/scripts/test-install.sh` files asserted, against `forge.py kit`.

The bash tests ran the bash installers and only on POSIX. These run `forge.apply_kit`, `forge.doctor_repo` and the
command line on every host (D01 T02 section 3). The scripts, the installers and the two `doctor.sh` files were
retired in D01 T02 section 4: `forge.py` is the only installer and the only doctor. The seventh kit, `unattended`, never had a bash installer: its install
tests are `UnattendedKitTests` in `tests/test_forge.py`.

Assertion map. Every line of each script is in exactly one row: `lines` are the script's own line numbers, `assertion`
says what the lines require and the outcome they expect (a loop is written out: "3 agents", "4 prompt templates"), and
`test` is the method of `KitInstallTests` that requires the same of `forge.py` (`none` for lines that assert nothing).
The map is the record of the port: its line numbers are those of the scripts as last committed, at 9f196ea3cb49
(read one with `git show 9f196ea3cb49:kits/<kit>/scripts/test-install.sh`). While the scripts existed,
`AssertionMapTests` read them and failed on a line in no row and on a line that could fail a script in a `none` row;
it still fails when a line is in two rows or when a row names a test this file does not define.

kit | lines | assertion | test
automations | 1-11 | script header: shell options, native links, scratch folder | none
automations | 13-20 | fixture with its own tasks.json; the install exits 0 | test_automations_keeps_the_task_list_and_installs_the_rest
automations | 22-23 | the project's tasks.json keeps its bytes | test_automations_keeps_the_task_list_and_installs_the_rest
automations | 24-27 | SKILL.md for .agents, .claude, .codex; Codex openai.yaml | test_automations_keeps_the_task_list_and_installs_the_rest
automations | 28-30 | run.py, alert.py, install.ps1, README.md are files | test_automations_keeps_the_task_list_and_installs_the_rest
automations | 31 | install.sh is mode 755 | test_automations_keeps_the_task_list_and_installs_the_rest
automations | 32 | run.py --check prints the project's folder | test_automations_keeps_the_task_list_and_installs_the_rest
automations | 34-41 | fresh: exit 0, folder null, run.py --check exits non-zero | test_automations_fresh_install_has_no_folder_yet
automations | 43-45 | second install exits 0, every file digest unchanged | test_a_second_install_changes_no_file
automations | 47-50 | dry run exits 0, the folder stays empty | test_a_dry_run_writes_nothing
automations | 52-55 | --force exits non-zero | test_force_is_refused_and_changes_nothing
automations | 57-64 | linked .conclave: exits non-zero, sentinel unchanged | test_a_linked_destination_folder_is_refused
automations | 66 | closing summary line | none
base | 1-11 | script header: shell options, native links, scratch folder | none
base | 13-25 | fixture with its own three files; the install exits 0 | test_base_keeps_the_projects_files_and_installs_the_rest
base | 27-29 | AGENTS.md, a Claude skill, Codex settings keep their bytes | test_base_keeps_the_projects_files_and_installs_the_rest
base | 30-35 | authoring-skills for 3 agents, tiers script; no agy files | test_base_keeps_the_projects_files_and_installs_the_rest
base | 36-38 | a skill is mode 644, verify-agent-tiers.mjs 755 | test_base_keeps_the_projects_files_and_installs_the_rest
base | 40-42 | second install exits 0, every file digest unchanged | test_a_second_install_changes_no_file
base | 44-47 | dry run exits 0, the folder stays empty | test_a_dry_run_writes_nothing
base | 49-52 | --force exits non-zero | test_force_is_refused_and_changes_nothing
base | 54-63 | linked scripts: exits non-zero, nothing written anywhere | test_a_linked_destination_folder_is_refused
base | 65 | closing summary line | none
laravel | 1-12 | script header: shell options, native links, scratch folder | none
laravel | 14-25 | fixture with artisan and its own AGENTS.md; install exits 0 | test_laravel_keeps_agents_md_and_installs_at_the_app_root
laravel | 27 | AGENTS.md keeps its bytes | test_laravel_keeps_agents_md_and_installs_at_the_app_root
laravel | 28-38 | script, hook, boost.json, doc, 3 skills, .mcp.json; modes | test_laravel_keeps_agents_md_and_installs_at_the_app_root
laravel | 39 | .mcp.json args are [artisan, boost:mcp] | test_laravel_keeps_agents_md_and_installs_at_the_app_root
laravel | 41 | lsp-diagnostics.py --help exits 0 | test_laravel_keeps_agents_md_and_installs_at_the_app_root
laravel | 43-45 | doctor exits 0 and reports artisan, lsp-diagnostics.py | test_laravel_doctor_reports_artisan_and_the_diagnostics_script
laravel | 47-49 | second install exits 0, every file digest unchanged | test_a_second_install_changes_no_file
laravel | 51-56 | dry run exits 0, no script and no .mcp.json written | test_a_dry_run_writes_nothing
laravel | 58-61 | --force exits non-zero | test_force_is_refused_and_changes_nothing
laravel | 63-68 | no artisan: the install exits non-zero | test_laravel_refuses_a_project_with_no_artisan
laravel | 70-77 | platform/artisan: boost.json and .mcp.json point at it | test_laravel_finds_a_nested_platform_app
laravel | 79-87 | linked scripts: exits non-zero, sentinel unchanged | test_a_linked_destination_folder_is_refused
laravel | 89 | closing summary line | none
reviewer | 1-11 | script header: shell options, native links, scratch folder | none
reviewer | 13-20 | fixture with its own pin; the install exits 0 | test_reviewer_keeps_the_pin_and_installs_runnable_tools
reviewer | 22-23 | the project's reviewers.toml keeps its bytes | test_reviewer_keeps_the_pin_and_installs_runnable_tools
reviewer | 24-30 | SKILL.md for 3 agents, openai.yaml, 4 prompt templates | test_reviewer_keeps_the_pin_and_installs_runnable_tools
reviewer | 31-32 | review-dispatch.py is mode 755 and --help exits 0 | test_reviewer_keeps_the_pin_and_installs_runnable_tools
reviewer | 33-39 | review_pin.py, review-prompt.py, their tests; --help exits 0 | test_reviewer_keeps_the_pin_and_installs_runnable_tools
reviewer | 41-45 | fresh: exit 0, review_pin --check and --check-pin exit 0 | test_reviewer_fresh_pin_passes_its_checks_and_is_three_pass
reviewer | 46-50 | pin: astra model, claude and agy to astra, three-pass | test_reviewer_fresh_pin_passes_its_checks_and_is_three_pass
reviewer | 51-52 | --caps prints pass_cap 33; completion has plan-delivery | test_reviewer_fresh_pin_passes_its_checks_and_is_three_pass
reviewer | 53-58 | no codex or gemini route, no carbon, no sonnet | test_reviewer_fresh_pin_passes_its_checks_and_is_three_pass
reviewer | 60-62 | second install exits 0, every file digest unchanged | test_a_second_install_changes_no_file
reviewer | 64-67 | dry run exits 0, the folder stays empty | test_a_dry_run_writes_nothing
reviewer | 69-72 | --force exits non-zero | test_force_is_refused_and_changes_nothing
reviewer | 74-81 | linked scripts: exits non-zero, sentinel unchanged | test_a_linked_destination_folder_is_refused
reviewer | 83 | closing summary line | none
todo | 1-11 | script header: shell options, native links, scratch folder | none
todo | 13-20 | fixture with its own plan index; the install exits 0 | test_todo_keeps_the_plan_and_installs_a_runnable_graph
todo | 22-23 | the project's TODO-00-INDEX.md keeps its bytes | test_todo_keeps_the_plan_and_installs_a_runnable_graph
todo | 24-32 | 8 skills for 3 agents, openai.yaml, README, template, doc | test_todo_keeps_the_plan_and_installs_a_runnable_graph
todo | 33-35 | todo-graph.py is mode 755, todo/README.md 644 | test_todo_keeps_the_plan_and_installs_a_runnable_graph
todo | 36-37 | todo-graph.py --help exits 0 from the project | test_todo_keeps_the_plan_and_installs_a_runnable_graph
todo | 39-41 | second install exits 0, every file digest unchanged | test_a_second_install_changes_no_file
todo | 43-46 | dry run exits 0, the folder stays empty | test_a_dry_run_writes_nothing
todo | 48-51 | --force exits non-zero | test_force_is_refused_and_changes_nothing
todo | 53-61 | linked scripts: exits non-zero, outside holds only sentinel | test_a_linked_destination_folder_is_refused
todo | 63 | closing summary line | none
wordpress | 1-12 | script header: shell options, native links, scratch folder | none
wordpress | 13-20 | cleanup of the bytecode planted in the kit | test_wordpress_never_installs_bytecode_left_in_the_kit
wordpress | 22-29 | fixture with wp-load.php and its own AGENTS.md | test_wordpress_keeps_agents_md_and_installs_the_pressable_overlay
wordpress | 31-36 | install exits 0 and copies no __pycache__ from the kit | test_wordpress_never_installs_bytecode_left_in_the_kit
wordpress | 38 | AGENTS.md keeps its bytes | test_wordpress_keeps_agents_md_and_installs_the_pressable_overlay
wordpress | 39-48 | doc, phpcs files, 3 safety skills, connect skill, hook, DDEV | test_wordpress_keeps_agents_md_and_installs_the_pressable_overlay
wordpress | 49-50 | the MCP example is JSON; the pin's host is pressable | test_wordpress_keeps_agents_md_and_installs_the_pressable_overlay
wordpress | 51-53 | bin/wp-remote is mode 755, phpcs.xml.dist 644 | test_wordpress_keeps_agents_md_and_installs_the_pressable_overlay
wordpress | 55-61 | doctor: root listed, identity setup_required, strict fails | test_wordpress_doctor_reports_setup_and_strict_exits_3
wordpress | 63-65 | second install exits 0, every file digest unchanged | test_a_second_install_changes_no_file
wordpress | 67-71 | dry run exits 0, phpcs.xml.dist not written | test_a_dry_run_writes_nothing
wordpress | 73-76 | --force exits non-zero | test_force_is_refused_and_changes_nothing
wordpress | 78-81 | --host kinsta exits non-zero | test_wordpress_refuses_an_unknown_host
wordpress | 83-94 | wpcom: helper and skill, no DDEV or MCP files, no-ddev ok | test_wordpress_com_site_has_no_mirror_and_keeps_its_host
wordpress | 95-101 | rerun follows the pin; --host pressable exits non-zero | test_wordpress_com_site_has_no_mirror_and_keeps_its_host
wordpress | 103-107 | website/wp-load.php: install exits 0, phpcs.xml.dist lands | test_wordpress_finds_a_nested_website_tree
wordpress | 109-115 | site/wp-load.php: doctor wordpress-root ok ending /site | test_wordpress_doctor_finds_a_first_level_child
wordpress | 117-125 | linked docs: exits non-zero, sentinel unchanged | test_a_linked_destination_folder_is_refused
wordpress | 127 | closing summary line | none
"""
import contextlib
import hashlib
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

SDK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))
import forge  # noqa: E402

# The todo kit's install asks Codex's app-server to approve its Stop hook; tests answer from a stub, never the
# machine's real Codex (as tests/test_forge.py does).
os.environ["CODEX_HOOK_TRUST_SERVER"] = json.dumps([sys.executable, str(SDK_ROOT / "tests/fixtures/codex_app_server_stub.py")])

BASH_KITS = ("automations", "base", "laravel", "reviewer", "todo", "wordpress")
# The file a project of that stack already has, and the folder each script replaced with a link.
STACK_FILE = {"laravel": "artisan", "wordpress": "wp-load.php"}
# The WordPress script's dry run stood on a root known only by its wp-config.php: that input stays accepted.
DRY_STACK_FILE = {"laravel": "artisan", "wordpress": "wp-config.php"}
# What the scripts required by name, written here and never read from forge: a constant changed there must not
# change what these tests expect.
AGENT_DIRS = (".agents", ".claude", ".codex")
TODO_SKILLS = ("add-todo", "create-todo", "groom-plan", "process-phase", "process-plan", "process-todo-file",
               "process-todo-section", "review-todo-section")
LINKED_FOLDER = {"automations": ".conclave", "base": "scripts", "laravel": "scripts", "reviewer": "scripts",
                 "todo": "scripts", "wordpress": "docs"}
TOOL_SECONDS = 120


def provisioned_mode(posix_mode):
    """The mode forge leaves on a file: exact on POSIX. Windows keeps only the read-only flag, so a file forge wrote
    reads back as 0o666 there."""
    return posix_mode if os.name != "nt" else 0o666


def make_link(target, link):
    # A junction on Windows (no rights needed), a symlink elsewhere.
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link)


def tree(root):
    """relative path -> digest of every file under `root`: what `find -type f | sha256sum` gave the scripts."""
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def run_tool(project, *argv):
    """One installed tool, run from the project as the scripts ran it: no shell, no bytecode, a time limit."""
    return subprocess.run([sys.executable, "-B", *argv], cwd=project, capture_output=True, text=True,
                          timeout=TOOL_SECONDS)


def command_line(*argv):
    """`forge.py <argv>` in process: (exit code, stdout, stderr). argparse's own refusals exit through SystemExit."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = forge.main([str(arg) for arg in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def map_rows():
    """The docstring's table as (kit, line numbers, assertion, test)."""
    rows = []
    for line in (__doc__ or "").splitlines():
        cells = [cell.strip() for cell in line.split(" | ")]
        if len(cells) != 4 or cells[0] not in BASH_KITS:
            continue
        first, _, last = cells[1].partition("-")
        rows.append((cells[0], set(range(int(first), int(last or first) + 1)), cells[2], cells[3]))
    return rows


class KitInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Resolved: a runner's temp folder can be an 8.3 short name that forge's own paths spell long.
        self.work = pathlib.Path(self.tmp.name).resolve()

    def project(self, name, kit=None, stack=STACK_FILE):
        """An empty project folder, holding the file that makes it a project of the kit's stack."""
        project = self.work / name
        project.mkdir()
        if kit in stack:
            (project / stack[kit]).write_bytes(b"<?php\n")
        return project

    def own_file(self, project, rel, data):
        """A file the project already has, written as bytes: the scripts compared digests, so a kept file is
        byte for byte the same, line endings included."""
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def assert_files(self, project, *rels):
        for rel in rels:
            self.assertTrue((project / rel).is_file(), f"{rel} was not installed")

    def assert_mode(self, project, rel, posix_mode):
        self.assertEqual((project / rel).stat().st_mode & 0o777, provisioned_mode(posix_mode), rel)

    def assert_runs(self, project, *argv):
        result = run_tool(project, *argv)
        self.assertEqual(result.returncode, 0, f"{' '.join(argv)}: {result.stderr[-2000:]}")
        return result.stdout

    # automations

    def test_automations_keeps_the_task_list_and_installs_the_rest(self):
        project = self.project("target")
        tasks = project / ".conclave/automations/tasks.json"
        tasks.parent.mkdir(parents=True)
        tasks.write_text('{"schema_version": 1, "folder": "\\\\Demo\\\\", "tasks": []}\n', encoding="utf-8")
        before = tasks.read_bytes()
        res = forge.apply_kit(project, "automations")
        self.assertEqual(tasks.read_bytes(), before)
        self.assertIn(".conclave/automations/tasks.json", res["preserved"])
        self.assert_files(project, *(f"{agent_dir}/skills/scheduled-automations/SKILL.md" for agent_dir in AGENT_DIRS))
        self.assert_files(project, ".codex/skills/scheduled-automations/agents/openai.yaml")
        self.assert_files(project, *(f".conclave/automations/{name}" for name in ("run.py", "alert.py", "install.ps1", "README.md")))
        self.assert_mode(project, ".conclave/automations/install.sh", 0o755)
        self.assertEqual(self.assert_runs(project, ".conclave/automations/run.py", "--check").strip(), "\\Demo\\")

    def test_automations_fresh_install_has_no_folder_yet(self):
        project = self.project("fresh")
        forge.apply_kit(project, "automations")
        tasks = json.loads((project / ".conclave/automations/tasks.json").read_text(encoding="utf-8"))
        self.assertIsNone(tasks["folder"])
        result = run_tool(project, ".conclave/automations/run.py", "--check")
        self.assertNotEqual(result.returncode, 0, "a fresh kit with no folder passed the install check")

    # base

    def test_base_keeps_the_projects_files_and_installs_the_rest(self):
        project = self.project("target")
        own = {"AGENTS.md": b"locally tuned\r\n", ".claude/skills/local-tool-safety/SKILL.md": b"custom skill\n",
               ".codex/settings.toml": b"custom settings\r\n"}
        for rel, data in own.items():
            self.own_file(project, rel, data)
        forge.apply_kit(project, "base")
        for rel, data in own.items():
            self.assertEqual((project / rel).read_bytes(), data, rel)
        self.assert_files(project, *(f"{agent_dir}/skills/authoring-skills/SKILL.md" for agent_dir in AGENT_DIRS))
        self.assert_files(project, "scripts/verify-agent-tiers.mjs")
        # Retired with the native Antigravity orchestrator (D00 T02 section 3): neither may come back.
        self.assertFalse((project / ".agents/agents").exists())
        self.assertFalse((project / "scripts/agy-subagent.py").exists())
        self.assert_mode(project, ".claude/skills/authoring-skills/SKILL.md", 0o644)
        self.assert_mode(project, "scripts/verify-agent-tiers.mjs", 0o755)

    # laravel

    def test_laravel_keeps_agents_md_and_installs_at_the_app_root(self):
        project = self.project("target", "laravel")
        (project / "composer.json").write_text('{"name":"fixture/laravel","require-dev":{}}\n', encoding="utf-8")
        (project / "resources/css").mkdir(parents=True)
        (project / "resources/css/app.css").write_text('@import "tailwindcss";\n', encoding="utf-8")
        self.own_file(project, "AGENTS.md", b"locally tuned\r\n")
        forge.apply_kit(project, "laravel")
        self.assertEqual((project / "AGENTS.md").read_bytes(), b"locally tuned\r\n")
        self.assert_files(project, "scripts/lsp-diagnostics.py", "scripts/hooks/laravel-lsp-pre-push.sh", "boost.json",
                          "docs/laravel-agent-tooling.md", ".mcp.json",
                          *(f"{agent_dir}/skills/laravel-boost/SKILL.md" for agent_dir in AGENT_DIRS))
        self.assert_mode(project, "scripts/hooks/laravel-lsp-pre-push.sh", 0o755)
        self.assert_mode(project, "docs/laravel-agent-tooling.md", 0o644)
        mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp["mcpServers"]["laravel-boost"]["args"], ["artisan", "boost:mcp"])
        self.assert_runs(project, "scripts/lsp-diagnostics.py", "--help")

    def test_laravel_doctor_reports_artisan_and_the_diagnostics_script(self):
        project = self.project("target", "laravel")
        forge.apply_kit(project, "laravel")
        code, out, _err = command_line("doctor", project, "laravel")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["kit"], "laravel")
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(checks["artisan"]["status"], "ok")
        self.assertEqual(checks["artisan"]["detail"], (project / "artisan").as_posix())
        self.assertEqual(checks["lsp-diagnostics.py"]["status"], "ok")
        (project / "scripts/lsp-diagnostics.py").unlink()
        checks = {check["name"]: check["status"] for check in forge.doctor_repo(project, "laravel")["checks"]}
        self.assertEqual(checks["lsp-diagnostics.py"], "missing")

    LARAVEL_CHECKS = {"artisan", "lsp-diagnostics.py", "boost.json", "laravel/boost", "laravel-lsp",
                      "tailwindcss-language-server", "intelephense", "skill:.agents", "skill:.claude", "skill:.codex"}
    BOOST_HINT = "composer require --dev laravel/boost (dependency approval)"

    def boost_check(self, project):
        """The `laravel/boost` check of the Laravel doctor, after proving the report still holds every check the
        retired `kits/laravel/scripts/doctor.sh` reported."""
        checks = {check["name"]: check for check in forge.doctor_repo(project, "laravel")["checks"]}
        self.assertEqual(set(checks), self.LARAVEL_CHECKS)
        return checks["laravel/boost"]["status"], checks["laravel/boost"]["detail"]

    def test_laravel_doctor_reports_the_boost_package_composer_installed(self):
        # `composer show laravel/boost` reads vendor/composer/installed.json; the doctor reads the same file itself.
        project = self.project("target", "laravel")
        installed = self.own_file(project, "vendor/composer/installed.json", json.dumps(
            {"packages": [{"name": "laravel/framework"}, {"name": "laravel/boost", "version": "v1.0.0"}]}).encode())
        self.assertEqual(self.boost_check(project), ("ok", installed.as_posix()))
        # Composer 1 wrote the package list as the document itself.
        installed.write_text(json.dumps([{"name": "laravel/boost"}]), encoding="utf-8")
        self.assertEqual(self.boost_check(project)[0], "ok")
        # A package composer.json requires and nobody installed is not present.
        installed.unlink()
        self.own_file(project, "composer.json", b'{"require-dev": {"laravel/boost": "^1.0"}}')
        self.assertEqual(self.boost_check(project), ("setup_required", self.BOOST_HINT))

    def test_laravel_doctor_reads_the_boost_package_at_the_app_root(self):
        project = self.project("nested")
        self.own_file(project, "platform/artisan", b"<?php\n")
        self.assertEqual(self.boost_check(project), ("setup_required", self.BOOST_HINT))
        # At the repository root the file is not the app's: only the one beside artisan counts.
        self.own_file(project, "vendor/composer/installed.json", b'{"packages": [{"name": "laravel/boost"}]}')
        self.assertEqual(self.boost_check(project), ("setup_required", self.BOOST_HINT))
        installed = self.own_file(project, "platform/vendor/composer/installed.json",
                                  b'{"packages": [{"name": "laravel/boost"}]}')
        self.assertEqual(self.boost_check(project), ("ok", installed.as_posix()))

    def test_laravel_doctor_asks_for_boost_when_composer_does_not_list_it(self):
        project = self.project("target", "laravel")
        absent = ("setup_required", self.BOOST_HINT)
        self.assertEqual(self.boost_check(project), absent)  # no vendor folder at all
        installed = self.own_file(project, "vendor/composer/installed.json",
                                  b'{"packages": [{"name": "laravel/framework"}, {"name": "laravel/boost-extras"}]}')
        self.assertEqual(self.boost_check(project), absent)  # a valid list of other packages
        for data in (b"not json", b"\xff\xfe", b'"laravel/boost"', b'{"packages": "laravel/boost"}',
                     b'{"packages": ["laravel/boost", 7, null]}', b"[[[" * 20000):
            with self.subTest(data=data[:24]):
                installed.write_bytes(data)
                self.assertEqual(self.boost_check(project), absent)
        installed.write_bytes(b'{"packages": [{"name": "laravel/boost"}]}')
        with unittest.mock.patch.object(pathlib.Path, "read_text", side_effect=PermissionError("locked")):
            self.assertEqual(self.boost_check(project), absent)  # a file that cannot be read; the report goes on
        self.assertEqual(self.boost_check(project)[0], "ok")
        # With no artisan there is no app root to read.
        empty = self.project("empty")
        self.own_file(empty, "vendor/composer/installed.json", b'{"packages": [{"name": "laravel/boost"}]}')
        self.assertEqual(self.boost_check(empty), absent)

    def test_doctor_refuses_a_target_that_is_not_a_folder(self):
        # Both retired doctor scripts exited 2 on such a target; a report of nine missing checks would hide the typo.
        a_file = self.own_file(self.work, "a-file", b"x")
        for target in (self.work / "missing", a_file):
            for extra in ((), ("laravel",), ("wordpress", "--strict")):
                with self.subTest(target=target.name, extra=extra):
                    code, out, err = command_line("doctor", target, *extra)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")
                    self.assertEqual(err, f"doctor: not a directory: {target}\n")

    def test_laravel_refuses_a_project_with_no_artisan(self):
        project = self.project("empty")
        with self.assertRaisesRegex(ValueError, "No artisan"):
            forge.apply_kit(project, "laravel")
        code, _out, err = command_line("kit", project, "laravel")
        self.assertEqual(code, 2)
        self.assertIn("No artisan", err)
        self.assertEqual(tree(project), {})

    def test_laravel_finds_a_nested_platform_app(self):
        project = self.project("nested")
        (project / "platform/resources/css").mkdir(parents=True)
        (project / "platform/artisan").write_text("<?php\n", encoding="utf-8")
        (project / "platform/composer.json").write_text('{"name":"fixture/nested"}\n', encoding="utf-8")
        forge.apply_kit(project, "laravel")
        self.assert_files(project, "scripts/lsp-diagnostics.py", "platform/boost.json")
        mcp = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp["mcpServers"]["laravel-boost"]["args"][0], "platform/artisan")

    # reviewer

    def test_reviewer_keeps_the_pin_and_installs_runnable_tools(self):
        project = self.project("target")
        pin = self.own_file(project, ".conclave/reviewers.toml", b"schema_version = 1\r\n# tuned locally\r\n")
        forge.apply_kit(project, "reviewer")
        self.assertEqual(pin.read_bytes(), b"schema_version = 1\r\n# tuned locally\r\n")
        self.assert_files(project, *(f"{agent_dir}/skills/independent-review/SKILL.md" for agent_dir in AGENT_DIRS))
        self.assert_files(project, ".codex/skills/independent-review/agents/openai.yaml")
        self.assert_files(project, *(f"docs/{prompt}-prompt.md" for prompt in (
            "plan-review", "review-round", "completion-review", "reconciliation-review")))
        self.assert_mode(project, "scripts/review-dispatch.py", 0o755)
        self.assert_runs(project, "scripts/review-dispatch.py", "--help")
        # The dispatcher loads the pin's rules from review_pin.py beside it, and the prompt filler fills the
        # templates in docs/: both land, each with its own tests.
        self.assert_files(project, "scripts/review_pin.py", "scripts/tests/test_review_pin.py",
                          "scripts/review-prompt.py", "scripts/tests/test_review_prompt.py")
        self.assert_runs(project, "scripts/review-prompt.py", "--help")

    def test_reviewer_fresh_pin_passes_its_checks_and_is_three_pass(self):
        project = self.project("fresh")
        forge.apply_kit(project, "reviewer")
        self.assert_runs(project, "scripts/review_pin.py", "--check")
        self.assert_runs(project, "scripts/review-dispatch.py", "--check-pin")
        pin = (project / ".conclave/reviewers.toml").read_text(encoding="utf-8").splitlines()
        # A new install starts on three-pass and routes the two writers to Astra.
        for line in ('model = "gpt-6-astra"', 'claude = ["astra"]', 'agy = ["astra"]',
                     'policy = "three-pass"'):
            self.assertIn(line, pin)
        # Codex only reviews (no writer route, no Carbon reviewer), no route under Antigravity's other name,
        # and no Claude model reviews (Claude writes and never reviews).
        self.assertEqual([line for line in pin if line.startswith(("gemini = ", "codex = ", "[reviewers.carbon]"))
                          or "sonnet" in line], [])
        self.assertIn("pass_cap 33", self.assert_runs(project, "scripts/review_pin.py", "--caps").splitlines())
        lenses = self.assert_runs(project, "scripts/review_pin.py", "--lenses", "completion").splitlines()
        self.assertTrue(any(line.startswith("plan-delivery: ") for line in lenses), lenses)

    # todo

    def test_todo_keeps_the_plan_and_installs_a_runnable_graph(self):
        project = self.project("target")
        index = self.own_file(project, "todo/TODO-00-INDEX.md", b"project plan index\r\n")
        forge.apply_kit(project, "todo")
        self.assertEqual(index.read_bytes(), b"project plan index\r\n")
        self.assert_files(project, *(f"{agent_dir}/skills/{skill}/SKILL.md"
                                     for agent_dir in AGENT_DIRS for skill in TODO_SKILLS))
        self.assert_files(project, ".codex/skills/add-todo/agents/openai.yaml", "todo/README.md",
                          "todo/templates/TODO-template.md", "docs/todo-workflow.md")
        self.assert_mode(project, "scripts/todo-graph.py", 0o755)
        self.assert_mode(project, "todo/README.md", 0o644)
        self.assert_runs(project, "scripts/todo-graph.py", "--help")

    # wordpress

    def test_wordpress_never_installs_bytecode_left_in_the_kit(self):
        # Bytecode from running the kit's own tests is planted in a scratch copy of the kits, never in the checkout.
        scratch = self.work / "sdk"
        shutil.copytree(forge.FORGE_ROOT / "kits", scratch / "kits", ignore=shutil.ignore_patterns("__pycache__"))
        cache = scratch / "kits/wordpress/templates/scripts/lib/__pycache__"
        cache.mkdir()
        (cache / "stray.pyc").write_bytes(b"\x00")
        project = self.project("target", "wordpress")
        with unittest.mock.patch.object(forge, "FORGE_ROOT", scratch):
            res = forge.apply_kit(project, "wordpress")
        self.assert_files(project, "scripts/lib/wp_site.py")
        self.assertFalse((project / "scripts/lib/__pycache__").exists())
        self.assertEqual([rel for rel in res["installed"] if "__pycache__" in rel or rel.endswith(".pyc")], [])

    def test_wordpress_keeps_agents_md_and_installs_the_pressable_overlay(self):
        project = self.project("target", "wordpress")
        self.own_file(project, "AGENTS.md", b"locally tuned\r\n")
        forge.apply_kit(project, "wordpress")
        self.assertEqual((project / "AGENTS.md").read_bytes(), b"locally tuned\r\n")
        self.assert_files(project, "docs/wordpress-agent-tooling.md", "phpcs.xml.dist", "tools/phpcs/composer.json",
                          "mcp.wordpress.example.json", "scripts/hooks/wordpress-phpcs-pre-push.sh",
                          ".agents/skills/wordpress-connect/SKILL.md", ".ddev/providers/production.yaml",
                          *(f"{agent_dir}/skills/wordpress-site-safety/SKILL.md" for agent_dir in AGENT_DIRS))
        json.loads((project / "mcp.wordpress.example.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((project / ".conclave/wordpress-site.json").read_text(encoding="utf-8"))["host"], "pressable")
        self.assert_mode(project, "bin/wp-remote", 0o755)
        self.assert_mode(project, "phpcs.xml.dist", 0o644)

    def test_wordpress_doctor_reports_setup_and_strict_exits_3(self):
        project = self.project("target", "wordpress")
        forge.apply_kit(project, "wordpress")
        code, out, _err = command_line("doctor", project, "wordpress")
        self.assertEqual(code, 0)
        checks = {check["name"]: check["status"] for check in json.loads(out)["checks"]}
        self.assertIn("wordpress-root", checks)
        self.assertEqual(checks["site-identity"], "setup_required")
        code, _out, _err = command_line("doctor", project, "wordpress", "--strict")
        self.assertEqual(code, 3, "strict doctor passed with setup still required")

    def test_wordpress_refuses_an_unknown_host(self):
        project = self.project("target", "wordpress")
        forge.apply_kit(project, "wordpress")
        before = tree(project)
        with self.assertRaisesRegex(ValueError, "Unknown WordPress host 'kinsta'"):
            forge.apply_kit(project, "wordpress", host="kinsta")
        code, _out, err = command_line("kit", project, "wordpress", "--host", "kinsta")
        self.assertEqual(code, 2)
        self.assertIn("kinsta", err)
        self.assertEqual(tree(project), before)

    def test_wordpress_com_site_has_no_mirror_and_keeps_its_host(self):
        # A WordPress.com site has no local tree, no DDEV and no project MCP servers.
        project = self.project("wpcom")
        forge.apply_kit(project, "wordpress", host="wpcom")
        self.assert_files(project, "bin/wp-remote", ".claude/skills/wordpress-connect/SKILL.md")
        for rel in (".ddev", "mcp.wordpress.example.json", "scripts/mcp-headers.py"):
            self.assertFalse((project / rel).exists(), rel)
        self.assertEqual(json.loads((project / ".conclave/wordpress-site.json").read_text(encoding="utf-8"))["host"], "wpcom")
        checks = {check["name"]: check["status"] for check in forge.doctor_repo(project, "wordpress")["checks"]}
        self.assertEqual(checks["no-ddev"], "ok")
        # Re-running without a host follows the pin; a conflicting host is refused.
        before = tree(project)
        res = forge.apply_kit(project, "wordpress")
        self.assertEqual(res["host"], "wpcom")
        self.assertFalse((project / ".ddev").exists())
        with self.assertRaisesRegex(ValueError, "pins host 'wpcom'"):
            forge.apply_kit(project, "wordpress", host="pressable")
        code, _out, _err = command_line("kit", project, "wordpress", "--host", "pressable")
        self.assertEqual(code, 2)
        self.assertEqual(tree(project), before)

    def test_wordpress_finds_a_nested_website_tree(self):
        project = self.project("nested")
        (project / "website").mkdir()
        (project / "website/wp-load.php").write_text("<?php\n", encoding="utf-8")
        res = forge.apply_kit(project, "wordpress")
        self.assertEqual(res["wordpress"], "website")
        self.assert_files(project, "phpcs.xml.dist")

    def test_wordpress_doctor_finds_a_first_level_child(self):
        # The doctor finds the same first-level child the install accepts.
        project = self.project("child")
        (project / "site").mkdir()
        (project / "site/wp-load.php").write_text("<?php\n", encoding="utf-8")
        res = forge.apply_kit(project, "wordpress")
        self.assertEqual(res["wordpress"], "site")
        checks = {check["name"]: check for check in forge.doctor_repo(project, "wordpress")["checks"]}
        self.assertEqual(checks["wordpress-root"]["status"], "ok")
        self.assertTrue(checks["wordpress-root"]["detail"].endswith("/site"), checks["wordpress-root"]["detail"])

    # every kit: what each script asserted of the installer itself

    def test_a_second_install_changes_no_file(self):
        for kit in BASH_KITS:
            with self.subTest(kit=kit):
                project = self.project(f"again-{kit}", kit)
                first = forge.apply_kit(project, kit)
                self.assertTrue(first["installed"])
                before = tree(project)
                second = forge.apply_kit(project, kit)
                self.assertEqual(second["installed"], [])
                self.assertEqual(tree(project), before)

    def test_a_dry_run_writes_nothing(self):
        for kit in BASH_KITS:
            with self.subTest(kit=kit):
                project = self.project(f"dry-{kit}", kit, DRY_STACK_FILE)
                before = tree(project)
                res = forge.apply_kit(project, kit, dry_run=True)
                self.assertTrue(res["installed"], "a dry run names what it would install")
                self.assertEqual(tree(project), before)
                self.assertEqual(sorted(path.name for path in project.iterdir()), sorted(before))
                code, out, _err = command_line("kit", project, kit, "--dry-run")
                self.assertEqual((code, json.loads(out)["dry_run"]), (0, True))
                self.assertEqual(sorted(path.name for path in project.iterdir()), sorted(before))

    def test_force_is_refused_and_changes_nothing(self):
        # The bash installers once took --force to overwrite; forge.py kit has no such mode.
        for kit in BASH_KITS:
            with self.subTest(kit=kit):
                project = self.project(f"force-{kit}", kit)
                forge.apply_kit(project, kit)
                before = tree(project)
                code, _out, err = command_line("kit", project, kit, "--force")
                self.assertEqual(code, 2)
                self.assertIn("--force", err)
                self.assertEqual(tree(project), before)

    def test_a_linked_destination_folder_is_refused(self):
        for kit in BASH_KITS:
            with self.subTest(kit=kit):
                project = self.project(f"link-{kit}", kit)
                outside = self.work / f"outside-{kit}"
                outside.mkdir()
                (outside / "sentinel").write_bytes(b"outside sentinel\n")
                link = project / LINKED_FOLDER[kit]
                make_link(outside, link)
                own = sorted(path.name for path in project.iterdir())
                with self.assertRaises(ValueError):
                    forge.apply_kit(project, kit)
                code, _out, _err = command_line("kit", project, kit)
                self.assertEqual(code, 2)
                # Nothing was written through the link, and nothing beside it either: the refusal comes first.
                self.assertEqual(sorted(path.name for path in outside.iterdir()), ["sentinel"])
                self.assertEqual((outside / "sentinel").read_bytes(), b"outside sentinel\n")
                self.assertEqual(sorted(path.name for path in project.iterdir()), own)


class KitTemplateRemovalTests(unittest.TestCase):
    """Each kit's install test fails when a template file it names is gone from the kit: the tests read the kit as it
    is, not a list of their own. Run on a scratch copy of `kits/`, with a control run that must pass first."""

    REMOVALS = {
        "automations": (".conclave/automations/run.py", "test_automations_keeps_the_task_list_and_installs_the_rest"),
        "base": ("scripts/verify-agent-tiers.mjs", "test_base_keeps_the_projects_files_and_installs_the_rest"),
        "laravel": ("scripts/lsp-diagnostics.py", "test_laravel_keeps_agents_md_and_installs_at_the_app_root"),
        "reviewer": ("scripts/review_pin.py", "test_reviewer_keeps_the_pin_and_installs_runnable_tools"),
        "todo": ("todo/templates/TODO-template.md", "test_todo_keeps_the_plan_and_installs_a_runnable_graph"),
        "wordpress": ("phpcs.xml.dist", "test_wordpress_keeps_agents_md_and_installs_the_pressable_overlay"),
    }

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.scratch = pathlib.Path(cls.tmp.name).resolve()
        shutil.copytree(SDK_ROOT / "kits", cls.scratch / "kits", ignore=shutil.ignore_patterns("__pycache__"))

    @staticmethod
    def outcome(name):
        result = unittest.TestResult()
        KitInstallTests(name).run(result)
        return result

    def test_every_bash_kit_has_a_removal(self):
        self.assertEqual(sorted(self.REMOVALS), sorted(BASH_KITS))

    def test_each_install_test_fails_when_its_template_file_is_removed(self):
        held = self.scratch / "held"
        held.mkdir()
        with unittest.mock.patch.object(forge, "FORGE_ROOT", self.scratch):
            for kit, (rel, name) in self.REMOVALS.items():
                with self.subTest(kit=kit):
                    control = self.outcome(name)
                    self.assertTrue(control.wasSuccessful(), control.failures + control.errors)
                    template = self.scratch / "kits" / kit / "templates" / rel
                    shutil.move(template, held / kit)
                    try:
                        removed = self.outcome(name)
                    finally:
                        shutil.move(held / kit, template)
                    self.assertEqual(removed.testsRun, 1)
                    self.assertFalse(removed.wasSuccessful(), f"{name} passed with {rel} gone from the {kit} kit")


class AssertionMapTests(unittest.TestCase):
    def test_the_map_has_rows_for_all_six_kits(self):
        self.assertEqual(sorted({kit for kit, _lines, _what, _test in map_rows()}), sorted(BASH_KITS))

    def test_every_row_names_a_test_this_file_defines(self):
        for kit, lines, what, test in map_rows():
            with self.subTest(kit=kit, lines=sorted(lines)[0]):
                self.assertTrue(what)
                if test != "none":
                    self.assertTrue(callable(getattr(KitInstallTests, test, None)), f"{test} is not a test of this file")

    def test_no_line_is_in_two_rows(self):
        for kit in BASH_KITS:
            seen = set()
            for row_kit, lines, _what, _test in map_rows():
                if row_kit == kit:
                    self.assertFalse(seen & lines, f"{kit}: lines {sorted(seen & lines)} are in two rows")
                    seen |= lines


if __name__ == "__main__":
    unittest.main()
