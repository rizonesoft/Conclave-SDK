"""The `lsp` kit as `forge.py` knows it: install, record, detection and doctor (D04 T01 section 1).

The kit's own scripts are tested in the kit, under `kits/lsp/templates/scripts/tests/`.
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock

SDK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))
import forge  # noqa: E402

SERVER = {"name": "stub-ls", "command": ["stub-ls", "--stdio"], "extensions": {".py": "python"},
          "install": "install stub-ls by hand"}

TABLE = ".conclave/lsp.json"


def command_line(*argv):
    """`forge.py <argv>` in process: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = forge.main([str(arg) for arg in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def kit_files(root=SDK_ROOT):
    """Every file the kit installs, as the project sees it."""
    templates = root / "kits/lsp/templates"
    return sorted(path.relative_to(templates).as_posix() for path in templates.rglob("*")
                  if path.is_file() and "__pycache__" not in path.parts)


class LspKitTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = pathlib.Path(tmp.name).resolve()

    def project(self, name="project"):
        folder = self.work / name
        folder.mkdir()
        return folder

    def snapshot(self, folder):
        return {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()}

    def checks(self, report):
        return {check["name"]: check for check in report["checks"]}

    def test_the_kit_is_listed_and_seeds_an_empty_server_table(self):
        self.assertIn("lsp", forge.list_kits())
        self.assertLess(forge.KIT_ORDER.index("lsp"), forge.KIT_ORDER.index("laravel"))
        code, out, _err = command_line("kits")
        self.assertEqual(code, 0)
        self.assertIn("lsp", json.loads(out)["kits"])
        seed = (SDK_ROOT / "kits/lsp/templates" / TABLE).read_text(encoding="utf-8")
        self.assertEqual(json.loads(seed), {"schema_version": 1, "servers": []})
        self.assertTrue(seed.endswith("\n"))
        self.assertTrue((SDK_ROOT / "kits/lsp/README.md").is_file())

    def test_the_kit_is_named_wherever_forge_lists_its_kits(self):
        # The usage text and the help of each command that takes a kit name.
        (usage,) = [line for line in (forge.__doc__ or "").splitlines() if "forge.py doctor" in line]
        self.assertIn("|lsp|", usage.replace("[", "|").replace("]", "|"))
        for kit in forge.KIT_ORDER:  # every kit on that one line, which a test of the unattended kit reads too
            self.assertIn(kit, usage, "the doctor usage line omits a kit")
        for command in ("init", "kit"):
            code, out, _err = command_line(command, "--help")
            self.assertEqual(code, 0)
            self.assertIn("lsp", out, command)
        self.assertIn("'lsp'", forge.apply_kit.__doc__ or "")

    def test_init_and_kit_install_the_table_and_record_it(self):
        for name, argv in (("by-init", ("init", "{project}", "--kit", "lsp")), ("by-kit", ("kit", "{project}", "lsp"))):
            with self.subTest(command=argv[0]):
                project = self.project(name)
                code, _out, err = command_line(*(str(project) if arg == "{project}" else arg for arg in argv))
                self.assertEqual(code, 0, err)
                self.assertEqual(json.loads((project / TABLE).read_text(encoding="utf-8")),
                                 {"schema_version": 1, "servers": []})
                record = json.loads((project / forge.RECORD).read_text(encoding="utf-8"))
                self.assertIn("lsp", record["kits"])
                self.assertEqual(record["files"][TABLE]["kit"], "lsp")

    def test_a_second_install_changes_nothing_and_a_projects_own_table_is_kept(self):
        project = self.project()
        first = forge.apply_kit(project, "lsp")
        self.assertEqual(first["installed"], kit_files())
        before = self.snapshot(project)
        second = forge.apply_kit(project, "lsp")
        self.assertEqual((second["installed"], second["preserved"]), ([], kit_files()))
        self.assertEqual(self.snapshot(project), before)
        owned = self.project("owned")
        own = b'{"schema_version": 1, "servers": [{"name": "mine"}]}\r\n'
        (owned / ".conclave").mkdir()
        (owned / TABLE).write_bytes(own)
        result = forge.apply_kit(owned, "lsp")
        self.assertIn(TABLE, result["preserved"])
        self.assertEqual((owned / TABLE).read_bytes(), own)
        dry = self.project("dry")
        self.assertEqual(forge.apply_kit(dry, "lsp", dry_run=True)["installed"], kit_files())
        self.assertEqual(list(dry.iterdir()), [])

    def test_the_kit_is_detected_by_its_table(self):
        project = self.project()
        self.assertNotIn("lsp", forge.check_repo(project)["kits"])
        forge.apply_kit(project, "lsp")
        self.assertIn("lsp", forge.check_repo(project)["kits"])
        # A client alone is not this kit (a Laravel project from before the kit has one).
        alone = self.project("alone")
        (alone / "scripts").mkdir()
        shutil.copyfile(SDK_ROOT / "kits/lsp/templates/scripts/lsp-diagnostics.py",
                        alone / "scripts/lsp-diagnostics.py")
        self.assertNotIn("lsp", forge.check_repo(alone)["kits"])
        # The Laravel kit brings this kit with it (D04 T01 section 4).
        laravel = self.project("laravel")
        (laravel / "artisan").write_bytes(b"<?php\n")
        forge.apply_kit(laravel, "laravel")
        kits = forge.check_repo(laravel)["kits"]
        self.assertIn("laravel", kits)
        self.assertIn("lsp", kits)

    def test_the_doctor_reports_each_file_the_kit_installs(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        code, out, _err = command_line("doctor", project, "lsp", "--strict")
        report = json.loads(out)
        self.assertEqual((code, report["kit"], report["missing_or_setup_required"]), (0, "lsp", 0))
        self.assertEqual({name: check["status"] for name, check in self.checks(report).items()},
                         {**{rel: "ok" for rel in kit_files()}, "server-table": "ok", "mcp-bridge": "optional",
                          "claude-plugin": "optional"})
        self.assertEqual(self.checks(report)[TABLE]["detail"], (project / TABLE).as_posix())
        (project / TABLE).unlink()
        code, out, _err = command_line("doctor", project, "lsp", "--strict")
        self.assertEqual(code, 3)
        self.assertEqual(self.checks(json.loads(out))[TABLE]["status"], "missing")

    def test_the_doctor_reads_the_file_list_from_the_kit(self):
        # A file a later section adds to the kit is checked with no second list to extend.
        scratch = self.work / "sdk"
        shutil.copytree(SDK_ROOT / "kits/lsp", scratch / "kits/lsp")
        added = scratch / "kits/lsp/templates/scripts/added-later.py"
        added.parent.mkdir(parents=True, exist_ok=True)
        added.write_text("print('later')\n", encoding="utf-8")
        project = self.project()
        with unittest.mock.patch.object(forge, "FORGE_ROOT", scratch):
            forge.apply_kit(project, "lsp")
            checks = self.checks(forge.doctor_repo(project, "lsp"))
            self.assertEqual(checks["scripts/added-later.py"]["status"], "ok")
            (project / "scripts/added-later.py").unlink()
            checks = self.checks(forge.doctor_repo(project, "lsp"))
            self.assertEqual(checks["scripts/added-later.py"]["status"], "missing")

    def test_the_bare_doctor_checks_the_kit_when_it_is_installed(self):
        # Found by the plan review of D04 T01 section 1: with no kit named the doctor picked a stack kit or base and
        # never looked at an installed LSP kit.
        project = self.project()
        forge.apply_kit(project, "base")
        code, out, _err = command_line("doctor", project)
        bare = json.loads(out)
        self.assertEqual((code, bare["kit"]), (0, "base"))
        self.assertNotIn("also", bare)
        self.assertNotIn(TABLE, self.checks(bare))
        forge.apply_kit(project, "lsp")
        code, out, _err = command_line("doctor", project)
        report = json.loads(out)
        self.assertEqual((code, report["kit"], report["also"]), (0, "base", ["lsp"]))
        names = [check["name"] for check in report["checks"]]
        self.assertEqual(names[:len(bare["checks"])], [check["name"] for check in bare["checks"]])
        self.assertEqual(names[len(bare["checks"]):], kit_files() + ["server-table", "mcp-bridge", "claude-plugin"])
        self.assertEqual(self.checks(report)[TABLE]["status"], "ok")
        # A named kit is that kit alone, as before.
        named = json.loads(command_line("doctor", project, "base")[1])
        self.assertNotIn("also", named)
        self.assertNotIn(TABLE, self.checks(named))

    def table(self, project, *servers):
        (project / TABLE).write_text(json.dumps({"schema_version": 1, "servers": list(servers)}), encoding="utf-8")

    def stub_on_path(self, name):
        """A program of that name on a PATH that holds nothing else."""
        folder = self.work / "bin"
        folder.mkdir(exist_ok=True)
        launcher = folder / (f"{name}.cmd" if os.name == "nt" else name)
        launcher.write_text("@exit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n", encoding="utf-8")
        launcher.chmod(0o755)
        env = {"PATH": str(folder), **({"PATHEXT": ".CMD"} if os.name == "nt" else {})}
        patch = unittest.mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        return launcher

    def test_the_doctor_says_the_empty_table_holds_no_server_and_how_to_add_one(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        check = self.checks(forge.doctor_repo(project, "lsp"))["server-table"]
        self.assertEqual(check["status"], "ok")
        self.assertIn("holds no server yet", check["detail"])
        self.assertIn("python scripts/lsp-servers.py add <preset>", check["detail"])

    def test_the_doctor_reports_each_server_installed_or_with_its_install_hint(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        launcher = self.stub_on_path("stub-ls")
        self.table(project, SERVER, dict(SERVER, name="absent-ls", command=["absent-ls"],
                                         install="npm install -g absent-ls"))
        for report in (forge.doctor_repo(project, "lsp"), forge.doctor_repo(project)):  # named, and the bare form
            checks = self.checks(report)
            self.assertEqual(checks["server-table"], {"name": "server-table", "status": "ok",
                                                      "detail": f"{TABLE}: stub-ls, absent-ls"})
            self.assertEqual(checks["server:stub-ls"]["status"], "ok")
            self.assertTrue(os.path.samefile(checks["server:stub-ls"]["detail"], launcher))
            self.assertEqual(checks["server:absent-ls"], {"name": "server:absent-ls", "status": "setup_required",
                                                          "detail": "npm install -g absent-ls"})
        code, _out, _err = command_line("doctor", project, "lsp", "--strict")
        self.assertEqual(code, 3)

    def test_a_server_named_by_a_path_is_looked_for_in_the_folder_it_runs_in(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        self.stub_on_path("unrelated")
        local = dict(SERVER, name="local-ls", command=["vendor/bin/local-ls"], root="app")
        self.table(project, local)
        self.assertEqual(self.checks(forge.doctor_repo(project, "lsp"))["server:local-ls"]["status"], "setup_required")
        # The same path under the working directory is not the project's: the doctor reads the server's own folder.
        held, elsewhere = os.getcwd(), self.work / "elsewhere"
        for base in (elsewhere, project / "app"):
            (base / "vendor/bin").mkdir(parents=True)
        program = "local-ls.cmd" if os.name == "nt" else "local-ls"
        body = "@exit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n"
        (elsewhere / "vendor/bin" / program).write_text(body, encoding="utf-8")
        (elsewhere / "vendor/bin" / program).chmod(0o755)
        os.chdir(elsewhere)
        try:
            self.assertEqual(self.checks(forge.doctor_repo(project, "lsp"))["server:local-ls"]["status"],
                             "setup_required")
            local = project / "app/vendor/bin" / program
            local.write_text(body, encoding="utf-8")
            local.chmod(0o644)
            if os.name != "nt":  # a file the system will not execute is not an installed server
                self.assertEqual(self.checks(forge.doctor_repo(project, "lsp"))["server:local-ls"]["status"],
                                 "setup_required")
            local.chmod(0o755)
            check = self.checks(forge.doctor_repo(project, "lsp"))["server:local-ls"]
        finally:
            os.chdir(held)
        self.assertEqual(check["status"], "ok")
        self.assertTrue(os.path.samefile(check["detail"], local), check["detail"])

    def test_a_table_that_does_not_load_is_reported_with_the_refusal_and_no_server_check(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        self.table(project, dict(SERVER, command="stub-ls --stdio"))
        report = forge.doctor_repo(project, "lsp")
        checks = self.checks(report)
        self.assertEqual(checks["server-table"]["status"], "missing")
        self.assertIn(".conclave/lsp.json: server 'stub-ls': command:", checks["server-table"]["detail"])
        self.assertEqual([name for name in checks if name.startswith("server:")], [])
        self.assertEqual(report["missing_or_setup_required"], 1)

    def test_the_kits_diagnostics_client_does_not_make_a_project_a_laravel_project(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        self.assertTrue((project / "scripts/lsp-diagnostics.py").is_file())
        self.assertNotIn("laravel", forge.check_repo(project)["kits"])
        laravel = self.project("laravel")
        (laravel / "artisan").write_bytes(b"<?php\n")
        forge.apply_kit(laravel, "laravel")
        self.assertIn("laravel", forge.check_repo(laravel)["kits"])
        # Detected by a file only that kit installs, also without its skills.
        for agent in (".agents", ".claude", ".codex"):
            shutil.rmtree(laravel / agent / "skills" / "laravel-boost")
        self.assertIn("laravel", forge.check_repo(laravel)["kits"])

    def test_the_readme_names_every_key_every_preset_and_every_file(self):
        readme = (SDK_ROOT / "kits/lsp/README.md").read_text(encoding="utf-8")
        table = forge._lsp_table_module()
        for key in ("name", *table.REQUIRED, *table.DEFAULTS):
            self.assertIn(f"`{key}`", readme, f"the README does not describe the table key {key}")
        for preset in table.load_presets()["presets"]:
            self.assertIn(f"`{preset}`", readme, f"the README does not name the preset {preset}")
        for rel in kit_files():
            self.assertIn(f"`{rel}`", readme, f"the README does not list {rel}")
        for command in ("lsp-servers.py list", "lsp-servers.py add", "lsp-servers.py remove",
                        "lsp-diagnostics.py --all --staged", "lsp-diagnostics.py --server"):
            self.assertIn(command, readme)
        for result in ("ok", "idle", "missing", "skipped", "failed", "partial"):
            self.assertIn(f"| `{result}` |", readme, f"the README does not describe the result {result}")
        self.assertIn("`${scratch}`", readme)
        # The Claude Code plugin (section 5): its folder, the command, how it is loaded and where that is said.
        plugin = forge._lsp_plugin_module()
        for word in (f"`{plugin.FOLDER}/`", "lsp-servers.py plugin", f"`{plugin.LOAD}`", "`CLAUDE_CODE_PLUGIN_DIRS`",
                     "`claude-plugin`", "`unexpected`", "`optional`", "claude --help", "`.lsp.json`",
                     "code.claude.com/docs/en/plugins/"):
            self.assertIn(word, readme)
        self.assertRegex(readme, r"Claude Code 2\.\d+\.\d+")

    def test_the_bare_doctor_adds_the_kit_to_a_stack_kits_checks(self):
        project = self.project()
        forge.apply_kit(project, "wordpress")
        forge.apply_kit(project, "lsp")
        report = forge.doctor_repo(project)
        self.assertEqual((report["kit"], report["also"]), ("wordpress", ["lsp"]))
        self.assertEqual(self.checks(report)[TABLE]["status"], "ok")
        # The Laravel kit runs this kit's checks in its own branch, so they are listed once and not under `also`.
        laravel = self.project("laravel")
        (laravel / "artisan").write_bytes(b"<?php\n")
        forge.apply_kit(laravel, "laravel")
        report = forge.doctor_repo(laravel)
        self.assertEqual(report["kit"], "laravel")
        self.assertNotIn("also", report)
        names = [check["name"] for check in report["checks"]]
        self.assertEqual((names.count(TABLE), names.count("server-table"), names.count("artisan")), (1, 1, 1))

    def test_a_failing_appended_check_is_counted_and_fails_strict(self):
        # Found by the round of D04 T01 section 1: the count must include the checks the bare form appends. The kit
        # is detected by its table, so the failing check is a second kit file, from a scratch copy of the kit.
        scratch = self.work / "sdk"
        shutil.copytree(SDK_ROOT / "kits", scratch / "kits", ignore=shutil.ignore_patterns("__pycache__"))
        added = scratch / "kits/lsp/templates/scripts/added-later.py"
        added.parent.mkdir(parents=True, exist_ok=True)
        added.write_text("print('later')\n", encoding="utf-8")
        project = self.project()
        with unittest.mock.patch.object(forge, "FORGE_ROOT", scratch):
            forge.apply_kit(project, "base")
            forge.apply_kit(project, "lsp")
            clean = forge.doctor_repo(project)
            self.assertEqual(command_line("doctor", project, "--strict")[0], 0)
            (project / "scripts/added-later.py").unlink()
            report = forge.doctor_repo(project)
            self.assertEqual(report["also"], ["lsp"])
            self.assertEqual(self.checks(report)["scripts/added-later.py"]["status"], "missing")
            self.assertEqual(report["missing_or_setup_required"], clean["missing_or_setup_required"] + 1)
            self.assertEqual(command_line("doctor", project, "--strict")[0], 3)


# The stub language server of the live proof: it publishes one diagnostic carrying the marker it is given and
# logs what Claude Code sends it.
LIVE_STUB = r'''
import json, os, sys

marker, log = sys.argv[1], sys.argv[2]


def note(text):
    with open(log, "a", encoding="utf-8") as out:
        out.write(text + "\n")


note("cwd " + os.getcwd())


def send(message):
    body = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    sys.stdout.buffer.flush()


note("started")
while True:
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            sys.exit(0)
        line = line.strip()
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    message = json.loads(sys.stdin.buffer.read(length))
    method = message.get("method")
    if method == "initialize":
        note("root " + str(message["params"].get("rootUri")))
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"capabilities": {"textDocumentSync": 1}}})
    elif method in ("textDocument/didOpen", "textDocument/didChange"):
        uri = message["params"]["textDocument"]["uri"]
        note("document " + uri)
        send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics", "params": {"uri": uri, "diagnostics": [
            {"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}}, "severity": 1,
             "source": "stub", "message": "planted diagnostic " + marker}]}})
    elif method == "shutdown":
        send({"jsonrpc": "2.0", "id": message["id"], "result": None})
    elif method == "exit":
        sys.exit(0)
    elif "id" in message and method:
        send({"jsonrpc": "2.0", "id": message["id"], "result": None})
'''


def run_claude(argv, cwd, env=None, timeout=180):
    """Run Claude Code and end its whole process tree on every way out (the timeout, an interrupt, a normal
    end): (exit code, stdout, stderr). A session starts language servers and, on Windows, runs under a shell,
    so stopping only the process started would leave the rest running."""
    windows = os.name == "nt"
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", shell=windows,
                            start_new_session=not windows,
                            creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
                            if windows else 0)
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out, err
    finally:
        if windows:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass   # the session ended and took its tree with it
        try:
            proc.communicate(timeout=30)
        except (subprocess.TimeoutExpired, ValueError):
            proc.kill()


class ClaudePluginTests(unittest.TestCase):
    """D04 T01 section 5: the doctor's `claude-plugin` check, the plugin following a stack kit's install, and the
    plugin held against Claude Code itself."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = pathlib.Path(tmp.name).resolve()
        self.plugin = forge._lsp_plugin_module()
        self.table = forge._lsp_table_module()

    def project(self, name="project", claude=True):
        folder = self.work / name
        folder.mkdir()
        # Installed for Claude Code (its skill makes the .claude folder), or for Codex alone.
        forge.apply_kit(folder, "lsp", agent="claude" if claude else "codex")
        return folder

    def tool(self, project, *argv):
        ran = subprocess.run([sys.executable, "-B", str(project / "scripts/lsp-servers.py"), *argv], cwd=project,
                             capture_output=True, text=True, timeout=120,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(ran.returncode, 0, ran.stderr)
        return ran.stdout

    def check(self, project, kit="lsp"):
        checks = [check for check in forge.doctor_repo(project, kit)["checks"] if check["name"] == "claude-plugin"]
        self.assertEqual(len(checks), 1, "the claude-plugin check is listed once")
        return checks[0]["status"], checks[0]["detail"]

    def listed(self, project):
        return list(json.loads((project / self.plugin.FOLDER / self.plugin.SERVERS).read_text(encoding="utf-8")))

    def test_the_doctor_says_whether_the_plugin_is_in_step_behind_or_never_generated(self):
        command = "python scripts/lsp-servers.py plugin"
        project = self.project()
        self.assertTrue((project / ".claude").is_dir())
        # No server yet: nothing to run, so the plugin is not asked for.
        status, detail = self.check(project)
        self.assertEqual(status, "optional")
        self.assertIn(command, detail)
        self.tool(project, "add", "cpp")
        self.assertEqual(self.check(project)[0], "setup_required")   # a server, a .claude folder, no plugin
        self.assertIn(command, self.check(project)[1])
        self.tool(project, "plugin")
        self.assertEqual(self.check(project), ("ok", ".claude/lsp/conclave-lsp: clangd"))
        # The table edited by hand since: the plugin is behind it.
        document = json.loads((project / TABLE).read_text(encoding="utf-8"))
        document["servers"][0]["command"] = ["clangd-19"]
        (project / TABLE).write_text(json.dumps(document), encoding="utf-8")
        status, detail = self.check(project)
        self.assertEqual(status, "unexpected")
        self.assertEqual(detail, ".claude/lsp/conclave-lsp is not what .conclave/lsp.json gives now: regenerate it with "
                                 + command)
        self.tool(project, "plugin")
        self.assertEqual(self.check(project)[0], "ok")
        # One of its two files gone is behind too, not "never generated".
        (project / self.plugin.FOLDER / self.plugin.MANIFEST).unlink()
        self.assertEqual(self.check(project)[0], "unexpected")
        # A project that does not use Claude Code is not asked for a Claude Code plugin.
        other = self.project("codex-only", claude=False)
        self.assertFalse((other / ".claude").exists())
        self.tool(other, "add", "cpp")
        self.assertEqual(self.check(other)[0], "optional")
        report = forge.doctor_repo(other, "lsp")
        counted = [check["name"] for check in report["checks"] if check["status"] in ("missing", "setup_required")]
        self.assertEqual(report["missing_or_setup_required"], len(counted))   # `optional` is never counted
        self.assertNotIn("claude-plugin", counted)
        # A table that does not load: no plugin check, as no server check.
        (other / TABLE).write_text("{", encoding="utf-8")
        self.assertEqual([c for c in forge.doctor_repo(other, "lsp")["checks"] if c["name"] == "claude-plugin"], [])

    def test_a_stack_kits_install_keeps_a_generated_plugin_in_step_and_makes_none_of_its_own(self):
        project = self.project()
        (project / "artisan").write_bytes(b"<?php\n")
        self.tool(project, "plugin")
        self.assertEqual(self.listed(project), [])
        result = forge.apply_kit(project, "laravel")
        self.assertEqual(self.listed(project), ["laravel-lsp", "intelephense", "tailwindcss"])
        self.assertNotIn("plugin_failed", result["lsp_servers"])
        self.assertEqual(self.check(project, "laravel")[0], "ok")   # the Laravel doctor lists it once too
        # A project without a plugin gets none from the install.
        fresh = self.work / "fresh"
        fresh.mkdir()
        (fresh / "artisan").write_bytes(b"<?php\n")
        forge.apply_kit(fresh, "laravel")
        self.assertFalse((fresh / self.plugin.FOLDER).exists())
        self.assertEqual(self.check(fresh, "laravel")[0], "setup_required")

    def test_an_install_that_cannot_regenerate_the_plugin_keeps_the_table_and_names_the_recovery(self):
        project = self.project()
        (project / "artisan").write_bytes(b"<?php\n")
        self.tool(project, "plugin")
        before = (project / self.plugin.FOLDER / self.plugin.SERVERS).read_bytes()
        real = os.replace

        def replace(source, target):
            if pathlib.Path(target).name == ".lsp.json":
                raise PermissionError(13, "Permission denied")
            return real(source, target)

        module = forge._lsp_plugin_module()
        failing = types.SimpleNamespace(**{name: getattr(os, name) for name in dir(os) if not name.startswith("__")})
        failing.replace = replace
        module.os = failing
        with unittest.mock.patch.object(forge, "_lsp_plugin_module", lambda: module):
            result = forge.apply_kit(project, "laravel")
        self.assertEqual(result["lsp_servers"]["added"], ["laravel-lsp", "intelephense", "tailwindcss"])
        self.assertEqual(result["lsp_servers"]["plugin_failed"],
                         ".claude/lsp/conclave-lsp/.lsp.json: cannot be written (Permission denied)")
        self.assertEqual(result["lsp_servers"]["plugin_retry"], "python scripts/lsp-servers.py plugin")
        self.assertEqual(result["merge_needed"], [".claude/lsp/conclave-lsp/.lsp.json"])
        # Found by the review round: the command line said 0 for this. A caller that reads only the exit code
        # must not take a plugin left behind, or a table that could not be written, for a finished install.
        self.assertTrue(forge._lsp_write_failed(result))
        self.assertTrue(forge._lsp_write_failed({"lsp_servers": {"failed": "x", "retry": "y"}}))
        for fine in ({}, {"lsp_servers": None}, {"lsp_servers": {"added": [], "kept": []}},
                     {"lsp_servers": {"refused": "the table does not load"}}):
            self.assertFalse(forge._lsp_write_failed(fine))
        other = self.project("cli")
        (other / "artisan").write_bytes(b"<?php\n")
        self.tool(other, "plugin")
        with unittest.mock.patch.object(forge, "_lsp_plugin_module", lambda: module):
            code, out, _err = command_line("kit", other, "laravel")
        self.assertEqual(code, 1)
        self.assertIn("plugin_failed", json.loads(out)["lsp_servers"])
        self.assertEqual(command_line("kit", other, "laravel")[0], 0)   # nothing left to write: a success
        fresh = self.work / "init"
        fresh.mkdir()
        (fresh / "artisan").write_bytes(b"<?php\n")
        (fresh / ".claude/lsp/conclave-lsp").mkdir(parents=True)
        (fresh / ".claude/lsp/conclave-lsp/.lsp.json").write_text("{}", encoding="utf-8")
        with unittest.mock.patch.object(forge, "_lsp_plugin_module", lambda: module):
            code, out, _err = command_line("init", fresh, "--kit", "laravel")
        self.assertEqual(code, 1)
        # The table kept its servers; the plugin's list is the earlier one, whole; the doctor says it is behind.
        self.assertEqual(len(self.table.load_servers(project)), 3)
        self.assertEqual((project / self.plugin.FOLDER / self.plugin.SERVERS).read_bytes(), before)
        self.assertEqual(self.check(project)[0], "unexpected")
        self.tool(project, "plugin")   # the recovery the result names
        self.assertEqual(self.listed(project), ["laravel-lsp", "intelephense", "tailwindcss"])
        self.assertEqual(self.check(project)[0], "ok")

    @unittest.skipUnless(shutil.which("claude"), "needs Claude Code on PATH")
    def test_claude_code_accepts_the_generated_plugin(self):
        project = self.project()
        (project / "artisan").write_bytes(b"<?php\n")
        self.tool(project, "add", "laravel")
        self.tool(project, "plugin")
        code, out, err = run_claude(["claude", "plugin", "validate", str(project / self.plugin.FOLDER)], project)
        self.assertEqual(code, 0, out + err)

    @unittest.skipUnless(os.environ.get("CONCLAVE_LIVE_CLAUDE") == "1" and shutil.which("claude"),
                         "starts a real Claude Code session: set CONCLAVE_LIVE_CLAUDE=1 to run it")
    def test_a_claude_code_session_starts_the_plugins_servers_and_is_given_their_diagnostics(self):
        project = self.project()
        (project / "api").mkdir()
        stub = self.work / "stub.py"
        stub.write_text(LIVE_STUB, encoding="utf-8")
        markers = {"alpha": "MARK-ALPHA-41c7", "beta": "MARK-BETA-9e02"}
        files = {"alpha": "notes.alpha", "beta": "api/style.beta"}
        prompt = ("Use the Edit tool to append the line `second line` to the file notes.alpha, then to the file "
                  "api/style.beta. Then reply DONE.")
        for mode in ("--plugin-dir", "CLAUDE_CODE_PLUGIN_DIRS"):
            with self.subTest(loaded_by=mode):
                servers = [{"name": name, "command": [sys.executable, str(stub), markers[name],
                                                      str(self.work / f"{name}-{mode.strip('-')}.log")],
                            "extensions": {f".{name}": "plaintext"}, "install": "none",
                            **({"root": "api"} if name == "beta" else {})} for name in markers]
                (project / TABLE).write_text(json.dumps({"schema_version": 1, "servers": servers}), encoding="utf-8")
                for rel in files.values():
                    (project / rel).write_bytes(b"first line\n")
                self.tool(project, "plugin")
                folder = project / self.plugin.FOLDER
                # The whole event stream, not the model's summary of it: what the session was given is in there,
                # whatever the model then chooses to say.
                argv = ["claude", "-p", prompt, "--model", "haiku", "--permission-mode", "acceptEdits",
                        "--allowedTools", "Edit,Read", "--output-format", "stream-json", "--verbose"]
                env = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
                                      "CLAUDE_PROJECT_DIR")}
                if mode == "--plugin-dir":
                    argv += ["--plugin-dir", str(folder)]
                else:
                    env["CLAUDE_CODE_PLUGIN_DIRS"] = str(folder)
                code, out, err = run_claude(argv, project, env, timeout=420)
                ran = types.SimpleNamespace(returncode=code, stdout=out, stderr=err)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                print(f"\nlive proof, loaded by {mode}:")
                for name, rel in files.items():
                    log = self.work / f"{name}-{mode.strip('-')}.log"
                    text = log.read_text(encoding="utf-8") if log.is_file() else ""
                    uri = (project / rel).resolve().as_uri()
                    back = markers[name] in ran.stdout
                    print(f"  {name}: started={'started' in text} document={uri in text} marker returned={back}")
                    self.assertIn("started", text, f"Claude Code did not start the {name} server")
                    self.assertIn(f"document {uri}", text, f"the {name} server was not given {rel}")
                    self.assertTrue(back, f"the {name} server's diagnostic did not come back: {ran.stdout[:400]}")
                # The server under a root of its own is given that folder as its workspace root and its process is
                # started there, as the kit's README says of this run: both are asserted, by each mechanism.
                beta = (self.work / f"beta-{mode.strip('-')}.log").read_text(encoding="utf-8")
                self.assertIn("root " + (project / "api").resolve().as_uri(), beta)
                started_in = [line[4:] for line in beta.splitlines() if line.startswith("cwd ")]
                self.assertTrue(started_in, "the beta server logged no working directory")
                for folder in started_in:
                    self.assertTrue(os.path.samefile(folder, project / "api"),
                                    f"the rooted server was started in {folder}, not in its root")
                print(f"  beta: workspace root=api, process started in {pathlib.Path(started_in[0]).name}/")
                alpha = (self.work / f"alpha-{mode.strip('-')}.log").read_text(encoding="utf-8")
                for folder in [line[4:] for line in alpha.splitlines() if line.startswith("cwd ")]:
                    self.assertTrue(os.path.samefile(folder, project), f"the alpha server was started in {folder}")


class McpBridgeTests(unittest.TestCase):
    """D04 T01 section 6: the doctor's `mcp-bridge` check, the registration document, and the bridge held against
    the three agents themselves."""

    DOCUMENT = SDK_ROOT / "kits/lsp/templates/docs/language-servers.md"
    BRIDGE = "scripts/lsp-mcp-bridge.py"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = pathlib.Path(tmp.name).resolve()

    def project(self, name="project"):
        folder = self.work / name
        folder.mkdir()
        forge.apply_kit(folder, "lsp")
        return folder

    def check(self, project, kit="lsp"):
        checks = [check for check in forge.doctor_repo(project, kit)["checks"] if check["name"] == "mcp-bridge"]
        self.assertEqual(len(checks), 1, "the mcp-bridge check is listed once")
        return checks[0]["status"], checks[0]["detail"]

    def test_the_doctor_says_whether_the_projects_mcp_file_registers_the_bridge(self):
        project = self.project()
        where = "how to register it for each agent: docs/language-servers.md"
        self.assertTrue((project / self.BRIDGE).is_file())
        self.assertTrue((project / "docs/language-servers.md").is_file())
        self.assertEqual(self.check(project), ("optional", f"no .mcp.json; {where}"))
        mcp = project / ".mcp.json"
        mcp.write_text(json.dumps({"mcpServers": {"laravel-boost": {"command": "php", "args": ["artisan", "boost:mcp"]}}}),
                       encoding="utf-8")
        self.assertEqual(self.check(project), ("optional", f".mcp.json does not register it; {where}"))
        for entry in ({"command": "python", "args": [self.BRIDGE]},
                      {"command": "python3", "args": ["-B", "./" + self.BRIDGE, "--timeout", "30"]},
                      {"command": "py", "args": [str(project / "scripts" / "lsp-mcp-bridge.py")]}):
            with self.subTest(entry=entry):
                mcp.write_text(json.dumps({"mcpServers": {"boost": {"command": "php", "args": []}, "lsp": entry}}),
                               encoding="utf-8")
                self.assertEqual(self.check(project), ("ok", ".mcp.json registers it as lsp"))
        # It is never setup_required, and optional is never counted.
        report = forge.doctor_repo(project, "lsp")
        self.assertEqual(report["missing_or_setup_required"], 0)
        for text in ("{", "[]", '{"mcpServers": "x"}'):
            with self.subTest(text=text):
                mcp.write_text(text, encoding="utf-8")
                status, detail = self.check(project)
                self.assertEqual(status, "unexpected" if text != '{"mcpServers": "x"}' else "optional")
                self.assertIn("docs/language-servers.md", detail)
        # The Laravel doctor runs the same checks, once.
        laravel = self.work / "laravel"
        laravel.mkdir()
        (laravel / "artisan").write_bytes(b"<?php\n")
        forge.apply_kit(laravel, "laravel")
        self.assertEqual(self.check(laravel, "laravel")[0], "optional")   # its .mcp.json holds Boost alone
        # A table that does not load: no bridge check, as no server check.
        (project / TABLE).write_text("{", encoding="utf-8")
        self.assertEqual([c for c in forge.doctor_repo(project, "lsp")["checks"] if c["name"] == "mcp-bridge"], [])

    def test_the_document_gives_each_agents_registration_with_its_version_and_source(self):
        text = self.DOCUMENT.read_text(encoding="utf-8")
        blocks = re.findall(r"```(\w+)\n(.*?)```", text, flags=re.DOTALL)
        # The registrations: every block of the section that registers the bridge. (The line that tries the
        # bridge by hand, in the section before it, names the script too and registers nothing.)
        registering = text.split("## Registering the bridge" + chr(10), 1)[1]
        registrations = [body for _kind, body in re.findall(r"```(\w+)\n(.*?)```", registering, flags=re.DOTALL)
                         if "lsp-mcp-bridge.py" in body]
        self.assertEqual(len(registrations), 5)   # Codex's command and its two tables, Antigravity's, Claude Code's
        for body in registrations:
            self.assertIn(self.BRIDGE, body)
            self.assertIn("conclave-lsp", body)
        self.assertIn("codex mcp add conclave-lsp -- python scripts/lsp-mcp-bridge.py", text)
        self.assertIn("agy mcp add conclave-lsp python scripts/lsp-mcp-bridge.py", text)
        self.assertEqual(json.loads(next(body for kind, body in blocks if kind == "json")),
                         {"mcpServers": {"conclave-lsp": {"command": "python", "args": [self.BRIDGE]}}})
        for agent, version, source in (("Codex", r"Codex 0\.\d+\.\d+", "codex mcp add --help"),
                                       ("Antigravity", r"Antigravity 1\.\d+\.\d+", "agy mcp add --help"),
                                       ("Claude Code", r"Claude Code 2\.\d+\.\d+", "--mcp-config")):
            section = text.split(f"### {agent}\n", 1)[1].split("\n### ", 1)[0]
            self.assertRegex(section, version, f"{agent}'s section names no version")
            self.assertIn(source, section, f"{agent}'s section does not say where its entry was confirmed")
        # The bridge's tools as the document lists them are the ones it offers, and no other.
        bridge = pathlib.Path(SDK_ROOT / "kits/lsp/templates" / self.BRIDGE).read_text(encoding="utf-8")
        tools = re.findall(r'_tool\("(\w+)"', bridge)
        self.assertEqual(tools, ["diagnostics", "definition", "references", "hover"])
        self.assertEqual(re.findall(r"^\| `(\w+)` \|", text, flags=re.MULTILINE), tools)
        for word in ("default_tools_approval_mode", "CONCLAVE_LIVE_AGENTS=1", "read-only", TABLE):
            self.assertIn(word, text)

    @unittest.skipUnless(os.environ.get("CONCLAVE_LIVE_AGENTS") == "1",
                         "starts real agent sessions: set CONCLAVE_LIVE_AGENTS=1 to run it")
    def test_each_agent_finds_the_bridge_calls_its_tool_and_is_given_the_servers_answer(self):
        python = pathlib.Path(sys.executable).as_posix()
        env = {key: value for key, value in os.environ.items()
               if key not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PROJECT_DIR")}
        stub = self.work / "stub.py"
        stub.write_text(LIVE_STUB, encoding="utf-8")
        for agent in ("claude", "codex", "agy"):
            with self.subTest(agent=agent):
                if not shutil.which(agent):
                    self.skipTest(f"{agent} is not on PATH")
                version = run_claude([agent, "--version"], self.work, env)[1].strip().splitlines()[0]
                project = self.project(agent)
                marker, log = f"MARK-BRIDGE-{agent}", self.work / f"{agent}.log"
                servers = [{"name": "alpha", "command": [sys.executable, str(stub), marker, str(log)],
                            "extensions": {".alpha": "plaintext"}, "install": "none", "settle": 1}]
                (project / TABLE).write_text(json.dumps({"schema_version": 1, "servers": servers}), encoding="utf-8")
                (project / "notes.alpha").write_bytes(b"first line\n")
                name = "conclave-lsp"
                registered = None
                if agent == "claude":
                    # The entry of the document, in a file given for this run.
                    config = self.work / "mcp.json"
                    config.write_text(json.dumps({"mcpServers": {name: {"command": python, "args": [self.BRIDGE]}}}),
                                      encoding="utf-8")
                    how = "--mcp-config (the document's .mcp.json entry), for this run"
                    argv = ["claude", "-p", "PROMPT", "--model", "haiku", "--mcp-config", str(config),
                            "--strict-mcp-config", "--allowedTools", f"mcp__{name}__diagnostics",
                            "--output-format", "stream-json", "--verbose"]
                elif agent == "codex":
                    # The table `codex mcp add` writes, given as overrides for this run.
                    how = "the [mcp_servers.conclave-lsp] table with default_tools_approval_mode, by -c for this run"
                    argv = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only",
                            "-c", f'mcp_servers.{name}.command="{python}"',
                            "-c", f'mcp_servers.{name}.args=["{self.BRIDGE}"]',
                            "-c", f'mcp_servers.{name}.default_tools_approval_mode="approve"', "PROMPT"]
                else:
                    # Antigravity has no registration for one run: the document's command, under a name of the
                    # test's own, removed again whatever happens.
                    name = "conclave-lsp-livetest"
                    registered = run_claude(["agy", "mcp", "list"], project, env)[1]
                    self.assertNotIn(name, registered)
                    added = run_claude(["agy", "mcp", "add", name, python, self.BRIDGE], project, env)
                    self.assertEqual(added[0], 0, added[1] + added[2])
                    how = f"agy mcp add {name} (the document's command), removed after the run"
                    argv = ["agy", "--print", "PROMPT", "--dangerously-skip-permissions", "--print-timeout", "240s"]
                prompt = (f"Call the `diagnostics` tool of the MCP server `{name}` with the argument file set to "
                          "notes.alpha, then reply with the tool's result text exactly as it was returned.")
                try:
                    code, out, err = run_claude([prompt if part == "PROMPT" else part for part in argv], project,
                                                env, timeout=420)
                finally:
                    if registered is not None:
                        run_claude(["agy", "mcp", "remove", name], project, env)
                        self.assertEqual(run_claude(["agy", "mcp", "list"], project, env)[1], registered,
                                         "Antigravity's MCP servers are not as they were before the test")
                text = log.read_text(encoding="utf-8") if log.is_file() else ""
                uri = (project / "notes.alpha").resolve().as_uri()
                print(f"\nlive proof through {agent} ({version}); registered by {how}: bridge started the "
                      f"server={'started' in text} document={uri in text} diagnostic returned={marker in out}")
                self.assertEqual(code, 0, err[-600:])
                self.assertIn("started", text, f"{agent} never started the bridge's server")
                self.assertIn(f"document {uri}", text)
                self.assertIn(marker, out, f"the diagnostic did not come back through {agent}: {out[-400:]}")


# A language server for the document and fresh-install tests. Its behaviour is the word in MODE: `clean` publishes
# what the text holds (a diagnostic for each line with `E:`), `refuse` answers initialize with an error, and `half`
# never answers for a file named skip.py.
DOC_STUB = r'''
import json, sys

MODE = "{mode}"


def send(message):
    body = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    sys.stdout.buffer.flush()


while True:
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            sys.exit(0)
        line = line.strip()
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":", 1)[1])
    message = json.loads(sys.stdin.buffer.read(length))
    method = message.get("method")
    if method == "initialize":
        if MODE == "refuse":
            send({{"jsonrpc": "2.0", "id": message["id"], "error": {{"code": -32002, "message": "no workspace here"}}}})
        else:
            send({{"jsonrpc": "2.0", "id": message["id"], "result": {{"capabilities": {{}}}}}})
    elif method == "textDocument/didOpen":
        document = message["params"]["textDocument"]
        if MODE == "half" and document["uri"].endswith("skip.py"):
            continue
        found = [{{"range": {{"start": {{"line": number, "character": 0}}, "end": {{"line": number, "character": 1}}}},
                  "severity": 1, "message": line.split("E:", 1)[1].strip()}}
                 for number, line in enumerate(document["text"].splitlines()) if "E:" in line]
        send({{"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
              "params": {{"uri": document["uri"], "diagnostics": found}}}})
    elif method == "shutdown":
        send({{"jsonrpc": "2.0", "id": message["id"], "result": None}})
    elif method == "exit":
        sys.exit(0)
    elif "id" in message and method:
        send({{"jsonrpc": "2.0", "id": message["id"], "result": None}})
'''

KIT = "kits/lsp/templates"
SKILL = "skills/language-servers/SKILL.md"
# What the skill must tell an agent, whichever agent reads it. Each is a statement of the policy, not a keyword.
POLICY = ("Before calling a change done: check the files the change touched.",
          "To find where a symbol is defined or used: ask a server",
          "Run the servers on the files the change touched, not on the whole project",
          "A diagnostic at or above a server's own threshold fails the check",
          "A `FAILED` or `PARTIAL` server fails the check too",
          "`SKIPPED` is not a pass.",
          "Never edit a file only to silence a diagnostic")


def kit_script(name, root=None):
    """A script of the kit, loaded as a module (its own parser and all)."""
    path = (root or forge.FORGE_ROOT) / KIT / "scripts" / name
    spec = importlib.util.spec_from_file_location("_kit_" + name.replace("-", "_").replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstalledProject(unittest.TestCase):
    """A project with the kit installed, stub language servers, and the installed scripts run as programs."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = pathlib.Path(tmp.name).resolve()

    def install(self, name="project", **options):
        folder = self.work / name
        folder.mkdir()
        forge.apply_kit(folder, "lsp", **options)
        return folder

    def stub(self, mode):
        """The command of a stub language server behaving as `mode` says."""
        path = self.work / f"server-{mode}.py"
        path.write_text(DOC_STUB.format(mode=mode), encoding="utf-8")
        return [sys.executable, str(path)]

    def servers(self, project, *entries):
        """Write the project's table: (name, mode or None for a program that is not installed)."""
        servers = [{"name": name, "command": self.stub(mode) if mode else [f"no-such-{name}-anywhere"],
                    "extensions": {".py": "python"}, "install": f"install {name} by hand", "settle": 1}
                   for name, mode in entries]
        (project / TABLE).write_text(json.dumps({"schema_version": 1, "servers": servers}), encoding="utf-8")

    def run_script(self, project, *argv, env=None):
        ran = subprocess.run([sys.executable, "-B", *[str(arg) for arg in argv]], cwd=project, env=env,
                             capture_output=True, text=True, timeout=300,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return ran.returncode, ran.stdout, ran.stderr

    def git(self, project, *args):
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True, env=env,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class DocumentTests(InstalledProject):
    """D04 T01 section 7: the installed document's commands and explanations, held to the scripts."""

    DOCUMENT = SDK_ROOT / KIT / "docs/language-servers.md"
    SCRIPTS = ("lsp-servers.py", "lsp-diagnostics.py", "lsp-mcp-bridge.py")

    def commands(self, section=None):
        """Every command line of the kit's scripts in the document (or in one of its sections), in its order:
        (script, arguments)."""
        text = self.DOCUMENT.read_text(encoding="utf-8")
        if section:
            text = text.split(f"## {section}" + chr(10), 1)[1].split(chr(10) + "## ", 1)[0]
        found = []
        for match in re.finditer(r"python3? scripts/(lsp-[a-z-]+\.py)([^`\n\"\]]*)", text):
            script, rest = match.group(1), match.group(2).split("#", 1)[0]
            found.append((script, shlex.split(rest)))
        return found

    def test_every_documented_command_fits_its_scripts_own_parser_whole(self):
        commands = self.commands()
        self.assertEqual({script for script, _arguments in commands}, set(self.SCRIPTS))
        presets = forge._lsp_table_module().load_presets()["presets"]
        for script, arguments in commands:
            with self.subTest(command=f"{script} {' '.join(arguments)}"):
                parser = kit_script(script).build_parser()
                with contextlib.redirect_stderr(io.StringIO()) as errors:
                    try:
                        parsed = parser.parse_args(arguments)
                    except SystemExit:
                        self.fail(f"the document's command does not parse: {errors.getvalue().strip()}")
                if script == "lsp-servers.py" and parsed.command == "add":
                    self.assertIn(parsed.preset, presets)
        # Each use the document promises has an example.
        lines = {f"{script} {' '.join(arguments)}" for script, arguments in commands}
        for promised in ("lsp-servers.py add python", "lsp-servers.py list", "lsp-servers.py remove basedpyright",
                         "lsp-servers.py plugin", "lsp-diagnostics.py --all --changed",
                         "lsp-diagnostics.py --all --staged",
                         "lsp-diagnostics.py --all --worktree", "lsp-diagnostics.py --all --commit HEAD",
                         "lsp-diagnostics.py --server basedpyright src/app.py",
                         "lsp-diagnostics.py --all --staged --json"):
            self.assertIn(promised, lines, "the document has no example of this")
        text = self.DOCUMENT.read_text(encoding="utf-8")
        for preset in presets:
            self.assertIn(f"`{preset}`", text, f"the document does not name the preset {preset}")

    def test_the_line_that_tries_the_bridge_by_hand_prints_the_four_tools(self):
        # D04 T01 section 8: this line printed nothing, because the end of input stopped the bridge first.
        project = self.install()
        text = (project / "docs/language-servers.md").read_text(encoding="utf-8")
        (line,) = [line for line in text.splitlines() if line.startswith("echo '")]
        self.assertTrue(line.endswith("| python scripts/lsp-mcp-bridge.py"), line)
        folder = self.work / "python-on-path"
        folder.mkdir()
        if os.name == "nt":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            if not shell:
                self.skipTest("needs PowerShell")
            argv = [shell, "-NoProfile", "-NonInteractive", "-Command", line]
            path = str(pathlib.Path(sys.executable).parent)
        else:
            launcher = folder / "python"
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
            argv = ["/bin/sh", "-c", line]
            path = str(folder)
        env = dict(os.environ, PATH=path + os.pathsep + os.environ["PATH"])
        ran = subprocess.run(argv, cwd=project, env=env, capture_output=True, text=True, timeout=180,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(ran.returncode, 0, ran.stderr)
        (reply,) = [json.loads(out) for out in ran.stdout.splitlines() if out.strip()]
        self.assertEqual((reply["id"], [tool["name"] for tool in reply["result"]["tools"]]),
                         (1, ["diagnostics", "definition", "references", "hover"]))
        for said in ("It prints one line of JSON that names the four tools, and exits 0.",
                     "a call needs the input kept open until its answer has been read"):
            self.assertIn(said, text)

    def test_a_command_the_scripts_lack_does_not_parse(self):
        # What the test above would do with a wrong document: an option that is not there, a missing argument.
        for script, arguments in (("lsp-servers.py", ["add"]), ("lsp-servers.py", ["install", "python"]),
                                  ("lsp-diagnostics.py", ["--all", "--modified"]),
                                  ("lsp-diagnostics.py", ["--all", "--commit"]), ("lsp-mcp-bridge.py", ["--port", "1"])):
            with self.subTest(command=f"{script} {' '.join(arguments)}"):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    kit_script(script).build_parser().parse_args(arguments)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_the_documents_setup_sequence_and_its_recovery_work_in_an_installed_project(self):
        # The document's own commands, in its order, on the table they leave: nothing is swapped in. The one thing
        # the test supplies is what the document says the reader must install, the server's program, as a stub.
        project = self.install()
        stub = self.stub("clean")
        folder = self.work / "bin"
        folder.mkdir()
        if os.name == "nt":
            (folder / "basedpyright-langserver.cmd").write_text(f'@"{stub[0]}" "{stub[1]}" %*\r\n', encoding="utf-8")
        else:
            launcher = folder / "basedpyright-langserver"
            launcher.write_text(f'#!/bin/sh\nexec "{stub[0]}" "{stub[1]}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        env = dict(os.environ, PATH=str(folder) + os.pathsep + os.environ["PATH"])
        setup = [arguments for script, arguments in self.commands("Setting up") if script == "lsp-servers.py"]
        steps, later = setup[:-1], setup[-1]
        self.assertEqual([arguments[0] for arguments in steps[:3]], ["add", "list", "plugin"])
        self.assertEqual(later[0], "remove", "taking a server out is shown after the steps, not among them")
        self.assertNotIn("remove", [arguments[0] for arguments in steps])
        for arguments in steps:
            code, _out, err = self.run_script(project, "scripts/lsp-servers.py", *arguments, env=env)
            self.assertEqual(code, 0, f"lsp-servers.py {' '.join(arguments)}: {err}")
        # After the steps the project has the server it added, and a plugin that names it.
        table = forge._lsp_table_module()
        self.assertEqual([server["name"] for server in table.load_servers(project)], ["basedpyright"])
        plugin = forge._lsp_plugin_module()
        listed = json.loads((project / plugin.FOLDER / plugin.SERVERS).read_text(encoding="utf-8"))
        self.assertEqual(list(listed), ["basedpyright"])

        def doctor():
            with unittest.mock.patch.dict(os.environ, {"PATH": env["PATH"]}):
                return {check["name"]: check["status"] for check in forge.doctor_repo(project, "lsp")["checks"]}

        self.assertEqual((doctor()["claude-plugin"], doctor()["server:basedpyright"]), ("ok", "ok"))
        # The table edited by hand: the plugin is behind it until the documented command is run again.
        document = json.loads((project / TABLE).read_text(encoding="utf-8"))
        document["servers"][0]["command"] = ["basedpyright-langserver", "--stdio", "--verbose"]
        (project / TABLE).write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual(doctor()["claude-plugin"], "unexpected")
        text = self.DOCUMENT.read_text(encoding="utf-8")
        self.assertIn("the plugin is behind it (the doctor's `claude-plugin` check says `unexpected`): run "
                      "`python scripts/lsp-servers.py plugin` again", text)
        self.assertEqual(self.run_script(project, "scripts/lsp-servers.py", "plugin", env=env)[0], 0)
        self.assertEqual(doctor()["claude-plugin"], "ok")
        for word in ("claude --plugin-dir .claude/lsp/conclave-lsp", "`CLAUDE_CODE_PLUGIN_DIRS`",
                     "Nothing here installs one"):
            self.assertIn(word, text)
        # The diagnostics commands, each as the document writes it, on that table: a clean file, checked by the
        # server the setup added, which must finish (`ok`), with exit 0. Not merely "did not refuse".
        # The installed kit is committed first, so that the change under check is the project's own file.
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                     ["add", "-A"], ["commit", "-qm", "the kit"]):
            self.git(project, *args)
        (project / "src").mkdir()
        (project / "src/app.py").write_text("x = 1\n", encoding="utf-8")
        for args in (["add", "src/app.py"], ["commit", "-qm", "first"]):
            self.git(project, *args)
        (project / "src/app.py").write_text("x = 2\n", encoding="utf-8")
        self.git(project, "add", "src/app.py")
        (project / "src/app.py").write_text("x = 3\n", encoding="utf-8")   # staged, and changed again since
        checking = [arguments for script, arguments in self.commands("Checking a change")
                    if script == "lsp-diagnostics.py" and arguments]
        self.assertGreaterEqual(len(checking), 6)
        for arguments in checking:
            with self.subTest(command=" ".join(arguments)):
                extra = [] if "--json" in arguments else ["--json"]
                code, out, err = self.run_script(project, "scripts/lsp-diagnostics.py", *arguments, *extra,
                                                 "--settle", "0.2", env=env)
                self.assertEqual(code, 0, f"lsp-diagnostics.py {' '.join(arguments)}: {err}")
                report = json.loads(out)
                self.assertEqual(report["servers"]["basedpyright"], {"status": "ok", "reason": None, "files": 1,
                                                                     "unanswered": [], "unread": []})
        # And the same commands report a diagnostic when the file has one.
        (project / "src/app.py").write_text("x = 3\nE: undefined name\n", encoding="utf-8")
        code, out, _err = self.run_script(project, "scripts/lsp-diagnostics.py", "--all", "--changed", "--json",
                                          "--settle", "0.2", env=env)
        self.assertEqual((code, json.loads(out)["diagnostics"][0]["message"]), (1, "undefined name"))
        # Taking the server out, as the document shows afterwards.
        self.assertEqual(self.run_script(project, "scripts/lsp-servers.py", *later, env=env)[0], 0)
        self.assertEqual(table.load_servers(project), [])

    def test_the_documents_table_of_outcomes_is_what_the_client_does(self):
        text = self.DOCUMENT.read_text(encoding="utf-8")
        rows = re.findall(r"^\| ([^|]+) \| ([^|]+) \| (\d) \|$", text, flags=re.MULTILINE)
        self.assertEqual(len(rows), 7, "the document's table of outcomes has seven runs")
        project = self.install()
        (project / "a.py").write_text("x = 1\n", encoding="utf-8")
        (project / "bad.py").write_text("E: undefined name\n", encoding="utf-8")
        (project / "skip.py").write_text("x = 1\n", encoding="utf-8")
        # Each run of the table, in its order: (the table's servers, the arguments, the word the row names).
        runs = [([("good", "clean")], ["--all", "a.py"], None),
                ([("good", "clean")], ["--all", "bad.py"], None),
                ([("absent", None), ("good", "clean")], ["--all", "a.py"], "SKIPPED"),
                ([("absent", None)], ["--all", "a.py"], "SKIPPED"),
                ([("broken", "refuse"), ("good", "clean")], ["--all", "a.py"], "FAILED"),
                ([("half", "half")], ["--all", "a.py", "skip.py"], "PARTIAL"),
                ([("good", "clean")], ["--server", "unknown", "a.py"], None)]
        for (label, printed, code), (entries, arguments, word) in zip(rows, runs):
            with self.subTest(run=label.strip()):
                self.servers(project, *entries)
                got, out, err = self.run_script(project, "scripts/lsp-diagnostics.py", *arguments, "--settle", "0.2",
                                                "--timeout", "4")
                self.assertEqual(got, int(code), f"the document says exit {code} for: {label.strip()}\n{out}{err}")
                if word:
                    self.assertIn(f"`{word}`", printed, f"the row does not name what the client prints: {word}")
                    self.assertIn(f"{word} -- ", err)
                for other in {"SKIPPED", "FAILED", "PARTIAL"} - {word}:
                    self.assertNotIn(f"{other} -- ", err, f"the client printed {other} in a run the row does not say")
        for word in ("SKIPPED", "FAILED", "PARTIAL"):
            self.assertRegex(text, rf"`{word}` means ")


class SkillTests(InstalledProject):
    """D04 T01 section 7: the skill in the three agent folders, and the doctor's file checks by agent."""

    FOLDERS = {".claude": "Claude Code", ".agents": "Antigravity", ".codex": "Codex"}

    def test_the_policy_is_stated_in_each_installed_copy(self):
        project = self.install()
        for folder, agent in self.FOLDERS.items():
            with self.subTest(agent=agent):
                text = (project / folder / SKILL).read_text(encoding="utf-8")
                front = text.split("---\n")[1]
                self.assertIn("name: language-servers\n", front)
                description = next(line for line in front.splitlines() if line.startswith("description: "))
                self.assertIn("before calling a code change done", description)
                self.assertIn("the definition or the uses of a symbol", description)
                for statement in POLICY:
                    self.assertIn(statement, text, f"{agent}'s skill does not say: {statement}")
                for named in ("scripts/lsp-diagnostics.py", "docs/language-servers.md", TABLE, "--all --changed",
                              "--worktree", "--staged", "--commit"):
                    self.assertIn(named, text)
                self.assertLess(len(text.splitlines()), 60)

    def test_each_copy_names_how_its_own_agent_reaches_the_servers(self):
        project = self.install()
        texts = {folder: (project / folder / SKILL).read_text(encoding="utf-8") for folder in self.FOLDERS}
        self.assertIn("claude --plugin-dir .claude/lsp/conclave-lsp", texts[".claude"])
        self.assertNotIn("lsp-mcp-bridge.py", texts[".claude"])
        for folder, register in ((".agents", "agy mcp add conclave-lsp python scripts/lsp-mcp-bridge.py"),
                                 (".codex", "codex mcp add conclave-lsp -- python scripts/lsp-mcp-bridge.py")):
            self.assertIn(register, texts[folder])
            self.assertNotIn("--plugin-dir", texts[folder], f"{folder} names the Claude Code plugin as its own")
            for tool in ("`diagnostics`", "`definition`", "`references`", "`hover`"):
                self.assertIn(tool, texts[folder])
        # The copies differ from the Claude file only in that paragraph.
        claude = texts[".claude"].splitlines()
        for folder in (".agents", ".codex"):
            differing = [number for number, (one, other) in enumerate(zip(claude, texts[folder].splitlines()))
                         if one != other]
            self.assertEqual(len(differing), 1, f"{folder} differs from the Claude file in more than its paragraph")
        self.assertTrue((project / ".codex/skills/language-servers/agents/openai.yaml").is_file())
        self.assertEqual([path.as_posix() for folder in (".claude", ".agents")
                          for path in (project / folder).rglob("openai.yaml")], [])
        self.assertEqual(forge.skill_copy_report(check=True), {"changed": [], "stray": []})

    def test_the_doctor_checks_the_skills_of_the_agents_the_project_was_installed_for(self):
        skills = {folder: f"{folder}/{SKILL}" for folder in self.FOLDERS}
        project = self.install()
        checks = {check["name"]: check["status"] for check in forge.doctor_repo(project, "lsp")["checks"]}
        for rel in skills.values():
            self.assertEqual(checks[rel], "ok")
        self.assertEqual(checks[".codex/skills/language-servers/agents/openai.yaml"], "ok")
        (project / skills[".agents"]).unlink()
        checks = {check["name"]: check["status"] for check in forge.doctor_repo(project, "lsp")["checks"]}
        self.assertEqual(checks[skills[".agents"]], "missing")
        # Installed for one agent: that agent's skill, and nothing said of the others.
        single = self.install("claude-only", agent="claude")
        report = forge.doctor_repo(single, "lsp")
        checks = {check["name"]: check["status"] for check in report["checks"]}
        self.assertEqual(checks[skills[".claude"]], "ok")
        for folder in (".agents", ".codex"):
            self.assertFalse(any(name.startswith(folder + "/") for name in checks), f"{folder} is listed")
        self.assertEqual([name for name, status in checks.items() if status == "missing"], [])
        self.assertIn("scripts/lsp-diagnostics.py", checks)   # what is not an agent's is checked for every install

    def test_the_readme_says_what_each_agent_gets(self):
        readme = (SDK_ROOT / "kits/lsp/README.md").read_text(encoding="utf-8")
        for agent, folder in (("Claude Code", ".claude"), ("Codex", ".codex"), ("Antigravity", ".agents")):
            row = next((line for line in readme.splitlines() if line.startswith(f"| {agent} |")), None)
            self.assertIsNotNone(row, f"the README has no row for {agent}")
            self.assertIn(f"`{folder}/skills/language-servers`", row)
            self.assertIn("lsp-diagnostics.py", row)
        self.assertNotIn("Still to come", readme)
        self.assertNotIn("being built in sections", readme)


class FreshInstallTests(InstalledProject):
    """D04 T01 section 7: a new project, from `init` to a diagnostic read back, with the kit as it is in the SDK."""

    def setUp(self):
        super().setUp()
        self.bin = self.work / "bin"
        self.bin.mkdir()
        stub = self.stub("clean")
        if os.name == "nt":
            (self.bin / "basedpyright-langserver.cmd").write_text(f'@"{stub[0]}" "{stub[1]}" %*\r\n', encoding="utf-8")
        else:
            launcher = self.bin / "basedpyright-langserver"
            launcher.write_text(f'#!/bin/sh\nexec "{stub[0]}" "{stub[1]}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"])

    def test_a_new_project_has_the_servers_from_init_to_a_diagnostic(self):
        project = self.work / "new"
        project.mkdir()
        code, out, err = command_line("init", project, "--kit", "lsp")
        self.assertEqual(code, 0, err)
        code, out, err = self.run_script(project, "scripts/lsp-servers.py", "add", "python", env=self.env)
        self.assertEqual((code, out), (0, "added: basedpyright\n"), err)
        with unittest.mock.patch.dict(os.environ, {"PATH": self.env["PATH"]}):
            report = forge.doctor_repo(project, "lsp")
        checks = {check["name"]: check for check in report["checks"]}
        for rel in kit_files(forge.FORGE_ROOT):
            self.assertEqual(checks[rel]["status"], "ok", f"{rel} is not installed")
        # What a project must have, written here and not read from the kit: a file gone from the kit is missed.
        for rel in (TABLE, "docs/language-servers.md", "scripts/lsp-servers.py", "scripts/lsp-diagnostics.py",
                    "scripts/lsp-mcp-bridge.py", "scripts/lib/lsp_table.py", "scripts/lib/lsp_client.py",
                    "scripts/lib/lsp_plugin.py", "scripts/lib/lsp_presets.json",
                    *[f"{folder}/{SKILL}" for folder in (".claude", ".agents", ".codex")],
                    ".codex/skills/language-servers/agents/openai.yaml"):
            self.assertTrue((project / rel).is_file(), f"a new project has no {rel}")
        self.assertEqual(checks["server:basedpyright"]["status"], "ok")
        self.assertEqual(checks["server-table"]["detail"], f"{TABLE}: basedpyright")
        (project / "app.py").write_text("x = 1\nE: undefined name\n", encoding="utf-8")
        code, out, err = self.run_script(project, "scripts/lsp-diagnostics.py", "--all", "app.py", "--settle", "0.2",
                                         "--json", env=self.env)
        self.assertEqual(code, 1, err)
        document = json.loads(out)
        self.assertEqual(document["servers"]["basedpyright"]["status"], "ok")
        self.assertEqual([(row["file"], row["line"], row["message"]) for row in document["diagnostics"]],
                         [("app.py", 2, "undefined name")])
        # The plugin of the installed copy is generated, and its bridge answers. (Until D04 T01 section 8 this
        # asserted only exit 0, and passed while the bridge printed nothing for a request followed by the end of
        # input.)
        self.assertEqual(self.run_script(project, "scripts/lsp-servers.py", "plugin", env=self.env)[0], 0)
        ran = subprocess.run([sys.executable, "-B", "scripts/lsp-mcp-bridge.py"], cwd=project, env=self.env,
                             input='{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}\n', capture_output=True,
                             text=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual([tool["name"] for tool in json.loads(ran.stdout)["result"]["tools"]],
                         ["diagnostics", "definition", "references", "hover"])

    @unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "slow: set CONCLAVE_FULL_TESTS=1 for the full suite")
    def test_the_kits_own_tests_pass_from_the_installed_copy(self):
        project = self.work / "new"
        project.mkdir()
        self.assertEqual(command_line("init", project, "--kit", "lsp")[0], 0)
        ran = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "scripts/tests", "-p",
                              "test_lsp_*.py"], cwd=project, capture_output=True, text=True, timeout=1500,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(ran.returncode, 0, ran.stderr[-2000:])

    def test_the_fresh_install_test_fails_when_a_template_file_is_gone_from_the_kit(self):
        scratch = self.work / "sdk"
        shutil.copytree(SDK_ROOT / "kits", scratch / "kits", ignore=shutil.ignore_patterns("__pycache__"))
        name = "test_a_new_project_has_the_servers_from_init_to_a_diagnostic"
        with unittest.mock.patch.object(forge, "FORGE_ROOT", scratch):
            control = unittest.TestResult()
            FreshInstallTests(name).run(control)
            self.assertTrue(control.wasSuccessful(), control.failures + control.errors)
            for rel in ("scripts/lib/lsp_client.py", "docs/language-servers.md", ".claude/" + SKILL):
                with self.subTest(removed=rel):
                    template = scratch / KIT / rel
                    held = scratch / "held"
                    shutil.move(template, held)
                    try:
                        removed = unittest.TestResult()
                        FreshInstallTests(name).run(removed)
                    finally:
                        shutil.move(held, template)
                    self.assertEqual(removed.testsRun, 1)
                    self.assertFalse(removed.wasSuccessful(), f"the fresh install passed with {rel} gone from the kit")


if __name__ == "__main__":
    unittest.main()
