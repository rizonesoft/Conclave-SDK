"""Tests for the shared local/overlay settings reader (`scripts/lib/local_settings.py`) and all callers."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
KIT_LS = REPO / "kits" / "base" / "templates" / "scripts" / "lib" / "local_settings.py"
INSTALLED_LS = REPO / "scripts" / "lib" / "local_settings.py"
ALERT_PATH = REPO / ".conclave" / "automations" / "alert.py"
WP_SITE_PATH = REPO / "kits" / "wordpress" / "templates" / "scripts" / "lib" / "wp_site.py"
VERIFY_DESIGN_PATH = REPO / "tools" / "verify-design-rules.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(root: Path, rel: str, text: str) -> Path:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def _try_symlink(link: Path, target: Path) -> bool:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link)
        return True
    except OSError:
        return False


class LocalSettingsReaderTests(unittest.TestCase):
    def setUp(self):
        self.ls = _load("test_kit_local_settings", KIT_LS)
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_override_only_reads_values(self):
        _write(self.root, ".conclave/local.toml", '[alert]\nsender = "a@example.com"\nto = "b@example.com"\n')
        data, loaded = self.ls.load_local_settings(self.root)
        self.assertEqual(loaded, (".conclave/local.toml",))
        self.assertEqual(data, {"alert": {"sender": "a@example.com", "to": "b@example.com"}})

    def test_overlay_only_reads_values(self):
        _write(self.root, ".private/local.toml", '[alert]\nsender = "ov@example.com"\nto = "to@example.com"\n')
        data, loaded = self.ls.load_local_settings(self.root)
        self.assertEqual(loaded, (".private/local.toml",))
        self.assertEqual(data, {"alert": {"sender": "ov@example.com", "to": "to@example.com"}})

    def test_both_files_merge_per_key_with_override_winning_and_non_tables_replaced_whole(self):
        _write(
            self.root,
            ".private/local.toml",
            '[alert]\nsender = "ov@example.com"\nto = "ov-to@example.com"\nkey_item = "op://Conclave/item1"\n'
            '[nested.deep]\nkeep = "from-overlay"\nwin = "from-overlay"\n'
            '[replace]\nlist_val = ["a", "b"]\nstr_val = "keep"\ntable_to_scalar = { k = 1 }\n',
        )
        _write(
            self.root,
            ".conclave/local.toml",
            '[alert]\nto = "local-to@example.com"\n'
            '[nested.deep]\nwin = "from-override"\n'
            '[replace]\nlist_val = []\nstr_val = ""\ntable_to_scalar = "scalar"\n',
        )
        merged = self.ls.read_local_settings(self.root)
        self.assertEqual(merged["alert"]["sender"], "ov@example.com")
        self.assertEqual(merged["alert"]["to"], "local-to@example.com")
        self.assertEqual(merged["alert"]["key_item"], "op://Conclave/item1")
        self.assertEqual(merged["nested"]["deep"], {"keep": "from-overlay", "win": "from-override"})
        self.assertEqual(merged["replace"]["list_val"], [])
        self.assertEqual(merged["replace"]["str_val"], "")
        self.assertEqual(merged["replace"]["table_to_scalar"], "scalar")

    def test_neither_file_returns_empty_and_no_loaded_sources(self):
        data, loaded = self.ls.load_local_settings(self.root)
        self.assertEqual(data, {})
        self.assertEqual(loaded, ())

    def test_malformed_overlay_is_refused_even_when_override_is_valid(self):
        _write(self.root, ".private/local.toml", "[alert\nbroken")
        _write(self.root, ".conclave/local.toml", '[alert]\nsender = "ok@example.com"\n')
        with self.assertRaisesRegex(self.ls.LocalSettingsError, r"\.private/local\.toml"):
            self.ls.read_local_settings(self.root)

    def test_directory_override_beside_valid_overlay_is_refused(self):
        _write(self.root, ".private/local.toml", '[alert]\nsender = "ov@example.com"\n')
        (self.root / ".conclave" / "local.toml").mkdir(parents=True)
        with self.assertRaisesRegex(self.ls.LocalSettingsError, r"\.conclave/local\.toml"):
            self.ls.read_local_settings(self.root)

    def test_broken_symlink_override_beside_valid_overlay_is_refused(self):
        _write(self.root, ".private/local.toml", '[alert]\nsender = "ov@example.com"\n')
        link = self.root / ".conclave" / "local.toml"
        if not _try_symlink(link, self.root / "does-not-exist.toml"):
            self.skipTest("symlinks require privilege on this host")
        with self.assertRaisesRegex(self.ls.LocalSettingsError, r"\.conclave/local\.toml.*broken symlink"):
            self.ls.read_local_settings(self.root)

    def test_working_file_symlink_override_is_accepted(self):
        target = _write(self.root, "external.toml", '[vault]\ncli = "custom-op"\n')
        link = self.root / ".conclave" / "local.toml"
        if not _try_symlink(link, target):
            self.skipTest("symlinks require privilege on this host")
        data = self.ls.read_local_settings(self.root)
        self.assertEqual(data["vault"]["cli"], "custom-op")

    def test_removing_overlay_reverts_cleanly_to_override_only(self):
        overlay = _write(self.root, ".private/local.toml", '[alert]\nsender = "ov@example.com"\nto = "ov@example.com"\n')
        _write(self.root, ".conclave/local.toml", '[alert]\nsender = "local@example.com"\n')
        self.assertEqual(self.ls.read_local_settings(self.root)["alert"]["to"], "ov@example.com")
        overlay.unlink()
        reverted = self.ls.read_local_settings(self.root)
        self.assertEqual(reverted, {"alert": {"sender": "local@example.com"}})


class ConsumerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_alert_settings_merges_overlay_refuses_neither_and_malformed_overlay(self):
        alert = _load("test_sdk_alert", ALERT_PATH)
        with self.assertRaisesRegex(alert.Refused, r"\.conclave[/\\]local\.toml.*missing.*\.private[/\\]local\.toml"):
            alert.settings(str(self.root))

        _write(
            self.root,
            ".private/local.toml",
            '[alert]\nsender = "ov@example.com"\nto = "ov-to@example.com"\nkey_item = "op://Conclave/item1"\n',
        )
        cfg = alert.settings(str(self.root))
        self.assertEqual(cfg["sender"], "ov@example.com")
        self.assertEqual(cfg["to"], "ov-to@example.com")

        _write(self.root, ".conclave/local.toml", '[alert]\nto = "local-to@example.com"\n')
        merged = alert.settings(str(self.root))
        self.assertEqual(merged["sender"], "ov@example.com")
        self.assertEqual(merged["to"], "local-to@example.com")

        # Missing required key names the key and both files
        _write(self.root, ".private/local.toml", '[alert]\nsender = "ov@example.com"\n')
        _write(self.root, ".conclave/local.toml", '[vault]\ncli = "conclave-op"\n')
        with self.assertRaisesRegex(alert.Refused, r"alert\.to"):
            alert.settings(str(self.root))

        # Malformed overlay beside valid override is refused
        _write(self.root, ".private/local.toml", "[alert\nbad")
        _write(
            self.root,
            ".conclave/local.toml",
            '[alert]\nsender = "a@example.com"\nto = "b@example.com"\nkey_item = "op://Conclave/item1"\n',
        )
        with self.assertRaisesRegex(alert.Refused, r"\.private/local\.toml"):
            alert.settings(str(self.root))

    def test_standalone_automations_install_runs_dry_run_from_unrelated_cwd(self):
        import forge

        target = self.root / "standalone_app"
        target.mkdir()
        res = forge.apply_kit(target, "automations")
        self.assertIn("scripts/lib/local_settings.py", res["installed"])
        _write(
            target,
            ".conclave/automations/tasks.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "folder": "\\Demo\\",
                    "tasks": [
                        {
                            "name": "demo-check",
                            "description": "Demo check",
                            "command": ["python", "-c", "print('ok')"],
                            "trigger": {"weekly": "Monday", "at": "07:00"},
                            "timeout_minutes": 1,
                        }
                    ],
                }
            ),
        )
        _write(
            target,
            ".private/local.toml",
            '[alert]\nsender = "ov@example.com"\nto = "owner@example.com"\nkey_item = "op://Conclave/item1"\n',
        )
        other_cwd = self.root / "other_cwd"
        other_cwd.mkdir()
        proc = subprocess.run(
            [sys.executable, str(target / ".conclave/automations/alert.py"), "demo-check", "--dry-run"],
            cwd=str(other_cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("From: Demo automations <ov@example.com>", proc.stdout)
        self.assertIn("To: owner@example.com", proc.stdout)

    def test_forge_load_projects_overlay_override_and_explicit_file_isolation(self):
        import forge

        with self.assertRaisesRegex(ValueError, r"\.conclave/local\.toml.*\.private/local\.toml.*missing"):
            forge.load_projects(root=self.root)

        _write(self.root, ".private/local.toml", '[[projects]]\nname = "OverlayProj"\nwindows = "C:\\\\work\\\\ov"\n')
        self.assertEqual(
            forge.load_projects(root=self.root),
            [{"name": "OverlayProj", "windows": "C:\\work\\ov", "posix": None}],
        )

        _write(self.root, ".conclave/local.toml", '[[projects]]\nname = "OverrideProj"\nposix = "/work/local"\n')
        self.assertEqual(
            forge.load_projects(root=self.root),
            [{"name": "OverrideProj", "windows": None, "posix": "/work/local"}],
        )

        # Explicit missing file refuses even though .private/local.toml exists
        with self.assertRaisesRegex(ValueError, r"missing: copy \.conclave/local\.example\.toml"):
            forge.load_projects(self.root / "missing.toml")

    def test_wp_site_vault_settings_reads_overlay_and_passes_selected_cli_and_vault(self):
        wp_site = _load("test_wp_site", WP_SITE_PATH)
        _write(self.root, ".private/local.toml", '[vault]\ncli = "/opt/overlay-op"\nname = "OverlayVault"\n')
        self.assertEqual(wp_site.vault_settings(root=self.root), ("/opt/overlay-op", "OverlayVault"))

        _write(self.root, ".conclave/local.toml", '[vault]\nname = "MachineVault"\n')
        self.assertEqual(wp_site.vault_settings(root=self.root), ("/opt/overlay-op", "MachineVault"))

        # Verify command invocation uses selected CLI and vault
        import unittest.mock

        seen = []
        cli, vault = wp_site.vault_settings(root=self.root)
        orig_op, orig_vault = wp_site.OP, wp_site.VAULT
        try:
            wp_site.OP, wp_site.VAULT = cli, vault
            item_id = "a" * 26

            def fake_run(cmd, **_kw):
                seen.append(cmd)
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=json.dumps({"id": item_id, "fields": []}), stderr=""
                )

            with unittest.mock.patch.object(wp_site.subprocess, "run", side_effect=fake_run):
                wp_site.vault_fields(item_id)
        finally:
            wp_site.OP, wp_site.VAULT = orig_op, orig_vault
        self.assertEqual(seen[0][0], "/opt/overlay-op")
        self.assertIn("MachineVault", seen[0])

    def test_verify_design_rules_fleet_reads_overlay_only_and_preserves_alias(self):
        vdr = _load("test_vdr", VERIFY_DESIGN_PATH)
        _write(
            self.root,
            ".private/local.toml",
            '[[projects]]\nname = "Resolute-SDK"\nalias = "Resolute-SDK"\nwindows = "C:\\\\work\\\\rsdk"\n',
        )
        cfg = vdr._read_local_settings(self.root)
        self.assertEqual(cfg["projects"][0]["alias"], "Resolute-SDK")

    def test_private_gitignore_in_sdk_and_provisioned_target(self):
        import forge

        sdk_check = subprocess.run(
            ["git", "check-ignore", "-v", "--", ".private/local.toml"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(sdk_check.returncode, 0, sdk_check.stderr)
        self.assertIn(".gitignore", sdk_check.stdout)
        self.assertIn(".private/", sdk_check.stdout)

        target = self.root / "new_project"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        (target / ".gitignore").write_text("build/\n", encoding="utf-8", newline="\n")
        res = forge.apply_kit(target, "base")
        self.assertEqual(res["private_gitignore"], "added")
        self.assertIn("build/", (target / ".gitignore").read_text(encoding="utf-8"))
        target_check = subprocess.run(
            ["git", "check-ignore", "-v", "--", ".private/local.toml"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(target_check.returncode, 0, target_check.stderr)
        self.assertIn(".private/", target_check.stdout)


if __name__ == "__main__":
    unittest.main()
