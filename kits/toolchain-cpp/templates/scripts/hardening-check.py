#!/usr/bin/env python3
"""Say whether the project's own compile commands carry the memory-safety hardening its pin file declares.

    python scripts/hardening-check.py [--root <project>] [--pins <pin file>] [--json]

The policy is the `hardening` key of `.conclave/toolchain-cpp.json`, which scripts/toolchain-check.py loads:

    "hardening": {"compile": ["_MSVC_STL_HARDENING=1", "/guard:cf"], "sources": ["src"], "exclude": ["src/vendor"]}

`compile` lists definitions (`NAME`, met by any value, or `NAME=VALUE`, met by that value only) and options (they
start with `-` or `/`). Every entry of the compile database whose source file is under one of `sources` (folders
under the pin file's `root`, `.` when left out) and under none of `exclude` must carry each of them; the other
entries are counted, never checked. A project with no `hardening` key gets no finding: the kit never chooses a
project's flags.

How an entry is read, as the compiler would read it:

- its `arguments`, or its `command` split by Windows rules when its `directory` is a Windows path (a drive letter
  or a backslash) and by POSIX rules otherwise;
- an `@file` argument is replaced by that response file (relative to `directory`, at most 1 MiB, UTF-8 or UTF-16
  with a byte order mark, split by the same rules); one that cannot be read faithfully, or that names a response
  file itself, makes the result `unknown`, never a guess;
- a definition is met by `-DNAME[=VALUE]` or `-D NAME[=VALUE]`, and on an MSVC-style entry (its compiler, after a
  `ccache` or `sccache` launcher, is `cl` or `clang-cl`, wherever it runs) by `/DNAME[=VALUE]` or `/D NAME[=VALUE]` too (`#` standing for `=` there,
  as cl reads it); `-DNAME` is `NAME=1`;
- an option is met by the same argument, and on an MSVC-style entry a `/` option by its `-` spelling too;
- only what the compiler itself reads counts: nothing after cl's `/link`, no `-Wl,`, `-Wa,` or `-Wp,` argument, and
  no value of an option that takes the next argument (`-Xlinker`, `-Xclang`, `-o`, `-I` and the like);
- the last occurrence wins: a later `-UNAME`, `-U NAME`, `/UNAME`, `/U NAME` or other value undoes a definition, and
  the `-fno-` form of an `-f` option, `/option-` or another value of a `-name=value` option undoes an option;
- option families are read as GCC and Clang read them: the last stack protector option sets the level, and a
  stronger level meets a weaker requirement (`-fstack-protector-all` meets `-fstack-protector-strong`, a later
  `-fno-stack-protector` undoes both); the values of `-fsanitize=` add up and `-fno-sanitize=` takes them away;
  `-fcf-protection` is `-fcf-protection=full`.

It prints one line with the status, then one line per requirement (`ok`, or `missing` with how many entries lack
it and the first of them). The status is `ok`; `missing` (exit 3); `unknown` (exit 1) when the database is not
`current` by scripts/compdb-check.py (stale, missing, invalid or too large: its detail and its regenerate line are
printed), a response file or command cannot be read faithfully, or no entry falls under the policy's sources;
`none` (exit 0) when no policy is declared. It exits 2 for bad usage or a pin file that does not load. `--json`
prints the loaded policy and the result as one document. It reads and reports: it writes nothing and runs nothing.
Standard library only.
"""
import argparse
import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path

PINS = ".conclave/toolchain-cpp.json"
RESPONSE_LIMIT = 1024 * 1024   # bytes of one response file this check reads
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
WINDOWS_DIRECTORY = re.compile(r"^[A-Za-z]:[\\/]|\\")
MSVC_DRIVERS = {"cl", "clang-cl"}   # compilers that read / options wherever they run
LAUNCHERS = {"ccache", "sccache"}   # a compiler cache named before the compiler
EXIT = {"ok": 0, "none": 0, "unknown": 1, "missing": 3}


def _sibling(name, module_name):
    """A script beside this one, loaded as a module: the kit's one implementation of what it owns."""
    path = Path(__file__).resolve().parent / name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Unreadable(ValueError):
    """An entry whose flags cannot be read faithfully: the message says which file and why."""


def split_windows(line):
    """A command line split as the Microsoft C runtime splits it (the rules CommandLineToArgvW follows, with the
    `""` inside quotes of the 2008 runtime). Raises Unreadable for a quote left open."""
    arguments, current, quoted, started, i = [], [], False, False, 0
    while i < len(line):
        char = line[i]
        if char == "\\":
            slashes = 0
            while i < len(line) and line[i] == "\\":
                slashes, i = slashes + 1, i + 1
            if i < len(line) and line[i] == '"':
                current.append("\\" * (slashes // 2))
                if slashes % 2:
                    current.append('"')
                    i += 1
                started = True
                continue
            current.append("\\" * slashes)
            started = True
            continue
        if char == '"':
            if quoted and i + 1 < len(line) and line[i + 1] == '"':
                current.append('"')
                i += 2
                continue
            quoted, started, i = not quoted, True, i + 1
            continue
        if char in " \t\r\n" and not quoted:
            if started:
                arguments.append("".join(current))
                current, started = [], False
            i += 1
            continue
        current.append(char)
        started, i = True, i + 1
    if quoted:
        raise Unreadable("a quote is left open")
    if started:
        arguments.append("".join(current))
    return arguments


def split_line(line, windows):
    if windows:
        return split_windows(line)
    try:
        return shlex.split(line, posix=True)
    except ValueError as exc:
        raise Unreadable(f"it cannot be split as a POSIX command line ({exc})") from exc


def _decode(raw):
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


def entry_arguments(entry, directory, windows, shown):
    """The arguments an entry compiles with, response files read in place. Raises Unreadable."""
    if "arguments" in entry:
        arguments = list(entry["arguments"])
    else:
        try:
            arguments = split_line(entry["command"], windows)
        except Unreadable as exc:
            raise Unreadable(f"the command of {shown}: {exc}") from exc
    expanded = []
    for argument in arguments:
        if not (argument.startswith("@") and len(argument) > 1):
            expanded.append(argument)
            continue
        name = argument[1:]
        path = Path(name) if Path(name).is_absolute() else directory / name
        where = f"response file {name} of {shown}"
        try:
            with open(path, "rb") as handle:
                raw = handle.read(RESPONSE_LIMIT + 1)
        except OSError as exc:
            raise Unreadable(f"{where} cannot be read ({exc.strerror or exc})") from exc
        if len(raw) > RESPONSE_LIMIT:
            raise Unreadable(f"{where} is larger than the {RESPONSE_LIMIT} bytes this check reads")
        try:
            text = _decode(raw)
        except UnicodeDecodeError as exc:
            raise Unreadable(f"{where} is neither UTF-8 nor UTF-16 with a byte order mark ({exc.reason})") from exc
        try:
            inner = split_line(text, windows)
        except Unreadable as exc:
            raise Unreadable(f"{where}: {exc}") from exc
        nested = [item for item in inner if item.startswith("@") and len(item) > 1]
        if nested:
            raise Unreadable(f"{where} names a response file itself ({nested[0]}), which this check does not follow")
        expanded.extend(inner)
    return expanded


def _definition(text, windows_form):
    """(NAME, VALUE) from the text after -D, or None when it names no macro."""
    if windows_form and "#" in text and "=" not in text:
        text = text.replace("#", "=", 1)
    name, equals, value = text.partition("=")
    if not IDENTIFIER.fullmatch(name):
        return None
    return name, (value if equals else "1")


# Options whose next argument is their value, never a flag of the compiler's own: that value is skipped, so a
# `-Xlinker -D_GLIBCXX_ASSERTIONS` (passed to the linker) or an `-o /guard:cf` meets nothing.
TAKES_VALUE = {"-o", "-x", "-I", "-L", "-l", "-MF", "-MT", "-MQ", "-MJ", "-include", "-imacros", "-isystem",
               "-iquote", "-idirafter", "-iprefix", "-iwithprefix", "-isysroot", "--sysroot", "-target", "--target",
               "-arch", "-Xlinker", "-Xassembler", "-Xpreprocessor", "-Xclang", "-mllvm", "-Xopenmp-target", "-z",
               "-T", "-u", "-e", "-aux-info", "-dumpdir", "-dumpbase", "--param"}
MSVC_TAKES_VALUE = {"/I", "-I", "/FI", "-FI", "/AI", "-AI", "/FU", "-FU", "/external:I", "-external:I", "/Tc", "/Tp"}
# The stack protector's levels, as GCC and Clang read them: the last of the family sets the level.
STACK_PROTECTOR = {"-fno-stack-protector": 0, "-fstack-protector-explicit": 1, "-fstack-protector": 2,
                   "-fstack-protector-strong": 3, "-fstack-protector-all": 4}
# A bare option that means one value of its `=` family.
ALIASES = {"-fcf-protection": "-fcf-protection=full"}
# Options whose values add up rather than replace each other, with the option that takes values away.
LISTS = {"-fsanitize=": "-fno-sanitize=", "-fsanitize-trap=": "-fno-sanitize-trap=",
         "-fsanitize-recover=": "-fno-sanitize-recover="}


def compiler_arguments(arguments, msvc):
    """The arguments the compiler itself reads, in order, without the compiler: a separated `-D NAME` or `-U NAME`
    (and `/D`, `/U` on an MSVC-style entry) joined into one, each option's own value skipped, a `-Wl,` or `-Wa,`
    argument (the linker's or the assembler's) left out, and nothing after cl's `/link` (the linker's)."""
    owned, i = [], 1
    while i < len(arguments):
        argument = arguments[i]
        if msvc and argument.lower() in ("/link", "-link"):
            break
        joined = ("-D", "-U") + (("/D", "/U") if msvc else ())
        if argument in joined:
            if i + 1 < len(arguments):
                owned.append(argument + arguments[i + 1])
            i += 2
            continue
        if argument in TAKES_VALUE or (msvc and argument in MSVC_TAKES_VALUE) or argument.startswith("-Xarch_"):
            i += 2
            continue
        if not argument.startswith(("-Wl,", "-Wa,", "-Wp,")):
            owned.append(argument)
        i += 1
    return owned


def _definition_state(owned, name, msvc):
    defined = None
    for argument in owned:
        head = argument[:2]
        if head == "-U" or (msvc and head == "/U"):
            if argument[2:] == name:
                defined = None
        elif head == "-D" or (msvc and head == "/D"):
            parsed = _definition(argument[2:], head == "/D")
            if parsed and parsed[0] == name:
                defined = parsed[1]
    return defined


def _canonical(argument, msvc):
    """One spelling of an option: cl's `-` form as its `/` form, and a bare alias as its `=` value."""
    if msvc and argument.startswith("-") and not argument.startswith("--"):
        slash = "/" + argument[1:]
        if not argument.startswith(("-f", "-m", "-D", "-U", "-I", "-X")):
            argument = slash
    return ALIASES.get(argument, argument)


def _option_state(owned, requirement, msvc):
    """Whether the option `requirement` is in force after the arguments the compiler reads, under the option
    families GCC, Clang and cl apply: the stack protector's levels (a stronger level meets a weaker requirement),
    list options whose values add up (`-fsanitize=`), `-name=value` options whose last value wins, `-fname` against
    `-fno-name`, and cl's `/option` against `/option-`."""
    wanted = _canonical(requirement, msvc)
    if wanted in STACK_PROTECTOR:
        level = 0
        for argument in owned:
            level = STACK_PROTECTOR.get(argument, level)
        required = STACK_PROTECTOR[wanted]
        return level == 0 if required == 0 else level >= required
    for adds, takes in LISTS.items():
        if wanted.startswith(adds):
            values = set()
            for argument in owned:
                if argument.startswith(adds):
                    values |= set(argument[len(adds):].split(","))
                elif argument.startswith(takes):
                    values -= set(argument[len(takes):].split(","))
            return set(wanted[len(adds):].split(",")) <= values
    family = wanted.split("=", 1)[0] if wanted.startswith("-") and "=" in wanted else None
    state = False
    for argument in owned:
        spelled = _canonical(argument, msvc)
        if spelled == wanted:
            state = True
        elif family and spelled.startswith(family + "="):
            state = False   # another value of the same option
        elif wanted.startswith("-fno-") and spelled == "-f" + wanted[5:]:
            state = False
        elif wanted.startswith("-f") and spelled in ("-fno-" + wanted[2:], "-fno-" + (family or wanted)[2:]):
            state = False
        elif msvc and wanted[0] == "/" and spelled == wanted + "-":
            state = False
    return state


def carries(arguments, requirement, msvc):
    """Whether a compile command's arguments (the compiler first) leave `requirement` in force at their end, as
    the compiler reads them (compiler_arguments)."""
    owned = compiler_arguments(arguments, msvc)
    if requirement[:2] in ("-D", "/D") and _definition(requirement[2:], requirement[0] == "/"):
        requirement = requirement[2:]   # a definition written with its option: held to the same rules
    if requirement[0] in "-/":
        return _option_state(owned, requirement, msvc)
    name, value = _definition(requirement, False)
    defined = _definition_state(owned, name, msvc)
    return defined is not None and ("=" not in requirement or defined == value)


def _key(path):
    return os.path.normcase(os.path.normpath(str(path)))


def _under(path_key, folder_key):
    return path_key == folder_key or path_key.startswith(folder_key.rstrip(os.sep) + os.sep)


def _program(argument):
    name = re.split(r"[\\/]", argument)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def msvc_style(arguments):
    """Whether an entry's compiler reads `/` options: cl or clang-cl, after any compiler cache launcher. A MinGW
    compiler on Windows takes `/DNAME` for a file, so the system the entry ran on does not decide it."""
    programs = [_program(argument) for argument in arguments]
    while programs and programs[0] in LAUNCHERS:
        programs.pop(0)
    return bool(programs) and programs[0] in MSVC_DRIVERS


def check_hardening(project, pin_file, compdb, read_limit=None):
    """The result of the policy of a loaded pin file against its compile database: {"status", "detail",
    "database", "checked", "excluded", "outside", "requirements", "regenerate"}. `compdb` is the loaded
    compdb-check module."""
    project = Path(project).resolve()
    policy = pin_file["hardening"]
    result = {"status": None, "detail": "", "database": None, "checked": 0, "excluded": 0, "outside": 0,
              "requirements": [], "regenerate": None}
    if policy is None:
        result.update(status="none", detail="no policy declared: add a `hardening` key to the pin file "
                                             "(docs/toolchain-cpp.md, Memory safety)")
        return result
    entries = []
    state = compdb.check_database(project, pin_file, entries_out=entries,
                                  read_limit=compdb.READ_LIMIT if read_limit is None else read_limit)
    result["database"] = state["path"]
    if state["status"] != "current":
        result.update(status="unknown", detail=f"the compile database is {state['status']}, so the flags it "
                                               f"holds may not be the build's: {state['detail']}",
                      regenerate=compdb.regenerate_line(state))
        return result
    base = project / pin_file["root"]
    sources = [_key(base / folder) for folder in policy["sources"]]
    exclude = [_key(base / folder) for folder in policy["exclude"]]
    database = compdb.database_path(project, pin_file)
    lacking = {requirement: [] for requirement in policy["compile"]}
    for entry in entries:
        source = compdb.entry_source(entry, database)
        source_key = _key(source)
        if any(_under(source_key, folder) for folder in exclude):
            result["excluded"] += 1
            continue
        if not any(_under(source_key, folder) for folder in sources):
            result["outside"] += 1
            continue
        result["checked"] += 1
        shown = compdb._shown(Path(os.path.normpath(str(source))), project)
        windows = bool(WINDOWS_DIRECTORY.search(entry["directory"]))
        directory = Path(entry["directory"])
        if not directory.is_absolute():
            directory = database.parent / directory
        try:
            arguments = entry_arguments(entry, directory, windows, shown)
        except Unreadable as exc:
            result.update(status="unknown", detail=f"{exc}, so its flags cannot be told")
            return result
        forms = msvc_style(arguments)
        for requirement in policy["compile"]:
            if not carries(arguments, requirement, forms):
                lacking[requirement].append(shown)
    counted = f"{result['excluded']} excluded, {result['outside']} outside the sources"
    if not result["checked"]:
        result.update(status="unknown", detail=f"{state['path']}: no entry is under the policy's sources "
                                               f"({', '.join(policy['sources'])}), so nothing was checked; "
                                               f"{counted}")
        return result
    for requirement, missing in lacking.items():
        result["requirements"].append({"requirement": requirement, "status": "missing" if missing else "ok",
                                       "lacking": len(missing), "first": missing[0] if missing else None})
    short = [item for item in result["requirements"] if item["status"] == "missing"]
    checked = f"{result['checked']} first-party entr{'y' if result['checked'] == 1 else 'ies'}"
    if short:
        result.update(status="missing", detail=f"{state['path']}: {len(short)} of {len(lacking)} requirement(s) "
                                               f"missing on {checked}; {counted}")
    else:
        result.update(status="ok", detail=f"{state['path']}: {len(lacking)} requirement(s) on {checked}; "
                                          f"{counted}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hardening-check.py",
                                     description="Say whether the project's compile commands carry its declared "
                                                 "hardening. Runs nothing.")
    parser.add_argument("--root", default=".", help="the project (default: the working directory)")
    parser.add_argument("--pins", help=f"the pin file (default: {PINS} under the root)")
    parser.add_argument("--json", action="store_true", help="print the policy and the result as one JSON document")
    args = parser.parse_args(argv)
    project = Path(args.root).resolve()
    pins = Path(args.pins) if args.pins else project / PINS
    module = _sibling("toolchain-check.py", "_toolchain_check")
    try:
        pin_file = module.load_pin_file(pins)
    except module.PinError as exc:
        print(f"hardening-check: {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps({"policy": None, "status": "refused", "detail": str(exc)}, indent=2))
        return 2
    result = check_hardening(project, pin_file, _sibling("compdb-check.py", "_compdb_check"))
    if args.json:
        print(json.dumps({"policy": pin_file["hardening"], **result}, indent=2))
    else:
        print(f"hardening:compile: {result['status']}: {result['detail']}")
        for item in result["requirements"]:
            if item["status"] == "ok":
                print(f"  ok       {item['requirement']}")
            else:
                print(f"  missing  {item['requirement']}: on {item['lacking']} entr"
                      f"{'y' if item['lacking'] == 1 else 'ies'}, first {item['first']}")
        if result["regenerate"]:
            print(result["regenerate"])
    return EXIT[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
