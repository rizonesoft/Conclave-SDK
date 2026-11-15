"""The two toolchain kits as the SDK holds them (D04 T02).

The kits' own scripts are tested in the kits, under `kits/toolchain-<name>/templates/scripts/tests/`.
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

PINS = ".conclave/toolchain-cpp.json"
# One line of each program's real `--version` output, with where it was captured (2026-11-15, Windows 11 and
# Ubuntu 26.04 in WSL). The Ubuntu forms carry the distribution's prefix. mold and Ubuntu's lld are not installed
# on that machine: each was run from its Ubuntu package (`apt download`, unpacked into scratch, nothing
# installed), so their lines are captured output too.
REAL_OUTPUT = {
    "ninja": [("1.13.2\n", "1.13.2", "ninja 1.13.2, Windows and Ubuntu")],
    "ccache": [("ccache version 4.12.3\n", "4.12.3", "ccache 4.12.3, Ubuntu")],
    "sccache": [("sccache 0.19.0\n", "0.19.0", "sccache 0.19.0, Windows")],
    "mold": [("mold 2.40.4 (compatible with GNU ld)\n", "2.40.4",
              "mold 2.40.4, run from Ubuntu's package mold 2.40.4+dfsg-2.1ubuntu1")],
    "ld.lld": [("LLD 22.1.3 (https://github.com/llvm/llvm-project e9846648fd6183ee6d8cbdb4502213fcf902a211) "
                "(compatible with GNU linkers)\n", "22.1.3", "LLD 22.1.3, Windows"),
               ("Ubuntu LLD 19.1.7 (compatible with GNU linkers)\n", "19.1.7",
                "LLD 19.1.7, run from Ubuntu's package lld-19 1:19.1.7-20ubuntu4")],
    "clangd": [("clangd version 22.1.3 (https://github.com/llvm/llvm-project "
                "e9846648fd6183ee6d8cbdb4502213fcf902a211)\n", "22.1.3", "clangd 22.1.3, Windows"),
               ("Ubuntu clangd version 19.1.7 (20ubuntu4)\n", "19.1.7", "clangd 19.1.7, Ubuntu")],
    "clang": [("clang version 22.1.3 (https://github.com/llvm/llvm-project "
               "e9846648fd6183ee6d8cbdb4502213fcf902a211)\nTarget: x86_64-pc-windows-msvc\n", "22.1.3",
               "clang 22.1.3, Windows"),
              ("Ubuntu clang version 19.1.7 (20ubuntu4)\nTarget: x86_64-pc-linux-gnu\n", "19.1.7",
               "clang 19.1.7, Ubuntu")],
    "gcc": [("gcc (Ubuntu 15.2.0-16ubuntu1) 15.2.0\nCopyright (C) 2025 Free Software Foundation, Inc.\n", "15.2.0",
             "gcc 15.2.0, Ubuntu")],
}


def command_line(*argv):
    """`forge.py <argv>` in process: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = forge.main([str(arg) for arg in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


# One source, two kits: the tool check and its tests ship in both, so a project with either kit has a tested script.
SHARED = ("scripts/toolchain-check.py", "scripts/tests/test_toolchain_check.py")


def differing(root):
    """The shared files whose copy in the web kit is not byte for byte the C and C++ kit's."""
    cpp, web = root / "kits/toolchain-cpp/templates", root / "kits/toolchain-web/templates"
    return [rel for rel in SHARED
            if not (web / rel).is_file() or (cpp / rel).read_bytes() != (web / rel).read_bytes()]


class SharedCheckTests(unittest.TestCase):
    def test_the_web_kits_copies_are_the_cpp_kits_files_byte_for_byte(self):
        self.assertEqual(differing(SDK_ROOT), [])

    def test_one_changed_byte_in_either_copy_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = pathlib.Path(tmp).resolve()
            for kit in ("toolchain-cpp", "toolchain-web"):
                shutil.copytree(SDK_ROOT / "kits" / kit, scratch / "kits" / kit,
                                ignore=shutil.ignore_patterns("__pycache__"))
            self.assertEqual(differing(scratch), [])
            for kit, rel in (("toolchain-web", SHARED[0]), ("toolchain-cpp", SHARED[1])):
                with self.subTest(kit=kit, rel=rel):
                    path = scratch / "kits" / kit / "templates" / rel
                    kept = path.read_bytes()
                    path.write_bytes(kept + b"\n")
                    self.assertEqual(differing(scratch), [rel])
                    path.write_bytes(kept)
            (scratch / "kits/toolchain-web/templates" / SHARED[1]).unlink()
            self.assertEqual(differing(scratch), [SHARED[1]])

    def test_each_kits_tests_are_a_suite_of_check_all(self):
        suites = {suite["name"]: suite["path"] for suite in forge.SUITES}
        for kit in ("toolchain-cpp", "toolchain-web"):
            self.assertEqual(suites.get(f"kit-{kit}"), f"kits/{kit}/templates/scripts/tests")
            self.assertIn(kit, forge.list_kits())


class CppKitTests(unittest.TestCase):
    """D04 T02 section 2: the toolchain-cpp kit's seed pins, its install and its doctor."""

    KIT = "toolchain-cpp"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = pathlib.Path(tmp.name).resolve()
        self.bin = self.work / "bin"
        self.bin.mkdir()
        # Only the stubs are on PATH: a tool this host really has must not answer for one a test left out.
        env = {"PATH": str(self.bin), **({"PATHEXT": ".CMD;.EXE"} if os.name == "nt" else {})}
        patch = unittest.mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        self.module = forge._toolchain_module(self.KIT)

    def project(self, name="project", install=True):
        folder = self.work / name
        folder.mkdir()
        if install:
            forge.apply_kit(folder, self.KIT)
        return folder

    def stub(self, name, body):
        """A program on the scratch PATH whose behaviour is the Python `body`; `{dir}` in it is the scratch folder."""
        code = self.work / f"{name}-stub.py"
        code.write_text(body.replace("{dir}", self.work.as_posix()), encoding="utf-8")
        if os.name == "nt":
            launcher = self.bin / f"{name}.cmd"
            launcher.write_text(f'@"{sys.executable}" "{code}" %*\r\n', encoding="utf-8")
        else:
            launcher = self.bin / name
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{code}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        return launcher

    def prints(self, name, text, code=0):
        return self.stub(name, f"import sys\nsys.stdout.write({text!r})\nsys.exit({code})\n")

    def pin(self, name, optional=False, minimum="2.0", command=None):
        return {"name": name, "optional": optional, "install": f"install {name} by hand",
                "commands": [{"command": command or name, "version_args": ["--version"],
                              "version_pattern": r"v([0-9.]+)", "min_version": minimum}]}

    def write_pins(self, project, *tools):
        (project / PINS).write_text(json.dumps({"schema_version": 1, "tools": list(tools)}), encoding="utf-8")

    def doctor(self, project, *extra):
        code, out, _err = command_line("doctor", project, self.KIT, *extra)
        report = json.loads(out)
        return code, report, {check["name"]: check for check in report["checks"]}

    def snapshot(self, folder):
        return {path.relative_to(folder).as_posix(): path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}

    # the seed

    def test_the_seed_pins_five_tools_and_marks_the_three_a_project_may_not_use_optional(self):
        seed = self.module.load_pins(SDK_ROOT / "kits" / self.KIT / "templates" / PINS)
        self.assertEqual([(tool["name"], tool["optional"], [c["command"] for c in tool["commands"]]) for tool in seed],
                         [("ninja", True, ["ninja"]), ("compiler-cache", True, ["ccache", "sccache"]),
                          ("linker", True, ["mold", "ld.lld"]), ("clangd", False, ["clangd"]),
                          ("compiler", False, ["clang", "gcc"])])
        for tool in seed:
            self.assertIn("apt install", tool["install"], tool["name"])
            self.assertIn("winget install", tool["install"], tool["name"])
            for entry in tool["commands"]:
                self.assertEqual(entry["version_args"], ["--version"])

    def test_each_seed_pattern_reads_the_version_from_that_programs_real_output(self):
        seed = self.module.load_pins(SDK_ROOT / "kits" / self.KIT / "templates" / PINS)
        entries = {entry["command"]: (tool, entry) for tool in seed for entry in tool["commands"]}
        self.assertEqual(sorted(entries), sorted(REAL_OUTPUT))
        for name, samples in REAL_OUTPUT.items():
            tool, entry = entries[name]
            for text, version, source in samples:
                with self.subTest(command=name, source=source):
                    self.prints(name, text)
                    result = self.module.check_tool(dict(tool, commands=[entry]))
                    self.assertEqual((result["status"], result["version"]), ("ok", version), result["detail"])
            (self.bin / (f"{name}.cmd" if os.name == "nt" else name)).unlink()

    # the install

    def test_init_and_kit_install_the_pins_and_the_check_and_record_them(self):
        files = [PINS, "scripts/tests/test_toolchain_check.py", "scripts/toolchain-check.py"]
        for name, argv in (("by-init", ("init", "{}", "--kit", self.KIT)), ("by-kit", ("kit", "{}", self.KIT))):
            with self.subTest(command=argv[0]):
                project = self.project(name, install=False)
                code, _out, err = command_line(*(str(project) if arg == "{}" else arg for arg in argv))
                self.assertEqual(code, 0, err)
                record = json.loads((project / forge.RECORD).read_text(encoding="utf-8"))
                self.assertIn(self.KIT, record["kits"])
                for rel in files:
                    self.assertTrue((project / rel).is_file(), rel)
                    self.assertEqual(record["files"][rel]["kit"], self.KIT)
        project = self.project("twice", install=False)
        self.assertEqual(forge.apply_kit(project, self.KIT)["installed"], files)
        before = self.snapshot(project)
        second = forge.apply_kit(project, self.KIT)
        self.assertEqual((second["installed"], second["preserved"]), ([], files))
        self.assertEqual(self.snapshot(project), before)
        owned = self.project("owned", install=False)
        own = b'{"schema_version": 1, "tools": []}\r\n'
        (owned / ".conclave").mkdir()
        (owned / PINS).write_bytes(own)
        self.assertIn(PINS, forge.apply_kit(owned, self.KIT)["preserved"])
        self.assertEqual((owned / PINS).read_bytes(), own)

    def test_the_kit_is_detected_by_its_pin_file(self):
        project = self.project(install=False)
        self.assertNotIn(self.KIT, forge.check_repo(project)["kits"])
        # The check script alone is not this kit: the web kit ships the same file.
        (project / "scripts").mkdir()
        shutil.copyfile(SDK_ROOT / "kits/toolchain-web/templates/scripts/toolchain-check.py",
                        project / "scripts/toolchain-check.py")
        self.assertNotIn(self.KIT, forge.check_repo(project)["kits"])
        forge.apply_kit(project, self.KIT)
        self.assertIn(self.KIT, forge.check_repo(project)["kits"])
        self.assertIn(self.KIT, forge.KIT_ORDER)
        self.assertLess(forge.KIT_ORDER.index("lsp"), forge.KIT_ORDER.index(self.KIT))
        self.assertIn("|toolchain-cpp|", (forge.__doc__ or "").replace("[", "|").replace("]", "|"))
        for command in ("init", "kit"):
            self.assertIn(self.KIT, command_line(command, "--help")[1], command)
        self.assertIn("'toolchain-cpp'", forge.apply_kit.__doc__ or "")

    # the doctor

    def test_the_doctor_reports_the_files_the_pins_and_each_tool_with_its_version(self):
        project = self.project()
        launcher = self.prints("alpha", "alpha v2.5.1\n")
        self.write_pins(project, self.pin("alpha"))
        code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["kit"], report["missing_or_setup_required"]), (0, self.KIT, 0))
        for rel in (PINS, "scripts/toolchain-check.py", "scripts/tests/test_toolchain_check.py"):
            self.assertEqual(checks[rel]["status"], "ok")
        self.assertEqual(checks["tool-pins"], {"name": "tool-pins", "status": "ok", "detail": f"{PINS}: alpha"})
        self.assertEqual(checks["tool:alpha"]["status"], "ok")
        found, version = checks["tool:alpha"]["detail"].rsplit(" ", 1)
        self.assertEqual(version, "2.5.1")
        self.assertTrue(os.path.samefile(found, launcher))

    def broken_tools(self):
        """One stub per way a tool can fail to be ok, by name; `absent` is not installed at all."""
        self.prints("old", "old v1.9\n")
        self.prints("failing", "failing v2.5\n", code=4)
        self.prints("unreadable", "no version here\n")
        self.stub("silent", "import time\ntime.sleep(120)\n")
        return {"absent": "not installed (absent not on PATH). Install: install absent by hand",
                "old": "older than the pinned 2.0",
                "failing": "exited 4",
                "unreadable": "does not match its output",
                "silent": "did not answer within 2 seconds and was stopped"}

    def test_a_required_tool_that_is_not_ok_is_setup_required_whatever_the_cause(self):
        project = self.project()
        causes = self.broken_tools()
        self.prints("fine", "fine v3.0\n")
        self.write_pins(project, *[self.pin(name) for name in causes], self.pin("fine"))
        with unittest.mock.patch.object(self.module, "TIME_LIMIT", 2.0):
            code, report, checks = self.doctor(project, "--strict")
        self.assertEqual(code, 3)
        for name, detail in causes.items():
            with self.subTest(cause=name):
                self.assertEqual(checks[f"tool:{name}"]["status"], "setup_required")
                self.assertIn(detail, checks[f"tool:{name}"]["detail"])
        self.assertIn("is 1.9, older than the pinned 2.0", checks["tool:old"]["detail"])
        self.assertEqual(checks["tool:fine"]["status"], "ok")  # every tool after a failure is still reported
        self.assertEqual(report["missing_or_setup_required"], len(causes))

    def test_an_optional_tool_that_is_not_ok_is_shown_as_optional_and_never_counted(self):
        project = self.project()
        causes = self.broken_tools()
        self.prints("fine", "fine v3.0\n")
        self.write_pins(project, *[self.pin(name, optional=True) for name in causes], self.pin("fine"))
        with unittest.mock.patch.object(self.module, "TIME_LIMIT", 2.0):
            code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["missing_or_setup_required"]), (0, 0))
        for name, detail in causes.items():
            with self.subTest(cause=name):
                self.assertEqual(checks[f"tool:{name}"]["status"], "optional")
                self.assertIn(detail, checks[f"tool:{name}"]["detail"])
        self.assertEqual(checks["tool:fine"]["status"], "ok")

    def test_a_pin_file_that_does_not_load_is_reported_with_the_refusal_and_no_tool_check(self):
        project = self.project()
        (project / PINS).write_text('{"schema_version": 1, "tools": [{"name": "x"}]}', encoding="utf-8")
        code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["missing_or_setup_required"]), (3, 1))
        self.assertEqual(checks["tool-pins"]["status"], "missing")
        self.assertIn("tool 'x': missing key", checks["tool-pins"]["detail"])
        self.assertEqual([name for name in checks if name.startswith("tool:")], [])

    def test_the_doctor_follows_the_projects_own_pin_file(self):
        # Found by the plan review of D04 T02 section 2: a kept pin file proves nothing unless the doctor reads it.
        project = self.project()
        launcher = self.prints("house-compiler", "house-compiler v2.5\n")
        self.write_pins(project, self.pin("compiler", command="house-compiler"))  # a command the seed never names
        code, _report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, checks["tool:compiler"]["status"]), (0, "ok"))
        self.assertTrue(os.path.samefile(checks["tool:compiler"]["detail"].rsplit(" ", 1)[0], launcher))
        self.assertNotIn("tool:ninja", checks)  # the seed's tools are not the project's
        self.write_pins(project, self.pin("compiler", command="house-compiler", minimum="3.0"))  # a raised minimum
        code, _report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, checks["tool:compiler"]["status"]), (3, "setup_required"))
        self.assertIn("is 2.5, older than the pinned 3.0", checks["tool:compiler"]["detail"])
        self.write_pins(project, self.pin("compiler", command="house-compiler", minimum="3.0", optional=True))
        code, _report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, checks["tool:compiler"]["status"]), (0, "optional"))

    def test_the_bare_doctor_starts_no_pinned_tool(self):
        project = self.project()
        self.stub("marked", "import pathlib, sys\n"
                            "with open(r'{dir}/ran', 'a') as mark:\n    mark.write('x')\n"
                            "print('marked v2.5')\n")
        self.write_pins(project, self.pin("marked"))
        code, out, _err = command_line("doctor", project)
        bare = json.loads(out)
        self.assertEqual((code, bare["kit"]), (0, "base"))
        self.assertNotIn("also", bare)
        self.assertEqual([check["name"] for check in bare["checks"] if check["name"].startswith("tool")], [])
        self.assertFalse((self.work / "ran").exists(), "the bare doctor started a pinned tool")
        _code, _report, checks = self.doctor(project)
        self.assertEqual(checks["tool:marked"]["status"], "ok")
        self.assertEqual((self.work / "ran").read_text(), "x")

    def test_the_readme_lists_every_file_every_seed_tool_and_the_optional_status(self):
        readme = (SDK_ROOT / "kits" / self.KIT / "README.md").read_text(encoding="utf-8")
        templates = SDK_ROOT / "kits" / self.KIT / "templates"
        for path in sorted(templates.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                self.assertIn(f"`{path.relative_to(templates).as_posix()}`", readme)
        for tool in self.module.load_pins(templates / PINS):
            self.assertIn(f"`{tool['name']}`", readme)
            for entry in tool["commands"]:
                self.assertIn(f"`{entry['command']}`", readme)
        for word in ("`optional`", "`setup_required`", "`tool-pins`", "`tool:<name>`"):
            self.assertIn(word, readme)


if __name__ == "__main__":
    unittest.main()
