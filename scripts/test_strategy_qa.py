#!/usr/bin/env python3
"""Unit tests on a fully fictional case. No real-law conclusions."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from strategy_qa import check
BASE=json.loads((Path(__file__).resolve().parent.parent/'examples/synthetic_strategy_case.json').read_text(encoding='utf-8'))
class QA(unittest.TestCase):
    def case(self):return copy.deepcopy(BASE)
    def test_valid(self):self.assertEqual(check(self.case()),[])
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
if __name__=='__main__':unittest.main()
