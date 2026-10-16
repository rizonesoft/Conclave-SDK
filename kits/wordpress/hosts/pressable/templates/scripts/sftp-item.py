#!/usr/bin/env python3
"""Give the pinned Pressable site its SFTP/SSH identity in the Conclave vault, without the password ever being printed.

    python3 scripts/sftp-item.py --title "Example Production SSH SFTP"

Generalised from rizonetech-com and jmrgroup-coza. A reset replaces the live site's SFTP/SSH password: anything still
using the old one stops working, so run it only with the owner's approval, and never when a working item exists.

It speaks MCP to Pressable's control plane through the pinned `bearer` connection (.conclave/wordpress-site.json),
checks the site id and URL against Pressable's record, finds the site's one owner FTP account, resets its password
(Pressable returns the new one once), and pipes the item JSON into `conclave-op item create -`. The password lives only
in this process's memory and on the pipe to 1Password. The new item is read back by its immutable id and compared by
SHA-256. It prints the new item id, the SFTP username and whether the hashes matched; put both into the pin's `ssh`.
Refuses when the item title already exists, so it never overwrites a credential.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import wp_site  # noqa: E402
from mcp_http import Client, connection_for  # noqa: E402

PRESSABLE = "https://mcp.pressable.com"


def vault(*args, input=None):
    return subprocess.run([wp_site.OP, *args, "--vault", wp_site.VAULT, "--format=json"], input=input,
                          capture_output=True, text=True, timeout=60)


def reset_password(reply):
    """The reply's shape is not documented beyond "returns the new plain-text password": take the one string held
    under a key naming a password, at any depth."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if isinstance(child, str) and "password" in key.lower():
                    found.append(child)
                else:
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(reply)
    return found[0] if len(set(found)) == 1 else ""


def owner_username(accounts):
    users = accounts.get("ftp_accounts") or accounts.get("accounts") or accounts.get("data") or []
    owners = [user for user in users if user.get("owner")] or users
    if len(owners) != 1 or not owners[0].get("username"):
        raise SystemExit("expected exactly one owner FTP account; nothing changed")
    return owners[0]["username"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()
    pin = wp_site.load()
    if pin["host"] != "pressable":
        raise SystemExit("only a Pressable site can reset SFTP credentials here; a WordPress.com site's come from Hosting > Settings")
    site_id, url, account, ssh_host, sftp_host, port = wp_site.require(
        pin, "site_id", "url", "pressable.account_id", "ssh.ssh_host", "ssh.sftp_host", "ssh.port")
    if vault("item", "get", args.title).returncode == 0:
        raise SystemExit("a Conclave item with that title already exists; nothing changed")
    with Client(connection_for(pin, "bearer", PRESSABLE), pin, "conclave-sftp-item") as mcp:
        details = mcp.pressable("get_site_details", {"site_id": site_id})
        if details.get("id") != site_id or details.get("https_url") != url or details.get("account_id") != account:
            raise SystemExit("the pinned site id, URL and account do not match Pressable's record; nothing changed")
        username = owner_username(mcp.pressable("list_site_ftp_accounts", {"site_id": site_id}))
        password = reset_password(mcp.pressable("reset_ftp_password", {"site_id": site_id, "username": username}))
    try:
        wp_site.secret({"password": password})
    except ValueError:
        raise SystemExit("Pressable did not return a usable password; the old one may have changed, so reset it again") from None
    item = {"title": args.title, "category": "LOGIN", "fields": [
        {"id": "username", "type": "STRING", "purpose": "USERNAME", "label": "username", "value": username},
        {"id": "password", "type": "CONCEALED", "purpose": "PASSWORD", "label": "password", "value": password},
        *({"label": key, "type": "STRING", "value": text} for key, text in (
            ("hostname", sftp_host), ("port", port), ("ssh_hostname", ssh_host), ("site_id", str(site_id)),
            ("site_url", url), ("environment", pin["environment"])))]}
    created = vault("item", "create", "-", input=json.dumps(item))
    want = hashlib.sha256(password.encode()).hexdigest()
    del password, item
    if created.returncode != 0:
        raise SystemExit("1Password refused the item; the SFTP password was reset, so run this again to reset and store it")
    item_id = json.loads(created.stdout)["id"]
    stored = vault("item", "get", item_id)
    if stored.returncode != 0:
        raise SystemExit(f"item {item_id} was created but could not be read back; check it before use")
    readback = json.loads(stored.stdout)
    fields = {(f.get("label") or f["id"]): f.get("value", "") for f in readback.get("fields", [])}
    got = hashlib.sha256(fields.get("password", "").encode()).hexdigest()
    print(json.dumps({"item_id": item_id, "id_matches": readback.get("id") == item_id, "username": username,
                      "sha256_match": got == want}))
    return 0 if got == want and readback.get("id") == item_id else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        # Never print upstream output: it could hold the new password.
        print("sftp-item failed: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
