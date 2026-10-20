"""The VS Code extension records the digest of the kits it bundles with its version (plan R39): a kit change ships with a
new extension version and a re-recorded digest, or this test fails."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "vscode"
RECORD = EXTENSION / "sdk-digest.json"
SCRIPT = EXTENSION / "scripts" / "record-sdk-digest.py"


def forge_digest(root=ROOT):
    run = subprocess.run([sys.executable, str(root / "forge.py"), "digest"], capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


class SdkDigestTests(unittest.TestCase):
    def test_the_recorded_kits_and_version_match_the_kits_and_the_extension(self):
        self.assertTrue(RECORD.is_file(), f"{RECORD} is missing: run extensions/vscode/scripts/record-sdk-digest.py")
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        kits = forge_digest()["kits"]
        changed = sorted(k for k in set(kits) | set(record["kits"]) if kits.get(k) != record["kits"].get(k))
        self.assertEqual(changed, [], f"kits changed since the extension's digest was recorded: {', '.join(changed)}; "
                                      "raise the extension's version and run extensions/vscode/scripts/record-sdk-digest.py")
        version = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))["version"]
        self.assertEqual(record["version"], version, "the extension's version changed without re-recording its digest")

    def test_the_record_script_refuses_changed_kits_under_the_recorded_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdk = pathlib.Path(tmp) / "sdk"
            sdk.mkdir()
            shutil.copy2(ROOT / "forge.py", sdk / "forge.py")
            shutil.copytree(ROOT / "kits" / "base", sdk / "kits" / "base")
            ext = sdk / "extensions" / "vscode"
            (ext / "scripts").mkdir(parents=True)
            shutil.copy2(SCRIPT, ext / "scripts" / SCRIPT.name)
            (ext / "package.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
            script = [sys.executable, str(ext / "scripts" / SCRIPT.name)]
            first = subprocess.run(script, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            recorded = (ext / "sdk-digest.json").read_bytes()
            again = subprocess.run(script, capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual((ext / "sdk-digest.json").read_bytes(), recorded, "a second run changed the record")
            (sdk / "kits" / "base" / "templates" / "AGENTS.md").write_text("changed\n", encoding="utf-8")
            refused = subprocess.run(script, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
            self.assertIn("raise the version", refused.stderr)
            self.assertEqual((ext / "sdk-digest.json").read_bytes(), recorded, "a refused run wrote the record")
            (ext / "package.json").write_text(json.dumps({"version": "1.0.1"}), encoding="utf-8")
            bumped = subprocess.run(script, capture_output=True, text=True)
            self.assertEqual(bumped.returncode, 0, bumped.stderr)
            self.assertEqual(json.loads((ext / "sdk-digest.json").read_text(encoding="utf-8"))["version"], "1.0.1")


if __name__ == "__main__":
    unittest.main()
