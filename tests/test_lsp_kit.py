"""The `lsp` kit as `forge.py` knows it: install, record, detection and doctor (D04 T01 section 1).

The kit's own scripts are tested in the kit, under `kits/lsp/templates/scripts/tests/`.
"""
import contextlib
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
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
        # The Laravel kit's own client is not this kit.
        laravel = self.project("laravel")
        (laravel / "artisan").write_bytes(b"<?php\n")
        forge.apply_kit(laravel, "laravel")
        kits = forge.check_repo(laravel)["kits"]
        self.assertIn("laravel", kits)
        self.assertNotIn("lsp", kits)

    def test_the_doctor_reports_each_file_the_kit_installs(self):
        project = self.project()
        forge.apply_kit(project, "lsp")
        code, out, _err = command_line("doctor", project, "lsp", "--strict")
        report = json.loads(out)
        self.assertEqual((code, report["kit"], report["missing_or_setup_required"]), (0, "lsp", 0))
        self.assertEqual({name: check["status"] for name, check in self.checks(report).items()},
                         {**{rel: "ok" for rel in kit_files()}, "server-table": "ok"})
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
        self.assertEqual(names[len(bare["checks"]):], kit_files() + ["server-table"])
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

    def test_the_readme_names_every_key_every_preset_and_every_file(self):
        readme = (SDK_ROOT / "kits/lsp/README.md").read_text(encoding="utf-8")
        table = forge._lsp_table_module()
        for key in ("name", *table.REQUIRED, *table.DEFAULTS):
            self.assertIn(f"`{key}`", readme, f"the README does not describe the table key {key}")
        for preset in table.load_presets()["presets"]:
            self.assertIn(f"`{preset}`", readme, f"the README does not name the preset {preset}")
        for rel in kit_files():
            self.assertIn(f"`{rel}`", readme, f"the README does not list {rel}")
        for command in ("lsp-servers.py list", "lsp-servers.py add", "lsp-servers.py remove"):
            self.assertIn(command, readme)

    def test_the_bare_doctor_adds_the_kit_to_a_stack_kits_checks(self):
        project = self.project()
        (project / "artisan").write_bytes(b"<?php\n")
        forge.apply_kit(project, "laravel")
        forge.apply_kit(project, "lsp")
        report = forge.doctor_repo(project)
        self.assertEqual((report["kit"], report["also"]), ("laravel", ["lsp"]))
        checks = self.checks(report)
        self.assertEqual(checks["artisan"]["status"], "ok")
        self.assertEqual(checks[TABLE]["status"], "ok")

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


if __name__ == "__main__":
    unittest.main()
