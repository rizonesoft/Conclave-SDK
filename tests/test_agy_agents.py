"""Tests for native Antigravity Orchestrator (Carbon) adoption in kits/base."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
KIT_BASE = ROOT / "kits" / "base"
TEMPLATES = KIT_BASE / "templates"
RETIRED_AGENT_FILES = (
    "code-explorer.md",
    "debug-evidence.md",
    "git-runner.md",
    "mutation-tester.md",
    "test-runner.md",
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import forge  # noqa: E402


def _load_review_pin():
    """Import scripts/lib/review_pin.py without mutating sys.path permanently."""
    path = ROOT / "kits" / "reviewer" / "templates" / "scripts" / "review_pin.py"
    spec = importlib.util.spec_from_file_location("review_pin_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _configure_win32_job_api():
    """Bind Win32 and ntdll APIs with explicit 64-bit-safe handle types."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    return kernel32, ntdll, JOBOBJECT_EXTENDED_LIMIT_INFORMATION


def _is_pid_alive(pid: int) -> bool:
    """Return True if pid still exists as an active OS process."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        kernel32, _, _ = _configure_win32_job_api()
        process_query_limited_information = 0x1000
        still_active = 259
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kill_tree(proc: subprocess.Popen[str], job_handle: int | None = None) -> None:
    """Terminate proc and every descendant process cleanly on Windows or POSIX."""
    if sys.platform == "win32":
        kernel32, _, _ = _configure_win32_job_api()
        if job_handle:
            try:
                kernel32.TerminateJobObject(job_handle, 1)
            except OSError:
                pass
        if proc.poll() is None:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        if job_handle:
            try:
                kernel32.CloseHandle(job_handle)
            except OSError:
                pass
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _run_bounded_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: float,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str, bool]:
    """Run cmd in a process tree / Job Object and kill the entire tree on timeout or exit."""
    popen_kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": env,
    }
    job_handle: int | None = None
    assigned_job = False

    if sys.platform == "win32":
        create_suspended = 0x00000004
        create_new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        popen_kwargs["creationflags"] = create_suspended | create_new_process_group
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)
    timed_out = False
    stdout = ""
    stderr = ""

    try:
        if sys.platform == "win32":
            kernel32, ntdll, ext_struct = _configure_win32_job_api()
            job_object_limit_kill_on_job_close = 0x2000
            job_object_extended_limit_information = 9
            job_handle = kernel32.CreateJobObjectW(None, None)
            if job_handle:
                info = ext_struct()
                info.BasicLimitInformation.LimitFlags = job_object_limit_kill_on_job_close
                if kernel32.SetInformationJobObject(
                    job_handle,
                    job_object_extended_limit_information,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                ):
                    assigned_job = bool(
                        kernel32.AssignProcessToJobObject(job_handle, int(proc._handle))
                    )
                if not assigned_job:
                    kernel32.CloseHandle(job_handle)
                    job_handle = None
            ntdll.NtResumeProcess(int(proc._handle))

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc, job_handle)
            job_handle = None
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout = stdout or ""
                stderr = stderr or ""
    finally:
        # Terminate any surviving descendants even when the root exited normally.
        _kill_tree(proc, job_handle)
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()

    returncode = proc.returncode if proc.returncode is not None else -1
    return returncode, stdout or "", stderr or "", timed_out


def _run_agy(
    prompt: str,
    *,
    cwd: Path,
    model: str = "gemini-pro-orchestrator",
    timeout: float = 240.0,
    extra_args: list[str] | None = None,
) -> tuple[int, str, str, bool]:
    """Invoke agy headless with stream-json output under bounded tree cleanup."""
    print_timeout = max(30, int(timeout) - 10)
    cmd = [
        "agy",
        "--model",
        model,
        "--dangerously-skip-permissions",
        "--output-format",
        "stream-json",
        "--print-timeout",
        f"{print_timeout}s",
        *(extra_args or []),
        "-p",
        prompt,
    ]
    return _run_bounded_subprocess(cmd, cwd=cwd, timeout=timeout)


def _extract_agy_step_update(
    step: dict[str, object],
    seen_tool_ids: set[str],
    tool_uses: list[dict[str, object]],
    tool_results: list[dict[str, object]],
    delta_chunks: list[str],
) -> None:
    """Extract tool/subagent call, result, and text events from agy 1.5.8 step_update."""
    step_type = str(step.get("step_type") or "").lower()
    state = str(step.get("state") or "").upper()
    if step_type == "agent_response":
        delta = step.get("text_delta")
        if isinstance(delta, str) and delta:
            delta_chunks.append(delta)
        return
    if step_type not in {"tool", "subagent"}:
        return

    tool_info = step.get("tool_info")
    info = tool_info if isinstance(tool_info, dict) else {}
    sub_info = step.get("subagent_info")
    sinfo = sub_info if isinstance(sub_info, dict) else {}
    name = str(step.get("tool_name") or info.get("name") or "")
    if not name and step_type == "subagent":
        name = "invoke_subagent"
    if not name:
        return
    step_idx = step.get("step_index")
    tool_id = str(step.get("tool_id") or (f"step-{step_idx}" if step_idx is not None else ""))

    if state == "ACTIVE" or (tool_id and tool_id not in seen_tool_ids):
        if tool_id:
            seen_tool_ids.add(tool_id)
        tool_uses.append(
            {
                "name": name,
                "id": tool_id,
                "args": info.get("parameters") or info.get("args") or sinfo or {},
            }
        )

    if state != "ACTIVE":
        err = step.get("error") or info.get("error") or sinfo.get("error")
        is_error = bool(
            state in {"ERROR", "FAILED", "FAILURE", "CANCELLED"}
            or step.get("is_error")
            or info.get("is_error")
            or sinfo.get("is_error")
            or err
        )
        tool_results.append(
            {
                "name": name,
                "id": tool_id,
                "status": "error" if is_error else (str(step.get("status") or state or "DONE")),
                "is_error": is_error,
                "output": info.get("output") or err or (sinfo if sinfo else ""),
            }
        )


def _extract_tool_events(
    event: dict[str, object],
    seen_tool_ids: set[str],
    tool_uses: list[dict[str, object]],
    tool_results: list[dict[str, object]],
    delta_chunks: list[str],
    result_texts: list[str],
) -> None:
    """Walk one parsed stream-json event recursively for tool calls, results, and text."""
    event_kind = str(event.get("event") or "").lower()
    if event_kind == "step_update" and isinstance(event.get("step_update"), dict):
        _extract_agy_step_update(
            event["step_update"], seen_tool_ids, tool_uses, tool_results, delta_chunks
        )
        return
    if event_kind == "result" and isinstance(event.get("result"), dict):
        res_obj = event["result"]
        for key in ("response", "result", "text", "summary"):
            val = res_obj.get(key)
            if isinstance(val, str) and val:
                result_texts.append(val)
        return

    etype = str(event.get("type") or "").lower()
    if etype in {"tool_use", "tool_call"}:
        name = str(event.get("tool_name") or event.get("name") or "")
        if name:
            tool_uses.append(
                {
                    "name": name,
                    "id": str(event.get("tool_id") or event.get("id") or event.get("call_id") or ""),
                    "args": event.get("parameters")
                    or event.get("arguments")
                    or event.get("args")
                    or event.get("input")
                    or {},
                }
            )
    elif etype in {"tool_result", "tool_response"}:
        tool_results.append(
            {
                "name": str(event.get("tool_name") or event.get("name") or ""),
                "id": str(event.get("tool_id") or event.get("id") or event.get("call_id") or ""),
                "status": str(event.get("status") or ""),
                "is_error": bool(event.get("is_error") or event.get("error")),
                "output": event.get("output") or event.get("result") or event.get("content") or "",
            }
        )
    elif etype == "message" and event.get("role") == "assistant":
        content = event.get("content")
        if isinstance(content, str):
            result_texts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    result_texts.append(item["text"])
                elif isinstance(item, str):
                    result_texts.append(item)
    elif etype == "result":
        for key in ("response", "result", "text", "summary"):
            val = event.get(key)
            if isinstance(val, str) and val:
                result_texts.append(val)

    for key in ("tool_calls", "calls", "parts"):
        nested = event.get(key)
        if isinstance(nested, list):
            for entry in nested:
                if isinstance(entry, dict):
                    if "functionCall" in entry and isinstance(entry["functionCall"], dict):
                        fc = entry["functionCall"]
                        tool_uses.append(
                            {
                                "name": str(fc.get("name") or ""),
                                "id": str(fc.get("id") or ""),
                                "args": fc.get("args") or {},
                            }
                        )
                    elif "functionResponse" in entry and isinstance(entry["functionResponse"], dict):
                        fr = entry["functionResponse"]
                        tool_results.append(
                            {
                                "name": str(fr.get("name") or ""),
                                "id": str(fr.get("id") or ""),
                                "status": str(fr.get("status") or ""),
                                "is_error": bool(fr.get("is_error") or fr.get("error")),
                                "output": fr.get("response") or fr.get("output") or "",
                            }
                        )
                    else:
                        _extract_tool_events(
                            entry,
                            seen_tool_ids,
                            tool_uses,
                            tool_results,
                            delta_chunks,
                            result_texts,
                        )


def _parse_ndjson_stream(
    ndjson: str, *, expected_model_prefix: str = "gemini-pro-orchestrator"
) -> dict[str, object]:
    """Parse Antigravity stream-json output and enforce init model + terminal success."""
    init_models: list[str] = []
    seen_tool_ids: set[str] = set()
    tool_uses: list[dict[str, object]] = []
    tool_results: list[dict[str, object]] = []
    delta_chunks: list[str] = []
    result_texts: list[str] = []
    result_events: list[dict[str, object]] = []
    steps: list[tuple[int, str, str]] = []

    for raw in ndjson.splitlines():
        line = raw.strip()
        if not line or not line.startswith("{"):
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            continue
        event_kind = str(event.get("event") or "").lower()
        etype = str(event.get("type") or "").lower()
        if event_kind == "step_update" and isinstance(event.get("step_update"), dict):
            su = event["step_update"]
            raw_idx = su.get("step_index")
            step_idx = raw_idx if isinstance(raw_idx, int) else -1
            steps.append(
                (
                    step_idx,
                    str(su.get("step_type") or "").lower(),
                    str(su.get("state") or "").upper(),
                )
            )
        if event_kind == "init" and isinstance(event.get("init"), dict):
            model = event["init"].get("model")
            if isinstance(model, str):
                init_models.append(model)
        elif etype == "init" and isinstance(event.get("model"), str):
            init_models.append(event["model"])

        if event_kind == "result" and isinstance(event.get("result"), dict):
            result_events.append(event["result"])
        elif etype == "result":
            result_events.append(event)

        _extract_tool_events(
            event, seen_tool_ids, tool_uses, tool_results, delta_chunks, result_texts
        )

    if not init_models:
        raise AssertionError("stream-json missing init.model event")
    bad_models = [m for m in init_models if not m.startswith(expected_model_prefix)]
    if bad_models:
        raise AssertionError(
            f"unexpected init.model {bad_models!r}; expected prefix {expected_model_prefix!r}"
        )
    if not result_events:
        raise AssertionError("stream-json incomplete: missing terminal result event")
    final_result = result_events[-1]
    status = str(final_result.get("status") or "")
    if status.upper() != "SUCCESS" or final_result.get("error"):
        raise AssertionError(
            f"stream-json did not finish with SUCCESS result: {final_result!r}"
        )

    streamed_text = "".join(delta_chunks)
    final_text = "\n".join(result_texts) if result_texts else streamed_text
    if streamed_text and result_texts and streamed_text not in final_text:
        final_text = streamed_text + "\n" + final_text

    return {
        "models": init_models,
        "tool_uses": tool_uses,
        "tool_results": tool_results,
        "steps": steps,
        "assistant_text": final_text,
        "result_status": status,
    }


def _matching_tool_results(
    tool_name: str, tool_uses: list[dict[str, object]], tool_results: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Return tool_results matching tool_name (via explicit name or matching tool_id)."""
    ids = {
        str(call["id"])
        for call in tool_uses
        if call.get("name") == tool_name and call.get("id")
    }
    matched: list[dict[str, object]] = []
    for res in tool_results:
        rid = str(res.get("id") or "")
        if res.get("name") == tool_name or (ids and rid in ids):
            matched.append(res)
    return matched


def _assert_result_succeeded(res: dict[str, object], tool_name: str) -> None:
    """Reject missing/errored tool_result dictionaries."""
    status = str(res.get("status") or "").lower()
    if res.get("is_error") or status in {"error", "failed", "failure"}:
        raise AssertionError(f"{tool_name} tool_result reported failure: {res!r}")


def parse_orchestrator_stream(
    ndjson: str, *, expected_model_prefix: str = "gemini-pro-orchestrator"
) -> dict[str, object]:
    """Validate that an Orchestrator run planned, exited plan mode, and executed cleanly."""
    parsed = _parse_ndjson_stream(ndjson, expected_model_prefix=expected_model_prefix)
    tool_uses: list[dict[str, object]] = parsed["tool_uses"]  # type: ignore[assignment]
    tool_results: list[dict[str, object]] = parsed["tool_results"]  # type: ignore[assignment]

    exit_indices = [i for i, call in enumerate(tool_uses) if call.get("name") == "exit_plan_mode"]
    if not exit_indices:
        raise AssertionError("Orchestrator stream did not invoke exit_plan_mode")

    exit_results = _matching_tool_results("exit_plan_mode", tool_uses, tool_results)
    if not exit_results:
        raise AssertionError("exit_plan_mode was called without a completion tool_result")
    for res in exit_results:
        _assert_result_succeeded(res, "exit_plan_mode")

    post_exit_tools = [
        call for call in tool_uses[exit_indices[0] + 1 :] if call.get("name") != "exit_plan_mode"
    ]
    if not post_exit_tools:
        raise AssertionError("Orchestrator emitted no execution tool call after exit_plan_mode")
    return parsed


def parse_subagent_delegation_stream(
    ndjson: str, *, expected_model_prefix: str = "gemini-pro-orchestrator"
) -> dict[str, object]:
    """Validate actual invoke_subagent delegation + completion in stream-json output."""
    parsed = _parse_ndjson_stream(ndjson, expected_model_prefix=expected_model_prefix)
    tool_uses: list[dict[str, object]] = parsed["tool_uses"]  # type: ignore[assignment]
    tool_results: list[dict[str, object]] = parsed["tool_results"]  # type: ignore[assignment]
    steps: list[tuple[int, str, str]] = parsed["steps"]  # type: ignore[assignment]

    subagent_calls = [call for call in tool_uses if call.get("name") == "invoke_subagent"]
    if not subagent_calls:
        raise AssertionError(
            "stream did not invoke invoke_subagent (listing-only output is insufficient)"
        )

    subagent_results = _matching_tool_results("invoke_subagent", tool_uses, tool_results)
    if len(subagent_results) < len(subagent_calls):
        raise AssertionError("invoke_subagent call lacked a matching completion tool_result")
    for res in subagent_results:
        _assert_result_succeeded(res, "invoke_subagent")
        out = res.get("output")
        if isinstance(out, dict) and isinstance(out.get("subagents"), list):
            for entry in out["subagents"]:
                if not isinstance(entry, dict) or not str(entry.get("conversation_id") or "").strip():
                    raise AssertionError(f"invoke_subagent result missing conversation_id: {entry!r}")

    launch_indices: list[int] = []
    for call in subagent_calls:
        cid = str(call.get("id") or "")
        if cid.startswith("step-"):
            tail = cid.removeprefix("step-")
            if tail.isdigit():
                launch_indices.append(int(tail))
    if launch_indices:
        min_launch = min(launch_indices)
        has_wakeup = any(
            idx > min_launch and stype == "system_message" and sstate == "DONE"
            for idx, stype, sstate in steps
        )
        if not has_wakeup:
            raise AssertionError(
                "invoke_subagent launched asynchronously without post-launch system_message completion"
            )

    parsed["subagent_calls"] = subagent_calls
    parsed["subagent_results"] = subagent_results
    return parsed


def _run_forge(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run forge.py synchronously inside ROOT."""
    return subprocess.run(
        [sys.executable, str(ROOT / "forge.py"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


class OrchestratorContractTests(unittest.TestCase):
    """Offline structural, migration, pin, and documentation contracts for Antigravity."""

    def test_retired_wrappers_and_suite_removed_everywhere(self) -> None:
        self.assertFalse((TEMPLATES / ".agents" / "agents").exists())
        self.assertFalse((TEMPLATES / "scripts" / "agy-subagent.py").exists())
        self.assertFalse((ROOT / ".agents" / "agents").exists())
        self.assertFalse((ROOT / "scripts" / "agy-subagent.py").exists())
        self.assertNotIn("agy-subagents", [suite["name"] for suite in forge.SUITES])

        claude_agents = sorted((TEMPLATES / ".claude" / "agents").glob("*.md"))
        self.assertEqual(len(claude_agents), 5)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "fresh-agy"
            _run_forge(["init", str(project), "--kit", "base", "--agent", "agy"])
            self.assertFalse((project / ".agents" / "agents").exists())
            self.assertFalse((project / "scripts" / "agy-subagent.py").exists())
            self.assertTrue((project / ".agents" / "skills").is_dir())
            self.assertTrue((project / "AGENTS.md").is_file())
            self.assertTrue((project / "GEMINI.md").is_file())

    def test_migration_preserves_custom_agents_and_removes_retired_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "legacy-agy"
            _run_forge(["init", str(project), "--kit", "base", "--agent", "agy"])

            kits_file = project / ".conclave" / "kits.json"
            kits_data = json.loads(kits_file.read_text(encoding="utf-8"))
            files_map: dict[str, dict[str, str]] = kits_data["files"]

            retired_paths = [
                *[f".agents/agents/{name}" for name in RETIRED_AGENT_FILES],
                "scripts/agy-subagent.py",
            ]
            for rel in retired_paths:
                dest = project / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                original_bytes = f"# legacy wrapper placeholder for {rel}\n".encode("utf-8")
                files_map[rel] = {
                    "kit": "base",
                    "sha256": hashlib.sha256(original_bytes).hexdigest(),
                }
                if rel == ".agents/agents/code-explorer.md":
                    dest.write_bytes(original_bytes + b"# project customization\n")
                else:
                    dest.write_bytes(original_bytes)

            kits_file.write_text(json.dumps(kits_data, indent=2) + "\n", encoding="utf-8")

            custom_agent = project / ".agents" / "agents" / "custom-reviewer.md"
            custom_text = "# Project-specific custom agent definition\n"
            custom_agent.write_text(custom_text, encoding="utf-8")

            diff_proc = _run_forge(["diff", str(project), "base"], check=False)
            self.assertEqual(diff_proc.returncode, 0, diff_proc.stderr)
            for rel in retired_paths:
                self.assertIn(rel, diff_proc.stdout)
                self.assertIn("project-only", diff_proc.stdout)

            update_proc = _run_forge(["update", str(project), "base"], check=False)
            self.assertEqual(update_proc.returncode, 0, update_proc.stderr)
            for rel in retired_paths:
                self.assertTrue((project / rel).is_file(), f"update removed {rel} unexpectedly")
            self.assertIn(
                b"# project customization\n",
                (project / ".agents/agents/code-explorer.md").read_bytes(),
            )
            self.assertEqual(custom_agent.read_text(encoding="utf-8"), custom_text)

            locally_modified = [
                rel
                for rel in retired_paths
                if hashlib.sha256((project / rel).read_bytes()).hexdigest()
                != files_map[rel]["sha256"]
            ]
            self.assertEqual(locally_modified, [".agents/agents/code-explorer.md"])

            # Follow the documented migration cleanup: remove only the 6 retired SDK paths.
            for rel in retired_paths:
                (project / rel).unlink()
            updated_kits = json.loads(kits_file.read_text(encoding="utf-8"))
            for rel in retired_paths:
                updated_kits["files"].pop(rel, None)
            kits_file.write_text(json.dumps(updated_kits, indent=2) + "\n", encoding="utf-8")

            self.assertEqual(custom_agent.read_text(encoding="utf-8"), custom_text)
            for rel in retired_paths:
                self.assertFalse((project / rel).exists())

            post_diff = _run_forge(["diff", str(project), "base"], check=False)
            self.assertEqual(post_diff.returncode, 0, post_diff.stderr)
            for rel in retired_paths:
                self.assertNotIn(rel, post_diff.stdout)

            doctor_proc = _run_forge(["doctor", str(project), "base"], check=False)
            self.assertEqual(doctor_proc.returncode, 0, doctor_proc.stdout + doctor_proc.stderr)

    def test_docs_self_sync_and_review_pin_orchestrator_helpers(self) -> None:
        readme = (KIT_BASE / "README.md").read_text(encoding="utf-8")
        self.assertIn("### Migrating existing installs to Orchestrator (Carbon)", readme)
        self.assertIn("### Live verification", readme)
        self.assertIn("--model gemini-pro-orchestrator", readme)
        self.assertIn(".agents/agents/<custom>.md", readme)
        for name in RETIRED_AGENT_FILES:
            self.assertIn(name, readme)
        self.assertIn("scripts/agy-subagent.py", readme)

        structure_template = (
            TEMPLATES / "docs" / "agent-skills-and-rules-structure.md"
        ).read_text(encoding="utf-8")
        structure_root = (ROOT / "docs" / "agent-skills-and-rules-structure.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(structure_template, structure_root)
        self.assertIn(
            "without `.agents/agents/*.md` files or `scripts/agy-subagent.py`",
            structure_root,
        )

        pin = _load_review_pin()
        self.assertTrue(pin.is_agy_orchestrator("gemini-pro-orchestrator"))
        self.assertTrue(pin.is_agy_orchestrator("gemini-pro-orchestrator-argon"))
        self.assertFalse(pin.is_agy_orchestrator("gemini-4-carbon-high"))

        three_pass_ok = {
            "policy": pin.THREE_PASS,
            "plan": {},
            "rounds": [{}],
            "completion": {},
            "reconciliation": {},
        }
        pin.check_agy_effort("carbon", "gemini-pro-orchestrator", three_pass_ok)

        three_pass_effort = {**three_pass_ok, "plan": {"effort": "medium"}}
        with self.assertRaisesRegex(pin.Refused, "manages its own effort and rejects --effort"):
            pin.check_agy_effort("carbon", "gemini-pro-orchestrator", three_pass_effort)

        rotation_effort = {
            "policy": "rotation",
            "plan": {},
            "rounds": [{}],
            "completion": {},
            "escalation": {"effort": "high"},
            "rotation": {},
        }
        with self.assertRaisesRegex(pin.Refused, "manages its own effort and rejects --effort"):
            pin.check_agy_effort("carbon", "gemini-pro-orchestrator-argon", rotation_effort)


def _agy_init_line(model: str = "gemini-pro-orchestrator") -> str:
    """Return an agy 1.5.8 init NDJSON line."""
    return json.dumps({"event": "init", "conversation_id": "c1", "init": {"model": model}})


def _agy_tool_pair(
    step_index: int,
    tool_name: str,
    *,
    parameters: dict[str, object] | None = None,
    state: str = "DONE",
    output: str = "",
    error: str = "",
) -> list[str]:
    """Return ACTIVE and terminal step_update lines matching agy 1.5.8 stream-json."""
    active = json.dumps(
        {
            "event": "step_update",
            "step_update": {
                "conversation_id": "c1",
                "step_index": step_index,
                "state": "ACTIVE",
                "step_type": "tool",
                "tool_name": tool_name,
                "tool_info": {"name": tool_name, "parameters": parameters or {}},
            },
        }
    )
    done_step: dict[str, object] = {
        "conversation_id": "c1",
        "step_index": step_index,
        "state": state,
        "step_type": "tool",
        "tool_name": tool_name,
        "tool_info": {
            "name": tool_name,
            "parameters": parameters or {},
            **({"output": output} if output else {}),
        },
    }
    if error:
        done_step["error"] = error
    return [active, json.dumps({"event": "step_update", "step_update": done_step})]


def _agy_subagent_pair(
    step_index: int,
    type_name: str = "research",
    *,
    state: str = "DONE",
    error: str = "",
) -> list[str]:
    """Return ACTIVE and terminal step_update lines matching agy 1.5.8 invoke_subagent."""
    sub_entry: dict[str, object] = {
        "type_name": type_name,
        "role": "Codebase Researcher",
        "initial_prompt": "Locate halve in calc.py",
    }
    active = json.dumps(
        {
            "event": "step_update",
            "step_update": {
                "conversation_id": "c1",
                "step_index": step_index,
                "state": "ACTIVE",
                "step_type": "subagent",
                "tool_name": "invoke_subagent",
                "subagent_info": {"subagents": [sub_entry]},
            },
        }
    )
    done_entry = {**sub_entry, "conversation_id": "sub-1"}
    done_step: dict[str, object] = {
        "conversation_id": "c1",
        "step_index": step_index,
        "state": state,
        "step_type": "subagent",
        "tool_name": "invoke_subagent",
        "subagent_info": {"subagents": [done_entry]},
    }
    if error:
        done_step["error"] = error
    return [active, json.dumps({"event": "step_update", "step_update": done_step})]


def _agy_result_line(status: str = "SUCCESS", response: str = "Done.") -> str:
    """Return an agy 1.5.8 terminal result NDJSON line."""
    return json.dumps(
        {
            "event": "result",
            "result": {"conversation_id": "c1", "status": status, "response": response},
        }
    )


class ProcessAndStreamContractTests(unittest.TestCase):
    """Process-tree teardown and positive/negative stream-json parser tests."""

    def test_timeout_kills_parent_and_descendant_process_tree(self) -> None:
        child_script = """
import subprocess, sys, time
from pathlib import Path

pid_file = Path(sys.argv[1])
if len(sys.argv) == 2:
    grand = subprocess.Popen([sys.executable, __file__, str(pid_file), "grandchild"])
    pid_file.write_text(str(grand.pid), encoding="utf-8")
    time.sleep(60)
else:
    time.sleep(60)
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script = tmp_path / "spawn_tree.py"
            grand_pid_file = tmp_path / "grand.pid"
            script.write_text(child_script.strip() + "\n", encoding="utf-8")

            # Use a child wrapper that lets the script write grand.pid before timing out.
            # Retry deadline comfortably longer than Python startup + file write (<0.4s).
            _, _, _, timed_out = _run_bounded_subprocess(
                [sys.executable, str(script), str(grand_pid_file)],
                cwd=tmp_path,
                timeout=1.5,
            )
            self.assertTrue(timed_out, "spawn_tree.py should have timed out")
            self.assertTrue(grand_pid_file.is_file(), "child did not spawn grandchild in time")
            grand_pid = int(grand_pid_file.read_text(encoding="utf-8").strip())

            deadline = time.monotonic() + 3.0
            while _is_pid_alive(grand_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(
                _is_pid_alive(grand_pid),
                f"descendant PID {grand_pid} survived bounded tree cleanup",
            )

    def test_accepts_valid_orchestrator_exit_plan_and_execution_stream(self) -> None:
        stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(
                    12,
                    "exit_plan_mode",
                    parameters={"plan": "fix calc.add"},
                    output="Plan mode is off.",
                ),
                *_agy_tool_pair(15, "edit_file", parameters={"Path": "calc.py"}),
                _agy_result_line("SUCCESS", "Fixed add() and ran unittest."),
            ]
        )
        parsed = parse_orchestrator_stream(stream)
        self.assertEqual(parsed["models"], ["gemini-pro-orchestrator"])

    def test_accepts_valid_invoke_subagent_delegation_stream(self) -> None:
        stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator-argon"),
                *_agy_subagent_pair(3, "research"),
                json.dumps(
                    {
                        "event": "step_update",
                        "step_update": {
                            "conversation_id": "c1",
                            "step_index": 5,
                            "state": "DONE",
                            "step_type": "system_message",
                        },
                    }
                ),
                json.dumps(
                    {
                        "event": "step_update",
                        "step_update": {
                            "conversation_id": "c1",
                            "step_index": 6,
                            "state": "ACTIVE",
                            "step_type": "agent_response",
                            "text_delta": "halve is on ",
                        },
                    }
                ),
                json.dumps(
                    {
                        "event": "step_update",
                        "step_update": {
                            "conversation_id": "c1",
                            "step_index": 6,
                            "state": "DONE",
                            "step_type": "agent_response",
                            "text_delta": "line 5.",
                        },
                    }
                ),
                _agy_result_line("SUCCESS", "halve is on line 5 of calc.py and returns n / 2."),
            ]
        )
        parsed = parse_subagent_delegation_stream(stream)
        self.assertIn("line 5", str(parsed["assistant_text"]))

    def test_rejects_listing_only_output_without_invoke_subagent(self) -> None:
        stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                _agy_result_line("SUCCESS", "Available subagents: self, research, image-generator."),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_subagent_delegation_stream(stream)

    def test_rejects_failed_or_incomplete_invoke_subagent(self) -> None:
        failed_stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_subagent_pair(
                    3,
                    "research",
                    state="ERROR",
                    error="subagent launch denied",
                ),
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_subagent_delegation_stream(failed_stream)

        incomplete_call_stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                _agy_subagent_pair(3, "research")[0],
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_subagent_delegation_stream(incomplete_call_stream)

        launch_only_stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_subagent_pair(3, "research"),
                _agy_result_line("SUCCESS", "Launched research subagent."),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_subagent_delegation_stream(launch_only_stream)

    def test_rejects_missing_exit_plan_mode_wrong_model_and_incomplete_result(self) -> None:
        no_exit = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(3, "edit_file", parameters={"Path": "calc.py"}),
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_orchestrator_stream(no_exit)

        wrong_model = "\n".join(
            [
                _agy_init_line("gemini-4-carbon-high"),
                *_agy_tool_pair(3, "exit_plan_mode", output="Plan mode is off."),
                *_agy_tool_pair(4, "edit_file"),
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_orchestrator_stream(wrong_model)

        incomplete = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(3, "exit_plan_mode", output="Plan mode is off."),
                *_agy_tool_pair(4, "edit_file"),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_orchestrator_stream(incomplete)

        failed_result = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(3, "exit_plan_mode", output="Plan mode is off."),
                *_agy_tool_pair(4, "edit_file"),
                _agy_result_line("ERROR"),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_orchestrator_stream(failed_result)


CALC_SOURCE = """def add(a, b):
    return a - b


def halve(n):
    return n / 2
"""

TESTS_SOURCE = """import unittest
from calc import add, halve


class CalcTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_halve(self):
        self.assertEqual(halve(10), 5)
"""


def _make_live_workspace(tmp_root: Path) -> Path:
    """Create a fresh base+agy workspace with a known buggy calc.py and failing unit test."""
    ws = tmp_root / "ws"
    _run_forge(["init", str(ws), "--kit", "base", "--agent", "agy"])
    (ws / "calc.py").write_text(CALC_SOURCE, encoding="utf-8")
    (ws / "tests").mkdir(exist_ok=True)
    (ws / "tests" / "test_calc.py").write_text(TESTS_SOURCE, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(ws), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(ws),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(ws),
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=str(ws), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial buggy calc"],
        cwd=str(ws),
        check=True,
        capture_output=True,
    )
    return ws


def _dump_stream_on_error(name: str, stdout: str, stderr: str) -> Path:
    """Save raw stream output under build/ when a live assertion fails."""
    dump_dir = ROOT / "build"
    dump_dir.mkdir(exist_ok=True)
    dump = dump_dir / f"live-agy-{name}.jsonl"
    dump.write_text(stdout + ("\n--- STDERR ---\n" + stderr if stderr else ""), encoding="utf-8")
    return dump


@unittest.skipUnless(
    bool(os.environ.get("CONCLAVE_LIVE_AGY")) and bool(shutil.which("agy")),
    "live Orchestrator proof runs only when CONCLAVE_LIVE_AGY is set and agy is on PATH",
)
class LiveOrchestratorTests(unittest.TestCase):
    """Live agy 1.5.8 proofs for built-in subagents, invoke_subagent, and exit_plan_mode."""

    def test_00_builtin_subagents_listed_without_legacy_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_live_workspace(Path(tmp))
            self.assertFalse((ws / ".agents" / "agents").exists())
            prompt = (
                "Do not edit any files. First exit plan mode if needed, or answer directly: "
                "list the built-in subagent TypeName identifiers visible in your <subagents> "
                "prompt section (including self, research, image-generator) and check whether "
                "a .agents/agents directory exists in this workspace."
            )
            rc, stdout, stderr, timed_out = _run_agy(prompt, cwd=ws, timeout=180.0)
            try:
                self.assertFalse(timed_out, f"agy timed out; stderr={stderr}")
                self.assertEqual(rc, 0, f"agy rc={rc}; stderr={stderr}\nstdout={stdout[-1000:]}")
                parsed = _parse_ndjson_stream(stdout)
                text = str(parsed["assistant_text"]).lower()
                for name in ("self", "research", "image-generator"):
                    self.assertIn(name, text, f"missing built-in subagent {name!r} in:\n{text}")
            except AssertionError as exc:
                dump = _dump_stream_on_error("test00", stdout, stderr)
                raise AssertionError(f"{exc} (stream saved to {dump})") from exc

    def test_01_live_invoke_subagent_known_answer_delegation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_live_workspace(Path(tmp))
            prompt = (
                "Call invoke_subagent once with TypeName='research' to read calc.py and find the "
                "exact 1-based line number of `def halve` and the expression it returns. "
                "Wait for the subagent reply (stop calling other tools until it replies), then "
                "report the exact line number and returned expression."
            )
            rc, stdout, stderr, timed_out = _run_agy(prompt, cwd=ws, timeout=240.0)
            try:
                self.assertFalse(timed_out, f"agy timed out; stderr={stderr}")
                self.assertEqual(rc, 0, f"agy rc={rc}; stderr={stderr}\nstdout={stdout[-1200:]}")
                parsed = parse_subagent_delegation_stream(stdout)
                combined = (
                    str(parsed["assistant_text"]) + "\n" + json.dumps(parsed["subagent_results"])
                )
                self.assertRegex(combined, r"\b5\b", f"expected line 5 in:\n{combined}")
                self.assertIn("n / 2", combined, f"expected 'n / 2' in:\n{combined}")
            except AssertionError as exc:
                dump = _dump_stream_on_error("test01", stdout, stderr)
                raise AssertionError(f"{exc} (stream saved to {dump})") from exc

    def test_02_live_orchestrator_plans_exits_plan_mode_and_executes_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_live_workspace(Path(tmp))
            prompt = (
                "Plan and fix the bug in calc.py so `python -m unittest tests.test_calc` passes "
                "all tests. Use your normal planning phase, invoke exit_plan_mode to transition "
                "to execution, apply the fix to calc.py, run `python -m unittest tests.test_calc`, "
                "and report the test output."
            )
            rc, stdout, stderr, timed_out = _run_agy(prompt, cwd=ws, timeout=240.0)
            try:
                self.assertFalse(timed_out, f"agy timed out; stderr={stderr}")
                self.assertEqual(rc, 0, f"agy rc={rc}; stderr={stderr}\nstdout={stdout[-1200:]}")
                parse_orchestrator_stream(stdout)
            except AssertionError as exc:
                dump = _dump_stream_on_error("test02", stdout, stderr)
                raise AssertionError(f"{exc} (stream saved to {dump})") from exc
            fixed_src = (ws / "calc.py").read_text(encoding="utf-8")
            self.assertIn("a + b", fixed_src)
            check = subprocess.run(
                [sys.executable, "-m", "unittest", "tests.test_calc"],
                cwd=str(ws),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
