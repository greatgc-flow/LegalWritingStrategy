"""Seven regression tests on synthetic data. These are not legal truth tests."""
import sys, json, copy, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from legal_qa import check_record
root = Path(__file__).resolve().parents[1]
base = json.loads((root / 'examples/synthetic_case.json').read_text(encoding='utf-8'))

class TestLegalQA(unittest.TestCase):
    def test_clean(self): self.assertEqual(check_record(base), [])
    def test_missing_fact_evidence_link(self):
        x=copy.deepcopy(base);x['facts'][0]['evidence_ids']=[]
        self.assertTrue(any('NO_EVIDENCE_LINK' in e for e in check_record(x)))
    def test_missing_evidence_reference(self):
        x=copy.deepcopy(base);x['facts'][0]['evidence_ids']=['EV-999']
        self.assertTrue(any('MISSING_EVIDENCE' in e for e in check_record(x)))
    def test_unverified_evidence(self):
        x=copy.deepcopy(base);x['evidence'][0]['verified']=False
        self.assertTrue(any('NOT_VERIFIED' in e for e in check_record(x)))
    def test_quote_mismatch(self):
        x=copy.deepcopy(base);x['paragraphs'][0]['quote']='완료했다'
        self.assertTrue(any('QUOTE_MISMATCH' in e for e in check_record(x)))
    def test_amount_mismatch(self):
        x=copy.deepcopy(base);x['paragraphs'][1]['amount_krw']=1200000
        self.assertTrue(any('AMOUNT_MISMATCH' in e for e in check_record(x)))
    def test_missing_fact(self):
        x=copy.deepcopy(base);x['paragraphs'][0]['fact_ids']=['FACT-999']
        self.assertTrue(any('MISSING_FACT' in e for e in check_record(x)))

if __name__ == '__main__': unittest.main(verbosity=2)
