#!/usr/bin/env python3
"""Global Codex hook: keep "fix it at the correct layer" (section 1 of the global rules) honest.

Runs unchanged on Windows and WSL. It never blocks a tool call. Two parts:

- Masking patterns. When an edit adds code that typically hides a problem instead of fixing it where it is owned
  (an output buffer, a filter over rendered HTML, CSS hiding an element, a suppressed type or lint error, a
  skipped test, a swallowed error, a bypassed git hook, a direct database write), the agent is told which lines
  and asked to justify them. A `WORKAROUND: <reason>` comment on the line or up to three lines above answers it.
  Claude's Write, Edit and MultiEdit are read at PreToolUse, while the old file is still on disk, so only added
  lines count, and they count as changed code only once PostToolUse shows they landed (another hook, such as a
  repository's own gate, may deny them). Codex's apply_patch is read at PostToolUse from the patch's added lines.
- Layer statement. After a turn that changed code, the final report must carry a `Layer:` line naming the layer
  that owns the behaviour, the layer changed and any workaround. If it is missing, the Stop event sends the
  agent back once to add it; the second stop always succeeds.

Prose files (Markdown, plain text) are neither scanned nor counted as code changes.
"""
import json
import os
import re
import sys
import tempfile

CLAUDE_FILE_TOOLS = ("Write", "Edit", "MultiEdit")
PROSE = (".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc", ".csv", ".log")
WORKAROUND = "WORKAROUND:"
LAYER_LINE = re.compile(r"^\W*layer\W*:", re.I | re.M)
STATE_DIR = os.path.join(tempfile.gettempdir(), "codex-layer-rules")

# (name, pattern, extensions it applies to or None for all code files)
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


def emit(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def is_code(path):
    return bool(path) and not path.lower().endswith(PROSE)


def added_lines(old_text, new_text):
    """0-based line numbers in new_text that old_text does not already have (a multiset difference)."""
    pool = {}
    for line in old_text.splitlines():
        pool[line] = pool.get(line, 0) + 1
    added = set()
    for i, line in enumerate(new_text.splitlines()):
        if pool.get(line):
            pool[line] -= 1
        else:
            added.add(i)
    return added


def scan(path, new_text, added):
    """Masking patterns that touch an added line and have no WORKAROUND comment nearby."""
    if not is_code(path) or not added:
        return []
    ext = os.path.splitext(path)[1].lower()
    lines = new_text.splitlines()
    flags = []
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


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def claude_edits(tool_name, tool_input, cwd):
    """(path, new text, added line numbers) for Claude's file tools, read before the edit lands."""
    path = tool_input.get("file_path", "")
    if path and not os.path.isabs(path):
        path = os.path.join(cwd, path)
    if tool_name == "Write":
        new = tool_input.get("content", "")
        return [(path, new, added_lines(read(path), new))]
    edits = tool_input.get("edits", []) if tool_name == "MultiEdit" else [tool_input]
    return [(path, e.get("new_string", ""), added_lines(e.get("old_string", ""), e.get("new_string", ""))) for e in edits]


def patch_edits(patch, cwd):
    """(path, new text, added line numbers) per file in a Codex apply_patch body."""
    out, path, lines, added = [], None, [], set()

    def flush():
        if path:
            out.append((path if os.path.isabs(path) else os.path.join(cwd, path), "\n".join(lines), set(added)))

    for raw in patch.splitlines():
        header = re.match(r"\*\*\* (Add|Update) File: (.+?)\s*$", raw)
        if header or raw.startswith("*** "):
            flush()
            path, lines, added = (header.group(2) if header else None), [], set()
        elif path is not None:
            if raw.startswith("+"):
                added.add(len(lines))
                lines.append(raw[1:])
            elif raw.startswith(" "):
                lines.append(raw[1:])
    flush()
    return out


def strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


def state_path(session):
    return os.path.join(STATE_DIR, re.sub(r"[^\w.-]", "_", session or "default") + ".json")


def load_state(session):
    try:
        with open(state_path(session), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"files": [], "flags": [], "pending": {}}


def save_state(session, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(state_path(session), "w", encoding="utf-8") as f:
        json.dump(state, f)


def clear_state(session):
    try:
        os.remove(state_path(session))
    except OSError:
        pass


def record(session, event, edits, landed):
    """Scan edits and warn. Landed edits count as changed code at once; an edit still waiting for its tool call (a
    Claude PreToolUse) is held as pending until confirm() sees it land, so an edit another hook denies changes nothing."""
    edits = [e for e in edits if is_code(e[0])]
    if not edits:
        return
    flags = [f for path, new, added in edits for f in scan(path, new, added)]
    state = load_state(session)
    if landed:
        state["files"] = sorted(set(state["files"]) | {path for path, _, _ in edits})
        state["flags"] += flags
    else:
        pending = state.setdefault("pending", {})
        for path, _, _ in edits:
            pending.setdefault(path, [])
        for f in flags:
            pending[f["file"]].append(f)
    save_state(session, state)
    if flags:
        listed = "\n".join(f"- {f['file']}:{f['line']}: {f['pattern']}: `{f['code']}`" for f in flags[:10])
        emit(event, "This edit adds code that often hides a problem instead of fixing it where it is owned "
                    "(section 1 of the global rules):\n" + listed + "\nIf this is the owning layer, or legitimate "
                    "business logic, carry on and say so in the Layer line. If it hides a problem, fix it in the layer "
                    f"that owns it. If that layer genuinely cannot express the fix, keep it and add a `{WORKAROUND} "
                    "<reason>` comment on or just above the line.")


def confirm(session, path):
    """A Claude file tool finished: its pending edit to `path` is now changed code."""
    if not is_code(path):
        return
    state = load_state(session)
    state["flags"] += state.setdefault("pending", {}).pop(path, [])
    state["files"] = sorted(set(state["files"]) | {path})
    save_state(session, state)


def text_of(content):
    if isinstance(content, str):
        return [content]
    return [b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") in ("text", "output_text", "input_text")]


def final_report(transcript_path):
    """The assistant's text since the user's last prompt, from a Claude or Codex transcript."""
    texts = []
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError, TypeError):
        return ""
    for entry in entries:
        item = entry.get("payload", {}) if entry.get("type") == "response_item" else entry.get("message", {})
        role = item.get("role") or entry.get("type")
        content = item.get("content")
        if role == "user":
            blocks = content if isinstance(content, list) else []
            if isinstance(content, str) or any(isinstance(b, dict) and b.get("type") in ("text", "input_text") for b in blocks):
                texts = []
        elif role == "assistant":
            texts += text_of(content)
    return "\n".join(texts)


def stop(data, session):
    state = load_state(session)
    if not state["files"]:
        return
    # The hook's own record, not stop_hook_active, limits it to one send-back: another Stop hook (a repository's
    # campaign controller) keeps stop_hook_active true for a whole unattended run, which would switch this off.
    if state.get("sent_back"):
        clear_state(session)
        return
    report = data.get("last_assistant_message") or final_report(data.get("transcript_path"))
    if LAYER_LINE.search(report or ""):
        clear_state(session)
        return
    state["sent_back"] = True
    save_state(session, state)
    files = ", ".join(state["files"][:8]) + (" and more" if len(state["files"]) > 8 else "")
    reason = (f"This turn changed code ({files}). End the report with a `Layer:` line (section 1 of the global rules): "
              "the layer that owns the behaviour, the layer you changed, and whether anything is a workaround.")
    if state["flags"]:
        reason += " Cover these flagged lines in it: " + "; ".join(
            f"{f['file']}:{f['line']} {f['pattern']}" for f in state["flags"][:10]) + "."
    print(json.dumps({"decision": "block", "reason": reason}))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    event = data.get("hook_event_name", "")
    session = data.get("session_id", "")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    cwd = data.get("cwd") or os.getcwd()
    if event == "UserPromptSubmit":
        clear_state(session)
    elif event == "PreToolUse" and tool_name in CLAUDE_FILE_TOOLS and isinstance(tool_input, dict):
        record(session, event, claude_edits(tool_name, tool_input, cwd), landed=False)
    elif event == "PostToolUse" and tool_name in CLAUDE_FILE_TOOLS and isinstance(tool_input, dict):
        path = tool_input.get("file_path", "")
        confirm(session, path if os.path.isabs(path) else os.path.join(cwd, path))
    elif event == "PostToolUse" and tool_name == "apply_patch":
        record(session, event, patch_edits("\n".join(strings(tool_input)), cwd), landed=True)
    elif event == "Stop":
        stop(data, session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
