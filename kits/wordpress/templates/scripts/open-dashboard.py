#!/usr/bin/env python3
"""Open the pinned WordPress site's dashboard, logged in, through a one-use ticket (D07 T02 section 2).

Installed by the Conclave-SDK WordPress kit. It makes a token of 64 lower-case hex characters and its SHA-256 digest,
stores only the digest on the site (one option, 60 seconds, the one WordPress user the pin names) through the pinned
SSH connection, and opens `<site url>/?conclave_ticket=<token>`, which the ticket login plugin
(`tools/ticket-login/conclave-ticket-login.php`) redeems once. The token never reaches an argument, a file other than
the browser's private redirect page, the output or a log. When the browser cannot be started the ticket is removed
again; `--check` stores a ticket, removes it again and opens nothing.

It runs in WSL or on Linux: the pinned SSH hands its password to `sshpass` on a private pipe, which native Windows
has not, so there it refuses before it makes a ticket.

    python3 scripts/open-dashboard.py           open the dashboard in the browser, logged in
    python3 scripts/open-dashboard.py --check   prove the site stores and removes a ticket; open nothing
"""
import argparse
import errno
import hashlib
import html
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import site_ssh
import wp_site

QUERY = "conclave_ticket"
OPTION = "conclave_login_ticket"
LIFETIME = 60
HEX64 = re.compile(r"[0-9a-f]{64}")
REMOTE_TIMEOUT = 90
CHILD_TIMEOUT = 60
LAUNCH_CHECK = 0.3
PAGES = Path.home() / ".cache" / "conclave-dashboard"

# Both run through `wp eval` on the site with the digest on standard input. STORE writes the ticket only where the
# ticket login plugin is loaded, with an expiry on the site's own clock (the plugin judges it by the same clock), and
# echoes `stored` only when the option reads back as written. DROP removes the ticket only when it is the one this
# run stored, by its exact row, as the plugin's redemption does: another run's newer ticket is left alone.
STORE = """if ( ! defined( 'CONCLAVE_TICKET_LOADED' ) ) { echo 'no plugin'; return; }
$h = trim( (string) fgets( STDIN ) );
if ( 1 !== preg_match( '/^[0-9a-f]{64}$/', $h ) ) { echo 'bad digest'; return; }
$t = array( 'hash' => $h, 'expires' => time() + %(lifetime)d, 'user' => %(user)d );
update_option( '%(option)s', $t, false );
wp_cache_delete( '%(option)s', 'options' );
$r = get_option( '%(option)s' );
echo ( is_array( $r ) && $r === $t ) ? 'stored' : 'not stored';"""

DROP = """$h = trim( (string) fgets( STDIN ) );
if ( 1 !== preg_match( '/^[0-9a-f]{64}$/', $h ) ) { echo 'bad digest'; return; }
global $wpdb;
$raw = $wpdb->get_var( $wpdb->prepare( "SELECT option_value FROM {$wpdb->options} WHERE option_name = %%s", '%(option)s' ) );
if ( null === $raw && '' !== (string) $wpdb->last_error ) { echo 'failed'; return; }
if ( ! is_string( $raw ) ) { echo 'absent'; return; }
$t = maybe_unserialize( $raw );
if ( ! is_array( $t ) || ! isset( $t['hash'] ) || ! is_string( $t['hash'] ) || ! hash_equals( $t['hash'], $h ) ) { echo 'not ours'; return; }
// WORKAROUND: the Options API has no compare-and-delete, so the row is deleted by its exact value, as the plugin does.
$n = $wpdb->query( $wpdb->prepare( "DELETE FROM {$wpdb->options} WHERE option_name = %%s AND option_value = %%s", '%(option)s', $raw ) );
wp_cache_delete( '%(option)s', 'options' );
echo ( 1 === $n ) ? 'dropped' : ( 0 === $n ? 'gone' : 'failed' );"""

# What DROP may answer when the ticket this run stored is no longer on the site.
REMOVED = {"dropped", "absent", "gone", "not ours"}

# PowerShell reads the private redirect HTML from its standard input, writes it atomically into
# %LOCALAPPDATA%\conclave-dashboard, prunes stale pages, and starts only the registered Windows HTTPS browser on the
# local file URI (no .html fallback, no ticket URL in PowerShell or browser arguments), propagating immediate exit.
POWERSHELL_OPEN = (
    "$ErrorActionPreference = 'Stop'; "
    "$h = [Console]::In.ReadToEnd(); if (-not $h -or -not $env:LOCALAPPDATA) { exit 1 }; "
    "$d = Join-Path $env:LOCALAPPDATA 'conclave-dashboard'; "
    "New-Item -ItemType Directory -Force -Path $d | Out-Null; "
    "$cut = [DateTime]::UtcNow.AddSeconds(-%(lifetime)d); "
    "Get-ChildItem -LiteralPath $d -File -ErrorAction Ignore "
    "| Where-Object { ($_.Name -like 'open-*.html' -or $_.Name -like '.open-*.tmp') -and $_.LastWriteTimeUtc -lt $cut } "
    "| Remove-Item -Force -ErrorAction Ignore; "
    "$id = [Guid]::NewGuid().ToString('N'); "
    "$tmp = Join-Path $d ('.open-' + $id + '.tmp'); "
    "$p = Join-Path $d ('open-' + $id + '.html'); "
    "try { [IO.File]::WriteAllText($tmp, $h, [Text.UTF8Encoding]::new($false)); [IO.File]::Move($tmp, $p) } "
    "catch { Remove-Item -LiteralPath $tmp -Force -ErrorAction Ignore; exit 1 }; "
    "try { "
    "function _RegVal($rp, $rn) { (Get-ItemProperty -LiteralPath $rp -ErrorAction Ignore).$rn }; "
    "$prog = _RegVal 'HKCU:\\Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\https\\UserChoice' 'ProgId'; "
    "if ($prog) { $prog = \"$prog\".Trim() }; "
    "$cmd = if ($prog) { if ($prog -match '[\\\\/]') { $null } else { _RegVal ('Registry::HKEY_CLASSES_ROOT\\' + $prog + '\\shell\\open\\command') '(default)' } } "
    "else { _RegVal 'Registry::HKEY_CLASSES_ROOT\\https\\shell\\open\\command' '(default)' }; "
    "if (-not $cmd) { throw 'no command' }; "
    "$cmd = $cmd.Trim(); "
    "if ($cmd.StartsWith('\"')) { $q = $cmd.IndexOf('\"', 1); if ($q -lt 2) { throw 'bad command' }; "
    "$exe = $cmd.Substring(1, $q - 1); $rest = $cmd.Substring($q + 1).Trim() } "
    "else { $sp = $cmd.IndexOf(' '); if ($sp -lt 0) { $exe = $cmd; $rest = '' } "
    "else { $exe = $cmd.Substring(0, $sp); $rest = $cmd.Substring($sp + 1).Trim() } }; "
    "$uri = ([Uri]$p).AbsoluteUri; "
    "$bargs = if ($rest -like '*%%1*') { $rest.Replace('%%1', $uri) } "
    "else { ($rest + ' \"' + $uri + '\"').Trim() }; "
    "$psi = [Diagnostics.ProcessStartInfo]::new($exe, $bargs); $psi.UseShellExecute = $false; "
    "$proc = [Diagnostics.Process]::Start($psi); if (-not $proc) { throw 'no process' }; "
    "if ($proc.WaitForExit(300) -and $proc.ExitCode -ne 0) { throw 'browser failed' } "
    "} catch { Remove-Item -LiteralPath $p -Force -ErrorAction Ignore; exit 1 }"
)

WINDOWS = ("the pinned SSH hands its password to sshpass, which native Windows has not: run "
           "python3 scripts/open-dashboard.py from WSL or Linux")


def native_windows():
    """True on Windows outside WSL, where the pinned SSH cannot run."""
    return os.name == "nt"


class Refusal(Exception):
    """A failure the opener explains in a sentence of its own; nothing else's text is ever printed."""

    def __init__(self, message, code=1, landed=True):
        super().__init__(message)
        self.code = code
        self.landed = landed   # False when nothing can have been written to the site


def ticket():
    """A fresh token of 64 lower-case hex characters and its SHA-256 hex digest."""
    token = secrets.token_hex(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def link(site_url, token):
    """`<site url>/?conclave_ticket=<token>`, for a site URL the pin accepts and a token of the right shape only."""
    if not isinstance(site_url, str) or not wp_site.URL.fullmatch(site_url) \
            or not isinstance(token, str) or not HEX64.fullmatch(token):
        raise ValueError("refused to build a login link")
    return f"{site_url}/?{QUERY}={token}"


def pinned_user(pin):
    """The one WordPress user every `basic` entry under `mcp` names; none, an entry naming none, or two is a refusal."""
    helper = getattr(wp_site, "pinned_user", None)
    if helper is not None:
        try:
            return helper(pin)
        except ValueError as error:
            raise Refusal(str(error), 2) from None
    named = [entry.get("wordpress_user_id") for entry in (pin.get("mcp") or {}).values()
             if isinstance(entry, dict) and entry.get("scheme") == "basic"]
    if not named:
        raise Refusal("no basic entry under mcp in .conclave/wordpress-site.json names a wordpress_user_id", 2)
    if any(user is None for user in named):
        raise Refusal("a basic entry under mcp in .conclave/wordpress-site.json names no wordpress_user_id", 2)
    if any(isinstance(user, bool) or not isinstance(user, int) or user < 1 or user > (1 << 63) - 1 for user in named):
        raise Refusal("a wordpress_user_id in .conclave/wordpress-site.json is not a user", 2)
    if len(set(named)) != 1:
        raise Refusal("the basic entries under mcp in .conclave/wordpress-site.json name different users", 2)
    return named[0]


def _remote(pin, program, digest):
    """Run one of the two programs on the site with the digest on its standard input; its trimmed answer, or None
    when the connection did not finish cleanly."""
    # --url: on a multisite every site shares ssh.wp_path, and WP-CLI acts on the main site unless told which. It goes
    # before the command: Pressable's wp refuses a global flag after `eval <code>` ("unknown --url parameter").
    done = site_ssh.wp(["--url=" + pin["url"], "eval", program], input=digest + "\n", timeout=REMOTE_TIMEOUT, pin=pin)
    return (done.stdout or "").strip() if done.returncode == 0 else None


def store(pin, digest, user_id):
    """Store the ticket on the site; return only once the site read it back as written."""
    if not isinstance(digest, str) or not HEX64.fullmatch(digest) \
            or isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise Refusal("refused to store a malformed ticket")
    said = _remote(pin, STORE % {"lifetime": LIFETIME, "user": user_id, "option": OPTION}, digest)
    if said == "stored":
        return
    if said == "no plugin":
        raise Refusal("the ticket login plugin is not active on the site: python3 scripts/ticket-login.py install "
                      "--yes puts it on the pinned site", landed=False)
    raise Refusal("the site did not confirm that it stored the ticket")


def drop(pin, digest):
    """Remove this run's ticket from the site, and no other; the site's answer when it is no longer there."""
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        raise Refusal("refused to remove a malformed ticket")
    said = _remote(pin, DROP % {"option": OPTION}, digest)
    if said in REMOVED:
        return said
    raise Refusal("the site did not confirm that it removed the ticket")


def _redirect_html(url):
    """The private redirect page carrying `url` without exposing it in any process argument."""
    target = html.escape(url, quote=True)
    return ("<!doctype html>\n<meta charset=\"utf-8\">\n<meta name=\"referrer\" content=\"no-referrer\">\n"
            f"<meta http-equiv=\"refresh\" content=\"0;url={target}\">\n<title>Opening the dashboard</title>\n"
            f"<script>location.replace({json.dumps(url)});</script>\n")


def _page(url):
    """A redirect page of this launch's own, in a folder only this user reads; the pages of earlier launches older
    than the ticket's lifetime (dead tickets) are removed."""
    try:
        PAGES.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(PAGES, 0o700)
        for pattern in ("open-*.html", ".open-*.tmp"):
            for old in PAGES.glob(pattern):
                try:
                    if time.time() - old.stat().st_mtime > LIFETIME:
                        old.unlink()
                except OSError:
                    pass   # a stale file that cannot go holds a dead ticket only; the next launch tries again
        text = _redirect_html(url)
        fd, temporary = tempfile.mkstemp(prefix=".open-", suffix=".tmp", dir=PAGES)   # mode 0600
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            page = PAGES / ("open-" + Path(temporary).name[len(".open-"):-len(".tmp")] + ".html")
            os.replace(temporary, page)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError:
        raise Refusal(f"the folder {PAGES} cannot be written, so the browser cannot be handed the link") from None
    return page


DESKTOP_ID = re.compile(r"[^\x00-\x1f\x7f-\x9f/\\]+\.desktop")
ANY_PERCENT = re.compile(r"%(.)?")
LOCALE_RE = re.compile(r"^([A-Za-z0-9-]+)(?:_([A-Za-z0-9-]+))?(?:\.[^@]*)?(?:@(.+))?$")
DESKTOP_UNESCAPE = re.compile(r"\\([sntr\\])")
DESKTOP_ESCAPES = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}


def _unescape_desktop(value):
    """Unescape desktop-entry string escapes (\\s, \\n, \\t, \\r, \\\\)."""
    return DESKTOP_UNESCAPE.sub(lambda m: DESKTOP_ESCAPES[m.group(1)], value)


def _split_desktop_exec(command):
    """Tokenize a Desktop Entry `Exec=` value after general string unescaping (`_unescape_desktop`)."""
    text = _unescape_desktop(command)
    words, current, in_word, quoted = [], [], False, False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if quoted:
            if ch == '"':
                quoted = False
            elif ch == "\\" and i + 1 < n and text[i + 1] in ('"', "`", "$", "\\"):
                current.append(text[i + 1])
                i += 1
            else:
                current.append(ch)
        else:
            if ch in (" ", "\t"):
                if in_word:
                    words.append("".join(current))
                    current, in_word = [], False
            elif ch == '"':
                quoted = True
                in_word = True
            else:
                current.append(ch)
                in_word = True
        i += 1
    if quoted:
        raise ValueError("unclosed quote")
    if in_word:
        words.append("".join(current))
    return words


MISS_ERRNOS = {errno.ENOENT, errno.ENOTDIR, errno.ENAMETOOLONG}


def _is_file_or_miss(path):
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError as error:
        if error.errno in MISS_ERRNOS:
            return False
        raise


def _is_dir_or_miss(path):
    try:
        return stat.S_ISDIR(os.stat(path).st_mode)
    except OSError as error:
        if error.errno in MISS_ERRNOS:
            return False
        raise


def _find_in_apps(directory, remaining):
    """Find `remaining` inside `directory` (flat first, then hyphen-to-slash subdirectories), never `.` or `..`."""
    if not remaining or remaining in (".", "..") or "/" in remaining or "\\" in remaining:
        return None
    direct = directory / remaining
    if _is_file_or_miss(direct):
        return direct
    pos = remaining.find("-")
    while pos != -1:
        head, tail = remaining[:pos], remaining[pos + 1:]
        if head and head not in (".", "..") and "/" not in head and "\\" not in head:
            sub = directory / head
            if _is_dir_or_miss(sub):
                found = _find_in_apps(sub, tail)
                if found is not None:
                    return found
        pos = remaining.find("-", pos + 1)
    return None


def _find_desktop_entry(folders, entry):
    """Search each absolute XDG data root's `applications/` in order, exhausting flat and nested matches per root."""
    try:
        for folder in folders:
            if not folder or not Path(folder).is_absolute():
                continue
            apps = Path(folder) / "applications"
            if _is_dir_or_miss(apps):
                found = _find_in_apps(apps, entry)
                if found is not None:
                    return found
    except OSError:
        raise Refusal("the browser's desktop entry could not be read") from None
    return None


def _parse_locale(text):
    """Parse a POSIX/desktop-entry locale `lang[_COUNTRY][.ENCODING][@MODIFIER]` ignoring ENCODING."""
    match = LOCALE_RE.match(text.strip())
    return match.groups() if match else None


def _locale_key(text):
    """Canonical desktop-entry locale key with any `.ENCODING` stripped, or None if invalid."""
    parsed = _parse_locale(text)
    if not parsed:
        return None
    lang, country, modifier = parsed
    key = lang
    if country:
        key += "_" + country
    if modifier:
        key += "@" + modifier
    return key


def _localized(values):
    """Pick the desktop-entry value matching the active locale (LC_ALL, LC_MESSAGES, LANG), ignoring encodings."""
    raw = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    if raw and raw not in ("C", "POSIX") and not raw.startswith(("C.", "POSIX.")):
        parsed = _parse_locale(raw)
        if parsed:
            lang, country, modifier = parsed
            candidates = []
            if country and modifier:
                candidates.append(f"{lang}_{country}@{modifier}")
            if country:
                candidates.append(f"{lang}_{country}")
            if modifier:
                candidates.append(f"{lang}@{modifier}")
            candidates.append(lang)
            for key in candidates:
                if key in values:
                    return values[key]
    return values.get("", "")


def _parse_desktop_entry(found):
    """Read `Exec`, localized `Name` and localized `Icon` from `[Desktop Entry]`, normalizing locale keys."""
    command, names, icons, group = None, {}, {}, None
    try:
        raw_lines = found.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        raise Refusal("the browser's desktop entry could not be read") from None
    for line in raw_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            group = line[1:-1]
        elif group == "Desktop Entry" and "=" in line:
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key == "Exec" and command is None:
                command = val
            elif key == "Name":
                names.setdefault("", _unescape_desktop(val))
            elif key.startswith("Name[") and key.endswith("]"):
                loc = _locale_key(key[5:-1])
                if loc is not None:
                    names.setdefault(loc, _unescape_desktop(val))
            elif key == "Icon":
                icons.setdefault("", _unescape_desktop(val))
            elif key.startswith("Icon[") and key.endswith("]"):
                loc = _locale_key(key[5:-1])
                if loc is not None:
                    icons.setdefault(loc, _unescape_desktop(val))
    return command, _localized(names), _localized(icons)


def _https_browser(page):
    """The command line of the desktop entry that opens https links, given the redirect page: `xdg-open` on an
    HTML file would pick the text/html handler, which can be an editor showing the page's source (round 1)."""
    query = shutil.which("xdg-mime")
    if not query:
        raise Refusal("there is no xdg-mime to find the browser that opens https links")
    done = subprocess.run([query, "query", "default", "x-scheme-handler/https"], capture_output=True, text=True,
                          timeout=CHILD_TIMEOUT)
    entry = (done.stdout or "").rstrip("\r\n")
    if done.returncode != 0 or not DESKTOP_ID.fullmatch(entry):
        raise Refusal("no browser is set to open https links (xdg-mime query default x-scheme-handler/https)")
    raw_home = os.environ.get("XDG_DATA_HOME") or ""
    if raw_home and Path(raw_home).is_absolute():
        home = raw_home
    else:
        try:
            home = str(Path.home() / ".local" / "share")
        except RuntimeError:
            home = ""
    raw_dirs = [d for d in (os.environ.get("XDG_DATA_DIRS") or "").split(os.pathsep) if d and Path(d).is_absolute()]
    folders = [home, *(raw_dirs or ["/usr/local/share", "/usr/share"])]
    found = _find_desktop_entry(folders, entry)
    if found is None:
        raise Refusal("the browser's desktop entry is in no applications folder")
    command, name, icon = _parse_desktop_entry(found)
    try:
        words = _split_desktop_exec(command or "")
    except ValueError:
        words = []
    if not words:
        raise Refusal("the browser's desktop entry has no command to run")
    argv, given = [], False

    def _expand(match):
        nonlocal given
        code = match.group(1)
        if code == "%":
            return "%"
        if code == "u":
            if given:
                raise Refusal("the browser's desktop entry has more than one target field code")
            given = True
            return page.as_uri()
        if code == "f":
            if given:
                raise Refusal("the browser's desktop entry has more than one target field code")
            given = True
            return str(page)
        if code == "c":
            return name
        if code == "k":
            return str(found)
        if code in ("d", "D", "n", "N", "v", "m"):
            return ""   # deprecated field codes are removed per Desktop Entry Spec
        raise Refusal("the browser's desktop entry has an unsupported field code")

    for word in words:
        if word == "%i":
            if icon:
                argv.extend(["--icon", icon])
        elif word == "%U":
            if given:
                raise Refusal("the browser's desktop entry has more than one target field code")
            argv.append(page.as_uri())
            given = True
        elif word == "%F":
            if given:
                raise Refusal("the browser's desktop entry has more than one target field code")
            argv.append(str(page))
            given = True
        elif word in ("%d", "%D", "%n", "%N", "%v", "%m"):
            continue
        else:
            argv.append(ANY_PERCENT.sub(_expand, word))
    return argv if given else [*argv, str(page)]


def open_browser(url):
    """Start the browser on the link: from WSL through Windows PowerShell, the link on its standard input; on Linux
    through the desktop entry that opens https links, the link in a private redirect page. The link is in no
    argument and no message."""
    if os.environ.get("WSL_DISTRO_NAME"):
        shell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
        if not shell:
            raise Refusal("there is no pwsh.exe or powershell.exe to open the browser from WSL")
        if not os.path.isdir("/mnt/c"):
            raise Refusal("there is no Windows drive at /mnt/c to start PowerShell from")
        done = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command",
                               POWERSHELL_OPEN % {"lifetime": LIFETIME}],
                              input=_redirect_html(url), capture_output=True, text=True, cwd="/mnt/c",
                              timeout=CHILD_TIMEOUT)
        if done.returncode != 0:
            raise Refusal("PowerShell could not open the browser")
        return
    page = _page(url)
    argv = _https_browser(page)
    try:
        # Not waited for to completion: a browser started fresh runs until closed, but an immediate non-zero exit
        # (e.g. no graphical display) is caught within LAUNCH_CHECK so the ticket is revoked.
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError:
        raise Refusal("the browser that opens https links could not be started") from None
    try:
        code = proc.wait(timeout=LAUNCH_CHECK)
    except subprocess.TimeoutExpired:
        return
    if code != 0:
        raise Refusal("the browser that opens https links could not be started")


def _say(stream, text):
    print("open-dashboard: " + text, file=stream)


def _failed(error):
    """The one line a failure prints: the opener's own sentence, or the exception's type and nothing of its text."""
    return str(error) if isinstance(error, Refusal) else f"{type(error).__name__}: unexpected failure"


def _clean_up(pin, digest, err):
    """After a failure once a ticket may be on the site: remove it, and say whether that was confirmed."""
    try:
        removed = drop(pin, digest)
    except Exception:   # any failure: reported by a fixed sentence, never its text, which may hold the token
        _say(err, f"the ticket could not be removed from the site; it expires within {LIFETIME} seconds")
        return
    if removed == "dropped":
        _say(err, "the ticket was removed from the site")
    else:
        _say(err, "the ticket was no longer on the site")


def _pin():
    """The pin and the pinned user, refused before any ticket exists (exit 2) when they cannot carry a login."""
    try:
        pin = wp_site.load()
        if not wp_site.ssh_enabled(pin):
            raise Refusal("the site pin has no SSH (ssh.ssh_host is null), so no ticket can be stored", 2)
        missing = wp_site.unset(pin, "url", "ssh.wp_path")
        if missing:
            raise Refusal("not set in .conclave/wordpress-site.json yet: " + ", ".join(missing), 2)
    except Refusal:
        raise
    except OSError:
        raise Refusal("the site pin .conclave/wordpress-site.json cannot be read", 2) from None
    except ValueError:
        raise Refusal("the site pin .conclave/wordpress-site.json is not valid: python3 scripts/site-access.py check "
                      "says why", 2) from None
    return pin, pinned_user(pin)


def main(argv=None, out=None, err=None):
    out, err = out or sys.stdout, err or sys.stderr
    parser = argparse.ArgumentParser(prog="open-dashboard.py", description=(
        "Open the pinned WordPress site's dashboard, logged in, through a one-use ticket that works for "
        f"{LIFETIME} seconds. Run it from WSL or Linux."))
    parser.add_argument("--check", action="store_true",
                        help="store a ticket on the site, remove it again and open nothing")
    args = parser.parse_args(argv)
    try:
        if native_windows():
            raise Refusal(WINDOWS, 2)
        pin, user = _pin()
        token, digest = ticket()
        url = link(pin["url"], token)
    except Exception as error:   # every failure is reported by `_failed`, never by its own text
        _say(err, _failed(error))
        return error.code if isinstance(error, Refusal) else 1
    try:
        store(pin, digest, user)
    except KeyboardInterrupt:
        _say(err, "interrupted")
        _clean_up(pin, digest, err)   # the write may have landed
        return 130
    except Exception as error:   # every failure is reported by `_failed`, never by its own text
        _say(err, _failed(error))
        if not (isinstance(error, Refusal) and not error.landed):
            _clean_up(pin, digest, err)   # the write may have landed though its reply was lost
        return 1
    if args.check:
        try:
            removed = drop(pin, digest)
        except KeyboardInterrupt:
            _say(err, "interrupted")
            _clean_up(pin, digest, err)
            return 130
        except Exception as error:   # every failure is reported by `_failed`, never by its own text
            _say(err, _failed(error))
            _say(err, f"the ticket expires within {LIFETIME} seconds")
            return 1
        if removed != "dropped":
            _say(err, "the ticket was replaced or gone before --check could remove it")
            return 1
        _say(out, "the site stored a ticket and removed it again; nothing was opened")
        return 0
    try:
        open_browser(url)
    except KeyboardInterrupt:
        _say(err, "interrupted")
        _clean_up(pin, digest, err)
        return 130
    except Exception as error:   # every failure is reported by `_failed`, never by its own text
        _say(err, _failed(error))
        _clean_up(pin, digest, err)
        return 1
    _say(out, f"the dashboard is opening in the browser, logged in (the link works once, within {LIFETIME} seconds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
