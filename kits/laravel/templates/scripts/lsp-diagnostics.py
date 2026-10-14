#!/usr/bin/env python3
"""Run a language server over a set of files and report its diagnostics.

Ported from jmr-online (laravel, tailwind and php clients) into
`kits/laravel`. Stdlib only. Read-only: it opens documents in the
server's memory and never writes to the repository.

**Why a runner wants a language server at all.** Completions and hovers are
editor affordances and a runner has no cursor. Diagnostics are the part that
transfers: each server resolves a class of defect the rest of this stack
cannot see.

  laravel   string-keyed edges. A route, config key, view, env var,
            middleware alias, or policy ability that does not exist. PHPStan
            cannot see them because they are strings, and Pest catches one
            only if a test happens to execute that line.
  tailwind  class conflicts. Two utilities on one element that set the same
            CSS property, so which one wins depends on stylesheet order
            rather than on intent. Nothing else here looks at that.
  php       Intelephense. ON DEMAND, never a gate: measured on 2026-08-22 as
            a strict subset of PHPStan level 6 plus Pint, except for unused
            local variables. The measurement is in the SERVERS table.

All three boot or index the LOCAL application, so nothing they report is
evidence about production.

Usage:
  python3 scripts/lsp-diagnostics.py --server laravel --staged
  python3 scripts/lsp-diagnostics.py --server tailwind --commit <sha>
  python3 scripts/lsp-diagnostics.py --all --staged
  python3 scripts/lsp-diagnostics.py --server laravel path/to/File.php
  python3 scripts/lsp-diagnostics.py --all --staged --json

Exit codes:
  0  no diagnostics at or above the threshold (or nothing to inspect)
  1  diagnostics found
  2  bad usage
  3  every requested server is missing or unresponsive
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def discover_app_root(repo: Path) -> Path:
    """The Laravel app is the directory that contains `artisan`."""
    if (repo / "artisan").is_file():
        return repo
    nested = repo / "platform"
    if (nested / "artisan").is_file():
        return nested
    if repo.is_dir():
        for child in sorted(p for p in repo.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if (child / "artisan").is_file():
                return child
    return repo


APP_ROOT = discover_app_root(ROOT)

SEVERITY = {1: "error", 2: "warning", 3: "information", 4: "hint"}
SEVERITY_RANK = {"error": 1, "warning": 2, "information": 3, "hint": 4}
class Client:
    """A minimal LSP stdio client: enough to open documents and read back."""

    def __init__(
        self,
        binary: str,
        root: Path,
        verbose: bool = False,
        extra_args: list[str] | None = None,
        configuration: dict | None = None,
    ) -> None:
        self.configuration = configuration
        self.proc = subprocess.Popen(
            [binary, *(extra_args or [])],
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL if not verbose else None,
        )
        self.root = root
        self.verbose = verbose
        self._id = 0
        self._lock = threading.Lock()
        self.diagnostics: dict[str, list[dict]] = {}
        self.responses: dict[int, dict] = {}
        self._alive = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # ---------------------------------------------------------------- io

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        assert self.proc.stdin is not None
        with self._lock:
            try:
                self.proc.stdin.write(header + body)
                self.proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                self._alive = False

    def _read_loop(self) -> None:
        stream = self.proc.stdout
        assert stream is not None
        while True:
            length = 0
            while True:
                line = stream.readline()
                if not line:
                    self._alive = False
                    return
                line = line.strip()
                if not line:
                    break
                if line.lower().startswith(b"content-length:"):
                    try:
                        length = int(line.split(b":", 1)[1])
                    except ValueError:
                        length = 0
            if not length:
                continue
            raw = stream.read(length)
            if not raw:
                self._alive = False
                return
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        method = msg.get("method")
        if method == "textDocument/publishDiagnostics":
            params = msg.get("params") or {}
            uri = params.get("uri") or ""
            self.diagnostics[uri] = params.get("diagnostics") or []
            return
        # Server-to-client requests must be answered or the server may block.
        #  is not optional for Tailwind: without a
        # real settings object back it registers no linting at all, which
        # would make this whole tool silently green.
        if method and "id" in msg:
            result = None
            if method == "workspace/configuration":
                items = (msg.get("params") or {}).get("items") or [{}]
                result = [self._config_for(i.get("section")) for i in items]
            elif method in ("window/workDoneProgress/create", "client/registerCapability"):
                result = None
            self._send({"jsonrpc": "2.0", "id": msg["id"], "result": result})
            return
        if "id" in msg and method is None:
            self.responses[msg["id"]] = msg

    def _config_for(self, section: str | None):
        """Answer one workspace/configuration item from this server's settings."""
        cfg = self.configuration or {}
        if not section:
            return cfg
        node = cfg
        for part in section.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    # ------------------------------------------------------------ protocol

    def request(self, method: str, params: dict, timeout: float = 60.0) -> dict | None:
        self._id += 1
        rid = self._id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if rid in self.responses:
                return self.responses.pop(rid)
            if not self._alive:
                return None
            time.sleep(0.02)
        return None

    def notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def initialize(self, options: dict, timeout: float) -> bool:
        result = self.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": self.root.as_uri(),
                "rootPath": str(self.root),
                "workspaceFolders": [
                    {"uri": self.root.as_uri(), "name": self.root.name}
                ],
                "clientInfo": {"name": "conclave-lsp-diagnostics", "version": "1"},
                "initializationOptions": options,
                "capabilities": {
                    "textDocument": {
                        "publishDiagnostics": {"relatedInformation": True},
                        "synchronization": {"dynamicRegistration": False},
                    },
                    "workspace": {
                        "workspaceFolders": True,
                        "configuration": True,
                        "didChangeConfiguration": {"dynamicRegistration": True},
                    },
                    "window": {"workDoneProgress": True},
                },
            },
            timeout=timeout,
        )
        if result is None:
            return False
        self.notify("initialized", {})
        return True

    def open(self, path: Path, language: str) -> str:
        uri = path.as_uri()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return uri
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language,
                    "version": 1,
                    "text": text,
                }
            },
        )
        return uri

    def close(self) -> None:
        try:
            self.request("shutdown", {}, timeout=5.0)
            self.notify("exit", {})
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass




# ---------------------------------------------------------------- servers
#
# One entry per language server. `configuration` answers the server's own
# `workspace/configuration` requests: Tailwind will not lint at all without
# one, which is the difference between this table and a plain binary name.


def language_for(path: Path) -> str | None:
    name = path.name
    if name.endswith(".blade.php"):
        return "blade"
    if name.endswith(".php"):
        return "php"
    if name.endswith(".css"):
        return "css"
    return None


TAILWIND_SETTINGS = {
    "tailwindCSS": {
        "validate": True,
        "lint": {
            # The one that earns this server's place. Two utilities setting
            # the same property on one element is a real defect and nothing
            # else in this repository looks for it.
            "cssConflict": "warning",
            "invalidApply": "error",
            "invalidScreen": "error",
            "invalidVariant": "error",
            "invalidConfigPath": "error",
            "invalidTailwindDirective": "error",
            "recommendedVariantOrder": "warning",
            # OFF, measured 2026-08-22: these are style suggestions, not
            # defects -- `start-3` "can be written as" `inset-s-3`,
            # `max-h-[360px]` as `max-h-90`. Five of the fourteen findings in
            # the first sweep were this, and a gate that reports preferences
            # trains its reader to skim it.
            "suggestCanonicalClasses": "ignore",
        },
        # Blade is HTML as far as class attributes are concerned, and the
        # server has no Blade mode of its own.
        "includeLanguages": {"blade": "html", "php": "html"},
        # NO custom classRegex, and that is a measured decision. An
        # `@class([...])` array was tried on 2026-08-22 and produced pure
        # false positives: its entries are MUTUALLY EXCLUSIVE conditional
        # branches, so flattening the array into one string makes the server
        # see amber + red + green on one element and report three conflicts
        # in correct code (`quote-load.blade.php:81`). Blade's conditional
        # class helpers cannot be conflict-linted by flattening; the plain
        # `class="..."` attribute the server already understands can.
        "emmetCompletions": False,
        "showPixelEquivalents": True,
    },
    "editor": {"tabSize": 4},
}

SERVERS: dict[str, dict] = {
    "laravel": {
        "binary": "laravel-lsp",
        "args": [],
        "root": APP_ROOT,
        "requires": APP_ROOT / "artisan",
        "languages": ("php", "blade"),
        "install": "composer global require laravel/lsp",
        # MEASURED 2026-08-22: the server reports "Route [x] not found" at
        # severity WARNING, never error. A threshold of `error` would never
        # fire on the findings this server exists for.
        "severity": "warning",
        "init": {
            "phpEnvironment": "local",
            "phpCommand": ["php"],
            # Never let a diagnostics run write into the repository.
            "pestGenerateDocBlocks": False,
        },
        "configuration": None,
        "settle": 8.0,
        "note": (
            "string-keyed edges: route, config, view, env, middleware, policy. "
            "Does NOT diagnose a missing Blade component, and an interpolated "
            "name is a known false positive."
        ),
    },
    "tailwind": {
        "binary": "tailwindcss-language-server",
        "args": ["--stdio"],
        "root": APP_ROOT,
        "requires": APP_ROOT / "resources" / "css" / "app.css",
        "languages": ("blade", "css", "php"),
        "install": "npm install -g @tailwindcss/language-server",
        "severity": "warning",
        "init": {"userLanguages": {"blade": "html"}},
        "configuration": TAILWIND_SETTINGS,
        "settle": 6.0,
        "note": (
            "class conflicts: two utilities on one element setting the same "
            "property, so stylesheet order decides the winner rather than intent."
        ),
    },
    "php": {
        "binary": "intelephense",
        "args": ["--stdio"],
        "root": APP_ROOT,
        "requires": APP_ROOT / "composer.json",
        "languages": ("php",),
        "install": "npm install -g intelephense",
        # ON DEMAND ONLY -- deliberately NOT a gate, on measurement.
        #
        # Probe file with an undefined function, variable, constant, and class,
        # plus an unused import and an unused local (2026-08-22):
        #
        #   PHPStan level 6   5 findings (the 4 undefined symbols, plus an
        #                     expression whose result is unused)
        #   Intelephense      4 errors -- a strict SUBSET of PHPStan's -- and
        #                     2 hints: the unused import and the unused local
        #   Pint              already fixes the unused import; `no_unused_imports`
        #                     is explicitly enabled in platform/pint.json and
        #                     Pint is already a pre-push gate
        #
        # So the only finding Intelephense adds to this repository is an unused
        # LOCAL VARIABLE, and it costs ~2.5 minutes of workspace indexing to
        # get there. That does not earn a place in pre-push. The better route
        # to that one gap is raising PHPStan's level, which phpstan.neon
        # already tells us to do deliberately.
        #
        # It stays in this table because on-demand it is still useful on a
        # single unfamiliar file, and because the measurement above should be
        # re-runnable rather than re-argued. Use `--server php --severity hint`.
        "severity": "error",
        "init": {
            "storagePath": None,  # filled in at runtime: a temp dir, never the repo
            "clearCache": False,
        },
        "configuration": {
            "intelephense": {
                "files": {
                    "maxSize": 3000000,
                    "exclude": [
                        "**/node_modules/**",
                        "**/bower_components/**",
                        "**/vendor/**/{Tests,tests}/**",
                        "**/.git/**",
                    ],
                },
                "diagnostics": {
                    "enable": True,
                    # Off: Larastan owns these and says more about them.
                    "typeErrors": False,
                    "argumentCount": True,
                    "undefinedTypes": True,
                    "undefinedFunctions": True,
                    "undefinedConstants": True,
                    "undefinedClassConstants": True,
                    "undefinedMethods": True,
                    "undefinedProperties": False,
                    "undefinedVariables": True,
                    "unusedSymbols": True,
                    "unexpectedTokens": True,
                    "duplicateSymbols": True,
                    "deprecated": True,
                },
            }
        },
        "settle": 10.0,
        "note": (
            "ON DEMAND, not a gate: measured as a subset of PHPStan level 6 plus "
            "Pint, except unused local variables. See the note in SERVERS."
        ),
    },
}


# ---------------------------------------------------------------- inputs


def run_git(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            args, cwd=str(ROOT), text=True, capture_output=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout


def input_paths(args: argparse.Namespace) -> list[Path]:
    if args.staged:
        raw = run_git(["git", "diff", "--cached", "--name-only", "--diff-filter=d"])
    elif args.commit:
        raw = run_git(
            ["git", "show", "--name-only", "--pretty=", "--diff-filter=d", args.commit]
        )
    elif args.worktree:
        raw = run_git(["git", "diff", "--name-only", "--diff-filter=d"])
    else:
        raw = "\n".join(args.paths)
    out: list[Path] = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        p = (ROOT / line).resolve()
        if not p.is_file():
            continue
        try:
            p.relative_to(APP_ROOT)
        except ValueError:
            continue
        if language_for(p):
            out.append(p)
    return out


# ---------------------------------------------------------------- one server


def run_server(name: str, spec: dict, paths: list[Path], args) -> dict:
    """Returns {status, rows, unanswered, files}. status: ok | missing | dead | idle."""
    binary = shutil.which(spec["binary"])
    if not binary:
        return {"status": "missing", "rows": [], "unanswered": [], "files": 0}
    if spec["requires"] and not Path(spec["requires"]).exists():
        return {"status": "missing", "rows": [], "unanswered": [], "files": 0}

    mine = [p for p in paths if language_for(p) in spec["languages"]]
    if not mine:
        return {"status": "idle", "rows": [], "unanswered": [], "files": 0}

    init = dict(spec["init"])
    if name == "php":
        # Never let the index land in the repository.
        init["storagePath"] = str(
            Path(os.environ.get("TMPDIR", "/tmp")) / "conclave-intelephense-index"
        )

    client = Client(
        binary,
        Path(spec["root"]),
        verbose=args.verbose,
        extra_args=spec["args"],
        configuration=spec["configuration"],
    )
    try:
        if not client.initialize(init, timeout=min(90.0, args.timeout)):
            return {"status": "dead", "rows": [], "unanswered": [], "files": len(mine)}
        if spec["configuration"]:
            client.notify(
                "workspace/didChangeConfiguration",
                {"settings": spec["configuration"]},
            )

        uris: dict[str, Path] = {}
        for p in mine:
            lang = language_for(p)
            uris[client.open(p, lang)] = p

        settle = args.settle if args.settle is not None else spec["settle"]
        deadline = time.monotonic() + args.timeout
        answered_at: float | None = None
        while time.monotonic() < deadline:
            if not client._alive:
                break
            if all(u in client.diagnostics for u in uris):
                if answered_at is None:
                    answered_at = time.monotonic()
                elif time.monotonic() - answered_at >= settle:
                    break
            time.sleep(0.2)

        collected = {u: list(client.diagnostics.get(u, [])) for u in uris}
        unanswered = [uris[u] for u in uris if u not in client.diagnostics]
    finally:
        client.close()

    rows = []
    for uri, diags in collected.items():
        rel = str(uris[uri].relative_to(ROOT))
        for d in diags:
            sev = SEVERITY.get(d.get("severity") or 1, "error")
            rng = (d.get("range") or {}).get("start") or {}
            rows.append(
                {
                    "server": name,
                    "file": rel,
                    "line": rng.get("line", 0) + 1,
                    "column": rng.get("character", 0) + 1,
                    "severity": sev,
                    "code": str(d.get("code") or ""),
                    "message": (d.get("message") or "").replace("\n", " ").strip(),
                }
            )
    return {
        "status": "ok",
        "rows": rows,
        "unanswered": [str(p.relative_to(ROOT)) for p in unanswered],
        "files": len(mine),
    }


# ---------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="lsp-diagnostics.py", description=__doc__)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--server", action="append", choices=tuple(SERVERS), default=None)
    ap.add_argument("--all", action="store_true", help="every server in the table")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--worktree", action="store_true")
    ap.add_argument("--commit")
    ap.add_argument(
        "--severity",
        default=None,
        choices=("error", "warning", "information", "hint"),
        help="override the per-server threshold (see SERVERS in the source)",
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--settle", type=float, default=None)
    ap.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("LSP_DIAGNOSTICS_TIMEOUT", "240")),
    )
    args = ap.parse_args(argv[1:])

    wanted = list(SERVERS) if args.all else (args.server or ["laravel"])

    paths = input_paths(args)
    if not paths:
        print("lsp-diagnostics: no PHP, Blade, or CSS files under the Laravel app root in the input.")
        return 0

    results = {}
    for name in wanted:
        results[name] = run_server(name, SERVERS[name], paths, args)

    all_rows = [r for res in results.values() for r in res["rows"]]
    failing = []
    for r in all_rows:
        threshold = args.severity or SERVERS[r["server"]]["severity"]
        if SEVERITY_RANK[r["severity"]] <= SEVERITY_RANK[threshold]:
            failing.append(r)
    all_rows.sort(key=lambda r: (r["server"], SEVERITY_RANK[r["severity"]], r["file"], r["line"]))

    if args.json:
        print(
            json.dumps(
                {
                    "servers": {
                        k: {
                            "status": v["status"],
                            "files": v["files"],
                            "unanswered": v["unanswered"],
                        }
                        for k, v in results.items()
                    },
                    "diagnostics": all_rows,
                    "failing": len(failing),
                },
                indent=2,
            )
        )
        return 1 if failing else 0

    for r in all_rows:
        code = f" [{r['code']}]" if r["code"] else ""
        print(
            f"{r['server']:9} {r['file']}:{r['line']}:{r['column']}  "
            f"{r['severity']:11} {r['message']}{code}"
        )

    print()
    live = 0
    for name in wanted:
        res = results[name]
        spec = SERVERS[name]
        if res["status"] == "missing":
            # Silence from a server nobody installed must never read as a pass.
            print(
                f"{name:9} SKIPPED -- not installed. Install: {spec['install']}",
                file=sys.stderr,
            )
            continue
        if res["status"] == "dead":
            print(f"{name:9} FAILED -- did not answer initialize", file=sys.stderr)
            continue
        if res["status"] == "idle":
            print(f"{name:9} no files of its kind in this input")
            live += 1
            continue
        live += 1
        n = len([r for r in res["rows"]])
        print(f"{name:9} {res['files']} file(s), {n} diagnostic(s). {spec['note']}")
        if res["unanswered"]:
            print(
                f"{name:9} {len(res['unanswered'])} file(s) never answered "
                f"(raise --timeout/--settle): {', '.join(res['unanswered'])}",
                file=sys.stderr,
            )

    if live == 0:
        return 3

    print(f"\nlsp-diagnostics: {len(failing)} diagnostic(s) at or above threshold.")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
