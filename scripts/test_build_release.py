"""Synthetic Git repositories only; never handles real case material."""
import hashlib
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import build_release as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('config', 'user.name', 'Synthetic fixture')
        policy = json.loads((Path(__file__).resolve().parents[1] / release.POLICY).read_text(encoding='utf-8'))
        self.put(release.POLICY, json.dumps(policy))
        self.put('README.md', 'Synthetic public kit\n')
        self.put('docs/example.md', 'Synthetic example\n')
        self.commit()

    def git(self, *args, data=None):
        return subprocess.run(['git', '-C', str(self.root), *args], input=data,
                              check=True, capture_output=True).stdout.decode().strip()

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))

    def commit(self):
        lines = ['# synthetic fixture manifest']
        for path in sorted(self.root.rglob('*')):
            name = path.relative_to(self.root).as_posix()
            if path.is_file() and '.git' not in path.parts and name != release.MANIFEST:
                lines.append(hashlib.sha256(release.normalized(path.read_bytes(), name)).hexdigest() + '  ' + name)
        self.put(release.MANIFEST, '\n'.join(lines) + '\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic fixture')
        return self.git('rev-parse', 'HEAD')

    def build(self, filename='output.zip', ref='HEAD'):
        return release.build(self.root, ref, self.base / filename)

    def test_public_files_and_archive_manifest(self):
        result = self.build()
        self.assertEqual(result['file_count'], 4)
        with zipfile.ZipFile(self.base / 'output.zip') as archive:
            entries = release.source_hashes(archive.read(release.MANIFEST))
            self.assertEqual(set(entries), set(archive.namelist()) - {release.MANIFEST})
            for name, digest in entries.items():
                self.assertEqual(digest, hashlib.sha256(release.normalized(archive.read(name), name)).hexdigest())

    def test_worktree_untracked_and_ignored_never_shipped(self):
        self.put('.gitignore', 'private/\n.env\n')
        self.put('private/sample.txt', 'synthetic only')
        self.put('.env', 'SYNTHETIC_PLACEHOLDER=not-a-secret')
        self.put('docs/uncommitted.md', 'synthetic unreviewed')
        self.build()
        with zipfile.ZipFile(self.base / 'output.zip') as archive:
            self.assertNotIn('docs/uncommitted.md', archive.namelist())
            self.assertNotIn('.env', archive.namelist())
            self.assertNotIn('private/sample.txt', archive.namelist())

    def test_tracked_private_nested_archives_logs_excluded(self):
        for name in ('private/example.md', 'docs/private/example.md', 'docs/.env',
                     'qa/session.log', 'examples/nested.zip', 'docs/x_private.md',
                     'docs/.cache/example.md', 'unknown/example.md', 'cases/example.md'):
            self.put(name, 'synthetic excluded')
        self.commit()
        self.build()
        with zipfile.ZipFile(self.base / 'output.zip') as archive:
            self.assertEqual(len(archive.namelist()), 4)

    def test_commit_bytes_not_modified_or_staged_worktree(self):
        self.put('README.md', 'unreviewed working text')
        self.git('add', 'README.md')
        self.build()
        with zipfile.ZipFile(self.base / 'output.zip') as archive:
            self.assertEqual(archive.read('README.md'), b'Synthetic public kit\n')

    def test_policy_also_comes_from_commit(self):
        self.put(release.POLICY, '{}')
        self.build()

    def test_manifest_mismatch_blocks_output(self):
        self.put('README.md', 'changed without manifest')
        self.git('add', 'README.md')
        self.git('commit', '-qm', 'Synthetic stale manifest')
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
            self.build()
        self.assertFalse((self.base / 'output.zip').exists())

    def test_symlink_blob_rejected_without_following(self):
        oid = self.git('hash-object', '-w', '--stdin', data=b'../../outside')
        self.git('update-index', '--add', '--cacheinfo', '120000,' + oid + ',docs/link.md')
        self.git('commit', '-qm', 'Synthetic symlink')
        with self.assertRaisesRegex(ValueError, 'non-regular'):
            self.build()

    def test_gitlink_rejected(self):
        oid = self.git('rev-parse', 'HEAD')
        self.git('update-index', '--add', '--cacheinfo', '160000,' + oid + ',docs/submodule.md')
        self.git('commit', '-qm', 'Synthetic gitlink')
        with self.assertRaisesRegex(ValueError, 'non-regular'):
            self.build()

    def test_deterministic_same_commit_and_ref_pinning(self):
        original = self.git('rev-parse', 'HEAD')
        first = self.build('first.zip', original)
        self.put('docs/later.md', 'later public content')
        self.commit()
        second = self.build('second.zip', original)
        self.assertEqual(first, second)
        self.assertEqual((self.base / 'first.zip').read_bytes(), (self.base / 'second.zip').read_bytes())

    def test_portable_case_collision_rejected(self):
        # Git index entries avoid platform-specific case-insensitive file writes.
        oid = self.git('hash-object', '-w', '--stdin', data=b'synthetic')
        manifest = (self.root / release.MANIFEST).read_text()
        self.put(release.MANIFEST, manifest + hashlib.sha256(b'synthetic').hexdigest() + '  docs/EXAMPLE.md\n')
        self.git('add', release.MANIFEST)
        self.git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',docs/EXAMPLE.md')
        self.git('commit', '-qm', 'Synthetic case collision')
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.build()

    def test_existing_output_is_not_overwritten(self):
        target = self.base / 'output.zip'
        target.write_bytes(b'preserve this')
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(target.read_bytes(), b'preserve this')

    def test_output_inside_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            release.build(self.root, 'HEAD', self.root / 'release.zip')

    def test_size_limit_fails_before_output(self):
        policy = json.loads((self.root / release.POLICY).read_text())
        policy['max_file_bytes'] = 1
        self.put(release.POLICY, json.dumps(policy))
        self.commit()
        with self.assertRaisesRegex(ValueError, 'too large'):
            self.build()

    def test_total_limit_fails(self):
        policy = json.loads((self.root / release.POLICY).read_text())
        policy['max_total_bytes'] = 1
        self.put(release.POLICY, json.dumps(policy))
        self.commit()
        with self.assertRaisesRegex(ValueError, 'total size'):
            self.build()

    def test_tampered_zip_rejected(self):
        _, expected = release.snapshot(self.root, 'HEAD')
        self.build()
        with zipfile.ZipFile(self.base / 'output.zip', 'a') as archive:
            archive.writestr('unexpected.txt', 'synthetic')
        with self.assertRaisesRegex(ValueError, 'membership'):
            release.verify_zip(self.base / 'output.zip', expected)

    def test_path_and_manifest_validation(self):
        for name in ('../a', '/a', 'a\\b', 'a//b', 'a/./b', 'C:/a', 'a\nb'):
            with self.subTest(name=name):
                self.assertFalse(release.safe_name(name))
        with self.assertRaisesRegex(ValueError, 'manifest'):
            release.source_hashes(b'not-a-sha  README.md\n')
        line = b'a' * 64 + b'  README.md\n'
        with self.assertRaisesRegex(ValueError, 'manifest'):
            release.source_hashes(line + line)

    def test_unknown_policy_keys_rejected(self):
        policy = json.loads((self.root / release.POLICY).read_text())
        policy['allow_everything'] = True
        with self.assertRaisesRegex(ValueError, 'contract'):
            release.validate_policy(policy)


if __name__ == '__main__':
    unittest.main()
