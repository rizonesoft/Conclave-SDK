#!/usr/bin/env python3
"""Install, inspect and remove the Conclave ticket login MU-plugin on the pinned WordPress site (D07 T02 section 3).

Installed by the Conclave-SDK WordPress kit. Every remote call goes through `scripts/lib/site_ssh.py` with the site
pin in `.conclave/wordpress-site.json`. Writes require `--yes` and refuse native Windows, incomplete pins, multisite
installations, and relocated MU-plugin directories before touching any remote file.

    python3 scripts/ticket-login.py status          show plugin state (absent, current, differs) and option presence
    python3 scripts/ticket-login.py install --yes   stage, verify, publish and read back the MU-plugin
    python3 scripts/ticket-login.py remove --yes    delete the MU-plugin and ticket option and confirm both absent
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import site_ssh
import wp_site

OPTION = "conclave_login_ticket"
PLUGIN_NAME = "conclave-ticket-login.php"
MU_REL = "wp-content/mu-plugins"
PLUGIN_REL = f"{MU_REL}/{PLUGIN_NAME}"
ROOT = Path(__file__).resolve().parents[1]
LOCAL_PLUGIN = ROOT / "tools" / "ticket-login" / PLUGIN_NAME
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REMOTE_TIMEOUT = 90
WINDOWS = ("the pinned SSH hands its password to sshpass, which native Windows has not: run "
           "python3 scripts/ticket-login.py from WSL or Linux")

WP_PROBE = (
    "global $wpdb; "
    f"$c = $wpdb->get_var( $wpdb->prepare( \"SELECT COUNT(*) FROM {{$wpdb->options}} WHERE option_name = %s\", '{OPTION}' ) ); "
    "if ( '' !== (string) $wpdb->last_error || null === $c ) { "
    "echo 'CONCLAVE_WP:' . json_encode( array( 'error' => 'db' ) ); return; } "
    "$mu_raw = defined( 'WPMU_PLUGIN_DIR' ) ? WPMU_PLUGIN_DIR : ''; "
    "$mu_real = ( '' !== $mu_raw && false !== realpath( $mu_raw ) ) ? realpath( $mu_raw ) : $mu_raw; "
    "$mu = rtrim( str_replace( '\\\\', '/', (string) $mu_real ), '/' ); "
    "$ab_raw = defined( 'ABSPATH' ) ? ABSPATH : ''; "
    "$ab_real = ( '' !== $ab_raw && false !== realpath( $ab_raw ) ) ? realpath( $ab_raw ) : $ab_raw; "
    "$expected = '' !== $ab_real ? rtrim( str_replace( '\\\\', '/', (string) $ab_real ), '/' ) . '/wp-content/mu-plugins' : ''; "
    "echo 'CONCLAVE_WP:' . json_encode( array( "
    "'option' => ( (int) $c > 0 ) ? 'present' : 'absent', "
    "'multisite' => function_exists( 'is_multisite' ) && is_multisite(), "
    "'mu_dir' => $mu, "
    "'mu_match' => ( '' !== $mu && '' !== $expected && $mu === $expected ) "
    ") );"
)

_FILE_ERRORS = {
    "not-dir": "could not inspect the remote plugin file (mu-plugins path is not a directory)",
    "unreadable": "could not inspect the remote plugin file (permission denied or unreadable)",
    "symlink": "could not inspect the remote plugin file (unexpected symbolic link)",
    "directory": "could not inspect the remote plugin file (target path is a directory)",
    "no-sha256": "could not inspect the remote plugin file (remote host lacks sha256sum and shasum)",
}

WP_DELETE_OPTION = (
    "global $wpdb; "
    f"delete_option( '{OPTION}' ); "
    f"wp_cache_delete( '{OPTION}', 'options' ); "
    "if ( '' !== (string) $wpdb->last_error ) { echo 'CONCLAVE_DEL:error'; return; } "
    "echo 'CONCLAVE_DEL:ok';"
)

WP_FALLBACK_ROOT = (
    "$r = WP_CLI::get_runner()->find_wp_root(); "
    "$real = ( is_string( $r ) && '' !== $r && false !== realpath( $r ) ) ? realpath( $r ) : (string) $r; "
    "echo 'CONCLAVE_ROOT:' . rtrim( str_replace( '\\\\', '/', $real ), '/' );"
)


def native_windows() -> bool:
    """True on Windows outside WSL, where the pinned SSH cannot run."""
    return os.name == "nt"


class Refusal(Exception):
    """A failure explained in a single fixed sentence without leaking remote output or secrets."""

    def __init__(self, message: str, code: int = 1, *, bootstrap_failed: bool = False):
        super().__init__(message)
        self.code = code
        self.bootstrap_failed = bootstrap_failed


def _say(stream, text: str) -> None:
    print("ticket-login: " + text, file=stream)


def _pin() -> dict:
    """Validate platform and site pin before any vault read or transport call (exit 2 on refusal)."""
    if native_windows():
        raise Refusal(WINDOWS, 2)
    try:
        pin = wp_site.load()
    except OSError:
        raise Refusal("the site pin .conclave/wordpress-site.json cannot be read", 2) from None
    except ValueError as error:
        raise Refusal(f"the site pin is invalid: {error}", 2) from None
    if not wp_site.ssh_enabled(pin):
        raise Refusal("the ticket login needs SSH (ssh.ssh_host is null in .conclave/wordpress-site.json)", 2)
    missing = wp_site.unset(pin, "url", "ssh.wp_path")
    if missing:
        if "ssh.wp_path" in missing:
            raise Refusal("the ticket login needs SSH and ssh.wp_path in .conclave/wordpress-site.json", 2)
        raise Refusal("not set in .conclave/wordpress-site.json yet: " + ", ".join(missing), 2)
    try:
        wp_site.ssh_identity(pin)
    except ValueError as error:
        raise Refusal(f"the ticket login needs complete SSH identity fields: {error}", 2) from None
    return pin


def _local_plugin_bytes() -> tuple[bytes, str]:
    try:
        raw = LOCAL_PLUGIN.read_bytes()
    except OSError:
        raise Refusal(f"the local plugin copy cannot be read: {LOCAL_PLUGIN}", 1) from None
    return raw, hashlib.sha256(raw).hexdigest()


def _wp_path(pin: dict) -> str:
    (wp_path,) = wp_site.require(pin, "ssh.wp_path")
    return wp_path


def _last_line(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def probe_file(pin: dict, rel: str = PLUGIN_REL) -> str | None:
    """Return the remote file's lowercase SHA-256 hex digest, None if confirmed absent, or raise Refusal(1)."""
    wp_path = _wp_path(pin)
    qrel = shlex.quote(rel)
    cmd = (
        f"cd {wp_path} || exit 20\n"
        f"p={qrel}\n"
        'd=$(dirname "$p")\n'
        'c=$(dirname "$d")\n'
        'if [ -L "$c" ]; then echo "ERR:symlink"; exit 0; fi\n'
        'if [ -e "$c" ] && [ ! -d "$c" ]; then echo "ERR:not-dir"; exit 0; fi\n'
        'if [ -d "$c" ] && { [ ! -x "$c" ] || [ ! -r "$c" ]; }; then echo "ERR:unreadable"; exit 0; fi\n'
        'if [ -L "$d" ]; then echo "ERR:symlink"; exit 0; fi\n'
        'if [ -e "$d" ] && [ ! -d "$d" ]; then echo "ERR:not-dir"; exit 0; fi\n'
        'if [ -d "$d" ] && { [ ! -x "$d" ] || [ ! -r "$d" ]; }; then echo "ERR:unreadable"; exit 0; fi\n'
        'if [ -L "$p" ]; then echo "ERR:symlink"; exit 0; fi\n'
        'if [ -d "$p" ]; then echo "ERR:directory"; exit 0; fi\n'
        'if [ ! -e "$p" ]; then echo "ABSENT"; exit 0; fi\n'
        'if [ ! -f "$p" ] || [ ! -r "$p" ]; then echo "ERR:unreadable"; exit 0; fi\n'
        'if command -v sha256sum >/dev/null 2>&1; then\n'
        '  h=$(sha256sum "$p" | awk "{print \\$1}")\n'
        'elif command -v shasum >/dev/null 2>&1; then\n'
        '  h=$(shasum -a 256 "$p" | awk "{print \\$1}")\n'
        'else\n'
        '  echo "ERR:no-sha256"; exit 0\n'
        'fi\n'
        '[ -n "$h" ] && echo "SHA256:$h" || echo "ERR:unreadable"\n'
    )
    try:
        done = site_ssh.run("ssh", [cmd], timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        raise
    except Exception:
        raise Refusal("could not inspect the remote plugin file", 1) from None
    if done.returncode != 0:
        raise Refusal("could not inspect the remote plugin file", 1)
    line = _last_line(done.stdout)
    if line == "ABSENT":
        return None
    if line.startswith("SHA256:"):
        digest = line[7:].strip().lower()
        if HEX64.fullmatch(digest):
            return digest
    if line.startswith("ERR:"):
        code = line[4:]
        if code in _FILE_ERRORS:
            raise Refusal(_FILE_ERRORS[code], 1)
    raise Refusal("unexpected reply while inspecting the remote plugin file", 1)


def _remote_wp_root(pin: dict) -> str:
    """Resolve the canonical POSIX path of ssh.wp_path on the remote host."""
    wp_path = _wp_path(pin)
    cmd = f"cd {wp_path} && pwd -P"
    try:
        done = site_ssh.run("ssh", [cmd], timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        raise
    except Exception:
        raise Refusal("could not resolve ssh.wp_path on the remote host", 1) from None
    root = _last_line(done.stdout).replace("\\", "/").rstrip("/")
    if done.returncode != 0 or not root:
        raise Refusal("could not resolve ssh.wp_path on the remote host", 1)
    return root


def probe_wp(pin: dict) -> dict:
    """Inspect option presence and WordPress MU-plugin layout via WP-CLI bound to --url=<pin.url>."""
    try:
        done = site_ssh.wp([f"--url={pin['url']}", "eval", WP_PROBE], timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        raise
    except Exception:
        raise Refusal("could not inspect WordPress on the pinned site", 1) from None
    marker = None
    for line in (done.stdout or "").splitlines():
        if line.strip().startswith("CONCLAVE_WP:"):
            marker = line.strip()[len("CONCLAVE_WP:"):]
    if done.returncode != 0 and not marker:
        raise Refusal("could not inspect WordPress on the pinned site", 1, bootstrap_failed=True)
    if done.returncode != 0 or not marker:
        raise Refusal("unexpected reply while inspecting WordPress on the pinned site", 1)
    try:
        data = json.loads(marker)
    except ValueError:
        raise Refusal("unexpected reply while inspecting WordPress on the pinned site", 1) from None
    if not isinstance(data, dict) or data.get("error"):
        raise Refusal("WordPress reported a database error while inspecting the ticket option", 1)
    opt = data.get("option")
    multisite = data.get("multisite")
    mu_match = data.get("mu_match")
    mu_dir = data.get("mu_dir", "")
    if (opt not in ("present", "absent") or not isinstance(multisite, bool)
            or not isinstance(mu_match, bool) or not isinstance(mu_dir, str)):
        raise Refusal("unexpected reply while inspecting WordPress on the pinned site", 1)
    return {"option": opt, "multisite": multisite, "mu_match": mu_match, "mu_dir": mu_dir.rstrip("/")}


def _truthy_config(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


def probe_layout_fallback(pin: dict) -> dict:
    """Fallback layout check via `wp eval --skip-wordpress` (WP-CLI core root) + `wp config list --format=json`."""
    try:
        root_done = site_ssh.wp([f"--url={pin['url']}", "eval", "--skip-wordpress", WP_FALLBACK_ROOT],
                                timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        raise
    except Exception:
        raise Refusal("could not verify the site's WordPress layout before changing files", 1) from None
    wp_cli_root = ""
    for line in (root_done.stdout or "").splitlines():
        if line.strip().startswith("CONCLAVE_ROOT:"):
            wp_cli_root = line.strip()[len("CONCLAVE_ROOT:"):].replace("\\", "/").rstrip("/")
    if root_done.returncode != 0 or not wp_cli_root:
        raise Refusal("could not verify the site's WordPress layout before changing files", 1)
    try:
        done = site_ssh.wp([f"--url={pin['url']}", "config", "list", "--format=json"], timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        raise
    except Exception:
        raise Refusal("could not verify the site's WordPress layout before changing files", 1) from None
    if done.returncode != 0:
        raise Refusal("could not verify the site's WordPress layout before changing files", 1)
    try:
        items = json.loads(done.stdout or "")
    except ValueError:
        raise Refusal("could not verify the site's WordPress layout before changing files", 1) from None
    if not isinstance(items, list):
        raise Refusal("could not verify the site's WordPress layout before changing files", 1)
    constants = {entry.get("name"): entry.get("value") for entry in items
                 if isinstance(entry, dict) and entry.get("type") == "constant" and isinstance(entry.get("name"), str)}
    # Mirror WordPress core is_multisite(): MULTISITE decides when defined; otherwise SUBDOMAIN_INSTALL, VHOST, or
    # SUNRISE being defined makes the installation multisite, while WP_ALLOW_MULTISITE alone does not.
    if "MULTISITE" in constants:
        multisite = _truthy_config(constants["MULTISITE"])
    else:
        multisite = any(name in constants for name in ("SUBDOMAIN_INSTALL", "VHOST", "SUNRISE"))
    relocated = "WPMU_PLUGIN_DIR" in constants or "WP_CONTENT_DIR" in constants
    return {"multisite": multisite, "mu_match": not relocated, "mu_dir": f"{wp_cli_root}/{MU_REL}"}


def check_supported_layout(pin: dict, *, allow_bootstrap_fallback: bool = False) -> None:
    """Refuse multisite installations and relocated/mismatched WPMU_PLUGIN_DIR before mutating MU-plugin files."""
    try:
        layout = probe_wp(pin)
    except Refusal as error:
        if not (allow_bootstrap_fallback and error.bootstrap_failed):
            raise
        layout = probe_layout_fallback(pin)
    if layout["multisite"]:
        raise Refusal("multisite installations are not supported for automatic MU-plugin mutation", 1)
    if not layout["mu_match"]:
        raise Refusal("WordPress loads MU-plugins from a relocated WPMU_PLUGIN_DIR; refusing to modify wp-content/mu-plugins", 1)
    wp_root = _remote_wp_root(pin)
    expected_mu = f"{wp_root}/{MU_REL}"
    if not layout.get("mu_dir") or layout["mu_dir"] != expected_mu:
        raise Refusal("WordPress WPMU_PLUGIN_DIR does not match ssh.wp_path/wp-content/mu-plugins; refusing to modify files", 1)


def _cleanup_temp(pin: dict, tmp_rel: str) -> bool:
    """Best-effort cleanup of this invocation's staging file only; never touches the final plugin file."""
    wp_path = _wp_path(pin)
    qtmp = shlex.quote(tmp_rel)
    cmd = f"cd {wp_path} && rm -f {qtmp} && [ ! -e {qtmp} ] && echo CLEANED"
    try:
        done = site_ssh.run("ssh", [cmd], timeout=REMOTE_TIMEOUT, pin=pin)
    except BaseException:
        return False
    return done.returncode == 0 and _last_line(done.stdout) == "CLEANED"


def cmd_status(pin: dict, out, _err) -> int:
    _, expected = _local_plugin_bytes()
    remote_sha = probe_file(pin, PLUGIN_REL)
    wp = probe_wp(pin)
    if remote_sha is None:
        plugin_state = "absent"
    elif remote_sha == expected:
        plugin_state = "current"
    else:
        plugin_state = "differs"
    print(f"plugin: {plugin_state}", file=out)
    print(f"option: {wp['option']}", file=out)
    return 0


def cmd_install(pin: dict, yes: bool, out, err) -> int:
    if not yes:
        _say(err, f"refused: pass --yes to install {PLUGIN_NAME} into {MU_REL}/ on {pin['url']}")
        return 2
    raw, expected = _local_plugin_bytes()
    check_supported_layout(pin, allow_bootstrap_fallback=True)
    wp_path = _wp_path(pin)
    tmp_name = f".conclave-ticket-login.{secrets.token_hex(8)}.tmp"
    tmp_rel = f"{MU_REL}/{tmp_name}"
    qtmp = shlex.quote(tmp_rel)
    qtarget = shlex.quote(PLUGIN_REL)
    qdir = shlex.quote(MU_REL)
    b64 = base64.b64encode(raw).decode("ascii") + "\n"
    stage_cmd = (
        f"cd {wp_path} || exit 20\n"
        f"if [ -e {qdir} ] && [ ! -d {qdir} ]; then echo 'ERR:not-dir'; exit 21; fi\n"
        f"if [ ! -d {qdir} ]; then mkdir -p {qdir} || exit 21; fi\n"
        f"chmod 0755 {qdir} || exit 21\n"
        f"if [ -d {qtarget} ]; then echo 'ERR:target-dir'; exit 22; fi\n"
        f"(umask 0022 && tr -d '\\r\\n' | base64 -d > {qtmp} && chmod 0644 {qtmp}) || {{ rm -f {qtmp}; exit 23; }}\n"
        "echo STAGED\n"
    )
    try:
        staged = site_ssh.run("ssh", [stage_cmd], input=b64, timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        _say(err, f"interrupted during staging ({note}); run status to confirm site state")
        return 130
    except Exception:
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        raise Refusal(f"failed to upload staging file ({note}); existing plugin untouched; run status to confirm site state", 1) from None
    if staged.returncode != 0 or _last_line(staged.stdout) != "STAGED":
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        raise Refusal(f"failed to stage {PLUGIN_NAME} ({note}); existing plugin untouched; run status to confirm site state", 1)

    try:
        staged_sha = probe_file(pin, tmp_rel)
    except KeyboardInterrupt:
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        _say(err, f"interrupted while verifying staging file ({note}); run status to confirm site state")
        return 130
    except Refusal:
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        raise Refusal(f"could not verify staged upload digest ({note}); existing plugin untouched; run status to confirm site state", 1) from None
    if staged_sha != expected:
        _cleanup_temp(pin, tmp_rel)
        raise Refusal("staged upload digest did not match the kit copy; existing plugin untouched", 1)

    publish_cmd = (
        f"cd {wp_path} || exit 20\n"
        f"if [ -d {qtarget} ]; then echo 'ERR:target-dir'; rm -f {qtmp}; exit 22; fi\n"
        f"mv -f {qtmp} {qtarget} && echo PUBLISHED\n"
    )
    try:
        published = site_ssh.run("ssh", [publish_cmd], timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        _say(err, f"interrupted at publication ({note}); run status to confirm site state")
        return 130
    except Exception:
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        raise Refusal(f"publication reply was lost ({note}); run status to confirm site state", 1) from None
    if published.returncode != 0 or _last_line(published.stdout) != "PUBLISHED":
        cleaned = _cleanup_temp(pin, tmp_rel)
        note = "staging file removed" if cleaned else "staging file cleanup could not be confirmed"
        raise Refusal(f"failed to publish {PLUGIN_NAME} ({note}); run status to confirm site state", 1)

    try:
        final_sha = probe_file(pin, PLUGIN_REL)
    except KeyboardInterrupt:
        _say(err, "interrupted after publication; run status to confirm site state")
        return 130
    except Refusal:
        raise Refusal("plugin was published, but final read-back failed; run status to confirm site state", 1) from None
    if final_sha != expected:
        raise Refusal("installed plugin read-back did not match the kit copy; run status to confirm site state", 1)
    print("plugin: current", file=out)
    return 0


def cmd_remove(pin: dict, yes: bool, out, err) -> int:
    if not yes:
        _say(err, f"refused: pass --yes to remove {PLUGIN_NAME} and option {OPTION} from {pin['url']}")
        return 2
    check_supported_layout(pin, allow_bootstrap_fallback=True)
    wp_path = _wp_path(pin)
    qtarget = shlex.quote(PLUGIN_REL)
    del_file_cmd = (
        f"cd {wp_path} || exit 20\n"
        f"if [ -d {qtarget} ]; then echo 'ERR:target-dir'; exit 22; fi\n"
        f"rm -f {qtarget} && echo DELETED\n"
    )
    try:
        file_done = site_ssh.run("ssh", [del_file_cmd], timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        _say(err, "interrupted while removing plugin file; run remove --yes again or status to confirm")
        return 130
    except Exception:
        raise Refusal("could not remove the remote plugin file", 1) from None
    if file_done.returncode != 0 or _last_line(file_done.stdout) != "DELETED":
        raise Refusal("could not remove the remote plugin file", 1)

    try:
        opt_done = site_ssh.wp([f"--url={pin['url']}", "eval", WP_DELETE_OPTION], timeout=REMOTE_TIMEOUT, pin=pin)
    except KeyboardInterrupt:
        _say(err, "interrupted after removing plugin file; run remove --yes again to finish option cleanup")
        return 130
    except Exception:
        raise Refusal("could not remove the ticket option from WordPress", 1) from None
    if opt_done.returncode != 0 or _last_line(opt_done.stdout) != "CONCLAVE_DEL:ok":
        raise Refusal("could not remove the ticket option from WordPress", 1)

    try:
        file_after = probe_file(pin, PLUGIN_REL)
        wp_after = probe_wp(pin)
    except KeyboardInterrupt:
        _say(err, "interrupted while confirming removal; run status or remove --yes to confirm")
        return 130
    if file_after is not None or wp_after["option"] != "absent":
        raise Refusal("removal could not be confirmed: plugin or ticket option is still present", 1)
    print("plugin: absent", file=out)
    print("option: absent", file=out)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket-login.py",
        description="Install, inspect and remove the Conclave ticket login MU-plugin on the pinned site.",
        allow_abbrev=False,
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show plugin state (absent, current, differs) and option presence", allow_abbrev=False)
    p_install = sub.add_parser("install", help="stage, verify, publish and read back the MU-plugin", allow_abbrev=False)
    p_install.add_argument("--yes", action="store_true", help="confirm writing the MU-plugin on the pinned site")
    p_remove = sub.add_parser("remove", help="delete the MU-plugin and ticket option and confirm both absent", allow_abbrev=False)
    p_remove.add_argument("--yes", action="store_true", help="confirm deleting the MU-plugin and option on the site")
    return parser


def main(argv=None, out=None, err=None) -> int:
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if not args.command:
        parser.print_usage(err)
        return 2
    try:
        pin = _pin()
        if args.command == "status":
            return cmd_status(pin, out, err)
        if args.command == "install":
            return cmd_install(pin, args.yes, out, err)
        if args.command == "remove":
            return cmd_remove(pin, args.yes, out, err)
        return 2
    except Refusal as error:
        _say(err, str(error))
        return error.code
    except KeyboardInterrupt:
        _say(err, "interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
