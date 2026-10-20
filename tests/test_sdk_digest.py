"""The VS Code extension records the digest of the SDK it bundles (forge.py and the kits) with its version (plan R39):
a change to either ships with a new, higher extension version and a re-recorded digest, or this test fails. The
record's own git history is the baseline, so deleting or rewriting the record cannot pass an old version off as new."""
import importlib.util
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
RECORD_PATH = "extensions/vscode/sdk-digest.json"
SCRIPT = EXTENSION / "scripts" / "record-sdk-digest.py"

_spec = importlib.util.spec_from_file_location("record_sdk_digest", SCRIPT)
record_sdk_digest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record_sdk_digest)


def forge_digest(root=ROOT):
    run = subprocess.run([sys.executable, str(root / "forge.py"), "digest"], capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


def committed_records():
    """Every committed version of the record, oldest first, from git; empty outside a checkout."""
    try:
        shas = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H", "--reverse", "--", RECORD_PATH],
                              capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return []
    records = []
    for sha in shas:
        shown = subprocess.run(["git", "-C", str(ROOT), "show", f"{sha}:{RECORD_PATH}"], capture_output=True, text=True)
        if shown.returncode == 0:
            records.append((sha[:7], json.loads(shown.stdout)))
    return records


class SdkDigestTests(unittest.TestCase):
    def test_the_recorded_digest_and_version_match_forge_the_kits_and_the_extension(self):
        self.assertTrue(RECORD.is_file(), f"{RECORD} is missing: run extensions/vscode/scripts/record-sdk-digest.py")
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        digest = forge_digest()
        changed = sorted(k for k in set(digest["kits"]) | set(record["kits"]) if digest["kits"].get(k) != record["kits"].get(k))
        if digest["forge"] != record.get("forge"):
            changed.insert(0, "forge.py")
        self.assertEqual(changed, [], f"changed since the extension's digest was recorded: {', '.join(changed)}; "
                                      "raise the extension's version and run extensions/vscode/scripts/record-sdk-digest.py")
        version = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))["version"]
        self.assertEqual(record["version"], version, "the extension's version changed without re-recording its digest")

    def test_no_committed_version_is_reused_for_other_contents_or_followed_by_a_lower_one(self):
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        contents = (record.get("forge"), record["kits"])
        for sha, old in committed_records():
            if old["version"] == record["version"]:
                self.assertEqual((old.get("forge"), old["kits"]), contents,
                                 f"version {record['version']} was recorded with other contents in {sha}: raise the version")
            self.assertGreaterEqual(record_sdk_digest.version_key(record["version"]), record_sdk_digest.version_key(old["version"]),
                                    f"version {record['version']} is lower than {old['version']}, recorded in {sha}")

    def test_the_record_script_refuses_changes_unless_the_version_is_higher(self):
        with tempfile.TemporaryDirectory() as tmp:
            sdk = pathlib.Path(tmp) / "sdk"
            sdk.mkdir()
            shutil.copy2(ROOT / "forge.py", sdk / "forge.py")
            shutil.copytree(ROOT / "kits" / "base", sdk / "kits" / "base")
            ext = sdk / "extensions" / "vscode"
            (ext / "scripts").mkdir(parents=True)
            shutil.copy2(SCRIPT, ext / "scripts" / SCRIPT.name)
            package = ext / "package.json"
            package.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
            script = [sys.executable, str(ext / "scripts" / SCRIPT.name)]
            first = subprocess.run(script, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            recorded = (ext / "sdk-digest.json").read_bytes()
            self.assertEqual(subprocess.run(script, capture_output=True, text=True).returncode, 0)
            self.assertEqual((ext / "sdk-digest.json").read_bytes(), recorded, "a second run changed the record")
            for change in ("kit", "forge"):
                if change == "kit":
                    (sdk / "kits" / "base" / "templates" / "AGENTS.md").write_text("changed\n", encoding="utf-8")
                else:
                    with open(sdk / "forge.py", "a", encoding="utf-8") as out:
                        out.write("# changed\n")
                for version in ("1.0.0", "0.9.9"):
                    package.write_text(json.dumps({"version": version}), encoding="utf-8")
                    refused = subprocess.run(script, capture_output=True, text=True)
                    self.assertEqual(refused.returncode, 2, f"{change} change under {version}: {refused.stdout}{refused.stderr}")
                    self.assertIn("not higher", refused.stderr)
                    self.assertEqual((ext / "sdk-digest.json").read_bytes(), recorded, "a refused run wrote the record")
            package.write_text(json.dumps({"version": "1.0.10"}), encoding="utf-8")
            bumped = subprocess.run(script, capture_output=True, text=True)
            self.assertEqual(bumped.returncode, 0, bumped.stderr)
            self.assertEqual(json.loads((ext / "sdk-digest.json").read_text(encoding="utf-8"))["version"], "1.0.10")

    def test_versions_order_by_their_numbers(self):
        key = record_sdk_digest.version_key
        self.assertLess(key("0.0.9"), key("0.0.10"))
        self.assertLess(key("0.9.9"), key("1.0.0"))
        with self.assertRaises(ValueError):
            key("1.0.0-beta")


if __name__ == "__main__":
    unittest.main()
