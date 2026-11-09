"""Break each frozen predicate in an isolated copy; never edit live ledgers/docs.

Integration uses the explicit probe, checking every nonrecursive row. The normal
scorer runs this full suite separately; no deferred row is treated as passing.
"""
import csv
import contextlib
import io
import json
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import score

ROOT = Path(__file__).resolve().parents[1]


class ScoreTests(unittest.TestCase):
    def setUp(self):
        cache = ROOT / 'scripts/__pycache__'
        cache.mkdir(exist_ok=True)
        self.root = (cache / ('score-qa-' + uuid.uuid4().hex)).resolve()
        assert self.root.is_relative_to(cache.resolve())
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(
            '.git', '.venv', '__pycache__', '.pytest_cache', '*.pyc'))
        self.addCleanup(shutil.rmtree, self.root)
        self.audit = score.Audit(self.root)
        self.regenerate()

    def regenerate(self):
        verifier = self.audit.module('verify_package')
        verifier.write_manifest(self.root, {p.relative_to(self.root).as_posix() for p in self.audit.files()})
        self.audit.cache.pop('package_issues', None)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))

    def change_json(self, relative, transform):
        value = json.loads(self.audit.text(relative))
        transform(value)
        self.write(relative, json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    def change_csv(self, relative, transform):
        rows = self.audit.rows(relative)
        fields = list(rows[0])
        transform(rows)
        output = io.StringIO()
        writer = csv.DictWriter(output, fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        self.write(relative, output.getvalue())

    def assert_broken(self, key):
        predicate = score.CRITERIA.get(key) or score.GATES[key]
        self.assertTrue(score.checked(predicate, self.audit), key)

    def test_single_ssot(self):
        master = next((self.root / 'docs').glob('00_*.md'))
        self.write('docs/duplicate.md', master.read_text(encoding='utf-8'))
        self.assert_broken('A1.single_ssot')

    def test_stage_ids(self):
        self.change_csv('references/research_register.csv', lambda rows: rows.append(dict(rows[0])))
        self.assert_broken('A1.stage_ids')

    def test_links_paths(self):
        self.write('README.md', self.audit.text('README.md') + '\n[Missing](docs/missing_score_fixture.md)\n')
        self.assert_broken('A1.links_paths')

    def test_reachability(self):
        self.write('docs/orphan_score_fixture.md', 'Unique disconnected synthetic document.\n')
        self.assert_broken('A1.reachability')

    def test_synthetic_cases(self):
        self.change_json('examples/synthetic_strategy_case.json', lambda x: x['issues'][0].update(rule_ids=[]))
        self.assert_broken('A2.synthetic_cases')

    def test_error_codes(self):
        (self.root / 'examples/adversarial_strategy/amount_mismatch.json').unlink()
        self.assert_broken('A2.error_codes')

    def test_node_schema(self):
        relative = 'scripts/strategy_qa.py'
        self.write(relative, self.audit.text(relative).replace("('EV', {})", "('ABSENT', {})"))
        self.assert_broken('A2.node_schema')

    def test_recursive_termination(self):
        (self.root / 'examples/adversarial_strategy/cycle_without_exit.json').unlink()
        self.assert_broken('A2.recursive_termination')

    def test_unit_tests(self):
        # Isolate the runner from this self-testing suite, then run a real failure.
        for path in (self.root / 'scripts').glob('test_*.py'):
            path.unlink()
        self.write('scripts/test_injected_failure.py',
                   'import unittest\nclass Broken(unittest.TestCase):\n'
                   '    def test_failure(self): self.fail("synthetic failure")\n')
        self.assert_broken('A3.unit_tests')

    def test_rule_test_mapping(self):
        self.change_csv('references/rule_test_map.csv', lambda rows: rows.__setitem__(
            slice(None), [row for row in rows if row['rule_id'] != '2']))
        self.assert_broken('A3.rule_test_mapping')

    def test_mapping_rejects_nonexistent_test(self):
        self.change_csv('references/rule_test_map.csv', lambda rows: rows[0].update(
            test_or_gate='test_strategy_qa.QA.test_nonexistent'))
        self.assert_broken('A3.rule_test_mapping')

    def test_final_states(self):
        self.write('docs/bad_status.md', '최종 ' + '상태: `UNAPPROVED_FINAL`\n')
        self.assert_broken('A3.final_states')

    def test_bibliography_identity(self):
        self.change_csv('references/research_register.csv', lambda rows: rows[0].update(doi_check='unverified'))
        self.assert_broken('A4.bibliography_identity')

    def test_grade_scope(self):
        self.change_csv('references/research_register.csv', lambda rows: rows[0].update(evidence_grade='metadata_only'))
        self.assert_broken('A4.grade_scope')

    def test_statute_ledger(self):
        self.change_csv('references/statute_ledger.csv', lambda rows: rows.pop(0))
        self.assert_broken('A4.statute_ledger')

    def test_statute_scan_detects_new_subarticle(self):
        self.write('docs/extra_citation.md', '형법 제1조의2\n')
        self.assert_broken('A4.statute_ledger')

    def test_statute_date_required(self):
        self.change_csv('references/statute_ledger.csv', lambda rows: rows[0].update(checked_on=''))
        self.assert_broken('A4.statute_ledger')

    def test_transfer_limits(self):
        self.change_csv('references/research_register.csv', lambda rows: rows[0].update(transfer_limit=' '))
        self.assert_broken('A4.transfer_limits')

    def test_package_integrity(self):
        self.write('score_fixture_extra.txt', 'Synthetic unlisted source.\n')
        self.assert_broken('A5.package_integrity')

    def test_ci_matrix(self):
        relative = '.github/workflows/qa.yml'
        self.write(relative, self.audit.text(relative).replace('windows-latest', 'macos-latest'))
        self.assert_broken('A5.ci_matrix')

    def test_determinism(self):
        relative = 'scripts/score.py'
        self.write(relative, 'import json,sys,uuid\nprint(json.dumps({"nonce":uuid.uuid4().hex}))\n'
                   'sys.exit(1)\n' + self.audit.text(relative))
        # Two real executions with valid but differing JSON, without network work.
        self.assert_broken('A5.determinism')

    def test_dependencies(self):
        self.write('requirements.txt', 'python-docx>=1.1,<2\n')
        def command(arguments, **kwargs):
            if 'install' in arguments:
                return subprocess.CompletedProcess(arguments, 0, 'Would install python-docx-1.2.0\n', '')
            return subprocess.CompletedProcess(arguments, 0, 'No broken requirements found.\n', '')
        with patch.object(self.audit, 'run', side_effect=command):
            details = score.dependencies(self.audit)
        self.assertTrue(any(d.startswith('not latest resolvable') for d in details))

    def test_dependency_unresolvable_fails(self):
        self.write('requirements.txt', 'PyMuPDF==2.1\n')
        def command(arguments, **kwargs):
            code = 1 if 'install' in arguments else 0
            return subprocess.CompletedProcess(arguments, code, 'No matching distribution found for onnxruntime', '')
        with patch.object(self.audit, 'run', side_effect=command):
            details = score.dependencies(self.audit)
        self.assertTrue(any(d.startswith('requirements.txt does not resolve') for d in details))

    def test_gate_secrets(self):
        self.write('docs/injected_secret.md', 'sk-' + 'Q' * 40 + '\n')
        self.assert_broken('SG1')

    def test_gate_account_pattern(self):
        self.write('docs/injected_account.md', 'Synthetic account: ' + '123' + '-45-' + '67890\n')
        self.assert_broken('SG1')

    def test_gate_disclaimer(self):
        self.write('README.md', 'Synthetic project without a disclaimer.\n')
        self.assert_broken('SG2')

    def test_gate_guarantees(self):
        self.write('docs/bad_claim.md', '승소 ' + '보장합니다.\n')
        self.assert_broken('SG3')

    def test_gate_fictional(self):
        self.change_json('examples/synthetic_strategy_case.json', lambda x: x.pop('scope'))
        self.assert_broken('SG4')

    def test_frozen_denominator(self):
        weights = score.rubric(self.audit)
        self.assertEqual(sum(row[2] for row in weights), 100)
        self.assertEqual(set(score.CRITERIA.values()), {getattr(score, key.split('.')[1]) for key in score.CRITERIA})
        self.assertEqual(len(weights), len(score.CRITERIA))

    def test_score_after_regeneration_reports_remaining_defects(self):
        # Copy the real tree and regenerate there; the live manifest stays untouched.
        arguments = ['scripts/score.py', '--json', '--probe']
        result = self.audit.run(arguments, timeout=240)
        report = json.loads(result.stdout)
        deferred = {'A3.unit_tests', 'A5.determinism'}
        # Documentation defects must remain score failures, not test failures.
        # Recompute all nonrecursive/static predicates in the same frozen copy.
        for row in report['criteria']:
            if row['id'] not in {'A3.unit_tests', 'A5.determinism', 'A5.dependencies'}:
                self.assertEqual(row['details'], score.checked(score.CRITERIA[row['id']], self.audit), row['id'])
            self.assertEqual(row['earned'], row['points'] if row['passed'] else 0)
            self.assertEqual(row['passed'], not row['details'])
        expected = sum(row['earned'] for row in report['criteria'])
        self.assertEqual(report['total'], expected)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(all(not row['passed'] for row in report['criteria'] if row['id'] in deferred))

    def test_cli_exit_requires_all_points_and_all_score_gates(self):
        for total, passed, expected in [(100, True, 0), (95, True, 1), (100, False, 1)]:
            with self.subTest(total=total, passed=passed), patch.object(score, 'evaluate', return_value={
                    'total':total, 'gates':{'SG1':{'passed':passed}}}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(score.main(['--json']), expected)

    def test_single_ssot_legacy_name_outside_docs(self):
        self.write('config/legacy_V4_notes.txt', 'Synthetic superseded configuration.\n')
        self.assertIn('obsolete name: config/legacy_V4_notes.txt', score.single_ssot(self.audit))

    def test_score_gate_names_are_separate(self):
        self.assertEqual(set(score.GATES), {'SG1', 'SG2', 'SG3', 'SG4'})
        self.assertTrue(all(row['test_or_gate'] not in {'G1','G2','G3','G4'}
                            for row in self.audit.rows('references/rule_test_map.csv')))

    def test_final_enums_without_final_prefix(self):
        samples = {'qa/competing.md': '상태: `PASS_INTERNAL_TESTS`, `NEEDS_CASE_SPECIFIC_REVIEW`\n',
                   'docs/competing.md': '결과 | READY | HOLD | FAIL\n',
                   'prompts/competing.md': '# 독립 판정\n\n## 출력\n`PASS / HOLD / NOT_TESTED`\n',
                   'docs/grades.md': '## 등급\n\n1. `DESIGN_COMPLETE_100`\n2. `CASE_READY`\n',
                   'qa/adjacent.md': '선택 가능한 상태\n\n`GREEN / AMBER / RED`\n'}
        for path, text in samples.items():
            self.write(path, text)
        errors=score.final_states(self.audit)
        for path in samples:
            self.assertTrue(any(path+':' in error for error in errors), path)

    def test_technical_acronyms_are_not_status_enums(self):
        self.write('qa/technical.md', '추출 결과: PDF/DOCX, SHA/EXIF, DOI/TACL\n')
        self.assertFalse(any('qa/technical.md:' in error for error in score.final_states(self.audit)))

    def test_error_codes_reject_unexpected_cascade(self):
        relative='examples/adversarial_strategy/unverified_law.json'
        self.change_json(relative, lambda x: x['operations'].append(
            {'path':['issues',0,'rule_ids'],'value':[]}))
        self.assertIn('exact expected code set differs: unverified_law.json', score.error_codes(self.audit))

    def test_rollback_fixture_is_required(self):
        (self.root/'examples/adversarial_strategy/rollback_incomplete.json').unlink()
        self.assertIn('missing failing rollback_incomplete.json fixture', score.recursive_termination(self.audit))

    def test_rubric_cannot_satisfy_its_own_currency_check(self):
        for pattern in ('docs/14_*.md', 'prompts/P2_*.md'):
            for path in self.root.glob(pattern):
                self.write(path.relative_to(self.root), 'Synthetic instructions without recheck language.\n')
        self.assertTrue(any('recheck instruction' in p for p in score.transfer_limits(self.audit)))

    def test_generic_statute_scan_includes_prompts(self):
        self.write('prompts/citation_fixture.md', '가상법시행령 제9조의2\n')
        self.assertIn('missing TEXT_MATCH/date: 가상법시행령 제9조의2', score.statute_ledger(self.audit))

    def test_statute_cited_in_is_required(self):
        self.change_csv('references/statute_ledger.csv', lambda rows: next(
            row for row in rows if row['law']=='형사소송법' and row['article']=='제307조').update(cited_in=''))
        self.assertTrue(any(p.startswith('missing cited_in: 형사소송법 제307조:')
                            for p in score.statute_ledger(self.audit)))

    def test_ci_requires_score_command(self):
        relative='.github/workflows/qa.yml'
        self.write(relative, self.audit.text(relative).replace('python scripts/score.py', 'echo omitted'))
        self.assert_broken('A5.ci_matrix')

    def test_legacy_and_duplicates_cannot_hide_in_archive(self):
        master=next((self.root/'docs').glob('00_*.md'))
        relative='docs/archive/legacy_V4.md'
        self.write(relative, master.read_text(encoding='utf-8'))
        problems=score.single_ssot(self.audit)
        self.assertIn('obsolete name: '+relative, problems)
        self.assertTrue(any(p.startswith('90% duplicate:') and relative in p for p in problems))

    def test_negative_ledger_notes_override_text_match(self):
        for note in ('prior TEXT_MATCH not reproduced', 'local source absent', '원문 재현 안 됨'):
            with self.subTest(note=note):
                self.change_csv('references/statute_ledger.csv', lambda rows: rows[0].update(
                    status='TEXT_MATCH', checked_on='2026-11-09', note=note))
                self.assertIn('not reproduced: 민사소송법 제1조', score.statute_ledger(self.audit))

    def test_single_result_table_cells_are_closed(self):
        self.write('qa/result_cells.md', '| 항목 | 검사 결과 |\n|---|---|\n'
                   '| a | COVERED |\n| b | 9/9 FILES |\n| c | PASS (container) |\n')
        errors=score.final_states(self.audit)
        for value in ('COVERED','9/9 FILES','PASS (container)'):
            self.assertTrue(any('qa/result_cells.md:' in p and p.endswith(': '+value) for p in errors), value)

    def test_result_table_accepts_item_and_final_states(self):
        values=sorted(score.ITEM_RESULTS | score.FINAL_STATES)
        self.write('qa/valid_result_cells.md', '| 항목 | 판정 |\n|---|---|\n'+''.join(
            '| synthetic | '+value+' |\n' for value in values))
        self.assertFalse(any('qa/valid_result_cells.md:' in p for p in score.final_states(self.audit)))

    def test_prose_outputs_are_not_result_status_tags(self):
        self.write('qa/prose_outputs.md','| 책임 | 넘기는 결과 |\n|---|---|\n'
                   '| synthetic | 적용 규정과 마감일 → 다른 영역 |\n')
        self.assertFalse(any('qa/prose_outputs.md:' in p for p in score.final_states(self.audit)))

    def test_failures_use_not_tested_vocabulary(self):
        def broken(a):
            raise ValueError('synthetic failure')
        self.assertTrue(score.checked(broken,self.audit)[0].startswith('NOT_TESTED:'))
        with patch.object(self.audit,'run',side_effect=[subprocess.CompletedProcess([],0,'',''),
                subprocess.TimeoutExpired('synthetic resolver',1)]):
            self.assertIn('NOT_TESTED: resolver unavailable',score.dependencies(self.audit))

    def test_resolver_permission_failure_is_not_tested(self):
        results=[subprocess.CompletedProcess([],0,'',''),
                 subprocess.CompletedProcess([],1,'','Permission denied: synthetic temporary metadata')]
        with patch.object(self.audit,'run',side_effect=results):
            self.assertIn('NOT_TESTED: resolver filesystem access denied',score.dependencies(self.audit))

    def test_tool_catalog_rejects_missing_verify(self):
        self.change_json('config/tool_catalog.json',lambda x:x['entries'][0].pop('verify'))
        self.regenerate()
        self.assertIn('missing tool verify command: pandoc',score.package_integrity(self.audit))

    def test_tool_catalog_rejects_unregistered_doc_tool(self):
        self.write('docs/unknown_tool.md','| Tool | Role |\n|---|---|\n| ghost-cli | Synthetic |\n')
        self.assertTrue(any('uncatalogued doc tool: docs/unknown_tool.md:3: ghost-cli' in p
                            for p in score.tool_catalog(self.audit)))

    def test_tool_catalog_ids_are_valid_and_unique(self):
        self.change_json('config/tool_catalog.json',lambda x:x['entries'][0].update(id='Bad Tool'))
        self.assertIn('invalid tool id: Bad Tool',score.tool_catalog(self.audit))
        self.change_json('config/tool_catalog.json',lambda x:x['entries'][0].update(id=x['entries'][1]['id']))
        self.assertTrue(any(p.startswith('duplicate tool id:') for p in score.tool_catalog(self.audit)))

    def test_tool_removed_from_catalog_is_detected_in_docs(self):
        self.change_json('config/tool_catalog.json',lambda x:x.update(entries=[
            entry for entry in x['entries'] if entry['id']!='pandoc']))
        self.assertTrue(any('uncatalogued doc tool:' in p and 'Pandoc' in p for p in score.tool_catalog(self.audit)))

    def test_statute_scan_includes_qa_and_config(self):
        self.write('qa/statute_fixture.md','가상법 제7조/제8조의2\n')
        self.write('config/statute_fixture.json',json.dumps({'authority':'가상법 제7조'},ensure_ascii=False))
        citations=score.statute_citations(self.audit)
        self.assertEqual(citations['가상법','제7조'],{'qa/statute_fixture.md','config/statute_fixture.json'})
        self.assertEqual(citations['가상법','제8조의2'],{'qa/statute_fixture.md'})
        self.assertIn('missing TEXT_MATCH/date: 가상법 제7조',score.statute_ledger(self.audit))

    def test_openpyxl_has_compatible_requirement_range(self):
        self.assertRegex(self.audit.text('requirements.txt'),r'(?m)^openpyxl>=3\.1,<4$')

    def test_claim_matrix_uses_documented_states(self):
        rows=self.audit.rows('examples/claim_evidence_matrix.csv')
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row['confidence'],{'VERIFIED','PARTIAL','UNVERIFIED','NOT_APPLICABLE'})
            self.assertIn(row['status'],{'PASS','FAIL','REVIEW'})


if __name__ == '__main__':
    unittest.main()
