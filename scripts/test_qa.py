"""Regression tests on synthetic data. These are not legal truth tests."""
import sys, json, copy, unittest, shutil, subprocess, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from legal_qa import check_record, check_docx
root = Path(__file__).resolve().parents[1]
base = json.loads((root / 'examples/synthetic_case.json').read_text(encoding='utf-8'))

class TestLegalQA(unittest.TestCase):
    def test_clean(self): self.assertEqual(check_record(base), [])
    def test_missing_fact_evidence_link(self):
        x=copy.deepcopy(base);x['facts'][0]['evidence_ids']=[]
        self.assertTrue(any('NO_EVIDENCE_LINK' in e for e in check_record(x)))
    def test_missing_evidence_reference(self):
        x=copy.deepcopy(base);x['facts'][0]['evidence_ids']=['EV-999']
        self.assertTrue(any('MISSING_REF' in e for e in check_record(x)))
    def test_unverified_evidence(self):
        x=copy.deepcopy(base);x['evidence'][0]['verified']=False
        self.assertTrue(any('UNVERIFIED_EVIDENCE' in e for e in check_record(x)))
    def test_quote_mismatch(self):
        x=copy.deepcopy(base);x['paragraphs'][0]['quote']='완료했다'
        self.assertTrue(any('QUOTE_MISMATCH' in e for e in check_record(x)))
    def test_amount_mismatch(self):
        x=copy.deepcopy(base);x['paragraphs'][1]['amount_krw']=1200000
        self.assertTrue(any('AMOUNT_MISMATCH' in e for e in check_record(x)))
    def test_missing_fact(self):
        x=copy.deepcopy(base);x['paragraphs'][0]['fact_ids']=['FACT-999']
        self.assertTrue(any('MISSING_REF' in e for e in check_record(x)))

class TestDocxQA(unittest.TestCase):
    def setUp(self):
        from docx import Document
        from docx.shared import Mm, Pt
        cache=root/'scripts/__pycache__';cache.mkdir(exist_ok=True)
        self.directory=(cache/('docx-qa-'+uuid.uuid4().hex)).resolve()
        assert self.directory.is_relative_to(cache.resolve())
        self.directory.mkdir();self.addCleanup(shutil.rmtree,self.directory)
        self.path=self.directory/'synthetic.docx'
        self.profile=json.loads((root/'config/style_profile.json').read_text(encoding='utf-8'))
        self.document=Document()
        self.document.styles['Normal'].font.size=Pt(12)
        self.document.styles['Normal'].paragraph_format.line_spacing=1.5
        for name,key in [('Title','title_pt'),('Heading 1','heading1_pt'),('Heading 2','heading2_pt')]:
            self.document.styles[name].font.size=Pt(self.profile['common'][key])
        self.document.add_paragraph('Fully fictional brief paragraph.')
        self.set_sections()

    def set_sections(self,kind='civil'):
        from docx.shared import Mm
        margins=self.profile[kind]['margin_mm' if kind=='civil' else 'illustrative_margin_mm']
        for section in self.document.sections:
            section.page_width=Mm(210);section.page_height=Mm(297)
            for side,value in margins.items():setattr(section,side+'_margin',Mm(value))

    def inspect(self,kind='civil'):
        self.document.save(self.path)
        return check_docx(self.path,kind,self.profile)

    def test_all_sections_tables_headers_and_footers_pass(self):
        self.document.add_section();self.document.add_paragraph('Second fictional section.')
        self.document.add_table(rows=1,cols=1).cell(0,0).text='Fictional table.'
        self.document.sections[0].header.paragraphs[0].text='Fictional header.'
        self.document.sections[0].footer.paragraphs[0].text='Fictional footer.'
        self.set_sections()
        result=self.inspect()
        self.assertEqual(result['issues'],[])
        self.assertEqual(len(result['sections']),2)
        self.assertTrue(any('.header.' in item['location'] for item in result['runs']))
        self.assertTrue(any('.footer.' in item['location'] for item in result['runs']))
        self.assertGreaterEqual(len(result['runs']),5)

    def test_second_section_margin_violation(self):
        from docx.shared import Mm
        self.document.add_section();self.set_sections()
        self.document.sections[1].top_margin=Mm(10)
        self.assertTrue(any(item['location']=='section[2].top_margin' for item in self.inspect()['issues']))

    def test_direct_run_font_violation(self):
        from docx.shared import Pt
        self.document.paragraphs[0].runs[0].font.size=Pt(8)
        self.assertTrue(any(item['code']=='FONT_SIZE' and '.run[' in item['location'] for item in self.inspect()['issues']))

    def test_inherited_style_violation(self):
        from docx.enum.style import WD_STYLE_TYPE
        from docx.shared import Pt
        style=self.document.styles.add_style('SyntheticSmall',WD_STYLE_TYPE.PARAGRAPH)
        style.base_style=self.document.styles['Normal'];style.font.size=Pt(8)
        self.document.paragraphs[0].style=style
        issues=self.inspect()['issues']
        self.assertTrue(any(item['location']=='style[SyntheticSmall]' for item in issues))
        self.assertTrue(any('.run[' in item['location'] for item in issues))

    def test_header_footer_and_table_font_violations(self):
        from docx.shared import Pt
        self.document.sections[0].header.paragraphs[0].add_run('header').font.size=Pt(6)
        self.document.sections[0].footer.paragraphs[0].add_run('footer').font.size=Pt(6)
        self.document.add_table(rows=1,cols=1).cell(0,0).paragraphs[0].add_run('table').font.size=Pt(6)
        locations=[item['location'] for item in self.inspect()['issues'] if item['code']=='FONT_SIZE']
        self.assertTrue(any('.header.' in p for p in locations))
        self.assertTrue(any('.footer.' in p for p in locations))
        self.assertTrue(any(p.startswith('body.') for p in locations))

    def test_applied_table_style_is_checked(self):
        from docx.enum.style import WD_STYLE_TYPE
        from docx.shared import Pt
        style=self.document.styles.add_style('SyntheticTable',WD_STYLE_TYPE.TABLE)
        style.font.size=Pt(6)
        table=self.document.add_table(rows=1,cols=1);table.style=style;table.cell(0,0).text='Fictional table.'
        self.assertTrue(any(item['location']=='style[SyntheticTable]' for item in self.inspect()['issues']))

    def test_hyperlink_run_is_checked(self):
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        link=OxmlElement('w:hyperlink');run=OxmlElement('w:r');properties=OxmlElement('w:rPr')
        size=OxmlElement('w:sz');size.set(qn('w:val'),'16');properties.append(size)
        text=OxmlElement('w:t');text.text='Fictional hyperlink'
        run.append(properties);run.append(text);link.append(run)
        self.document.paragraphs[0]._p.append(link)
        self.assertTrue(any(item['code']=='FONT_SIZE' and item['actual']==8 for item in self.inspect()['issues']))

    def test_field_instruction_run_is_checked(self):
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        run=OxmlElement('w:r');properties=OxmlElement('w:rPr')
        size=OxmlElement('w:sz');size.set(qn('w:val'),'12');properties.append(size)
        instruction=OxmlElement('w:instrText');instruction.text=' PAGE '
        run.append(properties);run.append(instruction)
        self.document.sections[0].footer.paragraphs[0]._p.append(run)
        self.assertTrue(any(item['code']=='FONT_SIZE' and '.footer.' in item['location'] for item in self.inspect()['issues']))

    def test_line_spacing_violation(self):
        self.document.paragraphs[0].paragraph_format.line_spacing=1.0
        self.assertTrue(any(item['code']=='LINE_SPACING' for item in self.inspect()['issues']))

    def test_configured_style_size_violation(self):
        from docx.shared import Pt
        self.document.styles['Heading 1'].font.size=Pt(10)
        self.assertTrue(any(item['location']=='style[Heading 1]' for item in self.inspect()['issues']))

    def test_criminal_profile(self):
        self.set_sections('criminal')
        self.assertEqual(self.inspect('criminal')['issues'],[])

    def test_page_orientation_follows_profile(self):
        from docx.shared import Mm
        self.profile['civil']['paper']='A4 landscape'
        self.document.sections[0].page_width=Mm(297);self.document.sections[0].page_height=Mm(210)
        self.assertEqual(self.inspect()['issues'],[])

    def test_unsupported_profile_paper_is_not_silently_accepted(self):
        self.profile['civil']['paper']='Letter'
        self.assertTrue(any(item['code']=='PROFILE_PAPER' for item in self.inspect()['issues']))

    def test_docx_violation_changes_cli_exit_code(self):
        from docx.shared import Pt
        self.document.paragraphs[0].runs[0].font.size=Pt(6);self.document.save(self.path)
        result=subprocess.run([sys.executable,str(root/'scripts/legal_qa.py'),'--docx',str(self.path)],
                              capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['docx']['status'],'FAIL')


if __name__ == '__main__': unittest.main(verbosity=2)
