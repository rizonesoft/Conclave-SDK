#!/usr/bin/env python3
"""Warn once per Codex session about SDK deployment, marketplace and bundle drift.

Checks run read-only in a daemon thread with a three-second wall-time budget.
The deployment check calls the same dry-run implementation as deploy.py --check,
without spawning a process that could outlive the prompt. No config values or
exception messages are emitted. Session markers live only in the shared scratch.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
import tomllib

SDK = Path(__file__).resolve().parents[3]
BUDGET = 3.0


def first_prompt(session, folder=None):
    if not session:
        return False
    folder = Path(folder or (r'R:\scratch\codex-drift' if os.name == 'nt'
                             else '/mnt/r/scratch/codex-drift'))
    folder.mkdir(parents=True, exist_ok=True)
    # Windows and WSL have independent deployments, even for a shared session ID.
    name = os.name + '-' + hashlib.sha256(session.encode()).hexdigest()
    try:
        fd = os.open(folder / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def deploy_drift(home, sdk):
    spec = importlib.util.spec_from_file_location('codex_drift_deploy', sdk / 'global/deploy.py')
    deploy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deploy)

    class QuietCheck(deploy.Deployer):
        def record(self, label, status):
            self.results.append((label, status))

        def skip(self, label, reason):
            self.results.append((label, 'skipped'))

    checker = QuietCheck(home, True)
    deploy.deploy_codex(checker)
    return ['global Codex deployment differs from the SDK'] if any(
        state in ('created', 'updated') for _, state in checker.results) else []


def normalized(path):
    return os.path.normcase(os.path.realpath(str(path).removeprefix('\\\\?\\')))


def plugin_drift(home, sdk, deadline):
    root = sdk / 'plugins/codex'
    config = tomllib.loads((home / '.codex/config.toml').read_text(encoding='utf-8-sig'))
    problems = []
    source = config.get('marketplaces', {}).get('rizonetech', {}).get('source', '')
    if (not isinstance(source, str) or not source or
            not Path(source.removeprefix('\\\\?\\')).is_absolute() or normalized(source) != normalized(root)):
        problems.append('rizonetech marketplace points outside this SDK')
    cache = home / '.codex/plugins/cache/rizonetech'
    catalog = json.loads((root / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
    for entry in catalog['plugins']:
        if time.monotonic() >= deadline:
            raise TimeoutError
        name = entry['name']
        plugin = root / name
        bundles = sorted((plugin / 'dist').glob('*.mjs'))
        # Conclave intentionally runs its dependency-free source launcher.
        package = json.loads((plugin / 'package.json').read_text(encoding='utf-8'))
        if package.get('scripts', {}).get('build') and not bundles:
            problems.append(name + ': SDK bundles missing')
        inputs = [p for folder in ('src',) for p in (plugin / folder).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts]
        newest = max((p.stat().st_mtime_ns for p in inputs), default=0)
        if any(p.stat().st_mtime_ns < newest for p in bundles):
            problems.append(name + ': SDK bundles older than inputs')
        versions = [p for p in (cache / name).iterdir() if p.is_dir()] if (cache / name).is_dir() else []
        enabled = config.get('plugins', {}).get(name + '@rizonetech', {}).get('enabled', False)
        if enabled and not versions:
            problems.append(name + ': enabled plugin cache missing')
        if not versions:
            continue
        expected = {p.name: hashlib.sha256(p.read_bytes()).digest() for p in bundles}
        # A bundled plugin still runs files from scripts/ (its launcher, its credential helper), so
        # scripts/ is compared for every plugin and src/ for the ones that run their source.
        watched = ('scripts',) if bundles else ('src', 'scripts')

        def source_hashes(base):
            return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).digest()
                    for folder in watched for p in (base / folder).rglob('*')
                    if p.is_file() and '__pycache__' not in p.parts}
        for version in versions:
            if source_hashes(plugin) != source_hashes(version):
                problems.append(name + ': cached source differs from SDK')
                break
            actual = {p.name: hashlib.sha256(p.read_bytes()).digest()
                      for p in (version / 'dist').glob('*.mjs')}
            if actual != expected:
                problems.append(name + ': cached bundles differ from SDK')
                break
            manifests = ('mcp.json', '.mcp.json')
            if any((plugin / name).is_file() != (version / name).is_file() or
                   ((plugin / name).is_file() and (plugin / name).read_bytes() != (version / name).read_bytes())
                   for name in manifests):
                problems.append(name + ': cached MCP manifest differs from SDK')
                break
    return problems


def check(home=None, sdk=SDK, deadline=None):
    home = Path(home or Path.home())
    deadline = deadline or time.monotonic() + BUDGET
    return deploy_drift(home, sdk) + plugin_drift(home, sdk, deadline)


def bounded_check(run=check, budget=BUDGET):
    result = []

    def work():
        try:
            result.append(run(deadline=time.monotonic() + budget))
        except TimeoutError:
            result.append(['check exceeded its three-second budget'])
        except Exception:
            result.append(['check could not read the deployment; run the checks manually'])

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(budget)
    return result[0] if result else ['check exceeded its three-second budget']


def main():
    try:
        data = json.load(sys.stdin)
        session = data.get('session_id') or os.environ.get('CODEX_THREAD_ID')
        if not first_prompt(str(session) if session else ''):
            return 0
        problems = bounded_check()
    except Exception:
        problems = ['session drift check unavailable']
    if problems:
        text = 'Codex setup drift: ' + '; '.join(dict.fromkeys(problems)) + '.'
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit',
                                                'additionalContext': text}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
