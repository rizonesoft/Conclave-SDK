"""Tests for the shared local/overlay settings reader (`.conclave/local_settings.py`) and all callers."""

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
KIT_LS = REPO / "kits" / "base" / "templates" / ".conclave" / "local_settings.py"
INSTALLED_LS = REPO / ".conclave" / "local_settings.py"
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

    def test_deeply_nested_toml_merges_without_recursion_error(self):
        dotted = ".".join(f"k{i}" for i in range(550))
        _write(self.root, ".private/local.toml", f'{dotted} = "overlay"\n')
        _write(self.root, ".conclave/local.toml", f'{dotted} = "override"\n')
        merged = self.ls.read_local_settings(self.root)
        cur = merged
        for i in range(550):
            cur = cur[f"k{i}"]
        self.assertEqual(cur, "override")


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
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        res = forge.apply_kit(target, "automations")
        self.assertIn(".conclave/local_settings.py", res["installed"])
        self.assertIn(".conclave/.gitignore", res["installed"])
        for rel in (".private/local.toml", ".conclave/local.toml"):
            chk = subprocess.run(
                ["git", "check-ignore", "-q", "--", rel],
                cwd=str(target),
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(chk.returncode, 0, f"{rel} not ignored in standalone automations install")
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

    def test_init_automations_no_scripts_keeps_alert_working_and_scripts_absent(self):
        import forge

        target = self.root / "no_scripts_app"
        forge.provision(target, kits=["automations"], include_scripts=False)
        self.assertFalse((target / "scripts").exists())
        self.assertTrue((target / ".conclave/local_settings.py").is_file())
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
        proc = subprocess.run(
            [sys.executable, str(target / ".conclave/automations/alert.py"), "demo-check", "--dry-run"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("From: Demo automations <ov@example.com>", proc.stdout)

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
        import io
        import contextlib

        vdr = _load("test_vdr", VERIFY_DESIGN_PATH)
        _write(
            self.root,
            ".private/local.toml",
            '[[projects]]\nname = "Resolute-SDK-Repo"\nalias = "Resolute-SDK"\nwindows = "C:\\\\work\\\\rsdk"\n'
            '[[projects]]\nname = "Other-Repo"\nalias = "OtherAlias"\nwindows = "C:\\\\work\\\\other"\n',
        )
        run_file = _write(
            self.root,
            "run.md",
            "## Fleet\n\n| Project | Commit | Disposition |\n| --- | --- | --- |\n"
            "| Resolute-SDK | abc123 | delivered |\n",
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vdr.run_fleet_mode(self.root, run_file, check_clean=False, negative_test=False)
        out = buf.getvalue()
        self.assertEqual(rc, 1)
        self.assertIn("OtherAlias", out)
        self.assertIn("Resolute-SDK", out)
        self.assertNotIn("Resolute-SDK-Repo", out)
        self.assertNotIn("Other-Repo", out)

    def test_open_dashboard_refusal_names_malformed_overlay_file(self):
        import forge

        target = self.root / "wp_site"
        target.mkdir()
        forge.apply_kit(target, "wordpress")
        _write(target, ".private/local.toml", "[vault\nbroken")
        orig_path = list(sys.path)
        saved = {name: sys.modules.pop(name, None) for name in ("wp_site", "site_ssh")}
        try:
            mod = _load("test_open_dashboard_malformed", target / "scripts/open-dashboard.py")
            with self.assertRaises(mod.Refusal) as caught:
                mod._pin()
        finally:
            sys.path[:] = orig_path
            for name, prev in saved.items():
                if prev is not None:
                    sys.modules[name] = prev
                else:
                    sys.modules.pop(name, None)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn(".private/local.toml", str(caught.exception))

    def test_open_dashboard_schema_error_in_override_only_blames_override_not_overlay(self):
        import forge

        target = self.root / "wp_override_only"
        target.mkdir()
        forge.apply_kit(target, "wordpress")
        _write(target, ".conclave/local.toml", "vault = []\n")
        orig_path = list(sys.path)
        saved = {name: sys.modules.pop(name, None) for name in ("wp_site", "site_ssh")}
        try:
            mod = _load("test_open_dashboard_override_only", target / "scripts/open-dashboard.py")
            with self.assertRaises(mod.Refusal) as caught:
                mod._pin()
        finally:
            sys.path[:] = orig_path
            for name, prev in saved.items():
                if prev is not None:
                    sys.modules[name] = prev
                else:
                    sys.modules.pop(name, None)
        self.assertEqual(str(caught.exception), "the local settings file .conclave/local.toml is not valid")

    def test_wp_site_loader_handles_drive_root_child_without_index_error(self):
        import unittest.mock

        wp_site = _load("test_wp_site_root", WP_SITE_PATH)
        with unittest.mock.patch.object(wp_site, "ROOT", Path("D:/nonexistent-site")):
            with self.assertRaisesRegex(ValueError, r"\.conclave/local_settings\.py is missing"):
                wp_site._local_settings()

    def test_verify_design_rules_fleet_without_settings_prints_controlled_failure(self):
        import contextlib
        import io

        vdr = _load("test_vdr_absent", VERIFY_DESIGN_PATH)
        run_file = _write(self.root, "run.md", "# empty\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vdr.run_fleet_mode(self.root, run_file, check_clean=False, negative_test=False)
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn(".conclave/local.toml", out)
        self.assertIn(".private/local.toml", out)

    def test_multi_kit_update_writes_shared_reader_once_and_adds_private_gitignore(self):
        import forge

        target = self.root / "pre_overlay_proj"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        (target / ".gitignore").write_text("build/\n", encoding="utf-8", newline="\n")
        forge.apply_kit(target, "base")
        forge.apply_kit(target, "automations")
        # Simulate a pre-overlay install: remove local_settings.py from disk and kits.json, and remove .private/ from .gitignore
        (target / ".conclave/local_settings.py").unlink()
        rec_path = target / ".conclave/kits.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        rec["files"].pop(".conclave/local_settings.py", None)
        rec_path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8", newline="\n")
        (target / ".gitignore").write_text("build/\n", encoding="utf-8", newline="\n")
        dry = forge.update_project(target, dry_run=True)
        self.assertEqual(dry["written"].count(".conclave/local_settings.py"), 1)
        self.assertEqual(dry["private_gitignore"], "would_add")

        res = forge.update_project(target)
        self.assertEqual(res["written"].count(".conclave/local_settings.py"), 1)
        self.assertFalse(any(item.get("state") == "changed-since-diff" for item in res["left"]))
        self.assertEqual(res["private_gitignore"], "added")
        self.assertIn("build/", (target / ".gitignore").read_text(encoding="utf-8"))
        chk = subprocess.run(
            ["git", "check-ignore", "-q", "--", ".private/local.toml"],
            cwd=str(target),
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0)

    def test_broad_negation_gitignore_and_symlink_refusal(self):
        import forge

        target = self.root / "broad_neg"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        (target / ".gitignore").write_text(".private/\n!*/\n", encoding="utf-8", newline="\n")
        dry = forge.apply_kit(target, "base", dry_run=True)
        self.assertEqual(dry["private_gitignore"], "would_add")
        res = forge.apply_kit(target, "base")
        self.assertEqual(res["private_gitignore"], "added")
        chk = subprocess.run(
            ["git", "check-ignore", "-q", "--", ".private/local.toml"],
            cwd=str(target),
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0)

        sym_target = self.root / "sym_gitignore"
        sym_target.mkdir()
        external = _write(self.root, "ext_gitignore", "build/\n")
        if _try_symlink(sym_target / ".gitignore", external):
            with self.assertRaisesRegex(ValueError, r"symlinked \.gitignore"):
                forge.apply_kit(sym_target, "base")
            self.assertFalse((sym_target / ".conclave").exists(), "refusal must happen before writing any kit file")

    def test_global_excludes_for_local_toml_still_adds_project_private_gitignore(self):
        import forge

        target = self.root / "global_excl_proj"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        global_excl = _write(self.root, "global.ignore", "local.toml\n")
        subprocess.run(["git", "config", "core.excludesFile", str(global_excl)], cwd=str(target), check=True, timeout=15)
        res = forge.apply_kit(target, "base")
        self.assertEqual(res["private_gitignore"], "created")
        chk = subprocess.run(
            ["git", "check-ignore", "-v", "--", ".private/plugins/example.py"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0, chk.stderr)
        self.assertTrue(chk.stdout.startswith(".gitignore:"), chk.stdout)

    def test_existing_conclave_gitignore_omitting_local_toml_gets_protected(self):
        import forge

        target = self.root / "existing_conclave_ig"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        _write(target, ".conclave/.gitignore", "cache/\n")
        res = forge.apply_kit(target, "automations")
        self.assertEqual(res.get("local_gitignore"), "added")
        chk = subprocess.run(
            ["git", "check-ignore", "-v", "--", ".conclave/local.toml"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0, chk.stderr)
        self.assertIn("cache/", (target / ".conclave/.gitignore").read_text(encoding="utf-8"))

    def test_selective_only_update_refuses_consumer_without_local_settings(self):
        import forge

        target = self.root / "selective_update"
        target.mkdir()
        forge.apply_kit(target, "automations")
        (target / ".conclave/local_settings.py").unlink()
        rec_path = target / ".conclave/kits.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        rec["files"].pop(".conclave/local_settings.py", None)
        rec["files"][".conclave/automations/alert.py"]["sha256"] = "0" * 64
        rec_path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8", newline="\n")
        (target / ".conclave/automations/alert.py").write_text("# old\n", encoding="utf-8", newline="\n")
        rec["files"][".conclave/automations/alert.py"]["sha256"] = forge.file_digest(b"# old\n")
        rec_path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(ValueError, r"--only selection updates a settings consumer without \.conclave/local_settings\.py"):
            forge.update_project(target, only=[".conclave/automations"])
        self.assertEqual((target / ".conclave/automations/alert.py").read_text(encoding="utf-8"), "# old\n")

    def test_open_dashboard_both_files_bad_override_blames_override(self):
        import forge

        target = self.root / "wp_both_bad_override"
        target.mkdir()
        forge.apply_kit(target, "wordpress")
        _write(target, ".private/local.toml", '[vault]\ncli = "conclave-op"\nname = "Conclave"\n')
        _write(target, ".conclave/local.toml", "vault = []\n")
        orig_path = list(sys.path)
        saved = {name: sys.modules.pop(name, None) for name in ("wp_site", "site_ssh")}
        try:
            mod = _load("test_open_dashboard_both_bad_ov", target / "scripts/open-dashboard.py")
            with self.assertRaises(mod.Refusal) as caught:
                mod._pin()
        finally:
            sys.path[:] = orig_path
            for name, prev in saved.items():
                if prev is not None:
                    sys.modules[name] = prev
                else:
                    sys.modules.pop(name, None)
        self.assertEqual(str(caught.exception), "the local settings file .conclave/local.toml is not valid")

    def test_verify_design_rules_fleet_incomplete_entry_prints_controlled_failure(self):
        import contextlib
        import io

        vdr = _load("test_vdr_incomplete", VERIFY_DESIGN_PATH)
        _write(self.root, ".private/local.toml", '[[projects]]\nname = "Resolute-SDK"\n')
        run_file = _write(self.root, "run.md", "# empty\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vdr.run_fleet_mode(self.root, run_file, check_clean=False, negative_test=False)
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn("windows", out)
        self.assertIn(".private/local.toml", out)

    def test_negated_local_toml_in_conclave_gitignore_is_fixed(self):
        import forge

        target = self.root / "neg_local_toml"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        _write(target, ".conclave/.gitignore", "local.toml\n!local.toml\n")
        res = forge.apply_kit(target, "automations")
        self.assertEqual(res.get("local_gitignore"), "added")
        chk = subprocess.run(
            ["git", "check-ignore", "-v", "--", ".conclave/local.toml"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0, chk.stderr)
        pattern = chk.stdout.splitlines()[0].split(":", 2)[2].split("\t", 1)[0]
        self.assertFalse(pattern.startswith("!"), chk.stdout)

    def test_selective_only_update_creates_missing_conclave_gitignore(self):
        import forge

        target = self.root / "selective_missing_ig"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        forge.apply_kit(target, "automations")
        (target / ".conclave/.gitignore").unlink()
        (target / ".conclave/local_settings.py").unlink()
        rec_path = target / ".conclave/kits.json"
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        rec["files"].pop(".conclave/local_settings.py", None)
        rec["files"].pop(".conclave/.gitignore", None)
        rec_path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8", newline="\n")
        res = forge.update_project(target, only=[".conclave/local_settings.py"])
        self.assertEqual(res.get("local_gitignore"), "created")
        chk = subprocess.run(
            ["git", "check-ignore", "-q", "--", ".conclave/local.toml"],
            cwd=str(target),
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0)

    def test_verify_design_rules_fleet_validates_all_entries_and_alias_type(self):
        import contextlib
        import io

        vdr = _load("test_vdr_all_entries", VERIFY_DESIGN_PATH)
        run_file = _write(self.root, "run.md", "# empty\n")
        # Non-Resolute-SDK entry missing windows
        _write(
            self.root,
            ".private/local.toml",
            '[[projects]]\nname = "Resolute-SDK"\nwindows = "C:\\\\work\\\\rsdk"\n'
            '[[projects]]\nname = "Second"\n',
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vdr.run_fleet_mode(self.root, run_file, check_clean=False, negative_test=False)
        self.assertEqual(rc, 1)
        self.assertIn("Second", buf.getvalue())
        self.assertIn("windows", buf.getvalue())

        # Non-string alias
        _write(
            self.root,
            ".private/local.toml",
            '[[projects]]\nname = "Resolute-SDK"\nalias = ["bad"]\nwindows = "C:\\\\work\\\\rsdk"\n',
        )
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = vdr.run_fleet_mode(self.root, run_file, check_clean=False, negative_test=False)
        self.assertEqual(rc2, 1)
        self.assertIn("alias", buf2.getvalue())

    def test_wp_site_reads_each_settings_file_only_once(self):
        import unittest.mock

        wp_site = _load("test_wp_site_once", WP_SITE_PATH)
        ls = wp_site._local_settings()
        _write(self.root, ".private/local.toml", '[vault]\ncli = "ov-op"\nname = "OvVault"\n')
        _write(self.root, ".conclave/local.toml", '[vault]\nname = "LocalVault"\n')
        calls = []
        real_read = ls.read_toml_file

        def counting_read(p, *, label=None):
            calls.append(label or str(p))
            return real_read(p, label=label)

        with unittest.mock.patch.object(wp_site, "_local_settings", return_value=ls), \
             unittest.mock.patch.object(ls, "read_toml_file", side_effect=counting_read):
            self.assertEqual(wp_site.vault_settings(root=self.root), ("ov-op", "LocalVault"))
        self.assertEqual(len(calls), 2, f"expected 2 reads (overlay + override), got {calls}")

    def test_private_star_with_child_negation_is_replaced_by_directory_ignore(self):
        import forge

        target = self.root / "child_neg_proj"
        target.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        (target / ".gitignore").write_text(".private/*\n!.private/README.md\n", encoding="utf-8", newline="\n")
        res = forge.apply_kit(target, "base")
        self.assertEqual(res["private_gitignore"], "added")
        chk = subprocess.run(
            ["git", "check-ignore", "-q", "--", ".private/README.md"],
            cwd=str(target),
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0)

    def test_verify_design_rules_fleet_rejects_duplicate_alias(self):
        import contextlib
        import io

        vdr = _load("test_vdr_dup_alias", VERIFY_DESIGN_PATH)
        _write(
            self.root,
            ".private/local.toml",
            '[[projects]]\nname = "First"\nalias = "Shared"\nwindows = "C:\\\\work\\\\a"\n'
            '[[projects]]\nname = "Second"\nalias = "Shared"\nwindows = "C:\\\\work\\\\b"\n',
        )
        run_file = _write(self.root, "run.md", "# empty\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vdr.run_fleet_mode(self.root, run_file, check_clean=False, negative_test=False)
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn("duplicate alias", out)
        self.assertIn("First", out)
        self.assertIn("Second", out)
        self.assertIn(".private/local.toml", out)

    def test_wp_site_quoted_top_level_key_does_not_collide_with_nested_provenance(self):
        wp_site = _load("test_wp_site_quoted", WP_SITE_PATH)
        _write(self.root, ".private/local.toml", "[vault]\ncli = []\n")
        _write(self.root, ".conclave/local.toml", '"vault.cli" = "unrelated"\n')
        with self.assertRaisesRegex(ValueError, r"^\.private/local\.toml: vault\.cli"):
            wp_site.vault_settings(root=self.root)

    def test_indented_gitignore_rules_before_git_init_are_not_treated_as_effective(self):
        import forge

        target = self.root / "pre_git_indented"
        target.mkdir()
        _write(target, ".gitignore", "  .private/\n")
        _write(target, ".conclave/.gitignore", "  local.toml\n")
        res = forge.apply_kit(target, "automations")
        self.assertEqual(res["private_gitignore"], "added")
        self.assertEqual(res.get("local_gitignore"), "added")
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        for rel in (".private/local.toml", ".conclave/local.toml"):
            chk = subprocess.run(
                ["git", "check-ignore", "-q", "--", rel],
                cwd=str(target),
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(chk.returncode, 0, f"{rel} not ignored after git init")

    def test_replacing_table_with_scalar_clears_descendant_provenance(self):
        ls = _load("test_ls_clear_desc", KIT_LS)
        _write(self.root, ".private/local.toml", '[vault]\ncli = "ov-op"\nname = "Ov"\n')
        _write(self.root, ".conclave/local.toml", "vault = false\n")
        merged, _loaded, origins = ls.load_local_settings_with_origins(self.root)
        self.assertIs(merged["vault"], False)
        self.assertEqual(origins[("vault",)], ".conclave/local.toml")
        self.assertNotIn(("vault", "cli"), origins)
        self.assertNotIn(("vault", "name"), origins)

    def test_git_check_ignore_fatal_error_is_propagated_not_swallowed(self):
        import unittest.mock
        import forge

        target = self.root / "dubious_repo"
        target.mkdir()
        (target / ".git").mkdir()
        _write(target, ".gitignore", ".private/\n")
        fatal = subprocess.CompletedProcess(["git"], 128, stdout="", stderr="fatal: detected dubious ownership")
        with unittest.mock.patch.object(forge.subprocess, "run", return_value=fatal):
            with self.assertRaisesRegex(ValueError, r"git rev-parse failed.*128.*dubious ownership"):
                forge._ensure_private_gitignore(target)

    def test_monorepo_subdirectory_detects_enclosing_repo_and_refuses_tracked_local_toml(self):
        import forge

        mono = self.root / "monorepo"
        sub = mono / "apps" / "web"
        sub.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(mono), check=True, timeout=15)
        # Track .conclave/local.toml BEFORE apply_kit: preflight must refuse with zero kit files written
        _write(sub, ".conclave/local.toml", '[paths]\nscratch = "x"\n')
        subprocess.run(["git", "add", "-f", "apps/web/.conclave/local.toml"], cwd=str(mono), check=True, timeout=15)
        with self.assertRaisesRegex(ValueError, r"already tracked in git"):
            forge.apply_kit(sub, "automations")
        self.assertFalse((sub / ".conclave/local_settings.py").exists(), "apply_kit must refuse before writing")

        # Untrack it, apply kit, then track it again and verify update_project also refuses before writing
        subprocess.run(["git", "rm", "-q", "--cached", "apps/web/.conclave/local.toml"], cwd=str(mono), check=True, timeout=15)
        res = forge.apply_kit(sub, "automations")
        self.assertEqual(res["private_gitignore"], "created")
        self.assertTrue(forge._git_repo_ignores(sub, ".private/", allowed_sources=(".gitignore",),
                                                require_patterns=(".private/",)))
        (sub / ".conclave/local_settings.py").unlink()
        subprocess.run(["git", "add", "-f", "apps/web/.conclave/local.toml"], cwd=str(mono), check=True, timeout=15)
        with self.assertRaisesRegex(ValueError, r"already tracked in git"):
            forge.update_project(sub)
        self.assertFalse((sub / ".conclave/local_settings.py").exists(), "update_project must refuse before writing")

    def test_concurrent_gitignore_edit_is_preserved_by_kernel_append(self):
        import unittest.mock
        import forge

        target = self.root / "concurrent_ig"
        target.mkdir()
        ig = _write(target, ".gitignore", "build/\n")
        real_append = forge._append_gitignore_rule

        def racing_append(path, rule_line, *, creating):
            # Simulate an editor saving a new rule AFTER Forge read the file and right before appending
            path.write_bytes(b"build/\ndist/")
            return real_append(path, rule_line, creating=creating)

        with unittest.mock.patch.object(forge, "_append_gitignore_rule", side_effect=racing_append):
            res = forge._ensure_private_gitignore(target)
        self.assertEqual(res, "added")
        content = ig.read_bytes()
        self.assertIn(b"dist/", content)
        self.assertIn(b"\n.private/\n", content)

    def test_short_write_retries_until_complete_and_post_open_concurrent_append_survives(self):
        import unittest.mock
        import forge

        target = self.root / "short_write_proj"
        target.mkdir()
        ig = target / ".gitignore"
        real_write = forge.os.write
        real_open = forge._open_regular_append
        first_call = [True]

        def interleaved_open(path, *, exclusive):
            fd = real_open(path, exclusive=exclusive)
            if exclusive and first_call[0]:
                first_call[0] = False
                # Second process appends AFTER first process exclusively created the file
                other_fd = real_open(path, exclusive=False)
                try:
                    real_write(other_fd, b"other/\n")
                finally:
                    os.close(other_fd)
            return fd

        def short_write(fd, buf):
            # Return 2 bytes at a time to prove _write_all completes the entire rule
            return real_write(fd, bytes(buf[:2]))

        with unittest.mock.patch.object(forge, "_open_regular_append", side_effect=interleaved_open), \
             unittest.mock.patch.object(forge.os, "write", side_effect=short_write):
            forge._append_gitignore_rule(ig, b".private/\n", creating=True)
        content = ig.read_bytes()
        self.assertIn(b"other/\n", content)
        self.assertTrue(forge._gitignore_bytes_end_with_rule(content, b".private/"))

    def test_git_worktree_prefix_preserves_leading_space_in_monorepo_dir(self):
        import unittest.mock
        import forge

        rev_out = subprocess.CompletedProcess(["git"], 0, stdout=" client/\n", stderr="")
        ls_out = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        chk_out = subprocess.CompletedProcess(
            ["git"], 0, stdout=b" client/.gitignore\x001\x00.private/\x00.private/\x00", stderr=b""
        )
        with unittest.mock.patch.object(forge.shutil, "which", return_value="git"), \
             unittest.mock.patch.object(forge.subprocess, "run", side_effect=[rev_out, ls_out, chk_out]):
            self.assertTrue(
                forge._git_repo_ignores(
                    self.root,
                    ".private/",
                    allowed_sources=(".gitignore",),
                    require_patterns=(".private/",),
                )
            )

    def test_missing_git_binary_in_existing_checkout_is_refused(self):
        import unittest.mock
        import forge

        mono = self.root / "no_git_bin_repo"
        sub = mono / "sub"
        sub.mkdir(parents=True)
        (mono / ".git").mkdir()
        with unittest.mock.patch.object(forge.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, r"git is not on PATH"):
                forge._ensure_private_gitignore(sub)

    def test_check_ignore_nul_parser_handles_colon_in_monorepo_path(self):
        import unittest.mock
        import forge

        fake_out = b"clients/acme:west/.gitignore\x001\x00.private/\x00.private/\x00"
        with unittest.mock.patch.object(forge, "_check_untracked_in_git", return_value="clients/acme:west/"), \
             unittest.mock.patch.object(
                 forge.subprocess,
                 "run",
                 return_value=subprocess.CompletedProcess(["git"], 0, stdout=fake_out, stderr=b""),
             ):
            self.assertTrue(
                forge._git_repo_ignores(
                    self.root,
                    ".private/",
                    allowed_sources=(".gitignore",),
                    require_patterns=(".private/",),
                )
            )

    def test_cr_only_gitignore_before_git_init_appends_lf_canonical_rule(self):
        import forge

        target = self.root / "cr_only_proj"
        target.mkdir()
        (target / ".gitignore").write_bytes(b"build/\r.private/\r")
        res = forge.apply_kit(target, "base")
        self.assertEqual(res["private_gitignore"], "added")
        # Idempotent on second call once LF-delimited canonical rule is at the end
        res2 = forge.apply_kit(target, "base")
        self.assertEqual(res2["private_gitignore"], "already_present")
        subprocess.run(["git", "init", "-q"], cwd=str(target), check=True, timeout=15)
        chk = subprocess.run(
            ["git", "check-ignore", "-q", "--", ".private/local.toml"],
            cwd=str(target),
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(chk.returncode, 0)

    def test_forge_load_projects_accepts_optional_fleet_alias(self):
        import forge

        _write(
            self.root,
            ".private/local.toml",
            '[[projects]]\nname = "Resolute-SDK"\nalias = "RSDK"\nwindows = "C:\\\\work\\\\rsdk"\n',
        )
        self.assertEqual(
            forge.load_projects(root=self.root),
            [{"name": "Resolute-SDK", "windows": "C:\\work\\rsdk", "posix": None}],
        )

    def test_verify_design_rules_fleet_rejects_non_string_posix(self):
        import contextlib
        import io

        vdr = _load("test_vdr_bad_posix", VERIFY_DESIGN_PATH)
        _write(
            self.root,
            ".private/local.toml",
            '[[projects]]\nname = "Resolute-SDK"\nwindows = "C:\\\\work\\\\rsdk"\nposix = ["/mnt/d/rsdk"]\n',
        )
        run_file = _write(self.root, "run.md", "# empty\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vdr.run_fleet_mode(self.root, run_file, check_clean=False, negative_test=False)
        self.assertEqual(rc, 1)
        self.assertIn("posix", buf.getvalue())
        self.assertIn(".private/local.toml", buf.getvalue())

    def test_minimal_override_preserves_overlay_alert_settings(self):
        alert = _load("test_sdk_alert_min", ALERT_PATH)
        _write(
            self.root,
            ".private/local.toml",
            '[alert]\nsender = "ov@example.com"\nto = "owner@example.com"\nkey_item = "op://Conclave/item1"\n',
        )
        _write(self.root, ".conclave/local.toml", '[paths]\nscratch = "C:\\\\work\\\\tmp"\n')
        cfg = alert.settings(str(self.root))
        self.assertEqual(cfg["sender"], "ov@example.com")
        self.assertEqual(cfg["to"], "owner@example.com")
        self.assertEqual(cfg["key_item"], "op://Conclave/item1")

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
        (target / ".gitignore").write_text("build/\n.private/\n!.private/\n", encoding="utf-8", newline="\n")
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
