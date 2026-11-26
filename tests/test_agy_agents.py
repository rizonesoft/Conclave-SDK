"""Tests for native Antigravity Orchestrator (Carbon) adoption in kits/base."""

from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
import zipfile
import urllib.request


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


@contextlib.contextmanager
def _temp_dir_released_by_its_tree(seconds: float = 5.0):
    """A temp folder for a test whose killed process tree ran in it. Windows reports a killed process gone a moment
    before it lets go of its working folder (about 0.1 s, measured 2026-11-14), so the removal waits for that, bounded:
    a folder still held after `seconds` is a process that survived, and the removal's error fails the test."""
    tmp = tempfile.mkdtemp()
    try:
        yield tmp
    finally:
        deadline = time.monotonic() + seconds
        while os.path.lexists(tmp):
            try:
                shutil.rmtree(tmp)
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)


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


def _kill_tree(
    proc: subprocess.Popen[str],
    job_handle: int | None = None,
    pgid: int | None = None,
) -> None:
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
        target_pgid = pgid
        if target_pgid is None:
            try:
                target_pgid = os.getpgid(proc.pid)
            except (ProcessLookupError, PermissionError, OSError):
                target_pgid = proc.pid
        if target_pgid and target_pgid > 0:
            try:
                os.killpg(target_pgid, signal.SIGKILL)
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
    # With start_new_session=True, proc.pid is its pgid even after communicate() reaps proc.
    pgid: int | None = proc.pid if sys.platform != "win32" else None
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
            _kill_tree(proc, job_handle, pgid=pgid)
            job_handle = None
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout = stdout or ""
                stderr = stderr or ""
    finally:
        # Terminate any surviving descendants even when the root exited normally.
        _kill_tree(proc, job_handle, pgid=pgid)
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
    conversation_id = ""
    seen_tool_ids: set[str] = set()
    tool_uses: list[dict[str, object]] = []
    tool_results: list[dict[str, object]] = []
    delta_chunks: list[str] = []
    result_texts: list[str] = []
    result_events: list[dict[str, object]] = []
    steps: list[tuple[int, str, str]] = []
    step_events: list[dict[str, object]] = []

    for raw in ndjson.splitlines():
        line = raw.strip()
        if not line or not line.startswith("{"):
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            continue
        if not conversation_id and isinstance(event.get("conversation_id"), str):
            conversation_id = event["conversation_id"]
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
            step_events.append(su)
        if event_kind == "init" and isinstance(event.get("init"), dict):
            model = event["init"].get("model")
            if isinstance(model, str):
                init_models.append(model)
        elif etype == "init" and isinstance(event.get("model"), str):
            init_models.append(event["model"])

        if event_kind == "result" and isinstance(event.get("result"), dict):
            res = event["result"]
            if not conversation_id and isinstance(res.get("conversation_id"), str):
                conversation_id = res["conversation_id"]
            result_events.append(res)
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
        "conversation_id": conversation_id,
        "models": init_models,
        "tool_uses": tool_uses,
        "tool_results": tool_results,
        "steps": steps,
        "step_events": step_events,
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
    if res.get("is_error") or status in {"error", "failed", "failure", "cancelled"}:
        raise AssertionError(f"{tool_name} tool_result reported failure: {res!r}")


def _results_for_call(
    call: dict[str, object],
    tool_results: list[dict[str, object]],
    consumed_indices: set[int],
) -> list[dict[str, object]]:
    """Return matching terminal tool_result records for one tool call."""
    call_id = str(call.get("id") or "")
    if call_id:
        matched: list[dict[str, object]] = []
        for idx, res in enumerate(tool_results):
            if str(res.get("id") or "") == call_id:
                consumed_indices.add(idx)
                matched.append(res)
        return matched
    call_name = str(call.get("name") or "")
    for idx, res in enumerate(tool_results):
        if idx in consumed_indices or str(res.get("id") or ""):
            continue
        if str(res.get("name") or "") == call_name:
            consumed_indices.add(idx)
            return [res]
    return []


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

    consumed_results: set[int] = set()
    for idx in exit_indices:
        matched_exit = _results_for_call(tool_uses[idx], tool_results, consumed_results)
        if not matched_exit:
            raise AssertionError("exit_plan_mode was called without a completion tool_result")
        for res in matched_exit:
            _assert_result_succeeded(res, "exit_plan_mode")

    post_exit_tools = [
        call for call in tool_uses[exit_indices[0] + 1 :] if call.get("name") != "exit_plan_mode"
    ]
    if not post_exit_tools:
        raise AssertionError("Orchestrator emitted no execution tool call after exit_plan_mode")

    for call in post_exit_tools:
        tool_name = str(call.get("name") or "tool")
        matched = _results_for_call(call, tool_results, consumed_results)
        if not matched:
            raise AssertionError(
                f"Orchestrator execution tool call {tool_name!r} did not complete: {call!r}"
            )
        for res in matched:
            _assert_result_succeeded(res, tool_name)
    return parsed


def _path_from_file_uri(uri: str) -> Path | None:
    """Resolve a file:// URI into a local filesystem Path."""
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file":
        return None
    local = urllib.request.url2pathname(parsed.path)
    return Path(local) if local else None


def _unwrap_json_str(value: object) -> str:
    """Decode transcript tool_call argument strings that may be double-JSON-encoded."""
    if not isinstance(value, str):
        return ""
    stripped = value.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        try:
            decoded = json.loads(stripped)
            if isinstance(decoded, str):
                return decoded
        except json.JSONDecodeError:
            return stripped.strip('"')
    return value


def _read_jsonl_records(path: Path) -> list[dict[str, object]]:
    """Load JSONL step dictionaries from a transcript file."""
    records: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            records.append(obj)
    return records


def _verify_subagent_transcript_completion(
    sub_cid: str,
    log_uri: str,
    parent_cid: str,
    launch_idx: int,
) -> str:
    """Verify completed subagent transcript send_message and matching parent SYSTEM_MESSAGE."""
    sub_log = _path_from_file_uri(log_uri)
    if sub_log is None or not sub_log.is_file():
        raise AssertionError(
            f"subagent {sub_cid!r} missing readable transcript at log_uri={log_uri!r}"
        )
    sub_records = _read_jsonl_records(sub_log)
    if not sub_records:
        raise AssertionError(f"subagent {sub_cid!r} transcript {sub_log} is empty")
    bad_statuses = {"ERROR", "FAILED", "FAILURE", "CANCELLED"}
    for rec in sub_records:
        rstatus = str(rec.get("status") or "").upper()
        if rstatus in bad_statuses or rec.get("error"):
            raise AssertionError(
                f"subagent {sub_cid!r} transcript recorded failed step: {rec!r}"
            )
    last_status = str(sub_records[-1].get("status") or "").upper()
    if last_status != "DONE":
        raise AssertionError(
            f"subagent {sub_cid!r} transcript did not end DONE (last={last_status!r})"
        )

    sent_messages: list[str] = []
    for idx, rec in enumerate(sub_records):
        tool_calls = rec.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tc in tool_calls:
            if not isinstance(tc, dict) or tc.get("name") != "send_message":
                continue
            args = tc.get("args")
            amap = args if isinstance(args, dict) else {}
            recipient = _unwrap_json_str(amap.get("Recipient"))
            message = _unwrap_json_str(amap.get("Message"))
            if parent_cid and recipient != parent_cid:
                continue
            if not message.strip():
                continue
            ack_ok = any(
                str(nxt.get("status") or "").upper() == "DONE"
                and "Message sent to" in str(nxt.get("content") or "")
                for nxt in sub_records[idx + 1 :]
            )
            if not ack_ok:
                raise AssertionError(
                    f"subagent {sub_cid!r} send_message lacked Message sent confirmation"
                )
            sent_messages.append(message)
    if not sent_messages:
        raise AssertionError(
            f"subagent {sub_cid!r} transcript recorded no completed send_message to {parent_cid!r}"
        )

    if len(sub_log.parents) < 4 or not parent_cid:
        raise AssertionError(
            f"cannot resolve parent transcript alongside {sub_log} for parent {parent_cid!r}"
        )
    parent_log = sub_log.parents[3] / parent_cid / ".system_generated" / "logs" / "transcript.jsonl"
    if not parent_log.is_file():
        raise AssertionError(f"parent transcript missing at {parent_log}")
    parent_records = _read_jsonl_records(parent_log)
    matched_parent = [
        rec
        for rec in parent_records
        if str(rec.get("type") or "").upper() == "SYSTEM_MESSAGE"
        and str(rec.get("status") or "").upper() == "DONE"
        and isinstance(rec.get("step_index"), int)
        and int(rec["step_index"]) > launch_idx
        and f"sender={sub_cid}" in str(rec.get("content") or "")
    ]
    if not matched_parent:
        raise AssertionError(
            f"parent transcript lacked post-launch SYSTEM_MESSAGE from sender={sub_cid!r}"
        )
    parent_msg = str(matched_parent[-1].get("content") or "")
    if not any(sent.strip() and sent.strip() in parent_msg for sent in sent_messages):
        raise AssertionError(
            f"parent SYSTEM_MESSAGE did not carry subagent {sub_cid!r} reply: {parent_msg!r}"
        )
    return "\n".join(sent_messages)


def _inline_system_message_reply(
    sub_cid: str,
    launch_idx: int,
    step_events: list[dict[str, object]],
) -> str | None:
    """Extract attributable completion reply from inline system_message events, if present."""
    for step in step_events:
        if str(step.get("step_type") or "").lower() != "system_message":
            continue
        raw_idx = step.get("step_index")
        step_idx = raw_idx if isinstance(raw_idx, int) else -1
        if step_idx <= launch_idx:
            continue
        sender = str(
            step.get("sender")
            or step.get("subagent_conversation_id")
            or step.get("source_conversation_id")
            or ""
        ).strip()
        content = str(step.get("content") or step.get("message") or step.get("text") or "")
        attributed = sender == sub_cid or f"sender={sub_cid}" in content
        if not attributed:
            continue
        state = str(step.get("state") or "").upper()
        err = step.get("error") or step.get("is_error")
        if state != "DONE" or err:
            raise AssertionError(
                f"subagent {sub_cid!r} system_message reported failure: {step!r}"
            )
        if not content.strip():
            raise AssertionError(
                f"subagent {sub_cid!r} system_message contained empty reply payload: {step!r}"
            )
        return content
    return None


def parse_subagent_delegation_stream(
    ndjson: str,
    *,
    expected_model_prefix: str = "gemini-pro-orchestrator",
    forbid_parent_tools: tuple[str, ...] = (),
) -> dict[str, object]:
    """Validate invoke_subagent delegation with attributable completion per launched subagent."""
    parsed = _parse_ndjson_stream(ndjson, expected_model_prefix=expected_model_prefix)
    tool_uses: list[dict[str, object]] = parsed["tool_uses"]  # type: ignore[assignment]
    tool_results: list[dict[str, object]] = parsed["tool_results"]  # type: ignore[assignment]
    step_events: list[dict[str, object]] = parsed["step_events"]  # type: ignore[assignment]
    parent_cid = str(parsed.get("conversation_id") or "")

    if forbid_parent_tools:
        forbidden = [
            call.get("name") for call in tool_uses if call.get("name") in forbid_parent_tools
        ]
        if forbidden:
            raise AssertionError(
                f"parent invoked forbidden direct inspection tools {forbidden!r} instead of delegating"
            )

    subagent_calls = [call for call in tool_uses if call.get("name") == "invoke_subagent"]
    if not subagent_calls:
        raise AssertionError(
            "stream did not invoke invoke_subagent (listing-only output is insufficient)"
        )

    subagent_results = _matching_tool_results("invoke_subagent", tool_uses, tool_results)
    if len(subagent_results) < len(subagent_calls):
        raise AssertionError("invoke_subagent call lacked a matching completion tool_result")

    launched: list[tuple[int, str, str]] = []
    for call, res in zip(subagent_calls, subagent_results):
        _assert_result_succeeded(res, "invoke_subagent")
        call_id = str(call.get("id") or "")
        tail = call_id.removeprefix("step-") if call_id.startswith("step-") else ""
        launch_idx = int(tail) if tail.isdigit() else -1
        out = res.get("output")
        if not isinstance(out, dict) or not isinstance(out.get("subagents"), list) or not out["subagents"]:
            raise AssertionError(f"invoke_subagent result missing subagents metadata: {res!r}")
        for entry in out["subagents"]:
            sub_cid = str(entry.get("conversation_id") or "").strip() if isinstance(entry, dict) else ""
            if not sub_cid:
                raise AssertionError(f"invoke_subagent result missing conversation_id: {entry!r}")
            log_uri = str(entry.get("log_uri") or "").strip()
            launched.append((launch_idx, sub_cid, log_uri))

    min_launch_idx = min(idx for idx, _, _ in launched)
    failed_wakeups = [
        step
        for step in step_events
        if str(step.get("step_type") or "").lower() == "system_message"
        and (
            min_launch_idx < 0
            or (isinstance(step.get("step_index"), int) and int(step["step_index"]) > min_launch_idx)
        )
        and (
            str(step.get("state") or "").upper() in {"ERROR", "FAILED", "FAILURE", "CANCELLED"}
            or step.get("error")
            or step.get("is_error")
        )
    ]
    if failed_wakeups:
        raise AssertionError(
            f"post-launch system_message reported failure: {failed_wakeups!r}"
        )

    post_launch_done_wakeups = [
        step
        for step in step_events
        if str(step.get("step_type") or "").lower() == "system_message"
        and str(step.get("state") or "").upper() == "DONE"
        and (
            min_launch_idx < 0
            or (isinstance(step.get("step_index"), int) and int(step["step_index"]) > min_launch_idx)
        )
        and not (step.get("error") or step.get("is_error"))
    ]
    if len(post_launch_done_wakeups) < len(launched):
        raise AssertionError(
            f"expected at least {len(launched)} post-launch DONE system_message wakeup(s), "
            f"got {len(post_launch_done_wakeups)}"
        )

    delegated_replies: list[str] = []
    for launch_idx, sub_cid, log_uri in launched:
        has_wakeup = any(
            str(step.get("step_type") or "").lower() == "system_message"
            and str(step.get("state") or "").upper() == "DONE"
            and (launch_idx < 0 or (isinstance(step.get("step_index"), int) and int(step["step_index"]) > launch_idx))
            and not (step.get("error") or step.get("is_error"))
            for step in step_events
        )
        if not has_wakeup:
            raise AssertionError(
                f"subagent {sub_cid!r} lacked post-launch DONE system_message wakeup"
            )

        inline_reply = _inline_system_message_reply(sub_cid, launch_idx, step_events)
        if inline_reply is not None:
            delegated_replies.append(inline_reply)
        elif log_uri:
            delegated_replies.append(
                _verify_subagent_transcript_completion(sub_cid, log_uri, parent_cid, launch_idx)
            )
        else:
            raise AssertionError(
                f"subagent {sub_cid!r} wakeup was unattributed (no matching sender={sub_cid!r} or log_uri)"
            )

    parsed["subagent_calls"] = subagent_calls
    parsed["subagent_results"] = subagent_results
    parsed["delegated_replies"] = delegated_replies
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
            expected_pre_bytes: dict[str, bytes] = {}
            for rel in retired_paths:
                dest = project / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                original_bytes = f"# legacy wrapper placeholder for {rel}\n".encode("utf-8")
                files_map[rel] = {
                    "kit": "base",
                    "sha256": hashlib.sha256(original_bytes).hexdigest(),
                }
                if rel == ".agents/agents/code-explorer.md":
                    content_bytes = original_bytes + b"# project customization\r\n"
                else:
                    content_bytes = original_bytes
                dest.write_bytes(content_bytes)
                expected_pre_bytes[rel] = content_bytes

            kits_file.write_text(json.dumps(kits_data, indent=2) + "\n", encoding="utf-8")

            custom_agent = project / ".agents" / "agents" / "custom-reviewer.md"
            custom_text = "# Project-specific custom agent definition\n"
            custom_agent.write_text(custom_text, encoding="utf-8")

            def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["git", *args],
                    cwd=str(project),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=check,
                )

            if os.name != "nt":
                (project / "scripts/agy-subagent.py").chmod(0o755)
            _git("init")
            _git("config", "core.autocrlf", "true")
            _git("config", "user.email", "test@example.com")
            _git("config", "user.name", "Test")
            _git("add", "-A")
            _git("commit", "-m", "chore: pre-migration baseline")
            _git("branch", "pre-orchestrator-migration")

            readme_text = (KIT_BASE / "README.md").read_text(encoding="utf-8")
            py_blocks = re.findall(r"```python\n(.*?)\n```", readme_text, re.DOTALL)
            self.assertGreaterEqual(len(py_blocks), 2, "backup and rollback python blocks missing in kits/base/README.md")
            archive_script, restore_script = py_blocks[0], py_blocks[1]

            # Synchronize two concurrent backup processes AFTER dst.exists() so both compete at os.link(tmp, dst).
            # Wrap both children in guaranteed process-tree teardown.
            subdir = project / "scripts"
            opt_env = os.environ.copy()
            opt_env["PYTHONOPTIMIZE"] = "1"
            barrier_dir = Path(tmp) / "barrier"
            barrier_dir.mkdir()
            sync_code = (
                "    import time\n"
                f"    b = pathlib.Path({str(barrier_dir)!r})\n"
                "    (b / f'ready-{os.getpid()}').write_text('1', encoding='utf-8')\n"
                "    deadline = time.monotonic() + 10.0\n"
                "    while len(list(b.glob('ready-*'))) < 2 and time.monotonic() < deadline:\n"
                "        time.sleep(0.02)\n"
                "    if len(list(b.glob('ready-*'))) < 2:\n"
                "        raise TimeoutError('overlap barrier expired before second process arrived')\n"
            )
            instrumented_archive = archive_script.replace("    os.link(tmp, dst)", sync_code + "    os.link(tmp, dst)", 1)
            self.assertIn("ready-", instrumented_archive)
            popen_kwargs: dict = {
                "cwd": str(subdir),
                "env": opt_env,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            }
            if os.name == "nt":
                popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            else:
                popen_kwargs["start_new_session"] = True
            procs: list[subprocess.Popen] = []
            try:
                for _ in range(2):
                    procs.append(subprocess.Popen([sys.executable, "-c", instrumented_archive], **popen_kwargs))
                outputs = [p.communicate(timeout=20) for p in procs]
            finally:
                for p in procs:
                    if p.poll() is None:
                        if os.name == "nt":
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                                capture_output=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            )
                        else:
                            with contextlib.suppress(ProcessLookupError):
                                os.killpg(p.pid, signal.SIGKILL)
                        p.wait(timeout=5)
            self.assertEqual(len(list(barrier_dir.glob("ready-*"))), 2)
            rcs = [p.returncode for p in procs]
            self.assertEqual(sorted([rc == 0 for rc in rcs]), [False, True], outputs)
            loser_stderr = outputs[0][1] if rcs[0] != 0 else outputs[1][1]
            self.assertIn("FileExistsError", loser_stderr)
            # Loser's temporary file must be cleaned up by finally.
            self.assertEqual(list((project / ".git").glob(".pre-orchestrator-migration.*.tmp")), [])
            archive_path = project / ".git" / "pre-orchestrator-migration.zip"
            self.assertTrue(archive_path.is_file())
            with zipfile.ZipFile(archive_path) as zf:
                self.assertIsNone(zf.testzip())
                self.assertEqual(
                    set(zf.namelist()),
                    set(retired_paths) | {".conclave/kits.json"},
                )

            diff_proc = _run_forge(["diff", str(project), "base"], check=False)
            self.assertEqual(diff_proc.returncode, 0, diff_proc.stderr)
            for rel in retired_paths:
                self.assertIn(rel, diff_proc.stdout)
                self.assertIn("project-only", diff_proc.stdout)

            update_proc = _run_forge(["update", str(project), "base"], check=False)
            self.assertEqual(update_proc.returncode, 0, update_proc.stderr)
            for rel in retired_paths:
                self.assertTrue((project / rel).is_file(), f"update removed {rel} unexpectedly")
            self.assertEqual(
                (project / ".agents/agents/code-explorer.md").read_bytes(),
                expected_pre_bytes[".agents/agents/code-explorer.md"],
            )
            self.assertEqual(custom_agent.read_text(encoding="utf-8"), custom_text)

            locally_modified = [
                rel
                for rel in retired_paths
                if hashlib.sha256((project / rel).read_bytes()).hexdigest()
                != files_map[rel]["sha256"]
            ]
            self.assertEqual(locally_modified, [".agents/agents/code-explorer.md"])

            # Preserve local customizations into a retained custom file before deleting retired paths.
            preserved_agent = project / ".agents" / "agents" / "preserved-code-explorer.md"
            preserved_agent.write_bytes((project / ".agents/agents/code-explorer.md").read_bytes())

            # Remove only the 6 retired SDK paths, update kits.json, and commit the cleanup.
            for rel in retired_paths:
                (project / rel).unlink()
            updated_kits = json.loads(kits_file.read_text(encoding="utf-8"))
            for rel in retired_paths:
                updated_kits["files"].pop(rel, None)
            kits_file.write_text(json.dumps(updated_kits, indent=2) + "\n", encoding="utf-8")

            _git("add", "-A")
            _git("commit", "-m", "chore: remove retired agy wrappers after preserving edits")

            self.assertEqual(custom_agent.read_text(encoding="utf-8"), custom_text)
            self.assertEqual(
                preserved_agent.read_bytes(),
                expected_pre_bytes[".agents/agents/code-explorer.md"],
            )
            for rel in retired_paths:
                self.assertFalse((project / rel).exists())

            post_diff = _run_forge(["diff", str(project), "base"], check=False)
            self.assertEqual(post_diff.returncode, 0, post_diff.stderr)
            for rel in retired_paths:
                self.assertNotIn(rel, post_diff.stdout)

            doctor_proc = _run_forge(["doctor", str(project), "base"], check=False)
            self.assertEqual(doctor_proc.returncode, 0, doctor_proc.stdout + doctor_proc.stderr)

            # Verify rollback via HEAD alone fails after commit, and plain checkout alters newlines under autocrlf=true.
            head_rollback = _git("checkout", "HEAD", "--", "scripts/agy-subagent.py", check=False)
            self.assertNotEqual(head_rollback.returncode, 0)

            _git("checkout", "pre-orchestrator-migration", "--", "scripts/agy-subagent.py")
            self.assertNotEqual(
                (project / "scripts/agy-subagent.py").read_bytes(),
                expected_pre_bytes["scripts/agy-subagent.py"],
            )

            # Reset the earlier plain-checkout demo file so all 6 retired paths are absent before corrupt-manifest check.
            _git("reset", "--hard", "HEAD")
            # Edit retained custom agent AND install a real second kit (reviewer) through Forge AFTER migration;
            # first verify a truncated kits.json fails rollback BEFORE mutating Git index or worktree.
            post_migration_custom = custom_text + "# post-migration edit\n"
            custom_agent.write_text(post_migration_custom, encoding="utf-8")
            later_install = _run_forge(["kit", str(project), "reviewer"], check=False)
            self.assertEqual(later_install.returncode, 0, later_install.stdout + later_install.stderr)
            valid_later_kits_bytes = kits_file.read_bytes()
            stage_before_corrupt = _git("ls-files", "--stage").stdout
            kits_file.write_text("{truncated", encoding="utf-8")
            bad_rb = subprocess.run([sys.executable, "-c", restore_script], cwd=str(subdir), capture_output=True, text=True)
            self.assertNotEqual(bad_rb.returncode, 0)
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_corrupt)
            for rel in retired_paths:
                self.assertFalse((project / rel).exists(), f"corrupt manifest mutated worktree: {rel}")

            kits_file.write_bytes(valid_later_kits_bytes)
            subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                check=True,
            )
            for rel, raw_bytes in expected_pre_bytes.items():
                self.assertTrue((project / rel).is_file(), f"rollback did not restore {rel}")
                self.assertEqual((project / rel).read_bytes(), raw_bytes, f"byte mismatch on {rel}")
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE((project / "scripts/agy-subagent.py").stat().st_mode), 0o755)
                self.assertEqual(stat.S_IMODE(kits_file.stat().st_mode), 0o644)
            restored_kits = json.loads(kits_file.read_text(encoding="utf-8"))
            self.assertIn("reviewer", restored_kits["kits"])
            self.assertIn(".conclave/reviewers.toml", restored_kits["files"])
            for rel in retired_paths:
                self.assertEqual(restored_kits["files"][rel], kits_data["files"][rel])
            self.assertEqual(custom_agent.read_text(encoding="utf-8"), post_migration_custom)
            # Forge diff loads and validates .conclave/kits.json via _check_record.
            post_rb_diff = _run_forge(["diff", str(project), "base"], check=False)
            self.assertEqual(post_rb_diff.returncode, 0, post_rb_diff.stdout + post_rb_diff.stderr)

            # Partial + ignored-wrapper rollback: remove test-runner.md before backup, and make git-runner.md
            # gitignored/untracked (present on disk and archived, absent from git ls-tree); remove all 6 registrations
            # on cleanup, then rollback from subdir and verify git-runner.md returns byte-for-byte and stays untracked.
            (project / ".agents/agents/test-runner.md").unlink()
            _git("rm", "--cached", ".agents/agents/git-runner.md")
            (project / ".gitignore").write_text(".agents/agents/git-runner.md\n", encoding="utf-8")
            _git("add", "-A")
            _git("commit", "-m", "chore: partial pre-migration baseline")
            partial_sha = _git("rev-parse", "HEAD").stdout.strip()
            archive_path.unlink()
            subprocess.run([sys.executable, "-c", archive_script], cwd=str(subdir), env=opt_env, check=True)
            for rel in retired_paths:
                if (project / rel).exists():
                    (project / rel).unlink()
            partial_kits = json.loads(kits_file.read_text(encoding="utf-8"))
            for rel in retired_paths:
                partial_kits["files"].pop(rel, None)
            kits_file.write_text(json.dumps(partial_kits, indent=2) + "\n", encoding="utf-8")
            _git("add", "-A")
            _git("commit", "-m", "chore: partial cleanup")
            partial_env = os.environ.copy()
            partial_env["RECOVERY_REF"] = partial_sha
            # Refusal on uncommitted edit: a differing existing gitignored wrapper must stop rollback before any
            # Git checkout or wrapper replacement, leaving the edit and Git index untouched.
            edited_bytes = b"# uncommitted local edit\n"
            (project / ".agents/agents/git-runner.md").write_bytes(edited_bytes)
            stage_before_edit_refusal = _git("ls-files", "--stage").stdout
            edit_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(edit_refusal.returncode, 0, "rollback must refuse differing existing wrapper")
            self.assertIn("git-runner.md", edit_refusal.stderr)
            self.assertEqual((project / ".agents/agents/git-runner.md").read_bytes(), edited_bytes)
            self.assertFalse((project / ".agents/agents/code-explorer.md").exists())
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_edit_refusal)
            (project / ".agents/agents/git-runner.md").unlink()
            # Refusal on staged-only edit: staging a customized tracked wrapper and unlinking its working copy
            # must stop rollback before mutating the index or worktree.
            (project / ".agents/agents/code-explorer.md").write_bytes(b"# staged customization\n")
            _git("add", ".agents/agents/code-explorer.md")
            (project / ".agents/agents/code-explorer.md").unlink()
            stage_with_custom = _git("ls-files", "--stage").stdout
            staged_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(staged_refusal.returncode, 0, "rollback must refuse conflicting staged entry")
            self.assertIn("code-explorer.md", staged_refusal.stderr)
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_with_custom)
            self.assertFalse((project / ".agents/agents/code-explorer.md").exists())
            _git("rm", "-q", "--cached", ".agents/agents/code-explorer.md")
            # Interrupted-retry safety: run the README restore script itself, interrupting immediately after
            # its `git restore` call returns; verify the wrapper is still absent from the worktree (proving
            # index-only restore; adding --worktree would fail here), then retry the unmodified script.
            interrupt_harness = (
                "import subprocess, sys\n"
                "_orig_run = subprocess.run\n"
                "def _wrapped_run(cmd, *a, **kw):\n"
                "    res = _orig_run(cmd, *a, **kw)\n"
                "    if isinstance(cmd, (list, tuple)) and 'restore' in cmd:\n"
                "        sys.exit(99)\n"
                "    return res\n"
                "subprocess.run = _wrapped_run\n"
                + restore_script
            )
            interrupted = subprocess.run(
                [sys.executable, "-c", interrupt_harness],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(interrupted.returncode, 99, interrupted.stderr)
            self.assertFalse(
                (project / ".agents/agents/code-explorer.md").exists(),
                "index-only restore must not write normalized bytes to worktree",
            )
            self.assertIn(".agents/agents/code-explorer.md", _git("ls-files", "--stage").stdout)
            # Hard-link safety: when an existing matching wrapper shares an inode with another file, atomic
            # os.replace must publish a fresh inode rather than writing through the hard link.
            linked_copy = project / ".agents/agents/preserved-hardlink.md"
            linked_copy.write_bytes(expected_pre_bytes[".agents/agents/git-runner.md"])
            os.link(linked_copy, project / ".agents/agents/git-runner.md")
            self.assertEqual(linked_copy.stat().st_ino, (project / ".agents/agents/git-runner.md").stat().st_ino)
            subprocess.run([sys.executable, "-c", restore_script], cwd=str(subdir), env=partial_env, check=True)
            self.assertNotEqual(linked_copy.stat().st_ino, (project / ".agents/agents/git-runner.md").stat().st_ino)
            linked_copy.unlink()
            self.assertFalse((project / ".agents/agents/test-runner.md").exists())
            self.assertEqual(
                (project / ".agents/agents/code-explorer.md").read_bytes(),
                expected_pre_bytes[".agents/agents/code-explorer.md"],
            )
            self.assertEqual(
                (project / ".agents/agents/git-runner.md").read_bytes(),
                expected_pre_bytes[".agents/agents/git-runner.md"],
            )
            self.assertEqual(custom_agent.read_text(encoding="utf-8"), post_migration_custom)
            self.assertEqual(
                _git("ls-files", ".agents/agents/git-runner.md").stdout.strip(),
                "",
            )
            restored_partial_kits = json.loads(kits_file.read_text(encoding="utf-8"))
            self.assertIn(".agents/agents/test-runner.md", restored_partial_kits["files"])
            self.assertEqual(
                preserved_agent.read_bytes(),
                expected_pre_bytes[".agents/agents/code-explorer.md"],
            )
            # Staged-deletion and unstaged-deletion refusals: after committing the restored wrapper, either an
            # unstaged filesystem deletion or a staged `git rm` must stop rollback before mutation.
            _git("add", ".agents/agents/code-explorer.md")
            _git("commit", "-m", "chore: commit restored wrapper")
            (project / ".agents/agents/code-explorer.md").unlink()
            unstaged_del_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unstaged_del_refusal.returncode, 0, "rollback must refuse undoing unstaged deletion")
            self.assertIn("code-explorer.md", unstaged_del_refusal.stderr)
            self.assertFalse((project / ".agents/agents/code-explorer.md").exists())
            _git("rm", "-q", ".agents/agents/code-explorer.md")
            stage_before_del_refusal = _git("ls-files", "--stage").stdout
            del_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(del_refusal.returncode, 0, "rollback must refuse undoing a staged deletion")
            self.assertIn("code-explorer.md", del_refusal.stderr)
            self.assertFalse((project / ".agents/agents/code-explorer.md").exists())
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_del_refusal)
            _git("reset", "-q", "--hard", "HEAD~1")
            # Conflicting manifest-ownership refusal: if another kit owns a retired path in .conclave/kits.json,
            # rollback must stop before mutating the manifest or worktree and preserve that owner.
            conflict_kits = json.loads(kits_file.read_text(encoding="utf-8"))
            conflict_entry = {"kit": "reviewer", "sha256": kits_data["files"][".agents/agents/code-explorer.md"]["sha256"]}
            conflict_kits["files"][".agents/agents/code-explorer.md"] = conflict_entry
            kits_file.write_text(json.dumps(conflict_kits, indent=2) + "\n", encoding="utf-8")
            owner_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(owner_refusal.returncode, 0, "rollback must refuse conflicting manifest ownership")
            self.assertIn("code-explorer.md", owner_refusal.stderr)
            self.assertEqual(
                json.loads(kits_file.read_text(encoding="utf-8"))["files"][".agents/agents/code-explorer.md"],
                conflict_entry,
            )
            _git("checkout", "--", ".conclave/kits.json")
            # Unified guard on archive-only wrapper (git-runner.md), staged descendants, and tracked manifest:
            # 1) Committed unchanged archive-only wrapper must NOT block rollback; deleting it in worktree must refuse.
            (project / ".agents/agents/git-runner.md").write_bytes(expected_pre_bytes[".agents/agents/git-runner.md"])
            _git("add", "-f", ".agents/agents/git-runner.md")
            _git("commit", "-m", "chore: track archive-only wrapper")
            subprocess.run([sys.executable, "-c", restore_script], cwd=str(subdir), env=partial_env, check=True)
            (project / ".agents/agents/git-runner.md").unlink()
            stage_before_arc_del = _git("ls-files", "--stage").stdout
            arc_del_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(arc_del_refusal.returncode, 0, "rollback must refuse undoing deletion of committed archive-only wrapper")
            self.assertIn("pending deletion would be undone", arc_del_refusal.stderr)
            self.assertIn("git-runner.md", arc_del_refusal.stderr)
            self.assertFalse((project / ".agents/agents/git-runner.md").exists())
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_arc_del)
            _git("reset", "-q", "--hard", "HEAD~1")
            # 2) Staged descendant beneath a retired wrapper path must refuse without mutating the index.
            desc_dir = project / ".agents/agents/code-explorer.md"
            desc_dir.mkdir(parents=True)
            (desc_dir / "nested.txt").write_text("descendant\n", encoding="utf-8")
            _git("add", ".agents/agents/code-explorer.md/nested.txt")
            shutil.rmtree(desc_dir)
            stage_before_desc = _git("ls-files", "--stage").stdout
            desc_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(desc_refusal.returncode, 0, "rollback must refuse staged descendant")
            self.assertIn("staged descendant blocks restore", desc_refusal.stderr)
            self.assertIn("code-explorer.md/nested.txt", desc_refusal.stderr)
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_desc)
            _git("rm", "-q", "--cached", ".agents/agents/code-explorer.md/nested.txt")
            # 3) Tracked .conclave/kits.json unstaged deletion, staged deletion, and single stage-2 unmerged entry.
            kits_file.unlink()
            stage_before_kits_del = _git("ls-files", "--stage").stdout
            kits_del_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(kits_del_refusal.returncode, 0, "rollback must refuse resurrecting unstaged-deleted kits.json")
            self.assertIn("pending deletion would be undone", kits_del_refusal.stderr)
            self.assertIn(".conclave/kits.json", kits_del_refusal.stderr)
            self.assertFalse(kits_file.exists())
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_kits_del)
            # Restore working copy before `git rm --cached` so staged-deletion guard is proven independently.
            _git("checkout", "HEAD", "--", ".conclave/kits.json")
            kits_bytes_before_cached_rm = kits_file.read_bytes()
            _git("rm", "-q", "--cached", ".conclave/kits.json")
            stage_before_kits_staged_del = _git("ls-files", "--stage").stdout
            kits_staged_del = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(kits_staged_del.returncode, 0, "rollback must refuse resurrecting staged-deleted kits.json")
            self.assertIn("pending deletion would be undone", kits_staged_del.stderr)
            self.assertIn(".conclave/kits.json", kits_staged_del.stderr)
            self.assertEqual(kits_file.read_bytes(), kits_bytes_before_cached_rm)
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_kits_staged_del)
            _git("checkout", "HEAD", "--", ".conclave/kits.json")
            kits_oid = _git("rev-parse", "HEAD:.conclave/kits.json").stdout.strip()
            _git("rm", "-q", "--cached", ".conclave/kits.json")
            subprocess.run(
                ["git", "-C", str(project), "update-index", "--index-info"],
                input=f"100644 {kits_oid} 2\t.conclave/kits.json\n".encode("utf-8"),
                check=True,
            )
            stage_before_unmerged = _git("ls-files", "--stage").stdout
            unmerged_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(unmerged_refusal.returncode, 0, "rollback must refuse single stage-2 unmerged kits.json")
            self.assertIn("unmerged index entry", unmerged_refusal.stderr)
            self.assertIn(".conclave/kits.json", unmerged_refusal.stderr)
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_unmerged)
            _git("reset", "-q", "--hard", "HEAD")
            # 4) Directory at .conclave/kits.json after manifest removal must refuse before restoring wrappers.
            _git("rm", "-q", ".conclave/kits.json")
            _git("commit", "-m", "chore: remove optional manifest")
            kits_file.mkdir()
            stage_before_kits_dir = _git("ls-files", "--stage").stdout
            kits_dir_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(kits_dir_refusal.returncode, 0, "rollback must refuse directory at .conclave/kits.json")
            self.assertIn("existing path is not a regular file", kits_dir_refusal.stderr)
            self.assertFalse((project / ".agents/agents/code-explorer.md").exists())
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_kits_dir)
            kits_file.rmdir()
            _git("reset", "-q", "--hard", "HEAD~1")
            # 5) Regular file staged at parent path .agents/agents must refuse before mutating index or worktree.
            shutil.rmtree(project / ".agents/agents")
            (project / ".agents/agents").write_text("file-blocking-parent\n", encoding="utf-8")
            _git("add", ".agents/agents")
            stage_before_parent_file = _git("ls-files", "--stage").stdout
            parent_file_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(parent_file_refusal.returncode, 0, "rollback must refuse file at parent path")
            self.assertIn("parent path is not a directory", parent_file_refusal.stderr)
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_parent_file)
            (project / ".agents/agents").unlink()
            stage_before_indexed_parent = _git("ls-files", "--stage").stdout
            indexed_parent_refusal = subprocess.run(
                [sys.executable, "-c", restore_script],
                cwd=str(subdir),
                env=partial_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(indexed_parent_refusal.returncode, 0, "rollback must refuse indexed file at parent path")
            self.assertIn("indexed file blocks parent directory", indexed_parent_refusal.stderr)
            self.assertEqual(_git("ls-files", "--stage").stdout, stage_before_indexed_parent)
            _git("reset", "-q", "--hard", "HEAD")

            # Junction (Windows) / symlink (POSIX) parent-directory refusal before backup or rollback mutation.
            shared_dir = Path(tmp) / "shared-agents"
            shared_dir.mkdir()
            sentinel = shared_dir / "code-explorer.md"
            sentinel.write_bytes(b"shared-secret\n")
            shutil.rmtree(project / ".agents/agents")
            link_target = project / ".agents/agents"
            if os.name == "nt":
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link_target), str(shared_dir)],
                    check=True,
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                os.symlink(str(shared_dir), str(link_target), target_is_directory=True)
            try:
                valid_partial_archive = archive_path.read_bytes()
                archive_path.unlink()
                j_bk = subprocess.run([sys.executable, "-c", archive_script], cwd=str(subdir), env=opt_env, capture_output=True, text=True)
                self.assertNotEqual(j_bk.returncode, 0)
                self.assertIn("link not allowed", j_bk.stderr)
                self.assertFalse(archive_path.exists())
                # Keep the valid partial-install archive so rollback must fail specifically at check_no_links.
                archive_path.write_bytes(valid_partial_archive)
                j_rb = subprocess.run([sys.executable, "-c", restore_script], cwd=str(subdir), env=partial_env, capture_output=True, text=True)
                self.assertNotEqual(j_rb.returncode, 0)
                self.assertIn("link not allowed", j_rb.stderr)
                self.assertEqual(sentinel.read_bytes(), b"shared-secret\n")
            finally:
                if os.name == "nt":
                    subprocess.run(
                        ["cmd", "/c", "rmdir", str(link_target)],
                        capture_output=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                else:
                    link_target.unlink(missing_ok=True)

    def test_docs_self_sync_and_review_pin_orchestrator_helpers(self) -> None:
        readme = (KIT_BASE / "README.md").read_text(encoding="utf-8")
        subagents_start = readme.index("## Subagents across the three writers")
        migration_start = readme.index("### Moving Antigravity to Gemini 4 Neon")
        active_section = readme[subagents_start:migration_start]
        self.assertIn("agy --model gemini-4-neon-medium --effort=medium", active_section)
        self.assertNotIn("Carbon", active_section)
        self.assertNotIn("Hydrogen", active_section)
        self.assertIn("### Moving Antigravity to Gemini 4 Neon", readme)
        self.assertIn("### Historical live verification (Orchestrator", readme)
        self.assertIn("--model gemini-pro-orchestrator", readme)
        self.assertIn(".agents/agents/<custom>.md", readme)
        self.assertIn("pre-orchestrator-migration", readme)
        self.assertIn("pre-orchestrator-migration.zip", readme)
        self.assertIn("--git-path", readme)
        self.assertIn("--show-toplevel", readme)
        self.assertIn('"--staged"', readme)
        self.assertIn("preserved-code-explorer.md", readme)
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
    sub_cid: str = "sub-1",
    log_uri: str = "",
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
    done_entry: dict[str, object] = {**sub_entry, "conversation_id": sub_cid}
    if log_uri:
        done_entry["log_uri"] = log_uri
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


def _write_transcript_fixture(
    brain_root: Path,
    parent_cid: str,
    sub_cid: str,
    *,
    parent_sys_sender: str | None = None,
    sub_reply: str = "halve is at line 5 returning n / 2.",
    sub_final_status: str = "DONE",
    sub_send_ack: bool = True,
    parent_sys_step_index: int = 5,
    omit_sub_send: bool = False,
) -> Path:
    """Create agy 1.5.8 parent and subagent transcript.jsonl files and return sub_log Path."""
    sub_log = brain_root / sub_cid / ".system_generated" / "logs" / "transcript.jsonl"
    sub_log.parent.mkdir(parents=True, exist_ok=True)
    sub_steps: list[dict[str, object]] = [
        {"step_index": 0, "type": "SYSTEM_MESSAGE", "status": "DONE", "content": f"sender={parent_cid}"},
        {"step_index": 1, "type": "PLANNER_RESPONSE", "status": "DONE", "tool_calls": [{"name": "read_file", "args": {"Path": "calc.py"}}]},
    ]
    if not omit_sub_send:
        sub_steps.append(
            {
                "step_index": 2,
                "type": "PLANNER_RESPONSE",
                "status": "DONE",
                "tool_calls": [
                    {
                        "name": "send_message",
                        "args": {
                            "Recipient": json.dumps(parent_cid),
                            "Message": json.dumps(sub_reply),
                        },
                    }
                ],
            }
        )
        if sub_send_ack:
            sub_steps.append(
                {
                    "step_index": 3,
                    "type": "GENERIC",
                    "status": "DONE",
                    "content": f'Message sent to "{parent_cid}".',
                }
            )
    sub_steps.append(
        {
            "step_index": 4,
            "type": "PLANNER_RESPONSE",
            "status": sub_final_status,
            "content": "Completed.",
        }
    )
    sub_log.write_text("\n".join(json.dumps(s) for s in sub_steps) + "\n", encoding="utf-8")

    parent_log = brain_root / parent_cid / ".system_generated" / "logs" / "transcript.jsonl"
    parent_log.parent.mkdir(parents=True, exist_ok=True)
    parent_steps: list[dict[str, object]] = [
        {"step_index": 0, "type": "USER_INPUT", "status": "DONE", "content": "delegate"},
    ]
    if parent_sys_sender is not None:
        parent_steps.append(
            {
                "step_index": parent_sys_step_index,
                "type": "SYSTEM_MESSAGE",
                "status": "DONE",
                "content": f"[Message] sender={parent_sys_sender} content={sub_reply}",
            }
        )
    parent_log.write_text("\n".join(json.dumps(s) for s in parent_steps) + "\n", encoding="utf-8")
    return sub_log


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
        with _temp_dir_released_by_its_tree() as tmp:
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

    def test_normal_exit_kills_detached_descendant_process_tree(self) -> None:
        child_script = """
import subprocess, sys, time
from pathlib import Path

pid_file = Path(sys.argv[1])
if len(sys.argv) == 2:
    grand = subprocess.Popen(
        [sys.executable, __file__, str(pid_file), "grandchild"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    pid_file.write_text(str(grand.pid), encoding="utf-8")
else:
    time.sleep(60)
"""
        with _temp_dir_released_by_its_tree() as tmp:
            tmp_path = Path(tmp)
            script = tmp_path / "spawn_and_exit.py"
            grand_pid_file = tmp_path / "grand.pid"
            script.write_text(child_script.strip() + "\n", encoding="utf-8")

            rc, _, stderr, timed_out = _run_bounded_subprocess(
                [sys.executable, str(script), str(grand_pid_file)],
                cwd=tmp_path,
                timeout=10.0,
            )
            self.assertFalse(timed_out, f"spawn_and_exit.py timed out; stderr={stderr}")
            self.assertEqual(rc, 0, stderr)
            self.assertTrue(grand_pid_file.is_file(), "child did not spawn grandchild")
            grand_pid = int(grand_pid_file.read_text(encoding="utf-8").strip())

            deadline = time.monotonic() + 3.0
            while _is_pid_alive(grand_pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(
                _is_pid_alive(grand_pid),
                f"detached descendant PID {grand_pid} survived parent exit cleanup",
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
        inline_stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator-argon"),
                *_agy_subagent_pair(3, "research", sub_cid="sub-1"),
                json.dumps(
                    {
                        "event": "step_update",
                        "step_update": {
                            "conversation_id": "c1",
                            "step_index": 5,
                            "state": "DONE",
                            "step_type": "system_message",
                            "sender": "sub-1",
                            "content": "[Message] sender=sub-1 halve is on line 5 returning n / 2.",
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
        inline_parsed = parse_subagent_delegation_stream(
            inline_stream, forbid_parent_tools=("read_file",)
        )
        self.assertIn("n / 2", "\n".join(inline_parsed["delegated_replies"]))  # type: ignore[arg-type]
        self.assertIn("line 5", str(inline_parsed["assistant_text"]))

        with tempfile.TemporaryDirectory() as tmp:
            sub_log = _write_transcript_fixture(
                Path(tmp),
                "c1",
                "sub-1",
                parent_sys_sender="sub-1",
                sub_reply="halve is on line 5 returning n / 2.",
            )
            transcript_stream = "\n".join(
                [
                    _agy_init_line("gemini-pro-orchestrator-argon"),
                    *_agy_subagent_pair(3, "research", sub_cid="sub-1", log_uri=sub_log.as_uri()),
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
                    _agy_result_line("SUCCESS", "halve is on line 5 of calc.py and returns n / 2."),
                ]
            )
            transcript_parsed = parse_subagent_delegation_stream(
                transcript_stream, forbid_parent_tools=("read_file",)
            )
        replies_text = "\n".join(transcript_parsed["delegated_replies"])  # type: ignore[arg-type]
        self.assertIn("n / 2", replies_text)
        self.assertRegex(replies_text, r"\b5\b")
        self.assertIn("line 5", str(transcript_parsed["assistant_text"]))

    def test_rejects_listing_only_output_without_invoke_subagent(self) -> None:
        stream = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                _agy_result_line("SUCCESS", "Available subagents: self, research, image-generator."),
            ]
        )
        with self.assertRaises(AssertionError):
            parse_subagent_delegation_stream(stream)

    def test_rejects_failed_unattributed_or_direct_inspection_delegation(self) -> None:
        right_answer = "halve is on line 5 of calc.py and returns n / 2."
        redacted_wakeup = json.dumps(
            {
                "event": "step_update",
                "step_update": {
                    "conversation_id": "c1",
                    "step_index": 5,
                    "state": "DONE",
                    "step_type": "system_message",
                },
            }
        )
        inline_cases: list[tuple[str, list[str], tuple[str, ...]]] = [
            (
                "failed invoke_subagent",
                [
                    *_agy_subagent_pair(3, "research", state="ERROR", error="subagent launch denied"),
                    redacted_wakeup,
                ],
                (),
            ),
            (
                "incomplete invoke_subagent",
                [_agy_subagent_pair(3, "research")[0], redacted_wakeup],
                (),
            ),
            (
                "launch without wakeup",
                [*_agy_subagent_pair(3, "research")],
                (),
            ),
            (
                "unattributed system_message without sender or log_uri",
                [*_agy_subagent_pair(3, "research"), redacted_wakeup],
                (),
            ),
            (
                "inline system_message from unrelated sender",
                [
                    *_agy_subagent_pair(3, "research", sub_cid="sub-1"),
                    json.dumps(
                        {
                            "event": "step_update",
                            "step_update": {
                                "conversation_id": "c1",
                                "step_index": 5,
                                "state": "DONE",
                                "step_type": "system_message",
                                "sender": "sub-unrelated",
                                "content": f"[Message] sender=sub-unrelated {right_answer}",
                            },
                        }
                    ),
                ],
                (),
            ),
            (
                "failed inline system_message",
                [
                    *_agy_subagent_pair(3, "research", sub_cid="sub-1"),
                    json.dumps(
                        {
                            "event": "step_update",
                            "step_update": {
                                "conversation_id": "c1",
                                "step_index": 5,
                                "state": "ERROR",
                                "step_type": "system_message",
                                "error": "subagent failed",
                            },
                        }
                    ),
                ],
                (),
            ),
            (
                "parent used forbidden direct read tool",
                [
                    *_agy_tool_pair(2, "read_file", parameters={"Path": "calc.py"}, output=right_answer),
                    *_agy_subagent_pair(3, "research", sub_cid="sub-1"),
                    json.dumps(
                        {
                            "event": "step_update",
                            "step_update": {
                                "conversation_id": "c1",
                                "step_index": 5,
                                "state": "DONE",
                                "step_type": "system_message",
                                "sender": "sub-1",
                                "content": f"[Message] sender=sub-1 {right_answer}",
                            },
                        }
                    ),
                ],
                ("read_file",),
            ),
            (
                "two subagents launched with only one DONE wakeup",
                [
                    *_agy_subagent_pair(3, "research", sub_cid="sub-1"),
                    *_agy_subagent_pair(4, "research", sub_cid="sub-2"),
                    json.dumps(
                        {
                            "event": "step_update",
                            "step_update": {
                                "conversation_id": "c1",
                                "step_index": 5,
                                "state": "DONE",
                                "step_type": "system_message",
                                "sender": "sub-1",
                                "content": f"[Message] sender=sub-1 {right_answer}",
                            },
                        }
                    ),
                ],
                (),
            ),
            (
                "mixed DONE and ERROR system_message wakeups",
                [
                    *_agy_subagent_pair(3, "research", sub_cid="sub-1"),
                    json.dumps(
                        {
                            "event": "step_update",
                            "step_update": {
                                "conversation_id": "c1",
                                "step_index": 5,
                                "state": "DONE",
                                "step_type": "system_message",
                                "sender": "sub-1",
                                "content": f"[Message] sender=sub-1 {right_answer}",
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "event": "step_update",
                            "step_update": {
                                "conversation_id": "c1",
                                "step_index": 6,
                                "state": "ERROR",
                                "step_type": "system_message",
                                "error": "secondary wakeup failed",
                            },
                        }
                    ),
                ],
                (),
            ),
        ]
        for label, events, forbidden in inline_cases:
            with self.subTest(case=label):
                stream = "\n".join(
                    [_agy_init_line("gemini-pro-orchestrator"), *events, _agy_result_line("SUCCESS", right_answer)]
                )
                with self.assertRaises(AssertionError):
                    parse_subagent_delegation_stream(stream, forbid_parent_tools=forbidden)

        transcript_cases: list[tuple[str, dict[str, object]]] = [
            ("unrelated sender in parent transcript", {"parent_sys_sender": "sub-unrelated"}),
            ("missing parent SYSTEM_MESSAGE reply", {"parent_sys_sender": None}),
            ("missing subagent send_message", {"parent_sys_sender": "sub-1", "omit_sub_send": True}),
            ("unconfirmed send_message", {"parent_sys_sender": "sub-1", "sub_send_ack": False}),
            ("failed subagent final status", {"parent_sys_sender": "sub-1", "sub_final_status": "ERROR"}),
        ]
        for label, fixture_kwargs in transcript_cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                sub_log = _write_transcript_fixture(Path(tmp), "c1", "sub-1", **fixture_kwargs)  # type: ignore[arg-type]
                stream = "\n".join(
                    [
                        _agy_init_line("gemini-pro-orchestrator"),
                        *_agy_subagent_pair(3, "research", sub_cid="sub-1", log_uri=sub_log.as_uri()),
                        redacted_wakeup,
                        _agy_result_line("SUCCESS", right_answer),
                    ]
                )
                with self.assertRaises(AssertionError):
                    parse_subagent_delegation_stream(stream)

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

    def test_rejects_incomplete_or_failed_execution_after_exit_plan_mode(self) -> None:
        active_only_exec = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(3, "exit_plan_mode", output="Plan mode is off."),
                _agy_tool_pair(4, "edit_file", parameters={"Path": "calc.py"})[0],
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaisesRegex(AssertionError, "did not complete"):
            parse_orchestrator_stream(active_only_exec)

        failed_exec_with_error = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(3, "exit_plan_mode", output="Plan mode is off."),
                *_agy_tool_pair(4, "edit_file", state="ERROR", error="permission denied"),
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaisesRegex(AssertionError, "reported failure"):
            parse_orchestrator_stream(failed_exec_with_error)

        failed_exec_state_only = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(3, "exit_plan_mode", output="Plan mode is off."),
                *_agy_tool_pair(4, "edit_file", state="ERROR"),
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaisesRegex(AssertionError, "reported failure"):
            parse_orchestrator_stream(failed_exec_state_only)

        active_second_exit = "\n".join(
            [
                _agy_init_line("gemini-pro-orchestrator"),
                *_agy_tool_pair(3, "exit_plan_mode", output="Plan mode is off."),
                _agy_tool_pair(4, "exit_plan_mode")[0],
                *_agy_tool_pair(5, "edit_file", parameters={"Path": "calc.py"}),
                _agy_result_line("SUCCESS"),
            ]
        )
        with self.assertRaisesRegex(AssertionError, "exit_plan_mode"):
            parse_orchestrator_stream(active_second_exit)


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
                "Do NOT read calc.py directly in this parent session; do not call read_file, "
                "view_file, grep_search, find_by_name, list_dir, or run_command. "
                "Call invoke_subagent once with TypeName='research' to read calc.py, find the "
                "exact 1-based line number of `def halve` and the expression it returns, and report "
                "them back with send_message. Wait for the subagent reply (stop calling other tools "
                "until it replies), then report the exact line number and returned expression."
            )
            rc, stdout, stderr, timed_out = _run_agy(prompt, cwd=ws, timeout=240.0)
            try:
                self.assertFalse(timed_out, f"agy timed out; stderr={stderr}")
                self.assertEqual(rc, 0, f"agy rc={rc}; stderr={stderr}\nstdout={stdout[-1200:]}")
                parsed = parse_subagent_delegation_stream(
                    stdout,
                    forbid_parent_tools=(
                        "read_file",
                        "file_read",
                        "view_file",
                        "grep_search",
                        "find_by_name",
                        "list_dir",
                        "run_command",
                        "run_in_terminal",
                    ),
                )
                delegated = "\n".join(parsed["delegated_replies"])  # type: ignore[arg-type]
                assistant = str(parsed["assistant_text"])
                for label, body in (("delegated_replies", delegated), ("assistant_text", assistant)):
                    self.assertRegex(body, r"\b5\b", f"expected line 5 in {label}:\n{body}")
                    self.assertIn("n / 2", body, f"expected 'n / 2' in {label}:\n{body}")
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
            v_rc, v_out, v_err, v_timed_out = _run_bounded_subprocess(
                [sys.executable, "-m", "unittest", "tests.test_calc"],
                cwd=ws,
                timeout=30.0,
            )
            self.assertFalse(v_timed_out, f"tests.test_calc timed out; stderr={v_err}")
            self.assertEqual(v_rc, 0, v_out + v_err)


if __name__ == "__main__":
    unittest.main()
