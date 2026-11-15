#!/usr/bin/env python3
"""Put a compiler cache (ccache or sccache) in front of the compilers a build names.

    python scripts/cc-cache.py [--cache <name>] [--shell sh|powershell|cmd] [--root <project>] <compiler>...

A program cannot change its caller's `PATH`, so this writes the wrappers and prints the one statement that puts
them first on `PATH`, in the calling shell's form. A build script checks the exit before it evaluates the output:

    sh           setup=$(python3 scripts/cc-cache.py cc c++) || exit 1; eval "$setup"
    PowerShell   $setup = python scripts/cc-cache.py clang; if ($LASTEXITCODE) { exit 1 }; $setup | Invoke-Expression

For each compiler found on `PATH` it writes a wrapper of that name, which runs the cache with the real compiler's
full path and the arguments it was given, into a folder of this project's own under the user's cache folder
(`$XDG_CACHE_HOME` or `~/.cache`; `%LOCALAPPDATA%` on Windows). The cache is `--cache <name>`, else the first of
ccache and sccache on `PATH`; the folder records which, for `cache-stats.py`.

The folder is exactly what the last run decided: a wrapper this run did not write is removed. With
`BUILD_NO_CCACHE` set, or no cache installed, every wrapper is removed and the output is a comment, so evaluating
it changes nothing and a shell that already has the folder on `PATH` reaches the real compilers. A wrapper also
stands aside by itself when it runs with `BUILD_NO_CCACHE` set or with the cache's program gone.

Exit 0 also when there is nothing to wrap (a missing cache never breaks a build); 1 when a wrapper cannot be
written; 2 for a compiler name that is not a bare name or a path that cannot be written safely. Standard library
only.
"""
import argparse
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHES = ("ccache", "sccache")
OPT_OUT = "BUILD_NO_CCACHE"
CHOICE = "cache-choice"   # in the wrapper folder: the name and the path of the cache the wrappers run
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9+._-]*")
SHELLS = ("sh", "powershell", "cmd")


class Refused(Exception):
    """Something that ends the run with one line and exit 2."""


def cache_home(environ=None):
    """The user's cache folder."""
    environ = os.environ if environ is None else environ
    if os.name == "nt":
        return Path(environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return Path(environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def wrapper_folder(project, environ=None):
    """The folder a project's wrappers are kept in: its own, under the user's cache folder."""
    project = Path(project).resolve()
    return cache_home(environ) / "conclave" / "cc-cache" / hashlib.sha256(str(project).encode("utf-8")).hexdigest()[:12]


def _same(one, other):
    try:
        return os.path.samefile(one, other)
    except OSError:
        return os.path.normcase(os.path.abspath(one)) == os.path.normcase(os.path.abspath(other))


def find(name, skip=(), environ=None):
    """The program a bare name is on `PATH`, as a full path, or None. The folders in `skip` are left out (the
    wrapper folder, so a wrapper is never taken for the compiler it wraps), and the working directory is never
    tried, which on Windows the standard lookup tries first."""
    environ = os.environ if environ is None else environ
    windows = os.name == "nt"
    suffixes = [ext for ext in environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep) if ext] \
        if windows else []
    names = [name]
    if windows and Path(name).suffix.upper() not in {ext.upper() for ext in suffixes}:
        names = [name + ext for ext in suffixes]
    for folder in environ.get("PATH", "").split(os.pathsep):
        if not folder or any(_same(folder, other) for other in skip):
            continue
        for candidate in names:
            path = Path(folder) / candidate
            if path.is_file() and os.access(path, os.X_OK):
                return path.resolve()
    return None


def _sh(text):
    return "'" + str(text).replace("'", "'\"'\"'") + "'"


def _powershell(text):
    return "'" + str(text).replace("'", "''") + "'"


def _cmd_safe(path):
    """A path that can stand inside double quotes in a `.cmd` or a `set`: one holding `"` or `%` cannot."""
    if '"' in str(path) or "%" in str(path):
        raise Refused(f"{path} holds a character a cmd file cannot quote (\" or %)")
    return str(path)


def wrapper_text(cache, real, windows=None):
    """The wrapper that runs `real` through `cache`: the cache with the real compiler's full path and the
    arguments given. It stands aside (runs the compiler directly) with BUILD_NO_CCACHE set or the cache gone."""
    windows = os.name == "nt" if windows is None else windows
    if windows:
        cache, real = _cmd_safe(cache), _cmd_safe(real)
        return ("@echo off\r\n"
                "rem Written by scripts/cc-cache.py: runs this compiler through the compiler cache. Not for editing.\r\n"
                f"if defined {OPT_OUT} goto real\r\n"
                f'if not exist "{cache}" goto real\r\n'
                f'"{cache}" "{real}" %*\r\n'
                "exit /b %errorlevel%\r\n"
                ":real\r\n"
                f'"{real}" %*\r\n'
                "exit /b %errorlevel%\r\n")
    return ("#!/bin/sh\n"
            "# Written by scripts/cc-cache.py: runs this compiler through the compiler cache. Not for editing.\n"
            f'if [ -z "${{{OPT_OUT}:-}}" ] && [ -x {_sh(cache)} ]; then\n'
            f'    exec {_sh(cache)} {_sh(real)} "$@"\n'
            "fi\n"
            f'exec {_sh(real)} "$@"\n')


def statement(folder, shell):
    """The one statement that puts the wrapper folder first on `PATH`, for a shell."""
    if shell == "sh":
        return f'export PATH={_sh(folder)}:"$PATH"'
    if shell == "powershell":
        return f"$env:PATH = {_powershell(folder)} + [IO.Path]::PathSeparator + $env:PATH"
    return f'set "PATH={_cmd_safe(folder)};%PATH%"'


def comment(text, shell):
    """A line that changes nothing when the shell evaluates it."""
    return f"rem {text}" if shell == "cmd" else f"# {text}"


def _write(path, data, executable):
    """Write a file through a temporary file and a replacement, only when its content would change."""
    try:
        if path.is_file() and path.read_bytes() == data:
            return False
    except OSError:
        pass   # unreadable now: the write below reports what is wrong with it
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".cc-cache-", suffix=".tmp")
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if executable and os.name != "nt":
            os.chmod(temporary, 0o755)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
    return True


def _keep_only(folder, keep):
    """Remove every file of the wrapper folder this run did not write."""
    if not folder.is_dir():
        return
    for path in folder.iterdir():
        if path.name not in keep and (path.is_file() or path.is_symlink()):
            path.unlink()


def recorded_choice(project, environ=None):
    """The cache a project's wrappers run, as (name, path), or None when it has none."""
    try:
        name, path = (wrapper_folder(project, environ) / CHOICE).read_text(encoding="utf-8").splitlines()[:2]
    except (OSError, ValueError):
        return None
    return name, Path(path)


def main(argv=None, root=None):
    parser = argparse.ArgumentParser(prog="cc-cache.py",
                                     description="Put a compiler cache in front of the compilers a build names.")
    parser.add_argument("compilers", nargs="+", help="the compilers the build runs, by name")
    parser.add_argument("--cache", choices=CACHES, help="the cache to use (default: the first of ccache and sccache "
                                                        "on PATH)")
    parser.add_argument("--shell", choices=SHELLS, default="powershell" if os.name == "nt" else "sh",
                        help="the shell that will evaluate the output (default: the system's)")
    parser.add_argument("--root", help="the project (default: the folder above scripts/)")
    args = parser.parse_args(argv)
    project = Path(root or args.root or ROOT).resolve()
    folder = wrapper_folder(project)
    windows = os.name == "nt"
    try:
        for name in args.compilers:
            if not NAME.fullmatch(name):
                raise Refused(f"{name!r} is not a compiler's name (a bare name, as the build runs it)")
        off, cache = None, None
        if os.environ.get(OPT_OUT):
            off = f"{OPT_OUT} is set"
        else:
            wanted = (args.cache,) if args.cache else CACHES
            cache = next((found for found in (find(name, skip=[folder]) for name in wanted) if found), None)
            if cache is None:
                off = f"{args.cache} is not installed" if args.cache else \
                    f"no compiler cache is installed ({' or '.join(CACHES)})"
        wrappers, wrapped = {}, []
        if off is None:
            for name in args.compilers:
                real = find(name, skip=[folder])
                if real is None:
                    print(f"cc-cache: {name} is not installed: no wrapper for it", file=sys.stderr)
                    continue
                wrappers[name + ".cmd" if windows else name] = wrapper_text(cache, real, windows).encode("utf-8")
                wrapped.append(name)
            if not wrappers:
                off = "none of the compilers named is installed"
        if off is not None:
            _keep_only(folder, ())   # a shell that still has the folder on PATH reaches the real compilers
            print(comment(f"cc-cache: off: {off}", args.shell))
            print(f"cc-cache: off: {off}", file=sys.stderr)
            return 0
        line = statement(folder, args.shell)
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in wrappers.items():
            _write(folder / name, data, executable=True)
        name = "sccache" if cache.stem.lower().startswith("sccache") else "ccache"
        _write(folder / CHOICE, f"{name}\n{cache}\n".encode("utf-8"), executable=False)
        _keep_only(folder, {*wrappers, CHOICE})
    except Refused as exc:
        print(f"cc-cache: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cc-cache: {folder}: cannot be written ({exc.strerror or exc})", file=sys.stderr)
        return 1
    print(line)
    print(f"cc-cache: {name} in front of {', '.join(wrapped)} ({folder})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
