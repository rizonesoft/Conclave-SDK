import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('drift', Path(__file__).with_name('session_drift_check.py'))
drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)


class DriftTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('R:/scratch' if os.name == 'nt' else '/mnt/r/scratch')
        self.tmp = tempfile.TemporaryDirectory(dir=scratch if scratch.is_dir() else None)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home'
        self.sdk = self.base / 'sdk'
        self.root = self.sdk / 'plugins/codex'
        self.plugin = self.root / 'sample'
        self.cache = self.home / '.codex/plugins/cache/rizonetech/sample/1'
        self.write(self.root / '.agents/plugins/marketplace.json', json.dumps({'plugins': [{'name': 'sample'}]}))
        self.write(self.plugin / 'package.json', '{"scripts":{"build":"build"}}')
        self.write(self.plugin / 'src/main.js', 'source')
        self.write(self.plugin / 'dist/server.mjs', 'bundle')
        self.write(self.cache / 'dist/server.mjs', 'bundle')
        self.write(self.plugin / 'mcp.json', '{}')
        self.write(self.cache / 'mcp.json', '{}')
        self.config(self.root.as_posix())

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def config(self, source):
        self.write(self.home / '.codex/config.toml', '[marketplaces.rizonetech]\nsource = ' + json.dumps(source)
                   + '\n[plugins."sample@rizonetech"]\nenabled = true\n')

    def check(self):
        return drift.plugin_drift(self.home, self.sdk, time.monotonic() + 3)

    def test_clean(self):
        self.assertEqual(self.check(), [])

    def test_wrong_marketplace(self):
        self.config('R:/Bin/codex')
        self.assertIn('marketplace', self.check()[0])

    def test_relative_or_empty_marketplace_is_drift(self):
        for source in ('', '.'):
            self.config(source)
            with patch('os.getcwd', return_value=str(self.root)):
                self.assertIn('marketplace', self.check()[0])

    def test_extra_cached_manifest(self):
        self.write(self.cache / '.mcp.json', '{}')
        self.assertIn('manifest', self.check()[0])

    def test_missing_cache(self):
        (self.cache / 'dist/server.mjs').unlink()
        self.assertIn('cached bundles', self.check()[0])

    def test_changed_cache(self):
        self.write(self.cache / 'dist/server.mjs', 'old')
        self.assertIn('cached bundles', self.check()[0])

    def test_stale_source(self):
        os.utime(self.plugin / 'src/main.js', (time.time() + 10,) * 2)
        self.assertIn('older than inputs', self.check()[0])

    def test_source_launcher_cache(self):
        self.write(self.plugin / 'package.json', '{}')
        (self.plugin / 'dist/server.mjs').unlink()
        (self.cache / 'dist/server.mjs').unlink()
        self.assertIn('cached source', self.check()[0])
        self.write(self.cache / 'src/main.js', 'source')
        self.assertEqual(self.check(), [])
        self.write(self.cache / 'src/removed.js', 'stale')
        self.assertIn('cached source', self.check()[0])

    def test_scripts_are_not_source_inputs(self):
        self.write(self.plugin / 'scripts/test.js', 'test')
        self.write(self.cache / 'scripts/test.js', 'test')
        os.utime(self.plugin / 'scripts/test.js', (time.time() + 10,) * 2)
        self.assertEqual(self.check(), [])

    def test_bundled_plugin_cached_scripts(self):
        # A bundled plugin runs its launcher and credential helper from scripts/, so a stale cached
        # copy is drift (found 2026-11-16: a fixed outlook-graph helper passed while the cache was old).
        self.write(self.plugin / 'scripts/launch.mjs', 'launcher')
        self.assertIn('cached source', self.check()[0])
        self.write(self.cache / 'scripts/launch.mjs', 'old launcher')
        self.assertIn('cached source', self.check()[0])
        self.write(self.cache / 'scripts/launch.mjs', 'launcher')
        self.assertEqual(self.check(), [])

    def test_manifest(self):
        self.write(self.cache / 'mcp.json', '{"old":true}')
        self.assertIn('manifest', self.check()[0])

    def test_once_per_session(self):
        folder = self.base / 'markers'
        self.assertTrue(drift.first_prompt('a/../b', folder))
        self.assertFalse(drift.first_prompt('a/../b', folder))
        self.assertTrue(drift.first_prompt('a_.._b', folder))
        self.assertFalse(drift.first_prompt('', folder))

    def test_deadline(self):
        start = time.monotonic()
        result = drift.bounded_check(lambda **kw: time.sleep(.1), budget=.01)
        self.assertLess(time.monotonic() - start, .08)
        self.assertIn('budget', result[0])

    def test_no_exception_secrets(self):
        def fail(**kw):
            raise ValueError('SECRET')
        self.assertNotIn('SECRET', str(drift.bounded_check(fail)))

    def test_silent_when_clean(self):
        with patch.object(drift, 'first_prompt', return_value=True), patch.object(drift, 'bounded_check', return_value=[]), \
                patch('sys.stdin', io.StringIO('{"session_id":"test"}')), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(drift.main(), 0)
            self.assertEqual(output.getvalue(), '')

    def test_deployment_uses_real_check(self):
        self.assertIn('deployment differs', drift.deploy_drift(self.home, drift.SDK)[0])


if __name__ == '__main__':
    unittest.main()
