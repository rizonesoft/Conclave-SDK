"""The unattended kit's Windows shortcut (D02 T02 §10): unattended-shortcut.ps1 against a stand-in for wsl.exe.

The links are read back through the launchers kit's IShellLinkW (scripts/lib/ShellLink.cs) and their own target and
arguments are run, windowless, against the stand-in, so the command line Windows would hand wsl.exe is the one checked. Nothing here opens a window or touches
the real desktop: every link goes to a scratch folder.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]


def renderer_for(scripts):
    """The launchers kit's renderer, which this kit brings (D07 T01 section 3): beside these scripts in an installed
    project, in that kit's own folder in the SDK otherwise. The SDK's folder is reached only when the local file is
    absent, through `.parent`, which stops at the drive, so a project at a drive's top (`D:\\Example\\scripts`) is
    never asked for a third parent it does not have."""
    local = scripts / "campaign-icon.py"
    if local.is_file():
        return local
    return scripts.parent.parent.parent / "launchers" / "templates" / "scripts" / "campaign-icon.py"


RENDERER = renderer_for(SCRIPTS)


def loader_for(scripts):
    """The launchers kit's profile loader, which this kit brings with the renderer (D07 T01 section 7): beside these
    scripts in an installed project, in that kit's own folder in the SDK otherwise."""
    local = scripts / "lib" / "launchers.py"
    if local.is_file():
        return local
    return scripts.parent.parent.parent / "launchers" / "templates" / "scripts" / "lib" / "launchers.py"


LOADER = loader_for(SCRIPTS)
LINK_CODE = LOADER.parent / "ShellLink.cs"  # the launchers kit's IShellLinkW, beside its loader
PROVIDER = "Microsoft.PowerShell.Core\\FileSystem::"  # what Resolve-Path's .Path puts before a file on a share
PWSH = shutil.which("pwsh")
# The stand-in for wsl.exe: it lists two distros, translates a Windows path, says whether a folder exists (all do but
# those in STUB_WSL_MISSING), and records every call; with STUB_WSL_FAIL set it fails everything.
STUB_WSL = r'''import json, os, sys
args = sys.argv[1:]
with open(os.environ["STUB_WSL_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
if os.environ.get("STUB_WSL_FAIL"):
    sys.exit(1)
if args[:2] == ["-l", "-q"]:
    print("Ubuntu\nDebian")
    sys.exit(0)
rest = args[args.index("--exec") + 1:] if "--exec" in args else []
if rest[:2] == ["wslpath", "-a"]:
    drive, _, tail = rest[2].partition(":")
    print("/mnt/" + drive.lower() + tail.replace("\\", "/"))
elif rest[:2] == ["test", "-d"]:
    sys.exit(1 if rest[2] in os.environ.get("STUB_WSL_MISSING", "").split("|") else 0)
'''


def windowless():
    """No console window of its own for any process a test starts on Windows (a console child of a parent with
    none opens one over the owner's work: 2026-11-12, Office's launcher tests flashed 5 to 10); 0 elsewhere."""
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



class RendererPathTest(unittest.TestCase):
    """Round 1 of D07 T01 section 3: the renderer is found beside an installed project's scripts at any depth."""

    def test_a_project_at_the_top_of_a_drive_finds_its_own_renderer(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = Path(tmp) / "scripts"
            scripts.mkdir()
            (scripts / "campaign-icon.py").write_text("", encoding="utf-8")
            self.assertEqual(renderer_for(scripts), scripts / "campaign-icon.py")
        top = Path(Path.cwd().anchor) / "Example" / "scripts"   # two parents only, and no renderer there
        self.assertEqual(renderer_for(top).name, "campaign-icon.py")

    def test_the_kit_tree_takes_the_launchers_kits_renderer(self):
        if SCRIPTS.parent.name == "templates":
            self.assertEqual(RENDERER, SCRIPTS.parents[2] / "launchers/templates/scripts/campaign-icon.py")
            self.assertTrue(RENDERER.is_file())

class ShortcutFixture(unittest.TestCase):
    """The scratch project, the stand-in for wsl.exe and the helpers every shortcut test uses; it holds no test."""

    PROFILE = {"schema_version": 1, "name": "demo", "agent": "claude", "model": "opus", "effort": "medium",
               "prompt_file": "docs/unattended-prompt.md", "branch": "main", "skip_permissions": True, "tools": [],
               "min_disk_gb": 1, "min_ram_gb": 1, "tick_seconds": 300, "idle_minutes": 45, "stall_hours": 6,
               "preflight": [], "runners": {"agy": {"model": "gemini-4-carbon-medium", "effort": "medium"}}}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.project = base / "My Proj's"  # a space and a quote
        for rel in ("lib/unattended.py", "unattended-shortcut.ps1"):
            (self.project / "scripts" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SCRIPTS / rel, self.project / "scripts" / rel)
        shutil.copyfile(RENDERER, self.project / "scripts" / "campaign-icon.py")
        shutil.copyfile(LOADER, self.project / "scripts" / "lib" / "launchers.py")
        shutil.copyfile(LINK_CODE, self.project / "scripts" / "lib" / "ShellLink.cs")
        (self.project / ".conclave").mkdir()
        (self.project / "docs").mkdir()
        (self.project / "docs" / "unattended-prompt.md").write_text("Run the plan.\n", encoding="utf-8")
        self.write_profile(self.PROFILE)
        icon_module = load("campaign_icon_for_shortcut", RENDERER)
        self.icon = base / "brand.png"
        self.icon.write_bytes(icon_module.write_png(256, 256, bytearray(bytes((16, 34, 26, 255)) * 256 * 256)))
        (self.project / "assets").mkdir()
        shutil.copyfile(self.icon, self.project / "assets" / "icon.png")
        self.desk, self.icons = base / "desk", base / "icons"
        stub = base / "stub_wsl.py"
        stub.write_text(STUB_WSL, encoding="utf-8")
        self.wsl = base / "wsl.cmd"
        self.wsl.write_text(f'@"{sys.executable}" "{stub}" %*\r\n', encoding="utf-8")
        self.log = base / "wsl.log"
        self.env = {**os.environ, "STUB_WSL_LOG": str(self.log)}
        self.run = load("unattended_run_for_shortcut", SCRIPTS / "unattended-run.py")

    def write_profile(self, profile):
        (self.project / ".conclave" / "unattended.json").write_text(json.dumps(profile), encoding="utf-8")

    def write_launchers(self, title, project=None):
        """The launchers kit's profile, `title` being a string, None (unset, as the kit installs it) or raw text."""
        path = (project or self.project) / ".conclave" / "launchers.json"
        if isinstance(title, str) and title.startswith("RAW:"):
            path.write_text(title[4:], encoding="utf-8")
            return
        path.write_text(json.dumps({"schema_version": 1, "title": title, "icon": "assets/icon.png",
                                    "agents": ["claude"], "skip_permissions": False, "links": []}),
                        encoding="utf-8")

    def shortcut(self, *args, project=None, icon_dir=True, **env):
        project = project or self.project
        command = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(project / "scripts" / "unattended-shortcut.ps1"),
                   "-ShortcutDir", str(self.desk), *(["-IconDir", str(self.icons)] if icon_dir else []),
                   "-Wsl", str(self.wsl), "-Python", sys.executable, *args]
        return subprocess.run(command, capture_output=True, text=True, timeout=180, env={**self.env, **env},
                              creationflags=windowless())

    def read_link(self, path):
        """A link's fields, read through the kit's own IShellLinkW (scripts/lib/ShellLink.cs), which keeps text in any
        script at its full length. The path goes through the environment: it holds a quote."""
        script = ("[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); Add-Type -Path $env:LINK_CODE; "
                  "$s = [Conclave.ShellLink]::Read($env:LINK_PATH); "
                  "@{target = $s.Target; arguments = $s.Arguments; icon = \"$($s.IconPath),$($s.IconIndex)\"; "
                  "description = $s.Description} | ConvertTo-Json -Compress")
        done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                              text=True, encoding="utf-8", timeout=60,
                              env={**os.environ, "LINK_PATH": str(path), "LINK_CODE": str(LINK_CODE)},
                              creationflags=windowless())
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()] if self.log.exists() \
            else []

    def links(self):
        return sorted(p.name for p in self.desk.glob("*.lnk")) if self.desk.exists() else []

    def install(self):
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done

    def activate(self, link, **env):
        """The link's own target and arguments, as Windows runs them on a double-click, windowless, Enter typed."""
        return subprocess.run(f'"{link["target"]}" {link["arguments"]}', input="\n", capture_output=True, text=True,
                              timeout=120, env={**self.env, **env}, creationflags=windowless())


@unittest.skipUnless(os.name == "nt" and PWSH, "a .lnk shortcut and IShellLinkW are Windows's (PowerShell 7)")
class ShortcutTest(ShortcutFixture):
    def test_one_link_per_runner_hands_wsl_the_start_command_of_that_runner(self):
        # The command itself (it starts the run, and waits for Enter when it cannot) is the Linux entry's, run in bash
        # by DesktopEntryTest; the live proof in the findings file ran it through the real wsl.exe.
        self.install()
        self.assertEqual(self.links(), ["My Proj's Carbon campaign.lnk", "My Proj's Claude campaign.lnk"])
        translated = next(c for c in self.calls() if c[3:5] == ["wslpath", "-a"])
        linux = "/mnt/" + translated[5][0].lower() + translated[5][2:].replace("\\", "/")
        self.assertTrue(linux.endswith("/My Proj's"), linux)
        for label, agent in (("Carbon", "agy"), ("Claude", "claude")):
            with self.subTest(agent):
                link = self.read_link(self.desk / f"My Proj's {label} campaign.lnk")
                self.assertEqual(Path(link["target"]).stem, "pwsh")
                icon = link["icon"].rsplit(",", 1)[0]
                self.assertRegex(Path(icon).name, rf"^campaign-{agent}-[0-9a-f]{{8}}\.ico$")
                self.assertTrue(Path(icon).is_file())
                self.log.unlink()
                ran = self.activate(link)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                self.assertEqual(self.calls(), [["-d", "Ubuntu", "--cd", linux, "--exec", "bash", "-lc",
                                                 self.run.start_command(agent)]])

    def test_a_project_in_wsl_starts_from_its_linux_path(self):
        for label, project in (("the distro's own UNC path", "\\\\wsl.localhost\\Ubuntu\\home\\x\\demo"),
                               ("the older wsl$ form", "\\\\wsl$\\Ubuntu\\home\\x\\demo"),
                               ("a Linux path", "/home/x/demo")):
            with self.subTest(label):
                shutil.rmtree(self.desk, ignore_errors=True)
                self.log.unlink(missing_ok=True)
                done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon), "-Project", project)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertFalse([c for c in self.calls() if "wslpath" in c], "a WSL path went through wslpath")
                self.log.unlink()
                ran = self.activate(self.read_link(self.desk / "demo Claude campaign.lnk"))
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                self.assertEqual(self.calls()[0][:5], ["-d", "Ubuntu", "--cd", "/home/x/demo", "--exec"])

    def test_a_project_in_another_distro_is_refused(self):
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon), "-Project",
                             "\\\\wsl.localhost\\Debian\\home\\x\\demo")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("the project is in distro 'Debian', not 'Ubuntu'", done.stdout)
        self.assertEqual(self.links(), [])

    def test_a_failure_of_wsl_itself_is_said_and_waits_for_enter(self):
        # Round 1 of D02 T02 §10: a drive gone or a distro removed fails before bash, whose own wait cannot run.
        self.install()
        link = self.read_link(self.desk / "My Proj's Claude campaign.lnk")
        waiting = subprocess.Popen(f'"{link["target"]}" {link["arguments"]}', stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   env={**self.env, "STUB_WSL_FAIL": "1"}, creationflags=windowless())
        self.addCleanup(lambda: waiting.poll() is None and waiting.kill())
        time.sleep(5)
        self.assertIsNone(waiting.poll(), "the window closed without waiting for Enter")
        out, _ = waiting.communicate("\n", timeout=60)  # Enter: it closes
        self.assertIn("WSL could not start the run (exit 1): the reason is above. Press Enter to close.", out)
        self.assertEqual(waiting.returncode, 0)

    def test_a_link_is_kept_when_its_replacement_cannot_be_made(self):
        self.install()
        link = self.desk / "My Proj's Claude campaign.lnk"
        before = link.read_bytes()
        broken = Path(self._tmp.name) / "not-an-image.png"
        broken.write_bytes(b"not a png")
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(broken))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("could not be rendered; its shortcut is left as it was", done.stdout)
        self.assertEqual(link.read_bytes(), before)
        self.assertEqual([p.name for p in self.desk.iterdir() if ".tmp" in p.name], [], "a temporary link was left")

    def test_remove_takes_this_projects_links_whatever_the_setup_now_is(self):
        self.install()
        other = self.desk / "Other Claude campaign.lnk"
        shutil.copyfile(self.desk / "My Proj's Claude campaign.lnk", other)
        done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                               "Add-Type -Path $env:LINK_CODE; $s = [Conclave.ShellLink]::Read($env:LINK_PATH); "
                               "$s.Description = 'conclave-unattended: D:\\elsewhere'; "
                               "[Conclave.ShellLink]::Write($env:LINK_PATH, $s)"],
                              capture_output=True, text=True, timeout=60,
                              env={**os.environ, "LINK_PATH": str(other), "LINK_CODE": str(LINK_CODE)},
                              creationflags=windowless())
        self.assertEqual(done.returncode, 0, done.stderr)
        (self.desk / "notes.txt").write_text("mine\n", encoding="utf-8")
        another = self.icons / "campaign-claude-deadbeef.ico"  # another project's icon in a shared icon folder
        another.write_bytes(b"icon")
        self.write_profile({**self.PROFILE, "runners": {}})  # the profile dropped a runner
        self.icon.unlink()  # the icon is gone
        done = self.shortcut("-Remove", STUB_WSL_FAIL="1")  # and WSL answers nothing
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Other Claude campaign.lnk"])
        self.assertTrue((self.desk / "notes.txt").exists())
        self.assertEqual(list(self.icons.glob("campaign-*.ico")), [another])

    def test_what_cannot_make_a_working_link_is_refused_before_anything_is_written(self):
        cases = {"a distro WSL does not list": (["-Distro", "Arch", "-Icon", str(self.icon)], {}, "no distro 'Arch'"),
                 "a project WSL does not have": (["-Distro", "Ubuntu", "-Icon", str(self.icon)],
                                                 {"STUB_WSL_MISSING": "*"}, "does not exist in 'Ubuntu'"),
                 "no icon": (["-Distro", "Ubuntu"], {}, "-Icon is not a file"),
                 "a profile the run would refuse": (["-Distro", "Ubuntu", "-Icon", str(self.icon)], {},
                                                    "the run profile cannot be read")}
        for label, (args, env, said) in cases.items():
            with self.subTest(label):
                if label == "a profile the run would refuse":
                    self.write_profile({**self.PROFILE, "effort": "extreme"})
                if label == "a project WSL does not have":
                    env = {"STUB_WSL_MISSING": "|".join(self._linux_candidates())}
                done = self.shortcut(*args, **env)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn(said, done.stdout)
                self.assertEqual(self.links(), [])

    def _linux_candidates(self):
        """The WSL path the stand-in gives this project, for the long and the short spelling of the temp folder."""
        paths = {str(self.project), os.path.realpath(self.project)}
        return ["/mnt/" + p[0].lower() + p[2:].replace("\\", "/") for p in paths]


@unittest.skipUnless(os.name == "nt" and PWSH, "a .lnk shortcut and IShellLinkW are Windows's (PowerShell 7)")
class CampaignTitleTest(ShortcutFixture):
    """D07 T01 section 7: the campaign links carry the launcher profile's title, read an icon from a share, keep one
    identity per project, and replace a set of links whole or not at all."""

    def snapshot(self):
        """Every file in the desktop and icon folders, by name, with its bytes."""
        return {p.relative_to(p.parents[1]).as_posix(): p.read_bytes()
                for folder in (self.desk, self.icons) if folder.exists() for p in folder.iterdir() if p.is_file()}

    def set_description(self, path, text, icon=None):
        """Rewrite a link's mark, and its icon when `icon` is given, through the kit's IShellLinkW."""
        done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
                               "Add-Type -Path $env:LINK_CODE; $s = [Conclave.ShellLink]::Read($env:LINK_PATH); "
                               "$s.Description = $env:LINK_MARK; if ($env:LINK_ICON) { $s.IconPath = $env:LINK_ICON }; "
                               "[Conclave.ShellLink]::Write($env:LINK_PATH, $s)"],
                              capture_output=True, text=True, timeout=60,
                              env={**os.environ, "LINK_PATH": str(path), "LINK_MARK": text, "LINK_ICON": icon or "",
                                   "LINK_CODE": str(LINK_CODE)},
                              creationflags=windowless())
        self.assertEqual(done.returncode, 0, done.stderr)

    def rendered(self, agent):
        return self.rendered_from(self.icon, agent)

    def second_project(self, title):
        other = Path(self._tmp.name) / "Other"
        shutil.copytree(self.project, other)
        self.write_launchers(title, other)
        return other

    def test_a_rename_with_a_provider_qualified_icon_writes_the_titled_set_and_nothing_else(self):
        self.install()
        self.assertEqual(self.links(), ["My Proj's Carbon campaign.lnk", "My Proj's Claude campaign.lnk"])
        self.write_launchers("Demo Site")
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", PROVIDER + str(self.icon))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Demo Site Carbon campaign.lnk", "Demo Site Claude campaign.lnk"])
        self.assertEqual(len(list(self.icons.glob("campaign-*.ico"))), 2)
        self.assertEqual(len(list(self.icons.iterdir())), 2)
        for label, agent in (("Carbon", "agy"), ("Claude", "claude")):
            with self.subTest(agent):
                link = self.read_link(self.desk / f"Demo Site {label} campaign.lnk")
                self.assertEqual(Path(link["icon"].rsplit(",", 1)[0]).read_bytes(), self.rendered(agent))
                self.log.unlink()
                ran = self.activate(link)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                self.assertEqual(self.calls()[0][-1], self.run.start_command(agent))
                self.assertEqual(self.calls()[0][:2], ["-d", "Ubuntu"])

    def test_a_provider_qualified_project_is_named_by_its_plain_path(self):
        self.install()
        plain = self.read_link(self.desk / "My Proj's Claude campaign.lnk")["description"]
        shutil.rmtree(self.desk)
        self.log.unlink()
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon), "-Project", PROVIDER + str(self.project))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        mark = self.read_link(self.desk / "My Proj's Claude campaign.lnk")["description"]
        self.assertEqual(mark, plain)
        self.assertNotIn("::", mark)
        translated = next(c for c in self.calls() if c[3:5] == ["wslpath", "-a"])
        self.assertNotIn("::", translated[5])

    def test_a_project_by_its_short_name_is_the_same_project_as_by_its_own(self):
        # CI's Windows runner keeps its temp folder as C:\Users\RUNNER~1: the same folder by two spellings.
        import ctypes
        size = 32768
        text = ctypes.create_unicode_buffer(size)
        long_name = os.path.realpath(self.project)
        if not ctypes.windll.kernel32.GetShortPathNameW(long_name, text, size) or text.value == long_name:
            self.skipTest("this volume keeps no 8.3 short names")
        short = text.value
        self.install()
        before = self.snapshot()
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon), "-Project", short)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["My Proj's Carbon campaign.lnk", "My Proj's Claude campaign.lnk"])
        self.assertEqual(sorted(k for k in self.snapshot()), sorted(before))
        mark = self.read_link(self.desk / "My Proj's Claude campaign.lnk")["description"]
        self.assertEqual(mark.lower(), ("conclave-unattended: " + long_name).lower())

    def test_the_title_names_the_links_exactly_whatever_its_script(self):
        self.write_launchers("\u6771\u4eac")
        self.install()
        self.assertEqual(self.links(), ["\u6771\u4eac Carbon campaign.lnk", "\u6771\u4eac Claude campaign.lnk"])

    def test_a_project_named_outside_the_ansi_code_page_keeps_its_links_its_own(self):
        # A project in WSL, so no path goes through the stand-in for wsl.exe: it is a batch file, and cmd hands a
        # batch file its arguments in the ANSI code page, which the real wsl.exe does not.
        where = ["-Distro", "Ubuntu", "-Project", "/home/x/東京"]
        for _ in range(2):  # the second run finds its own links by their mark, never refused as another's
            done = self.shortcut(*where, "-Icon", str(self.icon))
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["東京 Carbon campaign.lnk", "東京 Claude campaign.lnk"])
        link = self.read_link(self.desk / "東京 Claude campaign.lnk")
        self.assertEqual(link["description"], "conclave-unattended: \\\\wsl.localhost\\Ubuntu\\home\\x\\東京")
        self.assertTrue(Path(link["icon"].rsplit(",", 1)[0]).is_file(), link)
        self.assertIn("'/home/x/東京'", link["arguments"])
        self.log.unlink()
        ran = self.activate(link)  # the link's own arguments, as Windows reads them, start the run there
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertEqual(len(self.calls()), 1)
        done = self.shortcut("-Remove", *where)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual((self.links(), list(self.icons.glob("*.ico"))), ([], []))

    def test_an_unset_title_keeps_the_folders_name(self):
        for label, text in (("unset", None), ("the kit's template", "RAW:" + json.dumps(
                {"schema_version": 1, "title": None, "icon": None, "agents": ["claude"], "skip_permissions": False,
                 "links": []}))):
            with self.subTest(label):
                shutil.rmtree(self.desk, ignore_errors=True)
                self.write_launchers(text)
                self.install()
                self.assertEqual(self.links(), ["My Proj's Carbon campaign.lnk", "My Proj's Claude campaign.lnk"])

    def test_a_refused_profile_or_a_missing_loader_changes_nothing_and_says_why(self):
        self.install()
        before = self.snapshot()
        loader = self.project / "scripts" / "lib" / "launchers.py"
        cases = (("a bad title", lambda: self.write_launchers(" x"), "title: must not start or end with a space"),
                 ("not JSON", lambda: self.write_launchers("RAW:{"), "not JSON"),
                 ("no loader", lambda: loader.unlink(),
                  "there is no scripts/lib/launchers.py (python forge.py kit <project> unattended installs it)"))
        for label, make, said in cases:
            with self.subTest(label):
                self.write_launchers("Demo Site")
                make()
                done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon))
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn("unattended-shortcut: the launcher profile cannot be read: ", done.stdout)
                self.assertIn(said, done.stdout)
                self.assertIn("nothing was written", done.stdout)
                self.assertNotIn("Traceback", done.stdout + done.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_without_the_link_code_nothing_is_written_or_removed(self):
        self.install()
        before = self.snapshot()
        (self.project / "scripts" / "lib" / "ShellLink.cs").unlink()
        for args in (["-Distro", "Ubuntu", "-Icon", str(self.icon)], ["-Remove"]):
            with self.subTest(args[0]):
                done = self.shortcut(*args)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn("there is no scripts/lib/ShellLink.cs (python forge.py kit <project> unattended "
                              "installs it); nothing was written", done.stdout)
                self.assertEqual(self.snapshot(), before)

    def test_remove_works_with_the_launcher_profile_broken_or_its_loader_gone(self):
        for label in ("malformed", "no loader"):
            with self.subTest(label):
                self.install()
                self.write_launchers("RAW:{")
                if label == "no loader":
                    (self.project / "scripts" / "lib" / "launchers.py").unlink()
                done = self.shortcut("-Remove")
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertEqual((self.links(), list(self.icons.glob("*.ico"))), ([], []))
                shutil.copyfile(LOADER, self.project / "scripts" / "lib" / "launchers.py")
                (self.project / ".conclave" / "launchers.json").unlink()

    def test_a_dropped_runner_takes_its_link_and_badge_and_keeps_the_others(self):
        self.write_launchers("Demo Site")
        self.install()
        claude = [p for p in self.icons.iterdir() if p.name.startswith("campaign-claude-")]
        self.write_profile({**self.PROFILE, "runners": {}})
        self.install()
        self.assertEqual(self.links(), ["Demo Site Claude campaign.lnk"])
        self.assertEqual(list(self.icons.iterdir()), claude)

    def test_a_name_held_by_another_file_is_refused_and_a_retry_writes_the_whole_set(self):
        self.install()  # the folder-named set, which a rename must keep until it can replace it whole
        for label in ("another project's link", "a folder"):
            with self.subTest(label):
                blocker = self.desk / "Demo Site Carbon campaign.lnk"  # the second runner's new name
                if label == "a folder":
                    blocker.mkdir()
                else:
                    shutil.copyfile(self.desk / "My Proj's Claude campaign.lnk", blocker)
                    self.set_description(blocker, "conclave-unattended: D:\\elsewhere")
                before = self.snapshot()
                self.write_launchers("Demo Site")
                done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon))
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn("the shortcut name 'Demo Site Carbon campaign.lnk' is held by a file this project did "
                              "not write", done.stdout)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual([p.name for p in self.desk.iterdir() if ".tmp" in p.name], [])
                self.assertEqual([p.name for p in self.icons.iterdir() if ".tmp" in p.name], [])
                shutil.rmtree(blocker) if blocker.is_dir() else blocker.unlink()
                (self.project / ".conclave" / "launchers.json").unlink()
        self.write_launchers("Demo Site")
        self.install()
        self.assertEqual(self.links(), ["Demo Site Carbon campaign.lnk", "Demo Site Claude campaign.lnk"])
        self.assertEqual(len(list(self.icons.iterdir())), 2)

    def test_a_failure_on_the_second_runner_leaves_the_previous_set_whole(self):
        self.install()  # the folder-named set, from the first icon
        before = self.snapshot()
        icon_module = load("campaign_icon_for_partial", RENDERER)
        other = Path(self._tmp.name) / "other.png"
        other.write_bytes(icon_module.write_png(256, 256, bytearray(bytes((200, 40, 40, 255)) * 256 * 256)))
        # A renderer that draws the first runner's badge and fails on the second's (agy, after claude).
        installed = self.project / "scripts" / "campaign-icon.py"
        installed.write_text("import runpy, sys\n"
                             "if sys.argv[1:2] == ['badge'] and sys.argv[3:4] == ['agy']:\n    sys.exit(1)\n"
                             f"sys.argv[0] = {str(RENDERER)!r}\nrunpy.run_path(sys.argv[0], run_name='__main__')\n",
                             encoding="utf-8")
        self.write_launchers("Demo Site")
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(other))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("the icon for Demo Site Carbon campaign could not be rendered", done.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([p.name for p in [*self.desk.iterdir(), *self.icons.iterdir()] if ".tmp" in p.name], [])
        shutil.copyfile(RENDERER, installed)
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(other))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Demo Site Carbon campaign.lnk", "Demo Site Claude campaign.lnk"])
        self.assertEqual(sorted(p.read_bytes() for p in self.icons.iterdir()),
                         sorted(self.rendered_from(other, agent) for agent in ("agy", "claude")))

    def rendered_from(self, icon, agent):
        out = Path(self._tmp.name) / f"expected-{icon.stem}-{agent}.ico"
        done = subprocess.run([sys.executable, "-B", str(RENDERER), "badge", str(icon), agent, str(out)],
                              capture_output=True, text=True, timeout=120, creationflags=windowless())
        self.assertEqual(done.returncode, 0, done.stderr)
        return out.read_bytes()

    def test_one_linux_path_in_two_distros_is_two_projects(self):
        self.write_launchers("Alpha")
        other = self.second_project("Beta")
        linux = ["-Icon", str(self.icon), "-Project", "/home/x/demo"]
        self.assertEqual(self.shortcut("-Distro", "Ubuntu", *linux).returncode, 0)
        done = self.shortcut("-Distro", "Debian", *linux, project=other)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        beta = {k: v for k, v in self.snapshot().items() if "Beta" in k}
        self.assertEqual(len(beta), 2)
        beta_icons = sorted(self.read_link(self.desk / f"Beta {r} campaign.lnk")["icon"] for r in ("Carbon", "Claude"))
        theirs = {k: v for k, v in self.snapshot().items() if k.startswith("icons/") and
                  any(Path(i.rsplit(",", 1)[0]).name == k[6:] for i in beta_icons)}
        self.assertEqual(len(theirs), 2)
        self.write_launchers("Alpha Two")
        self.write_profile({**self.PROFILE, "runners": {}})
        for step in (["-Distro", "Ubuntu", *linux], ["-Remove", "-Distro", "Ubuntu", "-Project", "/home/x/demo"]):
            with self.subTest(step[0]):
                done = self.shortcut(*step)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                now = self.snapshot()
                self.assertEqual({k: now.get(k) for k in beta}, beta)
                self.assertEqual({k: now.get(k) for k in theirs}, theirs)
        self.assertEqual(self.links(), ["Beta Carbon campaign.lnk", "Beta Claude campaign.lnk"])
        done = self.shortcut("-Remove", "-Project", "/home/x/demo")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("-Project '/home/x/demo' is a Linux path: -Distro names the distro it is in", done.stdout)

    def test_links_and_badges_under_the_old_mark_and_key_are_replaced(self):
        # What the script wrote before for `-Project /home/x/Demo` (a capital, which Linux keeps): the folder-named set
        # under the path as typed, and its badges under that path's key, which the old script took in lower case.
        linux = ["-Distro", "Ubuntu", "-Icon", str(self.icon), "-Project", "/home/x/Demo"]
        self.assertEqual(self.shortcut(*linux).returncode, 0)
        old_key = hashlib.sha256(b"/home/x/demo").hexdigest()[:8]
        for link in self.desk.glob("*.lnk"):
            badge = Path(self.read_link(link)["icon"].rsplit(",", 1)[0])
            old = badge.with_name(f"{badge.name.split('-')[0]}-{badge.name.split('-')[1]}-{old_key}.ico")
            badge.rename(old)
            self.set_description(link, "conclave-unattended: /home/x/Demo", icon=str(old))
        self.assertEqual(self.links(), ["Demo Carbon campaign.lnk", "Demo Claude campaign.lnk"])
        # A titled link under the old mark is this project's too, so it is replaced, not refused as another's.
        shutil.copyfile(self.desk / "Demo Claude campaign.lnk", self.desk / "Demo Site Claude campaign.lnk")
        self.write_launchers("Demo Site")
        done = self.shortcut(*linux)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.links(), ["Demo Site Carbon campaign.lnk", "Demo Site Claude campaign.lnk"])
        self.assertEqual(list(self.icons.glob(f"campaign-*-{old_key}.ico")), [])
        self.assertFalse((self.icons / f"campaign-claude-{old_key}.ico").exists())
        new_key = hashlib.sha256(b"\\\\wsl.localhost\\ubuntu\\home\\x\\Demo").hexdigest()[:8]
        mark = self.read_link(self.desk / "Demo Site Claude campaign.lnk")["description"]
        self.assertEqual(mark, "conclave-unattended: \\\\wsl.localhost\\Ubuntu\\home\\x\\Demo")
        self.assertTrue((self.icons / f"campaign-claude-{new_key}.ico").is_file())

    def test_an_old_linux_path_mark_of_another_distro_is_never_this_projects(self):
        # Round 1: the old mark of `-Project /home/x/demo` names no distro; its link's arguments do.
        debian = ["-Distro", "Debian", "-Icon", str(self.icon), "-Project", "/home/x/demo"]
        self.assertEqual(self.shortcut(*debian).returncode, 0)
        for link in self.desk.glob("*.lnk"):
            self.set_description(link, "conclave-unattended: /home/x/demo")
        before = self.snapshot()
        done = self.shortcut("-Remove", "-Distro", "Ubuntu", "-Project", "/home/x/demo")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.snapshot(), before)
        done = self.shortcut("-Remove", "-Distro", "Debian", "-Project", "/home/x/demo")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual((self.links(), list(self.icons.iterdir())), ([], []))

    def test_linux_paths_that_differ_only_in_case_are_two_projects(self):
        # Round 1: Linux tells /home/x/Demo from /home/x/demo, so their marks and keys differ by case.
        self.write_launchers("Alpha")
        other = self.second_project("Beta")
        upper = ["-Distro", "Ubuntu", "-Icon", str(self.icon), "-Project", "/home/x/Demo"]
        lower = ["-Distro", "Ubuntu", "-Icon", str(self.icon), "-Project", "/home/x/demo"]
        self.assertEqual(self.shortcut(*upper).returncode, 0)
        alpha = self.snapshot()
        for step in (lower, ["-Remove", "-Distro", "Ubuntu", "-Project", "/home/x/demo"]):
            with self.subTest(step[0]):
                done = self.shortcut(*step, project=other)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                now = self.snapshot()
                self.assertEqual({k: now.get(k) for k in alpha}, alpha)

    def test_a_link_held_open_while_the_set_is_replaced_leaves_the_previous_set(self):
        # Round 1: the second runner's link cannot be moved aside while another program holds it open.
        self.install()
        before = self.snapshot()
        icon_module = load("campaign_icon_for_held", RENDERER)
        other = Path(self._tmp.name) / "other.png"
        other.write_bytes(icon_module.write_png(256, 256, bytearray(bytes((200, 40, 40, 255)) * 256 * 256)))
        with open(self.desk / "My Proj's Carbon campaign.lnk", "rb"):  # open without delete sharing
            done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(other))
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertIn("the shortcuts could not be put in place", done.stdout)
            self.assertIn("the previous ones are kept", done.stdout)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual([p.name for p in [*self.desk.iterdir(), *self.icons.iterdir()]
                              if ".tmp" in p.name or p.name.endswith(".old")], [])
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(other))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(sorted(p.read_bytes() for p in self.icons.iterdir()),
                         sorted(self.rendered_from(other, agent) for agent in ("agy", "claude")))

    def test_a_locked_stale_link_leaves_the_previous_set_and_a_retry_writes_the_new_one(self):
        # Completion gap: a rename retires the old links in the same change as it writes the new ones.
        self.install()
        before = self.snapshot()
        self.write_launchers("Demo Site")
        with open(self.desk / "My Proj's Carbon campaign.lnk", "rb"):  # a link the rename retires, held open
            done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon))
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertIn("the previous ones are kept", done.stdout)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.links(), ["My Proj's Carbon campaign.lnk", "My Proj's Claude campaign.lnk"])
            self.assertEqual([p.name for p in [*self.desk.iterdir(), *self.icons.iterdir()]
                              if ".tmp" in p.name or p.name.endswith(".old")], [])
        self.install()
        self.assertEqual(self.links(), ["Demo Site Carbon campaign.lnk", "Demo Site Claude campaign.lnk"])
        self.assertEqual(len(list(self.icons.iterdir())), 2)

    def test_a_link_another_installer_writes_while_this_one_works_is_kept(self):
        # Completion gap: the name was free at the check; another project's link takes it before the swap.
        foreign = Path(self._tmp.name) / "foreign.lnk"
        self.install()
        shutil.copyfile(self.desk / "My Proj's Carbon campaign.lnk", foreign)
        self.set_description(foreign, "conclave-unattended: D:\\elsewhere")
        self.assertEqual(self.shortcut("-Remove").returncode, 0)
        target = self.desk / "Demo Site Carbon campaign.lnk"
        installed = self.project / "scripts" / "campaign-icon.py"
        installed.write_text("import runpy, shutil, sys\n"
                             "if sys.argv[1:2] == ['badge'] and sys.argv[3:4] == ['agy']:\n"
                             f"    shutil.copyfile({str(foreign)!r}, {str(target)!r})\n"
                             f"sys.argv[0] = {str(RENDERER)!r}\nrunpy.run_path(sys.argv[0], run_name='__main__')\n",
                             encoding="utf-8")
        self.write_launchers("Demo Site")
        done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("was written by another project while this run was working", done.stdout)
        self.assertEqual(self.links(), ["Demo Site Carbon campaign.lnk"])
        self.assertEqual(target.read_bytes(), foreign.read_bytes())
        self.assertEqual(list(self.icons.glob("*.ico")), [])
        self.assertEqual([p.name for p in [*self.desk.iterdir(), *self.icons.iterdir()]
                          if ".tmp" in p.name or p.name.endswith(".old")], [])

    DEAD = 4000000  # beyond any process id Windows hands out: the run that wrote the journal is gone

    def stopped_rename(self, state):
        """The files and journal a rename to "Demo Site" leaves when it stops in `state`: every old file moved aside,
        the first runner's new badge and link moved in, the second's still under their temporary names."""
        shown = self.read_link(self.desk / "My Proj's Claude campaign.lnk")["icon"].rsplit(",", 1)[0]
        key = Path(shown).stem.split("-")[-1]  # this project's key, from the badge its own link shows
        aside, moves = [], []
        new_link = (self.desk / "My Proj's Claude campaign.lnk").read_bytes()  # a link of this project's
        for path in (*self.icons.glob("campaign-*.ico"), *self.desk.glob("*.lnk")):
            old = path.with_name(f"{path.name}.{self.DEAD}.old")
            path.rename(old)
            aside.append({"to": str(path), "old": str(old)})
        for n, (agent, label) in enumerate((("claude", "Claude"), ("agy", "Carbon"))):
            badge = self.icons / f"campaign-{agent}-{key}.ico"
            link = self.desk / f"Demo Site {label} campaign.lnk"
            for final, temp, data in ((badge, badge.with_name(f"{badge.name}.{self.DEAD}.tmp.ico"), b"new"),
                                      (link, link.with_name(f"{link.stem}.{self.DEAD}.tmp.lnk"), new_link)):
                (final if n == 0 else temp).write_bytes(data)  # the first runner is moved in, the second is not
                moves.append({"from": str(temp), "to": str(final)})
        journal = self.icons / f"campaign-{key}.{self.DEAD}.journal.json"
        journal.write_text(json.dumps({"state": state, "temps": [m["from"] for m in moves], "moves": moves,
                                       "aside": aside}), encoding="utf-8")
        return journal

    def test_a_run_stopped_while_swapping_is_rolled_back_whole(self):
        # Reconciliation 1: a stopped rename must leave the previous set, never both titles, old key's badge included.
        self.install()
        (self.icons / "campaign-claude-0badc0de.ico").write_bytes(b"old key")
        before = self.snapshot()
        journal = self.stopped_rename("swapping")
        done = self.shortcut("-Distro", "Arch", "-Icon", str(self.icon))  # any run, even one that then refuses
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("restored: ", done.stdout)
        self.assertFalse(journal.exists())
        self.assertEqual(self.snapshot(), before)

    def test_a_recovery_stopped_part_way_is_finished_by_the_next_run(self):
        # Reconciliation 2: recovery restored the original badge, then stopped before deleting the journal.
        self.install()
        before = self.snapshot()
        journal = self.stopped_rename("swapping")
        record = json.loads(journal.read_text(encoding="utf-8"))
        badge = record["moves"][0]  # the first runner's badge: moved in over the original, which is moved aside
        replaced = next(a for a in record["aside"] if a["to"] == badge["to"])
        Path(badge["to"]).unlink()                          # the first recovery took the new badge out
        Path(replaced["old"]).rename(replaced["to"])        # and put the original back, then stopped
        done = self.shortcut("-Distro", "Arch", "-Icon", str(self.icon))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertFalse(journal.exists())
        self.assertEqual(self.snapshot(), before)

    def test_a_journal_naming_files_outside_the_projects_links_is_not_played(self):
        # Reconciliation 2: a journal is a claim; one planted in a shared icon folder cannot reach anything else.
        self.install()
        outside = Path(self._tmp.name) / "precious.txt"
        outside.write_text("keep me\n", encoding="utf-8")
        (self.desk / f"notes.txt.{self.DEAD}.old").write_text("someone's\n", encoding="utf-8")  # not a link's
        claude = self.desk / "My Proj's Claude campaign.lnk"
        key = Path(self.read_link(claude)["icon"].rsplit(",", 1)[0]).stem.split("-")[-1]
        before = self.snapshot()
        for label, record in (
                ("a move to a file elsewhere", {"state": "swapping", "temps": [], "aside": [],
                                                "moves": [{"from": str(outside) + ".1.tmp.txt", "to": str(outside)}]}),
                ("a temporary file elsewhere", {"state": "writing", "temps": [str(outside)], "moves": [], "aside": []}),
                ("a file in the desktop folder that is no link", {"state": "swapping", "temps": [], "moves": [],
                 "aside": [{"to": str(self.desk / "notes.txt"),
                            "old": str(self.desk / f"notes.txt.{self.DEAD}.old")}]}),
                ("a link moved aside under another run's name", {"state": "committed", "temps": [], "moves": [],
                                                                 "aside": [{"to": str(claude), "old": str(claude)}]})):
            with self.subTest(label):
                journal = self.icons / f"campaign-{key}.{self.DEAD}.journal.json"
                journal.write_text(json.dumps(record), encoding="utf-8")
                done = self.shortcut("-Distro", "Arch", "-Icon", str(self.icon))
                self.assertIn("names files outside this project's links; it is left as it is", done.stdout)
                self.assertEqual(outside.read_text(encoding="utf-8"), "keep me\n")
                self.assertTrue(journal.exists())
                journal.unlink()
                self.assertEqual(self.snapshot(), before)

    def test_a_run_stopped_after_its_swap_is_finished(self):
        self.install()
        journal = self.stopped_rename("committed")
        record = json.loads(journal.read_text(encoding="utf-8"))
        for m in record["moves"]:  # a committed run moved them all in
            if Path(m["from"]).exists():
                Path(m["from"]).rename(m["to"])
        done = self.shortcut("-Distro", "Arch", "-Icon", str(self.icon))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertFalse(journal.exists())
        self.assertEqual(self.links(), ["Demo Site Carbon campaign.lnk", "Demo Site Claude campaign.lnk"])
        self.assertEqual([p.name for p in [*self.desk.iterdir(), *self.icons.iterdir()]
                          if ".tmp" in p.name or p.name.endswith(".old")], [])

    def test_a_journal_of_a_run_still_going_is_left_alone(self):
        self.install()
        before = self.snapshot()
        key = next(self.icons.glob("campaign-claude-*.ico")).stem.split("-")[-1]
        journal = self.icons / f"campaign-{key}.{os.getpid()}.journal.json"  # this test's own process: alive
        journal.write_text(json.dumps({"state": "swapping", "temps": [], "moves": [], "aside": []}), encoding="utf-8")
        done = self.shortcut("-Distro", "Arch", "-Icon", str(self.icon))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertTrue(journal.exists())
        journal.unlink()
        self.assertEqual(self.snapshot(), before)

    def test_the_default_icon_folder_is_named_by_the_folder_never_the_title(self):
        local = Path(self._tmp.name) / "local"
        local.mkdir()
        env = {"LOCALAPPDATA": str(local)}
        for title in (None, "Demo Site"):
            self.write_launchers(title)
            done = self.shortcut("-Distro", "Ubuntu", "-Icon", str(self.icon), icon_dir=False, **env)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(len(list((local / "My Proj's").glob("campaign-*.ico"))), 2)
        done = self.shortcut("-Remove", icon_dir=False, **env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(list((local / "My Proj's").iterdir()), [])
        self.assertFalse((local / "Demo Site").exists())


if __name__ == "__main__":
    unittest.main()
