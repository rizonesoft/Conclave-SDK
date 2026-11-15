"""The `lsp` kit as `forge.py` knows it: install, record, detection and doctor (D04 T01 section 1).

The kit's own scripts are tested in the kit, under `kits/lsp/templates/scripts/tests/`.
"""
import contextlib
import io
import json
import os
import pathlib
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
                         {**{rel: "ok" for rel in kit_files()}, "server-table": "ok", "claude-plugin": "optional"})
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
        self.assertEqual(names[len(bare["checks"]):], kit_files() + ["server-table", "claude-plugin"])
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
        forge.apply_kit(folder, "lsp")
        if claude:
            (folder / ".claude").mkdir()   # a project that uses Claude Code
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
                # The server under a root of its own is given that folder as its workspace root. Where Claude Code
                # starts the process is its own choice: it is printed, for the record, and not asserted.
                beta = (self.work / f"beta-{mode.strip('-')}.log").read_text(encoding="utf-8")
                self.assertIn("root " + (project / "api").resolve().as_uri(), beta)
                started_in = [line[4:] for line in beta.splitlines() if line.startswith("cwd ")]
                print(f"  beta: workspace root=api, process started in "
                      f"{'the root' if os.path.samefile(started_in[0], project / 'api') else 'the project'}")


if __name__ == "__main__":
    unittest.main()
