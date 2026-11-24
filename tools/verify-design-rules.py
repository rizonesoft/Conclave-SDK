#!/usr/bin/env python3
"""Verify .agents/rules/design-contract.md, raw-byte Claude mirror, and AGENTS.md from recorded Git commits."""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import tomllib

REQUIRED_HEADINGS = (
    "## Contract",
    "## Tokens and icons",
    "## Never",
    "## Static lint",
    "## Rendered check",
)

REQUIRED_BANS = ("#RRGGBB", "0xRRGGBB", "rgb()", "ColorF", "SVG", "emoji", "backdrop")
PROVIDER_PREFIXES = ("shared/resolute-ui/", "shared/lucide/")
# Only genuinely untracked runtime output or explicitly planned future paths
NON_TRACKED_EXACT = {
    "build/renders/",
    "src/ui/theme.rs",
    "src/res",
}
NON_PATH_TOKENS = {
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
}
ROOT_FILE_EXTS = (".md", ".json", ".toml", ".xaml", ".css", ".html", ".svg", ".png", ".ico")
HEX_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

_TREE_CACHE: dict[tuple[str, str], set[str]] = {}


def run_git_bytes(root: pathlib.Path, args: list[str], posix: str = "") -> subprocess.CompletedProcess[bytes]:
    if str(root).startswith("\\\\wsl") and posix:
        # Execute Linux git directly through Python argv (no shell, no bash interpolation).
        py_exec = "import os, subprocess, sys; raise SystemExit(subprocess.call(['git', '-C', os.path.expanduser(sys.argv[1]), *sys.argv[2:]]))"
        cmd = ["wsl.exe", "--exec", "python3", "-c", py_exec, posix, *args]
    else:
        cmd = ["git", "-C", str(root), *args]
    return subprocess.run(cmd, capture_output=True, timeout=30)


def git_show_bytes(root: pathlib.Path, commit: str, rel_path: str, posix: str = "") -> tuple[int, bytes]:
    r = run_git_bytes(root, ["show", f"{commit}:{rel_path}"], posix)
    return r.returncode, r.stdout


def git_tree_paths_at_commit(root: pathlib.Path, commit: str, posix: str = "") -> set[str]:
    key = (str(root), commit)
    if key in _TREE_CACHE:
        return _TREE_CACHE[key]
    r = run_git_bytes(root, ["ls-tree", "-r", "--name-only", commit], posix)
    if r.returncode != 0:
        _TREE_CACHE[key] = set()
        return set()
    entries: set[str] = set()
    for line in r.stdout.decode("utf-8", errors="replace").splitlines():
        p = line.strip()
        if not p:
            continue
        entries.add(p)
        parts = p.split("/")
        for i in range(1, len(parts)):
            entries.add("/".join(parts[:i]))
    _TREE_CACHE[key] = entries
    return entries


def git_path_exists_at_commit(root: pathlib.Path, commit: str, rel_path: str, posix: str = "") -> bool:
    return rel_path.rstrip("/") in git_tree_paths_at_commit(root, commit, posix)


def extract_referenced_paths(rule_text: str) -> list[str]:
    """Extract direct file-path spans, root-level file names, and script paths inside command spans."""
    paths: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"`([^`]+)`", rule_text):
        span = m.group(1).strip()
        if "§" in span or span.startswith(("#", "0x")):
            continue
        tokens = span.split() if " " in span else [span]
        for tok in tokens:
            tok = tok.rstrip(".,;:'\")").lstrip("'\"(")
            if not tok or tok.startswith(("#", "0x", "-", "<")) or "(" in tok or ")" in tok or "*" in tok or "<" in tok:
                continue
            if tok in NON_PATH_TOKENS:
                continue
            if "/" in tok or tok.endswith(ROOT_FILE_EXTS):
                if tok not in seen:
                    seen.add(tok)
                    paths.append(tok)
    return paths


def check_frontmatter_and_sections(rule_text: str) -> list[str]:
    errs: list[str] = []
    lines = rule_text.splitlines()
    if len(lines) >= 40:
        errs.append(f"lines={len(lines)}>=40")
    if not lines or lines[0].strip() != "---":
        errs.append("missing opening frontmatter delimiter")
    else:
        close_idx = None
        for i in range(1, min(len(lines), 8)):
            if lines[i].strip() == "---":
                close_idx = i
                break
        if close_idx is None:
            errs.append("unclosed YAML frontmatter")
        else:
            fm_lines = [l.strip() for l in lines[1:close_idx]]
            if "trigger: always_on" not in fm_lines:
                errs.append("missing trigger: always_on in frontmatter")

    heading_positions: dict[str, int] = {}
    for idx, line in enumerate(lines):
        s = line.strip()
        if s in REQUIRED_HEADINGS:
            heading_positions[s] = idx
    for h in REQUIRED_HEADINGS:
        if h not in heading_positions:
            errs.append(f"missing heading {h}")
            continue
        start = heading_positions[h] + 1
        end = len(lines)
        for j in range(start, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        body_bullets = [l for l in lines[start:end] if l.strip().startswith("- ") and len(l.strip()) > 10]
        if not body_bullets:
            errs.append(f"no substantive bullet under {h}")

    for b in REQUIRED_BANS:
        if b not in rule_text:
            errs.append(f"missing ban {b}")
    low = rule_text.lower()
    if "theme-only" not in low:
        missing_lit = [w for w in ("spacing", "radius", "font") if w not in low]
        if missing_lit:
            errs.append(f"missing literal prohibition terms: {', '.join(missing_lit)}")
    if "\u2014" in rule_text or "\u2013" in rule_text:
        errs.append("contains em/en dash")
    return errs


def check_rule_paths_at_commit(
    rule_text: str,
    project_root: pathlib.Path,
    commit: str,
    posix: str = "",
    provider_root: pathlib.Path | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    paths = extract_referenced_paths(rule_text)
    if not paths:
        errors.append("no file paths extracted")

    sdk_commit: str | None = None
    rc_sdk, raw_sdk = git_show_bytes(project_root, commit, "sdk.json", posix)
    if rc_sdk == 0 and raw_sdk:
        try:
            sdk_commit = json.loads(raw_sdk.decode("utf-8")).get("commit")
        except Exception:
            sdk_commit = None

    for rel in paths:
        if rel in NON_TRACKED_EXACT:
            continue
        if rel == "sdk/DESIGN.md":
            if not sdk_commit or provider_root is None:
                errors.append("sdk/DESIGN.md cited without pinned sdk.json commit and provider")
            elif not git_path_exists_at_commit(provider_root, sdk_commit, "DESIGN.md"):
                errors.append(f"provider DESIGN.md missing at {sdk_commit[:8]}")
            continue
        if rel == "DESIGN.md" and provider_root is not None:
            # Consumers citing provider DESIGN.md via sdk.json must prove it exists in the provider at sdk_commit too.
            if not sdk_commit:
                errors.append("provider DESIGN.md cited without pinned sdk.json commit")
            elif not git_path_exists_at_commit(provider_root, sdk_commit, "DESIGN.md"):
                errors.append(f"provider DESIGN.md missing at {sdk_commit[:8]}")
            if not git_path_exists_at_commit(project_root, commit, "DESIGN.md", posix):
                errors.append(f"missing local path at {commit[:8]}: DESIGN.md")
            continue
        if rel.startswith(PROVIDER_PREFIXES) and provider_root is not None:
            if not sdk_commit:
                errors.append(f"provider path {rel} without pinned sdk.json commit")
            elif not git_path_exists_at_commit(provider_root, sdk_commit, rel):
                errors.append(f"provider path missing at {sdk_commit[:8]}: {rel}")
            continue
        if not git_path_exists_at_commit(project_root, commit, rel, posix):
            errors.append(f"missing path at {commit[:8]}: {rel}")
    return errors, paths


def verify_project(
    project_root: pathlib.Path,
    commit: str = "HEAD",
    posix: str = "",
    provider_root: pathlib.Path | None = None,
    check_clean: bool = True,
) -> tuple[list[str], int]:
    errs: list[str] = []
    rc_rule, rule_bytes = git_show_bytes(project_root, commit, ".agents/rules/design-contract.md", posix)
    if rc_rule != 0:
        return [f"missing .agents/rules/design-contract.md at {commit}"], 0
    rule_txt = rule_bytes.decode("utf-8", errors="replace")
    errs.extend(check_frontmatter_and_sections(rule_txt))
    p_errs, p_list = check_rule_paths_at_commit(rule_txt, project_root, commit, posix, provider_root)
    errs.extend(p_errs)

    has_claude_rules_at_commit = git_path_exists_at_commit(project_root, commit, ".claude/rules", posix)
    if has_claude_rules_at_commit:
        rc_mir, mir_bytes = git_show_bytes(project_root, commit, ".claude/rules/design-contract.md", posix)
        if rc_mir != 0:
            errs.append("claude mirror missing at commit")
        elif mir_bytes != rule_bytes:
            errs.append("claude mirror raw bytes differ from .agents/rules/design-contract.md at commit")

    rc_ag, ag_bytes = git_show_bytes(project_root, commit, "AGENTS.md", posix)
    if rc_ag != 0:
        errs.append("AGENTS.md missing at commit")
    else:
        ag_txt = ag_bytes.decode("utf-8", errors="replace")
        if ".agents/rules/design-contract.md" not in ag_txt:
            errs.append("AGENTS.md missing .agents/rules/design-contract.md citation at commit")
        # Strip the rule links themselves so they cannot falsely satisfy the authoritative contract reference check
        ag_without_rule_links = ag_txt.replace(".agents/rules/design-contract.md", "").replace(
            ".claude/rules/design-contract.md", ""
        )
        if not re.search(
            r"SPEC\.md|DESIGN\.md|docs/design-contract\.md|standards/design-contract\.md|docs/design/|Design fidelity contract|gostore-child|design/inventory/REFERENCE\.md|docs/product-principles\.md",
            ag_without_rule_links,
            re.I,
        ):
            errs.append("AGENTS.md missing authoritative contract reference at commit")
        if not re.search(r"design-lint\.py|build-theme\.py|static design lint is planned", ag_txt, re.I):
            errs.append("AGENTS.md missing static lint reference at commit")

    if check_clean:
        r_st = run_git_bytes(project_root, ["status", "--short"], posix)
        if r_st.returncode != 0:
            errs.append(f"git status failed (rc={r_st.returncode})")
        elif r_st.stdout.strip():
            errs.append(f"dirty tree: {r_st.stdout.decode('utf-8', errors='replace').strip()[:80]}")

    return errs, len(p_list)


def parse_fleet_table(run_file: pathlib.Path) -> list[tuple[str, str, str]]:
    """Return list of (project_alias, sha_or_ref, disposition) from the fleet table."""
    rows: list[tuple[str, str, str]] = []
    in_table = False
    for line in run_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Project | SHA / Ref |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if line.startswith("| ---"):
                continue
            cols = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
            if len(cols) >= 6:
                rows.append((cols[0], cols[1], cols[5]))
    return rows


def run_fleet_mode(sdk_root: pathlib.Path, run_file: pathlib.Path, check_clean: bool, negative_test: bool) -> int:
    cfg = tomllib.loads((sdk_root / ".conclave" / "local.toml").read_text(encoding="utf-8"))
    proj_map: dict[str, dict] = {}
    for proj in cfg.get("projects", []):
        alias = proj.get("alias") or proj["name"]
        proj_map[alias] = proj

    rsdk_root = pathlib.Path(proj_map["Resolute-SDK"]["windows"])
    table_rows = parse_fleet_table(run_file)
    seen_aliases = [r[0] for r in table_rows]
    if len(seen_aliases) != len(set(seen_aliases)):
        print("FAIL fleet table contains duplicate project rows")
        return 1
    expected_set = set(proj_map.keys())
    actual_set = set(seen_aliases)
    if expected_set != actual_set:
        print(f"FAIL fleet coverage mismatch: missing={sorted(expected_set - actual_set)} extra={sorted(actual_set - expected_set)}")
        return 1

    r16 = subprocess.run(["python", "scripts/todo-graph.py", "resolve", "D00 T03 §16"], cwd=str(sdk_root), capture_output=True, text=True)
    if r16.returncode not in (0, 4):
        print(f"FAIL resolve D00 T03 §16 (rc={r16.returncode})")
        return 1
    s16_deps = set(json.loads(r16.stdout).get("depends", []))

    seen_retry_refs: dict[str, str] = {}
    all_ok = True
    for alias, sha_or_ref, disp in table_rows:
        proj = proj_map[alias]
        win = pathlib.Path(proj["windows"])
        posix = proj.get("posix", "")
        if "held" in disp.lower() or "§" in sha_or_ref:
            if "§" not in sha_or_ref:
                print(f"FAIL {alias:16} held disposition lacks retry ref ({sha_or_ref})")
                all_ok = False
                continue
            if sha_or_ref in seen_retry_refs:
                print(f"FAIL {alias:16} duplicate retry ref {sha_or_ref} already owned by {seen_retry_refs[sha_or_ref]}")
                all_ok = False
                continue
            seen_retry_refs[sha_or_ref] = alias
            r_ref = subprocess.run(["python", "scripts/todo-graph.py", "resolve", sha_or_ref], cwd=str(sdk_root), capture_output=True, text=True)
            if r_ref.returncode not in (0, 4):
                print(f"FAIL {alias:16} held retry {sha_or_ref} did not resolve (rc={r_ref.returncode})")
                all_ok = False
                continue
            resolved = json.loads(r_ref.stdout)
            if sha_or_ref not in s16_deps:
                print(f"FAIL {alias:16} held retry {sha_or_ref} is not in D00 T03 §16 depends")
                all_ok = False
            elif alias not in resolved.get("title", "") and alias not in resolved.get("body", ""):
                print(f"FAIL {alias:16} held retry {sha_or_ref} does not name {alias}")
                all_ok = False
            else:
                print(f"OK   {alias:16} HELD -> {sha_or_ref} resolves, names {alias}, and blocks D00 T03 §16")
            continue

        if not HEX_SHA_RE.match(sha_or_ref):
            print(f"FAIL {alias:16} delivered row revision is not a pinned hex SHA: {sha_or_ref!r}")
            all_ok = False
            continue
        provider = rsdk_root if alias in ("Busview", "Resolute") else None
        errs, p_count = verify_project(win, sha_or_ref, posix, provider, check_clean=check_clean)
        if errs:
            print(f"FAIL {alias:16} sha={sha_or_ref} errs={errs}")
            all_ok = False
        else:
            print(f"OK   {alias:16} sha={sha_or_ref} paths={p_count}")

    if negative_test:
        berth_sha = next(r[1] for r in table_rows if r[0] == "Berth")
        berth_root = pathlib.Path(proj_map["Berth"]["windows"])
        _, raw_b = git_show_bytes(berth_root, berth_sha, ".agents/rules/design-contract.md")
        bad = raw_b.decode("utf-8").replace("design/SPEC.md", "design/DOES-NOT-EXIST-NEGATIVE.md", 1)
        neg_errs, _ = check_rule_paths_at_commit(bad, berth_root, berth_sha)
        if any("design/DOES-NOT-EXIST-NEGATIVE.md" in e for e in neg_errs):
            print(f"OK   NEGATIVE-PATH   flagged {neg_errs[0]}")
        else:
            print(f"FAIL NEGATIVE-PATH   not flagged: {neg_errs}")
            all_ok = False
    return 0 if all_ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify design-contract rules, raw-byte mirrors, and AGENTS.md at recorded commits.")
    ap.add_argument("--fleet", action="store_true", help="Verify all projects from .conclave/local.toml and --run-file.")
    ap.add_argument("--run-file", default="", help="Phase run Markdown file holding the fleet table (for --fleet).")
    ap.add_argument("--sdk-root", default=".", help="Conclave-SDK root (default: .).")
    ap.add_argument("--project", default="", help="Single target project checkout path.")
    ap.add_argument("--commit", default="HEAD", help="Commit SHA to inspect (default: HEAD).")
    ap.add_argument("--posix", default="", help="Optional WSL POSIX path for git commands.")
    ap.add_argument("--provider", default="", help="Optional provider checkout path for sdk.json theme refs.")
    ap.add_argument("--content-only", action="store_true", help="Skip live git status check for pure historical reproducibility.")
    ap.add_argument("--negative-test", action="store_true", help="Prove a scratch missing-path copy fails.")
    args = ap.parse_args(argv)

    if args.fleet:
        if not args.run_file:
            print("FAIL --fleet requires --run-file")
            return 2
        return run_fleet_mode(pathlib.Path(args.sdk_root), pathlib.Path(args.run_file), not args.content_only, args.negative_test)

    if not args.project:
        print("FAIL pass either --fleet --run-file <path> or --project <dir>")
        return 2
    root = pathlib.Path(args.project)
    provider = pathlib.Path(args.provider) if args.provider else None
    errs, p_count = verify_project(root, args.commit, args.posix, provider, check_clean=not args.content_only)
    if errs:
        print(f"FAIL {root.name}: {errs}")
        return 1
    print(f"OK {root.name} at {args.commit} paths={p_count}")
    if args.negative_test:
        _, raw = git_show_bytes(root, args.commit, ".agents/rules/design-contract.md", args.posix)
        rule_txt = raw.decode("utf-8", errors="replace")
        paths = extract_referenced_paths(rule_txt)
        target_path = next((p for p in paths if p not in NON_TRACKED_EXACT and not p.startswith(PROVIDER_PREFIXES) and p != "sdk/DESIGN.md"), None)
        if not target_path:
            print("FAIL negative-test: no replaceable local path found")
            return 1
        bad = rule_txt.replace(target_path, "design/DOES-NOT-EXIST-NEGATIVE.md", 1)
        neg_errs, _ = check_rule_paths_at_commit(bad, root, args.commit, args.posix, provider)
        if not any("design/DOES-NOT-EXIST-NEGATIVE.md" in e for e in neg_errs):
            print(f"FAIL negative-test: missing path not flagged ({neg_errs})")
            return 1
        print(f"OK negative-test: flagged {neg_errs[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
