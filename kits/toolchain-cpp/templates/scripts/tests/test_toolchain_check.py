"""toolchain-check.py: the pin file's rules, version comparison, a tool's check and its bounds, the command line.

The tools are stubs on a scratch PATH: a launcher script on POSIX and a .cmd launcher on Windows, which is how npm
and Composer install theirs. No real build tool is run.
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "toolchain-check.py"
spec = importlib.util.spec_from_file_location("toolchain_check", SCRIPT)
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)

COMMAND = {"command": "ninja", "version_args": ["--version"], "version_pattern": r"^(\d+(?:\.\d+)*)",
           "min_version": "1.10"}
TOOL = {"name": "ninja", "commands": [COMMAND], "install": "apt install ninja-build"}


def alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def gone(pid, seconds=10):
    deadline = time.monotonic() + seconds
    while alive(pid):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name).resolve()
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        # Only the stubs are on PATH: a tool the host really has must not answer for one the test left out.
        env = {"PATH": str(self.bin)}
        if os.name == "nt":
            env["PATHEXT"] = ".CMD;.EXE"
        patch = unittest.mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)

    def pins(self, document):
        path = self.dir / "pins.json"
        path.write_text(document if isinstance(document, str) else json.dumps(document), encoding="utf-8")
        return path

    def stub(self, name, body):
        """A tool on the scratch PATH whose behaviour is the Python `body`; `{dir}` in it is the scratch folder."""
        code = self.dir / f"{name}-stub.py"
        code.write_text(body.replace("{dir}", self.dir.as_posix()), encoding="utf-8")
        if os.name == "nt":
            launcher = self.bin / f"{name}.cmd"
            launcher.write_text(f'@"{sys.executable}" "{code}" %*\r\n', encoding="utf-8")
        else:
            launcher = self.bin / name
            launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{code}" "$@"\n', encoding="utf-8")
            launcher.chmod(0o755)
        return launcher

    def prints(self, name, text, stream="stdout", code=0):
        return self.stub(name, f"import sys\nsys.{stream}.write({text!r})\nsys.exit({code})\n")

    def tool(self, name="ninja", commands=None, **extra):
        commands = commands or [dict(COMMAND, command=name)]
        return dict({"name": name, "commands": commands, "install": f"install {name} by hand", "optional": False},
                    **extra)


class LoadPinsTests(Fixture):
    def test_a_pin_file_loads_as_its_tools_in_order(self):
        cache = {"name": "compiler-cache", "optional": True, "install": "apt install ccache", "commands": [
            dict(COMMAND, command="ccache", version_pattern=r"ccache version ([0-9.]+)", min_version="4.0"),
            dict(COMMAND, command="sccache", version_pattern=r"sccache ([0-9.]+)", min_version="0.5")]}
        loaded = tc.load_pins(self.pins({"schema_version": 1, "tools": [TOOL, cache]}))
        self.assertEqual([tool["name"] for tool in loaded], ["ninja", "compiler-cache"])
        self.assertEqual(loaded[0], dict(TOOL, optional=False))  # optional is false when left out
        self.assertEqual(loaded[1]["optional"], True)
        self.assertEqual([c["min_version"] for c in loaded[1]["commands"]], ["4.0", "0.5"])
        self.assertEqual(tc.load_pins(self.pins({"schema_version": 1, "tools": []})), [])

    def test_a_file_that_cannot_be_read_as_a_pin_file_is_refused_naming_it(self):
        path = self.dir / "pins.json"
        with self.assertRaises(tc.PinError) as caught:
            tc.load_pins(path)  # missing
        self.assertTrue(str(caught.exception).startswith(f"{path.as_posix()}: cannot be read"), caught.exception)
        denied = PermissionError(13, "Permission denied")
        with unittest.mock.patch.object(pathlib.Path, "read_bytes", side_effect=denied):
            with self.assertRaises(tc.PinError) as caught:
                tc.load_pins(path)
        self.assertIn("cannot be read (Permission denied)", str(caught.exception))
        cases = {"not UTF-8": b"\xff\xfe{}", "not JSON": b"{", "an object": b"null", "an object ": b"[]",
                 "unknown key 'compdb'": json.dumps({"schema_version": 1, "tools": [], "compdb": {}}).encode(),
                 "missing key 'tools'": b'{"schema_version": 1}',
                 "schema_version: must be 1": b'{"schema_version": 2, "tools": []}',
                 "schema_version: must be 1 ": b'{"schema_version": true, "tools": []}',
                 "tools: a list": b'{"schema_version": 1, "tools": {}}',
                 "tool 1: a tool is an object": b'{"schema_version": 1, "tools": ["ninja"]}'}
        for expected, data in cases.items():
            with self.subTest(case=expected):
                path.write_bytes(data)
                with self.assertRaises(tc.PinError) as caught:
                    tc.load_pins(path)
                self.assertTrue(str(caught.exception).startswith(path.as_posix() + ": "), caught.exception)
                self.assertIn(expected.strip(), str(caught.exception))

    def test_each_fault_in_a_tool_is_refused_naming_the_tool_and_the_key(self):
        def tool(**changes):
            return dict(TOOL, **changes)

        def command(**changes):
            return tool(commands=[dict(COMMAND, **changes)])

        without = {key: value for key, value in COMMAND.items() if key != "min_version"}
        cases = [
            (tool(name="Ninja"), "tool 1: name:"),
            (tool(name=7), "tool 1: name:"),
            (tool(extra=1), "tool 'ninja': unknown key 'extra'"),
            ({key: value for key, value in TOOL.items() if key != "install"}, "tool 'ninja': missing key 'install'"),
            (tool(commands=[]), "tool 'ninja': commands:"),
            (tool(commands="ninja"), "tool 'ninja': commands:"),
            (tool(commands=["ninja"]), "tool 'ninja': a command is an object"),
            (command(command="./ninja"), "tool 'ninja': command: a bare program name"),
            (command(command="bin/ninja"), "tool 'ninja': command: a bare program name"),
            (command(command="C:\\tools\\ninja.exe"), "tool 'ninja': command: a bare program name"),
            (tool(commands=[dict(COMMAND, extra=1)]), "tool 'ninja': command 'ninja': unknown key 'extra'"),
            (tool(commands=[without]), "tool 'ninja': command 'ninja': missing key 'min_version'"),
            (command(version_args="--version"), "command 'ninja': version_args: a list of strings"),
            (command(version_args=[1]), "command 'ninja': version_args: a list of strings"),
            (command(version_args=["--version & calc"]), "command 'ninja': version_args:"),
            (command(version_args=["%PATH%"]), "command 'ninja': version_args:"),
            (command(version_args=[""]), "command 'ninja': version_args:"),
            (command(version_pattern="("), "command 'ninja': version_pattern: does not compile"),
            (command(version_pattern="version"), "command 'ninja': version_pattern: needs exactly one group, has 0"),
            (command(version_pattern="(v)(.*)"), "command 'ninja': version_pattern: needs exactly one group, has 2"),
            (command(version_pattern=None), "command 'ninja': version_pattern:"),
            (command(min_version="1.x"), "command 'ninja': min_version:"),
            (command(min_version="v1.2"), "command 'ninja': min_version:"),
            (command(min_version=1.2), "command 'ninja': min_version:"),
            # Found by the round of D04 T02 section 1: inputs the loader took and the check then choked on.
            (command(min_version="9" * 4301), "command 'ninja': min_version:"),
            (command(min_version=".".join(["1"] * 9)), "command 'ninja': min_version:"),
            (command(version_pattern="(?:" * 1000 + "(1)" + ")" * 1000), "command 'ninja': version_pattern:"),
            (command(version_pattern="(1)" + "a" * 600), "command 'ninja': version_pattern: longer than"),
            (tool(install="one\ntwo"), "tool 'ninja': install: a one-line hint"),
            (tool(install=""), "tool 'ninja': install: a one-line hint"),
            (tool(optional="yes"), "tool 'ninja': optional: true or false"),
            (tool(optional=1), "tool 'ninja': optional: true or false"),
        ]
        for entry, expected in cases:
            with self.subTest(expected=expected, entry=str(entry)[:60]):
                path = self.pins({"schema_version": 1, "tools": [entry]})
                with self.assertRaises(tc.PinError) as caught:
                    tc.load_pins(path)
                self.assertTrue(str(caught.exception).startswith(path.as_posix() + ": "), caught.exception)
                self.assertIn(expected, str(caught.exception))
        path = self.pins({"schema_version": 1, "tools": [TOOL, TOOL]})
        with self.assertRaises(tc.PinError) as caught:
            tc.load_pins(path)
        self.assertIn("tool 'ninja': name: used by two tools", str(caught.exception))


class VersionTests(unittest.TestCase):
    def test_versions_compare_number_by_number(self):
        self.assertEqual(tc.compare_versions("1.10", "1.9"), 1)  # as strings, 1.10 sorts before 1.9
        self.assertEqual(tc.compare_versions("1.9", "1.10"), -1)
        self.assertEqual(tc.compare_versions("1.2", "1.2.0"), 0)  # a missing trailing part is zero
        self.assertEqual(tc.compare_versions("1.2.0", "1.2"), 0)
        self.assertEqual(tc.compare_versions("1.2.1", "1.2"), 1)
        self.assertEqual(tc.compare_versions("2", "2.0.1"), -1)
        self.assertEqual(tc.compare_versions("10.0", "9.99.99"), 1)
        self.assertEqual(tc.compare_versions("19", "19"), 0)

    def test_only_dotted_numbers_are_a_version(self):
        self.assertEqual(tc.parse_version("19.1.7"), (19, 1, 7))
        for text in ("unknown", "", "1.", ".1", "1..2", "1.2-rc1", "v1.2", " 1.2", None, 12):
            with self.subTest(text=text):
                self.assertIsNone(tc.parse_version(text))
        with self.assertRaises(ValueError):
            tc.compare_versions("unknown", "1.0")


class CheckToolTests(Fixture):
    def test_an_installed_tool_new_enough_is_ok_with_its_version_and_path(self):
        launcher = self.prints("ninja", "1.11.1\n")
        result = tc.check_tool(self.tool())
        self.assertEqual(result, {"name": "ninja", "status": "ok", "detail": result["command"], "version": "1.11.1",
                                  "command": result["command"], "optional": False})
        self.assertTrue(os.path.samefile(result["command"], launcher))
        self.prints("ninja", "1.10\n")
        self.assertEqual(tc.check_tool(self.tool())["status"], "ok")  # the pinned version itself is new enough

    def test_a_version_printed_on_standard_error_is_read(self):
        self.prints("ninja", "ninja 1.12.0\n", stream="stderr")
        result = tc.check_tool(self.tool(commands=[dict(COMMAND, version_pattern=r"ninja ([0-9.]+)")]))
        self.assertEqual((result["status"], result["version"]), ("ok", "1.12.0"))

    def test_the_arguments_of_the_pin_reach_the_tool(self):
        self.stub("ninja", "import sys\nprint('1.11' if sys.argv[1:] == ['--version', '-q'] else 'usage')\n")
        result = tc.check_tool(self.tool(commands=[dict(COMMAND, version_args=["--version", "-q"])]))
        self.assertEqual((result["status"], result["version"]), ("ok", "1.11"))

    def test_each_command_is_held_to_its_own_minimum(self):
        commands = [dict(COMMAND, command="ccache", version_pattern=r"ccache version ([0-9.]+)", min_version="4.0"),
                    dict(COMMAND, command="sccache", version_pattern=r"sccache ([0-9.]+)", min_version="0.5")]
        pin = self.tool("compiler-cache", commands)
        self.prints("sccache", "sccache 0.8.1\n")
        result = tc.check_tool(pin)  # 0.8.1 is older than ccache's 4.0 and newer than sccache's 0.5
        self.assertEqual((result["status"], result["version"]), ("ok", "0.8.1"))
        self.assertIn("sccache", os.path.basename(result["command"]))
        # The first command found is the one checked: an old ccache is reported, sccache is not tried in its place.
        self.prints("ccache", "ccache version 3.7.7\n")
        result = tc.check_tool(pin)
        self.assertEqual((result["status"], result["version"]), ("setup_required", "3.7.7"))
        self.assertIn("is 3.7.7, older than the pinned 4.0. Install: install compiler-cache by hand", result["detail"])
        self.assertIn("ccache", os.path.basename(result["command"]))

    def test_a_tool_that_is_not_installed_names_its_commands_and_the_hint(self):
        commands = [dict(COMMAND, command="mold"), dict(COMMAND, command="ld.lld")]
        result = tc.check_tool(self.tool("linker", commands, optional=True))
        self.assertEqual(result, {"name": "linker", "status": "setup_required", "version": None, "command": None,
                                  "optional": True,
                                  "detail": "not installed (mold, ld.lld not on PATH). "
                                            "Install: install linker by hand"})

    def test_a_version_below_the_pin_names_both_versions(self):
        self.prints("ninja", "1.9.0\n")
        result = tc.check_tool(self.tool())
        self.assertEqual((result["status"], result["version"]), ("setup_required", "1.9.0"))
        self.assertIn("is 1.9.0, older than the pinned 1.10. Install: install ninja by hand", result["detail"])

    def test_output_the_pattern_cannot_read_is_not_a_version(self):
        self.prints("ninja", "ninja, a small build system\n")
        result = tc.check_tool(self.tool())
        self.assertEqual((result["status"], result["version"]), ("setup_required", None))
        self.assertIn("does not match its output", result["detail"])
        self.prints("ninja", "version unknown\n")
        for pattern in (r"version (\w+)", r"version(?: (\d+))? unknown"):  # text, and a group that took no part
            with self.subTest(pattern=pattern):
                result = tc.check_tool(self.tool(commands=[dict(COMMAND, version_pattern=pattern)]))
                self.assertEqual((result["status"], result["version"]), ("setup_required", None))
                self.assertIn("which is not a version", result["detail"])

    def test_a_tool_that_exits_non_zero_is_not_ok_whatever_it_printed(self):
        for text in ("", "1.11.1\n"):
            with self.subTest(printed=text):
                self.prints("ninja", text, code=3)
                result = tc.check_tool(self.tool())
                self.assertEqual((result["status"], result["version"]), ("setup_required", None))
                self.assertTrue(result["detail"].endswith("--version exited 3"), result["detail"])

    def test_a_file_on_path_that_cannot_be_started_names_the_systems_reason(self):
        if os.name == "nt":
            (self.bin / "ninja.exe").write_bytes(b"not a program")
        else:
            broken = self.bin / "ninja"
            broken.write_text("#!/nonexistent/interpreter\n", encoding="utf-8")
            broken.chmod(broken.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        result = tc.check_tool(self.tool())
        self.assertEqual(result["status"], "setup_required")
        self.assertIn("could not be started: ", result["detail"])
        self.assertGreater(len(result["detail"].split("could not be started: ")[1]), 3)


CHILD = ("import subprocess, sys, time\n"
         "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
         "open(r'{dir}/pids', 'w').write(f'{os.getpid()} {child.pid}')\n")


class BoundTests(Fixture):
    def pids(self):
        deadline = time.monotonic() + 10
        path = self.dir / "pids"
        while not (path.is_file() and len(path.read_text().split()) == 2):
            self.assertLess(time.monotonic(), deadline, "the stub never wrote its process ids")
            time.sleep(0.05)
        return [int(pid) for pid in path.read_text().split()]

    def test_a_tool_that_never_answers_is_stopped_with_everything_it_started(self):
        self.stub("ninja", "import os\n" + CHILD + "time.sleep(120)\n")
        started = time.monotonic()
        result = tc.check_tool(self.tool(), time_limit=3)
        elapsed = time.monotonic() - started
        self.assertEqual(result["status"], "setup_required")
        self.assertIn("did not answer within 3 seconds and was stopped", result["detail"])
        self.assertLess(elapsed, 13, "the check outlived its limit")
        for pid in self.pids():
            self.assertTrue(gone(pid), f"process {pid} outlived the check")

    def test_a_tool_that_floods_its_output_is_stopped_at_the_cap_with_everything_it_started(self):
        # The stub's own bound: 64 MiB, far past the cap and nowhere near a disk.
        self.stub("ninja", "import os, sys\n" + CHILD
                  + "for _ in range(65536):\n    sys.stdout.write('x' * 1023 + '\\n')\n    sys.stdout.flush()\n"
                  + "time.sleep(120)\n")
        started = time.monotonic()
        result = tc.check_tool(self.tool(), time_limit=60, output_cap=4096)
        elapsed = time.monotonic() - started
        self.assertEqual(result["status"], "setup_required")
        self.assertIn("printed more than 4096 bytes and was stopped", result["detail"])
        self.assertLess(elapsed, 30, "the check read to the end of the flood, or waited out the limit")
        for pid in self.pids():
            self.assertTrue(gone(pid), f"process {pid} outlived the check")

    def test_what_is_kept_of_the_output_stops_at_the_cap(self):
        self.stub("ninja", "import sys\nsys.stdout.write('y' * 100000)\n")
        ran = tc.run_bounded([str(self.bin / ("ninja.cmd" if os.name == "nt" else "ninja"))], 30, 1000)
        self.assertEqual((ran["stopped"], len(ran["output"])), ("output", 1000))

    def test_a_pattern_that_never_finishes_is_stopped_and_the_next_tool_is_checked(self):
        # Found by the round of D04 T02 section 1: the pattern ran outside every limit. `(?:a+)+([0-9])$` on a line
        # of a's with no digit backtracks for hours.
        self.prints("ninja", "a" * 64 + "!\n")
        self.prints("clangd", "clangd version 19.1.7\n")
        slow = self.tool(commands=[dict(COMMAND, version_pattern=r"(?:a+)+([0-9])$")])
        fine = self.tool("clangd", [dict(COMMAND, command="clangd", version_pattern=r"version ([0-9.]+)",
                                         min_version="15")])
        started = time.monotonic()
        with unittest.mock.patch.object(tc, "PATTERN_LIMIT", 2.0):
            results = tc.check_tools([slow, fine])
        self.assertLess(time.monotonic() - started, 30, "the pattern ran past its limit")
        self.assertEqual([result["status"] for result in results], ["setup_required", "ok"])
        self.assertIn("did not finish reading its output within 2 seconds", results[0]["detail"])

    def test_an_interrupted_check_leaves_no_tool_running(self):
        # Same round: Ctrl+C while a tool is being waited on skipped the cleanup, and the tool has its own session.
        self.stub("ninja", "import os\n" + CHILD + "time.sleep(120)\n")
        real = time.monotonic
        calls = []

        def interrupted():
            calls.append(1)
            if len(calls) > 3 and (self.dir / "pids").is_file() and len((self.dir / "pids").read_text().split()) == 2:
                raise KeyboardInterrupt
            return real()

        with unittest.mock.patch.object(tc.time, "monotonic", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                tc.check_tool(self.tool(), time_limit=60)
        for pid in self.pids():
            self.assertTrue(gone(pid), f"process {pid} outlived the interrupted check")

    def test_a_capture_too_long_to_be_a_version_is_not_one(self):
        self.prints("ninja", "9" * 5000 + "\n")
        result = tc.check_tool(self.tool(commands=[dict(COMMAND, version_pattern=r"^(\d+)")]))
        self.assertEqual((result["status"], result["version"]), ("setup_required", None))
        self.assertIn("which is not a version", result["detail"])
        self.assertLess(len(result["detail"]), 400)


class CommandLineTests(Fixture):
    def run_script(self, *argv):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *argv], capture_output=True, text=True, timeout=120,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def document(self, *tools):
        return self.pins({"schema_version": 1, "tools": list(tools)})

    def test_every_tool_is_reported_and_a_missing_required_one_exits_3(self):
        self.prints("clangd", "clangd version 19.1.7\n")
        pins = self.document(
            {"name": "ninja", "commands": [COMMAND], "install": "apt install ninja-build"},
            {"name": "clangd", "install": "apt install clangd", "commands": [
                dict(COMMAND, command="clangd", version_pattern=r"clangd version ([0-9.]+)", min_version="15")]})
        ran = self.run_script("--pins", pins, "--json")
        self.assertEqual(ran.returncode, 3, ran.stderr)
        report = json.loads(ran.stdout)
        self.assertEqual(report["pins"], pins.as_posix())
        self.assertEqual(report["required_not_ok"], 1)
        self.assertEqual([(tool["name"], tool["status"]) for tool in report["tools"]],
                         [("ninja", "setup_required"), ("clangd", "ok")])  # the tool after the failure is checked
        self.assertEqual(set(report["tools"][1]), {"name", "status", "detail", "version", "command", "optional"})
        self.assertEqual(report["tools"][1]["version"], "19.1.7")
        text = self.run_script("--pins", pins)
        self.assertEqual(text.returncode, 3)
        lines = text.stdout.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("ninja  setup_required  not installed (ninja not on PATH)"), lines[0])
        self.assertTrue(lines[1].startswith("clangd  ok  "), lines[1])

    def test_a_missing_optional_tool_is_shown_and_exits_0(self):
        pins = self.document({"name": "ninja", "commands": [COMMAND], "install": "apt install ninja-build",
                              "optional": True})
        ran = self.run_script("--pins", pins, "--json")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        report = json.loads(ran.stdout)
        self.assertEqual((report["required_not_ok"], report["tools"][0]["status"]), (0, "setup_required"))

    def test_a_pin_file_that_does_not_load_is_one_line_and_exit_2(self):
        for name, data in (("malformed", '{"schema_version": 1, "tools": [{"name": "x"}]}'), ("missing", None)):
            with self.subTest(case=name):
                path = self.dir / f"{name}.json"
                if data is not None:
                    path.write_text(data, encoding="utf-8")
                ran = self.run_script("--pins", path, "--json")
                self.assertEqual((ran.returncode, ran.stdout), (2, ""))
                self.assertEqual(len(ran.stderr.splitlines()), 1, ran.stderr)
                self.assertTrue(ran.stderr.startswith(f"toolchain-check: {path.as_posix()}: "), ran.stderr)

    def snapshot(self):
        return {path.relative_to(self.dir).as_posix(): path.read_bytes()
                for path in self.dir.rglob("*") if path.is_file()}

    def test_the_check_writes_nothing(self):
        self.prints("ninja", "1.11.1\n")
        pins = self.document({"name": "ninja", "commands": [COMMAND], "install": "apt install ninja-build"})
        before = self.snapshot()
        self.assertEqual(self.run_script("--pins", pins).returncode, 0)
        self.assertEqual(self.snapshot(), before)


class InProcessTests(Fixture):
    def test_main_prints_the_same_report_in_process(self):
        self.prints("ninja", "1.11.1\n")
        pins = self.pins({"schema_version": 1, "tools": [TOOL]})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tc.main(["--pins", str(pins), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["tools"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
