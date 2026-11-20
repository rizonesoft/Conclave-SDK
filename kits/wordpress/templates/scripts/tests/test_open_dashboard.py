"""The dashboard opener, `scripts/open-dashboard.py` (D07 T02 section 2).

Nothing here reaches a site or starts a browser. `site_ssh.wp` is replaced by a site: `PhpSite` runs the opener's
own `STORE` and `DROP` programs under the PHP CLI against `ticket_login_harness.php`, the stand-in for WordPress that
section 1's tests use, and the tests that need it skip, naming PHP, where there is none. The browser's children are
replaced by recorders.
"""
from __future__ import annotations

import hashlib
import html
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent   # the project, or the kit's templates/ folder
OPENER = SCRIPTS / "open-dashboard.py"
PLUGIN = ROOT / "tools" / "ticket-login" / "conclave-ticket-login.php"
HARNESS = HERE / "ticket_login_harness.php"
PHP = shutil.which("php")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HEX64 = re.compile(r"[0-9a-f]{64}")
REAL_ISDIR = os.path.isdir   # kept before a test patches os.path.isdir


def load_opener():
    spec = importlib.util.spec_from_file_location("open_dashboard", OPENER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


od = load_opener()


def pin(**changes):
    """A pin the kit accepts: a Pressable staging site under a subpath, SSH set up, one WordPress user."""
    value = {"host": "pressable", "site_id": 101, "url": "https://example.com/blog", "environment": "staging",
             "ssh": {"item": None, "ssh_host": "ssh.example.com", "sftp_host": "sftp.example.com", "port": "22",
                     "username": "site-user", "wp_path": "~/htdocs"},
             "mcp": {"site": {"scheme": "basic", "item": None, "url": None, "username": "admin",
                              "wordpress_user_id": 7, "application_password_uuid": None}}}
    for dotted, new in changes.items():
        node = value
        *path, last = dotted.split("__")
        for part in path:
            node = node[part]
        node[last] = new
    return od.wp_site.validate(value)


class PhpSite:
    """`site_ssh.wp` as the site would answer it: each program runs under PHP against the harness, the options
    table carried from one call to the next. `plugin` False is a site without section 1's plugin."""

    def __init__(self, test, *, plugin=True, option=None, **case):
        self.test, self.plugin, self.case, self.calls = test, plugin, case, []
        self.options = {} if option is None else {od.OPTION: option}
        self.autoload = {}

    def wp(self, arguments, *, input=None, timeout=None, pin=None):
        self.calls.append((list(arguments), input))
        self.test.assertEqual(arguments[0], "eval")
        case = {"plugins": [str(PLUGIN)] if self.plugin else [], "eval": arguments[1], **self.case}
        if od.OPTION in self.options:
            case["option"] = self.options[od.OPTION]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            done = subprocess.run([PHP, str(HARNESS), str(path)], input=input, capture_output=True, text=True,
                                  timeout=60, creationflags=NO_WINDOW)
        self.test.assertEqual(done.returncode, 0, done.stderr)
        report = json.loads(done.stdout)
        self.options = dict(report["options"])
        self.autoload.update(report["autoload"])
        return subprocess.CompletedProcess(arguments, 0, report["echo"], "")


class FakeSite:
    """A site that answers each program with a set reply (no PHP): `store` and `drop` are what the two programs
    echo; `lost` makes the store's SSH reply fail after the write."""

    def __init__(self, store="stored", drop="dropped", lost=False):
        self.store, self.drop, self.lost, self.calls = store, drop, lost, []

    def wp(self, arguments, *, input=None, timeout=None, pin=None):
        self.calls.append((list(arguments), input))
        storing = arguments[1].startswith("if ( ! defined( 'CONCLAVE_TICKET_LOADED' )")
        if storing and self.lost:
            return subprocess.CompletedProcess(arguments, 255, "", "Connection reset")
        return subprocess.CompletedProcess(arguments, 0, self.store if storing else self.drop, "")


def run_main(argv=(), *, site=None, the_pin=None, windows=False, opener=None):
    """main() with the pin, the site and the browser replaced; (exit code, stdout, stderr, the opener's calls)."""
    out, err, opened = io.StringIO(), io.StringIO(), []
    the_pin = the_pin or pin()
    site = site or FakeSite()

    def open_browser(url):
        opened.append(url)
        if opener:
            opener(url)

    with mock.patch.object(od.wp_site, "load", return_value=the_pin), \
            mock.patch.object(od.site_ssh, "wp", site.wp), \
            mock.patch.object(od, "native_windows", return_value=windows), \
            mock.patch.object(od, "open_browser", open_browser):
        code = od.main(list(argv), out=out, err=err)
    return code, out.getvalue(), err.getvalue(), opened


class TicketAndLinkTest(unittest.TestCase):

    def test_a_ticket_is_a_fresh_token_and_its_digest(self):
        token, digest = od.ticket()
        self.assertRegex(token, r"^[0-9a-f]{64}$")
        self.assertEqual(digest, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotEqual(od.ticket()[0], token)

    def test_a_link_is_built_only_for_a_pinned_url_and_a_whole_token(self):
        token = "ab" * 32
        self.assertEqual(od.link("https://example.com/blog", token), f"https://example.com/blog/?conclave_ticket={token}")
        self.assertEqual(od.link("https://example.com", token), f"https://example.com/?conclave_ticket={token}")
        for site, bad in (("https://example.com", "ab" * 31), ("https://example.com", "AB" * 32),
                          ("https://example.com", "zz" * 32), ("http://example.com", token),
                          ("https://example.com/?x=1", token), ("https://example.com\n", token),
                          ("https://example.com", token + "\n"), (None, token)):
            with self.subTest(site=site, token=bad[:8]):
                with self.assertRaisesRegex(ValueError, "^refused to build a login link$"):
                    od.link(site, bad)


class PinnedUserTest(unittest.TestCase):

    def entries(self, *entries):
        return {"mcp": {f"e{i}": entry for i, entry in enumerate(entries)}}

    def test_one_user_named_by_every_basic_entry_is_the_user(self):
        both = self.entries({"scheme": "basic", "wordpress_user_id": 7}, {"scheme": "basic", "wordpress_user_id": "7"})
        self.assertEqual(od.pinned_user(both), 7)
        beside = self.entries({"scheme": "bearer"}, {"scheme": "basic", "wordpress_user_id": 7})
        self.assertEqual(od.pinned_user(beside), 7)

    def test_none_an_unset_entry_or_two_users_is_a_refusal(self):
        for label, pins, said in (
                ("none", self.entries({"scheme": "bearer"}), "no basic entry"),
                ("no mcp", {}, "no basic entry"),
                ("one unset", self.entries({"scheme": "basic", "wordpress_user_id": 7},
                                           {"scheme": "basic", "wordpress_user_id": None}), "names no wordpress_user_id"),
                ("two", self.entries({"scheme": "basic", "wordpress_user_id": 7},
                                     {"scheme": "basic", "wordpress_user_id": 8}), "different users")):
            with self.subTest(label):
                with self.assertRaises(od.Refusal) as caught:
                    od.pinned_user(pins)
                self.assertIn(said, str(caught.exception))
                self.assertEqual(caught.exception.code, 2)


class RefusedBeforeATicketTest(unittest.TestCase):

    def test_each_pin_that_cannot_carry_a_login_and_native_windows_is_refused_first(self):
        wpcom = pin(host="wpcom", ssh__ssh_host=None, mcp={"site": {"scheme": "basic", "wordpress_user_id": 7}})
        for label, the_pin, windows, said in (
                ("no ssh", wpcom, False, "the site pin has no SSH (ssh.ssh_host is null), so no ticket can be stored"),
                ("no url", pin(url=None, mcp={"site": {"scheme": "basic", "wordpress_user_id": 7}}), False,
                 "the site pin is refused: not set in .conclave/wordpress-site.json yet: url"),
                ("no wp_path", pin(ssh__wp_path=None), False,
                 "the site pin is refused: not set in .conclave/wordpress-site.json yet: ssh.wp_path"),
                ("native windows", pin(), True, od.WINDOWS)):
            with self.subTest(label):
                site = FakeSite()
                with mock.patch.object(od, "ticket", wraps=od.ticket) as made:
                    code, out, err, opened = run_main(site=site, the_pin=the_pin, windows=windows)
                self.assertEqual((code, out, err), (2, "", f"open-dashboard: {said}\n"))
                self.assertEqual((made.call_count, site.calls, opened), (0, [], []))

    def test_an_unreadable_pin_is_refused_first(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(od.wp_site, "load", side_effect=FileNotFoundError("x")), \
                mock.patch.object(od, "native_windows", return_value=False):
            self.assertEqual(od.main([], out=out, err=err), 2)
        self.assertEqual(err.getvalue(), "open-dashboard: the site pin .conclave/wordpress-site.json cannot be read\n")


@unittest.skipUnless(PHP, "the store and drop programs run under PHP, which is not on this machine's PATH")
class StoreAndDropOnTheSiteTest(unittest.TestCase):

    def test_store_writes_the_digest_the_user_and_an_expiry_on_the_sites_clock_with_autoload_off(self):
        site = PhpSite(self)
        token, digest = od.ticket()
        before = int(time.time())
        with mock.patch.object(od.site_ssh, "wp", site.wp):
            od.store(pin(), digest, 7)
        after = int(time.time())
        stored = site.options[od.OPTION]
        self.assertEqual((stored["hash"], stored["user"]), (digest, 7))
        self.assertIsInstance(stored["expires"], int)
        self.assertTrue(before + od.LIFETIME <= stored["expires"] <= after + od.LIFETIME, stored["expires"])
        self.assertIs(site.autoload[od.OPTION], False)
        [(arguments, given)] = site.calls
        self.assertEqual(given, digest + "\n")   # only the digest crosses, on standard input
        self.assertNotIn(token, json.dumps(site.calls))
        self.assertNotIn(digest, json.dumps(arguments))

    def test_a_site_without_the_plugin_a_bad_digest_and_a_wrong_read_back_are_refused(self):
        _, digest = od.ticket()
        with mock.patch.object(od.site_ssh, "wp", PhpSite(self, plugin=False).wp):
            with self.assertRaisesRegex(od.Refusal, "plugin is not active on the site: python3 scripts/ticket-login.py install"):
                od.store(pin(), digest, 7)
        site = PhpSite(self)
        with mock.patch.object(od.site_ssh, "wp", site.wp):
            self.assertEqual(od._remote(pin(), od.STORE % {"lifetime": 60, "user": 7, "option": od.OPTION}, "XYZ"),
                             "bad digest")
            with self.assertRaisesRegex(od.Refusal, "refused to store a malformed ticket"):
                od.store(pin(), digest.upper(), 7)
        self.assertEqual(site.options, {})
        with mock.patch.object(od.site_ssh, "wp", PhpSite(self, read_back_differs=True).wp):
            with self.assertRaisesRegex(od.Refusal, "^the site did not confirm that it stored the ticket$"):
                od.store(pin(), digest, 7)

    def test_drop_removes_this_runs_ticket_and_never_another_runs(self):
        _, mine = od.ticket()
        _, theirs = od.ticket()
        ticket = {"hash": theirs, "expires": int(time.time()) + 60, "user": 7}
        site = PhpSite(self, option=ticket)
        with mock.patch.object(od.site_ssh, "wp", site.wp):
            self.assertEqual(od.drop(pin(), mine), "not ours")
            self.assertEqual(site.options[od.OPTION]["hash"], theirs)   # run B's newer ticket stays
            self.assertEqual(od.drop(pin(), theirs), "dropped")
            self.assertEqual(site.options, {})
            self.assertEqual(od.drop(pin(), theirs), "absent")

    def test_a_ticket_replaced_between_the_read_and_the_delete_stays_and_a_failed_delete_is_refused(self):
        _, mine = od.ticket()
        _, newer = od.ticket()
        now = int(time.time()) + 60
        site = PhpSite(self, option={"hash": mine, "expires": now, "user": 7},
                       replace_before_delete={"hash": newer, "expires": now, "user": 7})
        with mock.patch.object(od.site_ssh, "wp", site.wp):
            self.assertEqual(od.drop(pin(), mine), "gone")
        self.assertEqual(site.options[od.OPTION]["hash"], newer)
        failing = PhpSite(self, option={"hash": mine, "expires": now, "user": 7}, delete_fails=True)
        with mock.patch.object(od.site_ssh, "wp", failing.wp):
            with self.assertRaisesRegex(od.Refusal, "^the site did not confirm that it removed the ticket$"):
                od.drop(pin(), mine)

    def test_the_default_opens_the_pinned_url_with_the_token_the_site_holds(self):
        site, seen = PhpSite(self), []

        def opener(url):   # the site holds this very token's digest while the browser opens
            token = url.rsplit("=", 1)[1]
            seen.append((url, site.options[od.OPTION]["hash"] == hashlib.sha256(token.encode()).hexdigest()))

        code, out, err, opened = run_main(site=site, the_pin=pin(), opener=opener)
        self.assertEqual((code, err), (0, ""), err)
        [(url, held)] = seen
        self.assertRegex(url, r"^https://example\.com/blog/\?conclave_ticket=[0-9a-f]{64}$")
        self.assertTrue(held, "the browser was opened on a token the site does not hold")
        self.assertEqual(out, "open-dashboard: the dashboard is opening in the browser, logged in "
                              "(the link works once, within 60 seconds)\n")

    def test_check_stores_confirms_drops_and_opens_nothing(self):
        site = PhpSite(self)
        code, out, err, opened = run_main(["--check"], site=site)
        self.assertEqual((code, err, opened), (0, "", []))
        self.assertEqual(out, "open-dashboard: the site stored a ticket and removed it again; nothing was opened\n")
        self.assertEqual(site.options, {})
        self.assertEqual(len(site.calls), 2)
        self.assertEqual(site.calls[0][1], site.calls[1][1])   # the drop named the very digest the store wrote


class CleanUpTest(unittest.TestCase):

    def test_a_browser_that_fails_takes_the_ticket_off_the_site(self):
        site = FakeSite()

        def fails(url):
            raise od.Refusal("PowerShell could not open the browser")

        code, out, err, _ = run_main(site=site, opener=fails)
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err, "open-dashboard: PowerShell could not open the browser\n"
                              "open-dashboard: the ticket was removed from the site\n")
        self.assertEqual([call[0][1] == od.DROP % {"option": od.OPTION} for call in site.calls], [False, True])

    def test_a_lost_store_reply_takes_the_ticket_off_the_site(self):
        site = FakeSite(lost=True)
        code, out, err, opened = run_main(site=site)
        self.assertEqual((code, out, opened), (1, "", []))
        self.assertEqual(err, "open-dashboard: the site did not confirm that it stored the ticket\n"
                              "open-dashboard: the ticket was removed from the site\n")
        self.assertEqual(len(site.calls), 2)

    def test_a_removal_that_cannot_be_confirmed_says_when_the_ticket_dies(self):
        code, _, err, _ = run_main(site=FakeSite(lost=True, drop="failed"))
        self.assertEqual(code, 1)
        self.assertEqual(err, "open-dashboard: the site did not confirm that it stored the ticket\n"
                              "open-dashboard: the ticket could not be removed from the site; it expires within 60 seconds\n")
        code, out, err, _ = run_main(["--check"], site=FakeSite(drop="failed"))
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err, "open-dashboard: the site did not confirm that it removed the ticket\n"
                              "open-dashboard: the ticket expires within 60 seconds\n")

    def test_a_site_without_the_plugin_is_told_how_to_install_it_and_nothing_is_removed(self):
        site = FakeSite(store="no plugin")
        code, out, err, opened = run_main(site=site)
        self.assertEqual((code, out, opened, len(site.calls)), (1, "", [], 1))
        self.assertEqual(err, "open-dashboard: the ticket login plugin is not active on the site: "
                              "python3 scripts/ticket-login.py install puts it there\n")


class FixedMessagesTest(unittest.TestCase):
    """No failure prints the token, the digest or the link, whatever the exception carried."""

    def leaky(self, made):
        token, digest = made
        return RuntimeError(f"{token} {digest} https://example.com/blog/?conclave_ticket={token[:20]} child said {token}")

    def check(self, err, out):
        for text in (err, out):
            self.assertIsNone(HEX64.search(text), text)
            self.assertNotIn("conclave_ticket=", text)

    def test_each_step_that_raises_with_the_token_prints_only_fixed_lines(self):
        made = od.ticket()
        leak = self.leaky(made)
        for label, patches, expected in (
                ("store", {"store": mock.Mock(side_effect=leak)},
                 "open-dashboard: RuntimeError: unexpected failure\nopen-dashboard: the ticket was removed from the site\n"),
                ("store and its clean-up", {"store": mock.Mock(side_effect=leak), "drop": mock.Mock(side_effect=leak)},
                 "open-dashboard: RuntimeError: unexpected failure\n"
                 "open-dashboard: the ticket could not be removed from the site; it expires within 60 seconds\n"),
                ("link", {"link": mock.Mock(side_effect=leak)}, "open-dashboard: RuntimeError: unexpected failure\n")):
            with self.subTest(label), mock.patch.object(od, "ticket", return_value=made):
                with mock.patch.multiple(od, **patches):
                    code, out, err, _ = run_main()
                self.assertEqual((code, out, err), (1, "", expected))
                self.check(err, out)

    def test_a_browser_and_a_check_that_raise_with_the_token_print_only_fixed_lines(self):
        made = od.ticket()
        leak = self.leaky(made)

        def opener(url):
            raise leak

        with mock.patch.object(od, "ticket", return_value=made):
            code, out, err, _ = run_main(opener=opener)
            self.assertEqual(err, "open-dashboard: RuntimeError: unexpected failure\n"
                                  "open-dashboard: the ticket was removed from the site\n")
            self.check(err, out)
            with mock.patch.object(od, "drop", side_effect=leak):
                code, out, err, _ = run_main(["--check"])
            self.assertEqual((code, err), (1, "open-dashboard: RuntimeError: unexpected failure\n"
                                              "open-dashboard: the ticket expires within 60 seconds\n"))
            self.check(err, out)


class BrowserTest(unittest.TestCase):
    """Where the link travels and that the browser is really asked to open it."""

    URL = "https://example.com/blog/?conclave_ticket=" + "cd" * 32

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pages = Path(self._tmp.name) / "cache" / "conclave-dashboard"
        patcher = mock.patch.object(od, "PAGES", self.pages)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.runs = []

    def child(self, code=0):
        def run(argv, **kwargs):
            self.runs.append((list(argv), kwargs))
            return subprocess.CompletedProcess(argv, code, f"said {self.URL}", f"error {self.URL}")
        return run

    def open(self, *, wsl, which, mnt_c=True, code=0):
        environ = {"WSL_DISTRO_NAME": "Ubuntu"} if wsl else {}
        with mock.patch.dict(od.os.environ, environ, clear=True), \
                mock.patch.object(od.shutil, "which", side_effect=lambda name: which.get(name)), \
                mock.patch.object(od.os.path, "isdir", side_effect=lambda path: mnt_c if path == "/mnt/c" else REAL_ISDIR(path)), \
                mock.patch.object(od.subprocess, "run", self.child(code)):
            od.open_browser(self.URL)

    def test_from_wsl_the_link_goes_to_powershell_on_stdin_and_start_process_opens_it(self):
        for found, shell in (({"pwsh.exe": "/c/pwsh.exe", "powershell.exe": "/c/ps.exe"}, "/c/pwsh.exe"),
                             ({"powershell.exe": "/c/ps.exe"}, "/c/ps.exe")):
            with self.subTest(shell):
                self.runs.clear()
                self.open(wsl=True, which=found)
                [(argv, kwargs)] = self.runs
                self.assertEqual(argv[0], shell)
                self.assertEqual(argv[1:4], ["-NoProfile", "-NonInteractive", "-Command"])
                self.assertIn("[Console]::In.ReadLine()", argv[4])
                self.assertIn("Start-Process -FilePath $u", argv[4])
                self.assertEqual(kwargs["input"], self.URL + "\n")
                self.assertEqual(kwargs["cwd"], "/mnt/c")
                self.assertNotIn("conclave_ticket", " ".join(argv))

    def test_from_wsl_each_missing_piece_and_a_failed_child_is_refused(self):
        for label, kwargs, said in (
                ("no powershell", {"which": {}}, "there is no pwsh.exe or powershell.exe to open the browser from WSL"),
                ("no /mnt/c", {"which": {"pwsh.exe": "/c/pwsh.exe"}, "mnt_c": False},
                 "there is no Windows drive at /mnt/c to start PowerShell from"),
                ("child failed", {"which": {"pwsh.exe": "/c/pwsh.exe"}, "code": 1}, "PowerShell could not open the browser")):
            with self.subTest(label):
                with self.assertRaises(od.Refusal) as caught:
                    self.open(wsl=True, **kwargs)
                self.assertEqual(str(caught.exception), said)

    def page_target(self, page):
        text = page.read_text(encoding="utf-8")
        refresh = re.search(r'<meta http-equiv="refresh" content="0;url=([^"]+)">', text)
        script = re.search(r"location\.replace\((.+)\);", text)
        return html.unescape(refresh[1]), json.loads(script[1])

    def test_on_linux_the_link_is_in_a_private_page_of_its_own_and_xdg_open_gets_its_path(self):
        self.open(wsl=False, which={"xdg-open": "/usr/bin/xdg-open"})
        [(argv, _)] = self.runs
        self.assertEqual(argv[0], "/usr/bin/xdg-open")
        page = Path(argv[1])
        self.assertEqual(page.parent, self.pages)
        self.assertEqual(self.page_target(page), (self.URL, self.URL))
        self.assertNotIn("conclave_ticket", " ".join(argv))
        if os.name == "posix":
            self.assertEqual(self.pages.stat().st_mode & 0o777, 0o700)
            self.assertEqual(page.stat().st_mode & 0o777, 0o600)

    def test_two_launches_get_two_pages_and_only_dead_pages_are_removed(self):
        first, second = self.URL, "https://example.org/?conclave_ticket=" + "ef" * 32
        self.open(wsl=False, which={"xdg-open": "/usr/bin/xdg-open"})
        with mock.patch.object(BrowserTest, "URL", second):
            self.open(wsl=False, which={"xdg-open": "/usr/bin/xdg-open"})
        pages = [Path(argv[1]) for argv, _ in self.runs]
        self.assertNotEqual(pages[0], pages[1])
        self.assertEqual([self.page_target(p)[0] for p in pages], [first, second])
        dead = time.time() - od.LIFETIME - 5
        os.utime(pages[0], (dead, dead))
        self.open(wsl=False, which={"xdg-open": "/usr/bin/xdg-open"})
        self.assertFalse(pages[0].exists(), "a page older than the ticket's lifetime was kept")
        self.assertTrue(pages[1].exists(), "a page the browser may still need was removed")
        self.assertEqual(list(self.pages.glob("*.tmp")), [])

    def test_on_linux_each_missing_piece_and_a_failed_child_is_refused(self):
        with self.assertRaises(od.Refusal) as caught:
            self.open(wsl=False, which={})
        self.assertEqual(str(caught.exception), "there is no xdg-open to open the browser")
        with self.assertRaises(od.Refusal) as caught:
            self.open(wsl=False, which={"xdg-open": "/usr/bin/xdg-open"}, code=4)
        self.assertEqual(str(caught.exception), "xdg-open could not open the browser")
        shutil.rmtree(self.pages)   # the failed launch above made the folder; a file stands in its place now
        self.pages.write_text("a file where the folder goes", encoding="utf-8")
        self.runs.clear()
        with self.assertRaises(od.Refusal) as caught:
            self.open(wsl=False, which={"xdg-open": "/usr/bin/xdg-open"})
        self.assertEqual(str(caught.exception),
                         f"the folder {self.pages} cannot be written, so the browser cannot be handed the link")
        self.assertEqual(self.runs, [])


class CommandLineTest(unittest.TestCase):

    def test_help_prints_its_usage_in_a_scratch_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = Path(tmp) / "project" / "scripts"
            (scripts / "lib").mkdir(parents=True)
            shutil.copyfile(OPENER, scripts / "open-dashboard.py")
            for name in ("site_ssh.py", "wp_site.py"):
                shutil.copyfile(SCRIPTS / "lib" / name, scripts / "lib" / name)
            done = subprocess.run([sys.executable, "-B", str(scripts / "open-dashboard.py"), "--help"],
                                  capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("usage: open-dashboard.py [-h] [--check]", done.stdout)
        self.assertIn("Run it from WSL or Linux.", done.stdout)


if __name__ == "__main__":
    unittest.main()
