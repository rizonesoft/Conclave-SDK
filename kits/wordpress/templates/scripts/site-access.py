#!/usr/bin/env python3
"""Reach the live WordPress site over its pinned SSH identity (.conclave/wordpress-site.json).

    python3 scripts/site-access.py check                 # prove SSH and SFTP reach the pinned site (read-only)
    python3 scripts/site-access.py ssh 'wp core version'  # one explicitly supplied SSH command
    printf 'ls\\nbye\\n' | python3 scripts/site-access.py sftp   # an SFTP batch, on stdin only

`check` runs `wp option get home` over SSH and compares it with the pinned URL, then lists the SFTP home directory. It
prints a JSON summary and exits non-zero unless both work. Credentials come from the Conclave vault through
scripts/lib/site_ssh.py and never appear in an argument or the output.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import site_ssh  # noqa: E402
import wp_site  # noqa: E402


def check(pin):
    site_id, url = wp_site.require(pin, "site_id", "url")
    home = site_ssh.wp(["option", "get", "home"], timeout=120, pin=pin)
    sftp = site_ssh.run("sftp", input="pwd\nbye\n", timeout=60, pin=pin)
    report = {
        "host": pin["host"],
        "site_id": site_id,
        "url": url,
        "ssh_ok": home.returncode == 0,
        "home_matches": home.returncode == 0 and home.stdout.strip().rstrip("/") == url,
        "sftp_ok": sftp.returncode == 0,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["home_matches"] and report["sftp_ok"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["check", "ssh", "sftp"])
    parser.add_argument("command", nargs="?", help="One quoted SSH command; SFTP batch commands come from stdin")
    args = parser.parse_args()
    pin = wp_site.load()
    if args.action == "check":
        if args.command:
            parser.error("check takes no command")
        return check(pin)
    if (args.action == "ssh") != bool(args.command):
        parser.error("ssh requires one command; sftp accepts its batch only on stdin")
    result = site_ssh.run(args.action, [args.command] if args.command else (),
                          input=sys.stdin.read() if args.action == "sftp" else None, pin=pin)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as exc:
        # The helpers raise fixed messages only; never echo vault or transport output here.
        print("site-access: " + str(exc), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print("site-access failed: " + type(exc).__name__ + "; check the Conclave SSH item and the site pin.", file=sys.stderr)
        sys.exit(1)
