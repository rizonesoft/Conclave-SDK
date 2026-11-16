"""Minimal streamable-HTTP MCP client for diagnostics and setup, generalised from two production sites.

Headers come from scripts/mcp-headers.py in-process, so no credential reaches an argument, a log or stdout. The URL of
each connection is the `url` of its entry under `mcp` in `.conclave/wordpress-site.json`.
"""
import importlib.util
import json
from pathlib import Path
import urllib.request

import wp_site

_spec = importlib.util.spec_from_file_location("mcp_headers", Path(__file__).resolve().parents[1] / "mcp-headers.py")
mcp_headers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mcp_headers)

PROTOCOL = "2025-06-18"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def post(url, body, headers, timeout=120):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
        return response.headers.get("Mcp-Session-Id"), response.read().decode()


def decode(text):
    """A streamable HTTP reply is JSON, or server-sent events whose data lines carry the JSON-RPC reply."""
    if not text.strip():
        return None
    if text.lstrip().startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[5:])
            if "id" in data:
                return data
    return None


def payload(result):
    if result.get("isError"):
        raise ValueError("MCP tool call failed")
    data = result.get("structuredContent")
    if data is None:
        data = json.loads("\n".join(part["text"] for part in result.get("content", []) if part.get("type") == "text"))
    if not isinstance(data, (dict, list)):
        raise ValueError("unexpected MCP response")
    return data


class Client:
    def __init__(self, connection, pin=None, client_name="conclave-wordpress"):
        self.pin = pin or wp_site.load()
        (self.url,) = wp_site.require(self.pin, f"mcp.{connection}.url")
        self.headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                        **mcp_headers.headers(connection, self.pin)}
        self.client_name = client_name
        self.counter = 0
        self.server = None

    def __enter__(self):
        self.server = self.rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                              "clientInfo": {"name": self.client_name, "version": "1"}})
        # Every later request names the negotiated version; MCP Adapter 0.7.0 refuses one without it (HTTP 400).
        self.headers["MCP-Protocol-Version"] = self.server.get("protocolVersion", PROTOCOL)
        post(self.url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, self.headers)
        return self

    def __exit__(self, *args):
        return False

    def rpc(self, method, params):
        self.counter += 1
        session, text = post(self.url, {"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params}, self.headers)
        if session:
            self.headers["Mcp-Session-Id"] = session
        result = decode(text)
        if not result or "error" in result:
            raise RuntimeError("MCP request failed: " + method)
        return result["result"]

    def tools(self):
        names, cursor = [], None
        while True:
            page = self.rpc("tools/list", {"cursor": cursor} if cursor else {})
            names += [tool["name"] for tool in page.get("tools", [])]
            cursor = page.get("nextCursor")
            if not cursor:
                return names

    def call(self, tool, arguments):
        return payload(self.rpc("tools/call", {"name": tool, "arguments": arguments}))

    def pressable(self, tool, parameters):
        """Pressable's control plane exposes three tools and routes every operation through execute_tool."""
        return self.call("execute_tool", {"tool_name": tool, "parameters": parameters})


def connection_for(pin, scheme, url=None):
    """The one pinned connection with this scheme (and URL), or a refusal naming the ambiguity."""
    found = [name for name, entry in pin.get("mcp", {}).items()
             if entry["scheme"] == scheme and (url is None or entry.get("url") == url)]
    if len(found) != 1:
        raise ValueError(f"expected exactly one {scheme} MCP connection in .conclave/wordpress-site.json")
    return found[0]
