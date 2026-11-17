"""The launcher profile and its loader, `scripts/lib/launchers.py` (D07 T01 section 2)."""

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "lib" / "launchers.py"
spec = importlib.util.spec_from_file_location("launchers_under_test", SCRIPT)
launchers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launchers)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = pathlib.Path(tmp.name).resolve() / "project"
        (self.project / ".conclave").mkdir(parents=True)
        (self.project / "assets").mkdir()
        (self.project / "assets/icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.path = self.project / launchers.PROFILE

    def valid(self, **changes):
        profile = {"schema_version": 1, "title": "Example Site", "icon": "assets/icon.png",
                   "agents": ["claude", "codex"], "skip_permissions": True,
                   "links": [{"label": "Dashboard", "mark": "wordpress", "run": "python3 scripts/open-dashboard.py"},
                             {"label": "Site", "mark": "site", "url": "https://example.com/"}]}
        profile.update(changes)
        return profile

    def write(self, profile):
        self.path.write_text(json.dumps(profile) if not isinstance(profile, str) else profile, encoding="utf-8")

    def load(self, profile):
        self.write(profile)
        return launchers.load_profile(self.path)

    def refused(self, profile, *words):
        """The refusal of `profile`, which must name the file and each of `words`."""
        self.write(profile)
        with self.assertRaises(launchers.ProfileError) as caught:
            launchers.load_profile(self.path)
        message = str(caught.exception)
        self.assertTrue(message.startswith(self.path.as_posix() + ": "), message)
        for word in words:
            self.assertIn(word, message)
        return message


class FileTests(Fixture):
    def test_a_valid_profile_comes_back_with_every_value_it_holds(self):
        profile = self.valid()
        self.assertEqual(self.load(profile), profile)

    def test_a_missing_folder_unreadable_or_malformed_file_is_refused_by_name(self):
        with self.assertRaises(launchers.ProfileError) as caught:
            launchers.load_profile(self.path)
        self.assertIn("no such file", str(caught.exception))
        self.path.mkdir()
        with self.assertRaises(launchers.ProfileError) as caught:
            launchers.load_profile(self.path)
        self.assertIn("is a folder", str(caught.exception))
        self.path.rmdir()
        self.path.write_bytes(b"\xff\xfe{")
        with self.assertRaises(launchers.ProfileError) as caught:
            launchers.load_profile(self.path)
        self.assertIn("not UTF-8", str(caught.exception))
        self.refused("{not json", "not JSON")
        self.refused("[]", "a profile is an object")

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), "needs POSIX permissions")
    def test_an_unreadable_file_is_refused_by_name(self):
        self.write(self.valid())
        self.path.chmod(0)
        self.addCleanup(self.path.chmod, 0o644)
        with self.assertRaises(launchers.ProfileError) as caught:
            launchers.load_profile(self.path)
        self.assertIn("cannot be read", str(caught.exception))


class KeyTests(Fixture):
    def test_an_unknown_or_missing_key_is_refused(self):
        self.refused(self.valid(colour="blue"), "colour: is not a key")
        profile = self.valid()
        del profile["links"]
        self.refused(profile, "links: is missing")

    def test_schema_version_is_the_integer_1(self):
        for value in (2, "1", True, 1.0, None):
            with self.subTest(value=value):
                self.refused(self.valid(schema_version=value), "schema_version:")

    def test_title_rules(self):
        for value, words in ((None, "must be set"), (7, "must be a string"), ("", "must not be empty"),
                             ("x" * 61, "at most 60"), (" Site", "start or end with a space"),
                             ("Site ", "start or end with a space"), ("Site.", "end with a dot"),
                             ("A/B", "'/'"), ("A:B", "':'"), ('A"B', "'\"'"), ("A|B", "'|'"), ("A\x07B", "'\\x07'"),
                             ("A\x7fB", "'\\x7f'")):
            with self.subTest(value=value):
                self.refused(self.valid(title=value), "title:", words)
        self.assertEqual(self.load(self.valid(title="x" * 60))["title"], "x" * 60)

    def test_icon_rules(self):
        (self.project / "assets/folder.png").mkdir()
        (self.project / "assets/icon.svg").write_text("<svg/>", encoding="utf-8")
        outside = self.project.parent / "outside.png"
        outside.write_bytes(b"\x89PNG")
        for value, words in ((None, "must be set"), (3, "must be a string"), ("", "must not be empty"),
                             ("/abs/icon.png", "relative to the project"), ("C:/icon.png", "relative to the project"),
                             ("../outside.png", "inside the project"), ("assets/missing.png", "does not exist"),
                             ("assets/icon.svg", ".png or .ico"), ("assets/folder.png", "is not a file")):
            with self.subTest(value=value):
                self.refused(self.valid(icon=value), "icon:", words)
        self.assertEqual(self.load(self.valid(icon="assets/icon.png"))["icon"], "assets/icon.png")
        ico = self.project / "assets/ICON.ICO"
        ico.write_bytes(b"\0\0\1\0")
        self.assertEqual(self.load(self.valid(icon="assets/ICON.ICO"))["icon"], "assets/ICON.ICO")

    def test_an_icon_reached_through_a_link_is_refused(self):
        real = self.project / "real"
        real.mkdir()
        (real / "icon.png").write_bytes(b"\x89PNG")
        try:
            (self.project / "linked").symlink_to(real, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"this system makes no symbolic link here ({exc})")
        self.refused(self.valid(icon="linked/icon.png"), "icon:", "reached through a link")

    def test_agents_rules(self):
        for value, words in (([], "at least one"), (["gemini"], "'gemini' is not an agent"),
                             (["claude", "claude"], "named twice"), ({"claude": True}, "must be a list"),
                             ("claude", "must be a list"), ([1], "1 is not an agent")):
            with self.subTest(value=value):
                self.refused(self.valid(agents=value), "agents:", words)
        self.assertEqual(self.load(self.valid(agents=["agy", "codex", "claude"]))["agents"], ["agy", "codex", "claude"])

    def test_skip_permissions_is_a_boolean(self):
        for value in (0, 1, "false", None):
            with self.subTest(value=value):
                self.refused(self.valid(skip_permissions=value), "skip_permissions:")
        self.assertIs(self.load(self.valid(skip_permissions=False))["skip_permissions"], False)


class LinkTests(Fixture):
    def link(self, **fields):
        return self.valid(links=[{"label": "Site", "mark": "site", "url": "https://example.com", **fields}])

    def test_links_is_a_list_of_objects_with_label_mark_and_one_of_run_or_url(self):
        self.refused(self.valid(links={"label": "Site"}), "links: must be a list")
        self.refused(self.valid(links=["Site"]), "links[1]: must be an object")
        self.refused(self.valid(links=[{"label": "Site", "mark": "site"}]), "links[1]: is missing run or url")
        self.refused(self.valid(links=[{"label": "Site", "url": "https://example.com"}]), "links[1]: is missing mark")
        self.refused(self.link(run="x"), "links[1]: has both run and url")
        self.refused(self.link(colour="blue"), "links[1]: colour is not a key")

    def test_label_rules(self):
        for value, words in ((5, "must be a string"), ("", "must not be empty"), ("x" * 31, "at most 30"),
                             ("A/B", "'/'"), ("Claude", "an agent's link"), ("codex", "an agent's link"),
                             ("Antigravity", "an agent's link"), ("Nightly campaign", "ends in campaign"),
                             ("Run Campaign", "ends in campaign"), ("Agy", "an agent's icon"),
                             ("---", "no letter or digit")):
            with self.subTest(value=value):
                self.refused(self.link(label=value), "links[1].label:", words)
        self.assertEqual(self.load(self.link(label="x" * 30))["links"][0]["label"], "x" * 30)

    def test_labels_are_unique_by_case_and_by_icon_slug(self):
        two = [{"label": "Admin", "mark": "site", "url": "https://example.com"},
               {"label": "ADMIN", "mark": "site", "url": "https://example.com/b"}]
        self.refused(self.valid(links=two), "links[2].label:", "used by links[1]")
        two[1]["label"] = "Admin Panel"
        two.append({"label": "Admin-Panel", "mark": "wordpress", "run": "x"})
        self.refused(self.valid(links=two), "links[3].label:", "'admin-panel', as links[2] does")

    def test_mark_and_run_rules(self):
        self.refused(self.link(mark="laravel"), "links[1].mark:", "'laravel' is not a mark")
        run = {"label": "Dash", "mark": "wordpress"}
        for value in ("", "   ", "a\nb", "a\rb", 7):
            with self.subTest(value=value):
                self.refused(self.valid(links=[dict(run, run=value)]), "links[1].run:")
        self.assertEqual(self.load(self.valid(links=[dict(run, run="python3 x.py")]))["links"][0]["run"], "python3 x.py")

    def test_url_rules(self):
        for value in ("http://example.com", "ftp://example.com", "https://", "https://exa mple.com",
                      "https://example.com/a b", "https://example.com\n", "example.com", "http://example.test.evil",
                      7):
            with self.subTest(value=value):
                self.refused(self.link(url=value), "links[1].url:")
        for value in ("https://example.com", "https://example.com:8443/wp-admin/?a=1#b", "http://localhost",
                      "http://localhost:8080/x", "http://shop.test", "http://my-app.site/path"):
            with self.subTest(value=value):
                self.assertEqual(self.load(self.link(url=value))["links"][0]["url"], value)


class ShowTests(Fixture):
    def run_show(self, *args, script=SCRIPT, cwd=None):
        return subprocess.run([sys.executable, str(script), "show", *args], capture_output=True, text=True,
                              timeout=60, cwd=cwd, creationflags=NO_WINDOW)

    def test_show_prints_the_profile_as_one_line_of_json(self):
        profile = self.valid(title="Caf\u00e9 Site")
        self.write(profile)
        done = self.run_show("--root", str(self.project))
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertEqual(len(done.stdout.splitlines()), 1)
        self.assertEqual(json.loads(done.stdout), profile)
        self.assertTrue(done.stdout.isascii())

    def test_an_installed_copy_reads_its_own_project_from_anywhere(self):
        installed = self.project / "scripts/lib/launchers.py"
        installed.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, installed)
        profile = self.valid()
        self.write(profile)
        elsewhere = self.project.parent / "elsewhere"
        elsewhere.mkdir()
        done = self.run_show(script=installed, cwd=elsewhere)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), profile)

    def test_show_refuses_on_stderr_with_exit_1_and_no_traceback(self):
        cases = [("malformed", lambda: self.write(self.valid(title=None)), "title: must be set"),
                 ("folder", lambda: self.path.mkdir(), "is a folder"),
                 ("missing", lambda: None, "no such file")]
        for name, make, words in cases:
            with self.subTest(case=name):
                if self.path.is_dir():
                    self.path.rmdir()
                elif self.path.exists():
                    self.path.unlink()
                make()
                done = self.run_show("--root", str(self.project))
                self.assertEqual((done.returncode, done.stdout), (1, ""))
                self.assertIn(words, done.stderr)
                self.assertNotIn("Traceback", done.stderr)


if __name__ == "__main__":
    unittest.main()
