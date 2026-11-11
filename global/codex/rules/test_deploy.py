import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deploy import SOURCE, merge_hooks, write_if_changed


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.desired = json.loads((SOURCE / "hooks.json").read_text(encoding="utf-8"))

    def test_merge_needs_no_previous_repository_configuration(self):
        with tempfile.TemporaryDirectory() as folder, patch("deploy.SOURCE", Path(folder)):
            self.assertEqual(merge_hooks({}, self.desired), self.desired)

    def test_modified_owned_handler_is_preserved(self):
        old = json.loads(json.dumps(self.desired))
        old["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 51
        merged = merge_hooks(old, self.desired)
        self.assertEqual(merged["hooks"]["Stop"][0], old["hooks"]["Stop"][0])

    def test_preserves_unrelated_handlers_and_metadata(self):
        other = {"type": "command", "command": "python unrelated.py"}
        original = {"description": "Personal hooks", "hooks": {"UserPromptSubmit": [{"hooks": [
            self.desired["hooks"]["UserPromptSubmit"][0]["hooks"][0], other]}]}}
        merged = merge_hooks(original, self.desired)
        self.assertEqual(merged["description"], original["description"])
        self.assertEqual(merged["hooks"]["UserPromptSubmit"][0]["hooks"], [other])
        self.assertEqual(len(original["hooks"]["UserPromptSubmit"][0]["hooks"]), 2)

    def test_redeployment_is_idempotent(self):
        first = merge_hooks({}, self.desired)
        self.assertEqual(merge_hooks(first, self.desired), first)
        self.assertEqual(sum(len(g["hooks"]) for groups in first["hooks"].values() for g in groups), 6)

    def test_different_matcher_and_modified_handler_survive(self):
        handler = {**self.desired["hooks"]["Stop"][0]["hooks"][0], "timeout": 50}
        other = {"hooks": {"PostToolUse": [{"matcher": "custom", "hooks": [handler]}]}}
        merged = merge_hooks(other, self.desired)
        self.assertEqual(merged["hooks"]["PostToolUse"][0], other["hooks"]["PostToolUse"][0])

    def test_backup_readback_and_unchanged_write(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "AGENTS.md"
            target.write_bytes(b"previous")
            write_if_changed(target, b"new")
            write_if_changed(target, b"new")
            backups = list(Path(folder).glob("*.bak"))
            self.assertEqual(target.read_bytes(), b"new")
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"previous")


if __name__ == "__main__":
    unittest.main()
