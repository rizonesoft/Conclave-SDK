"""Unit tests for tools/verify-design-rules.py."""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "verify-design-rules.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_design_rules", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VALID_RULE = """---
trigger: always_on
---
# Design Contract Rule

## Contract
- Authoritative UI contract: `design/SPEC.md`.

## Tokens and icons
- Token source: `design/tokens.json`.

## Never
- Never add raw `#RRGGBB` or `0xRRGGBB`, hardcoded `rgb()` or `ColorF`, or literal spacing, radius, or font size where a token exists.
- Never add an inline unmanaged SVG, an emoji as an icon, or an unapproved backdrop.

## Static lint
- Run `python scripts/design-lint.py` from the repository root.

## Rendered check
- Run `pwsh scripts/render-window.ps1` from the repository root.
"""

VALID_AGENTS = """# AGENTS.md
- Design contract: `design/SPEC.md`.
- Always read `.agents/rules/design-contract.md` and run `python scripts/design-lint.py`.
"""


def init_git_repo(root: pathlib.Path, files: dict[str, bytes]) -> str:
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(root), check=True)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    subprocess.run(["git", "add", "."], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), check=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=True).stdout.strip()


class TestVerifyDesignRules(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_module()

    def _base_files(self) -> dict[str, bytes]:
        raw = VALID_RULE.encode("utf-8")
        return {
            "design/SPEC.md": b"# Spec\n",
            "design/tokens.json": b"{}\n",
            "scripts/design-lint.py": b"print('ok')\n",
            "scripts/render-window.ps1": b"Write-Output 'ok'\n",
            ".agents/rules/design-contract.md": raw,
            ".claude/rules/design-contract.md": raw,
            "AGENTS.md": VALID_AGENTS.encode("utf-8"),
        }

    def test_valid_commit_passes_and_survives_later_working_tree_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            sha = init_git_repo(root, self._base_files())
            errs, count = self.mod.verify_project(root, sha, check_clean=True)
            self.assertEqual(errs, [])
            self.assertGreaterEqual(count, 4)
            # Mutate working tree (delete file on disk) and confirm --content-only still verifies recorded SHA
            (root / "design" / "SPEC.md").unlink()
            errs_content, _ = self.mod.verify_project(root, sha, check_clean=False)
            self.assertEqual(errs_content, [])
            errs_clean, _ = self.mod.verify_project(root, sha, check_clean=True)
            self.assertTrue(any("dirty tree" in e for e in errs_clean))

    def test_rejects_crlf_lf_mirror_byte_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            files = self._base_files()
            files[".claude/rules/design-contract.md"] = VALID_RULE.replace("\n", "\r\n").encode("utf-8")
            sha = init_git_repo(root, files)
            errs, _ = self.mod.verify_project(root, sha, check_clean=False)
            self.assertTrue(any("raw bytes differ" in e for e in errs), errs)

    def test_rejects_missing_command_script_at_commit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            files = self._base_files()
            del files["scripts/render-window.ps1"]
            sha = init_git_repo(root, files)
            errs, _ = self.mod.verify_project(root, sha, check_clean=False)
            self.assertTrue(any("scripts/render-window.ps1" in e for e in errs), errs)

    def test_rejects_unclosed_frontmatter_empty_section_and_incomplete_agents(self) -> None:
        bad_rule = "---\ntrigger: always_on\n# No close\n## Contract\n## Tokens and icons\n- `design/tokens.json`\n## Never\n- No `#RRGGBB`\n## Static lint\n- ok\n## Rendered check\n- ok\n"
        errs = self.mod.check_frontmatter_and_sections(bad_rule)
        self.assertTrue(any("unclosed YAML frontmatter" in e for e in errs), errs)
        self.assertTrue(any("no substantive bullet under ## Contract" in e for e in errs), errs)
        self.assertTrue(any("missing literal prohibition terms" in e for e in errs), errs)

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            files = self._base_files()
            files["AGENTS.md"] = b"# AGENTS.md\nSee `.agents/rules/design-contract.md` and `python scripts/design-lint.py`.\n"
            sha = init_git_repo(root, files)
            errs_ag, _ = self.mod.verify_project(root, sha, check_clean=False)
            self.assertTrue(any("missing authoritative contract reference" in e for e in errs_ag), errs_ag)

    def test_extracts_root_level_filename_and_checks_all_literal_bans(self) -> None:
        self.assertIn("tokens.json", self.mod.extract_referenced_paths("Use `tokens.json` for colours."))
        partial_ban = VALID_RULE.replace("spacing, radius, or font size", "spacing only")
        errs = self.mod.check_frontmatter_and_sections(partial_ban)
        self.assertTrue(any("radius" in e and "font" in e for e in errs), errs)

    def test_wsl_git_uses_positional_args_without_shell_interpolation(self) -> None:
        # Verify no client identifiers exist in tools/verify-design-rules.py
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("redfern", src.lower())
        self.assertNotIn("swiss", src.lower())
        self.assertIn("wsl.exe", src)
        self.assertNotIn("bash -lc", src)
        self.assertIn("os.path.expanduser(sys.argv[1])", src)


if __name__ == "__main__":
    unittest.main()
