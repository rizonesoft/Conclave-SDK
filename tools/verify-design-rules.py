#!/usr/bin/env python3
"""Verify .agents/rules/design-contract.md, its Claude mirror, and AGENTS.md across projects."""

import argparse
import json
import pathlib
import re
import subprocess
import sys

REQUIRED_HEADINGS = (
    "## Contract",
    "## Tokens and icons",
    "## Never",
    "## Static lint",
    "## Rendered check",
)

REQUIRED_BANS = ("#RRGGBB", "0xRRGGBB", "rgb()", "ColorF", "SVG", "emoji", "backdrop")
PROVIDER_PREFIXES = ("shared/resolute-ui/", "shared/lucide/")
NON_TRACKED_EXACT = {
    "build/renders/",
    "src/ui/theme.rs",
    "src/res",
    "assets/icons/",
    "design/icons/",
    "assets/icons/src/",
    "design/contract/",
    "design/screens/",
    "design/ui/",
    "native/ui/",
    "shared/",
    "todo/",
    "sdk/DESIGN.md",
}


def run_git(root: pathlib.Path, args: list[str], posix: str = "") -> subprocess.CompletedProcess[str]:
    if str(root).startswith("\\\\wsl") and posix:
        quoted = " ".join(f"'{a}'" if " " in a else a for a in args)
        cmd = ["wsl.exe", "bash", "-lc", f"cd {posix} && git {quoted}"]
    else:
        cmd = ["git", "-C", str(root)] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def extract_file_paths(rule_text: str) -> list[str]:
    paths: list[str] = []
    for m in re.finditer(r"`([^`]+)`", rule_text):
        tok = m.group(1).strip()
        if " " in tok or tok.startswith(("#", "0x", "--", "-")) or "§" in tok:
            continue
        if "(" in tok or ")" in tok or "*" in tok or "<" in tok:
            continue
        if tok in (
            "strict",
            "theme-only",
            "Path",
            "KitsuneMenu",
            "Barlow",
            "Barlow Condensed",
            "Mr Dafoe",
            "isotone::ui",
            "recto-ui",
            "Steward.Console",
            "Resolute-SDK",
            "always_on",
        ):
            continue
        if "/" in tok or tok.endswith(
            (".md", ".json", ".xaml", ".css", ".py", ".ps1", ".mjs", ".cs", ".h", ".svg", ".png", ".ico", ".html")
        ):
            paths.append(tok)
    return paths


def check_rule_paths(
    rule_text: str,
    project_root: pathlib.Path,
    provider_root: pathlib.Path | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    paths = extract_file_paths(rule_text)
    if not paths:
        errors.append("no file paths extracted")
    sdk_commit = None
    sdk_json = project_root / "sdk.json"
    if sdk_json.exists():
        try:
            sdk_commit = json.loads(sdk_json.read_text(encoding="utf-8")).get("commit")
        except Exception:
            sdk_commit = None
    for rel in paths:
        if rel in NON_TRACKED_EXACT:
            continue
        if rel.startswith(PROVIDER_PREFIXES) and sdk_commit and provider_root is not None:
            r = subprocess.run(
                ["git", "-C", str(provider_root), "ls-tree", "-r", "--name-only", sdk_commit, rel.rstrip("/")],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if r.returncode != 0 or not r.stdout.strip():
                errors.append(f"provider path missing at {sdk_commit[:8]}: {rel}")
            continue
        if not (project_root / rel).exists():
            errors.append(f"missing path: {rel}")
    return errors, paths


def verify_project(
    project_root: pathlib.Path,
    commit: str = "HEAD",
    posix: str = "",
    provider_root: pathlib.Path | None = None,
) -> list[str]:
    errs: list[str] = []
    r_rule = run_git(project_root, ["show", f"{commit}:.agents/rules/design-contract.md"], posix)
    if r_rule.returncode != 0:
        return [f"missing .agents/rules/design-contract.md at {commit}"]
    rule_txt = r_rule.stdout
    lines = rule_txt.splitlines()
    if len(lines) >= 40:
        errs.append(f"lines={len(lines)}>=40")
    if not (len(lines) >= 3 and lines[0].strip() == "---" and "trigger: always_on" in lines[1:4]):
        errs.append("missing trigger: always_on frontmatter")
    for h in REQUIRED_HEADINGS:
        if h not in rule_txt:
            errs.append(f"missing heading {h}")
    for b in REQUIRED_BANS:
        if b not in rule_txt:
            errs.append(f"missing ban {b}")
    if "\u2014" in rule_txt or "\u2013" in rule_txt:
        errs.append("contains em/en dash")
    p_errs, _ = check_rule_paths(rule_txt, project_root, provider_root)
    errs.extend(p_errs)
    if (project_root / ".claude" / "rules").exists():
        r_mir = run_git(project_root, ["show", f"{commit}:.claude/rules/design-contract.md"], posix)
        if r_mir.returncode != 0 or r_mir.stdout != rule_txt:
            errs.append("claude mirror missing or differs at commit")
    r_ag = run_git(project_root, ["show", f"{commit}:AGENTS.md"], posix)
    if r_ag.returncode != 0 or ".agents/rules/design-contract.md" not in r_ag.stdout:
        errs.append("AGENTS.md missing .agents/rules/design-contract.md citation at commit")
    r_st = run_git(project_root, ["status", "--short"], posix)
    if r_st.stdout.strip():
        errs.append(f"dirty tree: {r_st.stdout.strip()[:80]}")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify a project's design-contract rule, mirror, and AGENTS.md.")
    ap.add_argument("--project", required=True, help="Path to the target project checkout.")
    ap.add_argument("--commit", default="HEAD", help="Commit SHA to inspect (default: HEAD).")
    ap.add_argument("--posix", default="", help="Optional WSL POSIX path for git commands.")
    ap.add_argument("--provider", default="", help="Optional provider checkout path for sdk.json theme refs.")
    ap.add_argument("--negative-test", action="store_true", help="Also prove a scratch missing-path copy fails.")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.project)
    provider = pathlib.Path(args.provider) if args.provider else None
    errs = verify_project(root, args.commit, args.posix, provider)
    if errs:
        print(f"FAIL {root.name}: {errs}")
        return 1
    print(f"OK {root.name} at {args.commit}")
    if args.negative_test:
        rule_txt = (root / ".agents" / "rules" / "design-contract.md").read_text(encoding="utf-8")
        paths = extract_file_paths(rule_txt)
        target_path = next((p for p in paths if p not in NON_TRACKED_EXACT and not p.startswith(PROVIDER_PREFIXES)), None)
        if not target_path:
            print("FAIL negative-test: no replaceable local path found in rule")
            return 1
        bad = rule_txt.replace(target_path, "design/DOES-NOT-EXIST-NEGATIVE.md", 1)
        neg_errs, _ = check_rule_paths(bad, root, provider)
        if not any("design/DOES-NOT-EXIST-NEGATIVE.md" in e for e in neg_errs):
            print(f"FAIL negative-test: missing path was not flagged ({neg_errs})")
            return 1
        print(f"OK negative-test: flagged {neg_errs[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
