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
# Only the standard runtime render output directory is not tracked in Git.
RUNTIME_OUTPUT_DIRS = {"build/renders/"}
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
ROOT_FILE_EXTS = (
    ".md", ".json", ".toml", ".xaml", ".css", ".html", ".svg", ".png", ".ico",
    ".ps1", ".py", ".mjs", ".cs", ".h",
)
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


def extract_section_body(rule_text: str, heading: str) -> str | None:
    lines = rule_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return None
    out = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return "\n".join(out)


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
            if "/" in tok or "\\" in tok or tok.endswith(ROOT_FILE_EXTS):
                norm = tok.replace("\\", "/")
                while norm.startswith("./"):
                    norm = norm[2:]
                if norm and norm not in seen:
                    seen.add(norm)
                    paths.append(norm)
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

    for h in REQUIRED_HEADINGS:
        body = extract_section_body(rule_text, h)
        if body is None:
            errs.append(f"missing heading {h}")
            continue
        body_bullets = [l for l in body.splitlines() if l.strip().startswith("- ") and len(l.strip()) > 10]
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
        if rel in RUNTIME_OUTPUT_DIRS:
            continue
        if rel == "sdk/DESIGN.md":
            if not sdk_commit or provider_root is None:
                errors.append("sdk/DESIGN.md cited without pinned sdk.json commit and provider")
            elif not git_path_exists_at_commit(provider_root, sdk_commit, "DESIGN.md"):
                errors.append(f"provider DESIGN.md missing at {sdk_commit[:8]}")
            continue
        if rel == "DESIGN.md" and provider_root is not None:
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


def check_agents_md_against_rule(ag_txt: str, rule_txt: str, has_provider: bool) -> list[str]:
    errs: list[str] = []
    if ".agents/rules/design-contract.md" not in ag_txt:
        errs.append("AGENTS.md missing .agents/rules/design-contract.md citation at commit")

    ag_no_rule_links = ag_txt.replace(".agents/rules/design-contract.md", "").replace(
        ".claude/rules/design-contract.md", ""
    )

    # Check authoritative primary contract citation derived from the rule's own ## Contract section
    contract_body = extract_section_body(rule_txt, "## Contract") or ""
    contract_paths = [p for p in extract_referenced_paths(contract_body) if p != "AGENTS.md"]
    if has_provider:
        # Exclude bare local pointer DESIGN.md so a consumer must cite its real contract or sdk.json/sdk/DESIGN.md
        auth_candidates = [p for p in contract_paths if p != "DESIGN.md"]
        if not auth_candidates:
            auth_candidates = ["sdk.json", "sdk/DESIGN.md"]
    else:
        auth_candidates = contract_paths
    if auth_candidates:
        primary = auth_candidates[0]
        if primary not in ag_no_rule_links:
            # Allow docs/design/ directory citation only when primary is docs/design/README.md (e.g. Gemail)
            if not (primary == "docs/design/README.md" and "docs/design/" in ag_no_rule_links):
                errs.append(f"AGENTS.md missing authoritative contract reference ({primary}) at commit")
    elif "Design fidelity contract" not in ag_no_rule_links and "gostore-child" not in ag_no_rule_links:
        errs.append("AGENTS.md missing authoritative contract reference at commit")

    # Check ALL installed static lint scripts derived from the rule's own ## Static lint section
    lint_body = extract_section_body(rule_txt, "## Static lint") or ""
    lint_scripts = [p for p in extract_referenced_paths(lint_body) if p.endswith((".py", ".ps1", ".mjs"))]
    if lint_scripts:
        missing_lint = [s for s in lint_scripts if s not in ag_txt]
        if missing_lint:
            errs.append(f"AGENTS.md missing installed static lint reference ({', '.join(missing_lint)}) at commit")
    else:
        if "static design lint is planned" not in ag_txt.lower():
            errs.append("AGENTS.md missing planned static lint note at commit")
    return errs


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
        errs.extend(check_agents_md_against_rule(ag_txt, rule_txt, has_provider=provider_root is not None))

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


def validate_held_retry(alias: str, ref: str, resolved: dict, s16_deps: set[str]) -> list[str]:
    errs: list[str] = []
    if ref not in s16_deps:
        errs.append(f"{ref} is not in D00 T03 §16 depends")
    if "D00 T03 §5" not in set(resolved.get("depends", [])):
        errs.append(f"{ref} does not depend on D00 T03 §5")
    title = resolved.get("title", "")
    body = resolved.get("body", "")
    if alias not in title:
        errs.append(f"{ref} title does not name {alias}")
    if ".agents/rules/design-contract.md" not in body:
        errs.append(f"{ref} does not deliver .agents/rules/design-contract.md")
    return errs


def _read_local_settings(sdk_root: pathlib.Path) -> tuple[dict, tuple[str, ...]]:
    import importlib.util

    for candidate in (
        sdk_root / ".conclave" / "local_settings.py",
        pathlib.Path(__file__).resolve().parents[1] / ".conclave" / "local_settings.py",
        pathlib.Path(__file__).resolve().parents[1] / "kits" / "base" / "templates" / ".conclave" / "local_settings.py",
    ):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_verify_design_local_settings", candidate)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.load_local_settings(sdk_root)
    raise RuntimeError(f".conclave/local_settings.py is missing under {sdk_root}")


def run_fleet_mode(sdk_root: pathlib.Path, run_file: pathlib.Path, check_clean: bool, negative_test: bool) -> int:
    try:
        cfg, loaded = _read_local_settings(sdk_root)
    except ValueError as exc:
        print(f"FAIL fleet settings invalid: {exc}")
        return 1
    if not loaded:
        print("FAIL fleet settings missing: configure [[projects]] in .conclave/local.toml or .private/local.toml")
        return 1
    sources = " / ".join(loaded)
    projects = cfg.get("projects", [])
    if not isinstance(projects, list):
        print(f"FAIL fleet settings invalid ({sources}): projects must be [[projects]] tables")
        return 1
    proj_map: dict[str, dict] = {}
    for idx, proj in enumerate(projects):
        if not isinstance(proj, dict) or not isinstance(proj.get("name"), str) or not proj["name"].strip():
            print(f"FAIL fleet settings invalid ({sources}): projects[{idx}] missing non-empty name")
            return 1
        raw_alias = proj.get("alias")
        if raw_alias is not None and (not isinstance(raw_alias, str) or not raw_alias.strip()):
            print(f"FAIL fleet settings invalid ({sources}): projects[{idx}] ({proj['name']}) alias must be a non-empty string")
            return 1
        raw_win = proj.get("windows")
        if not isinstance(raw_win, str) or not raw_win.strip():
            print(f"FAIL fleet settings invalid ({sources}): projects[{idx}] ({proj['name']}) missing non-empty windows path")
            return 1
        raw_posix = proj.get("posix")
        if raw_posix is not None and not isinstance(raw_posix, str):
            print(f"FAIL fleet settings invalid ({sources}): projects[{idx}] ({proj['name']}) posix must be a string")
            return 1
        alias = raw_alias or proj["name"]
        if alias in proj_map:
            print(f"FAIL fleet settings invalid ({sources}): duplicate alias '{alias}' ({proj_map[alias]['name']} and {proj['name']})")
            return 1
        proj_map[alias] = proj

    if "Resolute-SDK" not in proj_map:
        print(f"FAIL fleet settings missing Resolute-SDK entry under [[projects]] in {sources}")
        return 1
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
        if "held" in disp.lower():
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
            h_errs = validate_held_retry(alias, sha_or_ref, resolved, s16_deps)
            if h_errs:
                print(f"FAIL {alias:16} held retry {sha_or_ref} errs={h_errs}")
                all_ok = False
            else:
                print(f"OK   {alias:16} HELD -> {sha_or_ref} owns §5 retry for {alias} and blocks D00 T03 §16")
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
        delivered_candidates = [
            (a, s) for a, s, d in table_rows if "held" not in d.lower() and HEX_SHA_RE.match(s)
        ]
        neg_ran = False
        for neg_alias, neg_sha in delivered_candidates:
            neg_proj = proj_map[neg_alias]
            neg_root = pathlib.Path(neg_proj["windows"])
            neg_posix = neg_proj.get("posix", "")
            rc_n, raw_n = git_show_bytes(neg_root, neg_sha, ".agents/rules/design-contract.md", neg_posix)
            if rc_n != 0:
                continue
            rule_n = raw_n.decode("utf-8", errors="replace")
            paths_n = extract_referenced_paths(rule_n)
            target_p = next(
                (p for p in paths_n if p not in RUNTIME_OUTPUT_DIRS and not p.startswith(PROVIDER_PREFIXES) and p != "sdk/DESIGN.md"),
                None,
            )
            if not target_p:
                continue
            bad = rule_n.replace(target_p, "design/DOES-NOT-EXIST-NEGATIVE.md", 1)
            neg_provider = rsdk_root if neg_alias in ("Busview", "Resolute") else None
            neg_errs, _ = check_rule_paths_at_commit(bad, neg_root, neg_sha, neg_posix, neg_provider)
            if any("design/DOES-NOT-EXIST-NEGATIVE.md" in e for e in neg_errs):
                print(f"OK   NEGATIVE-PATH   ({neg_alias}) flagged {neg_errs[0]}")
                neg_ran = True
            else:
                print(f"FAIL NEGATIVE-PATH   ({neg_alias}) not flagged: {neg_errs}")
                all_ok = False
                neg_ran = True
            break
        if not neg_ran:
            print("FAIL NEGATIVE-PATH   no delivered project with a local path available")
            all_ok = False
    return 0 if all_ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify design-contract rules, raw-byte mirrors, and AGENTS.md at recorded commits.")
    ap.add_argument("--fleet", action="store_true", help="Verify all projects from .conclave/local.toml or .private/local.toml and --run-file.")
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
        target_path = next((p for p in paths if p not in RUNTIME_OUTPUT_DIRS and not p.startswith(PROVIDER_PREFIXES) and p != "sdk/DESIGN.md"), None)
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
