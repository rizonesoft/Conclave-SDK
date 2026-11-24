"""Unit tests for tools/verify-design-rules.py."""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

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

    def test_rejects_missing_command_script_and_missing_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            files = self._base_files()
            del files["scripts/render-window.ps1"]
            sha = init_git_repo(root, files)
            errs, _ = self.mod.verify_project(root, sha, check_clean=False)
            self.assertTrue(any("scripts/render-window.ps1" in e for e in errs), errs)
            # No source path like src/ui/theme.rs is unconditionally exempted
            bad_rule = VALID_RULE.replace("design/tokens.json", "src/ui/theme.rs")
            p_errs, _ = self.mod.check_rule_paths_at_commit(bad_rule, root, sha)
            self.assertTrue(any("src/ui/theme.rs" in e for e in p_errs), p_errs)

    def test_rejects_unclosed_frontmatter_and_empty_sections(self) -> None:
        bad_rule = "---\ntrigger: always_on\n# No close\n## Contract\n## Tokens and icons\n- `design/tokens.json`\n## Never\n- No `#RRGGBB`\n## Static lint\n- ok\n## Rendered check\n- ok\n"
        errs = self.mod.check_frontmatter_and_sections(bad_rule)
        self.assertTrue(any("unclosed YAML frontmatter" in e for e in errs), errs)
        self.assertTrue(any("no substantive bullet under ## Contract" in e for e in errs), errs)
        self.assertTrue(any("missing literal prohibition terms" in e for e in errs), errs)

    def test_rejects_missing_or_wrong_contract_and_missing_or_planned_lint_in_agents_md(self) -> None:
        # Missing contract when rule link and lint are present
        errs_no_contract = self.mod.check_agents_md_against_rule(
            "# AGENTS.md\nSee `.agents/rules/design-contract.md` and `python scripts/design-lint.py`.\n",
            VALID_RULE,
            has_provider=False,
        )
        self.assertTrue(any("missing authoritative contract reference" in e for e in errs_no_contract), errs_no_contract)

        # Missing installed lint citation
        errs_no_lint = self.mod.check_agents_md_against_rule(
            "# AGENTS.md\nSee `design/SPEC.md` and `.agents/rules/design-contract.md`.\n",
            VALID_RULE,
            has_provider=False,
        )
        self.assertTrue(any("missing installed static lint reference" in e for e in errs_no_lint), errs_no_lint)

        # Planned lint text rejected when rule declares an installed lint script
        errs_planned = self.mod.check_agents_md_against_rule(
            "# AGENTS.md\nSee `design/SPEC.md` and `.agents/rules/design-contract.md`; static design lint is planned.\n",
            VALID_RULE,
            has_provider=False,
        )
        self.assertTrue(any("missing installed static lint reference" in e for e in errs_planned), errs_planned)

        # Local pointer DESIGN.md alone rejected for a consumer with a provider
        provider_rule = VALID_RULE.replace("`design/SPEC.md`", "`DESIGN.md` at `sdk.json` (`sdk/DESIGN.md`)")
        errs_ptr = self.mod.check_agents_md_against_rule(
            "# AGENTS.md\nSee `DESIGN.md`, `.agents/rules/design-contract.md`, and `scripts/design-lint.py`.\n",
            provider_rule,
            has_provider=True,
        )
        self.assertTrue(any("missing authoritative contract reference" in e for e in errs_ptr), errs_ptr)

    def test_extracts_root_level_scripts_and_tokens_and_checks_all_literal_bans(self) -> None:
        extracted = self.mod.extract_referenced_paths("Use `tokens.json` and run `pwsh render.ps1` or `python lint.py`.")
        self.assertIn("tokens.json", extracted)
        self.assertIn("render.ps1", extracted)
        self.assertIn("lint.py", extracted)
        partial_ban = VALID_RULE.replace("spacing, radius, or font size", "spacing only")
        errs = self.mod.check_frontmatter_and_sections(partial_ban)
        self.assertTrue(any("radius" in e and "font" in e for e in errs), errs)

    def test_wsl_git_preserves_argv_boundaries_without_shell_interpolation(self) -> None:
        fake_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"ok", stderr=b"")
        with mock.patch.object(self.mod.subprocess, "run", return_value=fake_proc) as m_run:
            self.mod.run_git_bytes(
                pathlib.Path(r"\\wsl.localhost\Ubuntu\home\user\example-site"),
                ["show", "$(id):x"],
                "~/example-site",
            )
            self.assertEqual(m_run.call_count, 1)
            cmd = m_run.call_args.args[0]
            kwargs = m_run.call_args.kwargs
            self.assertFalse(kwargs.get("shell", False))
            self.assertEqual(cmd[:4], ["wsl.exe", "--exec", "python3", "-c"])
            self.assertEqual(cmd[5:], ["~/example-site", "show", "$(id):x"])

    def test_validate_held_retry_rejects_unrelated_section(self) -> None:
        unrelated = {
            "title": "Reviewer Scripts Current in ExampleProj",
            "depends": ["D00 T03 §3"],
            "body": "Refreshes reviewer scripts in ExampleProj.",
        }
        errs = self.mod.validate_held_retry("ExampleProj", "D00 T03 §10", unrelated, {"D00 T03 §10"})
        self.assertTrue(any("does not depend on D00 T03 §5" in e for e in errs), errs)
        self.assertTrue(any("does not deliver .agents/rules/design-contract.md" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
