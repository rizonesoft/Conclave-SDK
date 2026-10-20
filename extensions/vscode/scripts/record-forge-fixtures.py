"""Record forge.py's JSON output for every command the extension parses, as test fixtures.

    python scripts/record-forge-fixtures.py

Runs this SDK's own forge.py (two folders up) on fresh temporary folders and writes each command's stdout to
test/fixtures/forge/<name>.json, with the temporary folder written as <TARGET> and the SDK folder as <SDK>, so two runs
give the same files on one platform (the committed ones were recorded on Windows: the automations doctor checks
pythonw there and systemctl elsewhere, and stub CLIs are .cmd files there). A refusal (exit 2, its message on stderr)
is recorded as <name>.stderr with its exit code. Stdlib only; every file is written through a temporary file and
os.replace.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTENSION = HERE.parent
SDK = EXTENSION.parent.parent
FORGE = SDK / "forge.py"
OUT = EXTENSION / "test" / "fixtures" / "forge"


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def normalise(text, target, bin_dir=None):
    """The temporary folder, the SDK folder and the stub CLI folder as placeholders, in every spelling forge may print
    them."""
    marks = [(target, "<TARGET>"), (SDK, "<SDK>")] + ([(bin_dir, "<BIN>")] if bin_dir else [])
    for path, mark in marks:
        for spelling in {str(path), str(path).replace("\\", "/"), json.dumps(str(path))[1:-1], path.as_posix()}:
            text = text.replace(spelling, mark)
    return text


def forge(args, target, bin_dir=None):
    """forge.py's answer. With bin_dir, PATH is that folder alone, so the CLIs a doctor looks for are the stubs there:
    the same answer on every host."""
    env = None
    if bin_dir is not None:
        env = {k: v for k, v in os.environ.items() if k.upper() != "PATH"}
        env["PATH"] = str(bin_dir)
    run = subprocess.run([sys.executable, "-I", str(FORGE), *args], capture_output=True, text=True, encoding="utf-8",
                         cwd=SDK, timeout=300, env=env)
    return run.returncode, normalise(run.stdout, target, bin_dir), normalise(run.stderr, target, bin_dir)


def stub_bin(folder, clis):
    """A folder of stub CLIs (empty, never run), found by shutil.which on this platform."""
    folder.mkdir()
    for cli in clis:
        stub = folder / (f"{cli}.cmd" if os.name == "nt" else cli)
        stub.write_text("@exit /b 0\r\n" if os.name == "nt" else "#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)
    return folder


def record(name, args, target, expect=0, bin_dir=None):
    code, stdout, stderr = forge(args, target, bin_dir)
    if code != expect:
        sys.exit(f"{name}: forge exited {code}, expected {expect}\n{stderr[-2000:]}")
    if expect == 0:
        json.loads(stdout)  # forge's answer must be JSON, or the fixture is useless
        atomic_write(OUT / f"{name}.json", stdout if stdout.endswith("\n") else stdout + "\n")
    else:
        atomic_write(OUT / f"{name}.stderr", json.dumps({"exit": code, "stderr": stderr}, indent=2) + "\n")
    print(f"{name}: exit {code}")


def main():
    with tempfile.TemporaryDirectory(prefix="conclave-forge-") as work:
        work = Path(work)
        record("kits", ["kits"], work)
        kit_target = work / "kit"
        kit_target.mkdir()
        record("kit-dry-run", ["kit", str(kit_target), "reviewer", "--dry-run"], kit_target)
        record("kit", ["kit", str(kit_target), "reviewer"], kit_target)
        repo = work / "repo"
        repo.mkdir()
        # The extension never runs init or sync (read-only kit view): the folder is set up here, not recorded.
        code, _, stderr = forge(["init", str(repo), "--kit", "todo"], repo)
        if code != 0:
            raise SystemExit(f"forge init failed: {stderr}")
        record("check", ["check", str(repo)], repo)
        record("doctor", ["doctor", str(repo)], repo)
        record("kit-refused", ["kit", str(work / "missing"), "reviewer"], work / "missing", expect=2)
        # Kit state (D02 T01 §10): every kit's dry run on an empty folder, a base-only folder, a folder with every kit
        # that applies outside a Laravel app, and a folder provisioned for Claude alone.
        cases = {"empty": [], "base": ["init", "{dir}"], "all": ["init", "{dir}", "--kit", "todo", "--kit", "reviewer",
                 "--kit", "automations", "--kit", "wordpress"], "claude": ["init", "{dir}", "--agent", "claude"]}
        for case, setup in cases.items():
            folder = work / f"state-{case}"
            folder.mkdir()
            if setup:
                code, _, stderr = forge([a.replace("{dir}", str(folder)) for a in setup], folder)
                if code != 0:
                    sys.exit(f"state-{case}: setup exited {code}\n{stderr[-2000:]}")
            for kit in ("base", "todo", "reviewer", "automations", "wordpress"):
                record(f"dry-{case}-{kit}", ["kit", str(folder), kit, "--dry-run", "--agent", "all"], folder)
        record("dry-empty-laravel", ["kit", str(work / "state-empty"), "laravel", "--dry-run", "--agent", "all"],
               work / "state-empty", expect=2)
        # Kit health (D05 T01 §3): check once, and every kit's doctor on the folder with every kit, with every reviewer
        # CLI present; the reviewer doctor again with the Gemini CLI missing; the WordPress doctor needs its site set up.
        every = stub_bin(work / "bin-every", ["codex", "agy", "claude"])
        no_agy = stub_bin(work / "bin-no-agy", ["codex", "claude"])
        folder = work / "state-all"
        record("health-check", ["check", str(folder)], folder, bin_dir=every)
        for kit in ("base", "todo", "reviewer", "automations", "wordpress"):
            record(f"doctor-{kit}", ["doctor", str(folder), kit], folder, bin_dir=every)
        record("doctor-reviewer-no-agy", ["doctor", str(folder), "reviewer"], folder, bin_dir=no_agy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
