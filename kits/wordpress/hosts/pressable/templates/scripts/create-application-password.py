#!/usr/bin/env python3
"""Create the WordPress MCP Application Password for a pinned connection and store it in a new Conclave item.

    python3 scripts/create-application-password.py example-wordpress --title "Example Production WordPress MCP"

Generalised from two production sites. The connection is a `basic` entry under `mcp` in
.conclave/wordpress-site.json with `url`, `username` and `wordpress_user_id` set; its `application_password_uuid`
stays null until this script prints it. The password is created over the pinned private SSH channel
(scripts/lib/site_ssh.py), never through a Pressable command, because Pressable's operation logs capture command output.
It lives only in this process's memory and on the pipe to `conclave-op item create -`, never in an argument, the output,
a log or the repository. The item is read back by its immutable id and compared by SHA-256.

Refuses when the vault title or the Application Password name already exists, so it never overwrites a credential. If
the vault refuses the item, the just-created Application Password is deleted again by its UUID. This writes to the
live site's database: run it only with the owner's approval.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import site_ssh  # noqa: E402
import wp_site  # noqa: E402


def vault(*args, input=None):
    return subprocess.run([wp_site.OP, *args, "--vault", wp_site.VAULT, "--format=json"], input=input,
                          capture_output=True, text=True, timeout=60)


def wp(pin, *arguments):
    result = site_ssh.wp(list(arguments), timeout=120, pin=pin)
    if result.returncode:
        raise SystemExit("remote WP-CLI failed (output suppressed): wp " + " ".join(arguments[:3]))
    return result.stdout


def uuids(pin, user_id, name):
    listed = json.loads(wp(pin, "user", "application-password", "list", str(user_id), "--format=json", "--fields=uuid,name") or "[]")
    return [entry["uuid"] for entry in listed if entry.get("name") == name]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("connection")
    parser.add_argument("--title", required=True, help="New Conclave item title")
    parser.add_argument("--name", default="wordpress-mcp-claude-codex", help="Application Password name in WordPress")
    args = parser.parse_args()
    pin = wp_site.load()
    entry = pin.get("mcp", {}).get(args.connection)
    if not entry or entry["scheme"] != "basic":
        raise SystemExit("not a pinned WordPress MCP (basic) connection")
    if entry.get("application_password_uuid") is not None:
        raise SystemExit("the pin already names an Application Password for this connection; nothing changed")
    site_id, url, endpoint, username, user_id = wp_site.require(
        pin, "site_id", "url", f"mcp.{args.connection}.url", f"mcp.{args.connection}.username",
        f"mcp.{args.connection}.wordpress_user_id")
    if vault("item", "get", args.title).returncode == 0:
        raise SystemExit("a Conclave item with that title already exists; nothing changed")
    if wp(pin, "user", "get", str(user_id), "--field=user_login").strip() != username or wp(pin, "option", "get", "home").strip() != url:
        raise SystemExit("the site's user or URL does not match the pin; nothing changed")
    if uuids(pin, user_id, args.name):
        raise SystemExit("an Application Password with that name already exists; nothing changed")
    password = wp(pin, "user", "application-password", "create", str(user_id), args.name, "--porcelain").strip()
    created_uuid = uuids(pin, user_id, args.name)
    if len(created_uuid) != 1:
        raise SystemExit("could not identify the new Application Password; check wp-admin > Users > Profile")
    created_uuid = created_uuid[0]
    if len(password) != 24 or not password.isalnum():
        wp(pin, "user", "application-password", "delete", str(user_id), created_uuid)
        raise SystemExit("WordPress returned an unexpected password; it was deleted again")
    item = {"title": args.title, "category": "LOGIN", "fields": [
        {"id": "username", "type": "STRING", "purpose": "USERNAME", "label": "username", "value": username},
        {"id": "password", "type": "CONCEALED", "purpose": "PASSWORD", "label": "password", "value": password},
        *({"label": key, "type": "STRING", "value": text} for key, text in (
            ("site_id", str(site_id)), ("site_url", url), ("environment", pin["environment"]), ("endpoint", endpoint),
            ("wordpress_user_id", str(user_id)), ("application_password_name", args.name),
            ("application_password_uuid", created_uuid)))]}
    created = vault("item", "create", "-", input=json.dumps(item))
    want = hashlib.sha256(password.encode()).hexdigest()
    del password, item
    if created.returncode != 0:
        wp(pin, "user", "application-password", "delete", str(user_id), created_uuid)
        raise SystemExit("1Password refused the item; the Application Password was deleted again")
    item_id = json.loads(created.stdout)["id"]
    stored = vault("item", "get", item_id)
    if stored.returncode != 0:
        raise SystemExit(f"item {item_id} was created but could not be read back; check it before use")
    readback = json.loads(stored.stdout)
    fields = {(f.get("label") or f["id"]): f.get("value", "") for f in readback.get("fields", [])}
    got = hashlib.sha256(fields.get("password", "").encode()).hexdigest()
    print(json.dumps({"item_id": item_id, "id_matches": readback.get("id") == item_id,
                      "application_password_uuid": created_uuid, "sha256_match": got == want}))
    return 0 if got == want and readback.get("id") == item_id else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        # Never print upstream output: it could hold the new password.
        print("create-application-password failed: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
