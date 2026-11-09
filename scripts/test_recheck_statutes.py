"""Offline, fictional statute-hash tests. No live network requests."""
import contextlib
import csv
import hashlib
import io
import shutil
import unittest
import unicodedata
import uuid
from datetime import date
from pathlib import Path

from recheck_statutes import article_hash, run, source_path

TEXT = '##### 제1조 (가상)\n\n가상 첫 규정.\n\n##### 제69조의4 (가상)\n\n가상 두 번째 규정.\n'


class StatuteRecheckTests(unittest.TestCase):
    def setUp(self):
        cache = Path(__file__).resolve().parent/'__pycache__'
        cache.mkdir(exist_ok=True)
        directory = (cache/('statute-test-'+uuid.uuid4().hex)).resolve()
        assert directory.is_relative_to(cache.resolve())
        directory.mkdir()
        self.addCleanup(shutil.rmtree, directory)
        self.ledger = directory/'ledger.csv'
        self.rows = [dict(id='ST0'+str(index), source='legalize-kr GitHub upstream kr/가상법/법률.md',
                          article=article, text_sha256=article_hash(TEXT,article),
                          checked_on='2000-01-01', recheck_by='2000-03-31', status='TEXT_MATCH')
                     for index, article in enumerate(('제1조','제69조의4'),1)]
        self.write()

    def write(self):
        output = io.StringIO()
        writer = csv.DictWriter(output,fieldnames=self.rows[0],lineterminator='\n')
        writer.writeheader()
        writer.writerows(self.rows)
        self.ledger.write_bytes(output.getvalue().encode('utf-8'))

    def inspect(self, fetcher=lambda path: TEXT, update=False):
        self.output = io.StringIO()
        with contextlib.redirect_stdout(self.output):
            return run(self.ledger,update,fetcher,today=date(2026,11,9))

    def test_matching_verify_is_read_only_and_caches_each_file(self):
        original = self.ledger.read_bytes()
        calls = []
        self.assertEqual(self.inspect(lambda path: calls.append(path) or TEXT),0)
        self.assertEqual(calls,['kr/가상법/법률.md'])
        self.assertEqual(self.ledger.read_bytes(),original)

    def test_update_renews_dates_only_after_all_match(self):
        self.assertEqual(self.inspect(update=True),0)
        with self.ledger.open(encoding='utf-8',newline='') as handle:
            rows = list(csv.DictReader(handle))
        for before, after in zip(self.rows,rows):
            self.assertEqual(after,{**before,'checked_on':'2026-11-09','recheck_by':'2027-02-07'})

    def test_late_mismatch_never_updates_any_row(self):
        original = self.ledger.read_bytes()
        self.assertEqual(self.inspect(lambda path:TEXT.replace('두 번째','변경된'),update=True),1)
        self.assertIn('FAIL ST02: hash mismatch',self.output.getvalue())
        self.assertEqual(self.ledger.read_bytes(),original)

    def test_fetch_failure_reports_each_row_and_writes_nothing(self):
        original = self.ledger.read_bytes()
        def unavailable(path):
            raise OSError('offline synthetic failure')
        self.assertEqual(self.inspect(unavailable,update=True),1)
        for rid in ('ST01','ST02'):self.assertIn('FAIL '+rid+': fetch failed',self.output.getvalue())
        self.assertEqual(self.ledger.read_bytes(),original)

    def test_missing_article_is_a_failure_without_update(self):
        original = self.ledger.read_bytes()
        self.assertEqual(self.inspect(lambda path:'##### 제1조 (가상)\n가상 첫 규정.\n',True),1)
        self.assertIn('FAIL ST02: missing or ambiguous article',self.output.getvalue())
        self.assertEqual(self.ledger.read_bytes(),original)

    def test_subarticle_is_exact_and_stops_at_next_heading(self):
        block = '##### 제69조의4 (가상)\n\n가상 규정.\n'
        text = '##### 제69조 (별개)\n앞 조문\n'+block+'\n##### 제70조 (다음)\n다음 조문\n'
        self.assertEqual(article_hash(text,'제69조의4'),hashlib.sha256(block.encode('utf-8')).hexdigest())

    def test_nfc_and_lf_are_reproducible(self):
        variant = unicodedata.normalize('NFD',TEXT).replace('\n','\r\n')
        self.assertEqual(article_hash(variant,'제69조의4'),article_hash(TEXT,'제69조의4'))

    def test_supplementary_repeated_article_is_excluded(self):
        self.assertEqual(article_hash(TEXT+'\n## 부칙\n##### 제1조 (부칙)\n별도 규정\n','제1조'),
                         article_hash(TEXT,'제1조'))
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            article_hash(TEXT+'\n##### 제1조 (중복)\n중복 규정\n','제1조')

    def test_invalid_hash_and_nonmatched_status_cannot_be_renewed(self):
        for changes in ({'text_sha256':''},{'status':'UNVERIFIED'}):
            self.rows[0].update(text_sha256=article_hash(TEXT,'제1조'),status='TEXT_MATCH')
            self.rows[0].update(changes)
            self.write()
            original = self.ledger.read_bytes()
            self.assertEqual(self.inspect(update=True),1)
            self.assertEqual(self.ledger.read_bytes(),original)

    def test_source_path_is_fixed_to_upstream_kr_markdown(self):
        self.assertEqual(source_path(self.rows[0]['source']),'kr/가상법/법률.md')
        for value in ('https://example.com/law.md','kr/../law.md','kr/law.txt'):
            with self.assertRaises(ValueError):source_path(value)


if __name__ == '__main__':
    unittest.main()
