"""Advisory check for launcher tests, called from layer_rules.py: a launcher test never opens a window.

A launcher test is a test file whose text names a campaign or run launcher (start-campaign, start-run,
start-unattended-run, unattended-run, run-desktop). In such a file, an added subprocess.run or subprocess.Popen
without creationflags, or a Start-Process without -NoNewWindow, is flagged: on Windows a console child of a parent
with no console opens a visible window over the owner's work (Office's launcher tests flashed 5 to 10 per run on
2026-11-12). The rule is for console children only. A start whose program is an application rather than a console
program (an .exe other than pwsh, powershell, python, cmd, git, taskkill or node) is never flagged, because a test,
interface test or capture may need its window; and `window-exempt: <reason>` in a comment on the line accepts a start
as it is. Every other test file, and every non-test file, is left alone.
"""
import io
import os
import re
import tokenize

LAUNCHER = re.compile(r"start-campaign|start-run|start-unattended-run|unattended-run|run-desktop", re.I)
TEST_NAME = re.compile(r"(^test_.*\.py$|_test\.py$|\.tests?\.ps1$|^test.*\.ps1$|\.test\.[cm]?[jt]s$)", re.I)
CONSOLE = {"pwsh", "powershell", "python", "python3", "py", "cmd", "git", "taskkill", "node"}
EXEMPT = "window-exempt:"
PY_START = re.compile(r"\bsubprocess\.(run|Popen)\s*\(")
PS_START = re.compile(r"\bStart-Process\b", re.I)


def is_launcher_test(path, text):
    return bool(TEST_NAME.search(os.path.basename(path or ""))) and bool(LAUNCHER.search(text or ""))


def _call_text(text, open_paren):
    """The text of a call from its opening parenthesis to the one that closes it."""
    depth, i, quote = 0, open_paren, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren:i + 1]
        i += 1
    return text[open_paren:]


def _program(call):
    """The program a call starts, when its first string literal names one."""
    found = re.search(r"[\[(]\s*(?:r|f)?[\"']([^\"']+)[\"']", call)
    return found.group(1) if found else ""


def _is_application(program):
    base = os.path.basename(program.replace("\\", "/")).lower()
    return base.endswith(".exe") and base[:-4] not in CONSOLE


def _in_strings(path, text):
    """Character ranges of the string literals of a Python file: a start written inside one (a test's fixture text)
    is not a start. Other files have none."""
    if not path.lower().endswith(".py"):
        return []
    offsets, total = [], 0
    for line in text.splitlines(keepends=True):
        offsets.append(total)
        total += len(line)
    ranges = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.STRING:
                (sr, sc), (er, ec) = tok.start, tok.end
                ranges.append((offsets[sr - 1] + sc, offsets[er - 1] + ec))
    except (tokenize.TokenError, IndentationError, SyntaxError, IndexError):
        return ranges  # a file mid-edit may not tokenize to the end: what was read still counts
    return ranges


def check(path, new_text, added):
    """Flags for added starts in a launcher test that open a window: [(line, code)]."""
    if not added or not is_launcher_test(path, new_text):
        return []
    lines = new_text.splitlines()
    strings = _in_strings(path, new_text)

    def quoted(position):
        return any(start <= position < end for start, end in strings)
    flags = []
    for match in PY_START.finditer(new_text):
        if quoted(match.start()):
            continue
        first = new_text.count("\n", 0, match.start())
        call = _call_text(new_text, match.end() - 1)
        last = first + call.count("\n")
        if not added.intersection(range(first, last + 1)):
            continue
        if "creationflags" in call or _is_application(_program(call)):
            continue
        if any(EXEMPT in lines[i] for i in range(first, min(last + 1, len(lines)))):
            continue
        flags.append((first + 1, lines[first].strip()[:120]))
    for match in PS_START.finditer(new_text):
        if quoted(match.start()):
            continue
        line_no = new_text.count("\n", 0, match.start())
        line = lines[line_no]
        if line_no not in added or re.search(r"-NoNewWindow\b", line, re.I) or EXEMPT in line:
            continue
        value = r"(?:\"([^\"]+)\"|'([^']+)'|(\S+))"
        target = (re.search(r"-FilePath\s+" + value, line, re.I)
                  or re.search(r"Start-Process\s+(?!-)" + value, line, re.I))
        if target and _is_application(next(g for g in target.groups() if g)):
            continue
        flags.append((line_no + 1, line.strip()[:120]))
    return flags


def message(flagged):
    """The advisory for [(path, line, code)], or None."""
    if not flagged:
        return None
    listed = "\n".join(f"- {path}:{line}: `{code}`" for path, line, code in flagged[:10])
    return ("This launcher test starts a console child that can open a window (a launcher test never opens a "
            "window):\n" + listed + "\nPass creationflags=subprocess.CREATE_NO_WINDOW on Windows and 0 elsewhere "
            "(Python), or -NoNewWindow (Start-Process). A real application or browser whose window the test needs is "
            "not flagged; never put -WindowStyle Hidden on an app launch. If this start must keep its window, say why "
            f"in a `{EXEMPT} <reason>` comment on the line.")
