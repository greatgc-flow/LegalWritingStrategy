#!/usr/bin/env python3
"""Package allowed regular blobs from one Git commit, never the working tree.

Offline boundary check only; this is not a secret scanner or a legal audit.
The policy and source manifest are also read from the selected commit.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'config/release_policy.json'
MANIFEST = 'MANIFEST_SHA256.txt'


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], check=True,
                            capture_output=True, timeout=30)
    return result.stdout


def safe_name(name):
    if not isinstance(name, str):
        return False
    path = PurePosixPath(name)
    return (bool(name) and not path.is_absolute()
            and path.as_posix() == name and not re.search(r'[\\:\x00-\x1f\x7f]', name)
            and all(part not in ('.', '..', '') for part in name.split('/')))


def validate_policy(policy):
    keys = {'version', 'root_files', 'directory_extensions', 'blocked_parts',
            'blocked_suffixes', 'max_file_bytes', 'max_total_bytes'}
    if not isinstance(policy, dict) or set(policy) != keys or type(policy['version']) is not int or policy['version'] != 1:
        raise ValueError('invalid release policy contract')
    for key in ('root_files', 'blocked_parts', 'blocked_suffixes'):
        if not isinstance(policy[key], list) or not policy[key] or not all(
                isinstance(v, str) and v for v in policy[key]):
            raise ValueError('invalid policy list: ' + key)
    if not all(safe_name(v) and '/' not in v for v in policy['root_files']):
        raise ValueError('invalid root allowlist')
    dirs = policy['directory_extensions']
    if not isinstance(dirs, dict) or not dirs:
        raise ValueError('empty directory allowlist')
    for directory, extensions in dirs.items():
        if (not safe_name(directory) or '/' in directory or directory.startswith('.')
                or not isinstance(extensions, list) or not extensions
                or not all(isinstance(v, str) and re.fullmatch(r'\.[a-z0-9]+', v) for v in extensions)):
            raise ValueError('invalid directory allowlist')
    for key in ('max_file_bytes', 'max_total_bytes'):
        if type(policy[key]) is not int or policy[key] <= 0:
            raise ValueError('invalid size limit')


def allowed(name, policy):
    if not safe_name(name) or name == MANIFEST:
        return False
    path = PurePosixPath(name)
    parts = [part.casefold() for part in path.parts]
    if (any(part in policy['blocked_parts'] or part.startswith('.env') for part in parts)
            or any(part.startswith('.') for part in parts[1:])
            or any(part.endswith('_private') or '_private.' in part for part in parts)
            or path.suffix.casefold() in policy['blocked_suffixes']):
        return False
    if len(parts) == 1:
        return name in policy['root_files']
    return (path.parts[0] in policy['directory_extensions']
            and path.suffix.lower() in policy['directory_extensions'][path.parts[0]])


def normalized(data, name):
    # Same normalization contract as verify_package.py; originals are NOT changed.
    if PurePosixPath(name).suffix.lower() in {'.docx', '.pdf', '.png'} or b'\0' in data:
        return data
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    return data.replace(b'\r\n', b'\n')


def source_hashes(data):
    entries = {}
    for line in data.decode('utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        pair = line.split('  ', 1)
        if (len(pair) != 2 or not re.fullmatch(r'[a-f0-9]{64}', pair[0])
                or not safe_name(pair[1]) or pair[1] in entries):
            raise ValueError('invalid source manifest entry')
        entries[pair[1]] = pair[0]
    if not entries:
        raise ValueError('empty source manifest')
    return entries


def snapshot(root, ref):
    commit = git(root, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
    entries = {}
    for record in git(root, 'ls-tree', '-r', '-z', '-l', '--full-tree', commit).split(b'\0'):
        if not record:
            continue
        meta, raw_name = record.split(b'\t', 1)
        mode, kind, oid, size = meta.decode('ascii').split()
        name = raw_name.decode('utf-8')
        if not safe_name(name) or name in entries:
            raise ValueError('unsafe/duplicate Git path')
        entries[name] = (mode, kind, oid, size)

    def read(name, limit):
        mode, kind, oid, size = entries[name]
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('non-regular release input: ' + name)
        if not size.isdigit() or int(size) > limit:
            raise ValueError('release input too large: ' + name)
        data = git(root, 'cat-file', 'blob', oid)
        if len(data) != int(size):
            raise ValueError('blob length mismatch: ' + name)
        return data

    policy = json.loads(read(POLICY, 1024 * 1024))
    validate_policy(policy)
    hashes = source_hashes(read(MANIFEST, 4 * 1024 * 1024))
    selected, total, portable_names = {}, 0, set()
    for name in sorted(entries):
        if not allowed(name, policy):
            continue
        portable = unicodedata.normalize('NFC', name).casefold()
        if portable in portable_names:
            raise ValueError('portable path collision: ' + name)
        portable_names.add(portable)
        mode, kind, _, size = entries[name]
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('non-regular release input: ' + name)
        if not size.isdigit():
            raise ValueError('invalid blob size')
        total += int(size)
        if total > policy['max_total_bytes']:
            raise ValueError('release total size exceeded')
        data = read(name, policy['max_file_bytes'])
        if hashes.get(name) != hashlib.sha256(normalized(data, name)).hexdigest():
            raise ValueError('source manifest mismatch: ' + name)
        selected[name] = data
    if not selected or POLICY not in selected:
        raise ValueError('empty release or missing policy')
    # Preserve the verifier's LF-normalized source-manifest semantics in the ZIP.
    manifest = ['# SHA256 of release files; UTF-8 text normalized to LF; excludes itself.']
    manifest += [hashlib.sha256(normalized(data, name)).hexdigest() + '  ' + name
                 for name, data in sorted(selected.items())]
    selected[MANIFEST] = ('\n'.join(manifest) + '\n').encode('utf-8')
    return commit, selected


def verify_zip(path, expected):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('release ZIP membership mismatch')
        for info in archive.infolist():
            if (not safe_name(info.filename) or info.is_dir()
                    or (info.external_attr >> 16) & 0o170000 != 0o100000):
                raise ValueError('non-regular ZIP member')
            if archive.read(info) != expected[info.filename]:
                raise ValueError('release ZIP content mismatch: ' + info.filename)


def build(root, ref, output):
    root, output = Path(root).resolve(), Path(output).absolute()
    if output.resolve().is_relative_to(root):
        raise ValueError('release output must be outside the source directory')
    commit, selected = snapshot(root, ref)
    # Exclusive creation: never overwrite an existing artifact or symlink.
    with output.open('xb') as handle:
        try:
            with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in sorted(selected.items()):
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data)
        except Exception:
            handle.close()
            output.unlink(missing_ok=True)
            raise
    try:
        verify_zip(output, selected)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {'commit': commit, 'file_count': len(selected),
            'zip_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'scope': 'Committed allowlisted bytes only; not a secret scan or legal verification.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(ROOT, args.ref, args.out), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print('FAIL release: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
