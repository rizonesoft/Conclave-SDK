"""The MCP header helper and the Pressable setup helpers refuse anything not pinned. No network, no vault."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS / "lib"))
# In the Conclave-SDK checkout the shared helpers live in the kit's common templates, not next to these files.
if not (SCRIPTS / "lib/wp_site.py").is_file():
    sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "templates/scripts/lib"))
import wp_site  # noqa: E402
import mcp_http  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


headers = load("mcp_headers_under_test", SCRIPTS / "mcp-headers.py")
sftp_item = load("sftp_item_under_test", SCRIPTS / "sftp-item.py")

WP_ITEM = "abcdefghijklmnopqrstuvwxyz"
TOKEN_ITEM = "zyxwvutsrqponmlkjihgfedcba"
UUID = "62a010d2-6cf8-4200-abb0-d80117954d9c"


def pin(uuid=UUID):
    return wp_site.validate({
        "host": "pressable", "site_id": 1813618, "url": "https://example.com", "environment": "production",
        "ssh": {"item": None, "ssh_host": "ssh.pressable.com", "sftp_host": "sftp.pressable.com", "port": "22",
                "username": None, "wp_path": "~/htdocs"},
        "pressable": {"account_id": 1432766},
        "mcp": {
            "example-wordpress": {"item": WP_ITEM, "scheme": "basic", "url": "https://example.com/wp-json/mcp/mcp-adapter-default-server",
                                  "username": "example", "wordpress_user_id": 1, "application_password_uuid": uuid},
            "example-pressable": {"item": TOKEN_ITEM, "scheme": "bearer", "url": "https://mcp.pressable.com"},
        },
    })


def vault_item(item_id, **fields):
    return json.dumps({"id": item_id, "fields": [{"id": key, "label": key, "value": value} for key, value in fields.items()]})


def wordpress_fields(**overrides):
    return {"site_id": "1813618", "site_url": "https://example.com", "environment": "production", "username": "example",
            "endpoint": "https://example.com/wp-json/mcp/mcp-adapter-default-server", "wordpress_user_id": "1",
            "application_password_uuid": UUID, "password": "abcd efgh ijkl mnop qrst uvwx", **overrides}


class HeaderHelper(unittest.TestCase):
    def headers_for(self, connection, stdout, site=None):
        with patch.object(wp_site.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout, "")) as run:
            result = headers.headers(connection, site or pin())
        return result, run

    def test_the_pinned_wordpress_item_produces_basic_auth(self):
        result, run = self.headers_for("example-wordpress", vault_item(WP_ITEM, **wordpress_fields()))
        self.assertIn(WP_ITEM, run.call_args[0][0])
        decoded = base64.b64decode(result["Authorization"].split(" ", 1)[1]).decode()
        self.assertEqual(decoded, "example:abcd efgh ijkl mnop qrst uvwx")

    def test_every_pinned_field_is_enforced(self):
        for key in wordpress_fields():
            if key == "password":
                continue
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.headers_for("example-wordpress", vault_item(WP_ITEM, **wordpress_fields(**{key: "other"})))

    def test_a_missing_pinned_field_is_refused(self):
        fields = wordpress_fields()
        del fields["application_password_uuid"]
        with self.assertRaises(ValueError):
            self.headers_for("example-wordpress", vault_item(WP_ITEM, **fields))

    def test_a_swapped_item_is_refused(self):
        with self.assertRaises(ValueError):
            self.headers_for("example-wordpress", vault_item(TOKEN_ITEM, **wordpress_fields()))

    def test_an_unset_application_password_is_refused_before_the_vault(self):
        with patch.object(wp_site.subprocess, "run") as run, self.assertRaises(ValueError):
            headers.headers("example-wordpress", pin(uuid=None))
        run.assert_not_called()

    def test_the_bearer_connection_uses_its_own_item(self):
        result, run = self.headers_for("example-pressable", vault_item(TOKEN_ITEM, password="token-value"))
        self.assertIn(TOKEN_ITEM, run.call_args[0][0])
        self.assertEqual(result, {"Authorization": "Bearer token-value"})

    def test_an_unknown_connection_is_refused(self):
        with patch.object(wp_site.subprocess, "run") as run, self.assertRaises(ValueError):
            headers.headers("other-wordpress", pin())
        run.assert_not_called()

    def test_the_cli_never_prints_a_credential_on_failure(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "mcp-headers.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")


class SetupHelpers(unittest.TestCase):
    def test_the_reset_password_is_the_one_password_string(self):
        self.assertEqual(sftp_item.reset_password({"data": {"new_password": "p4ss"}}), "p4ss")
        self.assertEqual(sftp_item.reset_password({"a": {"password": "x"}, "b": [{"password": "y"}]}), "")
        self.assertEqual(sftp_item.reset_password({"message": "ok"}), "")

    def test_exactly_one_owner_account_is_required(self):
        self.assertEqual(sftp_item.owner_username({"ftp_accounts": [{"username": "a", "owner": True}, {"username": "b"}]}), "a")
        for accounts in ({"ftp_accounts": []}, {"ftp_accounts": [{"username": "a"}, {"username": "b"}]}):
            with self.subTest(accounts=accounts), self.assertRaises(SystemExit):
                sftp_item.owner_username(accounts)

    def test_connection_for_finds_the_one_pressable_bearer(self):
        self.assertEqual(mcp_http.connection_for(pin(), "bearer", "https://mcp.pressable.com"), "example-pressable")
        with self.assertRaises(ValueError):
            mcp_http.connection_for(pin(), "bearer", "https://elsewhere.example.com")


if __name__ == "__main__":
    unittest.main()
