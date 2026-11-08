"""Manifest generation/checking in isolated, entirely synthetic packages."""
import contextlib
import hashlib
import io
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import verify_package as package


class ManifestQA(unittest.TestCase):
    def setUp(self):
        cache = Path(__file__).resolve().parent / '__pycache__'
        cache.mkdir(exist_ok=True)
        self.root = (cache / ('manifest-qa-' + uuid.uuid4().hex)).resolve()
        assert self.root.is_relative_to(cache.resolve())
        # Inherit workspace ACLs: tempfile's Windows 0700 ACL denies sandbox tokens.
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.patch = patch.object(package, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        # Only fixture data, never the repository's protected documents/register.
        self.write('docs/00_최종_통합마스터_V5.md', b'Synthetic master\n')
        self.write('references/research_register.csv',
                   ('id\n' + ''.join(f'SYNTH-{i}\n' for i in range(42))).encode())
        for stage, count in (('P', 9), ('S', 7)):
            for number in range(count):
                directory = 'prompts/strategy' if stage == 'S' else 'prompts'
                self.write(f'{directory}/{stage}{number}_synthetic.md', b'Fictional\n')

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def run_package(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = package.main(list(args))
        return status, output.getvalue()

    def test_sorted_deterministic_manifest_and_default_check(self):
        self.write('z.txt', b'last\n')
        self.write('a.txt', b'first\n')
        self.assertEqual(self.run_package('--write-manifest')[0], 0)
        manifest = self.root / 'MANIFEST_SHA256.txt'
        original = manifest.read_bytes()
        paths = [line.split('  ', 1)[1] for line in original.decode().splitlines()[1:]]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn('MANIFEST_SHA256.txt', paths)
        self.assertNotIn(b'\r', original)
        self.assertEqual(self.run_package('--write-manifest')[0], 0)
        self.assertEqual(manifest.read_bytes(), original)
        self.assertEqual(self.run_package('--check-line-endings')[0], 0)
        self.assertEqual(manifest.read_bytes(), original)

    def test_crlf_hash_is_portable_but_strict_check_rejects_drift(self):
        path = self.write('text.txt', b'one\ntwo\n')
        self.assertEqual(self.run_package('--write-manifest')[0], 0)
        expected = package.digest(path)
        path.write_bytes(b'one\r\ntwo\r\n')
        self.assertEqual(package.digest(path), expected)
        self.assertEqual(self.run_package()[0], 0)
        status, output = self.run_package('--check-line-endings')
        self.assertEqual(status, 1)
        self.assertIn('LINE_ENDING_DRIFT: text.txt', output)

    def test_generation_with_strict_drift_does_not_write(self):
        self.write('text.txt', b'drift\r\n')
        self.assertEqual(self.run_package('--write-manifest', '--check-line-endings')[0], 1)
        self.assertFalse((self.root / 'MANIFEST_SHA256.txt').exists())

    def test_binary_hashes_remain_byte_exact(self):
        for name, data in (('file.docx', b'test\r\n'), ('file.pdf', b'test\r\n'),
                           ('file.png', b'test\r\n'), ('file.dat', b'\x00\r\n'),
                           ('encoded.dat', b'\xff\r\n')):
            with self.subTest(name=name):
                self.assertEqual(package.digest(self.write(name, data)), hashlib.sha256(data).hexdigest())

    def test_default_check_rejects_changed_and_unlisted_files(self):
        self.assertEqual(self.run_package('--write-manifest')[0], 0)
        manifest = self.root / 'MANIFEST_SHA256.txt'
        original = manifest.read_bytes()
        self.write('prompts/P0_synthetic.md', b'Changed\n')
        self.write('extra.txt', b'New\n')
        status, output = self.run_package()
        self.assertEqual(status, 1)
        self.assertIn('HASH_MISMATCH: prompts/P0_synthetic.md', output)
        self.assertIn('UNTRACKED_IN_MANIFEST: extra.txt', output)
        self.assertEqual(manifest.read_bytes(), original)

    def test_cache_files_excluded(self):
        self.write('__pycache__/ignored.pyc', b'cache')
        self.write('__pycache__/ignored.md', b'[Ignored cache link](missing.md)\n')
        self.write('.git/ignored', b'git')
        self.assertEqual(self.run_package('--write-manifest')[0], 0)
        contents = (self.root / 'MANIFEST_SHA256.txt').read_text()
        self.assertNotIn('ignored', contents)
        self.assertEqual(self.run_package()[0], 0)


if __name__ == '__main__':
    unittest.main()
