#!/usr/bin/env python3
"""Check and invoke this repository's Antigravity subagents on Gemini 4 Hydrogen medium.

Antigravity 1.5.8 loads workspace subagents from `.agents/agents/<name>.md`, but its agent frontmatter loader accepts
only the four tier tokens `inherit`, `flash_lite`, `flash` and `pro` in `model:` (skipping any file that writes a
concrete model ID there), while `invoke_subagent` maps `flash` and `pro` to `gemini-3.8-flash-tiered` and `inherit` to
the caller's Gemini 4 Carbon model. Each Conclave Antigravity subagent therefore declares `model: flash` (never
inheriting Carbon), `conclave_model: gemini-4-hydrogen-medium`, `subagent: true`, `mainAgent: true`,
`inheritMcp: false` and an explicit read-only `tools:` list, and this script both enforces that contract (`--check`)
and runs a named subagent on `gemini-4-hydrogen-medium` (`agy --model gemini-4-hydrogen-medium --agent <name>` with
the prompt piped on `stdin` via `--input-format text`).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

PINNED_MODEL = "gemini-4-hydrogen-medium"
LOADER_MODEL = "flash"
AGENT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REQUIRED_KEYS = (
    "name",
    "description",
    "model",
    "conclave_model",
    "subagent",
    "mainAgent",
    "inheritMcp",
    "tools",
)
WRITE_TOOLS = frozenset({"edit_file", "write_file"})
ALLOWED_TOOLS = frozenset({"read_file", "run_command", "manage_task", "search_web"})
BASE_SUBAGENT_TOOLS = ["read_file", "run_command", "manage_task"]
ROLE_TOOLS: dict[str, list[str]] = {
    "code-explorer": BASE_SUBAGENT_TOOLS,
    "debug-evidence": BASE_SUBAGENT_TOOLS,
    "git-runner": BASE_SUBAGENT_TOOLS,
    "mutation-tester": BASE_SUBAGENT_TOOLS,
    "test-runner": BASE_SUBAGENT_TOOLS,
}

CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


_WIN32 = None


def _win32_apis():
    global _WIN32
    if _WIN32 is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.TerminateJobObject.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
        ntdll.NtResumeProcess.restype = ctypes.c_int32
        _WIN32 = (kernel32, ntdll)
    return _WIN32


def _create_kill_on_close_job() -> int:
    kernel32, _ = _win32_apis()
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        job,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        kernel32.CloseHandle(job)
        raise ctypes.WinError(ctypes.get_last_error())
    return int(job)


def _assign_and_resume_windows(job: int, proc: subprocess.Popen[bytes]) -> None:
    kernel32, ntdll = _win32_apis()
    handle = ctypes.c_void_p(int(proc._handle))  # type: ignore[attr-defined]
    if not kernel32.AssignProcessToJobObject(job, handle):
        raise ctypes.WinError(ctypes.get_last_error())
    status = ntdll.NtResumeProcess(handle)
    if status != 0:
        raise OSError(f"NtResumeProcess returned 0x{status & 0xFFFFFFFF:08x}")


def _kill_tree(proc: subprocess.Popen[bytes] | None, job: int | None) -> None:
    """Terminate the subagent process and every surviving descendant, even if the leader has already exited."""
    if os.name == "nt":
        if job is not None:
            kernel32, _ = _win32_apis()
            kernel32.TerminateJobObject(job, 1)
            kernel32.CloseHandle(job)
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                pass
    elif proc is not None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc is not None:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _remove_scratch(path: Path, limit: float = 3.0) -> None:
    deadline = time.monotonic() + limit
    while True:
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if time.monotonic() >= deadline:
                return
            time.sleep(0.05)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".agy-subagent-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def parse_agent_markdown(text: str) -> tuple[list[tuple[str, str]] | None, str, str | None]:
    """Read opening YAML frontmatter as a strict closed subset; return (pairs, body, error)."""
    normalized = text.replace("\r\n", "\n")
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n(.*))?\Z", normalized, re.S)
    if match is None:
        return None, "", "has no opening frontmatter block"
    raw_front, body = match.group(1), match.group(2) or ""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw_line in raw_front.split("\n"):
        if raw_line.strip() == "" or re.match(r"^[ \t]*#", raw_line):
            continue
        if raw_line[:1] in (" ", "\t"):
            return None, "", f"frontmatter line {raw_line!r} is indented; nested YAML blocks are refused"
        entry = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+([^\n]*?))?[ \t]*$", raw_line)
        if entry is None:
            return None, "", f"frontmatter line {raw_line!r} is not a plain 'key: value' pair"
        key, rest = entry.group(1), entry.group(2) or ""
        if key in seen:
            return None, "", f"declares {key!r} more than once"
        seen.add(key)
        if rest == "":
            return None, "", f"{key!r} has an empty value"
        if key == "tools":
            cleaned = re.sub(r"[ \t]+#.*$", "", rest).strip()
            if cleaned[:1] in ("|", ">", "&", "*", "!", "{") or cleaned[:1] in ('"', "'"):
                return None, "", "'tools' must be an unquoted list or comma-separated tool names"
            pairs.append((key, cleaned))
            continue
        quoted_comment = re.match(r'^((["\'])(?:[^\\]|\\.)*?\2)[ \t]+#.*$', rest)
        candidate = quoted_comment.group(1) if quoted_comment else rest
        if candidate[:1] in ("|", ">"):
            return None, "", f"{key!r} uses a YAML block scalar indicator; write the value on one line"
        quoted = re.match(r'^(["\'])((?:[^\\]|\\.)*?)\1$', candidate)
        if quoted:
            if "\\" in quoted.group(2):
                return None, "", f"{key!r} contains a backslash escape; write the value plainly"
            pairs.append((key, quoted.group(2).strip()))
            continue
        if candidate[:1] in ('"', "'"):
            return None, "", f"{key!r} opens a quote that does not close on the same line"
        plain = re.sub(r"(?:^|[ \t])#.*$", "", candidate).strip()
        if plain[:1] in ("&", "*", "!", "[", "{"):
            return None, "", f"{key!r} uses YAML collection, anchor, alias or tag syntax ({plain!r})"
        pairs.append((key, plain))
    return pairs, body, None


def parse_tools_list(raw_tools: str | None) -> tuple[list[str] | None, list[str]]:
    if not raw_tools:
        return None, ["no tools list: an omitted list gets Antigravity's default set, not this role's"]
    match = re.fullmatch(r"\[(.*)\]", raw_tools.strip())
    if match is None:
        return None, ["tools must be written as '[tool, ...]'"]
    inner = match.group(1).strip()
    if not inner:
        return None, ["tools list is empty"]
    items = [part.strip() for part in inner.split(",")]
    errors: list[str] = []
    if any(not item for item in items):
        errors.append(f"malformed tools list {raw_tools!r}")
        return None, errors
    if "*" in items or any("*" in item for item in items):
        errors.append("grants wildcard '*' tools; subagents read and run, and the main loop writes")
    bad_write = sorted(WRITE_TOOLS & set(items))
    if bad_write:
        errors.append(f"lists a write tool: {bad_write}")
    unknown = [item for item in items if item not in ALLOWED_TOOLS and item not in WRITE_TOOLS and "*" not in item]
    if unknown:
        errors.append(f"lists unsupported tool(s): {unknown}")
    if len(set(items)) != len(items):
        errors.append(f"lists duplicate tool(s): {items}")
    return items, errors


def definition_problems(
    filename: str,
    text: str,
    *,
    expected_tools: list[str] | None = None,
    claude_text: str | None = None,
) -> list[str]:
    """Every way one Antigravity subagent definition fails its contract; empty when it holds."""
    pairs, body, error = parse_agent_markdown(text)
    if error is not None or pairs is None:
        return [error or "unreadable frontmatter"]
    keys = [key for key, _ in pairs]
    front = dict(pairs)
    found: list[str] = []
    if tuple(keys) != REQUIRED_KEYS:
        found.append(f"frontmatter keys are {keys}, not {list(REQUIRED_KEYS)}")
    stem = Path(filename).stem
    if not AGENT_NAME_RE.fullmatch(stem):
        found.append(f"file stem {stem!r} must be lowercase kebab-case")
    if front.get("name") != stem:
        found.append(f"name {front.get('name')!r} is not the file's name {stem!r}")
    if not (front.get("description") or "").strip():
        found.append("no description")
    model = front.get("model")
    if model != LOADER_MODEL:
        found.append(
            f"model is {model!r}, not {LOADER_MODEL!r}: Antigravity 1.5.8 skips concrete IDs in 'model:' and 'inherit' runs Carbon"
        )
    conclave_model = front.get("conclave_model")
    if conclave_model != PINNED_MODEL:
        found.append(f"conclave_model is {conclave_model!r}, not {PINNED_MODEL!r}")
    if front.get("subagent") != "true":
        found.append(f"subagent is {front.get('subagent')!r}, not 'true'")
    if front.get("mainAgent") != "true":
        found.append(f"mainAgent is {front.get('mainAgent')!r}, not 'true' (needed for 'agy --agent <name>')")
    if front.get("inheritMcp") != "false":
        found.append(f"inheritMcp is {front.get('inheritMcp')!r}, not 'false'")
    listed, tool_errors = parse_tools_list(front.get("tools"))
    found.extend(tool_errors)
    required_tools = expected_tools if expected_tools is not None else ROLE_TOOLS.get(stem)
    if listed is not None and required_tools is not None and listed != required_tools:
        found.append(f"tools are {listed}, not {required_tools}")
    if not body.strip():
        found.append("empty agent prompt body")
    if claude_text is not None:
        claude_pairs, claude_body, claude_err = parse_agent_markdown(claude_text)
        if claude_err is not None or claude_pairs is None:
            found.append(f"Claude counterpart is unreadable: {claude_err or 'missing frontmatter'}")
        else:
            claude_front = dict(claude_pairs)
            if body != claude_body:
                found.append("its body differs from the Claude subagent's")
            if front.get("description") != claude_front.get("description"):
                found.append("its description differs from the Claude subagent's")
    return found


def check_directory(repo_root: Path) -> tuple[int, list[str]]:
    agents_root = repo_root / ".agents"
    agents_dir = agents_root / "agents"
    if _is_link(agents_root) or _is_link(agents_dir):
        return 0, [".agents/agents must be a real directory, never a symlink or junction"]
    if not agents_dir.exists():
        return 0, []
    if not agents_dir.is_dir():
        return 0, [".agents/agents is not a directory"]
    errors: list[str] = []
    entries = sorted(agents_dir.iterdir(), key=lambda p: p.name)
    checked = 0
    for entry in entries:
        rel = f".agents/agents/{entry.name}"
        if _is_link(entry):
            errors.append(f"{rel} is a symlink or junction; agent definitions must be real files")
            continue
        if not entry.is_file() or entry.suffix != ".md":
            errors.append(f"{rel} is not a '.md' agent definition file")
            continue
        checked += 1
        text = entry.read_text(encoding="utf-8")
        for problem in definition_problems(entry.name, text):
            errors.append(f"{rel}: {problem}")
    return checked, errors


def _extract_tool_names(obj: object, found: list[str]) -> None:
    if isinstance(obj, dict):
        name = obj.get("tool_name") or obj.get("toolName")
        if isinstance(name, str) and name:
            found.append(name)
        for key, value in obj.items():
            if key not in ("response", "thinking", "content"):
                _extract_tool_names(value, found)
    elif isinstance(obj, list):
        for item in obj:
            _extract_tool_names(item, found)


def run_subagent(
    repo_root: Path,
    agent: str,
    prompt: str,
    *,
    timeout: int = 300,
    allow_commands: list[str] | None = None,
    agy_bin: str | None = None,
) -> dict[str, object]:
    if not AGENT_NAME_RE.fullmatch(agent):
        raise ValueError(f"invalid subagent name {agent!r}")
    if not prompt or not prompt.strip():
        raise ValueError("subagent prompt must be non-empty")
    if timeout < 1:
        raise ValueError("timeout must be at least 1 second")

    agents_root = repo_root / ".agents"
    agents_dir = agents_root / "agents"
    agent_file = agents_dir / f"{agent}.md"
    if _is_link(agents_root) or _is_link(agents_dir) or _is_link(agent_file):
        raise ValueError(f".agents/agents/{agent}.md must be a real file, never a symlink or junction")
    if not agent_file.is_file():
        raise ValueError(f"unknown Antigravity subagent {agent!r}: missing .agents/agents/{agent}.md")

    problems = definition_problems(agent_file.name, agent_file.read_text(encoding="utf-8"))
    if problems:
        raise ValueError(f".agents/agents/{agent}.md failed contract check: {'; '.join(problems)}")

    resolved_bin = agy_bin or os.environ.get("AGY_BIN") or shutil.which("agy")
    if not resolved_bin:
        raise RuntimeError("Antigravity CLI ('agy') was not found on PATH")

    permissions: dict[str, list[str]] = {"deny": ["write_file(*)", "edit_file(*)", "mcp(*)"]}
    if allow_commands:
        permissions["allow"] = list(allow_commands)
    settings = {"agentMode": "", "permissions": permissions}

    scratch = Path(tempfile.mkdtemp(prefix="conclave-agy-subagent-"))
    try:
        settings_path = scratch / "settings.json"
        prompt_path = scratch / "prompt.txt"
        stdout_path = scratch / "stdout.jsonl"
        stderr_path = scratch / "stderr.log"
        atomic_write_bytes(settings_path, json.dumps(settings).encode("utf-8"))
        atomic_write_bytes(prompt_path, prompt.encode("utf-8"))

        argv = [
            str(resolved_bin),
            "--model",
            PINNED_MODEL,
            "--agent",
            agent,
            "--settings",
            str(settings_path),
            "--input-format",
            "text",
            "--output-format",
            "stream-json",
            "--print-timeout",
            f"{timeout}s",
        ]
        windows = os.name == "nt"
        launch: list[str] | str = argv
        if windows and Path(argv[0]).suffix.lower() in (".cmd", ".bat"):
            launch = f'{os.environ.get("COMSPEC", "cmd.exe")} /d /s /c "{subprocess.list2cmdline(argv)}"'

        job: int | None = None
        proc: subprocess.Popen[bytes] | None = None
        wall_timeout = timeout + min(15, max(2, timeout))
        with (
            open(prompt_path, "rb") as stdin_handle,
            open(stdout_path, "wb") as stdout_handle,
            open(stderr_path, "wb") as stderr_handle,
        ):
            try:
                if windows:
                    job = _create_kill_on_close_job()
                    proc = subprocess.Popen(
                        launch,
                        cwd=str(repo_root),
                        stdin=stdin_handle,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                        creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED | CREATE_NO_WINDOW,
                    )
                    _assign_and_resume_windows(job, proc)
                else:
                    proc = subprocess.Popen(
                        launch,
                        cwd=str(repo_root),
                        stdin=stdin_handle,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                        start_new_session=True,
                    )
                try:
                    proc.wait(timeout=wall_timeout)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError(f"subagent {agent!r} timed out after {timeout}s") from exc
            except OSError as exc:
                raise RuntimeError(f"could not start Antigravity CLI {resolved_bin!r}: {exc.strerror or exc}") from exc
            finally:
                _kill_tree(proc, job)

        returncode = proc.returncode if proc is not None else 1
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    finally:
        _remove_scratch(scratch)

    init_event: dict[str, object] | None = None
    init_conversation_id = ""
    result_event: dict[str, object] | None = None
    tool_calls: list[str] = []
    forbidden_calls: list[str] = []

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        event = payload.get("event")
        if event == "init" and isinstance(payload.get("init"), dict):
            init_event = payload["init"]
            init_conversation_id = str(payload.get("conversation_id") or init_event.get("session_id") or "")
        elif event == "result" and isinstance(payload.get("result"), dict):
            result_event = payload["result"]
        else:
            seen_names: list[str] = []
            _extract_tool_names(payload, seen_names)
            for tool_name in seen_names:
                tool_calls.append(tool_name)
                if tool_name in WRITE_TOOLS:
                    forbidden_calls.append(tool_name)

    if forbidden_calls:
        raise RuntimeError(f"subagent {agent!r} attempted forbidden write tool(s): {sorted(set(forbidden_calls))}")
    if init_event is None:
        detail = (stderr or stdout).strip().splitlines()
        tail = detail[-1] if detail else f"exit code {returncode}"
        raise RuntimeError(f"subagent {agent!r} produced no stream-json init event ({tail})")
    actual_model = init_event.get("model")
    if actual_model != PINNED_MODEL:
        raise RuntimeError(f"subagent {agent!r} ran model {actual_model!r}, expected {PINNED_MODEL!r}")
    actual_agent = init_event.get("agent")
    if actual_agent != agent:
        raise RuntimeError(f"subagent {agent!r} ran agent {actual_agent!r}, expected {agent!r}")
    if returncode != 0 or result_event is None or result_event.get("status") != "SUCCESS":
        status = result_event.get("status") if result_event else "NO_RESULT"
        detail = (stderr or stdout).strip().splitlines()
        tail = detail[-1] if detail else f"exit code {returncode}"
        raise RuntimeError(f"subagent {agent!r} ended with status={status!r} rc={returncode} ({tail})")
    response = str(result_event.get("response") or "")
    if not response.strip():
        raise RuntimeError(f"subagent {agent!r} returned an empty response")

    return {
        "agent": agent,
        "model": actual_model,
        "conversation_id": init_conversation_id,
        "tool_calls": tool_calls,
        "response": response,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify Antigravity subagent definitions or invoke one on Gemini 4 Hydrogen medium."
    )
    parser.add_argument("agent", nargs="?", help="Subagent name under .agents/agents/<name>.md")
    parser.add_argument("--check", action="store_true", help="Check all .agents/agents/*.md definitions and exit")
    parser.add_argument("-p", "--prompt", help="Task prompt for the subagent (reads stdin when omitted)")
    parser.add_argument("--root", default=".", help="Project root holding .agents/agents/ (default: current directory)")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300)")
    parser.add_argument(
        "--allow-command",
        action="append",
        default=[],
        help="Optional session command allow rule, such as 'command(git)' or 'command(python)'",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON with model, agent, conversation_id and response")
    args = parser.parse_args(argv)

    repo_root = Path(args.root).resolve()
    if args.check:
        checked, errors = check_directory(repo_root)
        if errors:
            sys.stderr.write("Antigravity subagent contract failed:\n")
            for item in errors:
                sys.stderr.write(f"  - {item}\n")
            return 1
        sys.stdout.write(
            f"Antigravity subagents valid: {checked} definition(s) checked, all pinned to {PINNED_MODEL}.\n"
        )
        return 0

    if not args.agent:
        parser.error("pass <agent> to invoke a subagent, or --check to validate definitions")

    prompt = args.prompt if args.prompt is not None else sys.stdin.read()
    try:
        outcome = run_subagent(
            repo_root,
            args.agent,
            prompt,
            timeout=args.timeout,
            allow_commands=args.allow_command,
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except RuntimeError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(outcome, indent=2) + "\n")
    else:
        resp = str(outcome["response"])
        sys.stdout.write(resp if resp.endswith("\n") else resp + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
