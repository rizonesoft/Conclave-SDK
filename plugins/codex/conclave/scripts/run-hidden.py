"""Run a console command with no window, for scheduled tasks. Start it with pythonw.exe.

A console program started directly by Task Scheduler gets a console, and Windows Terminal takes
that console over when it is the default terminal, so pwsh's -WindowStyle Hidden cannot hide it.
pythonw.exe has no console, and CREATE_NO_WINDOW gives the child one that is never shown.

Stopping a task terminates only the process it started. The job object below extends that to the
child, so stopping the task still stops the command. Processes the child starts leave the job, so
a daemon it launches outlives it exactly as it would without this launcher.

The order in main() closes the gaps: the launcher joins the job first, so the child is inside it
from creation, and the child stays suspended until its own children are allowed to leave.
"""
import ctypes
import subprocess
import sys
from ctypes import wintypes

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x1000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
CREATE_SUSPENDED = 0x00000004


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", BasicLimits),
        ("IoInfo", IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.GetCurrentProcess.argtypes = ()
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
ntdll = ctypes.WinDLL("ntdll")
ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)
ntdll.NtResumeProcess.restype = ctypes.c_long


def set_job_limits(job, flags):
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = flags
    if not kernel32.SetInformationJobObject(
        job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def create_job():
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    set_job_limits(job, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
    return job


def main(command):
    if not command:
        return 2
    # This handle stays open for the launcher's lifetime. The system closes it when the launcher
    # dies, which ends the child, so every failure below can simply raise.
    job = create_job()
    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    child = subprocess.Popen(
        command,
        creationflags=subprocess.CREATE_NO_WINDOW | CREATE_SUSPENDED,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    set_job_limits(job, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK)
    # Popen does not expose the thread handle ResumeThread needs.
    status = ntdll.NtResumeProcess(int(child._handle))
    if status != 0:
        raise OSError(f"NtResumeProcess failed with status {status & 0xFFFFFFFF:#x}")
    return child.wait()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
