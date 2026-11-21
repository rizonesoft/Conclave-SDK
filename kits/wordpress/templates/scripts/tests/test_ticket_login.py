"""The one-use ticket login plugin, `tools/ticket-login/conclave-ticket-login.php` (D07 T02 section 1).

Two kinds of test. The text tests read the plugin and hold the properties its safety rests on, each proven able to
fail on a copy with that one property changed. The behaviour tests run the plugin under the PHP CLI against
`ticket_login_harness.php`, a stand-in for the WordPress functions it calls, and skip, naming PHP, where there is no
PHP. Nothing here reaches a site.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]   # the project, or the kit's templates/ folder
PLUGIN = ROOT / "tools" / "ticket-login" / "conclave-ticket-login.php"
HARNESS = HERE / "ticket_login_harness.php"
PHP = shutil.which("php")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TOKEN = "0123456789abcdef" * 4
HASH = hashlib.sha256(TOKEN.encode()).hexdigest()
ADMIN = {"7": {"login": "site-admin", "caps": ["manage_options", "read"]}}


def code_of(text: str) -> str:
    """The plugin's PHP without its comments, so a property is read from what runs."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)//.*$", "", text)


# Each property the plugin's safety rests on: (what it is, a check on the code, a copy with that one property broken).
def _delete_before_compare(code):
    return 0 <= code.find("DELETE FROM") < code.find("hash_equals(")


def _delete_bound_to_the_ticket_read(code):
    # Removed by name and by the exact value read (round 1: the Options API deletes by name only), and only the
    # request that removed one row goes on.
    return ("WHERE option_name = %s AND option_value = %s\", CONCLAVE_TICKET_OPTION, $raw" in code
            and re.search(r"1\s*!==\s*\$removed", code) is not None and "delete_option(" not in code)


HASH_CHECK = ("\t\tif ( ! hash_equals( $ticket['hash'], hash( 'sha256', $token ) ) ) {\n"
              "\t\t\tconclave_ticket_login_refuse();\n\t\t}\n")


def _hash_equals_not_equality(code):
    return "hash_equals(" in code and re.search(r"\[\s*'hash'\s*\]\s*[!=]==?|[!=]==?\s*\$ticket\[\s*'hash'", code) is None


PROPERTIES = {
    "the ticket is deleted before the hash is compared": (
        _delete_before_compare,
        lambda text: text.replace(HASH_CHECK, "", 1).replace("\t\tglobal $wpdb;\n", HASH_CHECK + "\t\tglobal $wpdb;\n", 1)),
    "the delete is bound to the ticket read, and decides": (
        _delete_bound_to_the_ticket_read,
        lambda text: text.replace("if ( 1 !== $removed ) {", "if ( false ) {", 1)),
    "the hash is compared with hash_equals, never ==": (
        _hash_equals_not_equality,
        lambda text: text.replace("! hash_equals( $ticket['hash'], hash( 'sha256', $token ) )", "$ticket['hash'] !== hash( 'sha256', $token )", 1)),
    "the user must hold manage_options": (
        lambda code: "user_can( $user, 'manage_options' )" in code,
        lambda text: text.replace("'manage_options'", "'read'", 1)),
    "a failure is wp_die with 403": (
        lambda code: re.search(r"wp_die\([^;]*'response'\s*=>\s*403", code, re.S) is not None,
        lambda text: text.replace("'response' => 403", "'response' => 200", 1)),
    "the redirect is wp_safe_redirect( admin_url() )": (
        lambda code: "wp_safe_redirect( admin_url() )" in code,
        lambda text: text.replace("wp_safe_redirect( admin_url() )", "wp_redirect( admin_url() )", 1)),
    "the login cookie does not persist": (
        lambda code: "wp_set_auth_cookie( $user->ID, false )" in code,
        lambda text: text.replace("wp_set_auth_cookie( $user->ID, false )", "wp_set_auth_cookie( $user->ID, true )", 1)),
    "the file stops outside WordPress": (
        lambda code: code.lstrip().startswith("<?php") and "defined( 'ABSPATH' ) || exit;" in code,
        lambda text: text.replace("defined( 'ABSPATH' ) || exit;", "", 1)),
    "each constant is defined once": (
        lambda code: all(f"if ( ! defined( '{name}' ) )" in code
                         for name in ("CONCLAVE_TICKET_LOADED", "CONCLAVE_TICKET_OPTION", "CONCLAVE_TICKET_QUERY")),
        lambda text: text.replace("if ( ! defined( 'CONCLAVE_TICKET_QUERY' ) ) {\n\t\tdefine( 'CONCLAVE_TICKET_QUERY', 'conclave_ticket' );\n\t}",
                                  "define( 'CONCLAVE_TICKET_QUERY', 'conclave_ticket' );", 1)),
}


class TextTest(unittest.TestCase):
    def setUp(self):
        self.text = PLUGIN.read_text(encoding="utf-8")

    def test_each_property_holds_and_each_check_fails_on_a_copy_without_it(self):
        for name, (holds, break_it) in PROPERTIES.items():
            with self.subTest(property=name):
                self.assertTrue(holds(code_of(self.text)), name)
                broken = break_it(self.text)
                self.assertNotEqual(broken, self.text, f"the copy for {name!r} changed nothing")
                self.assertFalse(holds(code_of(broken)), f"the check for {name!r} passes a copy without it")

    def test_the_names_and_the_header_are_the_kits(self):
        self.assertIn("define( 'CONCLAVE_TICKET_OPTION', 'conclave_login_ticket' );", self.text)
        self.assertIn("define( 'CONCLAVE_TICKET_QUERY', 'conclave_ticket' );", self.text)
        self.assertRegex(self.text, r"(?m)^ \* Plugin Name: Conclave ticket login$")
        self.assertRegex(self.text, r"(?m)^ \* Version: \d+\.\d+\.\d+$")
        self.assertIn("holds no key", self.text.lower())

    def test_the_file_names_no_site_owner_or_client(self):
        # Neutral: no address, host or domain of any site (example.com is the documentation's own), no e-mail.
        self.assertNotRegex(self.text, r"https?://")
        self.assertNotRegex(self.text, r"[\w.-]+@[\w-]+\.\w+")
        self.assertNotRegex(self.text, r"\b[\w-]+\.(?:com|net|org|co\.za|io|site|test)\b")

    def test_every_phpcs_ignore_is_a_nonce_read_with_its_reason(self):
        # The two reads of the query (the ticket is the proof); the direct queries are WordPress-Extra clean and
        # carry their reason as the WORKAROUND line (round 1: the Options API has no compare-and-delete).
        ignores = re.findall(r"phpcs:ignore ([^\n]*)", self.text)
        nonce = "WordPress.Security.NonceVerification.Recommended -- the one-use ticket is the proof"
        self.assertEqual([line.startswith(nonce) for line in ignores], [True, True])
        self.assertIn("WORKAROUND: the Options API (the owning layer) has no compare-and-delete", self.text)

@unittest.skipUnless(PHP, "the behaviour tests run the plugin under PHP, which is not on this machine's PATH")
class BehaviourTest(unittest.TestCase):
    def run_case(self, **case):
        case.setdefault("plugins", [str(PLUGIN)])
        case.setdefault("run_init", True)
        done = subprocess.run([str(PHP), "-d", "display_errors=stderr", str(HARNESS)], input=json.dumps(case),
                              capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW)
        self.assertEqual(done.stderr.strip(), "", "PHP reported an error or warning")
        report = json.loads(done.stdout)
        report["names"] = [call[0] for call in report["calls"]]
        return report

    def ticket(self, **changes):
        return {"hash": HASH, "expires": int(time.time()) + 60, "user": 7, **changes}

    def assert_refused(self, report, why):
        self.assertEqual(report["calls"][-1][0], "wp_die", why)
        self.assertEqual(report["calls"][-1][1][1], 403, why)
        for call in ("wp_set_auth_cookie", "wp_set_current_user", "wp_safe_redirect"):
            self.assertNotIn(call, report["names"], f"{why}: {call} was called")
        self.assertNotIn(["do_action", "wp_login"], [c[:1] + c[1][:1] for c in report["calls"]], why)

    def test_the_handler_is_registered_on_init_at_priority_1(self):
        report = self.run_case(run_init=False)
        self.assertEqual(report["init"], [["conclave_ticket_login_redeem", 1]])
        self.assertEqual(report["names"], ["add_action"])

    def test_a_request_without_the_query_leaves_the_ticket(self):
        report = self.run_case(option=self.ticket(), users=ADMIN)
        self.assertEqual(report["names"], ["add_action"])
        self.assertIn("conclave_login_ticket", report["options"])

    def test_a_valid_ticket_logs_the_user_in_once_and_redirects(self):
        report = self.run_case(query=TOKEN, option=self.ticket(), users=ADMIN)
        self.assertEqual(report["names"], ["add_action", "nocache_headers", "wpdb_get_var", "wpdb_delete",
                                           "wp_cache_delete", "get_userdata", "user_can", "wp_set_current_user", "wp_set_auth_cookie",
                                           "do_action", "wp_safe_redirect"])
        calls = dict((c[0], c[1]) for c in report["calls"])
        self.assertEqual(calls["user_can"], [7, "manage_options"])
        self.assertEqual(calls["wp_set_auth_cookie"], [7, False])
        self.assertEqual(calls["do_action"], ["wp_login", "site-admin", {"object": 7}])
        self.assertEqual(calls["wp_safe_redirect"], ["https://example.com/wp-admin/"])
        self.assertNotIn("conclave_login_ticket", report["options"], "the ticket was not consumed")

    def test_every_refusal_is_the_fixed_403_with_no_login(self):
        expired = self.ticket(expires=int(time.time()) - 1)
        cases = {
            "an expired ticket": dict(query=TOKEN, option=expired),
            "no ticket": dict(query=TOKEN),
            "a wrong token": dict(query="f" * 64, option=self.ticket()),
            "a malformed token": dict(query=TOKEN.upper(), option=self.ticket()),
            "a short token": dict(query=TOKEN[:-1], option=self.ticket()),
            "an array token": dict(query=[TOKEN], option=self.ticket()),
            "a user that does not exist": dict(query=TOKEN, option=self.ticket(user=8)),
            "a user without manage_options": dict(query=TOKEN, option=self.ticket(),
                                                  users={"7": {"login": "editor", "caps": ["read"]}}),
            "a ticket another request removed first": dict(query=TOKEN, option=self.ticket(), gone_before_delete=True),
            "an option that is not an array": dict(query=TOKEN, option=HASH),
            "an option without its user": dict(query=TOKEN, option={"hash": HASH, "expires": int(time.time()) + 60}),
            "a hash that is not a string": dict(query=TOKEN, option=self.ticket(hash=["x"])),
            "an expiry that is not an integer": dict(query=TOKEN, option=self.ticket(expires=str(int(time.time()) + 60))),
            "a user ID that is not an integer": dict(query=TOKEN, option=self.ticket(user="7")),
            "a user ID below 1": dict(query=TOKEN, option=self.ticket(user=0)),
        }
        for why, case in cases.items():
            with self.subTest(case=why):
                report = self.run_case(users=case.pop("users", ADMIN), **case)
                self.assert_refused(report, why)
                self.assertNotIn("conclave_login_ticket", report["options"], f"{why}: the ticket survived")
                messages = {c[1][0] for c in report["calls"] if c[0] == "wp_die"}
                self.assertEqual(messages, {"This login link is not valid. Make a new one with "
                                            "scripts/open-dashboard.py."}, why)

    def test_a_delete_the_database_refuses_logs_nobody_in(self):
        # Completion review: the DELETE itself fails (wpdb returns false) and the ticket stays on the site.
        report = self.run_case(query=TOKEN, option=self.ticket(), delete_fails=True, users=ADMIN)
        self.assert_refused(report, "a delete the database refused")
        left = report["options"].get("conclave_login_ticket")
        self.assertIsNotNone(left, "the ticket did not stay where it was")
        self.assertEqual((left["hash"], left["user"]), (HASH, 7))

    def test_an_old_redemption_never_uses_up_a_newer_ticket(self):
        # Round 1: request X reads ticket A; request Y redeems A; the opener stores B; X's delete must not remove B
        # and log in with A.
        newer = self.ticket(hash=hashlib.sha256(b"b" * 64).hexdigest())
        report = self.run_case(query=TOKEN, option=self.ticket(), replace_before_delete=newer, users=ADMIN)
        self.assert_refused(report, "a redemption of a ticket replaced since it was read")
        self.assertEqual(report["options"].get("conclave_login_ticket"), newer, "the newer ticket was used up")

    def test_a_wrong_token_uses_the_ticket_up(self):
        first = self.run_case(query="f" * 64, option=self.ticket(), users=ADMIN)
        self.assert_refused(first, "a wrong token")
        self.assertNotIn("conclave_login_ticket", first["options"])

    def test_two_copies_load_without_a_fatal_and_register_one_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "another-name.php"
            shutil.copyfile(PLUGIN, copy)
            report = self.run_case(plugins=[str(PLUGIN), str(copy)], run_init=False)
        self.assertEqual(report["init"], [["conclave_ticket_login_redeem", 1]])


@unittest.skipUnless(PHP, "php -l needs PHP, which is not on this machine's PATH")
class LintTest(unittest.TestCase):
    def test_the_plugin_and_the_harness_parse(self):
        for path in (PLUGIN, HARNESS):
            with self.subTest(file=path.name):
                done = subprocess.run([str(PHP), "-l", str(path)], capture_output=True, text=True, timeout=60,
                                      creationflags=NO_WINDOW)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class OpenerAgreementTest(unittest.TestCase):
    """The opener (`scripts/open-dashboard.py`, D07 T02 §2), installer (`scripts/ticket-login.py`, §3) and plugin agree."""

    def test_the_plugin_and_the_opener_name_one_option_and_one_query(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("open_dashboard_agreement", ROOT / "scripts" / "open-dashboard.py")
        assert spec is not None and spec.loader is not None
        opener = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(opener)
        spec_tl = importlib.util.spec_from_file_location("ticket_login_agreement", ROOT / "scripts" / "ticket-login.py")
        assert spec_tl is not None and spec_tl.loader is not None
        installer = importlib.util.module_from_spec(spec_tl)
        spec_tl.loader.exec_module(installer)
        code = code_of(PLUGIN.read_text(encoding="utf-8"))
        defined = dict(re.findall(r"define\(\s*'(CONCLAVE_TICKET_(?:OPTION|QUERY))',\s*'([^']*)'\s*\)", code))
        self.assertEqual(defined, {"CONCLAVE_TICKET_OPTION": opener.OPTION, "CONCLAVE_TICKET_QUERY": opener.QUERY})
        self.assertEqual(installer.OPTION, defined["CONCLAVE_TICKET_OPTION"])


def _find_bash():
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            cand = Path(git).resolve().parents[1] / "bin" / "bash.exe"
            if cand.is_file():
                return str(cand)
        return None
    return shutil.which("bash")


BASH = _find_bash()


def _load_ticket_login():
    spec = importlib.util.spec_from_file_location("ticket_login_mod", ROOT / "scripts" / "ticket-login.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeRemoteSite:
    """Stateful remote SSH/WP-CLI stand-in executing emitted shell against a real temp tree and PHP via CLI/shim."""

    def __init__(self, home: Path, wp_dir: Path, url: str = "https://example.com"):
        self.home = home
        self.wp_dir = wp_dir
        self.url = url
        self.calls: list[tuple[str, list[str], str | None]] = []
        self.options: dict[str, dict[str, object]] = {url: {}}
        self.multisite = False
        self.mu_dir_override: str | None = None
        self.db_error = ""
        self.raw_stderr = "RAW_REMOTE_DIAGNOSTIC_DO_NOT_LEAK"
        self.bootstrap_broken = False
        self.config_constants: list[dict[str, object]] = []
        self.umask: int | None = None
        self.hooks: dict[str, object] = {}

    def _run_php_eval(self, code: str, site_url: str) -> subprocess.CompletedProcess:
        if self.bootstrap_broken:
            return subprocess.CompletedProcess(["wp"], 1, "", "PHP Fatal error: syntax error in mu-plugin\n")
        site_opts = self.options.setdefault(site_url, {})
        abspath = str(self.wp_dir).replace("\\", "/") + "/"
        mu_dir = self.mu_dir_override or (abspath.rstrip("/") + "/wp-content/mu-plugins")
        if PHP:
            state = {
                "options": site_opts,
                "db_error": self.db_error,
                "multisite": self.multisite,
                "abspath": abspath,
                "mu_dir": mu_dir,
            }
            runner = (
                "<?php\n"
                "$state = json_decode(file_get_contents('php://stdin'), true);\n"
                "define('ABSPATH', $state['abspath']);\n"
                "define('WPMU_PLUGIN_DIR', $state['mu_dir']);\n"
                "function is_multisite() { global $state; return (bool)$state['multisite']; }\n"
                "function wp_cache_delete($k, $g = '') {}\n"
                "function delete_option($name) { global $state; unset($state['options'][$name]); return true; }\n"
                "class FakeWpdb {\n"
                "  public $options = 'wp_options';\n"
                "  public $last_error = '';\n"
                "  public function prepare($sql, ...$args) { return array($sql, $args); }\n"
                "  public function get_var($q) {\n"
                "    global $state;\n"
                "    if ($this->last_error !== '') return null;\n"
                "    $name = $q[1][0];\n"
                "    return array_key_exists($name, $state['options']) ? '1' : '0';\n"
                "  }\n"
                "}\n"
                "$wpdb = new FakeWpdb();\n"
                "$wpdb->last_error = $state['db_error'];\n"
                "ob_start();\n"
                "call_user_func(function() use (&$wpdb, &$state) {\n"
                + code + "\n"
                "});\n"
                "$out = ob_get_clean();\n"
                "echo json_encode(array('out' => $out, 'options' => $state['options']));\n"
            )
            with tempfile.NamedTemporaryFile("w", suffix=".php", delete=False, encoding="utf-8") as fh:
                fh.write(runner)
                php_file = fh.name
            try:
                res = subprocess.run([str(PHP), php_file], input=json.dumps(state), capture_output=True, text=True,
                                     timeout=30, creationflags=NO_WINDOW)
            finally:
                Path(php_file).unlink(missing_ok=True)
            if res.returncode != 0:
                return subprocess.CompletedProcess(["wp"], res.returncode, res.stdout, res.stderr)
            payload = json.loads(res.stdout)
            self.options[site_url] = payload["options"]
            return subprocess.CompletedProcess(["wp"], 0, payload["out"], self.raw_stderr)
        # Pure-Python fallback when PHP CLI is not installed (e.g., native Windows).
        if "SELECT COUNT(*)" in code:
            if self.db_error:
                return subprocess.CompletedProcess(["wp"], 0, 'CONCLAVE_WP:{"error":"db"}\n', self.raw_stderr)
            present = "present" if "conclave_login_ticket" in site_opts else "absent"
            mu_match = mu_dir.rstrip("/") == abspath.rstrip("/") + "/wp-content/mu-plugins"
            return subprocess.CompletedProcess(
                ["wp"], 0,
                "CONCLAVE_WP:" + json.dumps({"option": present, "multisite": self.multisite, "mu_match": mu_match}) + "\n",
                self.raw_stderr,
            )
        if "delete_option(" in code:
            if self.db_error:
                return subprocess.CompletedProcess(["wp"], 0, "CONCLAVE_DEL:error\n", self.raw_stderr)
            site_opts.pop("conclave_login_ticket", None)
            return subprocess.CompletedProcess(["wp"], 0, "CONCLAVE_DEL:ok\n", self.raw_stderr)
        return subprocess.CompletedProcess(["wp"], 1, "", "unsupported eval")

    def run(self, kind, arguments=(), *, input=None, timeout=90, pin=None):
        self.calls.append((kind, list(arguments), input))
        assert kind == "ssh", f"expected ssh transport, got {kind!r}"
        cmd = arguments[0]
        if " && wp " in cmd:
            _, _, wp_part = cmd.partition(" && wp ")
            tokens = shlex.split(wp_part)
            assert tokens and tokens[0].startswith("--url="), f"--url must precede WP-CLI subcommand: {tokens}"
            site_url = tokens[0].split("=", 1)[1]
            sub = tokens[1]
            if sub == "eval":
                hook = self.hooks.get("eval")
                if callable(hook):
                    out = hook(tokens, site_url)
                    if out is not None:
                        return out
                return self._run_php_eval(tokens[2], site_url)
            if sub == "config" and tokens[2:4] == ["list", "--format=json"]:
                hook = self.hooks.get("config")
                if callable(hook):
                    return hook(tokens, site_url)
                return subprocess.CompletedProcess(["wp"], 0, json.dumps(self.config_constants), "")
            return subprocess.CompletedProcess(["wp"], 1, "", f"unexpected wp subcommand: {tokens}")

        # Raw SSH shell command: run hooks, then execute emitted POSIX shell against real temp tree via bash.
        if "echo STAGED" in cmd:
            hook = self.hooks.get("stage")
            if callable(hook):
                out = hook(cmd, input)
                if out is not None:
                    return out
        elif "echo PUBLISHED" in cmd:
            hook = self.hooks.get("publish")
            if callable(hook):
                out = hook(cmd)
                if out is not None:
                    return out
        elif "echo DELETED" in cmd:
            hook = self.hooks.get("delete_file")
            if callable(hook):
                out = hook(cmd)
                if out is not None:
                    return out
        elif "SHA256:" in cmd:
            hook = self.hooks.get("probe_file")
            if callable(hook):
                out = hook(cmd)
                if out is not None:
                    return out

        assert BASH is not None, "bash is required to execute emitted SSH shell commands"
        env = {**os.environ, "HOME": self.home.as_posix()}
        script = cmd
        if self.umask is not None:
            script = f"umask {self.umask:04o}\n" + script
        if os.name == "nt":
            # Convert Windows drive paths in cd <abs> for Git Bash.
            def _to_posix(m):
                p = m.group(1)
                if len(p) >= 2 and p[1] == ":":
                    return f"cd /{p[0].lower()}{p[2:].replace(chr(92), '/')}"
                return m.group(0)
            script = re.sub(r"^cd ([A-Za-z]:[^\s&|;]+)", _to_posix, script, flags=re.M)
        res = subprocess.run([BASH, "-c", script], input=input, capture_output=True, text=True,
                             cwd=self.home, env=env, timeout=30, creationflags=NO_WINDOW)
        if "echo DELETED" in cmd and res.returncode == 0:
            self.bootstrap_broken = False
        return subprocess.CompletedProcess(["ssh"], res.returncode, res.stdout, res.stderr + self.raw_stderr)


@unittest.skipUnless(BASH, "bash is required to execute the emitted SSH shell commands")
class PluginOnSiteTest(unittest.TestCase):
    """Stateful command-boundary tests for `scripts/ticket-login.py` (D07 T02 section 3)."""

    def setUp(self):
        self.mod = _load_ticket_login()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()
        self.wp_dir = self.home / "htdocs"
        self.wp_dir.mkdir()
        self.site = _FakeRemoteSite(self.home, self.wp_dir)
        self.pin = {
            "host": "pressable",
            "site_id": 12345,
            "url": "https://example.com",
            "environment": "staging",
            "ssh": {
                "item": "abcdefghijklmnopqrstuvwxyz",
                "ssh_host": "ssh.example.com",
                "sftp_host": "sftp.example.com",
                "port": "22",
                "username": "wpuser",
                "wp_path": "~/htdocs",
            },
            "mcp": {},
        }

    def run_cli(self, argv, *, pin=None, native_win=False, local_plugin=None):
        out, err = io.StringIO(), io.StringIO()
        active_pin = self.pin if pin is None else pin
        vault_calls = []

        def fake_vault(*a, **kw):
            vault_calls.append((a, kw))
            raise AssertionError("vault_fields must not be called")

        def fake_load(*_a, **_kw):
            if isinstance(active_pin, BaseException):
                raise active_pin
            return active_pin

        patches = [
            mock.patch.object(self.mod, "native_windows", return_value=native_win),
            mock.patch.object(self.mod.wp_site, "load", side_effect=fake_load),
            mock.patch.object(self.mod.wp_site, "vault_fields", side_effect=fake_vault),
            mock.patch.object(self.mod.site_ssh, "run", side_effect=self.site.run),
        ]
        if local_plugin is not None:
            patches.append(mock.patch.object(self.mod, "LOCAL_PLUGIN", local_plugin))
        with patches[0], patches[1], patches[2], patches[3]:
            if local_plugin is not None:
                with patches[4]:
                    code = self.mod.main(argv, out=out, err=err)
            else:
                code = self.mod.main(argv, out=out, err=err)
        return code, out.getvalue(), err.getvalue(), vault_calls

    def test_plugin_on_site_usage_cwd_and_refusal_guards(self):
        # No command -> usage and exit 2, zero remote calls.
        code, _out, err, vault = self.run_cli([])
        self.assertEqual((code, self.site.calls, vault), (2, [], []))
        self.assertIn("usage:", err.lower())
        # Native Windows -> exit 2, zero vault/remote calls.
        code, _out, err, vault = self.run_cli(["status"], native_win=True)
        self.assertEqual((code, self.site.calls, vault), (2, [], []))
        self.assertIn("WSL", err)
        # Unreadable/invalid/no-SSH/incomplete pins -> exit 2, zero vault/remote calls.
        bad_pins = [
            ("unreadable", OSError("missing")),
            ("invalid", ValueError("bad json")),
            ("no-ssh", {**self.pin, "ssh": {**self.pin["ssh"], "ssh_host": None}}),
            ("no-wp-path", {**self.pin, "ssh": {**self.pin["ssh"], "wp_path": None}}),
            ("no-url", {**self.pin, "url": None}),
            ("no-ssh-item", {**self.pin, "ssh": {**self.pin["ssh"], "item": None}}),
        ]
        for label, bad in bad_pins:
            with self.subTest(case=label):
                code, _out, err, vault = self.run_cli(["status"], pin=bad)
                self.assertEqual((code, self.site.calls, vault), (2, [], []), label)
                if label in ("no-ssh", "no-wp-path"):
                    self.assertIn("SSH", err)
        # Both mutators without --yes -> exit 2, print site URL and intended change, zero vault/remote calls.
        for cmd in ("install", "remove"):
            with self.subTest(mutator=cmd):
                code, _out, err, vault = self.run_cli([cmd])
                self.assertEqual((code, self.site.calls, vault), (2, [], []))
                self.assertIn("https://example.com", err)
                self.assertIn("--yes", err)
        # Valid SSH pin with NO dashboard user (mcp: {}) works even from another working directory.
        old_cwd = os.getcwd()
        try:
            os.chdir(self._tmp.name)
            code, out, _err, _vault = self.run_cli(["status"])
        finally:
            os.chdir(old_cwd)
        self.assertEqual(code, 0)
        self.assertIn("plugin: absent", out)
        self.assertIn("option: absent", out)

    def test_plugin_on_site_status_states_secrets_and_errors(self):
        mu = self.wp_dir / "wp-content" / "mu-plugins"
        mu.mkdir(parents=True)
        target = mu / "conclave-ticket-login.php"
        secret = "SECRET_TICKET_HASH_DO_NOT_LEAK_999"
        # All 6 (absent|current|differs) x (present|absent), including falsey option value "".
        for pstate in ("absent", "current", "differs"):
            if pstate == "absent":
                target.unlink(missing_ok=True)
            elif pstate == "current":
                target.write_bytes(PLUGIN.read_bytes())
            else:
                target.write_bytes(b"<?php // different\n")
            for ostate, val in (("absent", None), ("present", ""), ("present", secret)):
                with self.subTest(plugin=pstate, option=ostate, val=val):
                    self.site.options[self.pin["url"]] = {} if val is None else {"conclave_login_ticket": val}
                    code, out, err, _ = self.run_cli(["status"])
                    self.assertEqual(code, 0, err)
                    self.assertIn(f"plugin: {pstate}", out)
                    self.assertIn(f"option: {ostate}", out)
                    self.assertNotIn(secret, out + err)
                    self.assertNotIn(self.site.raw_stderr, out + err)
        # DB error with WP-CLI exit 0 -> exit 1, never prints absent/current.
        self.site.db_error = "Lost connection to MySQL"
        code, out, err, _ = self.run_cli(["status"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("Lost connection", err)
        self.site.db_error = ""
        # Directory at target filename -> exit 1 (not absent).
        target.unlink(missing_ok=True)
        target.mkdir()
        code, out, _err, _ = self.run_cli(["status"])
        self.assertEqual((code, out), (1, ""))
        target.rmdir()
        # Dangling symlink at target filename -> exit 1 (not absent).
        if os.name != "nt":
            target.symlink_to(mu / "nowhere.php")
            try:
                code, out, _err, _ = self.run_cli(["status"])
                self.assertEqual((code, out), (1, ""))
            finally:
                target.unlink(missing_ok=True)
        # Missing local plugin copy -> exit 1.
        code, out, _err, _ = self.run_cli(["status"], local_plugin=self.home / "missing.php")
        self.assertEqual((code, out), (1, ""))
        # Malformed WP-CLI reply -> exit 1.
        self.site.hooks["eval"] = lambda *_: subprocess.CompletedProcess(["wp"], 0, "garbage\n", "")
        code, out, _err, _ = self.run_cli(["status"])
        self.assertEqual((code, out), (1, ""))
        self.site.hooks.clear()

    def test_plugin_on_site_install_staged_paths_umask_crlf_and_recovery(self):
        # Test all three wp_path forms: ~/htdocs, htdocs, and absolute path.
        abs_wp = self.wp_dir.as_posix()
        for wp_path in ("~/htdocs", "htdocs", abs_wp):
            with self.subTest(wp_path=wp_path):
                mu = self.wp_dir / "wp-content" / "mu-plugins"
                if mu.exists():
                    shutil.rmtree(mu)
                pin = {**self.pin, "ssh": {**self.pin["ssh"], "wp_path": wp_path}}
                self.site.umask = 0o077
                self.site.options[self.pin["url"]] = {"conclave_login_ticket": "keep-ambient"}
                code, out, err, _ = self.run_cli(["install", "--yes"], pin=pin)
                self.assertEqual(code, 0, err)
                self.assertIn("plugin: current", out)
                installed = mu / "conclave-ticket-login.php"
                self.assertEqual(installed.read_bytes(), PLUGIN.read_bytes())
                self.assertEqual(self.site.options[self.pin["url"]].get("conclave_login_ticket"), "keep-ambient")
                if os.name != "nt":
                    self.assertEqual(mu.stat().st_mode & 0o777, 0o755)
                    self.assertEqual(installed.stat().st_mode & 0o777, 0o644)
        self.site.umask = None
        # CRLF byte-for-byte preservation through base64 stdin.
        crlf_copy = self.home / "crlf-plugin.php"
        crlf_bytes = PLUGIN.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        crlf_copy.write_bytes(crlf_bytes)
        code, _out, err, _ = self.run_cli(["install", "--yes"], local_plugin=crlf_copy)
        self.assertEqual(code, 0, err)
        self.assertEqual((self.wp_dir / "wp-content/mu-plugins/conclave-ticket-login.php").read_bytes(), crlf_bytes)
        # Pre-publication hash mismatch leaves existing working plugin untouched and removes staging temp.
        installed = self.wp_dir / "wp-content/mu-plugins/conclave-ticket-login.php"
        installed.write_bytes(b"<?php // working\n")
        self.site.hooks["probe_file"] = lambda cmd: (
            subprocess.CompletedProcess(["ssh"], 0, "SHA256:" + "0" * 64 + "\n", "")
            if ".tmp" in cmd else None
        )
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.site.hooks.clear()
        self.assertEqual(code, 1)
        self.assertIn("untouched", err)
        self.assertEqual(installed.read_bytes(), b"<?php // working\n")
        self.assertEqual(list((self.wp_dir / "wp-content/mu-plugins").glob("*.tmp")), [])
        # Directory at target filename stays empty and exits 1.
        installed.unlink()
        installed.mkdir()
        code, _out, _err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 1)
        self.assertEqual(list(installed.iterdir()), [])
        self.assertEqual(list((self.wp_dir / "wp-content/mu-plugins").glob("*.tmp")), [])
        installed.rmdir()
        # Multisite refusal leaves shared file and both options intact.
        self.site.multisite = True
        self.site.options["https://sub.example.com"] = {"conclave_login_ticket": "sub-ticket"}
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 1)
        self.assertIn("multisite", err.lower())
        self.assertFalse(installed.exists())
        self.assertIn("conclave_login_ticket", self.site.options["https://sub.example.com"])
        self.site.multisite = False
        # Relocated WPMU_PLUGIN_DIR refusal.
        self.site.mu_dir_override = "/custom/mu-plugins"
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 1)
        self.assertIn("WPMU_PLUGIN_DIR", err)
        self.site.mu_dir_override = None
        # Broken MU-plugin stopping WordPress bootstrap: fallback to wp config list recovers install.
        installed.write_bytes(b"<?php syntax error !!!")
        self.site.bootstrap_broken = True
        self.site.config_constants = [{"name": "DB_NAME", "value": "wp", "type": "constant"}]
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 0, err)
        self.assertEqual(installed.read_bytes(), PLUGIN.read_bytes())
        self.site.bootstrap_broken = False
        # Lost reply at publication -> exit 1, advises status; KeyboardInterrupt before/at/after publication -> exit 130.
        self.site.hooks["stage"] = lambda _cmd, _inp: (_ for _ in ()).throw(KeyboardInterrupt())
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 130)
        self.assertIn("status", err)
        self.site.hooks.clear()
        self.site.hooks["publish"] = lambda _cmd: (_ for _ in ()).throw(RuntimeError("lost ssh"))
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 1)
        self.assertIn("status", err)
        self.site.hooks["publish"] = lambda _cmd: (_ for _ in ()).throw(KeyboardInterrupt())
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 130)
        self.assertIn("status", err)
        self.site.hooks.clear()
        self.site.hooks["probe_file"] = lambda cmd: (_ for _ in ()).throw(KeyboardInterrupt()) if ".tmp" not in cmd else None
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.site.hooks.clear()
        self.assertEqual(code, 130)
        self.assertIn("status", err)
        code, _out, err, _ = self.run_cli(["install", "--yes"])
        self.assertEqual(code, 0, err)
        # Directory permission error stops installation (Linux/WSL).
        if os.name != "nt":
            wp_content = self.wp_dir / "wp-content"
            shutil.rmtree(wp_content / "mu-plugins")
            wp_content.chmod(0o555)
            try:
                code, _out, _err, _ = self.run_cli(["install", "--yes"])
                self.assertEqual(code, 1)
            finally:
                wp_content.chmod(0o755)

    def test_plugin_on_site_remove_partial_states_recovery_and_interrupt(self):
        mu = self.wp_dir / "wp-content" / "mu-plugins"
        mu.mkdir(parents=True)
        target = mu / "conclave-ticket-login.php"
        # All 4 partial states + missing local PHP source.
        for has_file, has_opt in ((True, True), (True, False), (False, True), (False, False)):
            with self.subTest(has_file=has_file, has_opt=has_opt):
                if has_file:
                    target.write_bytes(PLUGIN.read_bytes())
                else:
                    target.unlink(missing_ok=True)
                self.site.options[self.pin["url"]] = {"conclave_login_ticket": "tok"} if has_opt else {}
                code, out, err, _ = self.run_cli(["remove", "--yes"], local_plugin=self.home / "absent.php")
                self.assertEqual(code, 0, err)
                self.assertIn("plugin: absent", out)
                self.assertIn("option: absent", out)
                self.assertFalse(target.exists())
                self.assertNotIn("conclave_login_ticket", self.site.options[self.pin["url"]])
        # Multisite refusal leaves shared file and both options intact.
        target.write_bytes(PLUGIN.read_bytes())
        self.site.multisite = True
        self.site.options[self.pin["url"]] = {"conclave_login_ticket": "main"}
        self.site.options["https://sub.example.com"] = {"conclave_login_ticket": "sub"}
        code, _out, _err, _ = self.run_cli(["remove", "--yes"])
        self.assertEqual(code, 1)
        self.assertTrue(target.exists())
        self.assertIn("conclave_login_ticket", self.site.options[self.pin["url"]])
        self.assertIn("conclave_login_ticket", self.site.options["https://sub.example.com"])
        self.site.multisite = False
        # Relocated WPMU_PLUGIN_DIR refusal leaves file intact.
        self.site.mu_dir_override = "/custom/mu-plugins"
        code, _out, err, _ = self.run_cli(["remove", "--yes"])
        self.assertEqual(code, 1)
        self.assertIn("WPMU_PLUGIN_DIR", err)
        self.assertTrue(target.exists())
        self.site.mu_dir_override = None
        # Operational failure between deletions followed by retry remove --yes succeeds.
        self.site.options[self.pin["url"]] = {"conclave_login_ticket": "retry-opt"}
        self.site.hooks["eval"] = lambda tokens, _u: (
            subprocess.CompletedProcess(["wp"], 1, "", "db down") if "delete_option(" in tokens[2] else None
        )
        code, _out, _err, _ = self.run_cli(["remove", "--yes"])
        self.site.hooks.clear()
        self.assertEqual(code, 1)
        self.assertFalse(target.exists())
        self.assertIn("conclave_login_ticket", self.site.options[self.pin["url"]])
        code, _out, err, _ = self.run_cli(["remove", "--yes"])
        self.assertEqual(code, 0, err)
        self.assertNotIn("conclave_login_ticket", self.site.options[self.pin["url"]])
        # Broken MU-plugin stopping WordPress bootstrap: fallback recovers remove --yes.
        target.write_bytes(b"<?php broken")
        self.site.bootstrap_broken = True
        self.site.config_constants = [{"name": "DB_NAME", "value": "wp", "type": "constant"}]
        code, _out, err, _ = self.run_cli(["remove", "--yes"])
        self.assertEqual(code, 0, err)
        self.assertFalse(target.exists())
        self.assertNotIn("conclave_login_ticket", self.site.options[self.pin["url"]])
        # KeyboardInterrupt after file delete before option delete -> exit 130, then retry remove --yes succeeds.
        target.write_bytes(PLUGIN.read_bytes())
        self.site.options[self.pin["url"]] = {"conclave_login_ticket": "t"}
        def interrupt_delete(tokens, _url):
            if "delete_option(" in tokens[2]:
                raise KeyboardInterrupt()
            return None
        self.site.hooks["eval"] = interrupt_delete
        code, _out, _err, _ = self.run_cli(["remove", "--yes"])
        self.site.hooks.clear()
        self.assertEqual(code, 130)
        self.assertFalse(target.exists())
        self.assertIn("conclave_login_ticket", self.site.options[self.pin["url"]])
        code, _out, err, _ = self.run_cli(["remove", "--yes"])
        self.assertEqual(code, 0, err)
        self.assertNotIn("conclave_login_ticket", self.site.options[self.pin["url"]])
        # Read-back seeing option still present -> exit 1.
        self.site.options[self.pin["url"]] = {"conclave_login_ticket": "stuck"}
        self.site.hooks["eval"] = lambda tokens, _u: (
            subprocess.CompletedProcess(["wp"], 0, "CONCLAVE_DEL:ok\n", "") if "delete_option(" in tokens[2] else None
        )
        code, _out, _err, _ = self.run_cli(["remove", "--yes"])
        self.site.hooks.clear()
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
