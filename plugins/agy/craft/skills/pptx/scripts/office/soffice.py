"""
Helper for running LibreOffice (soffice) in environments where AF_UNIX
sockets may be blocked (e.g., sandboxed VMs).  Detects the restriction
at runtime and applies an LD_PRELOAD shim if needed.

Usage:
    from office.soffice import run_soffice

    result = run_soffice(["--headless", "--convert-to", "pdf", "input.docx"])

Call soffice through run_soffice, not through subprocess with get_soffice_env():
the env dict carries the shim but names no user profile, and a non-root sandbox
cannot bootstrap the default one -- soffice aborts with "User installation could
not be completed" and converts nothing. get_soffice_env() stays public for the
callers that build their own argv (they must pass -env:UserInstallation too).
"""

import contextlib
import ctypes
import os
import signal
import socket
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path


def get_soffice_env() -> dict:
    env = os.environ.copy()
    env["SAL_USE_VCLPLUGIN"] = "svp"

    if _needs_shim():
        shim = _ensure_shim()
        env["LD_PRELOAD"] = str(shim)

    return env


_CREATE_SUSPENDED = 0x00000004
_JOB_EXTENDED_LIMIT_CLASS = 9
_JOB_KILL_ON_CLOSE = 0x00002000


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


_WIN32_APIS = None


def _win32():
    global _WIN32_APIS
    if _WIN32_APIS is None:
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
        _WIN32_APIS = kernel32, ntdll
    return _WIN32_APIS


def _open_windows_job():
    kernel32, _ = _win32()
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = _JOB_KILL_ON_CLOSE
    if not kernel32.SetInformationJobObject(job, _JOB_EXTENDED_LIMIT_CLASS, ctypes.byref(info), ctypes.sizeof(info)):
        err = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(err)
    return job


def _close_windows_job(job) -> None:
    if job is None:
        return
    kernel32, _ = _win32()
    kernel32.TerminateJobObject(job, 1)
    kernel32.CloseHandle(job)


def _assign_and_resume_windows(job, proc: subprocess.Popen):
    kernel32, ntdll = _win32()
    handle_val = getattr(proc, "_handle", None)
    if not isinstance(handle_val, int):
        kernel32.CloseHandle(job)
        return None
    proc_handle = ctypes.c_void_p(int(handle_val))
    assigned = kernel32.AssignProcessToJobObject(job, proc_handle)
    if not assigned:
        kernel32.CloseHandle(job)
        job = None
    status = ntdll.NtResumeProcess(proc_handle)
    if status != 0:
        if job is not None:
            _close_windows_job(job)
        raise OSError(f"NtResumeProcess returned 0x{status & 0xFFFFFFFF:08x}")
    return job


def _terminate_process_tree(proc: subprocess.Popen, job_ref: list | None = None) -> None:
    if os.name == "nt":
        job = job_ref[0] if job_ref else None
        if job is not None:
            job_ref[0] = None
            _close_windows_job(job)
        else:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    creationflags=flags,
                    check=False,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            proc.kill()
        except OSError:
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass


def run_process_tree(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run cmd and kill its entire owned process tree on timeout or abort."""
    cmd = list(cmd)
    timeout = kwargs.pop("timeout", None)
    check = kwargs.pop("check", False)
    capture_output = kwargs.pop("capture_output", False)
    input_data = kwargs.pop("input", None)
    if capture_output:
        if "stdout" in kwargs or "stderr" in kwargs:
            raise ValueError("stdout and stderr arguments may not be used with capture_output.")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    kwargs.setdefault("stdin", subprocess.DEVNULL if input_data is None else subprocess.PIPE)
    job = None
    if os.name == "nt":
        job = _open_windows_job()
        kwargs["creationflags"] = (
            kwargs.get("creationflags", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | _CREATE_SUSPENDED
        )
    else:
        kwargs.setdefault("start_new_session", True)

    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except BaseException:
        if os.name == "nt" and job is not None:
            _close_windows_job(job)
        raise
    job_ref = [None]
    try:
        if os.name == "nt" and job is not None:
            job_ref[0] = _assign_and_resume_windows(job, proc)
            job = None
        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(proc, job_ref)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = None, None
            raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)
        except BaseException:
            _terminate_process_tree(proc, job_ref)
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            raise
    finally:
        if os.name == "nt":
            if job_ref[0] is not None:
                _close_windows_job(job_ref[0])
                job_ref[0] = None
            elif job is not None:
                _close_windows_job(job)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
    completed = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd, output=stdout, stderr=stderr)
    return completed


def run_soffice(args: Iterable[str], **kwargs) -> subprocess.CompletedProcess:
    args = list(args)
    env = kwargs.pop("env", None)
    if env is None:
        env = get_soffice_env()
    with contextlib.ExitStack() as stack:
        if not any(str(a).startswith("-env:UserInstallation") for a in args):
            profile = stack.enter_context(
                tempfile.TemporaryDirectory(prefix="lo_profile_", ignore_cleanup_errors=True)
            )
            args = [f"-env:UserInstallation={Path(profile).as_uri()}"] + args
        cmd = ["soffice"] + args
        return run_process_tree(cmd, env=env, **kwargs)



_SHIM_SO = Path(tempfile.gettempdir()) / "lo_socket_shim.so"


def _needs_shim() -> bool:
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.close()
        return False
    except OSError:
        return True


def _ensure_shim() -> Path:
    if _SHIM_SO.exists():
        return _SHIM_SO

    fd, tmp_so_name = tempfile.mkstemp(
        prefix="lo_socket_shim.", suffix=".so", dir=_SHIM_SO.parent
    )
    os.close(fd)
    tmp_so = Path(tmp_so_name)
    try:
        with tempfile.TemporaryDirectory(
            prefix="lo_shim_src_", ignore_cleanup_errors=True
        ) as src_dir:
            src = Path(src_dir) / "lo_socket_shim.c"
            src.write_text(_SHIM_SOURCE, encoding="utf-8")
            run_process_tree(
                ["gcc", "-shared", "-fPIC", "-o", str(tmp_so), str(src), "-ldl"],
                check=True,
                capture_output=True,
                timeout=30,
            )
        os.replace(tmp_so, _SHIM_SO)
    finally:
        tmp_so.unlink(missing_ok=True)
    return _SHIM_SO



_SHIM_SOURCE = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

static int (*real_socket)(int, int, int);
static int (*real_socketpair)(int, int, int, int[2]);
static int (*real_listen)(int, int);
static int (*real_accept)(int, struct sockaddr *, socklen_t *);
static int (*real_close)(int);
static int (*real_read)(int, void *, size_t);

/* Per-FD bookkeeping (FDs >= 1024 are passed through unshimmed). */
static int is_shimmed[1024];
static int peer_of[1024];
static int wake_r[1024];            /* accept() blocks reading this */
static int wake_w[1024];            /* close()  writes to this      */
static int listener_fd = -1;        /* FD that received listen()    */

__attribute__((constructor))
static void init(void) {
    real_socket     = dlsym(RTLD_NEXT, "socket");
    real_socketpair = dlsym(RTLD_NEXT, "socketpair");
    real_listen     = dlsym(RTLD_NEXT, "listen");
    real_accept     = dlsym(RTLD_NEXT, "accept");
    real_close      = dlsym(RTLD_NEXT, "close");
    real_read       = dlsym(RTLD_NEXT, "read");
    for (int i = 0; i < 1024; i++) {
        peer_of[i] = -1;
        wake_r[i]  = -1;
        wake_w[i]  = -1;
    }
}

/* ---- socket ---------------------------------------------------------- */
int socket(int domain, int type, int protocol) {
    if (domain == AF_UNIX) {
        int fd = real_socket(domain, type, protocol);
        if (fd >= 0) return fd;
        /* socket(AF_UNIX) blocked - fall back to socketpair(). */
        int sv[2];
        if (real_socketpair(domain, type, protocol, sv) == 0) {
            if (sv[0] >= 0 && sv[0] < 1024) {
                is_shimmed[sv[0]] = 1;
                peer_of[sv[0]]    = sv[1];
                int wp[2];
                if (pipe(wp) == 0) {
                    wake_r[sv[0]] = wp[0];
                    wake_w[sv[0]] = wp[1];
                }
            }
            return sv[0];
        }
        errno = EPERM;
        return -1;
    }
    return real_socket(domain, type, protocol);
}

/* ---- listen ---------------------------------------------------------- */
int listen(int sockfd, int backlog) {
    if (sockfd >= 0 && sockfd < 1024 && is_shimmed[sockfd]) {
        listener_fd = sockfd;
        return 0;
    }
    return real_listen(sockfd, backlog);
}

/* ---- accept ---------------------------------------------------------- */
int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen) {
    if (sockfd >= 0 && sockfd < 1024 && is_shimmed[sockfd]) {
        /* Block until close() writes to the wake pipe. */
        if (wake_r[sockfd] >= 0) {
            char buf;
            real_read(wake_r[sockfd], &buf, 1);
        }
        errno = ECONNABORTED;
        return -1;
    }
    return real_accept(sockfd, addr, addrlen);
}

/* ---- close ----------------------------------------------------------- */
int close(int fd) {
    if (fd >= 0 && fd < 1024 && is_shimmed[fd]) {
        int was_listener = (fd == listener_fd);
        is_shimmed[fd] = 0;

        if (wake_w[fd] >= 0) {              /* unblock accept() */
            char c = 0;
            write(wake_w[fd], &c, 1);
            real_close(wake_w[fd]);
            wake_w[fd] = -1;
        }
        if (wake_r[fd] >= 0) { real_close(wake_r[fd]); wake_r[fd]  = -1; }
        if (peer_of[fd] >= 0) { real_close(peer_of[fd]); peer_of[fd] = -1; }

        if (was_listener)
            _exit(0);                        /* conversion done - exit */
    }
    return real_close(fd);
}
"""



if __name__ == "__main__":
    import sys
    result = run_soffice(sys.argv[1:])
    sys.exit(result.returncode)
