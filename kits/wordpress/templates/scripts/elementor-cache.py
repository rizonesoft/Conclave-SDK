#!/usr/bin/env python3
"""Keep cached pages of an Elementor site from naming stylesheets Elementor has deleted.

Installed by the Conclave-SDK WordPress kit. Elementor deletes its generated stylesheets on a plugin change or a cache
clear, and the Pressable and WordPress.com page cache goes on serving HTML that names them, so visitors get unstyled
pages. `tools/elementor-cache-purge/conclave-elementor-cache-purge.php` closes that; this installs and checks it.

    python3 scripts/elementor-cache.py check [--url URL]   read the pages as a visitor; exit 1 on a missing stylesheet
    python3 scripts/elementor-cache.py status              Elementor, the host's purge hook and the plugin on the site
    python3 scripts/elementor-cache.py install --yes       back up, write and read back the plugin (owner approval)
    python3 scripts/elementor-cache.py remove --yes        back up and delete it

`check` reads every published page the REST API lists (plus the front page) and needs no credential, so it also works
on a site with no pin. It proves nothing for a site whose stylesheets are combined or inlined: it says so instead.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shlex
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import site_ssh  # noqa: E402
import wp_site  # noqa: E402

NAME = "conclave-elementor-cache-purge.php"
PLUGIN = ROOT / "tools" / "elementor-cache-purge" / NAME
DIR = "wp-content/mu-plugins"
REL = f"{DIR}/{NAME}"
STYLESHEET = re.compile(r"/uploads/(?:sites/\d+/)?elementor/css/")
PROBE = (
    "global $wp_filter; echo 'CONCLAVE:' . wp_json_encode( array( "
    "'home' => get_option( 'home' ), "
    "'elementor' => defined( 'ELEMENTOR_VERSION' ) ? ELEMENTOR_VERSION : null, "
    "'hook' => ! empty( $wp_filter['edge_cache_purge_domain']->callbacks ), "
    "'loaded' => defined( 'CONCLAVE_ELEMENTOR_CACHE_PURGE_LOADED' ), "
    "'multisite' => is_multisite(), "
    "'mu' => ( realpath( WPMU_PLUGIN_DIR ) ?: realpath( dirname( WPMU_PLUGIN_DIR ) ) . '/' . basename( WPMU_PLUGIN_DIR ) ) "
    ") );"
)


def get(url):
    """(status, body, media type); status is None when there was no HTTP answer, or the address is not http(s)."""
    if urlsplit(url).scheme not in ("http", "https"):
        return None, "", ""
    try:
        with urlopen(Request(url, headers={"User-Agent": "conclave-elementor-cache-check"}), timeout=30) as reply:
            return reply.status, reply.read().decode("utf-8", "replace"), reply.headers.get_content_type()
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace"), ""
    except (URLError, TimeoutError, OSError):
        return None, "", ""


class Links(HTMLParser):
    """The hrefs of a page's live stylesheet links: not comments, and quoted or not."""

    def __init__(self, body):
        super().__init__()
        self.found = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "stylesheet" in (attrs.get("rel") or "").lower().split() and STYLESHEET.search(attrs.get("href") or ""):
            self.found.append(attrs["href"])


def list_pages(url, fetch):
    """(addresses on this site, whether the list is complete)."""
    pages, number, host = [], 1, urlsplit(url).netloc
    while True:
        status, body, _ = fetch(f"{url}/?rest_route=/wp/v2/pages&per_page=100&page={number}&_fields=link")
        try:
            found = [item["link"] for item in json.loads(body)] if status == 200 else None
        except (ValueError, KeyError, TypeError):
            found = None
        # WordPress answers 400 past the last page, which a list of exactly 100 reaches.
        if found is None:
            return pages, number > 1 and status == 400 and "rest_post_invalid_page_number" in body
        # Page data is public input: only this site's own addresses are read.
        new = [link for link in found if isinstance(link, str) and urlsplit(link).netloc == host
               and urlsplit(link).scheme in ("http", "https") and link not in pages]
        if not new and found:
            return pages, False
        pages += new
        if len(found) < 100:
            return pages, True
        number += 1


def check(url, fetch=get, out=print):
    """Exit status: 0 every stylesheet answers, 1 one is missing, 2 the site could not be read whole or proves nothing."""
    url = url.rstrip("/")
    sheets, counts = set(), {"missing": 0, "unproved": 0}

    def read(page):
        status, body, _ = fetch(page)
        if status != 200:
            counts["unproved"] += 1
            out(f"{page} answered {status}")
            return False
        # Each page's stylesheets are read before the next page: rendering another page rebuilds the ones they share.
        for href in Links(body).found:
            sheet = urljoin(page, href)
            if sheet in sheets:
                continue
            sheets.add(sheet)
            status, _, media = fetch(sheet)
            if status == 200 and media == "text/css":
                continue
            kind = "unproved" if status is None or status == 429 or status >= 500 else "missing"
            counts[kind] += 1
            out(f"{kind}: {status} {media or '(no type)'} {sheet} (named by {page})")
        return True

    if not read(url + "/"):
        return 2
    listed, complete = list_pages(url, fetch)
    pages = list(dict.fromkeys([url + "/"] + listed))
    if not complete:
        counts["unproved"] += 1
        out("the page list could not be read whole")
    for page in pages[1:]:
        read(page)
    missing, unproved = counts["missing"], counts["unproved"]
    out(f"pages {len(pages)}, stylesheets {len(sheets)}, missing {missing}, not proved {unproved}")
    if missing:
        return 1
    if unproved:
        return 2
    if not sheets:
        out("no Elementor stylesheet was found: the site has none, or combines or inlines them, so this proves nothing")
        return 2
    return 0


class NoAnswer(ValueError):
    """WordPress could not be asked."""


def probe(pin):
    done = site_ssh.wp([f"--url={pin['url']}", "eval", PROBE], timeout=90, pin=pin)
    for line in (done.stdout or "").splitlines():
        if line.startswith("CONCLAVE:"):
            # PHP on some sites prints a log entry straight after the answer, on the same line.
            return json.JSONDecoder().raw_decode(line[len("CONCLAVE:"):])[0]
    raise NoAnswer("WordPress on the pinned site gave no answer")


def remote(pin, mu, script, *, input=None):
    """The last line a script prints in ssh.wp_path, run only where that folder holds the must-use folder `mu` (any
    must-use folder when `mu` is None)."""
    (wp_path,) = wp_site.require(pin, "ssh.wp_path")
    test = f'[ "$(pwd -P)/{DIR}" = {shlex.quote(mu)} ]' if mu else f"[ -d {DIR} ]"
    bound = f"cd {wp_path} && {test} || exit 20\n"
    done = site_ssh.run("ssh", [bound + script], input=input, timeout=90, pin=pin)
    if done.returncode == 20:
        raise ValueError("WordPress loads must-use plugins from another folder than ssh.wp_path holds")
    if done.returncode != 0:
        raise ValueError(f"the remote command failed (exit {done.returncode})")
    return ((done.stdout or "").strip().splitlines() or [""])[-1]


def digest(pin, mu):
    """The installed plugin's SHA-256, or None when it is absent."""
    last = remote(pin, mu, f"if [ -e {REL} ]; then sha256sum {REL}; else echo ABSENT; fi")
    return None if last == "ABSENT" else last.split()[0]


def status(pin, out=print):
    facts = probe(pin)
    found = digest(pin, facts["mu"])
    want = hashlib.sha256(PLUGIN.read_bytes()).hexdigest()
    out(f"elementor: {facts['elementor'] or 'not active'}")
    out(f"host purge hook: {'present' if facts['hook'] else 'absent'}")
    out(f"plugin: {'absent' if found is None else 'current' if found == want else 'differs'}"
        + (", loaded" if facts["loaded"] else ""))
    return 0


# Every copy keeps its own name, so two runs never share one.
BACKUP = (f"mkdir -p ~/conclave-backups && if [ -e {REL} ]; then "
          f"b=$(mktemp ~/conclave-backups/{NAME}.$(date -u +%Y%m%dT%H%M%SZ).XXXXXX) && cp -p {REL} $b; fi")


def ready(pin):
    facts = probe(pin)
    if facts["multisite"]:
        raise ValueError("a multisite installation is not supported")
    if str(facts["home"]).rstrip("/") != pin["url"].rstrip("/"):
        raise ValueError("ssh.wp_path holds another WordPress site than the pinned url")
    return facts


def install(pin, out=print):
    facts = ready(pin)
    if not facts["elementor"]:
        raise ValueError("Elementor is not active on the pinned site")
    if not facts["hook"]:
        raise ValueError("the host has no edge_cache_purge_domain hook, so the plugin would do nothing: purge by hand")
    data = PLUGIN.read_bytes()
    want = hashlib.sha256(data).hexdigest()
    # Written to a file of this run's own (not .php, so never loaded) and checked there before it takes the live name.
    remote(pin, facts["mu"], f"{BACKUP} && mkdir -p {DIR} && t=$(mktemp {DIR}/.conclave-XXXXXX) || exit 21\n"
           f"tr -d '\\r\\n' | base64 -d > $t && echo \"{want}  $t\" | sha256sum -c - >/dev/null && chmod 644 $t "
           f"&& mv -f $t {REL} || {{ rm -f $t; exit 22; }}",
           input=base64.b64encode(data).decode() + "\n")
    if digest(pin, facts["mu"]) != want:
        raise ValueError("the read-back does not match: run status")
    if not probe(pin)["loaded"]:
        raise ValueError("the plugin is on the site but WordPress does not load it")
    done = site_ssh.wp(["edge-cache", "purge", "--domain", "--yes"], timeout=90, pin=pin)
    if done.returncode != 0:
        raise ValueError("installed, but the page cache could not be purged: purge it in the host's panel")
    out("plugin: current, loaded; page cache purged")
    return 0


def remove(pin, out=print):
    try:
        mu = ready(pin)["mu"]
    except NoAnswer:
        mu = None   # WordPress does not start, perhaps because of this file: it can still be taken away
    remote(pin, mu, f"{BACKUP} && rm -f {REL}")
    if digest(pin, mu) is not None:
        raise ValueError("the plugin is still on the site")
    out("plugin: absent")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", allow_abbrev=False).add_argument("--url", help="default: the pinned site")
    commands.add_parser("status", allow_abbrev=False)
    for name in ("install", "remove"):
        commands.add_parser(name, allow_abbrev=False).add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "check" and args.url:
            return check(args.url)
        pin = wp_site.load()
        (url,) = wp_site.require(pin, "url")
        if args.command == "check":
            return check(url)
        if args.command in ("install", "remove") and not args.yes:
            raise ValueError(f"this writes to {url}: get the owner's approval, then pass --yes")
        return {"status": status, "install": install, "remove": remove}[args.command](pin)
    except (OSError, ValueError) as error:
        print(f"elementor-cache: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
