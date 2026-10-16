#!/usr/bin/env python3
"""Verify every MCP connection pinned in .conclave/wordpress-site.json: identity, reads and auth refusal. Read-only.

For each connection it proves initialize, tools/list and at least one read, pins the answering site and credential,
and checks that an anonymous request and one with invalid credentials are both refused with 401 (or 403).

- `basic` (the site's `mcp-adapter`, enabled with Pressable `toggle_site_wordpress_mcp`): `core/get-site-info`,
  `core/get-environment-info` and `core/get-user-info` must answer as the pinned URL, environment and user.
- `bearer` (the Pressable control plane): `get_site_details` must return the pinned site and account.

The refusal probe sends initialize, because Pressable checks the session header before the token on any later method.

Usage: check-mcp.py [connection ...]   (default: every pinned connection)
"""
import json
from pathlib import Path
import sys
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import wp_site  # noqa: E402
from mcp_http import PROTOCOL, Client, post  # noqa: E402

INVALID = {"basic": "Basic aW52YWxpZDppbnZhbGlk", "bearer": "Bearer invalid-token"}


def refusals(url, scheme):
    codes = []
    for auth in (None, INVALID[scheme]):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if auth:
            headers["Authorization"] = auth
        try:
            post(url, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "conclave-refusal-probe", "version": "1"}}},
                headers, timeout=30)
        except urllib.error.HTTPError as error:
            if error.code not in (401, 403):
                raise ValueError("unexpected HTTP status " + str(error.code))
            codes.append(error.code)
        else:
            raise ValueError("unauthenticated request admitted")
    return codes


def execute(client, name, parameters):
    result = client.call("mcp-adapter-execute-ability", {"ability_name": name, "parameters": parameters})
    if result.get("success") is not True:
        raise ValueError("ability failed: " + name)
    return result["data"]


def wordpress(pin, connection):
    entry = pin["mcp"][connection]
    url, user_id = wp_site.require(pin, "url", f"mcp.{connection}.wordpress_user_id")
    with Client(connection, pin, "conclave-mcp-check") as client:
        tools = client.tools()
        abilities = {a["name"] for a in client.call("mcp-adapter-discover-abilities", {})["abilities"]}
        site = execute(client, "core/get-site-info", {"fields": ["name", "url", "version"]})
        env = execute(client, "core/get-environment-info", {"fields": ["environment", "php_version", "db_server_info", "wp_version"]})
        user = execute(client, "core/get-user-info", {"fields": ["id", "user_login"]})
    if site.get("url") != url or env.get("environment") != pin["environment"] or user.get("id") != user_id:
        raise ValueError("wrong WordPress site or credential identity")
    return {"server": client.server.get("serverInfo", {}), "tools": len(tools), "abilities": len(abilities), "site": site,
            "environment": env, "user": user, "refused": refusals(entry["url"], "basic")}


def pressable(pin, connection):
    entry = pin["mcp"][connection]
    site_id, url, account = wp_site.require(pin, "site_id", "url", "pressable.account_id")
    with Client(connection, pin, "conclave-mcp-check") as client:
        tools = client.tools()
        site = client.pressable("get_site_details", {"site_id": site_id})
    if site.get("id") != site_id or site.get("https_url") != url or site.get("account_id") != account:
        raise ValueError("Pressable site identity mismatch")
    # `staging` is reported, not enforced: a Pressable clone keeps `staging: true` even when it serves production.
    keys = ("id", "account_id", "name", "https_url", "state", "staging", "environment", "php_version", "datacenter_code")
    return {"server": client.server.get("serverInfo", {}), "tools": len(tools), **{k: site.get(k) for k in keys},
            "refused": refusals(entry["url"], "bearer")}


def main(argv):
    pin = wp_site.load()
    names = argv or list(pin.get("mcp", {}))
    if not names:
        raise SystemExit("no MCP connections are pinned in .conclave/wordpress-site.json yet")
    failed = False
    for name in names:
        try:
            if name not in pin.get("mcp", {}):
                raise ValueError("not pinned in .conclave/wordpress-site.json")
            check = wordpress if pin["mcp"][name]["scheme"] == "basic" else pressable
            print(name, json.dumps(check(pin, name), indent=2))
        except Exception as exc:
            failed = True
            # Messages above are fixed strings; never echo a response that could carry a credential.
            print(name + " check failed: " + type(exc).__name__ + ": " + str(exc)[:200], file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
