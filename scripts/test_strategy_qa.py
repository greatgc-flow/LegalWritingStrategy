#!/usr/bin/env python3
"""Unit tests on a fully fictional case. No real-law conclusions."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from strategy_qa import SCHEMA, OPTIONAL_COLLECTIONS, check
BASE=json.loads((Path(__file__).resolve().parent.parent/'examples/synthetic_strategy_case.json').read_text(encoding='utf-8'))
class QA(unittest.TestCase):
    def case(self):return copy.deepcopy(BASE)
    def test_valid(self):self.assertEqual(check(self.case()),[])
    def test_nfc_literal_matching_on_either_side(self):
        import unicodedata
        for side in ('sources', 'claims'):
            x=self.case()
            fields = [('laws','source_excerpt'),('evidence','source_excerpt'),('evidence','exact_quote')] if side=='sources' else [
                ('laws','source'),('facts','text'),('paragraphs','quote')]
            for table,field in fields:
                for row in x[table]:
                    if field in row:row[field]=unicodedata.normalize('NFD',row[field])
            self.assertEqual(check(x),[],side)

    def test_short_literal_text_is_rejected_after_nfc(self):
        import unicodedata
        for table,field in [('facts','text'),('evidence','exact_quote'),('paragraphs','quote')]:
            for value in ('가', ' 가 \t', unicodedata.normalize('NFD','각')):
                x=self.case();x[table][0][field]=value
                self.assertIn('TEXT_TOO_SHORT:'+x[table][0]['id']+':'+field,check(x))

    def test_missing_fact_evidence(self):
        x=self.case();x['facts'][0]['evidence_ids']=['EV-MISSING'];self.assertTrue(any('MISSING_REF' in z for z in check(x)))
    def test_missing_adverse(self):
        x=self.case();x['issues'][0]['adverse_ids']=[];self.assertTrue(any('NO_ADVERSE_REVIEW' in z for z in check(x)))
    def test_weak_adverse_response(self):
        x=self.case();x['adverse'][0]['response']=' ';self.assertTrue(any('ADVERSE_FIELD_EMPTY' in z for z in check(x)))
    def test_unknown_law(self):
        x=self.case();x['laws'][0]['verified']=False;self.assertTrue(any('UNVERIFIED_LAW' in z for z in check(x)))
    def test_modified_quote(self):
        x=self.case();x['paragraphs'][0]['quote']='이미 입금 완료';self.assertTrue(any('QUOTE_MISMATCH' in z for z in check(x)))
    def test_modified_amount(self):
        x=self.case();x['paragraphs'][0]['amount_krw']=4500000;self.assertTrue(any('AMOUNT_MISMATCH' in z for z in check(x)))
    def test_unverified_evidence(self):
        x=self.case();x['evidence'][0]['verified']=False;self.assertTrue(any('UNVERIFIED_EVIDENCE' in z for z in check(x)))
    def test_missing_paragraph_adverse(self):
        x=self.case();x['paragraphs'][0]['adverse_ids']=[];self.assertTrue(any('PARAGRAPH_ADVERSE_UNREVIEWED' in z for z in check(x)))
    def test_duplicate_id(self):
        x=self.case();x['evidence'].append(copy.deepcopy(x['evidence'][0]));self.assertTrue(any('DUPLICATE_ID' in z for z in check(x)))
    def test_non_boolean_law_verification(self):
        x=self.case();x['laws'][0]['verified']='False'
        self.assertTrue(any('UNVERIFIED_LAW' in z for z in check(x)))
    def test_non_boolean_evidence_verification(self):
        x=self.case();x['evidence'][0]['verified']='yes'
        self.assertTrue(any('UNVERIFIED_EVIDENCE' in z for z in check(x)))
    def test_quote_without_source(self):
        x=self.case();x['evidence'][0].pop('exact_quote')
        self.assertTrue(any('NO_QUOTE_SOURCE' in z for z in check(x)))
    def test_amount_without_source(self):
        x=self.case();x['evidence'][0].pop('amount_krw')
        self.assertTrue(any('NO_AMOUNT_SOURCE' in z for z in check(x)))
    def test_unverified_adverse_evidence(self):
        x=self.case();x['evidence'][1]['verified']=False
        self.assertTrue(any('UNVERIFIED_EVIDENCE' in z for z in check(x)))

    def test_all_mandatory_types_required(self):
        for table in SCHEMA:
            if table not in OPTIONAL_COLLECTIONS:
                with self.subTest(table=table):
                    x=self.case();x.pop(table)
                    self.assertTrue(any(z.startswith('MISSING_NODE_TYPE:') for z in check(x)))

    def test_non_mapping_input(self):
        for value in (None, [], '', 0, False):
            with self.subTest(value=value):
                self.assertEqual(check(value), ['EMPTY_RECORD:root'])

    def test_invalid_ids_and_links_do_not_crash(self):
        for value in (None, {}, [], 1, True, ' '):
            with self.subTest(value=value):
                x=self.case();x['facts'][0]['id']=value
                self.assertTrue(any(z.startswith('INVALID_RECORD:') for z in check(x)))
                x=self.case();x['paragraphs'][0]['fact_ids']=[value]
                self.assertTrue(any(z.startswith('INVALID_LINK:') for z in check(x)))

    def test_paragraph_cannot_bypass_argument(self):
        x=self.case();x['arguments'][0]['evidence_ids']=[]
        self.assertTrue(any(z.startswith('FORWARD_COVERAGE_GAP:') for z in check(x)))

    def test_reverse_sources_must_match_facts(self):
        x=self.case();x['paragraphs'][0]['evidence_ids'].append('EV-02')
        self.assertTrue(any(z.startswith('REVERSE_COVERAGE_GAP:') for z in check(x)))

    def test_disconnected_subgraph(self):
        x=self.case()
        x['facts'].append({'id':'FACT-ORPHAN','evidence_ids':['EV-ORPHAN']})
        x['evidence'].append({'id':'EV-ORPHAN','verified':True})
        errors=check(x)
        self.assertIn('ORPHAN_NODE:FACT-ORPHAN', errors)
        self.assertIn('ORPHAN_NODE:EV-ORPHAN', errors)

    def test_audit_missing_affected_node(self):
        x=self.case();x['audits'][0]['target_ids'].remove('EV-02')
        self.assertIn('CHANGE_NOT_REAUDITED:CHG-01', check(x))

    def test_invalid_revision_cannot_reaudit(self):
        for value in (None, True, '1', 0, -1):
            with self.subTest(value=value):
                x=self.case();x['changes'][0]['revision']=value
                self.assertIn('CHANGE_NOT_REAUDITED:CHG-01', check(x))

    def test_audit_revision_must_be_integer(self):
        x=self.case();x['audits'][0]['change_revisions']['CHG-01']=True
        self.assertIn('CHANGE_NOT_REAUDITED:CHG-01', check(x))

    def test_failed_audit_cannot_close(self):
        x=self.case();x['audits'][0]['state']='FAIL'
        errors=check(x)
        self.assertIn('CHANGE_NOT_REAUDITED:CHG-01', errors)
        self.assertIn('TERMINATION_NO_EXIT:CHG-01', errors)

    def test_valid_rollback(self):
        x=self.case();x['changes'][0].update(state='ROLLED_BACK',rollback_state='COMPLETED')
        self.assertEqual(check(x), [])

    def test_incomplete_rollback(self):
        x=self.case();x['changes'][0].update(state='ROLLED_BACK',rollback_state='PENDING')
        self.assertIn('TERMINATION_STATE_MISSING:CHG-01', check(x))

    def test_cycle_with_exit(self):
        x=self.case();x['changes'][0]['next_change_ids']=['CHG-01']
        self.assertEqual(check(x), [])

    def test_multi_change_cycle_with_and_without_exit(self):
        x=self.case()
        other=copy.deepcopy(x['changes'][0]);other.update(id='CHG-02',state='OPEN',next_change_ids=['CHG-01'])
        x['changes'][0]['next_change_ids']=['CHG-02']
        x['changes'].append(other)
        x['audits'][0]['change_revisions']['CHG-02']=1
        self.assertEqual(check(x), [])
        x['audits'][0]['terminal']=False
        errors=check(x)
        for rid in ('CHG-01','CHG-02'):
            self.assertIn('CYCLE_WITHOUT_EXIT:'+rid, errors)

    def test_conditional_artifact_links(self):
        x=self.case();x['facts'][0].update(needs_visual=True,visual_ids=['VIS-01'])
        x['evidence'][0].update(needs_attachment=True,attachment_ids=['ATT-01'])
        self.assertEqual(check(x),[])
        x['facts'][0]['visual_ids']=[]
        self.assertIn('VISUAL_REQUIRED:FACT-01',check(x))

    def test_plain_change_needs_no_dummy_visual(self):
        x=self.case()
        for table in ('visuals','attachments'):x.pop(table)
        for key in ('visual_ids','attachment_ids'):x['paragraphs'][0].pop(key)
        for row in (x['changes'][0],x['audits'][0]):
            key='affected_ids' if 'affected_ids' in row else 'target_ids'
            row[key]=[rid for rid in row[key] if rid not in ('VIS-01','ATT-01')]
        self.assertEqual(check(x),[])

    def test_comma_formatted_amount_is_literal(self):
        x=self.case();x['evidence'][0]['source_excerpt']=x['evidence'][0]['source_excerpt'].replace('2500000','2,500,000')
        self.assertEqual(check(x),[])

    def test_null_amount_cannot_hide_unit_or_symbol_amounts(self):
        for excerpt in ('입금 확인 예정; 가상 금액 250만원.', '입금 확인 예정; 가상 금액 2억5천만 원.',
                        '입금 확인 예정; 가상 금액 ₩2,500,000.', '입금 확인 예정; 가상 금액 2,500,000 KRW.'):
            with self.subTest(excerpt=excerpt):
                x=self.case();x['evidence'][0].pop('amount_krw');x['evidence'][0]['source_excerpt']=excerpt
                x['paragraphs'][0].update(amount_krw=None,amount_not_applicable_reason='synthetic claim of no amount')
                self.assertIn('AMOUNT_MISMATCH:PAR-01',check(x))
        x=self.case();x['evidence'][0].pop('amount_krw');x['evidence'][0]['source_excerpt']='입금 확인 예정; 2026년 1월 2일 2쪽.'
        x['paragraphs'][0].update(amount_krw=None,amount_not_applicable_reason='synthetic message without an amount')
        self.assertNotIn('AMOUNT_MISMATCH:PAR-01',check(x))

    def test_unresolved_items_are_explicit_and_never_override_source_errors(self):
        x=self.case();x['unresolved']=['Synthetic missing bank confirmation.']
        self.assertEqual(check(x),[])
        x['laws'][0].pop('source')
        self.assertIn('LAW_SOURCE_MISSING:LAW-01',check(x))

    def test_unknown_node_fields_are_not_silently_accepted(self):
        x=self.case();x['facts'][0]['misspelled_source_field']='synthetic'
        self.assertIn('INVALID_RECORD:FACT-01:unknown:misspelled_source_field',check(x))

    def test_standalone_audit_respects_terminal_state(self):
        x=self.case();x.pop('changes')
        for table in ('visuals','attachments'):x[table][0].pop('change_ids')
        x['audits'][0]['change_revisions']={}
        self.assertEqual(check(x),[])
        x['audits'][0]['state']='FAIL'
        self.assertIn('AUDIT_NOT_CLOSED:QA-01',check(x))

    def test_audit_change_reference_must_exist(self):
        x=self.case();x['audits'][0]['change_revisions']['CHG-MISSING']=1
        self.assertIn('MISSING_REF:QA-01:change_revisions:CHG-MISSING',check(x))


def apply_fixture(fixture):
    """Apply explicit synthetic mutations; [] replaces the root record."""
    x=copy.deepcopy(BASE)
    for operation in fixture['operations']:
        path=operation['path']
        if not path:
            x=copy.deepcopy(operation['value'])
            continue
        parent=x
        for key in path[:-1]:
            parent=parent[key]
        if operation.get('remove'):
            del parent[path[-1]]
        else:
            parent[path[-1]]=copy.deepcopy(operation['value'])
    return x


class AdversarialFixtures(unittest.TestCase):
    pass


FIXTURE_DIR=Path(__file__).resolve().parents[1]/'examples/adversarial_strategy'
EXPECTED_CODES=json.loads((FIXTURE_DIR/'expected_codes.json').read_text(encoding='utf-8'))['cases']
FIXTURES=[dict(json.loads(p.read_text(encoding='utf-8')), _file=p.name)
          for p in sorted(FIXTURE_DIR.glob('*.json')) if p.name != 'expected_codes.json']


def fixture_test(fixture):
    def test(self):
        codes={error.split(':',1)[0] for error in check(apply_fixture(fixture))}
        self.assertEqual(codes, set(EXPECTED_CODES[fixture['_file']]))
        if fixture['expected_code'] is not None:
            self.assertIn(fixture['expected_code'], codes)
    return test


for fixture in FIXTURES:
    setattr(AdversarialFixtures, 'test_'+Path(fixture['_file']).stem, fixture_test(fixture))
if __name__=='__main__':unittest.main()
