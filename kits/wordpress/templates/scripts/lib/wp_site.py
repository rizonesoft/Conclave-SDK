"""The one place that names this project's WordPress site: `.conclave/wordpress-site.json`.

Installed by the Conclave-SDK WordPress kit. Every helper reads the pin through this module. A malformed pin is
refused outright. A value the setup has not filled in yet is `null`, and `require` names it instead of guessing.
Credentials are read from the vault by immutable item id, never by title. Which vault, and which command line tool
reads it, are this owner's settings: `[vault] name` and `cli` in `.conclave/local.toml` with `.private/local.toml`
as the overlay fallback (both ignored by git; the template is `.conclave/local.example.toml`), `Conclave` and
`conclave-op` on PATH when unset.
"""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / ".conclave" / "wordpress-site.json"
LOCAL = ROOT / ".conclave" / "local.toml"


def _local_settings():
    """Load the shared local_settings helper from this project's `.conclave/local_settings.py` (falling back to
    the base kit template only when running directly inside the SDK's `kits/wordpress/templates/` tree)."""
    candidates = [ROOT / ".conclave" / "local_settings.py"]
    if ROOT.name == "templates" and len(ROOT.parents) >= 3:
        kits_dir = ROOT.parents[1]
        sdk_dir = ROOT.parents[2]
        if kits_dir.name == "kits" and (sdk_dir / "forge.py").is_file():
            candidates.append(kits_dir / "base" / "templates" / ".conclave" / "local_settings.py")
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_wp_local_settings", candidate)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise ValueError(f".conclave/local_settings.py is missing under {ROOT}")


def vault_settings(path=None, *, root=ROOT):
    """(cli, name) from `[vault]` in `.conclave/local.toml` and `.private/local.toml` (or an explicit `path`);
    a missing file or key keeps its default, and a file that is not TOML or a value that is not a plain non-empty
    string is refused."""
    ls = _local_settings()
    if path is not None:
        source = str(path)
        try:
            data = ls.read_toml_file(path)
        except FileNotFoundError:
            data = {}
        except ls.LocalSettingsError as error:
            raise ValueError(str(error).replace("not readable as UTF-8 TOML", "not readable as TOML")) from None
    else:
        try:
            data, loaded = ls.load_local_settings(root)
        except ls.LocalSettingsError as error:
            raise ValueError(str(error).replace("not readable as UTF-8 TOML", "not readable as TOML")) from None
        source = " / ".join(loaded) if loaded else f"{ls.LOCAL} / {ls.OVERLAY}"
    table = data.get("vault", {})
    if not isinstance(table, dict):
        raise ValueError(f"{source}: [vault] must be a table")
    found = []
    for key, default in (("cli", "conclave-op"), ("name", "Conclave")):
        value = table.get(key, default)
        if not isinstance(value, str) or not value.strip() or any(char in value for char in "\r\n\0"):
            raise ValueError(f"{source}: vault.{key} must be a non-empty string")
        found.append(value)
    return tuple(found)


OP, VAULT = vault_settings()

HOSTS = ("pressable", "wpcom")
ENVIRONMENTS = ("production", "staging")
SCHEMES = ("basic", "bearer")
# The account-wide Pressable token may only ever be sent here.
PRESSABLE_MCP = "https://mcp.pressable.com"
REQUIRED_MCP_KEYS = {
    "basic": ("item", "url", "username", "wordpress_user_id", "application_password_uuid"),
    "bearer": ("item", "url"),
}

ITEM_ID = re.compile(r"^[a-z0-9]{26}$")
URL = re.compile(r"^https://[a-z0-9.-]+\.[a-z]{2,}(/[A-Za-z0-9._~-]+)*$")
HOSTNAME = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
USERNAME = re.compile(r"^[A-Za-z0-9._@-]+$")
# Interpolated into `cd <wp_path>` on the server, so only plain path characters (and a leading `~/`) are allowed.
WP_PATH = re.compile(r"^(~/|/)?[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$")
CONNECTION = re.compile(r"^[a-z0-9][a-z0-9-]*$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
DIGITS = re.compile(r"^[0-9]+$")


def _optional(value, pattern, name):
    if value is None:
        return
    # fullmatch: `match` with a `$` anchor also accepts a trailing newline, which would reach a remote command line.
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid {name} in the site pin")
    if pattern is URL and any(segment in (".", "..") for segment in value.split("/")[3:]):
        raise ValueError(f"invalid {name} in the site pin")


MAX_PHP_INT = (1 << 63) - 1


def _optional_id(value, name):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > MAX_PHP_INT:
        raise ValueError(f"invalid {name} in the site pin")


def _keys(section, allowed, name):
    if not isinstance(section, dict):
        raise ValueError(f"{name} in the site pin must be an object")
    unknown = sorted(key for key in section if key not in allowed and not key.startswith("_"))
    if unknown:
        raise ValueError(f"unknown keys in {name} of the site pin: {', '.join(unknown)}")


def validate(pin):
    """Refuse a pin whose shape or values could point a helper at the wrong site or break a remote command."""
    _keys(pin, ("host", "site_id", "url", "environment", "ssh", "pressable", "mcp"), "the top level")
    if pin.get("host") not in HOSTS:
        raise ValueError("host in the site pin must be one of: " + ", ".join(HOSTS))
    _optional_id(pin.get("site_id"), "site_id")
    _optional(pin.get("url"), URL, "url")
    if pin.get("environment") not in ENVIRONMENTS:
        raise ValueError("environment in the site pin must be one of: " + ", ".join(ENVIRONMENTS))

    ssh = pin.get("ssh", {})
    _keys(ssh, ("item", "ssh_host", "sftp_host", "port", "username", "wp_path"), "ssh")
    _optional(ssh.get("item"), ITEM_ID, "ssh.item")
    _optional(ssh.get("ssh_host"), HOSTNAME, "ssh.ssh_host")
    _optional(ssh.get("sftp_host"), HOSTNAME, "ssh.sftp_host")
    _optional(ssh.get("port"), DIGITS, "ssh.port")
    _optional(ssh.get("username"), USERNAME, "ssh.username")
    _optional(ssh.get("wp_path"), WP_PATH, "ssh.wp_path")

    pressable = pin.get("pressable")
    if pressable is not None:
        if pin["host"] != "pressable":
            raise ValueError("only a Pressable site pin has a pressable section")
        _keys(pressable, ("account_id",), "pressable")
        _optional_id(pressable.get("account_id"), "pressable.account_id")

    mcp = pin.get("mcp", {})
    if not isinstance(mcp, dict):
        raise ValueError("mcp in the site pin must be an object")
    for name, entry in mcp.items():
        if not CONNECTION.fullmatch(name):
            raise ValueError("invalid mcp connection name in the site pin")
        _keys(entry, ("item", "scheme", "url", "username", "wordpress_user_id", "application_password_uuid"), "mcp." + name)
        if entry.get("scheme") not in SCHEMES:
            raise ValueError(f"mcp.{name}.scheme must be one of: " + ", ".join(SCHEMES))
        _optional(entry.get("item"), ITEM_ID, f"mcp.{name}.item")
        _optional(entry.get("url"), URL, f"mcp.{name}.url")
        if entry["scheme"] == "basic":
            _optional(entry.get("username"), USERNAME, f"mcp.{name}.username")
            _optional_id(entry.get("wordpress_user_id"), f"mcp.{name}.wordpress_user_id")
            _optional(entry.get("application_password_uuid"), UUID, f"mcp.{name}.application_password_uuid")
            # A site credential may only be sent to the pinned site itself.
            if entry.get("url") is not None and (pin.get("url") is None or not entry["url"].startswith(pin["url"] + "/wp-json/")):
                raise ValueError(f"mcp.{name}.url must be on the pinned site, under {pin.get('url')}/wp-json/")
        else:
            # A WordPress.com pin may carry the site's own `basic` MCP servers (the MCP Adapter, Elementor MCP) beside the
            # WordPress.com connector, but never the account-wide Pressable token.
            if pin["host"] != "pressable":
                raise ValueError(f"mcp.{name} is a bearer connection, which only a Pressable site pin carries")
            if any(entry.get(key) is not None for key in ("username", "wordpress_user_id", "application_password_uuid")):
                raise ValueError(f"mcp.{name} is a bearer connection and carries no WordPress user")
            if entry.get("url") not in (None, PRESSABLE_MCP):
                raise ValueError(f"mcp.{name} is a bearer connection, so its url must be {PRESSABLE_MCP}")
    return pin


def load(path=None):
    path = Path(path) if path else PIN
    with open(path, encoding="utf-8") as handle:
        return validate(json.load(handle))


def value(pin, dotted):
    node = pin
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def unset(pin, *dotted):
    return [name for name in dotted if value(pin, name) is None]


def require(pin, *dotted):
    """Return the named values, or refuse naming every one the setup has not filled in yet."""
    missing = unset(pin, *dotted)
    if missing:
        raise ValueError("not set in .conclave/wordpress-site.json yet: " + ", ".join(missing))
    return [value(pin, name) for name in dotted]


def ssh_identity(pin):
    """The vault item that holds the SSH/SFTP password, and the fields it must carry to be this site's."""
    item, ssh_host, sftp_host, port, username, site_id, url = require(
        pin, "ssh.item", "ssh.ssh_host", "ssh.sftp_host", "ssh.port", "ssh.username", "site_id", "url")
    # Both hosts are pinned in the vault item too, so an edited pin cannot send the password anywhere else.
    return item, {"hostname": sftp_host, "ssh_hostname": ssh_host, "port": port, "username": username,
                  "site_id": str(site_id), "site_url": url, "environment": pin["environment"]}


def ssh_enabled(pin):
    """A WordPress.com Simple site has no SSH; its pin says so with ssh.ssh_host null."""
    return not (pin["host"] == "wpcom" and value(pin, "ssh.ssh_host") is None)


def pinned_user(pin):
    """The one WordPress user every `basic` entry under `mcp` names; none, missing, invalid, or two is a ValueError."""
    named = [entry.get("wordpress_user_id") for entry in (pin.get("mcp") or {}).values()
             if isinstance(entry, dict) and entry.get("scheme") == "basic"]
    if not named:
        raise ValueError("no basic entry under mcp in .conclave/wordpress-site.json names a wordpress_user_id")
    if any(user is None for user in named):
        raise ValueError("a basic entry under mcp in .conclave/wordpress-site.json names no wordpress_user_id")
    if any(isinstance(user, bool) or not isinstance(user, int) or user < 1 or user > MAX_PHP_INT for user in named):
        raise ValueError("a wordpress_user_id in .conclave/wordpress-site.json is not a user")
    if len(set(named)) != 1:
        raise ValueError("the basic entries under mcp in .conclave/wordpress-site.json name different users")
    return named[0]


def vault_fields(item_id):
    """Read one Conclave item by immutable id and return its fields keyed by label. Never prints anything."""
    if not ITEM_ID.fullmatch(item_id or ""):
        raise ValueError("invalid vault item id")
    result = subprocess.run([OP, "item", "get", item_id, "--vault", VAULT, "--format=json"],
                            capture_output=True, text=True, timeout=30, check=True)
    item = json.loads(result.stdout)
    if item.get("id") != item_id:
        raise ValueError("unexpected vault item")
    # Key on label: 1Password assigns random ids to fields added through the CLI,
    # so a label is the only stable handle across items created by either route.
    return {(field.get("label") or field["id"]): field.get("value", "") for field in item.get("fields", [])}


def secret(fields, name="password"):
    """Refuse a missing secret, or one that could break the pipe or a header."""
    found = fields.get(name, "")
    if not found.strip() or len(found.encode()) > 1024 or any(char in found for char in "\r\n\0"):
        raise ValueError("missing or invalid credential")
    return found
