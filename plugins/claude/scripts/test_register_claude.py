"""Tests for build_claude.py and register_claude.py. Nothing here touches the real ~/.claude.json or runs npm or claude.

    python -m unittest discover -s plugins/claude/scripts -p "test_*.py"
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_claude  # noqa: E402
import register_claude  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "plugins"
        for name in build_claude.PLUGINS:
            plugin = self.root / name
            (plugin / "src").mkdir(parents=True)
            (plugin / "dist").mkdir()
            (plugin / "package.json").write_text('{"name": "%s"}\n' % name, encoding="utf-8")
            (plugin / "src" / "server.js").write_text("export const a = 1;\n", encoding="utf-8")
            (plugin / "dist" / "server.mjs").write_text("bundle\n", encoding="utf-8")
            build_claude.write_stamp(plugin)
        self.claude_json = self.tmp / ".claude.json"

    def write_servers(self, servers):
        self.claude_json.write_text(json.dumps({"numStartups": 3, "mcpServers": servers}), encoding="utf-8")

    def entry(self, name, **changes):
        # A drive-letter root, as the real checkout has: the fixture root may be a pure POSIX temporary folder.
        return {"type": "stdio", "command": register_claude.node_command(),
                "args": ["D:\\Conclave-SDK\\plugins\\claude\\%s\\dist\\server.mjs" % name], "env": {}, **changes}

    def good(self):
        return {name: {"type": "stdio", "command": register_claude.node_command(),
                       "args": [str(self.root / name / "dist" / "server.mjs")]}
                for name in build_claude.PLUGINS}


class BuildStampTest(Fixture):
    def test_a_fresh_stamp_is_current(self):
        for name in build_claude.PLUGINS:
            self.assertIsNone(build_claude.stale(self.root / name))

    def test_a_changed_source_or_manifest_makes_the_bundle_stale(self):
        plugin = self.root / "bunny-net"
        (plugin / "src" / "server.js").write_text("export const a = 2;\n", encoding="utf-8")
        self.assertIn("built from other sources", build_claude.stale(plugin))
        build_claude.write_stamp(plugin)
        self.assertIsNone(build_claude.stale(plugin))
        (plugin / "package.json").write_text('{"name": "changed"}\n', encoding="utf-8")
        self.assertIn("built from other sources", build_claude.stale(plugin))

    def test_a_new_source_file_makes_the_bundle_stale(self):
        plugin = self.root / "bunny-net"
        (plugin / "src" / "extra.js").write_text("export const b = 1;\n", encoding="utf-8")
        self.assertIn("built from other sources", build_claude.stale(plugin))

    def test_line_endings_and_file_times_do_not_matter(self):
        plugin = self.root / "bunny-net"
        (plugin / "src" / "server.js").write_bytes(b"export const a = 1;\r\n")
        os.utime(plugin / "src" / "server.js", (2000000000, 2000000000))
        self.assertIsNone(build_claude.stale(plugin))

    def test_a_missing_bundle_or_stamp_is_reported(self):
        plugin = self.root / "bunny-net"
        (plugin / "dist" / "source.sha256").unlink()
        self.assertEqual(build_claude.stale(plugin), "dist/source.sha256 is missing")
        (plugin / "dist" / "server.mjs").unlink()
        self.assertEqual(build_claude.stale(plugin), "dist/server.mjs is missing")

    def test_a_build_installs_from_the_lockfile_even_when_node_modules_exists(self):
        plugin = self.root / "bunny-net"
        (plugin / "node_modules").mkdir()
        (plugin / "dist" / "source.sha256").unlink()
        with unittest.mock.patch("shutil.which", return_value="npm"), \
                unittest.mock.patch("subprocess.run") as run:
            build_claude.build(plugin)
        self.assertEqual([call.args[0][1:3] for call in run.call_args_list], [["ci", "--no-audit"], ["run", "build"]])
        self.assertIsNone(build_claude.stale(plugin))

    def test_the_tracked_bundles_match_their_sources(self):
        for name in build_claude.PLUGINS:
            self.assertIsNone(build_claude.stale(build_claude.ROOT / name), name)


class PathTest(unittest.TestCase):
    def test_windows_path_of_each_form(self):
        self.assertEqual(register_claude.windows_path("/mnt/d/Conclave-SDK/plugins"), "D:\\Conclave-SDK\\plugins")
        self.assertEqual(register_claude.windows_path("d:/Conclave-SDK\\plugins"), "D:\\Conclave-SDK\\plugins")
        self.assertIsNone(register_claude.windows_path("/home/me/sdk"))

    def test_same_path_across_forms_and_case(self):
        self.assertTrue(register_claude.same_path("/mnt/d/a/B.mjs", "D:\\A\\b.mjs"))
        self.assertFalse(register_claude.same_path("/mnt/d/a/b.mjs", "R:\\a\\b.mjs"))
        self.assertTrue(register_claude.same_path("/home/me/x", "/home/me/x"))


class ProblemsTest(Fixture):
    def test_registrations_that_run_this_checkouts_bundles_pass(self):
        self.write_servers(self.good())
        self.assertEqual(register_claude.problems(self.claude_json, self.root), [])

    def test_an_absent_file_or_entry_is_reported(self):
        self.assertEqual(len(register_claude.problems(self.claude_json, self.root)), 2)
        servers = self.good()
        del servers["bunny-net"]
        self.write_servers(servers)
        self.assertEqual(register_claude.problems(self.claude_json, self.root),
                         ["bunny-net is not registered in %s" % self.claude_json])

    def test_a_moved_or_retired_checkout_is_reported_in_either_path_form(self):
        for elsewhere in ("R:\\Bin\\claude\\connections\\bunny-net\\dist\\server.mjs",
                          "/mnt/r/Bin/claude/connections/bunny-net/dist/server.mjs",
                          "D:\\Conclave-SDK\\plugins\\claude\\bunny-net\\dist\\server.mjs"):
            servers = self.good()
            servers["bunny-net"]["args"] = [elsewhere]
            self.write_servers(servers)
            self.assertEqual(register_claude.problems(self.claude_json, self.root),
                             ["bunny-net does not run %s and nothing else" % (self.root / "bunny-net" / "dist" / "server.mjs")])

    def test_another_bundle_is_reported(self):
        servers = self.good()
        servers["domains-co-za"]["args"] = [str(self.tmp / "elsewhere" / "server.mjs")]
        self.write_servers(servers)
        found = register_claude.problems(self.claude_json, self.root)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith("domains-co-za does not run "), found)

    def test_the_bundle_as_a_later_argument_or_under_another_node_does_not_pass(self):
        bundle = str(self.root / "bunny-net" / "dist" / "server.mjs")
        for change, wanted in (({"args": ["other.mjs", bundle]}, "does not run"),
                               ({"args": [bundle, "--extra"]}, "does not run"),
                               ({"command": "/usr/bin/node"}, "is not run by Windows Node"),
                               ({"type": "http"}, "is not run by Windows Node")):
            servers = self.good()
            servers["bunny-net"].update(change)
            self.write_servers(servers)
            found = register_claude.problems(self.claude_json, self.root)
            self.assertEqual(len(found), 1, change)
            self.assertIn(wanted, found[0])

    def test_windows_node_passes_only_in_the_form_this_platform_starts(self):
        mine, other = register_claude.node_command(), (
            "/mnt/c/Program Files/nodejs/node.exe" if os.name == "nt" else register_claude.NODE_WINDOWS)
        for node, passes in ((mine, True), (mine.replace("\\", "/"), True), (other, False)):
            servers = self.good()
            for entry in servers.values():
                entry["command"] = node
            self.write_servers(servers)
            self.assertEqual(register_claude.problems(self.claude_json, self.root) == [], passes, node)

    def test_a_bundle_in_its_mnt_form_does_not_pass(self):
        # Windows Node reads the bundle path, and it cannot open /mnt/d/...
        root = Path("D:/Conclave-SDK/plugins/claude")
        servers = {name: {"type": "stdio", "command": register_claude.node_command(),
                          "args": ["/mnt/d/Conclave-SDK/plugins/claude/%s/dist/server.mjs" % name]}
                   for name in build_claude.PLUGINS}
        self.write_servers(servers)
        found = [line for line in register_claude.problems(self.claude_json, root) if "does not run" in line]
        self.assertEqual(len(found), len(build_claude.PLUGINS), found)

    def test_a_wrong_entry_with_an_env_block_says_how_to_free_it_and_shows_no_value(self):
        servers = self.good()
        servers["bunny-net"] = self.entry("bunny-net", env={"TOKEN": "s3cret-value"})
        self.write_servers(servers)
        found = register_claude.problems(self.claude_json, self.root)
        self.assertEqual(len(found), 1)
        self.assertIn("its env block keeps it from being repaired automatically", found[0])
        self.assertNotIn("s3cret-value", found[0])
        self.assertNotIn("TOKEN", found[0])

    def test_a_stale_bundle_is_reported(self):
        self.write_servers(self.good())
        (self.root / "bunny-net" / "src" / "server.js").write_text("changed\n", encoding="utf-8")
        self.assertEqual(register_claude.problems(self.claude_json, self.root),
                         ["bunny-net: dist/server.mjs was built from other sources than src/ now holds"])


class FixableTest(Fixture):
    def setUp(self):
        super().setUp()
        patcher = unittest.mock.patch.object(register_claude, "blocker", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_nothing_is_fixable_where_register_cannot_run(self):
        self.write_servers({})
        with unittest.mock.patch.object(register_claude, "blocker", return_value="claude is not on PATH"):
            self.assertEqual(register_claude.fixable(self.claude_json, self.root), [])

    def test_correct_entries_are_left_alone(self):
        self.write_servers(self.good())
        self.assertEqual(register_claude.fixable(self.claude_json, self.root), [])

    def test_a_moved_checkout_or_a_missing_entry_is_fixable(self):
        servers = self.good()
        servers["bunny-net"] = self.entry("bunny-net")  # the checkout this entry names has moved
        del servers["domains-co-za"]
        self.write_servers(servers)
        self.assertEqual(register_claude.fixable(self.claude_json, self.root), list(build_claude.PLUGINS))

    def test_an_env_block_or_a_stale_bundle_is_left_for_a_person(self):
        servers = self.good()
        servers["bunny-net"] = self.entry("bunny-net", env={"TOKEN": "x"})
        servers["domains-co-za"] = self.entry("domains-co-za")
        self.write_servers(servers)
        (self.root / "domains-co-za" / "src" / "server.js").write_text("changed\n", encoding="utf-8")
        self.assertEqual(register_claude.fixable(self.claude_json, self.root), [])

    def test_repair_registers_only_the_fixable_entries(self):
        servers = self.good()
        servers["bunny-net"] = self.entry("bunny-net")
        self.write_servers(servers)
        with unittest.mock.patch.object(register_claude, "register") as register, \
                unittest.mock.patch.object(register_claude, "fixable", return_value=["bunny-net"]), \
                unittest.mock.patch.object(register_claude, "config_path", return_value=self.claude_json), \
                contextlib.redirect_stdout(io.StringIO()):
            register_claude.main(["--repair"])
        register.assert_called_once_with(self.claude_json, names=["bunny-net"], only_wrong=True)
        with unittest.mock.patch.object(register_claude, "register") as register, \
                unittest.mock.patch.object(register_claude, "fixable", return_value=[]), \
                unittest.mock.patch.object(register_claude, "config_path", return_value=self.claude_json), \
                contextlib.redirect_stdout(io.StringIO()):
            register_claude.main(["--repair"])
        register.assert_not_called()

    def test_the_cli_config_dir_is_the_file_checked(self):
        with unittest.mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.tmp / "profile")}):
            self.assertEqual(register_claude.config_path(), self.tmp / "profile" / ".claude.json")
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            self.assertEqual(register_claude.config_path(), Path.home() / ".claude.json")


class RegisterTest(Fixture):
    def register(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return unittest.mock.Mock(returncode=0)

        out = io.StringIO()
        with unittest.mock.patch("shutil.which", return_value="claude"), \
                unittest.mock.patch("os.path.isfile", return_value=True), \
                unittest.mock.patch("subprocess.run", side_effect=fake_run), \
                contextlib.redirect_stdout(out):
            try:
                register_claude.register(self.claude_json, Path("D:/Conclave-SDK/plugins/claude"))
                refusal = None
            except SystemExit as exc:
                refusal = str(exc)
        return calls, out.getvalue(), refusal

    def test_registration_of_named_plugins_touches_only_those(self):
        self.write_servers({"bunny-net": self.entry("bunny-net")})
        calls = []
        with unittest.mock.patch("shutil.which", return_value="claude"), \
                unittest.mock.patch("os.path.isfile", return_value=True), \
                unittest.mock.patch("subprocess.run", side_effect=lambda argv, **kw: calls.append((argv, kw))
                                    or unittest.mock.Mock(returncode=0)), \
                contextlib.redirect_stdout(io.StringIO()):
            register_claude.register(self.claude_json, Path("D:/Conclave-SDK/plugins/claude"), names=["bunny-net"])
        self.assertEqual([c[0][2:] for c in calls][0], ["remove", "bunny-net", "-s", "user"])
        self.assertEqual({c[0][-2] if c[0][2] == "add-json" else c[0][3] for c in calls}, {"bunny-net"})
        self.assertTrue(all(kw.get("timeout") == register_claude.CLI_TIMEOUT for _, kw in calls))

    def run_cli(self, **kwargs):
        calls = []
        with unittest.mock.patch("shutil.which", return_value="claude"), \
                unittest.mock.patch("os.path.isfile", return_value=True), \
                unittest.mock.patch("subprocess.run", side_effect=lambda argv, **kw: calls.append(argv)
                                    or unittest.mock.Mock(returncode=0)), \
                contextlib.redirect_stdout(io.StringIO()):
            register_claude.register(self.claude_json, Path("D:/Conclave-SDK/plugins/claude"), **kwargs)
        return calls

    def test_a_repair_leaves_an_entry_another_session_already_put_right(self):
        right = self.entry("bunny-net")  # what register() would write for the D: root below
        self.write_servers({"bunny-net": right})
        self.assertEqual(self.run_cli(names=["bunny-net"], only_wrong=True), [])

    def test_a_repair_only_adds_a_missing_entry_and_never_removes_first(self):
        self.write_servers({})
        calls = self.run_cli(names=["bunny-net"], only_wrong=True)
        self.assertEqual([c[2] for c in calls], ["add-json"])

    def test_a_repair_leaves_an_entry_that_gained_an_env_block(self):
        self.write_servers({"bunny-net": self.entry("bunny-net", args=["R:\\old\\server.mjs"], env={"T": "x"})})
        with unittest.mock.patch.object(register_claude, "registered",
                                        side_effect=[{}, register_claude.registered(self.claude_json)]):
            calls = self.run_cli(names=["bunny-net"], only_wrong=True)
        self.assertEqual(calls, [])

    def test_registration_goes_through_the_cli_at_user_scope(self):
        self.write_servers({"ticktick": {"type": "http", "url": "https://example.invalid"},
                            "bunny-net": self.entry("bunny-net")})
        calls, out, refusal = self.register()
        self.assertIsNone(refusal)
        expected = {"domains-co-za": ["add-json"], "bunny-net": ["remove", "add-json"]}  # a missing entry is only added
        self.assertEqual([c[0][2] for c in calls], [step for name in build_claude.PLUGINS for step in expected[name]])
        self.assertTrue(all(c[0][:2] == ["claude", "mcp"] for c in calls))
        added = {c[0][5]: json.loads(c[0][6]) for c in calls if c[0][2] == "add-json"}
        self.assertEqual(added["bunny-net"], {
            "type": "stdio", "command": register_claude.node_command(), "env": {},
            "args": ["D:\\Conclave-SDK\\plugins\\claude\\bunny-net\\dist\\server.mjs"]})
        self.assertEqual(sorted(added), sorted(build_claude.PLUGINS))
        self.assertTrue(all(c[0][3:5] == ["-s", "user"] for c in calls if c[0][2] == "add-json"))
        for _, kwargs in calls:  # the CLI's own output is discarded
            self.assertEqual((kwargs.get("stdout"), kwargs.get("stderr")), (-3, -3))

    def test_an_entry_with_an_env_block_is_refused_before_anything_runs_and_no_value_leaves(self):
        servers = {"domains-co-za": self.entry("domains-co-za"),
                   "bunny-net": self.entry("bunny-net", env={"TOKEN": "s3cret-value"})}
        self.write_servers(servers)
        calls, out, refusal = self.register()
        self.assertEqual(calls, [], "the CLI ran although an entry carries an env block")
        self.assertIn("bunny-net: the entry has an env block", refusal)
        self.assertNotIn("s3cret-value", refusal + out)
        self.assertNotIn("TOKEN", refusal + out)
        self.assertEqual(json.loads(self.claude_json.read_text(encoding="utf-8"))["mcpServers"], servers)

    def test_a_checkout_without_a_windows_path_is_refused(self):
        with self.assertRaises(SystemExit):
            register_claude.expected_entry("bunny-net", "/home/me/sdk/plugins/claude")


if __name__ == "__main__":
    unittest.main()
