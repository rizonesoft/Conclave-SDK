#!/usr/bin/env python3
"""MCP HTTP header helper for Claude Code (`headersHelper`) and Codex. Stdout is a private pipe to the client.

Never run it in a terminal or print its output: stdout carries the credential. Each connection is an entry under `mcp`
in `.conclave/wordpress-site.json`. A `basic` connection is the site's WordPress MCP (`mcp-adapter`): its Conclave item
must name the pinned site, environment, endpoint, WordPress user and Application Password UUID, or it is refused. A
`bearer` connection is the account-level Pressable control plane token.
"""
import base64
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import wp_site  # noqa: E402

BASIC_PINS = ("username", "url", "wordpress_user_id", "application_password_uuid")


def entry(pin, connection):
    found = pin.get("mcp", {}).get(connection)
    if found is None:
        raise ValueError("unknown MCP connection")
    return found


def expected_fields(pin, connection):
    """The fields a WordPress MCP item must carry to belong to this site and this connection."""
    if entry(pin, connection)["scheme"] != "basic":
        raise ValueError("not a WordPress MCP connection")
    site_id, url = wp_site.require(pin, "site_id", "url")
    username, endpoint, user_id, uuid = wp_site.require(pin, *(f"mcp.{connection}.{key}" for key in BASIC_PINS))
    return {"site_id": str(site_id), "site_url": url, "environment": pin["environment"], "username": username,
            "endpoint": endpoint, "wordpress_user_id": str(user_id), "application_password_uuid": uuid}


def headers(connection, pin=None):
    pin = pin or wp_site.load()
    found = entry(pin, connection)
    (item_id,) = wp_site.require(pin, f"mcp.{connection}.item")
    if found["scheme"] == "bearer":
        fields = wp_site.vault_fields(item_id)
        return {"Authorization": "Bearer " + wp_site.secret(fields)}
    expected = expected_fields(pin, connection)
    fields = wp_site.vault_fields(item_id)
    if any(fields.get(key) != value for key, value in expected.items()):
        raise ValueError("WordPress site identity mismatch")
    password = wp_site.secret(fields)
    encoded = base64.b64encode(f"{expected['username']}:{password}".encode()).decode()
    return {"Authorization": "Basic " + encoded}


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("expected one connection")
        output = headers(sys.argv[1])
    except Exception:
        # Never include upstream stdout/stderr or an exception that could contain a credential.
        print("MCP credential unavailable; check the connection's Conclave item and .conclave/wordpress-site.json.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(output))
