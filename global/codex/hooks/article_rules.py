#!/usr/bin/env python3
"""Global Codex hook: keep the owner's writing rules in front of every article and copy write.

Runs unchanged on Windows and WSL, for three events. It never blocks; it adds context. (Codex asks once to trust
the hook before it runs.)
- UserPromptSubmit: a prompt to write or rewrite an article, post, blog or marketing copy gets the rules.
- PreToolUse (a shell tool): a command that writes post content to WordPress (wp post create/update, a
  content-writing script) gets the rules and the `--post` check reminder.
- PostToolUse (a file write): a Markdown, HTML or text file in a drafts, articles, posts or blog folder, or
  matching the repository's "drafts" globs in .article-check.json, is run through the checker and the report
  is returned.

The checker is `article_check.py` beside this file, run with the same Python as the hook, so nothing needs to
be on PATH. A repository with its own `scripts/article-check.py` at its root owns its article standard, so its
drafts go through that checker instead, run from the repository root. The rules text is section 10 of the global rules in rules/codex.md; change both together.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "article_check.py")
sys.path.insert(0, HERE)
import article_check  # noqa: E402  (the checker beside this file; its config loader decides what a draft is)
CHECK_CMD = f'{"python" if os.name == "nt" else "python3"} "{CHECKER}"'

RULES = (
    "Owner writing rules (section 10 of the global rules):\n"
    "1. Creative writing (articles, page and marketing copy, product descriptions) uses NLP (natural language "
    "processing): answer first, question-shaped headings, short active sentences, clear named entities, no stock "
    "AI phrasing, no em or en dashes.\n"
    "Articles (blog posts, guides, whitepapers) also:\n"
    "2. Add original value: unique insights, first-hand experience and accurate facts, with every figure sourced.\n"
    "3. Meet E-E-A-T: a named author, first-hand detail, primary sources, honest limits and a review date.\n"
    "4. Never carry a line saying AI assisted with or wrote the article.\n"
    "5. Claude researches, writes and rewrites; Codex only reviews (facts, AI-sounding prose, SEO) and suggests. "
    "No humanizer or paraphrasing tools.\n"
    f"Run `{CHECK_CMD} <draft>` before writing an article back and `{CHECK_CMD} --post <id>` after (in a repository "
    "with its own article checker, use that one); fix every FAIL and answer every WARN."
)
WRITE_VERB = r"\b(write|rewrite|draft|improve|update|polish|expand|edit)\w*\s+(?:\w+\s+){0,4}?"
WRITING = (r"(article|articles|blog ?posts?|whitepapers?|copywriting|product descriptions?|newsletters?"
           r"|(marketing|page|web|website|sales|ad|product|homepage|hero|landing ?page) copy)\b")
# The prompt must ask to write something, not merely mention articles or the rules themselves.
PROMPT = re.compile(WRITE_VERB + WRITING + r"|\b(article|blog ?post|whitepaper)s?\s+(?:\w+\s+){0,3}?(rewrite|draft|update)\b", re.I)
RULES_TALK = re.compile(r"\b(rules?|hook|hooks|globally)\b", re.I)
WP_WRITE = re.compile(r"\bwp(-launch)?\b.*\bpost\s+(create|update)\b|post_content|article-(write|rewrite|apply)|update_post", re.I)
# A draft lives in a drafts, articles, posts or blog folder, or matches the repository's "drafts" globs in
# .article-check.json. File names alone prove nothing: style-guide.md and postgres-notes.md are not articles.
DRAFT_DIR = re.compile(r"/(drafts?|articles?|posts?|blog)/", re.I)
NOT_DRAFT_NAME = re.compile(r"^(readme|changelog|license|contributing|index)\.", re.I)
SHELL_TOOLS = ("Bash", "PowerShell", "shell", "exec_command", "local_shell")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "apply_patch")


def emit(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def strings(value):
    """Every string inside a tool input, whatever its shape (Codex passes commands and patches as text or argv)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings(v)]
    return []


def written_paths(tool_input):
    """Claude names the file; Codex's apply_patch carries it in the patch text."""
    if isinstance(tool_input, dict) and tool_input.get("file_path"):
        return [tool_input["file_path"]]
    return re.findall(r"\*\*\* (?:Add|Update) File: (.+?)\s*$", "\n".join(strings(tool_input)), re.M)


def is_draft(path):
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


REPO_CHECKER = os.path.join("scripts", "article-check.py")


def repo_checker(path):
    """A repository's own checker (scripts/article-check.py at its root) owns its article standard."""
    folder = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(folder, REPO_CHECKER)):
            return folder
        if os.path.exists(os.path.join(folder, ".git")) or os.path.dirname(folder) == folder:
            return None
        folder = os.path.dirname(folder)


def check_draft(path):
    root = repo_checker(path)
    command = [sys.executable, os.path.join(root, REPO_CHECKER) if root else CHECKER, os.path.abspath(path)]
    try:
        out = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=30, cwd=root)
    except subprocess.TimeoutExpired:
        return f"{path}: the article checker timed out; check the draft by hand."
    report = out.stdout.strip() or out.stderr.strip()
    return f"article check {path} ({'repository checker' if root else 'global checker'}):\n{report}"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    event = data.get("hook_event_name", "")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    if event == "UserPromptSubmit":
        prompt = data.get("prompt", "")
        if PROMPT.search(prompt) and not RULES_TALK.search(prompt):
            emit(event, RULES)
    elif event == "PreToolUse" and tool_name in SHELL_TOOLS:
        if WP_WRITE.search(" ".join(strings(tool_input))):
            emit(event, RULES)
    elif event == "PostToolUse" and tool_name in WRITE_TOOLS:
        cwd = data.get("cwd") or os.getcwd()
        reports = []
        for path in written_paths(tool_input):
            path = path if os.path.isabs(path) else os.path.join(cwd, path)
            if not is_draft(path):
                continue
            if os.path.isfile(path):
                reports.append(check_draft(path))
        if reports:
            emit(event, "\n\n".join(reports) + "\n\n" + RULES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
