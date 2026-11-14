#!/usr/bin/env python3
"""Antigravity lifecycle hook for Conclave Powertools.

Runs on Windows and WSL using only the Python 3 standard library. Reads Antigravity's
camelCase hook payloads from stdin and outputs exact contract responses on stdout:

- PreToolUse: gates only catastrophic point-of-no-return shell commands with
  decision="force_ask", checks WordPress writes for article rules reminders, and scans
  pending added lines of code files for masking patterns and windowed launcher test
  spawns. Never blocks normal shell commands or code edits.
- PostToolUse: confirms landed edits into per-turn state (discarding failed tool calls),
  queues masking/launcher notices, and runs article_check.py on modified drafts.
- PreInvocation: detects new user turns from lastUserInput, injects article writing rules
  once for article/copy prompts, and flushes queued notices once via injectSteps.
- Stop: after NO_TOOL_CALL turns that edited non-prose code outside artifactDirectoryPath,
  checks the assistant output since the last USER_INPUT for a Layer: line and sends the
  agent back at most once per turn with decision="continue".
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# Stamped by global/deploy.py on deploy; empty in the source checkout.
DEPLOYED_FROM = ""


def _sibling(name: str):
    """Load a sibling helper module by file path."""
    path = os.path.join(HERE, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher_tests = _sibling("launcher_tests")
article_check = _sibling("article_check")

PROSE = (".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc", ".csv", ".log")
WORKAROUND = "WORKAROUND:"
LAYER_LINE = re.compile(r"^\W*layer\W*:", re.I | re.M)

# (name, pattern, extensions or None for all code files)
PATTERNS = [
    ("output buffer rewriting the page", r"\bob_start\s*\(", None),
    ("filter over rendered output", r"add_filter\s*\(\s*['\"](the_content|the_title|the_excerpt|render_block\w*|widget_text\w*|"
                                    r"wp_footer|wp_head|script_loader_tag|style_loader_tag|final_output)['\"]", None),
    ("replace over rendered HTML", r"(preg_replace\w*|str_i?replace)\s*\([^;\n]*\$(html|content|buffer|output|markup)\b"
                                   r"|\.(innerHTML|outerHTML)\s*=[^;\n]*\.replace\(", None),
    ("CSS hiding a problem", r"(display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0)\s*!important", None),
    ("script rewriting the page", r"\bnew\s+MutationObserver\b|\.style\.display\s*=\s*['\"]none['\"]", None),
    ("suppressed type or lint error", r"@ts-ignore|@ts-nocheck|@ts-expect-error|eslint-disable|#\s*type:\s*ignore|#\s*noqa"
                                      r"|#\s*pylint:\s*disable|@SuppressWarnings|#\[allow\(|//\s*nolint|phpcs:ignore"
                                      r"|@phpstan-ignore|@psalm-suppress", None),
    ("skipped test", r"\b(it|test|describe)\.skip\s*\(|\bx(it|describe|test)\s*\(|@pytest\.mark\.(skip|xfail)"
                     r"|@unittest\.skip|markTestSkipped|\bt\.Skip(Now)?\(", None),
    ("swallowed error", r"except[^:\n]*:[ \t]*(\n[ \t]*)?(pass|\.\.\.)[ \t]*$|catch\s*(\([^)]*\))?\s*\{\s*\}"
                        r"|\|\|\s*true\b|-ErrorAction\s+SilentlyContinue", None),
    ("error suppression operator", r"(?<![\w@\"'])@\$?[a-z_]\w*\s*\(", (".php",)),
    ("bypassed git hook", r"--no-verify\b|\bHUSKY=0\b", None),
    ("direct database write", r"\$wpdb->(query|update|insert|replace|delete)\s*\(|\bUPDATE\s+wp_\w+\s+SET\b", None),
]
COMPILED = [(name, re.compile(rx, re.I | re.M), exts) for name, rx, exts in PATTERNS]

CHECKER = os.path.join(HERE, "article_check.py")
CHECK_CMD = f'{"python" if os.name == "nt" else "python3"} "{CHECKER}"'
ARTICLE_RULES = (
    "Owner writing rules:\n"
    "1. Creative writing (articles, page and marketing copy, product descriptions) uses NLP (natural language "
    "processing): answer first, question-shaped headings, short active sentences, clear named entities, no stock "
    "AI phrasing, no em or en dashes.\n"
    "Articles (blog posts, guides, whitepapers) also:\n"
    "2. Add original value: unique insights, first-hand experience and accurate facts, with every figure sourced.\n"
    "3. Meet E-E-A-T: a named author, first-hand detail, primary sources, honest limits and a review date.\n"
    "4. Never carry a line saying AI assisted with or wrote the article.\n"
    "5. Write and edit accurately, and get independent cross-family review on facts, AI-sounding prose, and SEO "
    "rather than relying on self-review alone. No humanizer or paraphrasing tools.\n"
    f"Run `{CHECK_CMD} <draft>` before writing an article back and `{CHECK_CMD} --post <id>` after (in a repository "
    "with its own article checker, use that one); fix every FAIL and answer every WARN."
)

WRITE_VERB = r"\b(write|rewrite|draft|improve|update|polish|expand|edit)\w*\s+(?:\w+\s+){0,4}?"
WRITING = (r"(article|articles|blog ?posts?|whitepapers?|copywriting|product descriptions?|newsletters?"
           r"|(marketing|page|web|website|sales|ad|product|homepage|hero|landing ?page) copy)\b")
PROMPT = re.compile(WRITE_VERB + WRITING + r"|\b(article|blog ?post|whitepaper)s?\s+(?:\w+\s+){0,3}?(rewrite|draft|update)\b", re.I)
RULES_TALK = re.compile(r"\b(rules?|hook|hooks|globally)\b", re.I)
WP_WRITE = re.compile(r"\bwp(-launch)?\b.*\bpost\s+(create|update)\b|post_content|article-(write|rewrite|apply)|update_post", re.I)
DRAFT_DIR = re.compile(r"/(drafts?|articles?|posts?|blog)/", re.I)
NOT_DRAFT_NAME = re.compile(r"^(readme|changelog|license|contributing|index)\.", re.I)
REPO_CHECKER = os.path.join("scripts", "article-check.py")


def _state_dir() -> str:
    base = os.environ.get("PLUGIN_DATA") or os.path.join(tempfile.gettempdir(), "agy-powertools-hooks")
    return os.path.join(base, "sessions")


def _state_path(session: str) -> str:
    safe = re.sub(r"[^\w.-]", "_", session or "default")
    return os.path.join(_state_dir(), safe + ".json")


def _default_state() -> dict:
    return {
        "last_user_input": "",
        "prompt_checked": False,
        "wp_reminded": False,
        "sent_back": False,
        "drift_checked": False,
        "files": [],
        "flags": [],
        "pending": {},
        "queued_notices": [],
    }


def load_state(session: str) -> dict:
    state = _default_state()
    try:
        with open(_state_path(session), encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            state.update(raw)
    except (OSError, ValueError, TypeError):
        pass
    return state


def save_state(session: str, state: dict) -> None:
    folder = _state_dir()
    os.makedirs(folder, exist_ok=True)
    target = _state_path(session)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def sync_turn(state: dict, raw_input: str) -> None:
    """Reset per-turn tracking when a new lastUserInput arrives."""
    if raw_input and raw_input != state.get("last_user_input"):
        state["last_user_input"] = raw_input
        state["prompt_checked"] = False
        state["wp_reminded"] = False
        state["sent_back"] = False
        state["files"] = []
        state["flags"] = []
        state["pending"] = {}
        state["queued_notices"] = []


def _resolve_cwd(data: dict) -> str:
    workspaces = data.get("workspacePaths") or []
    return data.get("cwd") or (workspaces[0] if workspaces else "") or os.getcwd()


def _resolve_path(path: str, cwd: str) -> str:
    if not path:
        return ""
    return path if os.path.isabs(path) else os.path.join(cwd, path)


def _in_artifact_dir(path: str, artifact_dir: str) -> bool:
    if not path or not artifact_dir:
        return False
    norm_art = os.path.normcase(os.path.normpath(os.path.abspath(artifact_dir)))
    norm_path = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    return norm_path == norm_art or norm_path.startswith(norm_art.rstrip("\\/") + os.sep)


def is_tracked_code(path: str, artifact_dir: str = "") -> bool:
    if not path or path.lower().endswith(PROSE):
        return False
    return not _in_artifact_dir(path, artifact_dir)


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def added_lines(old_text: str, new_text: str) -> set[int]:
    """0-based line numbers in new_text absent from old_text (multiset diff)."""
    pool: dict[str, int] = {}
    for line in old_text.splitlines():
        pool[line] = pool.get(line, 0) + 1
    added: set[int] = set()
    for i, line in enumerate(new_text.splitlines()):
        if pool.get(line):
            pool[line] -= 1
        else:
            added.add(i)
    return added


def scan(path: str, new_text: str, added: set[int], artifact_dir: str = "") -> list[dict]:
    """Find masking patterns touching added lines without a WORKAROUND comment nearby."""
    if not is_tracked_code(path, artifact_dir) or not added:
        return []
    ext = os.path.splitext(path)[1].lower()
    lines = new_text.splitlines()
    flags: list[dict] = []
    for name, rx, exts in COMPILED:
        if exts and ext not in exts:
            continue
        for m in rx.finditer(new_text):
            first = new_text.count("\n", 0, m.start())
            last = new_text.count("\n", 0, max(m.end() - 1, m.start()))
            if not added.intersection(range(first, last + 1)):
                continue
            if any(WORKAROUND in lines[i] for i in range(max(first - 3, 0), min(last + 1, len(lines)))):
                continue
            flags.append({"file": path, "line": first + 1, "pattern": name, "code": lines[first].strip()[:120]})
    return flags


def extract_clean_prompt(raw: str) -> str:
    m = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", raw, re.S)
    if m:
        return m.group(1)
    cleaned = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", raw, flags=re.S)
    cleaned = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", cleaned, flags=re.S)
    return cleaned.strip()


_PREFIX_SHELL_RX = r"^\s*(?:(?:sudo|env|command|time|nohup|nice|[A-Za-z_]\w*=\S+)\s+)*"
_NO_BS_SHELL_RE = re.compile(_PREFIX_SHELL_RX + r"(?:pwsh|powershell|cmd)(?:\.exe)?(?:\s|$)", re.I)
_PWSH_SHELL_RE = re.compile(_PREFIX_SHELL_RX + r"(?:pwsh|powershell)(?:\.exe)?(?:\s|$)", re.I)
_PWSH_VAL_OPTS = {
    "-executionpolicy", "-ep", "-windowstyle", "-w", "-inputformat", "-if",
    "-outputformat", "-of", "-configurationname", "-config", "-workingdirectory", "-wd",
    "-settingsfile",
}
_PWSH_CMD_OPTS = {"-command", "-c"}
_PWSH_STOP_OPTS = {"-file", "-f", "-encodedcommand", "-ec", "-e", "-enc", "-encodedarguments"}


def _join_wrapped_tokens(rem: list[tuple[str, bool]]) -> str:
    if len(rem) == 1:
        return rem[0][0]
    return " ".join(('"%s"' % t if (" " in t or "\t" in t) else t) for t, _ in rem)


def _split_shell_segments(cmd: str) -> list[str]:
    """Split a command string on unquoted pipeline/chain separators."""
    segments: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    allow_bs_escape = True
    allow_bt_escape = False
    i = 0
    n = len(cmd)
    while i < n:
        c = cmd[i]
        if quote:
            buf.append(c)
            if quote == '"':
                if allow_bs_escape and c == "\\" and i + 1 < n and cmd[i + 1] in ('"', "\\"):
                    i += 1
                    buf.append(cmd[i])
                    i += 1
                    continue
                if allow_bt_escape and c == "`" and i + 1 < n:
                    i += 1
                    buf.append(cmd[i])
                    i += 1
                    continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            prefix = "".join(buf)
            allow_bs_escape = not bool(_NO_BS_SHELL_RE.match(prefix))
            allow_bt_escape = bool(_PWSH_SHELL_RE.match(prefix))
            quote = c
            buf.append(c)
            i += 1
        elif c in ("\n", ";"):
            segments.append("".join(buf))
            buf = []
            i += 1
        elif cmd.startswith("&&", i) or cmd.startswith("||", i):
            segments.append("".join(buf))
            buf = []
            i += 2
        elif c in ("|", "&"):
            segments.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(c)
            i += 1
    if buf:
        segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _tokenize_segment(seg: str) -> list[tuple[str, bool]]:
    """Tokenize a shell segment preserving Windows path backslashes; returns (text, was_quoted)."""
    allow_bs_escape = not bool(_NO_BS_SHELL_RE.match(seg))
    allow_bt_escape = bool(_PWSH_SHELL_RE.match(seg))
    tokens: list[tuple[str, bool]] = []
    i = 0
    n = len(seg)
    while i < n:
        while i < n and seg[i].isspace():
            i += 1
        if i >= n:
            break
        buf: list[str] = []
        was_quoted = False
        while i < n and not seg[i].isspace():
            c = seg[i]
            if c in ("'", '"'):
                was_quoted = True
                q = c
                i += 1
                while i < n and seg[i] != q:
                    if q == '"':
                        if allow_bs_escape and seg[i] == "\\" and i + 1 < n and seg[i + 1] in ('"', "\\", "$", "`"):
                            buf.append(seg[i + 1])
                            i += 2
                            continue
                        if allow_bt_escape and seg[i] == "`" and i + 1 < n and seg[i + 1] in ('"', "`"):
                            buf.append(seg[i + 1])
                            i += 2
                            continue
                    buf.append(seg[i])
                    i += 1
                if i < n and seg[i] == q:
                    i += 1
            else:
                buf.append(c)
                i += 1
        tokens.append(("".join(buf), was_quoted))
    return tokens


def _unwrap_tokens(tokens: list[tuple[str, bool]], depth: int = 0) -> list[tuple[str, bool]]:
    """Strip env/prefix wrappers and inspect nested shell -c / -Command / /c payloads."""
    idx = 0
    while idx < len(tokens):
        tok, quoted = tokens[idx]
        low = tok.lower()
        base = os.path.basename(low.replace("\\", "/"))
        if not quoted and "=" in tok and not tok.startswith("-"):
            idx += 1
        elif base in ("env", "command", "time", "nohup", "nice"):
            idx += 1
            if base == "env":
                while idx < len(tokens) and tokens[idx][0].startswith("-"):
                    flag = tokens[idx][0]
                    idx += 1
                    if flag == "--":
                        break
                    if flag in ("-u", "-C", "-S"):
                        idx += 1
        elif base in ("sudo",):
            idx += 1
            while idx < len(tokens) and tokens[idx][0].startswith("-"):
                flag = tokens[idx][0]
                idx += 1
                if flag == "--":
                    break
                if flag in ("-u", "-g", "-C", "-D", "-R", "-T", "-U", "-h", "-p") and idx < len(tokens):
                    idx += 1
        elif base in ("wsl", "wsl.exe"):
            idx += 1
            while idx < len(tokens) and tokens[idx][0].startswith("-"):
                flag = tokens[idx][0]
                idx += 1
                if flag in ("-e", "--exec", "--"):
                    break
                if flag in ("-d", "--distribution", "-u", "--user", "--cd") and idx < len(tokens):
                    idx += 1
        elif base in ("bash", "bash.exe", "sh", "sh.exe", "zsh", "dash", "ksh", "ash"):
            j = idx + 1
            while j < len(tokens):
                flag = tokens[j][0]
                if flag == "--":
                    j += 1
                    break
                if flag == "-o" and j + 1 < len(tokens):
                    j += 2
                    continue
                if flag.startswith("-") and not flag.startswith("--") and "c" in flag[1:]:
                    if j + 1 < len(tokens):
                        res = catastrophic_command(tokens[j + 1][0], depth + 1)
                        return [("_FORCE_ASK:" + res, False)] if res else []
                    return []
                if flag.startswith("-"):
                    j += 1
                    continue
                break
            return []
        elif base in ("pwsh", "pwsh.exe", "powershell", "powershell.exe"):
            j = idx + 1
            while j < len(tokens):
                flag = tokens[j][0].lower()
                if flag in _PWSH_STOP_OPTS:
                    return []
                if flag in _PWSH_CMD_OPTS:
                    rem = tokens[j + 1:]
                    if rem:
                        res = catastrophic_command(_join_wrapped_tokens(rem), depth + 1)
                        return [("_FORCE_ASK:" + res, False)] if res else []
                    return []
                if flag in _PWSH_VAL_OPTS:
                    j += 2
                    continue
                if flag.startswith("-"):
                    j += 1
                    continue
                rem = tokens[j:]
                res = catastrophic_command(_join_wrapped_tokens(rem), depth + 1)
                return [("_FORCE_ASK:" + res, False)] if res else []
            return []
        elif base in ("cmd", "cmd.exe"):
            j = idx + 1
            while j < len(tokens):
                flag = tokens[j][0].lower()
                if flag in ("/c", "/k") or (flag.startswith("/") and len(flag) <= 4 and flag[-1] in ("c", "k")):
                    rem = tokens[j + 1:]
                    if rem:
                        res = catastrophic_command(_join_wrapped_tokens(rem), depth + 1)
                        return [("_FORCE_ASK:" + res, False)] if res else []
                    return []
                if flag.startswith("/"):
                    j += 1
                    continue
                break
            return []
        else:
            break
    return tokens[idx:]


_GIT_VAL_OPTS = {"-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
_PUSH_VAL_OPTS = {"-o", "--push-option", "--receive-pack", "--exec"}
_MIRROR_CFG_RE = re.compile(r"^remote\..+\.mirror\s*=\s*(true|yes|on|1)$", re.I)


def _check_git_force_push(tokens: list[tuple[str, bool]]) -> str | None:
    i = 1
    config_mirror = False
    while i < len(tokens):
        tok, _ = tokens[i]
        if tok == "--" or not tok.startswith("-"):
            break
        if tok == "-c":
            if i + 1 < len(tokens) and _MIRROR_CFG_RE.match(tokens[i + 1][0].strip()):
                config_mirror = True
            i += 2
            continue
        if tok.startswith("-c") and len(tok) > 2:
            if _MIRROR_CFG_RE.match(tok[2:].strip()):
                config_mirror = True
            i += 1
            continue
        if tok in _GIT_VAL_OPTS or tok == "-C":
            i += 2
            continue
        i += 1
    if i >= len(tokens) or tokens[i][0].lower() != "push":
        return None
    i += 1
    after_double_dash = False
    has_repo_opt = False
    mirror_opt = config_mirror
    pos_args: list[str] = []
    while i < len(tokens):
        tok, _ = tokens[i]
        if not after_double_dash:
            if tok == "--":
                after_double_dash = True
                i += 1
                continue
            if tok == "--repo":
                has_repo_opt = True
                i += 2
                continue
            if tok.startswith("--repo="):
                has_repo_opt = True
                i += 1
                continue
            if tok in _PUSH_VAL_OPTS:
                i += 2
                continue
            if tok == "--mirror":
                return "git force push (--mirror)"
            if tok == "--no-mirror":
                mirror_opt = False
                i += 1
                continue
            if tok in ("--delete", "--prune"):
                return "git remote ref deletion"
            if tok in ("--force", "--force-with-lease", "--force-if-includes") or tok.startswith(("--force=", "--force-with-lease=")):
                return "git force push"
            if tok.startswith("-") and not tok.startswith("--") and len(tok) > 1:
                consumed_val_opt = False
                for idx_ch, ch in enumerate(tok[1:], start=1):
                    if ch == "f":
                        return "git force push"
                    if ch == "d":
                        return "git remote ref deletion"
                    if ch == "o":
                        i += 2 if idx_ch == len(tok) - 1 else 1
                        consumed_val_opt = True
                        break
                if consumed_val_opt:
                    continue
        if after_double_dash or not tok.startswith("-"):
            pos_args.append(tok)
        i += 1
    if mirror_opt:
        return "git force push (--mirror)"
    refspecs = pos_args if has_repo_opt else pos_args[1:]
    if not has_repo_opt and len(pos_args) == 1 and (
        (pos_args[0].startswith("+") and ":" in pos_args[0])
        or (pos_args[0].startswith(":") and len(pos_args[0]) > 1)
    ):
        refspecs = pos_args
    for ref in refspecs:
        if ref.startswith("+") and len(ref) > 1:
            return "git force push (force refspec)"
        if ref.startswith(":") and len(ref) > 1:
            return "git remote ref deletion (delete refspec)"
    return None


def _is_root_target(arg: str) -> bool:
    cleaned = arg.strip().rstrip("\\/")
    if arg in ("/", "/*", "\\", "\\*"):
        return True
    if re.match(r"^[A-Za-z]:(?:[\\/]+\*?)?$", arg):
        return True
    return cleaned == "" and arg.startswith(("/", "\\"))


def catastrophic_command(cmd: str, _depth: int = 0) -> str | None:
    """Return a short reason label iff cmd contains a catastrophic point-of-no-return command."""
    if _depth > 5:
        return None
    for seg in _split_shell_segments(cmd):
        tokens = _unwrap_tokens(_tokenize_segment(seg), _depth)
        if not tokens:
            continue
        first_tok = tokens[0][0]
        if first_tok.startswith("_FORCE_ASK:"):
            return first_tok.split(":", 1)[1]
        base = os.path.basename(first_tok.lower().replace("\\", "/"))
        if base in ("git", "git.exe"):
            reason = _check_git_force_push(tokens)
            if reason:
                return reason
        elif base in ("gh", "gh.exe"):
            pos = [t for t, _ in tokens[1:] if not t.startswith("-")]
            if pos[:2] == ["repo", "delete"]:
                return "GitHub repository deletion"
        elif base in ("format-volume", "clear-disk", "initialize-disk", "diskpart", "diskpart.exe") or re.match(r"^mkfs(\.\w+)?$", base):
            return "disk or volume format/wipe"
        elif base in ("format", "format.com"):
            if any(re.match(r"^[A-Za-z]:$", t) for t, _ in tokens[1:]):
                return "disk or volume format/wipe"
        elif base in ("rm", "rm.exe"):
            recursive = False
            no_preserve = False
            after_dd = False
            targets: list[str] = []
            for t, _ in tokens[1:]:
                if not after_dd and t == "--":
                    after_dd = True
                elif not after_dd and t == "--no-preserve-root":
                    no_preserve = True
                elif not after_dd and (t == "--recursive" or (t.startswith("-") and not t.startswith("--") and ("r" in t.lower()))):
                    recursive = True
                elif after_dd or not t.startswith("-"):
                    targets.append(t)
            if no_preserve or (recursive and any(_is_root_target(t) for t in targets)):
                return "root filesystem delete"
        elif base in ("remove-item", "ri", "rd", "rmdir"):
            recursive = False
            after_dd = False
            targets = []
            for t, _ in tokens[1:]:
                if not after_dd and t == "--":
                    after_dd = True
                elif not after_dd and t.lower() in ("-recurse", "/s"):
                    recursive = True
                elif after_dd or not t.startswith(("-", "/")):
                    targets.append(t)
            if recursive and any(_is_root_target(t) for t in targets):
                return "root filesystem delete"
    return None


def is_draft(path: str, artifact_dir: str = "") -> bool:
    if _in_artifact_dir(path, artifact_dir):
        return False
    unix = path.replace("\\", "/")
    if not unix.lower().endswith((".md", ".html", ".txt")) or NOT_DRAFT_NAME.search(os.path.basename(unix)):
        return False
    if DRAFT_DIR.search(unix):
        return True
    config, root = article_check.load_config(os.path.dirname(path) or ".")
    if not root:
        return False
    relative = os.path.relpath(os.path.realpath(path), root).replace("\\", "/")
    return any(fnmatch.fnmatch(relative, pattern) for pattern in config.get("drafts", []))


def repo_checker(path: str) -> str | None:
    folder = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(folder, REPO_CHECKER)):
            return folder
        if os.path.exists(os.path.join(folder, ".git")) or os.path.dirname(folder) == folder:
            return None
        folder = os.path.dirname(folder)


def check_draft(path: str) -> str:
    root = repo_checker(path)
    command = [sys.executable, os.path.join(root, REPO_CHECKER) if root else CHECKER, os.path.abspath(path)]
    try:
        out = article_check.run_bounded_command(command, timeout=30, cwd=root)
    except subprocess.TimeoutExpired:
        return f"{path}: the article checker timed out; check the draft by hand."
    report = (out.stdout or "").strip() or (out.stderr or "").strip()
    return f"article check {path} ({'repository checker' if root else 'global checker'}):\n{report}"


def _format_masking_notice(flags: list[dict], windowed: list[tuple[str, int, str]]) -> list[str]:
    notices: list[str] = []
    if flags:
        listed = "\n".join(f"- {f['file']}:{f['line']}: {f['pattern']}: `{f['code']}`" for f in flags[:10])
        notices.append(
            "This edit adds code that often hides a problem instead of fixing it where it is owned "
            "(section 1 of the global rules):\n" + listed + "\nIf this is the owning layer, or legitimate "
            "business logic, carry on and say so in the Layer line. If it hides a problem, fix it in the layer "
            f"that owns it. If that layer genuinely cannot express the fix, keep it and add a `{WORKAROUND} "
            "<reason>` comment on or just above the line."
        )
    win_msg = launcher_tests.message(windowed)
    if win_msg:
        notices.append(win_msg)
    return notices


def _handle_pre_tool_use(data: dict, session: str, state: dict) -> dict:
    call = data.get("toolCall") or {}
    call_id = str(call.get("id") or "default")
    tool_name = call.get("name") or ""
    args = call.get("args") or {}
    cwd = _resolve_cwd(data)
    artifact_dir = data.get("artifactDirectoryPath") or ""

    if tool_name == "run_command":
        cmd = str(args.get("CommandLine") or "")
        bad = catastrophic_command(cmd)
        if bad:
            return {"decision": "force_ask", "reason": f"Point-of-no-return command ({bad}): confirm explicitly with the user."}
        if WP_WRITE.search(cmd) and not state.get("wp_reminded"):
            state.setdefault("queued_notices", []).append(ARTICLE_RULES)
            state["wp_reminded"] = True
            save_state(session, state)
        return {"decision": "allow"}

    if tool_name in ("write_file", "edit_file"):
        path = _resolve_path(str(args.get("Path") or ""), cwd)
        if is_tracked_code(path, artifact_dir):
            whole_text = read_text(path)
            if tool_name == "write_file":
                old_text = "" if args.get("Append") else whole_text
                new_text = str(args.get("Content") or "")
            else:
                old_text = str(args.get("Target") or "")
                new_text = str(args.get("Replacement") or "")
            added = added_lines(old_text, new_text)
            flags = scan(path, new_text, added, artifact_dir)
            windowed = [(path, line, code) for line, code in launcher_tests.check(path, new_text, added, whole_text)]
            notices = _format_masking_notice(flags, windowed)
            state.setdefault("pending", {})[call_id] = {"path": path, "flags": flags, "notices": notices}
            save_state(session, state)
        return {"decision": "allow"}

    return {"decision": "allow"}


def _handle_post_tool_use(data: dict, session: str, state: dict) -> dict:
    call = data.get("toolCall") or {}
    call_id = str(call.get("id") or "default")
    tool_name = call.get("name") or ""
    args = call.get("args") or {}
    cwd = _resolve_cwd(data)
    artifact_dir = data.get("artifactDirectoryPath") or ""

    pending_entry = state.setdefault("pending", {}).pop(call_id, None)
    if data.get("error"):
        save_state(session, state)
        return {}

    changed = False
    if pending_entry:
        path = pending_entry.get("path", "")
        if path:
            state["files"] = sorted(set(state.get("files") or []) | {path})
        state.setdefault("flags", []).extend(pending_entry.get("flags") or [])
        state.setdefault("queued_notices", []).extend(pending_entry.get("notices") or [])
        changed = True

    if tool_name in ("write_file", "edit_file"):
        path = _resolve_path(str(args.get("Path") or ""), cwd)
        if path and is_draft(path, artifact_dir) and os.path.isfile(path):
            report = check_draft(path)
            state.setdefault("queued_notices", []).append(report + "\n\n" + ARTICLE_RULES)
            changed = True

    if changed or pending_entry is not None:
        save_state(session, state)
    return {}


def _norm_hooks_json(raw: bytes) -> bytes:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return raw

    def walk(node):
        if isinstance(node, dict):
            cmd = node.get("command")
            if isinstance(cmd, str) and "hooks/powertools_hook.py" in cmd:
                node["command"] = "<PY> hooks/powertools_hook.py"
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for val in node:
                walk(val)

    walk(data)
    return json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _norm_hook_py(raw: bytes) -> bytes:
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return raw
    return re.sub(r"^DEPLOYED_FROM = .*$", 'DEPLOYED_FROM = ""', text, count=1, flags=re.M).encode("utf-8")


def _collect_plugin_files(folder: str) -> set[str]:
    files: set[str] = set()
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if name.endswith((".pyc", ".pyo")):
                continue
            rel = os.path.relpath(os.path.join(root, name), folder).replace("\\", "/")
            files.add(rel)
    return files


def _read_normalized_plugin_file(plugin_dir: str, rel: str) -> bytes:
    full = os.path.join(plugin_dir, *rel.split("/"))
    with open(full, "rb") as fh:
        raw = fh.read()
    if rel == "hooks.json":
        return _norm_hooks_json(raw)
    if rel == "hooks/powertools_hook.py":
        return _norm_hook_py(raw)
    return raw


def _check_plugin_drift() -> str | None:
    """Compare installed plugin bundles under HERE/../.. with the checkout named in DEPLOYED_FROM."""
    try:
        src_root = os.environ.get("CONCLAVE_AGY_SOURCE") or DEPLOYED_FROM
        installed_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        if not src_root or not os.path.isdir(src_root) or not os.path.isdir(installed_root):
            return None
        if os.path.normcase(os.path.realpath(src_root)) == os.path.normcase(os.path.realpath(installed_root)):
            return None

        drifted: list[str] = []
        for plugin_name in sorted(os.listdir(src_root)):
            src_plugin = os.path.join(src_root, plugin_name)
            if not os.path.isdir(src_plugin) or not os.path.isfile(os.path.join(src_plugin, "plugin.json")):
                continue
            inst_plugin = os.path.join(installed_root, plugin_name)
            if not os.path.isdir(inst_plugin):
                drifted.append(plugin_name)
                continue
            src_files = _collect_plugin_files(src_plugin)
            inst_files = _collect_plugin_files(inst_plugin)
            if src_files != inst_files:
                drifted.append(plugin_name)
                continue
            for rel in sorted(src_files):
                if _read_normalized_plugin_file(src_plugin, rel) != _read_normalized_plugin_file(inst_plugin, rel):
                    drifted.append(plugin_name)
                    break

        if not drifted:
            return None
        deploy_py = os.path.normpath(os.path.join(src_root, "..", "..", "global", "deploy.py")).replace("\\", "/")
        py_cmd = "python" if os.name == "nt" else "python3"
        return (
            f"Conclave plugin drift detected in {', '.join(drifted)} "
            f"(installed copy under {installed_root} differs from {src_root}). "
            f'Run `{py_cmd} "{deploy_py}" --agent agy` to sync.'
        )
    except OSError:
        return None


def _handle_pre_invocation(data: dict, session: str, state: dict) -> dict:
    raw_input = str(data.get("lastUserInput") or "")
    dirty = False
    if not state.get("drift_checked"):
        state["drift_checked"] = True
        dirty = True
        drift_msg = _check_plugin_drift()
        if drift_msg:
            state.setdefault("queued_notices", []).append(drift_msg)
    if raw_input and not state.get("prompt_checked"):
        clean = extract_clean_prompt(raw_input)
        state["prompt_checked"] = True
        dirty = True
        if PROMPT.search(clean) and not RULES_TALK.search(clean):
            state.setdefault("queued_notices", []).append(ARTICLE_RULES)
    notices = list(state.get("queued_notices") or [])
    if notices:
        state["queued_notices"] = []
        dirty = True
    if dirty:
        save_state(session, state)
    if notices:
        return {"injectSteps": [{"systemMessage": {"systemMessage": "\n\n".join(notices)}}]}
    return {}


def _transcript_report(transcript_path: str) -> str:
    """Assistant text emitted since the latest user prompt in transcript_full.jsonl or transcript.jsonl."""
    if not transcript_path:
        return ""
    candidate = transcript_path
    if os.path.basename(transcript_path) == "transcript.jsonl":
        full = os.path.join(os.path.dirname(transcript_path), "transcript_full.jsonl")
        if os.path.isfile(full):
            candidate = full
    try:
        with open(candidate, encoding="utf-8", errors="replace") as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError, TypeError):
        return ""
    texts: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        etype = entry.get("type")
        if etype == "USER_INPUT":
            texts = []
        elif etype == "PLANNER_RESPONSE":
            content = entry.get("content")
            if isinstance(content, str) and content:
                texts.append(content)
        else:
            msg = entry.get("message")
            if isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    texts = []
                elif role == "assistant" and isinstance(content, str) and content:
                    texts.append(content)
    return "\n".join(texts)


def _handle_stop(data: dict, session: str, state: dict) -> dict:
    if data.get("terminationReason", "NO_TOOL_CALL") != "NO_TOOL_CALL":
        return {"decision": "stop"}
    files = state.get("files") or []
    if not files:
        return {"decision": "stop"}
    if state.get("sent_back"):
        state["files"] = []
        state["flags"] = []
        state["sent_back"] = False
        save_state(session, state)
        return {"decision": "stop"}
    report = _transcript_report(str(data.get("transcriptPath") or ""))
    if LAYER_LINE.search(report):
        state["files"] = []
        state["flags"] = []
        state["sent_back"] = False
        save_state(session, state)
        return {"decision": "stop"}
    state["sent_back"] = True
    save_state(session, state)
    listed = ", ".join(files[:8]) + (" and more" if len(files) > 8 else "")
    reason = (
        f"This turn changed code ({listed}). End the report with a `Layer:` line (section 1 of the global rules): "
        "the layer that owns the behavior, the layer you changed, and whether anything is a workaround."
    )
    flags = state.get("flags") or []
    if flags:
        reason += " Cover these flagged lines in it: " + "; ".join(
            f"{f['file']}:{f['line']} {f['pattern']}" for f in flags[:10]
        ) + "."
    return {"decision": "continue", "reason": reason}


def dispatch(data: dict) -> dict:
    event = data.get("hookEventName", "")
    session = str(data.get("conversationId") or "default")
    state = load_state(session)
    raw_input = str(data.get("lastUserInput") or "")
    before = dict(state)
    sync_turn(state, raw_input)
    if state != before and event != "Stop":
        save_state(session, state)
    if event == "PreToolUse":
        return _handle_pre_tool_use(data, session, state)
    if event == "PostToolUse":
        return _handle_post_tool_use(data, session, state)
    if event == "PreInvocation":
        return _handle_pre_invocation(data, session, state)
    if event == "Stop":
        return _handle_stop(data, session, state)
    return {}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (ValueError, TypeError):
        print(json.dumps({"decision": "allow"}))
        return 0
    if not isinstance(data, dict):
        print(json.dumps({}))
        return 0
    out = dispatch(data)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
