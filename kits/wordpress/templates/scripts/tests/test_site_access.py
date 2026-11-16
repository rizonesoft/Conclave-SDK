"""The site pin and the pinned SSH helper refuse anything that is not this project's site. No network, no vault."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import site_ssh  # noqa: E402
import wp_site  # noqa: E402

ITEM = "abcdefghijklmnopqrstuvwxyz"


def pin(**overrides):
    base = {
        "host": "wpcom",
        "site_id": 257780254,
        "url": "https://example.wpcomstaging.com",
        "environment": "production",
        "ssh": {"item": ITEM, "ssh_host": "ssh.wp.com", "sftp_host": "sftp.wp.com", "port": "22",
                "username": "example.wordpress.com", "wp_path": "/srv/htdocs"},
    }
    for key, value in overrides.items():
        if key in base["ssh"]:
            base["ssh"][key] = value
        else:
            base[key] = value
    return wp_site.validate(base)


def vault_item(item_id=ITEM, **fields):
    return json.dumps({"id": item_id, "fields": [{"id": key, "label": key, "value": value} for key, value in fields.items()]})


def good_fields(**overrides):
    return {"hostname": "sftp.wp.com", "ssh_hostname": "ssh.wp.com", "port": "22", "username": "example.wordpress.com", "site_id": "257780254",
            "site_url": "https://example.wpcomstaging.com", "environment": "production", "password": "s3cret-pass", **overrides}


class Pin(unittest.TestCase):
    def test_the_kit_templates_are_valid_pins(self):
        kit = Path(__file__).resolve().parents[3]
        templates = sorted(kit.glob("hosts/*/templates/.conclave/wordpress-site.json"))
        if not templates:
            self.skipTest("run from the Conclave-SDK kit")
        for path in templates:
            with self.subTest(path=str(path)):
                loaded = wp_site.load(path)
                self.assertIn("site_id", wp_site.unset(loaded, "site_id", "url"))

    def test_load_reads_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pin.json"
            path.write_text(json.dumps({"_about": "x", "host": "pressable", "site_id": None, "url": None,
                                        "environment": "production", "ssh": {}, "mcp": {}}))
            self.assertEqual(wp_site.load(path)["host"], "pressable")

    def test_bad_values_are_refused(self):
        cases = {
            "host": "kinsta", "environment": "dev", "url": "http://example.com", "site_id": "257780254",
            "wp_path": "/srv/htdocs; rm -rf ~", "ssh_host": "ssh.wp.com -oProxyCommand=x", "username": "a b",
            "item": "not-an-item", "port": "22x",
        }
        for key, bad in cases.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                pin(**{key: bad})

    def test_url_with_trailing_slash_is_refused(self):
        with self.assertRaises(ValueError):
            pin(url="https://example.com/")

    def test_unknown_keys_are_refused(self):
        with self.assertRaises(ValueError):
            wp_site.validate({**pin(), "sitee_id": 1})

    def test_a_bearer_token_only_goes_to_pressable(self):
        base = {"host": "pressable", "site_id": 1, "url": "https://example.com", "environment": "production", "ssh": {}}
        good = {"x-pressable": {"item": ITEM, "scheme": "bearer", "url": "https://mcp.pressable.com"}}
        self.assertEqual(wp_site.validate({**base, "mcp": good})["host"], "pressable")
        with self.assertRaises(ValueError):
            wp_site.validate({**base, "mcp": {"x-pressable": {**good["x-pressable"], "url": "https://evil.example.com"}}})

    def test_values_must_match_whole(self):
        # A trailing newline would pass a `$`-anchored match and reach a remote command line.
        for key, bad in (("url", "https://example.wpcomstaging.com\n"), ("wp_path", "/srv/htdocs\n"), ("item", ITEM + "\n"),
                         ("username", "example.wordpress.com\n"), ("ssh_host", "ssh.wp.com\n")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                pin(**{key: bad})

    def test_a_simple_site_has_no_ssh(self):
        self.assertFalse(wp_site.ssh_enabled(pin(ssh_host=None)))
        self.assertTrue(wp_site.ssh_enabled(pin()))

    def test_a_wordpress_com_pin_takes_only_its_own_sites_wordpress_mcp(self):
        # The site's own MCP Adapter or Elementor MCP may sit beside the WordPress.com connector; the account-wide
        # Pressable token still has no place on a WordPress.com pin.
        own = {"item": ITEM, "scheme": "basic", "url": "https://example.wpcomstaging.com/wp-json/elementor/mcp",
               "username": "example", "wordpress_user_id": 1, "application_password_uuid": None}
        self.assertEqual(pin(mcp={"x-elementor": own})["mcp"]["x-elementor"]["url"], own["url"])
        for bad in ({"item": ITEM, "scheme": "bearer", "url": "https://mcp.pressable.com"},
                    {**own, "url": "https://elsewhere.example.com/wp-json/elementor/mcp"},
                    {**own, "url": "https://example.wpcomstaging.com.evil.example.com/wp-json/mcp"},
                    {**own, "url": "https://example.wpcomstaging.com/wp-admin/mcp"},
                    {**own, "url": "https://example.wpcomstaging.com/wp-json/../wp-admin"},
                    {**own, "url": "https://example.wpcomstaging.com/wp-json/elementor/mcp\n"}):
            with self.subTest(entry=bad), self.assertRaises(ValueError):
                pin(mcp={"x-wordpress": bad})

    def test_require_names_every_unset_value(self):
        with self.assertRaises(ValueError) as caught:
            wp_site.require(pin(item=None, username=None), "ssh.item", "ssh.username", "url")
        self.assertIn("ssh.item, ssh.username", str(caught.exception))

    def test_secret_refuses_line_breaks(self):
        for bad in ("", "   ", "a\nb", "a\rb", "a\0b", "x" * 1025):
            with self.subTest(bad=bad[:8]), self.assertRaises(ValueError):
                wp_site.secret({"password": bad})


class VaultSettings(unittest.TestCase):
    """Which vault and which tool reads it are the owner's settings, never a path written into the kit."""

    def test_the_vault_and_its_tool_come_from_local_toml_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "local.toml"
            self.assertEqual(wp_site.vault_settings(local), ("conclave-op", "Conclave"), "no settings file")
            local.write_text('[paths]\nscratch = "x"\n', encoding="utf-8")
            self.assertEqual(wp_site.vault_settings(local), ("conclave-op", "Conclave"), "no [vault] table")
            local.write_text('[vault]\ncli = "/opt/tools/op"\nname = "Team"\n', encoding="utf-8")
            self.assertEqual(wp_site.vault_settings(local), ("/opt/tools/op", "Team"))
            for bad in ('[vault]\ncli = ""\n', "[vault]\nname = 7\n", "vault = 1\n", "[vault\n"):
                local.write_text(bad, encoding="utf-8")
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    wp_site.vault_settings(local)

    def test_no_script_names_a_home_folder(self):
        scripts = Path(wp_site.__file__).resolve().parents[1]
        for source in sorted(scripts.rglob("*.py")):
            if source.parent.name != "tests":
                self.assertNotRegex(source.read_text(encoding="utf-8"), r"/home/\w|[A-Za-z]:\\\\?Users", source.name)

    def test_the_vault_read_runs_the_configured_tool(self):
        stdout = json.dumps({"id": ITEM, "fields": []})
        with patch.object(wp_site, "OP", "/opt/tools/op"), patch.object(wp_site, "VAULT", "Team"), \
                patch.object(wp_site.subprocess, "run",
                             return_value=subprocess.CompletedProcess([], 0, stdout, "")) as run:
            wp_site.vault_fields(ITEM)
        self.assertEqual(run.call_args[0][0][:1] + run.call_args[0][0][4:6], ["/opt/tools/op", "--vault", "Team"])


class Identity(unittest.TestCase):
    def connect(self, stdout, site=None):
        with patch.object(wp_site.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout, "")) as run:
            fields = site_ssh.connection(site or pin())
        self.assertIn(ITEM, run.call_args[0][0])
        return fields

    def test_the_pinned_item_connects(self):
        fields = self.connect(vault_item(**good_fields()))
        self.assertEqual(fields["ssh_host"], "ssh.wp.com")

    def test_every_pinned_field_is_enforced(self):
        for key in ("hostname", "ssh_hostname", "port", "username", "site_id", "site_url", "environment"):
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.connect(vault_item(**good_fields(**{key: "other"})))

    def test_a_missing_pinned_field_is_refused(self):
        for key in ("site_url", "ssh_hostname"):
            fields = good_fields()
            del fields[key]
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.connect(vault_item(**fields))

    def test_an_edited_ssh_host_in_the_pin_is_refused(self):
        # The vault item still names ssh.wp.com, so a pin pointing elsewhere never gets the password.
        with self.assertRaises(ValueError):
            self.connect(vault_item(**good_fields()), pin(ssh_host="ssh.attacker.example"))

    def test_a_pressable_pin_connects_to_pressable_hosts(self):
        site = pin(host="pressable", ssh_host="ssh.pressable.com", sftp_host="sftp.pressable.com", username="h91ada5f30fd618e4",
                   wp_path="~/htdocs", url="https://example.com")
        fields = self.connect(vault_item(**good_fields(
            hostname="sftp.pressable.com", ssh_hostname="ssh.pressable.com", username="h91ada5f30fd618e4",
            site_url="https://example.com")), site)
        self.assertIn("h91ada5f30fd618e4@ssh.pressable.com", site_ssh.command("ssh", ["true"], fields))
        self.assertEqual(site_ssh.wp_command(["core", "version"], site), "cd ~/htdocs && wp core version")

    def test_a_swapped_item_is_refused(self):
        with self.assertRaises(ValueError):
            self.connect(vault_item(item_id="zyxwvutsrqponmlkjihgfedcba", **good_fields()))

    def test_an_unset_ssh_item_is_refused_before_the_vault(self):
        with patch.object(wp_site.subprocess, "run") as run, self.assertRaises(ValueError):
            site_ssh.connection(pin(item=None))
        run.assert_not_called()


class Commands(unittest.TestCase):
    fields = {**good_fields(), "ssh_host": "ssh.wp.com"}

    def test_ssh_and_sftp_use_only_the_pinned_hosts(self):
        ssh = site_ssh.command("ssh", ["wp core version"], self.fields)
        self.assertIn("example.wordpress.com@ssh.wp.com", ssh)
        sftp = site_ssh.command("sftp", [], self.fields)
        self.assertEqual(sftp[-1], "example.wordpress.com@sftp.wp.com")
        self.assertNotIn("s3cret-pass", " ".join(ssh + sftp))

    def test_sftp_refuses_arguments(self):
        with self.assertRaises(ValueError):
            site_ssh.command("sftp", ["get x"], self.fields)

    def test_rsync_remote_paths_need_the_remote_prefix(self):
        argv = site_ssh.command("rsync", ["-a", "remote:wp-content/uploads/", "local/"], self.fields)
        self.assertIn("example.wordpress.com@ssh.wp.com:wp-content/uploads/", argv)
        with self.assertRaises(ValueError):
            site_ssh.command("rsync", ["-a", "attacker@evil.example:/", "local/"], self.fields)

    def test_unknown_transport_is_refused(self):
        with self.assertRaises(ValueError):
            site_ssh.run("scp", pin=pin())

    def test_wp_runs_in_the_pinned_root_with_quoted_arguments(self):
        line = site_ssh.wp_command(["option", "get", "home; reboot"], pin())
        self.assertEqual(line, "cd /srv/htdocs && wp option get 'home; reboot'")

    def test_home_paths_map_to_the_server_home(self):
        self.assertEqual(site_ssh.remote_arg("~/backups/x.sql"), '"$HOME"/backups/x.sql')
        self.assertEqual(site_ssh.remote_arg(site_ssh.LOCAL_HOME + "b.sql"), '"$HOME"/b.sql')
        self.assertEqual(site_ssh.remote_arg("--file=~/b.sql"), "--file=\"$HOME\"/b.sql")

    def test_wp_needs_a_pinned_root(self):
        with self.assertRaises(ValueError):
            site_ssh.wp_command(["core", "version"], pin(wp_path=None))


if __name__ == "__main__":
    unittest.main()
