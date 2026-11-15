"""The two toolchain kits as the SDK holds them (D04 T02).

The kits' own scripts are tested in the kits, under `kits/toolchain-<name>/templates/scripts/tests/`.
"""
import contextlib
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

# The PHP and Node tools' real `--version` output, first line, with where it was captured (2026-11-15, Windows 11 and
# Ubuntu 26.04 in WSL). phpstan, pint, phpcs and pnpm were run from a scratch `composer require --dev` and
# `npm install` (nothing installed on the machine), which is also where a project keeps them.
REAL_WEB_OUTPUT = {
    "php": [("PHP 8.4.25 (cli) (built: Aug 25 2026 18:38:47) (ZTS Visual C++ 2022 x64)\nCopyright (c) The PHP Group\n",
             "8.4.25", "PHP 8.4.25, Windows"),
            ("PHP 8.5.12 (cli) (built: Oct 28 2026 20:06:37) (NTS)\nCopyright (c) The PHP Group\n", "8.5.12",
             "PHP 8.5.12, Ubuntu")],
    "composer": [("Composer version 2.10.3 2026-08-27 13:34:23\nPHP version 8.5.12 (/usr/bin/php)\n", "2.10.3",
                  "Composer 2.10.3, Windows and Ubuntu (its second line names the PHP it runs on)")],
    "node": [("v24.22.2\n", "24.22.2", "Node 24.22.2, Windows"), ("v22.22.1\n", "22.22.1", "Node 22.22.1, Ubuntu")],
    "pnpm": [("12.21.0\n", "12.21.0", "pnpm 12.21.0, from a scratch npm install, Ubuntu")],
    "npm": [("11.19.1\n", "11.19.1", "npm 11.19.1, Windows"), ("9.2.0\n", "9.2.0", "npm 9.2.0, Ubuntu")],
    "phpstan": [("PHPStan - PHP Static Analysis Tool 2.3.5\n", "2.3.5",
                 "PHPStan 2.3.5, from a scratch composer install, Ubuntu")],
    "pint": [("Pint 1.32.3\n", "1.32.3", "Pint 1.32.3, from a scratch composer install, Ubuntu")],
    "phpcs": [("PHP_CodeSniffer version 4.0.4 (stable) by Squiz and PHPCSStandards\n", "4.0.4",
               "PHP_CodeSniffer 4.0.4, from a scratch composer install, Ubuntu")],
}
WEB_PINS = ".conclave/toolchain-web.json"
THEN = 1_700_000_000_000_000_000   # the time a fixture's compile database is given, in nanoseconds
LATER = THEN + 5_000_000_000
LSP_TABLE = ".conclave/lsp.json"
# Found before the fixtures narrow PATH to their stubs: the real clangd, for the one test that runs it.
CLANGD = shutil.which("clangd")
REAL_PATH = os.environ.get("PATH", "")


def command_line(*argv):
    """`forge.py <argv>` in process: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = forge.main([str(arg) for arg in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def doctor_usage_line():
    """The one line of forge.py's usage text that shows `doctor`: every kit is named on it (a test of the unattended
    kit reads them from that line, and CI went red on 2026-11-15 when it was wrapped over two)."""
    (line,) = [line for line in (forge.__doc__ or "").splitlines() if "forge.py doctor" in line]
    return line


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


class ToolchainFixture(unittest.TestCase):
    """A scratch project, stub tools on a scratch PATH and the doctor, for either toolchain kit."""

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
        pins = project / forge.TOOLCHAIN_PINS[self.KIT]
        pins.write_text(json.dumps({"schema_version": 1, "tools": list(tools)}), encoding="utf-8")

    def doctor(self, project, *extra):
        code, out, _err = command_line("doctor", project, self.KIT, *extra)
        report = json.loads(out)
        return code, report, {check["name"]: check for check in report["checks"]}

    def snapshot(self, folder):
        return {path.relative_to(folder).as_posix(): path.read_bytes()
                for path in folder.rglob("*") if path.is_file()}


class CppKitTests(ToolchainFixture):
    """D04 T02 section 2: the toolchain-cpp kit's seed pins, its install and its doctor."""

    def project(self, name="project", install=True, database=True, lsp=True):
        """A project with a current compile database (section 3) and the lsp kit beside this one (section 5: the
        table then holds clangd), so the doctor's other checks are read alone."""
        folder = super().project(name, install)
        if install and database:
            self.database(folder)
        if install and lsp:
            forge.apply_kit(folder, "lsp")
        return folder

    def database(self, project, rel="compile_commands.json", entries=None, when=THEN):
        """A compile database under the project: one entry whose source file exists, unless given."""
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if entries is None:
            (path.parent / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
            entries = [{"directory": str(path.parent), "file": "main.c", "command": "cc -c main.c"}]
        path.write_text(entries if isinstance(entries, str) else json.dumps(entries), encoding="utf-8")
        os.utime(path, ns=(when, when))
        return path

    def touch(self, path, when):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n", encoding="utf-8")
        os.utime(path, ns=(when, when))

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
        files = [".clangd", PINS, "scripts/cache-stats.py", "scripts/cc-cache.py", "scripts/compdb-check.py",
                 "scripts/tests/test_cc_cache.py", "scripts/tests/test_compdb_check.py",
                 "scripts/tests/test_toolchain_check.py", "scripts/toolchain-check.py"]
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
        self.assertIn("|toolchain-cpp|", doctor_usage_line().replace("[", "|").replace("]", "|"))
        for kit in forge.KIT_ORDER:
            self.assertIn(kit, doctor_usage_line(), "the doctor usage line omits a kit")
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
        project = self.project(lsp=False)
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

    # the compile database (section 3)

    def compdb_pins(self, project, **top):
        pins = project / PINS
        pins.write_text(json.dumps({"schema_version": 1, "tools": [self.pin("alpha")], **top}), encoding="utf-8")

    def test_the_doctor_reports_a_current_compile_database_at_the_pin_files_root_and_path(self):
        project = self.project(database=False)
        self.prints("alpha", "alpha v2.5.1\n")
        self.compdb_pins(project, root="engine", compdb={"path": "build/compile_commands.json"})
        self.database(project, "engine/build/compile_commands.json")
        (project / ".clangd").write_text("CompileFlags:" + chr(10) + "  CompilationDatabase: engine/build" + chr(10),
                                         encoding="utf-8")   # clangd is given the folder the check watches
        # Decoys the doctor must not read: at the project root and in the working directory.
        self.database(project, "compile_commands.json", entries="not json")
        elsewhere = self.work / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "compile_commands.json").write_text("[]", encoding="utf-8")
        cwd = os.getcwd()
        os.chdir(elsewhere)
        self.addCleanup(os.chdir, cwd)
        code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["missing_or_setup_required"]), (0, 0))
        self.assertEqual(checks["compile-database"], {"name": "compile-database", "status": "ok",
                                                     "detail": "engine/build/compile_commands.json, 1 entry"})
        for rel in ("scripts/compdb-check.py", "scripts/tests/test_compdb_check.py"):
            self.assertEqual(checks[rel]["status"], "ok")

    def test_a_compile_database_that_is_not_current_is_setup_required_with_the_reason(self):
        project = self.project(database=False)
        self.prints("alpha", "alpha v2.5.1\n")
        again = ["cmake", "-S", ".", "-B", "build"]
        self.compdb_pins(project, compdb={"regenerate": again})

        def found():
            code, report, checks = self.doctor(project, "--strict")
            self.assertEqual((code, report["missing_or_setup_required"]), (3, 1))
            self.assertEqual(checks["tool:alpha"]["status"], "ok")   # every other check is still listed
            self.assertEqual(checks["compile-database"]["status"], "setup_required")
            return checks["compile-database"]["detail"]

        line = ("; regenerate with (PowerShell): cmake -S '.' -B build" if os.name == "nt"
                else "; regenerate with (sh): cmake -S . -B build")
        self.assertEqual(found(), "missing: compile_commands.json does not exist" + line)
        self.database(project, entries="[]")
        self.assertEqual(found(), "invalid: compile_commands.json holds no entry, so it describes no build" + line)
        self.database(project, entries=[{"directory": str(project), "file": "a.c", "command": ""}])
        self.assertEqual(found(), "invalid: compile_commands.json: entry 1: `command` is not a command line" + line)
        (project / "compile_commands.json").unlink()
        (project / "compile_commands.json").mkdir()   # a database that cannot be read
        self.assertTrue(found().startswith("invalid: compile_commands.json cannot be read ("))
        (project / "compile_commands.json").rmdir()
        self.database(project)
        self.touch(project / "Makefile", LATER)
        self.assertEqual(found(), "stale: compile_commands.json: older than Makefile" + line)
        # The pin file's own build files: a configured file that is not one of the usual ones.
        self.compdb_pins(project, compdb={"build_files": ["cmake/flags.cmake"]})
        self.touch(project / "cmake/flags.cmake", THEN)
        code, _report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, checks["compile-database"]["status"]), (0, "ok"))   # the Makefile no longer counts
        self.touch(project / "cmake/flags.cmake", LATER)
        self.assertEqual(found(), "stale: compile_commands.json: older than cmake/flags.cmake")
        (project / "cmake/flags.cmake").unlink()
        self.assertEqual(found(), "unknown: compile_commands.json: a build file named by the pin file cannot be "
                                  "read, so its freshness cannot be told: cmake/flags.cmake (it does not exist)")

    def test_a_source_file_the_system_will_not_show_is_reported_and_the_doctor_finishes(self):
        # Found by the completion review of section 3: a permission error on a source file raised out of the
        # check, so the doctor printed no report.
        project = self.project(database=False)
        self.prints("alpha", "alpha v2.5.1\n")
        self.compdb_pins(project)
        self.database(project, entries=[{"directory": str(project), "file": "locked/a.c", "command": "cc -c a.c"}])
        real = pathlib.Path.stat

        def stat(path, *args, **kwargs):
            if path.parent.name == "locked":
                raise PermissionError(13, "Permission denied")
            return real(path, *args, **kwargs)

        with unittest.mock.patch.object(pathlib.Path, "stat", stat):
            code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["missing_or_setup_required"]), (3, 1))
        self.assertEqual(checks["tool:alpha"]["status"], "ok")
        self.assertEqual(checks["compile-database"], {
            "name": "compile-database", "status": "setup_required",
            "detail": "unknown: compile_commands.json: 1 source file(s) it names cannot be inspected, so its "
                      "freshness cannot be told: locked/a.c (Permission denied)"})
        # Found by the reconciliation: beside what makes the database stale, the file is still named.
        entries = [{"directory": str(project), "file": name, "command": "cc -c x.c"}
                   for name in ("locked/a.c", "deleted.c")]
        self.database(project, entries=entries)
        self.touch(project / "Makefile", LATER)
        with unittest.mock.patch.object(pathlib.Path, "stat", stat):
            code, _report, checks = self.doctor(project, "--strict")
        self.assertEqual(code, 3)
        self.assertEqual(checks["compile-database"]["detail"],
                         "stale: compile_commands.json: older than Makefile; 1 source file(s) it names no longer "
                         "exist: deleted.c; 1 source file(s) it names cannot be inspected: locked/a.c "
                         "(Permission denied)")

    def test_the_compile_database_check_starts_nothing_and_is_the_cpp_kits_alone(self):
        project = self.project(database=False)
        self.stub("marked", "with open(r'{dir}/ran', 'a') as mark:\n    mark.write('x')\n")
        self.compdb_pins(project, compdb={"regenerate": ["marked"]})
        self.prints("alpha", "alpha v2.5.1\n")
        _code, _report, checks = self.doctor(project)
        self.assertRegex(checks["compile-database"]["detail"], r"; regenerate with \((PowerShell|sh)\): marked$")
        self.assertFalse((self.work / "ran").exists(), "the doctor ran the regenerate command")
        # A pin file that does not load: no database check, as no tool check.
        (project / PINS).write_text('{"schema_version": 1, "tools": [], "compdb": {"path": "../x"}}',
                                    encoding="utf-8")
        _code, _report, checks = self.doctor(project)
        self.assertIn("compdb: path: a file inside the project", checks["tool-pins"]["detail"])
        self.assertNotIn("compile-database", checks)
        # The web kit's copy of the loader accepts the key, and its doctor has no such check.
        web = self.work / "web"
        web.mkdir()
        forge.apply_kit(web, "toolchain-web")
        (web / WEB_PINS).write_text(json.dumps({"schema_version": 1, "tools": [], "compdb": {}}), encoding="utf-8")
        code, out, _err = command_line("doctor", web, "toolchain-web")
        names = [check["name"] for check in json.loads(out)["checks"]]
        self.assertIn("tool-pins", names)
        self.assertNotIn("compile-database", names)

    # clangd (section 5)

    def clangd_settings(self, text):
        """The seed's settings, by a reader written for this test: `Section:` at the margin, `Key: value` under it."""
        settings, section = {}, None
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, _colon, value = line.strip().partition(":")
            if not line[0].isspace():
                section = key
                self.assertEqual(value.strip(), "", f"{key} is not written as a block")
            else:
                settings[f"{section}.{key}"] = value.strip()
        return settings

    def test_the_seed_holds_what_is_common_to_any_project_and_nothing_of_one(self):
        seed = (SDK_ROOT / "kits" / self.KIT / "templates/.clangd").read_text(encoding="utf-8")
        self.assertEqual(self.clangd_settings(seed), {
            "CompileFlags.CompilationDatabase": ".", "Index.Background": "Build",
            "Diagnostics.UnusedIncludes": "Strict", "Diagnostics.MissingIncludes": "None"})
        code = [line for line in seed.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        for line in code:
            for unwanted in ("--target", "-I", "Add:", "Remove:", "ClangTidy", "/", "\\", "-nostd", "-D"):
                self.assertNotIn(unwanted, line, f"the seed holds something of one project: {line.strip()}")
        self.assertEqual(forge._clangd_database(SDK_ROOT / "kits" / self.KIT / "templates/.clangd"), ("folder", "."))
        # A fresh install has it, and a project's own is kept byte for byte.
        fresh = self.project("fresh", lsp=False)
        self.assertEqual((fresh / ".clangd").read_text(encoding="utf-8"), seed)
        own = self.project("own", install=False)
        (own / ".clangd").write_bytes(b"CompileFlags:\n  Add: [--target=x86_64-elf]\n")
        result = forge.apply_kit(own, self.KIT)
        self.assertIn(".clangd", result["preserved"])
        self.assertEqual((own / ".clangd").read_bytes(), b"CompileFlags:\n  Add: [--target=x86_64-elf]\n")

    def table(self, project):
        return {server["name"]: server for server in forge._lsp_table_module().load_servers(project)}

    def test_clangd_is_added_to_the_table_in_either_order_of_the_two_kits(self):
        first = self.project("lsp-first", install=False)
        forge.apply_kit(first, "lsp")
        result = forge.apply_kit(first, self.KIT)
        self.assertEqual(result["lsp_servers"], {"added": ["clangd"], "kept": [], "differs": []})
        self.assertEqual(result["merge_needed"], [])
        second = self.project("cpp-first", install=False)
        result = forge.apply_kit(second, self.KIT)
        # Without the lsp kit nothing is written, and the result names the command that installs it.
        self.assertEqual(result["lsp_servers"], {"not_installed": f"python forge.py kit {second.as_posix()} lsp"})
        self.assertFalse((second / LSP_TABLE).exists())
        result = forge.apply_kit(second, "lsp")
        self.assertEqual(result["lsp_servers"], {"added": ["clangd"], "kept": [], "differs": []})
        self.assertEqual((second / LSP_TABLE).read_bytes(), (first / LSP_TABLE).read_bytes())
        entry = self.table(first)["clangd"]
        self.assertEqual((entry["command"], entry["root"], entry["extensions"][".c"]), (["clangd"], ".", "c"))
        # A second install adds nothing, and a dry run writes nothing and names it.
        self.assertEqual(forge.apply_kit(first, self.KIT)["lsp_servers"], {"added": [], "kept": ["clangd"],
                                                                         "differs": []})
        dry = self.project("dry", install=False)
        forge.apply_kit(dry, "lsp")
        before = self.snapshot(dry)
        self.assertEqual(forge.apply_kit(dry, self.KIT, dry_run=True)["lsp_servers"]["added"], ["clangd"])
        self.assertEqual(self.snapshot(dry), before)

    def test_the_entry_is_rooted_at_the_pin_files_root_and_a_generated_plugin_follows(self):
        project = self.project("rooted", install=False)
        forge.apply_kit(project, "lsp")
        (project / "engine").mkdir()
        (project / ".conclave").mkdir(exist_ok=True)
        (project / PINS).write_text(json.dumps({"schema_version": 1, "root": "engine", "tools": []}), encoding="utf-8")
        plugin = forge._lsp_plugin_module()
        plugin.write_plugin(project, [])
        result = forge.apply_kit(project, self.KIT)
        self.assertEqual(result["lsp_servers"]["added"], ["clangd"])
        self.assertEqual(self.table(project)["clangd"]["root"], "engine")
        listed = json.loads((project / plugin.FOLDER / plugin.SERVERS).read_text(encoding="utf-8"))
        self.assertEqual(listed["clangd"]["workspaceFolder"], "${CLAUDE_PROJECT_DIR}/engine")

    def test_a_projects_own_clangd_entry_is_never_changed_and_is_said_to_differ(self):
        project = self.project("own-entry", install=False)
        forge.apply_kit(project, "lsp")
        own = {"name": "clangd", "command": ["clangd-19", "--background-index"], "extensions": {".c": "c"},
               "install": "apt install clangd-19", "note": "the project's own"}
        (project / LSP_TABLE).write_text(json.dumps({"schema_version": 1, "servers": [own]}), encoding="utf-8")
        before = (project / LSP_TABLE).read_bytes()
        result = forge.apply_kit(project, self.KIT)
        self.assertEqual(result["lsp_servers"], {"added": [], "kept": ["clangd"], "differs": ["clangd"]})
        self.assertEqual(result["merge_needed"], [])
        self.assertEqual((project / LSP_TABLE).read_bytes(), before)
        # A table that does not load is reported and left as it was.
        (project / LSP_TABLE).write_text('{"schema_version": 1, "servers": [{"name": "x"}]}', encoding="utf-8")
        before = (project / LSP_TABLE).read_bytes()
        result = forge.apply_kit(project, self.KIT)
        self.assertIn("server 'x': missing key", result["lsp_servers"]["refused"])
        self.assertEqual(result["merge_needed"], [LSP_TABLE])
        self.assertEqual((project / LSP_TABLE).read_bytes(), before)

    def clangd_checks(self, project):
        checks = {check["name"]: check for check in forge.doctor_repo(project, self.KIT)["checks"]}
        self.assertIn("tool-pins", checks)   # the other checks are still reported
        return {name: (check["status"], check["detail"]) for name, check in checks.items()
                if name.startswith("clangd-")}

    def test_the_doctor_says_whether_the_table_has_clangd_and_how_to_add_it(self):
        project = self.project()
        self.assertEqual(self.clangd_checks(project)["clangd-server"], ("ok", f"{LSP_TABLE}: clangd, in ."))
        bare = self.project("no-lsp", lsp=False)
        self.assertEqual(self.clangd_checks(bare)["clangd-server"],
                         ("setup_required", f"no {LSP_TABLE}: install the lsp kit with python forge.py kit "
                                            f"{bare.as_posix()} lsp"))
        (project / LSP_TABLE).write_text('{"schema_version": 1, "servers": []}', encoding="utf-8")
        self.assertEqual(self.clangd_checks(project)["clangd-server"],
                         ("setup_required", f"{LSP_TABLE} has no clangd: python scripts/lsp-servers.py add cpp"))
        (project / LSP_TABLE).write_text("{", encoding="utf-8")
        status, detail = self.clangd_checks(project)["clangd-server"]
        self.assertEqual(status, "unexpected")
        self.assertTrue(detail.startswith(f"{LSP_TABLE}: "), detail)
        # A pin file whose root is not the project: the command carries it, and the entry it writes is rooted there.
        rooted = self.project("rooted")
        (rooted / "engine").mkdir()
        self.compdb_pins(rooted, root="engine")
        (rooted / LSP_TABLE).write_text('{"schema_version": 1, "servers": []}', encoding="utf-8")
        status, detail = self.clangd_checks(rooted)["clangd-server"]
        command = "python scripts/lsp-servers.py add cpp --root engine"
        self.assertEqual((status, detail), ("setup_required", f"{LSP_TABLE} has no clangd: {command}"))
        ran = subprocess.run([sys.executable, "-B", *command.split()[1:]], cwd=rooted, capture_output=True, text=True,
                             timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(self.table(rooted)["clangd"]["root"], "engine")
        self.assertEqual(self.clangd_checks(rooted)["clangd-server"], ("ok", f"{LSP_TABLE}: clangd, in engine"))
        # The web kit has no such checks.
        web = self.work / "web"
        web.mkdir()
        forge.apply_kit(web, "toolchain-web")
        names = [check["name"] for check in forge.doctor_repo(web, "toolchain-web")["checks"]]
        self.assertEqual([name for name in names if name.startswith("clangd")], [])

    def clangd_file(self, project, text):
        (project / ".clangd").write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))

    def test_the_doctor_compares_the_folder_clangd_reads_with_the_folder_the_database_is_in(self):
        project = self.project()
        self.assertEqual(self.clangd_checks(project)["clangd-config"],
                         ("ok", ".clangd: CompilationDatabase ., where the database is"))
        # A nested app: the check reads engine/compile_commands.json, clangd would read the decoy at the root.
        (project / "engine").mkdir()
        self.compdb_pins(project, root="engine")
        self.database(project, "engine/compile_commands.json")
        status, detail = self.clangd_checks(project)["clangd-config"]
        self.assertEqual(status, "unexpected")
        self.assertEqual(detail, ".clangd names CompilationDatabase ., and the database the freshness check watches "
                                 "is in engine: write `CompilationDatabase: engine`")
        self.clangd_file(project, "CompileFlags:\n  CompilationDatabase: engine\n")
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "ok")
        # The database in another folder. (A `build` folder of the folder clangd is given is searched by clangd
        # itself, so that one is no mismatch: see the test that runs clangd.)
        self.compdb_pins(project, compdb={"path": "build/compile_commands.json"})
        self.clangd_file(project, "CompileFlags:\n  CompilationDatabase: .\n")
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "ok")
        self.compdb_pins(project, compdb={"path": "out/compile_commands.json"})
        status, detail = self.clangd_checks(project)["clangd-config"]
        self.assertEqual((status, detail.endswith("write `CompilationDatabase: out`")), ("unexpected", True))
        self.compdb_pins(project, compdb={"path": "build/compile_commands.json"})
        self.clangd_file(project, "CompileFlags:\n  CompilationDatabase: src\n")
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "unexpected")
        for text in ("CompileFlags:\n  CompilationDatabase: build\n", 'CompileFlags:\n  CompilationDatabase: "build"\n',
                     "CompileFlags:\n  CompilationDatabase: 'build'   # the build folder\n",
                     "# clangd\nCompileFlags:\n  Remove: [-Werror]\n  CompilationDatabase: build # here\nIndex:\n"
                     "  Background: Build\n", "CompileFlags:\n  CompilationDatabase: ./build/\n"):
            with self.subTest(text=text):
                self.clangd_file(project, text)
                self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "ok")
        self.clangd_file(project, "CompileFlags:\n  CompilationDatabase: None\n")
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "unexpected")
        # A key of that name under another section is not the setting.
        self.compdb_pins(project, compdb={"path": "out/compile_commands.json"})
        self.clangd_file(project, "Index:\n  CompilationDatabase: out\n")
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "optional")

    def test_a_clangd_file_the_doctor_cannot_read_that_way_is_said_and_never_guessed(self):
        project = self.project()
        self.compdb_pins(project, compdb={"path": "out/compile_commands.json"})
        told = "whether clangd reads the database in out cannot be told from the file: it must be given " \
               "`CompilationDatabase: out`"
        cases = [("CompileFlags:\n  CompilationDatabase: build\n---\nIf:\n  PathMatch: .*\\.h\n",
                  "it holds more than one document"),
                 ("If:\n  PathMatch: src/.*\nCompileFlags:\n  CompilationDatabase: build\n", "it has a condition (`If:`)"),
                 ("CompileFlags: {CompilationDatabase: build}\n", "`CompileFlags` is not written as a block"),
                 ("Index:\n  Background: Build\n",
                  "it names no `CompilationDatabase`, so clangd searches the folders above each source file"),
                 ("CompileFlags:\n  CompilationDatabase: Ancestors\n",
                  "it names no `CompilationDatabase`, so clangd searches the folders above each source file")]
        for text, why in cases:
            with self.subTest(why=why):
                self.clangd_file(project, text)
                before = (project / ".clangd").read_bytes()
                self.assertEqual(self.clangd_checks(project)["clangd-config"], ("optional", f".clangd: {why}; {told}"))
                self.assertEqual((project / ".clangd").read_bytes(), before)
        self.clangd_file(project, b"CompileFlags:\n  CompilationDatabase: \xff\xfe\n")
        status, detail = self.clangd_checks(project)["clangd-config"]
        self.assertEqual(status, "unexpected")
        self.assertTrue(detail.startswith(".clangd cannot be read (not UTF-8"), detail)
        real = pathlib.Path.read_bytes

        def read_bytes(path):
            if path.name == ".clangd":
                raise PermissionError(13, "Permission denied")
            return real(path)

        with unittest.mock.patch.object(pathlib.Path, "read_bytes", read_bytes):
            self.assertEqual(self.clangd_checks(project)["clangd-config"],
                             ("unexpected", ".clangd cannot be read (Permission denied)"))
        # Absent: the kit's file check says it is missing, and there is no second line.
        (project / ".clangd").unlink()
        self.assertNotIn("clangd-config", self.clangd_checks(project))

    @unittest.skipUnless(CLANGD, "needs clangd on PATH")
    def test_clangd_itself_takes_its_flags_from_the_database_the_seed_names(self):
        # A real clangd, a real PATH: the fixture's scratch PATH holds only stubs.
        version = subprocess.run([CLANGD, "--version"], capture_output=True, text=True, timeout=60,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.splitlines()[0]
        project = self.project("real", database=False)
        (project / "main.c").write_text("#ifndef FROM_DATABASE\n#error the compile database was not read\n#endif\n"
                                        "int main(void) { return 0; }\n", encoding="utf-8")
        entry = {"directory": str(project), "file": "main.c", "arguments": ["clang", "-DFROM_DATABASE", "-c", "main.c"]}

        def diagnostics():
            env = dict(os.environ, PATH=str(pathlib.Path(CLANGD).parent) + os.pathsep + REAL_PATH)
            ran = subprocess.run([sys.executable, "-B", "scripts/lsp-diagnostics.py", "--server", "clangd", "main.c",
                                  "--json", "--settle", "2"], cwd=project, env=env, capture_output=True, text=True,
                                 timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            report = json.loads(ran.stdout)
            self.assertEqual(report["servers"]["clangd"]["status"], "ok", ran.stderr)
            return [row["message"] for row in report["diagnostics"] if row["severity"] == "error"]

        (project / "compile_commands.json").write_text(json.dumps([entry]), encoding="utf-8")
        seeded = diagnostics()
        print(f"\nclangd itself ({version}): with the seed and the database, errors: {seeded}")
        self.assertEqual(seeded, [], "clangd did not take the definition from the database the seed names")
        # The selection broken: a folder with no database.
        seed = (project / ".clangd").read_bytes()
        (project / "empty").mkdir()
        self.clangd_file(project, "CompileFlags:\n  CompilationDatabase: empty\n")
        broken = diagnostics()
        self.assertTrue(any("the compile database was not read" in message.lower() for message in broken), broken)
        # What the doctor's rule rests on, measured: given a folder, clangd finds the database in it and in its
        # `build` subfolder, and nowhere else. So the seed's `.` works for a database in build/ ...
        (project / ".clangd").write_bytes(seed)
        (project / "build").mkdir()
        (project / "compile_commands.json").rename(project / "build/compile_commands.json")
        self.compdb_pins(project, compdb={"path": "build/compile_commands.json"})
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "ok")
        in_build = diagnostics()
        self.assertEqual(in_build, [], "clangd did not find the database in the build folder of the folder named")
        # ... and not for one in any other folder, which is the case `clangd-config` reports.
        (project / "out").mkdir()
        (project / "build/compile_commands.json").rename(project / "out/compile_commands.json")
        self.compdb_pins(project, compdb={"path": "out/compile_commands.json"})
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "unexpected")
        elsewhere = diagnostics()
        self.assertTrue(any("the compile database was not read" in message.lower() for message in elsewhere),
                        elsewhere)
        self.clangd_file(project, "CompileFlags:\n  CompilationDatabase: out\n")
        self.assertEqual(self.clangd_checks(project)["clangd-config"][0], "ok")
        self.assertEqual(diagnostics(), [])
        print(f"clangd itself ({version}): errors with a folder that has no database: {len(broken)}; with the "
              f"database in build/ and the seed's `.`: {len(in_build)}; with it in out/ and the seed's `.`: "
              f"{len(elsewhere)}; after `CompilationDatabase: out`: 0")

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
        for word in ("`optional`", "`setup_required`", "`tool-pins`", "`tool:<name>`", "`compile-database`",
                     "`compdb`", "`path`", "`build_files`", "`regenerate`", "`current`", "`stale`", "`unknown`",
                     "`invalid`", "`missing`", "compdb-check.py --json", "`BUILD_NO_CCACHE`", "cc-cache.py",
                     "cache-stats.py --min-hit-rate", "`ccache`", "`sccache`", "`clangd-server`",
                     "`clangd-config`", "`CompilationDatabase`", "lsp-servers.py add cpp"):
            self.assertIn(word, readme)
        self.assertIn("`compdb`", (SDK_ROOT / "kits/toolchain-web/README.md").read_text(encoding="utf-8"))



class WebKitTests(ToolchainFixture):
    """D04 T02 section 6: the toolchain-web kit's seed, its install, its doctor, the project's own constraints and
    the language servers it adds to an LSP table."""

    KIT = "toolchain-web"

    def local_tool(self, folder, name, text):
        """A tool in a folder of the project, as Composer and npm install them."""
        folder.mkdir(parents=True, exist_ok=True)
        code = folder / f"{name}-stub.py"
        code.write_text(f"import sys\nsys.stdout.write({text!r})\n", encoding="utf-8")
        if os.name == "nt":
            launcher = folder / f"{name}.bat"
            launcher.write_text(f'@"{sys.executable}" "{code}" %*\r\n', encoding="utf-8")
        else:
            launcher = folder / name
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{code}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        return launcher

    def setUp(self):
        super().setUp()
        if os.name == "nt":
            os.environ["PATHEXT"] = ".CMD;.EXE;.BAT"  # restored with PATH by the fixture's patch

    def manifest(self, folder, name, document):
        folder.mkdir(parents=True, exist_ok=True)
        data = document if isinstance(document, bytes) else json.dumps(document).encode("utf-8")
        (folder / name).write_bytes(data)

    # the seed

    def test_the_seed_pins_seven_tools_and_names_the_projects_tool_folders(self):
        seed = self.module.load_pin_file(SDK_ROOT / "kits" / self.KIT / "templates" / WEB_PINS)
        self.assertEqual((seed["root"], seed["search"]), (".", ["vendor/bin", "node_modules/.bin"]))
        self.assertEqual([(tool["name"], tool["optional"], [c["command"] for c in tool["commands"]])
                          for tool in seed["tools"]],
                         [("php", False, ["php"]), ("composer", False, ["composer"]), ("node", False, ["node"]),
                          ("package-manager", False, ["pnpm", "npm"]), ("phpstan", True, ["phpstan"]),
                          ("pint", True, ["pint"]), ("phpcs", True, ["phpcs"])])
        # Intelephense has no version command: it is a language server, checked by the LSP kit's doctor.
        self.assertNotIn("intelephense", json.dumps(seed["tools"]))

    def test_each_seed_pattern_reads_the_version_from_that_programs_real_output(self):
        seed = self.module.load_pins(SDK_ROOT / "kits" / self.KIT / "templates" / WEB_PINS)
        entries = {entry["command"]: (tool, entry) for tool in seed for entry in tool["commands"]}
        self.assertEqual(sorted(entries), sorted(REAL_WEB_OUTPUT))
        for name, samples in REAL_WEB_OUTPUT.items():
            tool, entry = entries[name]
            for text, version, source in samples:
                with self.subTest(command=name, source=source):
                    self.prints(name, text)
                    result = self.module.check_tool(dict(tool, commands=[entry]))
                    self.assertEqual((result["status"], result["version"]), ("ok", version), result["detail"])
            (self.bin / (f"{name}.cmd" if os.name == "nt" else name)).unlink()

    # the install and the app's folder

    def test_init_and_kit_install_and_record_the_kit_and_keep_a_projects_own_pins(self):
        files = [WEB_PINS, "scripts/tests/test_toolchain_check.py", "scripts/toolchain-check.py"]
        for name, argv in (("by-init", ("init", "{}", "--kit", self.KIT)), ("by-kit", ("kit", "{}", self.KIT))):
            with self.subTest(command=argv[0]):
                project = self.project(name, install=False)
                code, _out, err = command_line(*(str(project) if arg == "{}" else arg for arg in argv))
                self.assertEqual(code, 0, err)
                record = json.loads((project / forge.RECORD).read_text(encoding="utf-8"))
                self.assertIn(self.KIT, record["kits"])
                for rel in files:
                    self.assertEqual(record["files"][rel]["kit"], self.KIT)
        project = self.project("twice", install=False)
        first = forge.apply_kit(project, self.KIT)
        self.assertEqual((first["installed"], first["app_root"]), (files, "."))
        before = self.snapshot(project)
        second = forge.apply_kit(project, self.KIT)
        self.assertEqual((second["installed"], second["preserved"]), ([], files))
        self.assertEqual(self.snapshot(project), before)
        owned = self.project("owned", install=False)
        own = b'{"schema_version": 1, "tools": []}\r\n'
        (owned / ".conclave").mkdir()
        (owned / WEB_PINS).write_bytes(own)
        self.manifest(owned / "platform", "composer.json", {})  # a nested app does not rewrite the project's file
        result = forge.apply_kit(owned, self.KIT)
        self.assertIn(WEB_PINS, result["preserved"])
        self.assertEqual(((owned / WEB_PINS).read_bytes(), result["app_root"]), (own, "platform"))
        dry = self.project("dry", install=False)
        self.manifest(dry / "platform", "composer.json", {})
        self.assertEqual(forge.apply_kit(dry, self.KIT, dry_run=True)["app_root"], "platform")
        self.assertFalse((dry / ".conclave").exists())

    def test_a_nested_apps_pin_file_is_written_once_with_its_root_and_a_seed_left_without_it_is_repaired(self):
        # Found by the round and the reconciliations of D04 T02 section 6. Copying the seed and adding the root in a
        # second step left a seed with no root when the install stopped between the two, and completing it later
        # meant changing a file the project already had. The file is written once, with its root.
        seed = (SDK_ROOT / "kits" / self.KIT / "templates" / WEB_PINS).read_bytes()
        project = self.project("interrupted", install=False)
        self.manifest(project / "platform", "composer.json", {"require": {"php": "^8.3"}})
        with unittest.mock.patch.object(forge, "_fill_lsp_table", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):  # stopped at the first step after the files are written
                forge.apply_kit(project, self.KIT)
        self.assertEqual(self.module.load_pin_file(project / WEB_PINS)["root"], "platform")
        self.assertNotEqual((project / WEB_PINS).read_bytes(), seed)
        written = (project / WEB_PINS).read_bytes()
        result = forge.apply_kit(project, self.KIT)
        self.assertEqual(result["app_root"], "platform")
        self.assertIn(WEB_PINS, result["preserved"])
        self.assertNotIn("repaired", result)
        self.assertEqual((project / WEB_PINS).read_bytes(), written)
        # A fresh install lists the file as installed and records it like every installed file: its kit and the
        # digest of the bytes written. `diff` then finds it identical to what the kit holds for this project, and
        # `update` has nothing to do with it.
        fresh = self.project("fresh", install=False)
        self.manifest(fresh / "platform", "package.json", {})
        installed = forge.apply_kit(fresh, self.KIT)
        self.assertIn(WEB_PINS, installed["installed"])
        entry = json.loads((fresh / forge.RECORD).read_text(encoding="utf-8"))["files"][WEB_PINS]
        self.assertEqual(entry, {"kit": self.KIT, "sha256": forge.file_digest((fresh / WEB_PINS).read_bytes())})
        self.assertNotEqual((fresh / WEB_PINS).read_bytes(), seed)
        code, out, err = command_line("diff", fresh, self.KIT)
        self.assertEqual(code, 0, err)
        states = {item["path"]: item["state"] for kit in json.loads(out)["kits"].values() for item in kit["files"]}
        self.assertEqual(states[WEB_PINS], "identical")
        rooted = (fresh / WEB_PINS).read_bytes()
        code, _out, err = command_line("update", fresh, self.KIT)
        self.assertEqual(code, 0, err)
        self.assertEqual((fresh / WEB_PINS).read_bytes(), rooted)
        # When the one write fails nothing is left behind, the command says why, and the next install completes.
        failing = self.project("failing", install=False)
        self.manifest(failing / "platform", "package.json", {})
        real = forge.atomic_write

        def refuse_the_pin(path, data):
            if pathlib.Path(path).name.startswith("toolchain-web.json"):  # the file, staged beside itself
                raise PermissionError(13, "Access is denied")
            return real(path, data)

        with unittest.mock.patch.object(forge, "atomic_write", refuse_the_pin):
            code, out, err = command_line("kit", failing, self.KIT)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Access is denied", err)
        self.assertFalse((failing / WEB_PINS).exists())
        self.assertEqual(forge.apply_kit(failing, self.KIT)["app_root"], "platform")
        self.assertEqual(self.module.load_pin_file(failing / WEB_PINS)["root"], "platform")
        # A pin file the project has changed in any way is never touched.
        edited = self.project("owned-edited", install=False)
        (edited / ".conclave").mkdir()
        (edited / WEB_PINS).write_bytes(seed.replace(b'"8.2"', b'"8.3"'))
        self.manifest(edited / "platform", "composer.json", {})
        kept = forge.apply_kit(edited, self.KIT)
        self.assertEqual(kept["app_root"], "platform")
        self.assertIn(WEB_PINS, kept["preserved"])
        self.assertNotIn("repaired", kept)
        self.assertEqual((edited / WEB_PINS).read_bytes(), seed.replace(b'"8.2"', b'"8.3"'))
        # The one exception: a pin file that is still the kit's seed byte for byte, in a project whose app is not at
        # the root, is what an install stopped between the seed's copy and its root left behind. It is not yet the
        # project's: the next install gives it its root and says so, as repaired, never as preserved or installed.
        left = self.project("owned-seed", install=False)
        (left / ".conclave").mkdir()
        (left / WEB_PINS).write_bytes(seed)
        self.manifest(left / "platform", "composer.json", {})
        dry = forge.apply_kit(left, self.KIT, dry_run=True)
        self.assertEqual(dry["repaired"], [WEB_PINS])
        self.assertEqual((left / WEB_PINS).read_bytes(), seed)  # a dry run writes nothing
        repaired = forge.apply_kit(left, self.KIT)
        self.assertEqual((repaired["app_root"], repaired["repaired"]), ("platform", [WEB_PINS]))
        self.assertNotIn(WEB_PINS, repaired["preserved"])
        self.assertNotIn(WEB_PINS, repaired["installed"])
        self.assertEqual(self.module.load_pin_file(left / WEB_PINS)["root"], "platform")
        entry = json.loads((left / forge.RECORD).read_text(encoding="utf-8"))["files"][WEB_PINS]
        self.assertEqual(entry, {"kit": self.KIT, "sha256": forge.file_digest((left / WEB_PINS).read_bytes())})
        settled = forge.apply_kit(left, self.KIT)  # with its root it is the project's: preserved from then on
        self.assertIn(WEB_PINS, settled["preserved"])
        self.assertNotIn("repaired", settled)
        # The same seed in a project whose app is at the root is simply the project's pin file: preserved.
        flat = self.project("flat-seed", install=False)
        (flat / ".conclave").mkdir()
        (flat / WEB_PINS).write_bytes(seed)
        self.manifest(flat, "composer.json", {})
        unchanged = forge.apply_kit(flat, self.KIT)
        self.assertIn(WEB_PINS, unchanged["preserved"])
        self.assertNotIn("repaired", unchanged)
        self.assertEqual((flat / WEB_PINS).read_bytes(), seed)

    def test_the_kit_is_detected_by_its_own_pin_file_and_named_where_forge_lists_kits(self):
        project = self.project(install=False)
        forge.apply_kit(project, "toolchain-cpp")
        kits = forge.check_repo(project)["kits"]
        self.assertIn("toolchain-cpp", kits)
        self.assertNotIn(self.KIT, kits)  # the shared check script is not this kit
        forge.apply_kit(project, self.KIT)
        self.assertIn(self.KIT, forge.check_repo(project)["kits"])
        self.assertLess(forge.KIT_ORDER.index("toolchain-cpp"), forge.KIT_ORDER.index(self.KIT))
        self.assertIn("|toolchain-web|", doctor_usage_line().replace("[", "|").replace("]", "|"))
        for command in ("init", "kit"):
            self.assertIn(self.KIT, command_line(command, "--help")[1], command)
        self.assertIn("'toolchain-web'", forge.apply_kit.__doc__ or "")

    def test_the_apps_folder_is_found_written_and_read_by_everything(self):
        for folder in (".", "platform", "backend"):
            with self.subTest(app=folder):
                project = self.project(f"app-{folder.strip('.') or 'root'}", install=False)
                app = project if folder == "." else project / folder
                (project / "aaa-docs").mkdir()  # an earlier child with no manifest is passed
                self.manifest(app, "composer.json", {"require": {"php": "^8.3"}})
                forge.apply_kit(project, "lsp")
                result = forge.apply_kit(project, self.KIT)
                self.assertEqual(result["app_root"], folder)
                written = json.loads((project / WEB_PINS).read_text(encoding="utf-8"))
                self.assertEqual(written.get("root", "."), folder)
                self.assertEqual("root" in written, folder != ".")
                self.assertEqual(self.module.load_pin_file(project / WEB_PINS)["root"], folder)
                # The doctor, run from an unrelated working directory, reads the app's folder for all three.
                local = self.local_tool(app / "vendor/bin", "phpstan", "PHPStan - PHP Static Analysis Tool 2.3.5\n")
                held = os.getcwd()
                os.chdir(self.work)
                try:
                    _code, _report, checks = self.doctor(project)
                finally:
                    os.chdir(held)
                self.assertEqual(checks["tool:phpstan"]["status"], "ok")
                self.assertTrue(os.path.samefile(checks["tool:phpstan"]["detail"].rsplit(" ", 1)[0], local))
                self.assertIn("composer.json requires php ^8.3", checks["constraint:php"]["detail"])
                self.assertEqual(result["lsp_servers"], {"added": ["intelephense"], "kept": []})
                (server,) = forge._lsp_table_module().load_servers(project)
                self.assertEqual((server["name"], server["root"]), ("intelephense", folder))

    # the doctor

    def test_the_doctor_reports_required_and_optional_tools_and_the_bare_form_starts_none(self):
        project = self.project()
        self.stub("marked", "with open(r'{dir}/ran', 'a') as mark:\n    mark.write('x')\nprint('marked v2.5')\n")
        self.write_pins(project, self.pin("marked"), self.pin("absent"), self.pin("spare", optional=True))
        code, out, _err = command_line("doctor", project)
        self.assertEqual((code, json.loads(out)["kit"]), (0, "base"))
        self.assertFalse((self.work / "ran").exists(), "the bare doctor started a pinned tool")
        code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["missing_or_setup_required"]), (3, 1))
        self.assertEqual([checks[f"tool:{name}"]["status"] for name in ("marked", "absent", "spare")],
                         ["ok", "setup_required", "optional"])
        self.assertEqual(checks["tool-pins"]["detail"], f"{WEB_PINS}: marked, absent, spare")

    def constraint_project(self, name, minimum, manifests):
        """A project whose pin file holds php and node at `minimum`, both installed, with the given manifests."""
        project = self.project(name)
        self.prints("php", "php v9.9\n")
        self.prints("node", "node v99.0\n")
        self.write_pins(project, self.pin("php", minimum=minimum["php"]), self.pin("node", minimum=minimum["node"]))
        for manifest, document in manifests.items():
            self.manifest(project, manifest, document)
        return project

    def test_a_pin_below_the_projects_own_constraint_is_unexpected_for_php_and_for_node(self):
        project = self.constraint_project("low", {"php": "8.2", "node": "18"}, {
            "composer.json": {"require": {"php": "^8.3", "laravel/framework": "^12.0"}},
            "package.json": {"engines": {"node": ">=20"}}})
        code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["missing_or_setup_required"]), (3, 2))
        self.assertEqual(checks["constraint:php"], {
            "name": "constraint:php", "status": "unexpected",
            "detail": "composer.json requires php ^8.3 and the pin accepts 8.2: "
                      "raise min_version of the php pin to 8.3"})
        self.assertEqual(checks["constraint:node"], {
            "name": "constraint:node", "status": "unexpected",
            "detail": "package.json requires node >=20 and the pin accepts 18: "
                      "raise min_version of the node pin to 20"})
        self.assertEqual((checks["tool:php"]["status"], checks["tool:node"]["status"]), ("ok", "ok"))

    def test_a_pin_the_constraint_satisfies_is_ok_with_both_shown(self):
        project = self.constraint_project("fine", {"php": "8.3", "node": "22"}, {
            "composer.json": {"require": {"php": "^8.2 || ^8.3"}}, "package.json": {"engines": {"node": "20.x"}}})
        code, report, checks = self.doctor(project, "--strict")
        self.assertEqual((code, report["missing_or_setup_required"]), (0, 0))
        self.assertEqual((checks["constraint:php"]["status"], checks["constraint:php"]["detail"]),
                         ("ok", "composer.json requires php ^8.2 || ^8.3; the pin's minimum is 8.3"))
        self.assertEqual((checks["constraint:node"]["status"], checks["constraint:node"]["detail"]),
                         ("ok", "package.json requires node 20.x; the pin's minimum is 22"))

    def test_a_constraint_of_unknown_form_is_ok_and_said_to_be_not_compared(self):
        project = self.constraint_project("unknown", {"php": "8.2", "node": "18"}, {
            "composer.json": {"require": {"php": "<9"}}, "package.json": {"engines": {"node": "*"}}})
        code, _report, checks = self.doctor(project, "--strict")
        self.assertEqual(code, 0)
        for name in ("php", "node"):
            self.assertEqual(checks[f"constraint:{name}"]["status"], "ok")
            self.assertIn("a form the doctor does not compare", checks[f"constraint:{name}"]["detail"])

    def test_no_manifest_no_constraint_or_no_pin_of_that_name_is_no_check(self):
        neither = self.constraint_project("neither", {"php": "8.2", "node": "18"}, {})
        silent = self.constraint_project("silent", {"php": "8.2", "node": "18"}, {
            "composer.json": {"require": {"laravel/framework": "^12.0"}}, "package.json": {"name": "app"}})
        for project in (neither, silent):
            _code, _report, checks = self.doctor(project)
            self.assertEqual([name for name in checks if name.startswith("constraint:")], [])
        unpinned = self.project("unpinned")
        self.write_pins(unpinned, self.pin("composer"))
        self.manifest(unpinned, "composer.json", {"require": {"php": "^8.3"}})
        self.manifest(unpinned, "package.json", {"engines": {"node": ">=20"}})
        _code, _report, checks = self.doctor(unpinned)
        self.assertEqual([name for name in checks if name.startswith("constraint:")], [])

    def test_the_lowest_version_of_each_constraint_form_is_read(self):
        compare = self.module.compare_versions
        forms = {"^8.3": "8.3", ">=8.3": "8.3", "~8.3.0": "8.3.0", "8.3.*": "8.3", "^8.2 || ^8.3": "8.2",
                 "^8.2|^8.3": "8.2", "^8.3 || ^8.2": "8.2", ">=20": "20", "20.x": "20", ">=8.2 <8.5": "8.2",
                 "^20.0.0 || >=22": "20.0.0", "v22.1": "22.1", "=8.3.1": "8.3.1", ">=8.2, <9": "8.2"}
        for constraint, lowest in forms.items():
            with self.subTest(constraint=constraint):
                self.assertEqual(forge._lowest_allowed(constraint, compare), lowest)
        for constraint in ("*", "<9", ">8.2", "dev-main", "latest", "", "^8.3 || *", "8.x.y"):
            with self.subTest(unknown=constraint):
                self.assertIsNone(forge._lowest_allowed(constraint, compare))

    def test_every_comparator_of_a_constraint_is_read_not_only_the_first(self):
        # Found by the round of D04 T02 section 6: `>=8.2 >=8.3` was read as 8.2, and the pin at 8.2 as fine.
        compare = self.module.compare_versions
        forms = {">=8.2 >=8.3": "8.3", ">=8.2, >=8.3": "8.3", ">=8.3 >=8.2": "8.3", "^8.2 >=8.2.5": "8.2.5",
                 ">=8.2 <8.5": "8.2", "<8.5 >=8.2": "8.2", ">=8.2,<9": "8.2", ">=20 <=22": "20",
                 ">=8.2 >=8.3 || ^8.4": "8.3", "^8.4 || >=8.2 >=8.3": "8.3", "~8.2.0 >=8.2.3 <8.3": "8.2.3"}
        for constraint, lowest in forms.items():
            with self.subTest(constraint=constraint):
                self.assertEqual(forge._lowest_allowed(constraint, compare), lowest)
        # A comparator the doctor does not read makes the whole constraint not compared, never a guess.
        for constraint in (">=8.2 !=8.2.5", ">=8.2 >8.3", "8.2 - 8.4", ">=8.2 dev-main", "<9 <10", ">=8.2 ||"):
            with self.subTest(unknown=constraint):
                self.assertIsNone(forge._lowest_allowed(constraint, compare))
        project = self.constraint_project("both-bounds", {"php": "8.2", "node": "18"}, {
            "composer.json": {"require": {"php": ">=8.2 >=8.3"}}, "package.json": {"engines": {"node": ">=18 >=20"}}})
        code, _report, checks = self.doctor(project, "--strict")
        self.assertEqual(code, 3)
        self.assertIn("raise min_version of the php pin to 8.3", checks["constraint:php"]["detail"])
        self.assertIn("raise min_version of the node pin to 20", checks["constraint:node"]["detail"])

    def test_a_manifest_that_cannot_be_used_is_unexpected_and_the_rest_is_still_reported(self):
        cases = {b"{": "is not JSON in UTF-8", b"\xff\xfe{}": "is not JSON in UTF-8", b"null": "is not a JSON object",
                 b"[]": "is not a JSON object", b'{"require": [], "engines": []}': "is not an object",
                 b'{"require": {"php": 8}, "engines": {"node": 20}}': "is not a version constraint as text",
                 b'{"require": {"php": ""}, "engines": {"node": " "}}': "is not a version constraint as text"}
        for number, (data, expected) in enumerate(cases.items()):
            with self.subTest(manifest=data):
                project = self.constraint_project(f"broken-{number}", {"php": "8.2", "node": "18"},
                                                  {"composer.json": data, "package.json": data})
                code, _report, checks = self.doctor(project, "--strict")
                self.assertEqual(code, 3)
                for name in ("php", "node"):
                    self.assertEqual(checks[f"constraint:{name}"]["status"], "unexpected")
                    self.assertIn(expected, checks[f"constraint:{name}"]["detail"])
                self.assertEqual((checks["tool:php"]["status"], checks["tool:node"]["status"]), ("ok", "ok"))
        project = self.constraint_project("locked", {"php": "8.2", "node": "18"},
                                          {"composer.json": {"require": {"php": "^8.3"}}})
        real = pathlib.Path.read_bytes

        def locked(path):
            if path.name == "composer.json":
                raise PermissionError(13, "Permission denied")
            return real(path)

        with unittest.mock.patch.object(pathlib.Path, "read_bytes", locked):
            _code, _report, checks = self.doctor(project)
        self.assertEqual(checks["constraint:php"]["status"], "unexpected")
        self.assertIn("composer.json cannot be read (Permission denied)", checks["constraint:php"]["detail"])
        self.assertEqual(checks["tool:node"]["status"], "ok")

    # the language servers

    def stack_project(self, name, lsp=True):
        project = self.project(name, install=False)
        self.manifest(project, "composer.json", {"require": {"php": "^8.3"}})
        self.manifest(project, "package.json", {"engines": {"node": ">=20"}})
        if lsp:
            forge.apply_kit(project, "lsp")
        return project

    def servers(self, project):
        return [server["name"] for server in forge._lsp_table_module().load_servers(project)]

    def test_the_stacks_servers_are_added_to_an_lsp_table_and_a_projects_own_entry_is_kept(self):
        project = self.stack_project("both")
        result = forge.apply_kit(project, self.KIT)
        self.assertEqual(result["lsp_servers"], {"added": ["intelephense", "typescript", "tailwindcss"], "kept": []})
        self.assertEqual(self.servers(project), ["intelephense", "typescript", "tailwindcss"])
        self.assertEqual(result["merge_needed"], [])
        again = forge.apply_kit(project, self.KIT)
        self.assertEqual(again["lsp_servers"], {"added": [], "kept": ["intelephense", "typescript", "tailwindcss"]})
        # A table that already has intelephense with the project's own command keeps it.
        own = self.stack_project("own")
        mine = {"name": "intelephense", "command": ["intelephense", "--stdio", "--mine"],
                "extensions": {".php": "php"}, "install": "ours"}
        (own / LSP_TABLE).write_text(json.dumps({"schema_version": 1, "servers": [mine]}), encoding="utf-8")
        result = forge.apply_kit(own, self.KIT)
        self.assertEqual(result["lsp_servers"], {"added": ["typescript", "tailwindcss"], "kept": ["intelephense"]})
        loaded = forge._lsp_table_module().load_servers(own)
        self.assertEqual(loaded[0]["command"], ["intelephense", "--stdio", "--mine"])
        # Only the manifests the app has decide the presets.
        php_only = self.project("php-only", install=False)
        self.manifest(php_only, "composer.json", {})
        forge.apply_kit(php_only, "lsp")
        self.assertEqual(forge.apply_kit(php_only, self.KIT)["lsp_servers"], {"added": ["intelephense"], "kept": []})

    def test_without_the_lsp_kit_nothing_is_written_and_one_command_recovers(self):
        project = self.stack_project("later", lsp=False)
        result = forge.apply_kit(project, self.KIT)
        self.assertEqual(result["lsp_servers"], {"not_installed": f"python forge.py kit {project.as_posix()} lsp"})
        self.assertFalse((project / LSP_TABLE).exists())
        code, out, err = command_line("kit", project, "lsp")  # the command the result named
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["lsp_servers"],
                         {"added": ["intelephense", "typescript", "tailwindcss"], "kept": []})
        self.assertEqual(self.servers(project), ["intelephense", "typescript", "tailwindcss"])
        # A project with the LSP kit and no toolchain kit has nothing to add and says nothing.
        plain = self.project("plain", install=False)
        self.assertNotIn("lsp_servers", forge.apply_kit(plain, "lsp"))

    def test_a_table_that_does_not_load_or_cannot_be_written_is_reported_and_left_as_it_was(self):
        project = self.stack_project("broken")
        (project / LSP_TABLE).write_text('{"schema_version": 1, "servers": [{"name": "x"}]}', encoding="utf-8")
        before = (project / LSP_TABLE).read_bytes()
        result = forge.apply_kit(project, self.KIT)
        self.assertEqual(list(result["lsp_servers"]), ["refused"])
        self.assertIn(".conclave/lsp.json: server 'x': missing key", result["lsp_servers"]["refused"])
        self.assertIn(LSP_TABLE, result["merge_needed"])
        self.assertEqual((project / LSP_TABLE).read_bytes(), before)
        # A table that loads and cannot be written: the kit's pin file is in place, the replace is refused.
        locked = self.stack_project("locked")
        (locked / WEB_PINS).write_bytes((SDK_ROOT / "kits" / self.KIT / "templates" / WEB_PINS).read_bytes())
        before = (locked / LSP_TABLE).read_bytes()
        with unittest.mock.patch.object(os, "replace", side_effect=PermissionError(13, "Access is denied")):
            failed = forge._fill_lsp_table(locked, dry_run=False)
        self.assertEqual(failed, {"failed": ".conclave/lsp.json: cannot be written (Access is denied)",
                                  "retry": f"python forge.py kit {locked.as_posix()} toolchain-web"})
        self.assertEqual((locked / LSP_TABLE).read_bytes(), before)
        self.assertEqual(sorted(path.name for path in (locked / ".conclave").iterdir()),
                         ["kits.json", "lsp.json", "toolchain-web.json"])
        retried = forge.apply_kit(locked, self.KIT)  # the retry the result named
        self.assertEqual(retried["lsp_servers"], {"added": ["intelephense", "typescript", "tailwindcss"], "kept": []})

    def test_a_dry_run_writes_no_server(self):
        project = self.stack_project("dry")
        before = self.snapshot(project)
        result = forge.apply_kit(project, self.KIT, dry_run=True)
        self.assertEqual(result["lsp_servers"], {"added": ["intelephense", "typescript", "tailwindcss"], "kept": []})
        self.assertEqual(self.snapshot(project), before)

    def test_the_readme_lists_every_file_tool_command_and_check(self):
        readme = (SDK_ROOT / "kits" / self.KIT / "README.md").read_text(encoding="utf-8")
        templates = SDK_ROOT / "kits" / self.KIT / "templates"
        for path in sorted(templates.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                self.assertIn(f"`{path.relative_to(templates).as_posix()}`", readme)
        seed = self.module.load_pin_file(templates / WEB_PINS)
        for tool in seed["tools"]:
            self.assertIn(f"`{tool['name']}`", readme)
            for entry in tool["commands"]:
                self.assertIn(f"`{entry['command']}`", readme)
        for word in ("`search`", "`root`", "`vendor/bin`", "`node_modules/.bin`", "`tool-pins`", "`tool:<name>`",
                     "`constraint:php`", "`constraint:node`", "`optional`", "`unexpected`", "`php`", "`web`"):
            self.assertIn(word, readme)
        for word in ("`search`", "`root`"):
            self.assertIn(word, (SDK_ROOT / "kits/toolchain-cpp/README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
