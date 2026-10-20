#!/usr/bin/env python3
"""Reference for the reviewer editor's in-place pin edits (D00 T01 §4, design spec section 2).

    python design/spikes/pin_edits.py [--diff] [--write extensions/vscode/test/fixtures/edits]

Applies each edit the editor makes to the shipped pin, line by line under the narrow layout the spec allows, checks
every result with the dispatcher's own load_pin, and prints each edit as a unified diff of the shipped pin. These
diffs are the expected outputs D02 T01 §4's golden tests reproduce in TypeScript. Stdlib only.
"""
import difflib
import importlib.util
import json
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / "kits/reviewer/templates/.conclave/reviewers.toml"

# The layout the editor edits in place; any other line makes the pin read-only (the pin-layout state).
HEADER = re.compile(r"\[(reviewers\.[A-Za-z0-9_-]+|routes)\][ \t]*(#.*)?")
KEY = re.compile(r"([A-Za-z0-9_-]+)[ \t]*=[ \t]*(\"[^\"\\\n]*\"|'[^'\n]*'|[0-9]+)([ \t]*#.*)?")
# Elements need the comma between them that TOML requires, so no two quantifiers compete for the same spaces and a
# long malformed array cannot backtrack exponentially.
ROUTE = re.compile(r"([A-Za-z0-9_-]+)[ \t]*=[ \t]*\[([ \t]*(?:\"[A-Za-z0-9_-]+\"(?:[ \t]*,[ \t]*\"[A-Za-z0-9_-]+\")*(?:[ \t]*,)?[ \t]*)?)\]([ \t]*#.*)?")
TOKEN = re.compile(r'"([A-Za-z0-9_-]+)"')


def editable(text):
    """True when every line is blank, a comment, a header, a one-line key or a one-line route array."""
    table = None
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if m := HEADER.fullmatch(s):
            table = m.group(1)
        elif table == "routes":
            if not ROUTE.fullmatch(s):
                return False
        elif not KEY.fullmatch(s):
            return False
    return True


def lines_of(text):
    """Lines split on \n alone, each keeping its ending: TOML ends a line with \n or \r\n and nothing else, so a
    U+2028 or a form feed inside a comment is a character of that line (str.splitlines would split there)."""
    return re.findall(r"[^\n]*\n|[^\n]+$", text)


def rebuild(inner, names):
    """The array's inside with these names, in its own style: the spacing after "[", between elements and before "]"
    are kept, so an edit changes only the names."""
    tokens = list(TOKEN.finditer(inner))
    lead = inner[:tokens[0].start()] if tokens else ""
    trail = inner[tokens[-1].end():] if tokens else ""
    sep = inner[tokens[0].end():tokens[1].start()] if len(tokens) >= 2 else ", "
    return lead + sep.join(f'"{n}"' for n in names) + trail


def eol(text):
    return "\r\n" if "\r\n" in text else "\n"


def table_span(lines, name):
    """Index of the header line and one past the table's last key line (trailing blank lines excluded)."""
    start = next(i for i, l in enumerate(lines) if HEADER.fullmatch(l.strip()) and HEADER.fullmatch(l.strip()).group(1) == name)
    end = start + 1
    while end < len(lines) and not HEADER.fullmatch(lines[end].strip()):
        end += 1
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return start, end


def ending(line, nl):
    """A line given its line ending if it has none (the last line of a file without a final newline)."""
    return line if line.endswith(("\n", "\r")) else line + nl


def remove_line(lines, i, comment):
    """Remove a key or route line; a trailing comment on it stays behind as a comment line in its place."""
    if comment:
        body = lines[i].rstrip("\r\n")
        lines[i] = body[:len(body) - len(body.lstrip())] + comment.strip() + lines[i][len(body):]
    else:
        del lines[i]


def comment_block_above(lines, start):
    """The comment lines directly above a header, with no blank line between them and it."""
    i = start
    while i > 0 and lines[i - 1].lstrip().startswith("#"):
        i -= 1
    return i


def set_field(text, reviewer, key, value):
    """Set, add (value given, key absent) or remove (value None) one key of one reviewer table."""
    lines, nl = lines_of(text), eol(text)
    start, end = table_span(lines, f"reviewers.{reviewer}")
    for i in range(start + 1, end):
        m = KEY.fullmatch(lines[i].strip())
        if m and m.group(1) == key:
            if value is None:
                remove_line(lines, i, m.group(3))
            else:
                quote = m.group(2)[0]
                lines[i] = re.sub(re.escape(m.group(2)), f"{quote}{value}{quote}", lines[i], count=1)
            return "".join(lines)
    if value is not None:
        lines[end - 1] = ending(lines[end - 1], nl)
        lines.insert(end, f'{key} = "{value}"{nl}')
    return "".join(lines)


def add_reviewer(text, name, entry):
    """A new table after the last reviewer table, before the comment block above [routes], blank line each side."""
    lines, nl = lines_of(text), eol(text)
    last = max(i for i, l in enumerate(lines) if (m := HEADER.fullmatch(l.strip())) and m.group(1).startswith("reviewers."))
    _, end = table_span(lines, HEADER.fullmatch(lines[last].strip()).group(1))
    lines[end - 1] = ending(lines[end - 1], nl)
    block = [nl, f"[reviewers.{name}]{nl}"] + [f'{k} = "{v}"{nl}' for k, v in entry.items()]
    lines[end:end] = block
    return "".join(lines)


def rename_reviewer(text, old, new):
    lines = lines_of(text)
    start, _ = table_span(lines, f"reviewers.{old}")
    lines[start] = lines[start].replace(f"[reviewers.{old}]", f"[reviewers.{new}]", 1)
    out = "".join(lines)
    return set_routes(out, lambda names: [new if n == old else n for n in names])


def delete_reviewer(text, name):
    """The table, the comment block directly above it and one blank line after it; its name leaves every route."""
    lines = lines_of(text)
    start, end = table_span(lines, f"reviewers.{name}")
    first = comment_block_above(lines, start)
    if end < len(lines) and not lines[end].strip():
        end += 1
    del lines[first:end]
    return set_routes("".join(lines), lambda names: [n for n in names if n != name])


def set_routes(text, change):
    """Apply change(names) to every route; a route left empty is removed, never written as []."""
    lines = lines_of(text)
    start, end = table_span(lines, "routes")
    for i in range(end - 1, start, -1):
        m = ROUTE.fullmatch(lines[i].strip())
        if not m:
            continue
        names = TOKEN.findall(m.group(2))
        new = change(names)
        if new == names:
            continue
        if not new:
            remove_line(lines, i, m.group(3))
        else:
            lines[i] = lines[i].replace(f"[{m.group(2)}]", "[" + rebuild(m.group(2), new) + "]", 1)
    return "".join(lines)


def set_route(text, writer, names):
    """Rewrite one writer's array on its own line, or append a line after the last route when it has none."""
    lines, nl = lines_of(text), eol(text)
    start, end = table_span(lines, "routes")
    array = "[" + ", ".join(f'"{n}"' for n in names) + "]"
    for i in range(start + 1, end):
        m = ROUTE.fullmatch(lines[i].strip())
        if m and m.group(1) == writer:
            if TOKEN.findall(m.group(2)) != list(names):
                lines[i] = lines[i].replace(f"[{m.group(2)}]", "[" + rebuild(m.group(2), names) + "]", 1)
            return "".join(lines)
    lines[end - 1] = ending(lines[end - 1], nl)
    lines.insert(end, f"{writer} = {array}{nl}")
    return "".join(lines)


def remove_route(text, writer):
    lines = lines_of(text)
    start, end = table_span(lines, "routes")
    for i in range(start + 1, end):
        m = ROUTE.fullmatch(lines[i].strip())
        if m and m.group(1) == writer:
            remove_line(lines, i, m.group(3))
            break
    return "".join(lines)


def load_pin():
    spec = importlib.util.spec_from_file_location("dispatch", ROOT / "kits/reviewer/templates/scripts/review-dispatch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_pin, module.Refused


def cases(shipped):
    added = add_reviewer(shipped, "mini", {"cli": "codex", "model": "gpt-6-mini", "effort": "low"})
    to_agy = set_field(set_field(added, "mini", "cli", "agy"), "mini", "model", "gemini-4-argon-low")
    removed_route = remove_route(shipped, "gemini")
    return [
        ("set-field", "astra's effort from medium to high", shipped, set_field(shipped, "astra", "effort", "high")),
        ("add-reviewer", "add mini (codex, gpt-6-mini, low)", shipped, added),
        ("remove-field", "mini moved to Antigravity: cli, model, and its effort line removed", added,
         set_field(to_agy, "mini", "effort", None)),
        ("add-field", "the reverse: mini back to Codex, its effort line added", set_field(to_agy, "mini", "effort", None),
         set_field(set_field(set_field(set_field(to_agy, "mini", "effort", None), "mini", "cli", "codex"),
                             "mini", "model", "gpt-6-mini"), "mini", "effort", "low")),
        ("rename-reviewer", "astra renamed gpt6", shipped, rename_reviewer(shipped, "astra", "gpt6")),
        ("delete-reviewer", "sonnet deleted", shipped, delete_reviewer(shipped, "sonnet")),
        ("set-route", "codex reviewed by sonnet, then gemini", shipped, set_route(shipped, "codex", ["sonnet", "gemini"])),
        ("remove-route", "gemini's route removed", shipped, removed_route),
        ("add-route", "a route for a writer with none, appended", removed_route,
         set_route(removed_route, "gemini", ["sonnet", "astra"])),
    ]


EDITS = {"set_field": set_field, "add_reviewer": add_reviewer, "rename_reviewer": rename_reviewer,
         "delete_reviewer": delete_reviewer, "set_route": set_route, "remove_route": remove_route}


def golden(shipped):
    """Every golden case as (name, input, edits): the edits are [function, *args] applied in order. The TypeScript
    editor (extensions/vscode/src/core/pinText.ts) replays the same edits and must give the same bytes."""
    mini = {"cli": "codex", "model": "gpt-6-mini", "effort": "low"}
    added = add_reviewer(shipped, "mini", mini)
    to_agy = [["set_field", "mini", "cli", "agy"], ["set_field", "mini", "model", "gemini-4-argon-low"]]
    no_effort = apply(added, to_agy + [["set_field", "mini", "effort", None]])
    back = [["set_field", "mini", "cli", "codex"], ["set_field", "mini", "model", "gpt-6-mini"],
            ["set_field", "mini", "effort", "low"]]
    bare = 'schema_version = 1\n[routes]\n[reviewers.mini]\ncli = "agy"\nmodel = "gemini-4-argon-low"'
    return [
        ("set-field", shipped, [["set_field", "astra", "effort", "high"]]),
        ("add-reviewer", shipped, [["add_reviewer", "mini", mini]]),
        ("remove-field", added, to_agy + [["set_field", "mini", "effort", None]]),
        ("add-field", no_effort, back),
        ("rename-reviewer", shipped, [["rename_reviewer", "astra", "gpt6"]]),
        ("delete-reviewer", shipped, [["delete_reviewer", "sonnet"]]),
        ("set-route", shipped, [["set_route", "codex", ["sonnet", "gemini"]]]),
        ("remove-route", shipped, [["remove_route", "gemini"]]),
        ("add-route", remove_route(shipped, "gemini"), [["set_route", "gemini", ["sonnet", "astra"]]]),
        # The same move to Antigravity as remove-field, with a note on the effort line that must stay behind.
        ("remove-field-comment", added.replace('effort = "low"', 'effort = "low" # retained operator note'),
         to_agy + [["set_field", "mini", "effort", None]]),
        ("remove-route-comment", shipped.replace('gemini = ["astra", "sonnet"]', 'gemini = ["astra", "sonnet"] # kept'),
         [["remove_route", "gemini"]]),
        ("add-field-no-final-newline", apply(bare, back[:2]), [["set_field", "mini", "effort", "low"]]),
        # Review round 1 of D02 T01 §4: a route keeps its own spacing through a rename and a reorder.
        ("route-style", shipped.replace('claude = ["astra", "gemini"]', 'claude = [ "astra" ,\t"gemini" ] # keep'),
         [["rename_reviewer", "astra", "gpt6"], ["set_route", "claude", ["gemini", "gpt6"]]]),
    ]


def apply(text, edits):
    for name, *args in edits:
        text = EDITS[name](text, *args)
    return text


def write_golden(directory, shipped):
    """Write each golden case as <name>/input.toml, edits.json and expected.toml, byte for byte."""
    by_name = {name: after for name, _, _, after in cases(shipped)}
    for name, before, edits in golden(shipped):
        after = apply(before, edits)
        if name in by_name:
            assert after == by_name[name], f"{name}: the golden edits disagree with the published case"
        case = Path(directory) / name
        case.mkdir(parents=True, exist_ok=True)
        (case / "input.toml").write_bytes(before.encode("utf-8"))
        (case / "expected.toml").write_bytes(after.encode("utf-8"))
        (case / "edits.json").write_bytes((json.dumps(edits, indent=2) + "\n").encode("utf-8"))
    print(f"wrote {len(golden(shipped))} golden cases to {directory}", file=sys.stderr)


def main():
    shipped = PIN.read_text(encoding="utf-8")
    if "--write" in sys.argv:
        write_golden(sys.argv[sys.argv.index("--write") + 1], shipped)
    assert editable(shipped), "the shipped pin must be in the editable layout"
    assert not editable("reviewers = { astra = { cli = 'codex' } }\n"), "an inline table is not editable"
    check, Refused = load_pin()
    # Review round 1 of D02 T01 §4: a U+2028 in a comment is part of that line, an unchanged route is not rewritten,
    # and a long malformed array is refused at once.
    sep = shipped.replace('effort = "medium"', 'effort = "medium" # one\u2028# two')
    assert editable(sep) and set_field(sep, "astra", "effort", "high").count("# one\u2028# two") == 1
    spaced = shipped.replace('claude = ["astra", "gemini"]', 'claude = [ "astra" ,\t"gemini" ] # keep')
    assert set_route(spaced, "claude", ["astra", "gemini"]) == spaced
    started = time.monotonic()
    assert not editable('[routes]\nclaude = [' + '"a" ' * 5000 + '!')
    assert time.monotonic() - started < 1, "the route pattern backtracks"
    # Review round 2 of D00 T01 §4: a removed line's trailing comment stays, and an insert after a last line with no
    # final newline still starts its own line.
    noted = cases(shipped)[1][3].replace('effort = "low"', 'effort = "low" # retained operator note')
    assert "\n# retained operator note\n" in set_field(noted, "mini", "effort", None), "field comment dropped"
    routed = shipped.replace('gemini = ["astra", "sonnet"]', 'gemini = ["astra", "sonnet"] # kept')
    assert routed.endswith("# kept\n") and remove_route(routed, "gemini").endswith("# kept\n"), "route comment dropped"
    bare = 'schema_version = 1\n[routes]\n[reviewers.mini]\ncli = "agy"\nmodel = "gemini-4-argon-low"'
    assert editable(bare)
    moved = set_field(set_field(bare, "mini", "cli", "codex"), "mini", "model", "gpt-6-mini")
    assert set_field(moved, "mini", "effort", "low").endswith('model = "gpt-6-mini"\neffort = "low"\n'), "joined lines"
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, what, before, after in cases(shipped):
            for label, text in (("before", before), ("after", after)):
                path = Path(tmp) / f"{name}-{label}.toml"
                path.write_bytes(text.encode("utf-8"))
                try:
                    check(path)
                except Refused as exc:
                    failed += 1
                    print(f"{name} ({label}) refused: {exc}", file=sys.stderr)
            comments = lambda t: [l for l in t.splitlines() if l.lstrip().startswith("#")]
            lost = [c for c in comments(before) if c not in comments(after)]
            if "--diff" in sys.argv:
                print(f"### {name}: {what}" + (f" (comments removed: {len(lost)})" if lost else ""))
                print("".join(difflib.unified_diff(lines_of(before), lines_of(after), "before", "after", n=1)))
            crlf = after.replace("\n", "\r\n")
            assert cases(shipped.replace("\n", "\r\n"))[[c[0] for c in cases(shipped)].index(name)][3] == crlf, name
    print(f"{len(cases(shipped))} edits, {failed} refused by load_pin", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
