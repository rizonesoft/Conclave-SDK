import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('deploy', Path(__file__).parents[1] / 'deploy.py')
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'global'
        self.skill = self.source / 'example'
        self.skill.mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('name: example\n', encoding='utf-8')
        self.home = self.root / 'home'

    def test_preview_does_not_write(self):
        deploy.deploy('example', self.source, self.home, apply=False)
        self.assertFalse(self.home.exists())

    def test_install_update_backup_and_cache_removal(self):
        cache = self.skill / '__pycache__'
        cache.mkdir()
        (cache / 'a.pyc').write_bytes(b'cache')
        deploy.deploy('example', self.source, self.home, apply=True)
        dest = self.home / '.agents/skills/example'
        self.assertEqual((dest / 'SKILL.md').read_bytes(), (self.skill / 'SKILL.md').read_bytes())
        self.assertFalse((dest / '__pycache__').exists())
        sibling = dest.parent / 'unrelated'
        sibling.mkdir()
        (sibling / 'keep.txt').write_text('keep')
        (dest / 'obsolete.txt').write_text('old')
        (dest / '__pycache__').mkdir()
        (dest / '__pycache__/old.pyc').write_bytes(b'old')
        deploy.deploy('example', self.source, self.home, apply=True)
        self.assertFalse((dest / 'obsolete.txt').exists())
        self.assertFalse((dest / '__pycache__').exists())
        self.assertTrue((sibling / 'keep.txt').exists())
        self.assertEqual(len(list((self.home / '.codex/skill-backups').glob('*/obsolete.txt'))), 1)

    def test_rejects_non_global_names(self):
        for name in ('../project', 'global/example', r'..\project', str(self.skill), '.', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                deploy.deploy(name, self.source, self.home, apply=True)
        self.assertFalse(self.home.exists())

    def test_rejects_missing_manifest(self):
        (self.skill / 'SKILL.md').unlink()
        with self.assertRaises(ValueError):
            deploy.deploy('example', self.source, self.home, apply=True)

    def make_link(self, path, target):
        try:
            path.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'Symlink privilege unavailable: {error}')

    def test_rejects_source_link(self):
        self.make_link(self.source / 'escape', self.root)
        with self.assertRaises(ValueError):
            deploy.deploy('escape', self.source, self.home, apply=True)

    def test_rejects_nested_source_link(self):
        self.make_link(self.skill / 'external', self.root)
        with self.assertRaises(ValueError):
            deploy.deploy('example', self.source, self.home, apply=True)

    def test_rejects_destination_link(self):
        self.home.mkdir()
        self.make_link(self.home / '.agents', self.root)
        with self.assertRaises(ValueError):
            deploy.deploy('example', self.source, self.home, apply=True)


if __name__ == '__main__':
    unittest.main()
