"""hardening-check.py: a project's declared hardening held to its compile commands (D04 T03 section 1): how each
entry's flags are read, which entries are the project's own, what is unknown, the output and the exit codes."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hardening_check", SCRIPTS / "hardening-check.py")
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)

THEN = 1_700_000_000_000_000_000   # the time every fixture file is given, in nanoseconds
LATER = THEN + 5_000_000_000
STL = "_MSVC_STL_HARDENING=1"


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name).resolve()
        self.project = self.dir / "project"
        (self.project / ".conclave").mkdir(parents=True)
        cwd = os.getcwd()
        os.chdir(self.dir)
        self.addCleanup(os.chdir, cwd)

    def pins(self, hardening=None, **top):
        document = {"schema_version": 1, "tools": [], **top}
        if hardening is not None:
            document["hardening"] = hardening
        path = self.project / ".conclave/toolchain-cpp.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def file(self, rel, text="int main(void) { return 0; }\n", when=THEN, data=None):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if data is not None:
            path.write_bytes(data)
        else:
            path.write_text(text, encoding="utf-8")
        os.utime(path, ns=(when, when))
        return path

    def entry(self, source, flags, compiler="c++", command=False):
        """An entry compiling `source` (created) with `flags`, as `arguments` or as one `command` string."""
        self.file(source)
        argv = [compiler, *flags, "-c", source]
        entry = {"directory": str(self.project), "file": source}
        entry.update({"command": " ".join(argv)} if command else {"arguments": argv})
        return entry

    def database(self, entries, when=THEN):
        return self.file("compile_commands.json", entries if isinstance(entries, str) else json.dumps(entries), when)

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = hc.main(["--root", str(self.project), *[str(arg) for arg in argv]])
        return code, out.getvalue(), err.getvalue()

    def both(self):
        """The check as text and as JSON: (exit, status, the text, the JSON document). The two must agree."""
        code, text, err = self.run_main()
        json_code, document, _err = self.run_main("--json")
        report = json.loads(document)
        self.assertEqual((json_code, err), (code, ""))
        self.assertEqual(text.splitlines()[0], f"hardening:compile: {report['status']}: {report['detail']}")
        self.assertEqual(code, {"ok": 0, "none": 0, "unknown": 1, "missing": 3}[report["status"]])
        return code, report["status"], text, report

    def policy(self, *required, **keys):
        self.pins({"compile": list(required), **keys})


class PolicyTests(Fixture):
    def test_a_project_with_no_policy_gets_no_finding(self):
        self.pins()
        code, status, text, report = self.both()
        self.assertEqual((code, status, report["policy"]), (0, "none", None))
        self.assertIn("no policy declared", text)
        self.assertEqual(report["requirements"], [])

    def test_json_prints_the_loaded_policy(self):
        self.policy(STL, "/guard:cf", exclude=["third_party"])
        self.database([self.entry("src/a.cpp", [f"/D{STL}", "/guard:cf"], compiler="cl.exe")])
        code, status, _text, report = self.both()
        self.assertEqual((code, status), (0, "ok"))
        self.assertEqual(report["policy"], {"compile": [STL, "/guard:cf"], "sources": ["."],
                                            "exclude": ["third_party"]})

    def test_a_policy_that_does_not_load_exits_2_with_the_loaders_refusal(self):
        path = self.pins({"compile": [STL, 7]})
        code, out, err = self.run_main()
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err.strip(), f"hardening-check: {path.as_posix()}: hardening: compile: each entry is a "
                                      "definition or option on one line without spaces around it, not 7")
        code, out, _err = self.run_main("--json")
        self.assertEqual((code, json.loads(out)["status"]), (2, "refused"))


class MatchTests(Fixture):
    def test_every_entry_hardened_passes_with_one_line_per_requirement(self):
        self.policy(STL, "/guard:cf")
        self.database([self.entry(f"src/{name}.cpp", [f"/D{STL}", "/guard:cf"], compiler="cl.exe")
                       for name in ("a", "b", "c")])
        code, status, text, report = self.both()
        self.assertEqual((code, status), (0, "ok"))
        self.assertEqual(report["checked"], 3)
        self.assertEqual(text.splitlines()[1:], [f"  ok       {STL}", "  ok       /guard:cf"])

    def test_one_unhardened_first_party_source_exits_3_naming_the_requirement_and_the_source(self):
        # The other entries carry it, so a search over the whole file would pass.
        self.policy(STL)
        entries = [self.entry("src/a.cpp", [f"/D{STL}"], compiler="cl.exe"),
                   self.entry("src/b.cpp", [], compiler="cl.exe"),
                   self.entry("src/c.cpp", [f"/D{STL}"], compiler="cl.exe")]
        self.database(entries)
        code, status, text, report = self.both()
        self.assertEqual((code, status), (3, "missing"))
        self.assertEqual(report["requirements"], [{"requirement": STL, "status": "missing", "lacking": 1,
                                                   "first": "src/b.cpp"}])
        self.assertIn(f"  missing  {STL}: on 1 entry, first src/b.cpp", text)

    def test_the_last_occurrence_on_a_command_wins(self):
        pairs = [("_GLIBCXX_ASSERTIONS", "g++", ["-D_GLIBCXX_ASSERTIONS"], ["-U_GLIBCXX_ASSERTIONS"]),
                 ("_GLIBCXX_ASSERTIONS", "g++", ["-D", "_GLIBCXX_ASSERTIONS"], ["-U", "_GLIBCXX_ASSERTIONS"]),
                 ("_MSVC_STL_HARDENING", "cl.exe", ["/D_MSVC_STL_HARDENING=1"], ["/U_MSVC_STL_HARDENING"]),
                 ("_MSVC_STL_HARDENING", "cl.exe", ["/D", "_MSVC_STL_HARDENING=1"], ["/U", "_MSVC_STL_HARDENING"]),
                 (STL, "cl.exe", [f"/D{STL}"], ["/D_MSVC_STL_HARDENING=0"]),
                 ("-fstack-protector-strong", "g++", ["-fstack-protector-strong"], ["-fno-stack-protector"]),
                 ("-fstack-protector-strong", "clang++", ["-fstack-protector-strong"], ["-fstack-protector"]),
                 ("-fsanitize=address", "clang++", ["-fsanitize=address"], ["-fno-sanitize=address"]),
                 ("-fcf-protection=full", "gcc", ["-fcf-protection"], ["-fcf-protection=none"]),
                 ("-fcf-protection", "gcc", ["-fcf-protection=full"], ["-fno-cf-protection"]),
                 ("/guard:cf", "cl.exe", ["/guard:cf"], ["/guard:cf-"]),
                 ("-ftrivial-auto-var-init=zero", "clang++", ["-ftrivial-auto-var-init=zero"],
                  ["-ftrivial-auto-var-init=uninitialized"])]
        for requirement, compiler, on, off in pairs:
            for flags, expected in ((on + off, 3), (off + on, 0)):
                with self.subTest(requirement=requirement, flags=flags):
                    self.policy(requirement)
                    self.database([self.entry("src/a.cpp", flags, compiler=compiler)])
                    self.assertEqual(self.both()[0], expected)

    def test_only_what_the_compiler_itself_reads_counts(self):
        # Round 1 of the review: what the linker, the assembler or an option's own value takes is not a flag.
        cases = [("/guard:cf", "cl.exe", ["/c", "src/a.cpp", "/link", "/guard:cf"], 3),
                 ("/guard:cf", "cl.exe", ["/guard:cf", "/c", "src/a.cpp", "/link", "/guard:cf-"], 0),
                 ("_GLIBCXX_ASSERTIONS", "clang++", ["-Xlinker", "-D_GLIBCXX_ASSERTIONS"], 3),
                 ("_GLIBCXX_ASSERTIONS", "clang++", ["-Xclang", "-D_GLIBCXX_ASSERTIONS"], 3),
                 ("-fstack-protector-strong", "g++", ["-Wl,-fstack-protector-strong"], 3),
                 ("_GLIBCXX_ASSERTIONS", "g++", ["-o", "-D_GLIBCXX_ASSERTIONS"], 3),
                 ("_GLIBCXX_ASSERTIONS", "g++", ["-I", "inc", "-D", "_GLIBCXX_ASSERTIONS"], 0)]
        for requirement, compiler, flags, expected in cases:
            with self.subTest(requirement=requirement, flags=flags):
                self.policy(requirement)
                self.database([self.entry("src/a.cpp", flags, compiler=compiler)])
                self.assertEqual(self.both()[0], expected)

    def test_option_families_as_the_compilers_read_them(self):
        cases = [("-fstack-protector-strong", ["-fstack-protector-all"], 0),   # a stronger level meets it
                 ("-fstack-protector-strong", ["-fstack-protector"], 3),
                 ("-fstack-protector", ["-fstack-protector-strong"], 0),
                 ("-fstack-protector", ["-fstack-protector-explicit"], 3),
                 ("-fsanitize=address", ["-fsanitize=address", "-fsanitize=undefined"], 0),   # values add up
                 ("-fsanitize=address,undefined", ["-fsanitize=undefined", "-fsanitize=address"], 0),
                 ("-fsanitize=address,undefined", ["-fsanitize=address,undefined", "-fno-sanitize=undefined"], 3),
                 ("-ftrivial-auto-var-init=zero", ["-ftrivial-auto-var-init=zero", "-O2"], 0)]
        for requirement, flags, expected in cases:
            with self.subTest(requirement=requirement, flags=flags):
                self.policy(requirement)
                self.database([self.entry("src/a.cpp", flags, compiler="clang++")])
                self.assertEqual(self.both()[0], expected)

    def test_each_spelling_of_a_definition_and_an_option(self):
        cases = [("_GLIBCXX_ASSERTIONS", "g++", ["-D_GLIBCXX_ASSERTIONS=1"], 0),     # a bare name: any value
                 ("_GLIBCXX_ASSERTIONS", "g++", ["-D", "_GLIBCXX_ASSERTIONS"], 0),
                 ("_FORTIFY_SOURCE=3", "g++", ["-D_FORTIFY_SOURCE=2"], 3),            # a value: that value only
                 ("_FORTIFY_SOURCE=3", "g++", ["-D_FORTIFY_SOURCE=3"], 0),
                 (STL, "g++", ["-D_MSVC_STL_HARDENING"], 0),                          # -DNAME is NAME=1
                 (STL, "cl.exe", ["/D_MSVC_STL_HARDENING#1"], 0),                     # cl's # for =
                 (STL, "cl.exe", ["-D_MSVC_STL_HARDENING=1"], 0),
                 (STL, "g++", ["/D_MSVC_STL_HARDENING=1"], 3),                        # not a / reader
                 (STL, "C:/VS/bin/CL.EXE", ["/D_MSVC_STL_HARDENING=1"], 0),
                 (STL, "clang-cl", ["/D", "_MSVC_STL_HARDENING=1"], 0),
                 (STL, "sccache", ["cl", "/D_MSVC_STL_HARDENING=1"], 0),                # after a launcher
                 ("/guard:cf", "cl.exe", ["-guard:cf"], 0),                           # cl's - spelling
                 ("-fstack-protector-strong", "g++", ["-fstack-protector-strong=1"], 3),
                 (STL, "cl.exe", ["/D_MSVC_STL_HARDENING_EXTRA=1"], 3)]
        for requirement, compiler, flags, expected in cases:
            with self.subTest(requirement=requirement, compiler=compiler, flags=flags):
                self.policy(requirement)
                self.database([self.entry("src/a.cpp", flags, compiler=compiler)])
                self.assertEqual(self.both()[0], expected)

    def test_a_command_string_is_split_as_its_system_splits_it(self):
        self.policy("_GLIBCXX_ASSERTIONS", "-DNAME=a b")
        self.database([self.entry("src/a.cpp", ["-D_GLIBCXX_ASSERTIONS", '"-DNAME=a b"'], command=True)])
        self.assertEqual(self.both()[0], 0)
        self.assertEqual(hc.split_windows(r'cl "/DNAME=a b" /DQ=\"x\" a\\b.c "C:\dir\\" ""'),
                         ["cl", "/DNAME=a b", '/DQ="x"', r"a\\b.c", "C:\\dir\\", ""])
        self.assertEqual(hc.split_windows('cl "say ""hi"""'), ["cl", 'say "hi"'])
        with self.assertRaises(hc.Unreadable):
            hc.split_windows('cl "/DNAME=1')

    def test_a_windows_directory_splits_by_windows_rules(self):
        self.assertTrue(hc.WINDOWS_DIRECTORY.search("C:/work/build"))
        self.assertTrue(hc.WINDOWS_DIRECTORY.search(r"build\x64"))
        self.assertFalse(hc.WINDOWS_DIRECTORY.search("/home/me/build"))
        if os.name == "nt":
            # A real Windows entry: a backslash in a command is no escape.
            self.policy("_GLIBCXX_ASSERTIONS")
            self.file("src/a.cpp")
            self.database([{"directory": str(self.project), "file": "src/a.cpp",
                            "command": r'g++ "-I C:\inc\\" -D_GLIBCXX_ASSERTIONS -c src\a.cpp'}])
            self.assertEqual(self.both()[0], 0)


class ScopeTests(Fixture):
    def test_an_unhardened_entry_under_an_excluded_folder_is_counted_and_not_checked(self):
        self.policy("_GLIBCXX_ASSERTIONS", exclude=["src/vendor"])
        self.database([self.entry("src/a.cpp", ["-D_GLIBCXX_ASSERTIONS"]), self.entry("src/vendor/z.cpp", [])])
        code, status, _text, report = self.both()
        self.assertEqual((code, status, report["checked"], report["excluded"]), (0, "ok", 1, 1))
        self.assertIn("1 excluded", report["detail"])

    def test_entries_outside_the_sources_are_counted_and_not_checked(self):
        self.policy("_GLIBCXX_ASSERTIONS", sources=["src"])
        self.database([self.entry("src/a.cpp", ["-D_GLIBCXX_ASSERTIONS"]), self.entry("tools/gen.cpp", []),
                       self.entry("srcgen/b.cpp", [])])   # a sibling whose name starts like the folder
        code, status, _text, report = self.both()
        self.assertEqual((code, status, report["checked"], report["outside"]), (0, "ok", 1, 2))
        self.assertIn("2 outside the sources", report["detail"])

    def test_the_sources_are_under_the_pin_files_root(self):
        self.pins({"compile": ["_GLIBCXX_ASSERTIONS"], "sources": ["src"]}, root="engine")
        self.file("engine/src/a.cpp")
        self.file("engine/compile_commands.json", json.dumps([
            {"directory": str(self.project / "engine"), "file": "src/a.cpp", "arguments": ["g++", "-c", "src/a.cpp"]}]))
        code, status, text, _report = self.both()
        self.assertEqual((code, status), (3, "missing"))
        self.assertIn("first engine/src/a.cpp", text)

    def test_a_policy_no_entry_falls_under_is_unknown(self):
        self.policy("_GLIBCXX_ASSERTIONS", sources=["src"], exclude=["src"])
        self.database([self.entry("src/a.cpp", [])])
        code, status, _text, report = self.both()
        self.assertEqual((code, status), (1, "unknown"))
        self.assertIn("no entry is under the policy's sources (src), so nothing was checked", report["detail"])


class UnknownTests(Fixture):
    def test_a_database_that_is_missing_or_invalid_is_unknown(self):
        self.policy("_GLIBCXX_ASSERTIONS")
        code, status, _text, report = self.both()
        self.assertEqual((code, status), (1, "unknown"))
        self.assertIn("the compile database is missing", report["detail"])
        self.database("[{]")
        code, status, _text, report = self.both()
        self.assertEqual((code, status), (1, "unknown"))
        self.assertIn("the compile database is invalid", report["detail"])

    def test_a_database_larger_than_the_read_limit_is_unknown(self):
        self.policy("_GLIBCXX_ASSERTIONS")
        self.database([self.entry("src/a.cpp", ["-D_GLIBCXX_ASSERTIONS"])])
        pin_file = hc._sibling("toolchain-check.py", "tc").load_pin_file(self.project / hc.PINS)
        compdb = hc._sibling("compdb-check.py", "cc")
        result = hc.check_hardening(self.project, pin_file, compdb, read_limit=16)
        self.assertEqual(result["status"], "unknown")
        self.assertIn("is larger than the 16 bytes this check reads", result["detail"])
        self.assertEqual(compdb.READ_LIMIT, 256 * 1024 * 1024)   # the default it reads up to

    def test_a_hardened_database_older_than_a_build_file_is_unknown_with_the_regenerate_line(self):
        self.pins({"compile": ["_GLIBCXX_ASSERTIONS"]}, compdb={"regenerate": ["cmake", "-B", "build"]})
        self.database([self.entry("src/a.cpp", ["-D_GLIBCXX_ASSERTIONS"])])
        self.file("CMakeLists.txt", "add_compile_definitions()\n", when=LATER)
        code, status, text, report = self.both()
        self.assertEqual((code, status), (1, "unknown"))
        self.assertIn("the compile database is stale", report["detail"])
        self.assertIn("older than CMakeLists.txt", report["detail"])
        self.assertRegex(text.splitlines()[-1], r"^regenerate with \((PowerShell|sh)\): cmake -B build$")


class ResponseFileTests(Fixture):
    def policy_with(self, rsp_text=None, rsp_data=None, flags=("@flags.rsp",)):
        self.policy("_GLIBCXX_ASSERTIONS", "-DNAME=a b")
        if rsp_text is not None or rsp_data is not None:
            self.file("flags.rsp", rsp_text or "", data=rsp_data)
        self.database([self.entry("src/a.cpp", list(flags))])

    def test_a_requirement_only_in_a_quoted_response_file_passes(self):
        self.policy_with('-D_GLIBCXX_ASSERTIONS\n"-DNAME=a b"\n')
        self.assertEqual(self.both()[:2], (0, "ok"))

    def test_a_utf16_response_file_with_a_byte_order_mark_passes(self):
        self.policy_with(rsp_data='-D_GLIBCXX_ASSERTIONS "-DNAME=a b"'.encode("utf-16"))
        self.assertEqual(self.both()[:2], (0, "ok"))

    def test_a_flag_after_the_response_file_still_wins(self):
        self.policy_with('-D_GLIBCXX_ASSERTIONS "-DNAME=a b"', flags=("@flags.rsp", "-U_GLIBCXX_ASSERTIONS"))
        self.assertEqual(self.both()[:2], (3, "missing"))

    def test_a_response_file_that_cannot_be_read_faithfully_is_unknown(self):
        cases = [(None, None, "response file flags.rsp of src/a.cpp cannot be read"),
                 ("-D_GLIBCXX_ASSERTIONS " * 10, None, "is larger than the 64 bytes this check reads"),
                 (None, b"-D\xff\xfe\xfa", "is neither UTF-8 nor UTF-16 with a byte order mark"),
                 ('-D_GLIBCXX_ASSERTIONS "-DNAME=a b', None, "response file flags.rsp of src/a.cpp: "),
                 ('-D_GLIBCXX_ASSERTIONS "-DNAME=a b" @inner.rsp', None, "names a response file itself (@inner.rsp)")]
        for text, data, expected in cases:
            with self.subTest(expected=expected):
                (self.project / "flags.rsp").unlink(missing_ok=True)
                self.file("inner.rsp", "-U_GLIBCXX_ASSERTIONS\n")
                with unittest.mock.patch.object(hc, "RESPONSE_LIMIT", 64):
                    self.policy_with(text, data)
                    code, status, _text, report = self.both()
                self.assertEqual((code, status), (1, "unknown"))
                self.assertIn(expected, report["detail"])
                self.assertTrue(report["detail"].endswith("so its flags cannot be told"), report["detail"])

    def test_an_unbalanced_quote_in_a_command_is_unknown(self):
        self.policy("_GLIBCXX_ASSERTIONS")
        self.file("src/a.cpp")
        self.database([{"directory": str(self.project), "file": "src/a.cpp",
                        "command": 'g++ "-D_GLIBCXX_ASSERTIONS -c src/a.cpp'}])
        code, status, _text, report = self.both()
        self.assertEqual((code, status), (1, "unknown"))
        self.assertIn("the command of src/a.cpp: ", report["detail"])


class ReadOnlyTests(Fixture):
    def test_the_check_starts_no_process_and_writes_nothing(self):
        self.policy("_GLIBCXX_ASSERTIONS")
        self.database([self.entry("src/a.cpp", ["-D_GLIBCXX_ASSERTIONS"])])
        before = {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        with unittest.mock.patch.object(subprocess, "Popen", side_effect=AssertionError("a process was started")):
            self.assertEqual(self.both()[0], 0)
        self.assertEqual({path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}, before)

    def test_the_script_runs_as_a_program(self):
        self.policy("_GLIBCXX_ASSERTIONS")
        self.database([self.entry("src/a.cpp", [])])
        done = subprocess.run([sys.executable, str(SCRIPTS / "hardening-check.py"), "--root", str(self.project)],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertTrue(done.stdout.startswith("hardening:compile: missing: "), done.stdout)


if __name__ == "__main__":
    unittest.main()
