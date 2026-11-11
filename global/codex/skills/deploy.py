"""Preview or deploy one repository global skill into this user's Codex skills."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import shutil
import tempfile

SOURCE = Path(__file__).resolve().parent / 'global'


def reject_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError(f'Refusing linked path: {part}')


def manifest(path):
    result = {}
    for item in path.rglob('*'):
        reject_links(item)
        relative = item.relative_to(path)
        if '__pycache__' in relative.parts or item.suffix in ('.pyc', '.pyo'):
            continue
        if item.is_file():
            result[relative.as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def deploy(name, source_root=SOURCE, home=None, *, apply=False):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise ValueError('Choose a single skill name directly beneath skills/global')
    source_root = Path(source_root).absolute()
    source = source_root / name
    reject_links(source)
    if source.resolve().parent != source_root.resolve() or not (source / 'SKILL.md').is_file():
        raise ValueError(f'Not a global skill: {name}')
    expected = manifest(source)
    home = Path.home() if home is None else Path(home).absolute()
    destination = home / '.agents' / 'skills' / name
    backups = home / '.codex' / 'skill-backups'
    reject_links(destination)
    reject_links(backups)
    if destination.exists():
        if not destination.is_dir():
            raise ValueError(f'Destination is not a directory: {destination}')
        manifest(destination)  # Refuse nested links before any replacement.
    print(f'{"Deploy" if apply else "Preview"}: {source} -> {destination} ({len(expected)} files)')
    if not apply:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='skill-stage-', dir=destination.parent.parent))
    candidate = staging / name
    backup = None
    try:
        shutil.copytree(source, candidate, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
        if manifest(candidate) != expected:
            raise RuntimeError('Staged copy failed verification')
        if manifest(source) != expected:
            raise RuntimeError('Source changed during deployment')
        if destination.exists():
            backups.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = backups / f'{name}-{stamp}'
            destination.rename(backup)
        try:
            candidate.rename(destination)
        except OSError:
            if backup is not None:
                backup.rename(destination)
            raise
        if manifest(destination) != expected:
            raise RuntimeError(f'Installed read-back failed; recovery copy: {backup}')
        print(f'Verified: {destination}')
        if backup is not None:
            print(f'Recovery copy: {backup}')
    finally:
        # Only delete the freshly allocated staging directory, inside .agents.
        if staging.resolve().parent != destination.parent.parent.resolve():
            raise RuntimeError('Staging cleanup escaped the destination root')
        shutil.rmtree(staging)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name', help='A folder name in skills/global; paths are refused')
    parser.add_argument('--apply', action='store_true', help='Install after preflight; default is preview')
    args = parser.parse_args()
    try:
        deploy(args.name, apply=args.apply)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
