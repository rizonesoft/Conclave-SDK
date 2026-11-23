"""`scripts/elementor-cache.py` and its must-use plugin: nothing here reaches a site.

Found 2026-11-23: after a plugin was deactivated, a page cache served HTML naming stylesheets Elementor had deleted.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]   # the project, or the kit's templates/ folder
PLUGIN = ROOT / "tools" / "elementor-cache-purge" / "conclave-elementor-cache-purge.php"
PHP = shutil.which("php")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

spec = importlib.util.spec_from_file_location("elementor_cache", ROOT / "scripts" / "elementor-cache.py")
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)

SITE = "https://example.com"
PAGE = f"<link rel='stylesheet' href='{SITE}/wp-content/uploads/elementor/css/local-7-frontend-desktop.css?ver=1&#038;x=2'>"
SHEET = f"{SITE}/wp-content/uploads/elementor/css/local-7-frontend-desktop.css?ver=1&x=2"
PIN = {"url": SITE, "ssh": {"wp_path": "~/htdocs"}}
CSS = (200, "a{}", "text/css")
LIST = f"{SITE}/?rest_route=/wp/v2/pages&per_page=100&page=%d&_fields=link"
BASH = shutil.which("bash") if os.name == "posix" else None


class CheckTests(unittest.TestCase):
    def run_check(self, answers):
        lines = []
        def fetch(url):
            answer = answers.get(url, (404, ""))
            return answer if len(answer) == 3 else (*answer, "text/html")
        code = cache.check(SITE, fetch=fetch, out=lines.append)
        return code, "\n".join(lines)

    def site(self, **over):
        answers = {SITE + "/": (200, PAGE), SHEET: CSS, LIST % 1: (200, json.dumps([{"link": f"{SITE}/about/"}])),
                   f"{SITE}/about/": (200, PAGE)}
        answers.update(over)
        return answers

    def test_every_stylesheet_answering_passes(self):
        self.assertEqual(self.run_check(self.site()), (0, "pages 2, stylesheets 1, missing 0, not proved 0"))

    def test_a_deleted_stylesheet_fails_and_names_the_page(self):
        code, text = self.run_check({**self.site(), SHEET: (404, "")})
        self.assertEqual(code, 1)
        self.assertIn(f"{SHEET} (named by {SITE}/)", text)

    def test_html_in_place_of_a_stylesheet_is_missing(self):
        self.assertEqual(self.run_check({**self.site(), SHEET: (200, "<!doctype html>", "text/html")})[0], 1)

    def test_a_stylesheet_only_a_listed_page_names_is_checked(self):
        answers = {**self.site(), SITE + "/": (200, "no styles"), SHEET: (404, "")}
        self.assertEqual(self.run_check(answers)[0], 1)

    def test_unquoted_links_count_and_commented_ones_do_not(self):
        bare = "<link rel=stylesheet href=/wp-content/uploads/elementor/css/post-9.css>"
        self.assertEqual(self.run_check({**self.site(), f"{SITE}/about/": (200, bare)})[0], 1)
        self.assertEqual(self.run_check({**self.site(), f"{SITE}/about/": (200, f"<!-- {bare} -->")})[0], 0)

    def test_a_stylesheet_is_read_before_another_page_can_rebuild_it(self):
        rendered = []
        def fetch(url):
            if url == f"{SITE}/about/":
                rendered.append(url)
            if url == SHEET:
                return CSS if rendered else (404, "", "")
            return (*self.site()[url], "text/html")
        self.assertEqual(cache.check(SITE, fetch=fetch, out=lambda text: None), 1)

    def test_only_wordpress_saying_past_the_last_page_ends_a_full_list(self):
        batch = (200, json.dumps([{"link": f"{SITE}/{n}/"} for n in range(100)]))
        base = {**self.site(), LIST % 1: batch, **{f"{SITE}/{n}/": (200, PAGE) for n in range(100)}}
        self.assertEqual(self.run_check({**base, LIST % 2: (400, "{\"code\":\"rest_post_invalid_page_number\"}")})[0], 0)
        self.assertEqual(self.run_check({**base, LIST % 2: (400, "blocked")})[0], 2)

    def test_a_root_relative_stylesheet_is_resolved(self):
        page = PAGE.replace(SITE, "")
        self.assertEqual(self.run_check({**self.site(), SITE + "/": (200, page), f"{SITE}/about/": (200, page)})[0], 0)

    def test_evidence_that_is_not_whole_is_never_a_pass(self):
        cases = {"no site": {}, "page list failed": {**self.site(), LIST % 1: (503, "")},
                 "page list not JSON": {**self.site(), LIST % 1: (200, "<html>")},
                 "page failed": {**self.site(), f"{SITE}/about/": (None, "")},
                 "stylesheet timed out": {**self.site(), SHEET: (None, "")},
                 "stylesheet throttled": {**self.site(), SHEET: (429, "")},
                 "no stylesheet": {**self.site(), SITE + "/": (200, "x"), f"{SITE}/about/": (200, "x")}}
        for name, answers in cases.items():
            with self.subTest(name):
                self.assertEqual(self.run_check(answers)[0], 2)

    def test_a_page_list_that_repeats_itself_ends_and_is_not_whole(self):
        batch = (200, json.dumps([{"link": f"{SITE}/{n}/"} for n in range(100)]))
        answers = {**self.site(), LIST % 1: batch, LIST % 2: batch, **{f"{SITE}/{n}/": (200, PAGE) for n in range(100)}}
        self.assertEqual(self.run_check(answers)[0], 2)

    def test_public_page_data_never_leads_off_the_site(self):
        asked = []
        links = json.dumps([{"link": "file:///etc/passwd"}, {"link": "https://elsewhere.example/"}, {"link": f"{SITE}/about/"}])
        answers = {**self.site(), LIST % 1: (200, links, "application/json")}
        def fetch(url):
            asked.append(url)
            answer = answers.get(url, (404, ""))
            return answer if len(answer) == 3 else (*answer, "text/html")
        cache.check(SITE, fetch=fetch, out=lambda text: None)
        self.assertTrue(all(url.startswith(SITE) for url in asked), asked)
        self.assertEqual(cache.get("file:///etc/passwd")[0], None)


class WriteTests(unittest.TestCase):
    """The production shell runs for real, in a throwaway folder that stands in for the server's home."""

    def setUp(self):
        if not BASH or not shutil.which("sha256sum"):
            self.skipTest("bash and sha256sum are needed")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name).resolve()
        (self.home / "htdocs/wp-content").mkdir(parents=True)
        self.mu = self.home / "htdocs/wp-content/mu-plugins"
        self.live = self.mu / cache.NAME
        self.facts = {"elementor": "4.4.1", "hook": True, "loaded": True, "multisite": False, "mu": str(self.mu), "home": SITE}
        self.boots = True
        self.scripts, self.wp_calls = [], []

        def run(kind, arguments, *, input=None, timeout=90, pin=None):
            self.scripts.append(arguments[0])
            return subprocess.run([BASH, "-c", arguments[0]], input=input or "", capture_output=True, text=True, timeout=30,
                                  env={**os.environ, "HOME": str(self.home)}, creationflags=NO_WINDOW)

        def wp(arguments, *, timeout=90, pin=None):
            self.wp_calls.append(" ".join(arguments))
            return SimpleNamespace(returncode=0, stdout="CONCLAVE:" + json.dumps(self.facts) if self.boots else "Fatal error")

        for name, fake in (("run", run), ("wp", wp)):
            patch = mock.patch.object(cache.site_ssh, name, fake)
            patch.start()
            self.addCleanup(patch.stop)

    def backups(self):
        return list((self.home / "conclave-backups").glob("*")) if (self.home / "conclave-backups").exists() else []

    def install(self):
        return cache.install(PIN, out=lambda text: None)

    def test_install_creates_the_folder_writes_the_exact_bytes_and_purges(self):
        self.assertEqual(self.install(), 0)
        self.assertEqual(self.live.read_bytes(), PLUGIN.read_bytes())
        self.assertEqual([path.name for path in self.mu.iterdir()], [cache.NAME])
        self.assertIn("edge-cache purge --domain --yes", self.wp_calls[-1])

    def test_install_and_remove_back_up_what_was_there(self):
        self.mu.mkdir()
        self.live.write_bytes(b"old")
        self.assertEqual(self.install(), 0)
        self.assertEqual([path.read_bytes() for path in self.backups()], [b"old"])
        self.assertEqual(cache.remove(PIN, out=lambda text: None), 0)
        self.assertFalse(self.live.exists())
        self.assertEqual(sorted(path.read_bytes() for path in self.backups()), sorted([b"old", PLUGIN.read_bytes()]))

    def test_a_cut_transfer_leaves_the_live_file_alone(self):
        self.mu.mkdir()
        self.live.write_bytes(b"old")
        with mock.patch.object(cache.base64, "b64encode", return_value=b"b2xk"), self.assertRaises(ValueError):
            self.install()
        self.assertEqual(self.live.read_bytes(), b"old")
        self.assertEqual([path.name for path in self.mu.iterdir()], [cache.NAME])

    def test_refused_with_no_write(self):
        for change in ({"elementor": None}, {"hook": False}, {"multisite": True}, {"home": "https://copy.example"}):
            with self.subTest(change=change):
                self.facts.update(change)
                with self.assertRaises(ValueError):
                    self.install()
                self.assertEqual(self.scripts, [])
                self.facts.update({"elementor": "4.4.1", "hook": True, "multisite": False, "home": SITE})

    def test_another_must_use_folder_is_never_written_or_removed(self):
        self.mu.mkdir()
        self.live.write_bytes(b"old")
        self.facts["mu"] = str(self.home / "elsewhere/wp-content/mu-plugins")
        for action in (cache.install, cache.remove):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "another folder"):
                action(PIN, out=lambda text: None)
        self.assertEqual((self.live.read_bytes(), self.backups()), (b"old", []))

    def test_a_file_that_stops_wordpress_can_be_removed(self):
        self.mu.mkdir()
        self.live.write_bytes(b"broken")
        self.boots = False
        self.assertEqual(cache.remove(PIN, out=lambda text: None), 0)
        self.assertEqual((self.live.exists(), [path.read_bytes() for path in self.backups()]), (False, [b"broken"]))

    def test_a_plugin_wordpress_does_not_load_is_not_success(self):
        self.facts["loaded"] = False
        with self.assertRaisesRegex(ValueError, "does not load"):
            self.install()

    def test_a_write_needs_yes(self):
        for command in ("install", "remove"):
            with self.subTest(command=command), mock.patch.object(cache.wp_site, "load", return_value=PIN), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cache.main([command]), 2)
        self.assertEqual(self.scripts, [])


HARNESS = r"""<?php
define('ABSPATH', '/tmp/');
$GLOBALS['hooks'] = []; $GLOBALS['purges'] = 0; $GLOBALS['doing'] = null;
function add_action($tag, $cb, $prio = 10, $args = 1) { $GLOBALS['hooks'][$tag][] = [$cb, $args]; }
function do_action($tag, ...$a) { foreach ($GLOBALS['hooks'][$tag] ?? [] as [$cb, $n]) { $cb(...array_slice($a, 0, $n)); } }
function doing_action($tag) { return $GLOBALS['doing'] === $tag; }
add_action('edge_cache_purge_domain', function () { $GLOBALS['purges']++; }, 10, 0);
require $argv[1]; require $argv[1];
"""


@unittest.skipUnless(PHP, "PHP is not installed")
class PluginTests(unittest.TestCase):
    def purges(self, body):
        done = subprocess.run([PHP, "--", str(PLUGIN)], input=f"{HARNESS}{body} echo $GLOBALS['purges'];",
                              capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW, check=True)
        return int(done.stdout)

    def test_loading_it_twice_purges_nothing(self):
        self.assertEqual(self.purges(""), 0)

    def test_clearing_every_stylesheet_purges_once(self):
        self.assertEqual(self.purges("do_action('elementor/core/files/clear_cache');"), 1)

    def test_style_path_clears(self):
        for path, doing, want in (("['local', 7]", "null", 1), ("['global', 7, 'frontend']", "null", 1),
                                  ("['global']", "null", 1), ("['local', 7, 'preview']", "null", 0),
                                  ("['global', 'preview']", "null", 0), ("['local', 9]", "'deleted_post'", 0),
                                  ("['global']", "'deleted_post'", 1)):
            with self.subTest(path=path, doing=doing):
                self.assertEqual(self.purges(
                    f"$GLOBALS['doing'] = {doing}; do_action('elementor/atomic-widgets/styles/clear', {path});"), want)

    def test_a_host_without_the_hook_is_unaffected(self):
        self.assertEqual(self.purges(
            "unset($GLOBALS['hooks']['edge_cache_purge_domain']); do_action('elementor/core/files/clear_cache');"), 0)


if __name__ == "__main__":
    unittest.main()
