"""Tests of the unattended kit's shared module (`scripts/lib/unattended.py`): the run profile loader."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import unittest.mock

SCRIPTS = Path(__file__).resolve().parents[1]
TEMPLATES = SCRIPTS.parent
_spec = importlib.util.spec_from_file_location("unattended_lib", SCRIPTS / "lib" / "unattended.py")
assert _spec is not None and _spec.loader is not None
unattended = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(unattended)

TEMPLATE = TEMPLATES / ".conclave" / "unattended.json"
PROMPT = TEMPLATES / "docs" / "unattended-prompt.md"
# In the SDK these files are the kit's templates; installed in a project they are the project's own, which it edits.
IN_KIT = TEMPLATES.name == "templates" and TEMPLATES.parent.name == "unattended"
in_kit_only = unittest.skipUnless(IN_KIT, "checks the shipped template; a project's profile is its own")
# The loader tests use their own profile and prompt, so they hold whatever a project does with its copies.
FIXTURE = {"schema_version": 1, "name": "impossible-os", "agent": "claude", "model": "claude-opus-5-5", "effort": "high",
           "prompt_file": "docs/run-prompt.md", "branch": "main", "skip_permissions": True,
           "tools": ["git", "python3", "tmux"], "min_disk_gb": 20, "min_ram_gb": 2, "tick_seconds": 300,
           "idle_minutes": 45, "stall_hours": 6, "preflight": []}


class LoadProfileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / ".conclave").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "docs" / "run-prompt.md").write_text("Run the plan.\n", encoding="utf-8")
        self.profile = json.loads(json.dumps(FIXTURE))

    def write(self, data):
        (self.root / ".conclave" / "unattended.json").write_text(
            data if isinstance(data, str) else json.dumps(data), encoding="utf-8")

    def refused(self, key, data=None):
        self.write(self.profile if data is None else data)
        with self.assertRaises(unattended.ProfileError) as caught:
            unattended.load_profile(self.root)
        message = str(caught.exception)
        self.assertTrue(message.startswith(".conclave/unattended.json: "), message)
        self.assertIn(key, message)
        return message

    def with_(self, **changes):
        return {**self.profile, **changes}

    @in_kit_only
    def test_the_template_set_for_a_project_loads(self):
        shutil.copyfile(PROMPT, self.root / "docs" / "unattended-prompt.md")
        configured = {**json.loads(TEMPLATE.read_text(encoding="utf-8")),
                      "name": "impossible-os", "model": "claude-opus-5-5", "effort": "high"}
        self.write(configured)
        loaded = unattended.load_profile(self.root)
        self.assertEqual(loaded, configured)
        self.assertEqual((loaded["agent"], loaded["branch"], loaded["min_disk_gb"], loaded["min_ram_gb"],
                          loaded["tick_seconds"], loaded["idle_minutes"], loaded["stall_hours"]),
                         ("claude", "main", 20, 2, 300, 45, 6))
        self.assertEqual(loaded["prompt_file"], "docs/unattended-prompt.md")

    @in_kit_only
    def test_the_shipped_template_unchanged_names_the_three_to_set(self):
        self.write(TEMPLATE.read_text(encoding="utf-8"))
        message = self.refused("name", json.loads(TEMPLATE.read_text(encoding="utf-8")))
        for key in ("name", "model", "effort"):
            self.assertIn(key, message)
        self.assertIn("set", message)

    def test_each_null_is_named(self):
        for key in ("name", "model", "effort"):
            with self.subTest(key=key):
                self.refused(key, self.with_(**{key: None}))

    def test_a_missing_profile_or_unreadable_json_is_refused(self):
        with self.assertRaises(unattended.ProfileError) as caught:
            unattended.load_profile(self.root)
        self.assertIn("missing", str(caught.exception))
        self.refused("JSON", "{not json")
        self.refused("object", "[1, 2]")

    def test_an_unknown_or_missing_key_is_refused(self):
        self.refused("agnet", self.with_(agnet="claude"))
        data = dict(self.profile)
        del data["tick_seconds"]
        self.assertIn("is required", self.refused("tick_seconds", data))

    def test_the_schema_version_must_be_1(self):
        for bad in (2, "1", True, None):
            with self.subTest(bad=bad):
                self.refused("schema_version", self.with_(schema_version=bad))

    def test_an_unknown_agent_is_refused(self):
        for bad in ("gemini", "Claude", "", None, 1):
            with self.subTest(bad=bad):
                self.refused("agent", self.with_(agent=bad))
        for good in ("claude", "codex", "agy"):
            self.write(self.with_(agent=good))
            self.assertEqual(unattended.load_profile(self.root)["agent"], good)

    def test_the_name_must_be_a_session_name(self):
        for bad in ("a", "Impossible", "-run", "has space", "x" * 42, "dots.no", 7):
            with self.subTest(bad=bad):
                self.refused("name", self.with_(name=bad))

    def test_strings_must_be_strings(self):
        for key in ("model", "effort", "branch"):
            for bad in ("", "  ", 3, ["x"]):
                with self.subTest(key=key, bad=bad):
                    self.refused(key, self.with_(**{key: bad}))
        self.refused("skip_permissions", self.with_(skip_permissions="yes"))

    def test_numbers_must_be_whole_and_positive(self):
        for key in unattended.WHOLE:
            for bad in (0, -1, 2.5, "20", True, None):
                with self.subTest(key=key, bad=bad):
                    self.refused(key, self.with_(**{key: bad}))

    def test_tools_must_be_command_names(self):
        for bad in ("git", ["git", ""], ["git", 3], None):
            with self.subTest(bad=bad):
                self.refused("tools", self.with_(tools=bad))

    def test_the_prompt_file_must_exist_inside_the_repository(self):
        outside = Path(self._tmp.name).parent / "outside-prompt.md"
        for bad in ("../outside-prompt.md", "docs/../../x.md", str(outside), "/etc/passwd", "C:/x.md", "", 4):
            with self.subTest(bad=bad):
                self.refused("prompt_file", self.with_(prompt_file=bad))
        self.assertIn("does not exist", self.refused("prompt_file", self.with_(prompt_file="docs/nope.md")))

    def test_preflight_checks_are_name_command_and_timeout(self):
        good = {"name": "suite", "command": ["python3", "-m", "unittest"], "timeout_seconds": 600}
        self.write(self.with_(preflight=[good]))
        self.assertEqual(unattended.load_profile(self.root)["preflight"], [good])
        bad_cases = [
            ("preflight", {"preflight": {"name": "x"}}),
            ("preflight[0]", {"preflight": ["python3 -m unittest"]}),
            ("preflight[0]", {"preflight": [{**good, "extra": 1}]}),
            ("preflight[0]", {"preflight": [{"name": "x", "command": ["y"]}]}),
            ("preflight[0].name", {"preflight": [{**good, "name": ""}]}),
            ("preflight[0].command", {"preflight": [{**good, "command": "python3 -m unittest"}]}),
            ("preflight[0].command", {"preflight": [{**good, "command": []}]}),
            ("preflight[0].command", {"preflight": [{**good, "command": ["python3", 1]}]}),
            ("preflight[1].timeout_seconds", {"preflight": [good, {**good, "timeout_seconds": 0}]}),
            ("preflight[0].timeout_seconds", {"preflight": [{**good, "timeout_seconds": True}]}),
        ]
        for key, change in bad_cases:
            with self.subTest(key=key, change=change):
                self.refused(key, self.with_(**change))

    def test_an_edited_profile_is_read_back_on_reload(self):
        self.write(self.profile)
        self.assertEqual(unattended.load_profile(self.root)["idle_minutes"], self.profile["idle_minutes"])
        self.write(self.with_(idle_minutes=self.profile["idle_minutes"] + 45, branch="trunk", agent="codex", effort="xhigh"))
        loaded = unattended.load_profile(self.root)
        self.assertEqual((loaded["idle_minutes"], loaded["branch"], loaded["agent"], loaded["effort"]),
                         (self.profile["idle_minutes"] + 45, "trunk", "codex", "xhigh"))

    def test_the_effort_must_be_one_the_agent_takes(self):
        self.assertIn("for claude", self.refused("effort", self.with_(effort="minimal")))
        self.refused("effort", self.with_(agent="codex", effort="max"))
        for agent, effort in (("claude", "max"), ("codex", "minimal"), ("agy", "anything")):
            self.write(self.with_(agent=agent, effort=effort))
            self.assertEqual(unattended.load_profile(self.root)["effort"], effort)

    def test_a_preflight_command_must_start_with_a_program(self):
        good = {"name": "suite", "command": ["python3"], "timeout_seconds": 60}
        for bad in ([""], ["  ", "-m"]):
            with self.subTest(bad=bad):
                self.refused("preflight[0].command", self.with_(preflight=[{**good, "command": bad}]))

    def test_a_nul_in_an_argument_or_a_path_is_refused(self):
        good = {"name": "check", "command": ["python3"], "timeout_seconds": 60}
        self.refused("preflight[0].command", self.with_(preflight=[{**good, "command": ["python3", "\0"]}]))
        self.refused("tools", self.with_(tools=["git\0"]))
        for key in ("model", "effort", "branch", "prompt_file"):
            with self.subTest(key=key):
                self.assertIn("NUL", self.refused(key, self.with_(**{key: self.profile[key] + "\0x"})))

    def denied(self, name):
        """Path.read_bytes raising PermissionError for one file, as an unreadable file does on any system."""
        real = Path.read_bytes

        def read_bytes(path):
            if path.name == name:
                raise PermissionError(13, "Permission denied", str(path))
            return real(path)
        return unittest.mock.patch.object(Path, "read_bytes", read_bytes)

    def test_a_profile_that_cannot_be_read_is_refused(self):
        self.write(self.profile)
        with self.denied("unattended.json"):
            with self.assertRaises(unattended.ProfileError) as caught:
                unattended.load_profile(self.root)
        self.assertIn("not readable", str(caught.exception))
        self.assertIn("Permission denied", str(caught.exception))

    def test_a_prompt_that_cannot_be_read_is_refused(self):
        self.write(self.profile)
        with self.denied("run-prompt.md"):
            message = self.refused("prompt_file")
        self.assertIn("Permission denied", message)

    def test_the_prompt_file_must_be_a_readable_text_file(self):
        (self.root / "docs" / "folder.md").mkdir()
        self.assertIn("not a file", self.refused("prompt_file", self.with_(prompt_file="docs/folder.md")))
        (self.root / "docs" / "binary.md").write_bytes(b"\xff\xfe\x00bad")
        self.assertIn("UTF-8", self.refused("prompt_file", self.with_(prompt_file="docs/binary.md")))

    def test_a_prompt_link_leading_outside_the_repository_is_refused(self):
        outside = Path(self._tmp.name + "-outside.md")
        outside.write_text("outside", encoding="utf-8")
        self.addCleanup(outside.unlink)
        link = self.root / "docs" / "link.md"
        try:
            link.symlink_to(outside)
        except OSError as exc:  # Windows without the symlink privilege or developer mode
            self.skipTest(f"cannot make a symlink here: {exc}")
        self.assertIn("outside the repository", self.refused("prompt_file", self.with_(prompt_file="docs/link.md")))

    @in_kit_only
    def test_the_seed_prompt_names_no_project_and_says_what_a_run_must_do(self):
        text = PROMPT.read_text(encoding="utf-8")
        for phrase in ("process-plan", "Never ask the operator", "run file", "docs/phase-runs/", "PARKED"):
            self.assertIn(phrase, text)
        for name in ("RasterFold", "Impossible OS", "Conclave-SDK"):
            self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
