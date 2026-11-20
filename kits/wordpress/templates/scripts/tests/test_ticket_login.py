"""The one-use ticket login plugin, `tools/ticket-login/conclave-ticket-login.php` (D07 T02 section 1).

Two kinds of test. The text tests read the plugin and hold the properties its safety rests on, each proven able to
fail on a copy with that one property changed. The behaviour tests run the plugin under the PHP CLI against
`ticket_login_harness.php`, a stand-in for the WordPress functions it calls, and skip, naming PHP, where there is no
PHP. Nothing here reaches a site.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

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
    """The opener (`scripts/open-dashboard.py`, D07 T02 section 2) and the plugin name the same option and query."""

    def test_the_plugin_and_the_opener_name_one_option_and_one_query(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("open_dashboard_agreement", ROOT / "scripts" / "open-dashboard.py")
        assert spec is not None and spec.loader is not None
        opener = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(opener)
        code = code_of(PLUGIN.read_text(encoding="utf-8"))
        defined = dict(re.findall(r"define\(\s*'(CONCLAVE_TICKET_(?:OPTION|QUERY))',\s*'([^']*)'\s*\)", code))
        self.assertEqual(defined, {"CONCLAVE_TICKET_OPTION": opener.OPTION, "CONCLAVE_TICKET_QUERY": opener.QUERY})


if __name__ == "__main__":
    unittest.main()
