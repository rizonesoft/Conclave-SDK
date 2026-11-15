"""The `lsp` kit as `forge.py` knows it: install, record, detection and doctor (D04 T01 section 1).

The kit's own scripts are tested in the kit, under `kits/lsp/templates/scripts/tests/`.
"""
import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
import unittest.mock

SDK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))
import forge  # noqa: E402

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
        self.assertIn("|lsp|", (forge.__doc__ or "").replace("[", "|").replace("]", "|"))
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
                         {rel: "ok" for rel in kit_files()})
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
        self.assertEqual(names[len(bare["checks"]):], kit_files())
        self.assertEqual(self.checks(report)[TABLE]["status"], "ok")
        # A named kit is that kit alone, as before.
        named = json.loads(command_line("doctor", project, "base")[1])
        self.assertNotIn("also", named)
        self.assertNotIn(TABLE, self.checks(named))

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
