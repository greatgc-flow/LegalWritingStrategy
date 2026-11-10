"""Contract tests use synthetic prompt files; live CLI behavior is not tested."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mode_plan as modes


class ModePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = json.loads((Path(__file__).resolve().parents[1] / modes.CATALOG).read_text(encoding='utf-8'))
        paths = [self.catalog['common_prompt'], *self.catalog['stages'].values(),
                 *[r['prompt'] for r in self.catalog['modes']]]
        for name in paths:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# Synthetic prompt\n', encoding='utf-8')
        (self.root / 'config').mkdir()
        (self.root / modes.CATALOG).write_text(json.dumps(self.catalog), encoding='utf-8')

    def test_all_six_modes_validate_and_plan_only(self):
        modes.validate(self.catalog, self.root)
        for key in modes.MODES:
            result = modes.plan(self.catalog, key)
            self.assertTrue(result['plan_only'])
            self.assertEqual(result['execution_result'], 'NOT_TESTED')
            self.assertEqual(len(result['stage_files']), len(result['default_steps']))

    def test_duplicate_mode_rejected(self):
        self.catalog['modes'][1] = copy.deepcopy(self.catalog['modes'][0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            modes.validate(self.catalog, self.root)

    def test_missing_mode_rejected(self):
        self.catalog['modes'].pop()
        with self.assertRaisesRegex(ValueError, 'six'):
            modes.validate(self.catalog, self.root)

    def test_unknown_field_rejected(self):
        self.catalog['modes'][0]['auto_submit'] = True
        with self.assertRaisesRegex(ValueError, 'fields'):
            modes.validate(self.catalog, self.root)

    def test_unknown_stage_rejected(self):
        self.catalog['modes'][0]['default_steps'].append('P99')
        with self.assertRaisesRegex(ValueError, 'unknown stage'):
            modes.validate(self.catalog, self.root)

    def test_no_write_to_original_or_exports(self):
        for scope in ('sources', 'exports', 'submissions', '../other'):
            catalog = copy.deepcopy(self.catalog)
            catalog['modes'][0]['write_scopes'].append(scope)
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                modes.validate(catalog, self.root)

    def test_report_modes_cannot_edit_drafts(self):
        for key in modes.REPORT_ONLY:
            catalog = copy.deepcopy(self.catalog)
            next(r for r in catalog['modes'] if r['id'] == key)['write_scopes'].append('drafts')
            with self.subTest(mode=key), self.assertRaisesRegex(ValueError, 'reports'):
                modes.validate(catalog, self.root)

    def test_original_freeze_required(self):
        self.catalog['modes'][0]['default_steps'].remove('P0')
        with self.assertRaisesRegex(ValueError, 'freeze'):
            modes.validate(self.catalog, self.root)

    def test_final_review_required(self):
        self.catalog['modes'][0]['default_steps'].remove('P8')
        with self.assertRaisesRegex(ValueError, 'review'):
            modes.validate(self.catalog, self.root)

    def test_missing_prompt_rejected(self):
        (self.root / self.catalog['modes'][0]['prompt']).unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            modes.validate(self.catalog, self.root)

    def test_path_escape_rejected(self):
        for path in ('../external.md', '/tmp/external.md', 'a\\b.md', 'https://example.invalid/a.md'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                modes.require_path(self.root, path)

    def test_empty_required_inputs_rejected(self):
        self.catalog['modes'][0]['required_inputs'] = []
        with self.assertRaisesRegex(ValueError, 'list'):
            modes.validate(self.catalog, self.root)

    def test_bad_version_rejected(self):
        self.catalog['version'] = True
        with self.assertRaisesRegex(ValueError, 'contract'):
            modes.validate(self.catalog, self.root)

    def test_cli_has_no_case_writes(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch.object(modes, 'ROOT', self.root), patch('builtins.print'):
            self.assertEqual(modes.main(['--mode', 'COMPARE']), 0)
            self.assertEqual(modes.main(['--check']), 0)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_unknown_mode_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unknown'):
            modes.plan(self.catalog, 'INVALID')


if __name__ == '__main__':
    unittest.main()
