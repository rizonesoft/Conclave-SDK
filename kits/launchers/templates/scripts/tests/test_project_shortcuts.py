"""Tests of `scripts/project-shortcuts.ps1`: the desktop links that open the project in an agent (D07 T01 section 5).

Every link is written to a scratch folder and then run, not only read back: its target and arguments are executed
windowless against recording stand-ins (a compiled `wt.exe`, a `wsl.exe` script, an agent script), so what each
program would receive, and where, is what the tests hold. Windows only, with PowerShell 7; the `bash` tests run
wherever a real bash is.
"""
from __future__ import annotations

import base64
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
PWSH = shutil.which("pwsh")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SUSPENDED = 0x4  # CREATE_SUSPENDED: the child joins its job object before it can start anything


class Interactive:
    """A child started as run_tree starts it (its whole tree ends with it), whose stdin stays open: a test reads its
    output as it comes, sees whether it is still waiting, and sends Enter when it chooses."""

    def __init__(self, command, **kwargs):
        self.job = None
        if os.name == "nt":
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel32.CreateJobObjectW.restype = ctypes.c_void_p
            self.kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                                              ctypes.c_uint32]
            self.kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            self.job = self.kernel32.CreateJobObjectW(None, None)
            limits = _ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000
            self.kernel32.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, creationflags=NO_WINDOW | SUSPENDED,
                                         **kwargs)
            handle = ctypes.c_void_p(int(self.proc._handle))
            self.kernel32.AssignProcessToJobObject(self.job, handle)
            ntdll = ctypes.WinDLL("ntdll")
            ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
            ntdll.NtResumeProcess(handle)
        else:
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, start_new_session=True,
                                         creationflags=NO_WINDOW, **kwargs)
        self.output = []
        self.reader = threading.Thread(target=lambda: self.output.extend(iter(lambda: self.proc.stdout.read(1), "")),
                                       daemon=True)
        self.reader.start()

    def text(self):
        return "".join(self.output)

    def wait_for(self, needle, timeout=60):
        end = time.monotonic() + timeout
        while needle not in self.text():
            if time.monotonic() > end or (self.proc.poll() is not None and not self.reader.is_alive()):
                return False
            time.sleep(0.1)
        return True

    def enter(self):
        self.proc.stdin.write("\n")
        self.proc.stdin.flush()
        self.proc.stdin.close()

    def close(self):
        if self.job is not None:
            self.kernel32.TerminateJobObject(self.job, 1)
            self.kernel32.CloseHandle(self.job)
        elif self.proc.poll() is None:
            os.killpg(self.proc.pid, 9)
        self.proc.wait(timeout=30)


class _Limits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32)]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _Limits), ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def run_tree(command, timeout, **kwargs):
    """subprocess.run that ends the child's whole tree, never only the child: on Windows the child starts suspended
    inside a job object that kills every process in it when closed, elsewhere in a session of its own whose group is
    killed. The owner's rule: a child process never outlives its test (an orphaned child filled C: on 2026-11-08)."""
    stdin = kwargs.pop("input", None)
    if os.name != "nt":
        proc = subprocess.Popen(command, start_new_session=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, creationflags=NO_WINDOW, **kwargs)
        try:
            out, err = proc.communicate(stdin, timeout=timeout)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, 9)
                proc.wait()
        return subprocess.CompletedProcess(command, proc.returncode, out, err)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
    job = kernel32.CreateJobObjectW(None, None)
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, creationflags=NO_WINDOW | SUSPENDED, **kwargs)
        try:
            handle = ctypes.c_void_p(int(proc._handle))
            if not kernel32.AssignProcessToJobObject(job, handle):
                raise ctypes.WinError(ctypes.get_last_error())
            ntdll.NtResumeProcess(handle)
            out, err = proc.communicate(stdin, timeout=timeout)
        finally:
            kernel32.TerminateJobObject(job, 1)
            proc.wait()
    finally:
        kernel32.CloseHandle(job)
    return subprocess.CompletedProcess(command, proc.returncode, out, err)
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
# The stand-in for wsl.exe: it lists two distros, says whether a folder exists (all do but those in STUB_WSL_MISSING),
# fails everything with STUB_WSL_FAIL set, and records every call.
STUB_WSL = r'''import json, os, sys
args = sys.argv[1:]
with open(os.environ["STUB_WSL_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
if os.environ.get("STUB_WSL_FAIL"):
    print("the stand-in WSL failed", file=sys.stderr)
    sys.exit(4)
if args[:2] == ["-l", "-q"]:
    print("Ubuntu\nDebian")
    sys.exit(0)
rest = args[args.index("--exec") + 1:] if "--exec" in args else []
if rest[:2] == ["test", "-d"]:
    sys.exit(1 if rest[2] in os.environ.get("STUB_WSL_MISSING", "").split("|") else 0)
'''
# The stand-in for Windows Terminal: a real .exe (the link's target must be one), recording its working folder and
# each argument it was given, base64 per line, and starting nothing.
STUB_WT = r'''using System; using System.IO; using System.Text;
class Recorder {
  static int Main(string[] args) {
    var lines = new StringBuilder(Convert.ToBase64String(Encoding.UTF8.GetBytes(Environment.CurrentDirectory)));
    foreach (var a in args) lines.Append(' ').Append(Convert.ToBase64String(Encoding.UTF8.GetBytes(a)));
    File.AppendAllText(Environment.GetEnvironmentVariable("STUB_WT_LOG"), lines + "\n");
    return 0;
  }
}
'''
PROFILE = {"schema_version": 1, "title": "Example Site", "icon": "assets/icon.png", "agents": ["claude"],
           "skip_permissions": False, "links": []}
LABELS = {"claude": "Claude", "codex": "Codex", "agy": "Antigravity"}
FLAGS = {"claude": "--dangerously-skip-permissions", "codex": "--dangerously-bypass-approvals-and-sandbox",
         "agy": "--dangerously-skip-permissions"}


def folder(path):
    """A folder as a folder: Windows reports one by its long name or an 8.3 short one (RUNNER~1 on GitHub's runners,
    PROGRA~1), so working folders are compared resolved, never by spelling."""
    return Path(path).resolve()


def bash_command(agent, skip=False):
    command = f"{agent} {FLAGS[agent]}" if skip else agent
    return (f"{command} || (echo '{LABELS[agent]} did not start: the reason is above. Press Enter to close.'"
            " && read -r _)")


def renderer():
    spec = importlib.util.spec_from_file_location("campaign_icon_for_links", SCRIPTS / "campaign-icon.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(os.name == "nt" and PWSH and CSC.is_file(),
                     "a .lnk link, WScript.Shell, PowerShell 7 and the .NET Framework compiler are Windows's")
class ProjectShortcutsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._shared = tempfile.TemporaryDirectory()
        cls.wt_dir = Path(cls._shared.name) / "terminal"
        cls.wt_dir.mkdir()
        (cls.wt_dir / "recorder.cs").write_text(STUB_WT, encoding="utf-8")
        built = run_tree([str(CSC), "/nologo", f"/out:{cls.wt_dir / 'wt.exe'}", str(cls.wt_dir / "recorder.cs")],
                         timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        cls.icon_png = renderer().write_png(64, 64, bytearray(b"\x10\x22\x1a\xff" * 64 * 64))

    @classmethod
    def tearDownClass(cls):
        cls._shared.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.project = self.make_project("My Site's")   # a space and a quote
        self.desk, self.icons = self.base / "desk", self.base / "icons"
        stub = self.base / "stub_wsl.py"
        stub.write_text(STUB_WSL, encoding="utf-8")
        self.wsl = self.base / "wsl.cmd"
        self.wsl.write_text(f'@"{sys.executable}" "{stub}" %*\r\n', encoding="utf-8")
        self.wsl_log, self.wt_log, self.agent_log = self.base / "wsl.log", self.base / "wt.log", self.base / "agent.log"
        # An agent stand-in for the Windows form: it records where it ran and what it was given.
        self.agents = self.base / "agents"
        self.agents.mkdir()
        for agent in LABELS:
            (self.agents / f"{agent}.cmd").write_text(f'@echo {agent}^|%CD%^|%*>>"%STUB_AGENT_LOG%"\r\n',
                                                     encoding="utf-8")
        self.plain_path = os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep)
                                          if p and not (Path(p) / "wt.exe").exists())

    # --- fixtures ---------------------------------------------------------------------------------------------------

    def make_project(self, name, profile=PROFILE):
        project = self.base / name
        for rel in ("project-shortcuts.ps1", "campaign-icon.py", "lib/launchers.py"):
            (project / "scripts" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SCRIPTS / rel, project / "scripts" / rel)
        (project / "assets").mkdir()
        (project / "assets/icon.png").write_bytes(self.icon_png)
        (project / ".conclave").mkdir()
        self.write_profile(project, profile)
        return project

    @staticmethod
    def write_profile(project, profile):
        (project / ".conclave/launchers.json").write_text(json.dumps(profile), encoding="utf-8")

    def env(self, terminal=True, **extra):
        path = (str(self.wt_dir) + os.pathsep if terminal else "") + self.plain_path
        return {**os.environ, "PATH": path, "STUB_WSL_LOG": str(self.wsl_log), "STUB_WT_LOG": str(self.wt_log),
                "STUB_AGENT_LOG": str(self.agent_log), **extra}

    def run_script(self, *args, project=None, terminal=True, desk=None, icons=None, **extra):
        project = project or self.project
        command = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(project / "scripts/project-shortcuts.ps1"),
                   "-ShortcutDir", str(desk or self.desk), "-IconDir", str(icons or self.icons), "-Wsl", str(self.wsl),
                   "-Python", sys.executable, *args]
        return run_tree(command, timeout=300, env=self.env(terminal, **extra))

    def read_link(self, title="Example Site", agent="claude"):
        path = self.desk / f"{title} ({LABELS[agent]}).lnk"
        script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LINK_PATH); "
                  "@{target = $s.TargetPath; arguments = $s.Arguments; icon = $s.IconLocation; "
                  "description = $s.Description; workdir = $s.WorkingDirectory} | ConvertTo-Json -Compress")
        done = run_tree([PWSH, "-NoProfile", "-NonInteractive", "-Command", script], timeout=60,
                        env={**os.environ, "LINK_PATH": str(path)})
        return json.loads(done.stdout)

    def run_link(self, link, terminal=True, stdin="", **extra):
        """Start the link's target with its arguments, as the shell would, from its working folder."""
        return run_tree(f'"{link["target"]}" {link["arguments"]}', timeout=120, cwd=link["workdir"], input=stdin,
                        env=self.env(terminal, **extra))

    def terminal_calls(self):
        calls = []
        for line in self.wt_log.read_text(encoding="utf-8").splitlines():
            words = [base64.b64decode(w).decode("utf-8") for w in line.split(" ")]
            calls.append({"cwd": words[0], "argv": words[1:]})
        return calls

    def links(self):
        return sorted(p.name for p in self.desk.glob("*.lnk")) if self.desk.exists() else []

    def leftovers(self):
        found = [*self.desk.glob("*.tmp.*"), *self.desk.glob("*.old"), *self.icons.glob("*.tmp.*"),
                 *self.icons.glob("*.old")] if self.desk.exists() else []
        return [p.name for p in found]

    # --- refusals ---------------------------------------------------------------------------------------------------

    def test_a_project_folder_that_does_not_exist_is_refused(self):
        done = self.run_script("-Project", str(self.base / "nowhere"))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertRegex(done.stdout.strip(), r"the project folder does not exist: .*; nothing was written$")
        self.assertEqual(self.links(), [])

    def test_a_linux_path_needs_a_distro(self):
        done = self.run_script("-Project", "/home/me/site")
        self.assertEqual(done.returncode, 1)
        self.assertIn("a Linux path needs -Distro", done.stdout)
        self.assertEqual(self.links(), [])

    def test_a_malformed_profile_is_refused_with_the_loaders_message(self):
        self.write_profile(self.project, dict(PROFILE, title=None))
        done = self.run_script()
        self.assertEqual(done.returncode, 1)
        self.assertIn("the launcher profile cannot be read: launchers:", done.stdout)
        self.assertIn("title: must be set", done.stdout)
        self.assertTrue(done.stdout.strip().endswith("nothing was written"))
        self.assertEqual(self.links(), [])

    def test_a_wsl_folder_wsl_does_not_have_is_refused(self):
        done = self.run_script("-Project", "/srv/gone", "-Distro", "Ubuntu", STUB_WSL_MISSING="/srv/gone")
        self.assertEqual(done.returncode, 1)
        self.assertIn("does not exist in 'Ubuntu'", done.stdout)
        self.assertEqual(self.links(), [])

    def test_a_name_another_project_holds_is_refused_and_left_alone(self):
        other = self.make_project("other", PROFILE)   # the same title
        self.assertEqual(self.run_script(project=other).returncode, 0)
        before = (self.desk / "Example Site (Claude).lnk").read_bytes()
        done = self.run_script()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("is already there and is not this project's link; nothing was written", done.stdout)
        self.assertEqual((self.desk / "Example Site (Claude).lnk").read_bytes(), before)
        self.assertEqual(self.read_link()["description"], f"conclave-launcher: {str(other).lower()}")

    # --- the WSL form -----------------------------------------------------------------------------------------------

    def test_a_wsl_project_opens_in_windows_terminal_with_an_interactive_login_shell(self):
        done = self.run_script("-Project", r"\\wsl.localhost\Debian\home\me\site")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Example Site (Claude).lnk"])
        link = self.read_link()
        self.assertEqual(Path(link["target"]), self.wt_dir / "wt.exe")
        self.assertEqual(link["workdir"], os.environ["USERPROFILE"])
        self.assertEqual(link["description"], "conclave-launcher: wsl:debian:/home/me/site")
        icon = Path(link["icon"].rsplit(",", 1)[0])
        self.assertRegex(icon.name, r"^launcher-claude-[0-9a-f]{8}\.ico$")
        self.assertEqual(icon.parent, self.icons)
        self.assertTrue(icon.is_file())
        self.assertEqual(self.run_link(link).returncode, 0)
        (call,) = self.terminal_calls()
        self.assertEqual(folder(call["cwd"]), folder(os.environ["USERPROFILE"]))
        self.assertEqual(call["argv"], [str(self.wsl), "-d", "Debian", "--cd", "/home/me/site", "--exec", "bash",
                                        "-lic", bash_command("claude")])

    def test_a_linux_path_with_a_space_and_a_quote_reaches_wsl_whole(self):
        done = self.run_script("-Project", "/srv/my site's", "-Distro", "Ubuntu")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.run_link(self.read_link())
        self.assertEqual(self.terminal_calls()[0]["argv"][1:5], ["-d", "Ubuntu", "--cd", "/srv/my site's"])

    def test_without_windows_terminal_powershell_runs_wsl_and_holds_its_failure(self):
        done = self.run_script("-Project", "/srv/my site's", "-Distro", "Ubuntu", terminal=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        link = self.read_link()
        self.assertEqual(Path(link["target"]).name.lower(), "pwsh.exe")
        self.wsl_log.unlink()
        ran = self.run_link(link, terminal=False)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertEqual([json.loads(line) for line in self.wsl_log.read_text(encoding="utf-8").splitlines()],
                         [["-d", "Ubuntu", "--cd", "/srv/my site's", "--exec", "bash", "-lic", bash_command("claude")]])
        waiting = Interactive(f'"{link["target"]}" {link["arguments"]}', cwd=link["workdir"],
                              env=self.env(False, STUB_WSL_FAIL="1"))
        try:
            self.assertTrue(waiting.wait_for("WSL could not open the project (exit 4): the reason is above. "
                                             "Press Enter to close."), waiting.text())
            time.sleep(2)
            self.assertIsNone(waiting.proc.poll(), "the window closed before Enter")
            waiting.enter()
            self.assertEqual(waiting.proc.wait(timeout=30), 0)
        finally:
            waiting.close()

    # --- the Windows form -------------------------------------------------------------------------------------------

    def test_a_windows_project_opens_in_windows_terminal_in_its_folder(self):
        done = self.run_script()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        link = self.read_link()
        self.assertEqual(Path(link["target"]), self.wt_dir / "wt.exe")
        self.assertEqual(link["workdir"], str(self.project))
        self.run_link(link)
        (call,) = self.terminal_calls()
        self.assertEqual(folder(call["cwd"]), folder(self.project))
        self.assertEqual(call["argv"][:2], ["-d", str(self.project)])
        self.assertEqual(Path(call["argv"][2]).name.lower(), "pwsh.exe")
        self.assertEqual(call["argv"][3:], ["-NoLogo", "-NoExit", "-Command", "claude"])

    def test_without_windows_terminal_powershell_starts_the_agent_in_the_project(self):
        done = self.run_script(terminal=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        link = self.read_link()
        self.assertEqual(Path(link["target"]).name.lower(), "pwsh.exe")
        self.assertEqual(link["arguments"], "-NoLogo -NoExit -Command claude")
        env_path = str(self.agents) + os.pathsep + self.plain_path
        self.run_link(link, terminal=False, PATH=env_path)
        agent, cwd = self.agent_log.read_text(encoding="utf-8").split("|")[:2]
        # The same folder, compared as a folder: cmd reports its long name where the test's path may hold a short
        # 8.3 one (CI red at 92a02a1: RUNNER~1 against runneradmin).
        self.assertEqual((agent, folder(cwd)), ("claude", folder(self.project)))

    # --- the agent command ------------------------------------------------------------------------------------------

    def test_the_permission_flag_is_added_only_when_the_profile_asks(self):
        for skip in (False, True):
            with self.subTest(skip_permissions=skip):
                self.write_profile(self.project, dict(PROFILE, agents=list(LABELS), skip_permissions=skip))
                if self.wt_log.exists():
                    self.wt_log.unlink()
                done = self.run_script("-Project", "/srv/site", "-Distro", "Ubuntu")
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                for agent in LABELS:
                    self.run_link(self.read_link(agent=agent))
                received = [call["argv"][-1] for call in self.terminal_calls()]
                self.assertEqual(received, [bash_command(agent, skip) for agent in LABELS])
        # The Windows form too, under its own title (the WSL identity above holds "Example Site").
        self.write_profile(self.project, dict(PROFILE, title="Windows Site", agents=["codex"], skip_permissions=True))
        self.assertEqual(self.run_script(terminal=False).returncode, 0)
        self.run_link(self.read_link(title="Windows Site", agent="codex"), terminal=False,
                      PATH=str(self.agents) + os.pathsep + self.plain_path)
        self.assertEqual(self.agent_log.read_text(encoding="utf-8").split("|")[2].strip(),
                         "--dangerously-bypass-approvals-and-sandbox")

    def test_every_form_runs_the_agent_with_the_flag_only_when_asked(self):
        # Completion review: WSL and Windows projects, with and without Windows Terminal, the permission flag both
        # ways, each link run and what it handed on read where it arrived.
        agent_path = str(self.agents) + os.pathsep + self.plain_path
        for form, terminal, skip in [(f, t, s) for f in ("wsl", "windows") for t in (True, False) for s in (False, True)]:
            with self.subTest(form=form, terminal=terminal, skip_permissions=skip):
                title = f"{form} {'wt' if terminal else 'plain'} {'skip' if skip else 'ask'}"
                project = self.make_project(title, dict(PROFILE, title=title, agents=["codex"], skip_permissions=skip))
                for log in (self.wt_log, self.wsl_log, self.agent_log):
                    if log.exists():
                        log.unlink()
                where = ("-Project", f"/srv/{title.replace(' ', '-')}", "-Distro", "Ubuntu") if form == "wsl" else ()
                done = self.run_script(*where, project=project, terminal=terminal)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                link = self.read_link(title=title, agent="codex")
                ran = self.run_link(link, terminal=terminal, PATH=agent_path if not terminal else self.env()["PATH"])
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                if form == "wsl":
                    expected = ["-d", "Ubuntu", "--cd", f"/srv/{title.replace(' ', '-')}", "--exec", "bash", "-lic",
                                bash_command("codex", skip)]
                    if terminal:
                        (call,) = self.terminal_calls()
                        self.assertEqual((folder(call["cwd"]), call["argv"]),
                                         (folder(os.environ["USERPROFILE"]), [str(self.wsl), *expected]))
                    else:
                        calls = [json.loads(line) for line in self.wsl_log.read_text(encoding="utf-8").splitlines()]
                        self.assertEqual(calls[-1], expected)   # after the script's own -l and test -d calls
                else:
                    command = ["codex", FLAGS["codex"]] if skip else ["codex"]
                    if terminal:
                        (call,) = self.terminal_calls()
                        self.assertEqual(folder(call["cwd"]), folder(project))
                        self.assertEqual(call["argv"][:2], ["-d", str(project)])
                        self.assertEqual(call["argv"][3:], ["-NoLogo", "-NoExit", "-Command", " ".join(command)])
                    else:
                        agent, cwd, args = self.agent_log.read_text(encoding="utf-8").strip().split("|")
                        self.assertEqual((agent, folder(cwd), args.strip()),
                                         ("codex", folder(project), " ".join(command[1:])))

    def test_the_flags_are_the_ones_the_unattended_run_passes(self):
        run = SCRIPTS.parents[2] / "unattended/templates/scripts/unattended-run.py"
        if not run.is_file():
            self.skipTest("an installed project: the unattended kit's launcher is not beside this one")
        text = run.read_text(encoding="utf-8")
        script = (SCRIPTS / "project-shortcuts.ps1").read_text(encoding="utf-8")
        for agent in LABELS:
            block = re.search(rf'if agent == "{agent}":(.*?)(?:\n    if agent ==|\n    raise RunError)', text, re.S)
            flags = re.findall(r'"(--dangerously-[a-z-]+)"', block.group(1))
            self.assertEqual(flags, [FLAGS[agent]], agent)
            self.assertRegex(script, rf"{agent} = '{re.escape(FLAGS[agent])}'")

    # --- identity, removal and publication --------------------------------------------------------------------------

    def test_one_path_in_two_distros_is_two_projects_and_each_spelling_is_one(self):
        debian = self.make_project("debian", dict(PROFILE, title="Debian Site"))
        self.assertEqual(self.run_script("-Project", "/srv/site", "-Distro", "Ubuntu").returncode, 0)
        self.assertEqual(self.run_script("-Project", r"\\wsl.localhost\Debian\srv\site", project=debian).returncode, 0)
        icons = sorted(p.name for p in self.icons.iterdir())
        self.assertEqual(len(icons), 2, "the two distros' icons share a key")
        done = self.run_script("-Project", "/srv/site/", "-Distro", "Ubuntu", "-Remove")
        self.assertIn("1 link(s) and 1 icon(s)", done.stdout)
        self.assertEqual(self.links(), ["Debian Site (Claude).lnk"])
        self.assertEqual(len(list(self.icons.iterdir())), 1)
        done = self.run_script("-Project", "\\\\wsl$\\Debian\\srv\\site\\", "-Remove")
        self.assertIn("1 link(s) and 1 icon(s) of wsl:debian:/srv/site removed", done.stdout)
        self.assertEqual(self.links(), [])
        self.assertEqual(list(self.icons.iterdir()), [])

    def test_two_linux_paths_that_differ_in_case_are_two_projects(self):
        # Round 1 P1: PowerShell's -eq ignored case, so /srv/Site pruned and removed /srv/site's links.
        upper = self.make_project("upper", dict(PROFILE, title="Upper Site"))
        self.assertEqual(self.run_script("-Project", "/srv/site", "-Distro", "Ubuntu").returncode, 0)
        done = self.run_script("-Project", "/srv/Site", "-Distro", "ubuntu", project=upper)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Example Site (Claude).lnk", "Upper Site (Claude).lnk"])
        gone = self.run_script("-Project", "/srv/Site", "-Distro", "Ubuntu", "-Remove", project=upper)
        self.assertIn("1 link(s) and 1 icon(s)", gone.stdout)
        self.assertEqual(self.links(), ["Example Site (Claude).lnk"])
        same = self.make_project("same", PROFILE)   # the same title as /srv/site's, in another case
        refused = self.run_script("-Project", "/srv/SITE", "-Distro", "Ubuntu", project=same)
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("is not this project's link", refused.stdout)

    def test_a_folder_spelled_another_way_still_writes_and_keeps_its_links(self):
        # CI red on 2026-11-17 (62801e0): the runner's temp folder resolved under a short 8.3 name, so the script's
        # own temporary links, compared by full path, were listed as stale; once renamed into place they could not be
        # moved aside, and the whole run rolled back.
        self.desk.mkdir()
        self.icons.mkdir()
        desk, icons = self.desk / ".." / "desk", self.icons / ".." / "icons"
        for terminal in (True, False):
            with self.subTest(terminal=terminal):
                self.write_profile(self.project, dict(PROFILE, agents=["claude", "codex"]))
                done = self.run_script(terminal=terminal, desk=desk, icons=icons)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertEqual(self.links(), ["Example Site (Claude).lnk", "Example Site (Codex).lnk"])
                self.assertEqual(self.leftovers(), [])
        self.write_profile(self.project, dict(PROFILE, agents=["claude"]))
        done = self.run_script(desk=desk, icons=icons)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Example Site (Claude).lnk"], "a stale link is still found and removed")

    def test_remove_takes_this_projects_links_and_icons_and_nothing_else(self):
        other = self.make_project("other-site", dict(PROFILE, title="Other Site"))
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.run_script(project=other).returncode, 0)
        campaign = self.desk / "My Site's Claude campaign.lnk"
        shutil.copyfile(self.desk / "Example Site (Claude).lnk", campaign)
        run_tree([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LINK_PATH); "
                        "$s.Description = 'conclave-unattended: ' + $env:PROJECT; $s.Save()"],
                       env={**os.environ, "LINK_PATH": str(campaign), "PROJECT": str(self.project)}, timeout=60)
        count = len(list(self.icons.iterdir()))
        done = self.run_script("-Remove")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("1 link(s) and 1 icon(s)", done.stdout)
        self.assertEqual(self.links(), ["My Site's Claude campaign.lnk", "Other Site (Claude).lnk"])
        self.assertEqual(len(list(self.icons.iterdir())), count - 1)

    def test_remove_needs_no_profile_icon_python_or_wsl_and_runs_twice(self):
        self.assertEqual(self.run_script("-Project", "/srv/site", "-Distro", "Ubuntu").returncode, 0)
        self.write_profile(self.project, {"broken": True})
        (self.project / "assets/icon.png").unlink()
        done = self.run_script("-Project", "/srv/site", "-Distro", "Ubuntu", "-Remove", STUB_WSL_FAIL="1",
                               PATH="")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("1 link(s) and 1 icon(s)", done.stdout)
        again = self.run_script("-Project", "/srv/site", "-Distro", "Ubuntu", "-Remove")
        self.assertEqual(again.returncode, 0)
        self.assertIn("0 link(s) and 0 icon(s)", again.stdout)
        gone = self.run_script("-Project", str(self.base / "deleted-folder"), "-Remove")
        self.assertEqual((gone.returncode, "0 link(s) and 0 icon(s)" in gone.stdout), (0, True), gone.stdout)

    def test_a_link_the_profile_no_longer_names_is_removed_with_its_icon(self):
        self.write_profile(self.project, dict(PROFILE, agents=["claude", "codex"]))
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.links(), ["Example Site (Claude).lnk", "Example Site (Codex).lnk"])
        self.write_profile(self.project, dict(PROFILE, title="Renamed Site"))
        done = self.run_script()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Renamed Site (Claude).lnk"])
        self.assertEqual([p.name.split("-")[1] for p in self.icons.iterdir()], ["claude"])

    def test_a_failed_render_or_move_keeps_every_earlier_link_and_icon(self):
        self.write_profile(self.project, dict(PROFILE, agents=["claude", "codex"]))
        self.assertEqual(self.run_script().returncode, 0)
        before = {p.name: p.read_bytes() for p in [*self.desk.iterdir(), *self.icons.iterdir()]}
        self.write_profile(self.project, dict(PROFILE, agents=["claude", "codex", "agy"]))
        (self.project / "assets/icon.png").write_bytes(b"\x89PNG not an image")
        done = self.run_script()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("could not be rendered", done.stdout)
        self.assertEqual({p.name: p.read_bytes() for p in [*self.desk.iterdir(), *self.icons.iterdir()]}, before)
        # A link that cannot be replaced: held open without delete sharing, as an editor or a scan would.
        (self.project / "assets/icon.png").write_bytes(self.icon_png)
        with open(self.desk / "Example Site (Codex).lnk", "rb"):
            done = self.run_script()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("could not be put in place", done.stdout)
        self.assertEqual({p.name: p.read_bytes() for p in [*self.desk.iterdir(), *self.icons.iterdir()]}, before)
        self.assertEqual(self.leftovers(), [])
        # A stale link that cannot be removed (round 1 P2): the new links are put back with the rest.
        self.write_profile(self.project, dict(PROFILE, title="Renamed Site"))
        with open(self.desk / "Example Site (Codex).lnk", "rb"):
            done = self.run_script()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("could not be put in place or removed", done.stdout)
        self.assertEqual({p.name: p.read_bytes() for p in [*self.desk.iterdir(), *self.icons.iterdir()]}, before)
        self.assertEqual(self.leftovers(), [])


def find_bash():
    """A real bash: Git's on Windows (System32's starts WSL instead), the system's elsewhere."""
    if os.name == "nt":
        git = shutil.which("git")
        candidates = [Path(git).resolve().parents[1] / "bin/bash.exe"] if git else []
        return next((str(c) for c in candidates if c.is_file()), None)
    return shutil.which("bash")


BASH = find_bash()


@unittest.skipUnless(BASH, "the shell tests need a real bash (Git's on Windows)")
class InteractiveShellTest(unittest.TestCase):
    """Why the WSL link runs `bash -lic`: an owner's wrapper for the agent lives in ~/.bashrc after its "not
    interactive: return" guard, which a login shell reaches through ~/.profile (Ubuntu's own shape) only when it is
    interactive. And what an agent that does not start leaves on screen."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        (self.home / ".profile").write_text('if [ -n "$BASH_VERSION" ] && [ -f "$HOME/.bashrc" ]; then\n'
                                            '  . "$HOME/.bashrc"\nfi\n', encoding="utf-8", newline="\n")
        (self.home / ".bashrc").write_text("case $- in\n  *i*) ;;\n  *) return;;\nesac\n"
                                           "conclave_wrapper() { echo wrapped; }\n", encoding="utf-8", newline="\n")

    def bash(self, flags, command, stdin=""):
        return run_tree([BASH, flags, command], timeout=60, input=stdin, cwd=self.home,
                        env={**os.environ, "HOME": str(self.home), "BASH_ENV": ""})

    def test_the_wrapper_is_reached_by_an_interactive_login_shell_only(self):
        self.assertIn("wrapped", self.bash("-lic", "conclave_wrapper").stdout)
        self.assertNotEqual(self.bash("-lc", "conclave_wrapper").returncode, 0)

    def test_an_agent_that_does_not_start_says_so_and_waits_for_enter(self):
        command = bash_command("claude").replace("claude ||", "conclave-no-such-agent ||", 1)
        waiting = Interactive([BASH, "-lic", command], cwd=self.home,
                              env={**os.environ, "HOME": str(self.home), "BASH_ENV": ""})
        try:
            self.assertTrue(waiting.wait_for("Claude did not start: the reason is above. Press Enter to close."),
                            waiting.text())
            time.sleep(2)
            self.assertIsNone(waiting.proc.poll(), "the shell ended before Enter")
            waiting.enter()
            self.assertEqual(waiting.proc.wait(timeout=30), 0, "read -r took the Enter")
        finally:
            waiting.close()


if __name__ == "__main__":
    unittest.main()
