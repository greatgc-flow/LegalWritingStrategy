"""Lossless canonical JSON/CSV node round trips; all case data are fictional."""
import contextlib
import copy
import csv
import io
import json
import shutil
import unittest
import uuid
from pathlib import Path

from csv_to_record import convert, main
from strategy_qa import SCHEMA, check, field_types

ROOT = Path(__file__).resolve().parents[1]


class CSVImport(unittest.TestCase):
    def setUp(self):
        cache = ROOT/'scripts/__pycache__'
        cache.mkdir(exist_ok=True)
        self.root = (cache/('csv-case-'+uuid.uuid4().hex)).resolve()
        assert self.root.is_relative_to(cache.resolve())
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.base = json.loads((ROOT/'examples/synthetic_strategy_case.json').read_text(encoding='utf-8'))
        self.strategy, self.adverse = self.root/'strategy.csv', self.root/'adverse.csv'

    def export(self, record):
        for target, template, tables in [(self.strategy, 'STRATEGY_LINK_빈양식.csv', [k for k in SCHEMA if k!='adverse']),
                                         (self.adverse, 'ADVERSE_MATRIX_빈양식.csv', ['adverse'])]:
            with (ROOT/'templates'/template).open(encoding='utf-8', newline='') as handle:
                headers=next(csv.reader(handle))
            with target.open('w', encoding='utf-8', newline='') as handle:
                writer=csv.DictWriter(handle, headers, lineterminator='\n');writer.writeheader()
                for table in tables:
                    for node in record.get(table, []):
                        row={key:(value if field_types(table)[key]=='str' else json.dumps(value,ensure_ascii=False))
                             for key,value in node.items()}
                        if table!='adverse':row['collection']=table
                        writer.writerow(row)

    def test_round_trip_preserves_nodes_types_and_metadata(self):
        self.export(self.base)
        imported=convert(self.strategy,self.adverse,self.base)
        self.assertEqual(imported,self.base)
        self.assertEqual(check(imported),[])

    def test_plain_brief_round_trip(self):
        record=copy.deepcopy(self.base)
        for table in ('visuals','attachments','changes','audits'):record[table]=[]
        for paragraph in record['paragraphs']:
            paragraph.pop('visual_ids',None);paragraph.pop('attachment_ids',None)
        record['unresolved']=['Synthetic issue retained for human review.']
        self.export(record)
        imported=convert(self.strategy,self.adverse,record)
        self.assertEqual(imported,record)
        self.assertEqual(check(imported),[])

    def test_second_canonical_example_round_trip(self):
        record=json.loads((ROOT/'examples/synthetic_case.json').read_text(encoding='utf-8'))
        for table in SCHEMA:record.setdefault(table,[])
        self.export(record)
        imported=convert(self.strategy,self.adverse,record)
        self.assertEqual(imported,record)
        self.assertEqual(check(imported),[])

    def test_false_is_not_coerced_to_true(self):
        self.base['evidence'][0]['verified']=False
        self.export(self.base)
        imported=convert(self.strategy,self.adverse)
        self.assertIs(imported['evidence'][0]['verified'],False)
        self.assertTrue(any(p.startswith('UNVERIFIED_EVIDENCE:') for p in check(imported)))

    def test_unknown_headers_rejected(self):
        self.export(self.base)
        self.strategy.write_text('collection,id,legacy_field\nfacts,FACT-01,fictional\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'headers'):
            convert(self.strategy,self.adverse)

    def test_fields_from_another_collection_rejected(self):
        self.export(self.base)
        self.strategy.write_text('collection,id,quote\nfacts,FACT-01,fictional\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'does not belong'):
            convert(self.strategy,self.adverse)

    def test_cli_round_trip_and_distinct_output(self):
        self.export(self.base)
        original=self.root/'base.json';original.write_text(json.dumps(self.base),encoding='utf-8')
        output=self.root/'imported.json'
        args=['--strategy',str(self.strategy),'--adverse',str(self.adverse),'--base',str(original)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args+['--out',str(output)]),0)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')),self.base)
        before=original.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(args+['--out',str(original)])
        self.assertEqual(original.read_bytes(),before)


if __name__=='__main__':unittest.main()
