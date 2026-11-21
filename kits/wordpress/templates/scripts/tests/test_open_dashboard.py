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
        # Pressable's wp refuses a global flag after the command ("unknown --url parameter"), so --url comes first.
        self.test.assertEqual(arguments[:2], ["--url=https://example.com/blog", "eval"])
        case = {"plugins": [str(PLUGIN)] if self.plugin else [], "eval": arguments[2], **self.case}
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
        storing = arguments[2].startswith("if ( ! defined( 'CONCLAVE_TICKET_LOADED' )")
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
        both = pin(mcp={"a": {"scheme": "basic", "wordpress_user_id": 7}, "b": {"scheme": "basic", "wordpress_user_id": 7}})
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
                                     {"scheme": "basic", "wordpress_user_id": 8}), "different users"),
                ("not a whole number", self.entries({"scheme": "basic", "wordpress_user_id": "7"}), "is not a user"),
                ("true", self.entries({"scheme": "basic", "wordpress_user_id": True}), "is not a user")):
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
                 "not set in .conclave/wordpress-site.json yet: url"),
                ("no wp_path", pin(ssh__wp_path=None), False,
                 "not set in .conclave/wordpress-site.json yet: ssh.wp_path"),
                ("native windows", pin(), True, od.WINDOWS)):
            with self.subTest(label):
                site = FakeSite()
                with mock.patch.object(od, "ticket", wraps=od.ticket) as made:
                    code, out, err, opened = run_main(site=site, the_pin=the_pin, windows=windows)
                self.assertEqual((code, out, err), (2, "", f"open-dashboard: {said}\n"))
                self.assertEqual((made.call_count, site.calls, opened), (0, [], []))

    def test_an_invalid_pin_is_refused_in_a_fixed_sentence(self):
        # Round 1: the validator's text named an unknown key, which a malformed pin could fill with anything.
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(od.wp_site, "load",
                               side_effect=ValueError("unknown key unexpected-input-marker\nforged line")), \
                mock.patch.object(od, "native_windows", return_value=False):
            self.assertEqual(od.main([], out=out, err=err), 2)
        self.assertEqual(err.getvalue(), "open-dashboard: the site pin .conclave/wordpress-site.json is not valid: "
                                         "python3 scripts/site-access.py check says why\n")

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
        self.assertEqual(arguments[0], "--url=https://example.com/blog")   # the pinned site of a multisite, before eval
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

    def test_a_read_that_fails_is_no_proof_the_ticket_is_gone(self):
        # Round 1: wpdb::get_var answers null on a failed query; DROP took that for absence.
        _, mine = od.ticket()
        site = PhpSite(self, option={"hash": mine, "expires": int(time.time()) + 60, "user": 7}, read_fails=True)
        with mock.patch.object(od.site_ssh, "wp", site.wp):
            with self.assertRaisesRegex(od.Refusal, "^the site did not confirm that it removed the ticket$"):
                od.drop(pin(), mine)
        self.assertEqual(site.options[od.OPTION]["hash"], mine)
        self.assertEqual(site.calls[0][0][0], "--url=https://example.com/blog")

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
        self.assertEqual([call[0][2] == od.DROP % {"option": od.OPTION} for call in site.calls], [False, True])

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


class InterruptTest(unittest.TestCase):
    """Round 1: Ctrl+C escaped `except Exception` and left a live ticket on the site."""

    def test_an_interrupt_while_the_browser_starts_or_the_store_runs_removes_the_ticket(self):
        def interrupted(url):
            raise KeyboardInterrupt

        site = FakeSite()
        code, out, err, _ = run_main(site=site, opener=interrupted)
        self.assertEqual((code, out), (130, ""))
        self.assertEqual(err, "open-dashboard: interrupted\nopen-dashboard: the ticket was removed from the site\n")
        self.assertEqual(len(site.calls), 2)
        site = FakeSite()
        with mock.patch.object(od, "store", side_effect=KeyboardInterrupt):
            code, out, err, opened = run_main(site=site)
        self.assertEqual((code, opened), (130, []))
        self.assertEqual(err, "open-dashboard: interrupted\nopen-dashboard: the ticket was removed from the site\n")


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
        self.runs, self.started = [], []

    def open(self, *, wsl, which, mnt_c=True, code=0, handler="firefox.desktop", entry="Exec=firefox %u\n",
             starts=None, extra_env=None):
        """open_browser with the platform faked: `which` the programs on PATH, `handler` what xdg-mime answers for
        https links, `entry` the lines of that desktop entry's [Desktop Entry] group, `starts` a Popen stand-in."""
        data = Path(self._tmp.name) / "data"
        if entry is not None:
            (data / "applications").mkdir(parents=True, exist_ok=True)
            (data / "applications" / "firefox.desktop").write_text("[Desktop Entry]\nName=Firefox\n" + entry,
                                                                    encoding="utf-8")
        environ = {"WSL_DISTRO_NAME": "Ubuntu"} if wsl else {"XDG_DATA_HOME": str(data), "XDG_DATA_DIRS": "/nowhere"}
        if extra_env:
            environ.update(extra_env)

        def run(argv, **kwargs):
            self.runs.append((list(argv), kwargs))
            answer = handler + "\n" if argv[:2] == [which.get("xdg-mime"), "query"] else f"said {self.URL}"
            return subprocess.CompletedProcess(argv, code, answer, f"error {self.URL}")

        def popen(argv, **kwargs):
            self.started.append((list(argv), kwargs))
            if starts:
                starts(argv)
            return mock.Mock()

        with mock.patch.dict(od.os.environ, environ, clear=True), \
                mock.patch.object(od.shutil, "which", side_effect=lambda name: which.get(name)), \
                mock.patch.object(od.os.path, "isdir", side_effect=lambda path: mnt_c if path == "/mnt/c" else REAL_ISDIR(path)), \
                mock.patch.object(od.subprocess, "run", run), mock.patch.object(od.subprocess, "Popen", popen):
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

    LINUX = {"xdg-mime": "/usr/bin/xdg-mime"}

    def test_on_linux_the_page_goes_to_the_browser_that_opens_https_links(self):
        # Round 1: xdg-open on an HTML file picks the text/html handler, which can be an editor.
        self.open(wsl=False, which=self.LINUX)
        [(query, _)] = self.runs
        self.assertEqual(query, ["/usr/bin/xdg-mime", "query", "default", "x-scheme-handler/https"])
        [(argv, kwargs)] = self.started
        self.assertEqual(argv[0], "firefox")
        self.assertTrue(argv[1].startswith("file://"), argv)
        self.assertEqual(kwargs.get("start_new_session"), True)
        self.assertNotIn("conclave_ticket", " ".join(argv))
        [made] = self.pages.glob("open-*.html")
        self.assertEqual(argv[1], made.as_uri())
        self.assertEqual(self.page_target(made), (self.URL, self.URL))
        if os.name == "posix":
            self.assertEqual(self.pages.stat().st_mode & 0o777, 0o700)
            self.assertEqual(made.stat().st_mode & 0o777, 0o600)

    def test_each_kind_of_desktop_entry_command_gets_the_page(self):
        desktop = str(Path(self._tmp.name) / "data" / "applications" / "firefox.desktop")
        for label, entry, expected in (
                ("a file code", "Exec=browser --new-window %f\n", ["browser", "--new-window", "<path>"]),
                ("a quoted program and a list code", 'Exec="/opt/my browser/br" %U\n', ["/opt/my browser/br", "<uri>"]),
                ("no code", "Exec=browser\n", ["browser", "<path>"]),
                ("name, desktop location and icon codes",
                 "Icon=firefox-icon\nExec=wrapper --name %c --desktop %k %i %u\n",
                 ["wrapper", "--name", "Firefox", "--desktop", "<desktop>", "--icon", "firefox-icon", "<uri>"]),
                ("missing icon omits %i while keeping %c position",
                 "Exec=wrapper --name %c %i %u\n",
                 ["wrapper", "--name", "Firefox", "<uri>"]),
                ("inline field codes and literal percent",
                 "Exec=browser --zoom=100%% --name=%c %u\n",
                 ["browser", "--zoom=100%", "--name=Firefox", "<uri>"]),
                ("escaped percent before u appends path",
                 "Exec=browser --flag=%%u\n",
                 ["browser", "--flag=%u", "<path>"]),
                ("another group first", "[Desktop Action new]\nExec=wrong %u\n", None)):
            with self.subTest(label):
                self.started.clear()
                self.runs.clear()
                if expected is None:   # an Exec outside [Desktop Entry] is not the entry's command
                    with self.assertRaises(od.Refusal) as caught:
                        self.open(wsl=False, which=self.LINUX, entry=entry)
                    self.assertEqual(str(caught.exception), "the browser's desktop entry firefox.desktop has no command to run")
                    continue
                before = set(self.pages.glob("open-*.html"))
                self.open(wsl=False, which=self.LINUX, entry=entry)
                [(argv, _)] = self.started
                [page] = set(self.pages.glob("open-*.html")) - before
                mapping = {"<path>": str(page), "<uri>": page.as_uri(), "<desktop>": desktop}
                self.assertEqual(argv, [mapping.get(w, w) for w in expected])
                self.assertNotIn("conclave_ticket", " ".join(argv))

    def test_localized_desktop_entry_name_and_icon_follow_locale_precedence(self):
        desktop = str(Path(self._tmp.name) / "data" / "applications" / "firefox.desktop")
        entry = ("Name[fr]=Navigateur\nName[fr_FR.UTF-8]=Navigateur FR\nName[fr_CA]=Navigateur CA\n"
                 "Name[sr_RS.UTF-8@latin]=Pregledac RS\nName[sr@latin]=Pregledac\n"
                 "Icon=firefox-icon\nIcon[fr_FR.UTF-8]=firefox-fr-utf8\nIcon[fr]=firefox-fr\n"
                 "Exec=wrapper --name %c --desktop %k %i %u\n")
        for label, extra_env, name, icon in (
                ("LC_ALL matches encoding-bearing key suffix", {"LC_ALL": "fr_FR.UTF-8"}, "Navigateur FR", "firefox-fr-utf8"),
                ("LC_ALL strips encoding on both sides", {"LC_ALL": "fr_FR.ISO-8859-1"}, "Navigateur FR", "firefox-fr-utf8"),
                ("LC_ALL matches lang_COUNTRY over lang", {"LC_ALL": "fr_CA.UTF-8"}, "Navigateur CA", "firefox-fr"),
                ("LC_ALL falls back to lang", {"LC_ALL": "fr_BE.UTF-8"}, "Navigateur", "firefox-fr"),
                ("LC_MESSAGES matches encoding-bearing modifier key", {"LC_MESSAGES": "sr_RS.UTF-8@latin"}, "Pregledac RS", "firefox-icon"),
                ("LC_MESSAGES falls back to lang@modifier", {"LC_MESSAGES": "sr_ME.UTF-8@latin"}, "Pregledac", "firefox-icon"),
                ("LANG falls back to unqualified", {"LANG": "de_DE.UTF-8"}, "Firefox", "firefox-icon"),
                ("C locale uses unqualified", {"LC_ALL": "C"}, "Firefox", "firefox-icon")):
            with self.subTest(label):
                self.started.clear()
                self.runs.clear()
                before = set(self.pages.glob("open-*.html"))
                self.open(wsl=False, which=self.LINUX, entry=entry, extra_env=extra_env)
                [(argv, _)] = self.started
                [page] = set(self.pages.glob("open-*.html")) - before
                self.assertEqual(argv, ["wrapper", "--name", name, "--desktop", desktop, "--icon", icon, page.as_uri()])
                self.assertNotIn("conclave_ticket", " ".join(argv))

    def test_two_launches_get_two_pages_and_only_dead_pages_are_removed(self):
        first, second = self.URL, "https://example.org/?conclave_ticket=" + "ef" * 32
        self.open(wsl=False, which=self.LINUX)
        with mock.patch.object(BrowserTest, "URL", second):
            self.open(wsl=False, which=self.LINUX)
        pages = sorted(self.pages.glob("open-*.html"), key=lambda f: self.page_target(f)[0] != first)
        self.assertEqual(len(pages), 2)
        self.assertEqual([self.page_target(p)[0] for p in pages], [first, second])
        self.assertEqual({argv[1] for argv, _ in self.started}, {p.as_uri() for p in pages})
        dead = time.time() - od.LIFETIME - 5
        os.utime(pages[0], (dead, dead))
        self.open(wsl=False, which=self.LINUX)
        self.assertFalse(pages[0].exists(), "a page older than the ticket's lifetime was kept")
        self.assertTrue(pages[1].exists(), "a page the browser may still need was removed")
        self.assertEqual(list(self.pages.glob("*.tmp")), [])

    def test_on_linux_each_missing_piece_is_refused_before_a_browser_starts(self):
        def fails(argv):
            raise FileNotFoundError(argv[0])

        for label, kwargs, said in (
                ("no xdg-mime", {"which": {}}, "there is no xdg-mime to find the browser that opens https links"),
                ("no browser set", {"which": self.LINUX, "handler": ""},
                 "no browser is set to open https links (xdg-mime query default x-scheme-handler/https)"),
                ("a strange answer", {"which": self.LINUX, "handler": "../evil.desktop"},
                 "no browser is set to open https links (xdg-mime query default x-scheme-handler/https)"),
                ("xdg-mime failed", {"which": self.LINUX, "code": 3},
                 "no browser is set to open https links (xdg-mime query default x-scheme-handler/https)"),
                ("no entry file", {"which": self.LINUX, "handler": "chromium.desktop"},
                 "the browser's desktop entry chromium.desktop is in no applications folder"),
                ("no command", {"which": self.LINUX, "entry": "Name=only\n"},
                 "the browser's desktop entry firefox.desktop has no command to run"),
                ("an unclosed quote", {"which": self.LINUX, "entry": 'Exec="browser %u\n'},
                 "the browser's desktop entry firefox.desktop has no command to run"),
                ("the browser cannot start", {"which": self.LINUX, "starts": fails},
                 "the browser that opens https links could not be started")):
            with self.subTest(label):
                with self.assertRaises(od.Refusal) as caught:
                    self.open(wsl=False, **kwargs)
                self.assertEqual(str(caught.exception), said)
        shutil.rmtree(self.pages)   # the launches above made the folder; a file stands in its place now
        self.pages.write_text("a file where the folder goes", encoding="utf-8")
        self.started.clear()
        with self.assertRaises(od.Refusal) as caught:
            self.open(wsl=False, which=self.LINUX)
        self.assertEqual(str(caught.exception),
                         f"the folder {self.pages} cannot be written, so the browser cannot be handed the link")
        self.assertEqual(self.started, [])


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
