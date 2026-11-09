#!/usr/bin/env python3
"""Create editable example legal-document templates. All substantive data are synthetic."""
import json
from pathlib import Path
from docx import Document
from docx.shared import Pt, Mm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'templates'
OUT.mkdir(exist_ok=True)

def set_font(style, name, size):
    style.font.name=name
    style.font.size=Pt(size)
    rpr=style.element.get_or_add_rPr()
    rfonts=rpr.rFonts
    if rfonts is None:
        rfonts=OxmlElement('w:rFonts');rpr.insert(0,rfonts)
    for tag in ('ascii','hAnsi','eastAsia','cs'):
        rfonts.set(qn('w:'+tag), name)

def make_doc(is_civil=True):
    profile=json.loads((ROOT/'config/style_profile.json').read_text(encoding='utf-8'))
    d=Document()
    sec=d.sections[0]
    sec.page_width=Mm(210); sec.page_height=Mm(297)
    margins=profile['civil']['margin_mm'] if is_civil else profile['criminal']['illustrative_margin_mm']
    for side in ('top','bottom','left','right'):
        setattr(sec,side+'_margin',Mm(margins[side]))
    if is_civil:
        font='Noto Sans CJK KR'
    else:
        font='Noto Serif CJK KR'
    st=d.styles['Normal'];set_font(st,font,12);st.paragraph_format.line_spacing=1.5
    st.paragraph_format.space_after=Pt(2)
    for sty,siz in [('Title',16),('Heading 1',14),('Heading 2',12)]:
        set_font(d.styles[sty],font,siz)
        d.styles[sty].font.bold=True
    d.core_properties.title='가상 법률서면 템플릿: 제출 금지'
    d.core_properties.subject='교육용 빈서식, 실제 제출 불가'
    d.core_properties.author=''
    d.core_properties.keywords='synthetic, template'
    hdr=sec.header.paragraphs[0]
    hdr.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    run=hdr.add_run('가상 예시 · 실제 사건에 제출 금지')
    run.font.name=font;run.font.size=Pt(9);run.font.color.rgb=RGBColor(120,130,140)
    title='민사 준비서면 (빈 서식·작성 예시)' if is_civil else '수사기관 제출 의견서 (빈 서식·작성 예시)'
    d.add_paragraph(title,'Title').alignment=WD_ALIGN_PARAGRAPH.CENTER
    d.add_paragraph('※ 교육용 구조 예시입니다. 실제 사건 내용·절차요건·제출기관 지정서식·법령 적용 여부를 별도로 확인하십시오.')
    if is_civil:
        for txt in ['사건: [사건번호 및 사건명]   제출법원: [관할 확인]', '원고: [인명/대리인]   피고: [인명/대리인]']:
            d.add_paragraph(txt)
        d.add_paragraph('1. 이번 준비서면의 쟁점','Heading 1')
        d.add_paragraph('[이번에 추가 또는 다투는 쟁점을 두세 문장으로 설명. 이미 제출한 사실의 불필요한 반복을 피함.]')
        d.add_paragraph('2. 요건사실 및 증거','Heading 1')
        d.add_paragraph('[LAW-001] 적용 법률과 행위 시점 확인. [FACT-001] 주장 사실과 [EV-001] 원본 위치를 구체적으로 적음.')
        d.add_paragraph('3. 상대방 항변과 검토','Heading 1')
        d.add_paragraph('[상대방 주장의 정확한 취지] / [이에 대한 근거와 증거의 한계]')
        d.add_paragraph('4. 결론 및 증거방법','Heading 1')
        d.add_paragraph('[법률적 요청과 필요한 증거의 위치를 기재]')
        fname='민사_A4_reference.docx'
    else:
        for txt in ['사건: [사건번호]', '제출기관: [경찰서/검찰청]', '제출자 지위: [신청인/피해자 등 확인]']:
            d.add_paragraph(txt)
        d.add_paragraph('1. 제출 취지','Heading 1')
        d.add_paragraph('[실제 신청 지위·기한·취지를 확인하고 기재]')
        d.add_paragraph('2. 확인된 사실과 증거','Heading 1')
        d.add_paragraph('가상 예시: 갑이 을에게 “완료”라는 메시지를 보낸 사실은 메시지 원본에 표시됩니다(EV-001, 2쪽). 이 문구만으로 실제 송금 사실이나 승인자를 특정할 수는 없습니다.')
        d.add_paragraph('3. 법률요건 및 반론','Heading 1')
        d.add_paragraph('[구성요건별 대응 사실 / 반대증거 / 미확인 사항을 기재]')
        d.add_paragraph('4. 구체적인 조사 요청','Heading 1')
        d.add_paragraph('[누구에게/어떤 원본을/어떤 시점을 확인해야 하는가]')
        fname='형사_의견서_가상서식.docx'
    d.add_paragraph('증거 대응표 (행/열/단위/출처 확인)','Heading 2')
    t=d.add_table(rows=1, cols=3)
    t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.style='Table Grid'
    # Keep each table row intact; subsequent visual QA must inspect page breaks.
    for row in t.rows:
        rowPr=row._tr.get_or_add_trPr()
        e=OxmlElement('w:cantSplit');rowPr.append(e)
    for cell, txt in zip(t.rows[0].cells,['쟁점','직접 근거','미확인 사항']): cell.text=txt
    trPr=t.rows[0]._tr.get_or_add_trPr(); head=OxmlElement('w:tblHeader');head.set(qn('w:val'),'true');trPr.append(head)
    for cells in [('ISS-001','EV-001 원본 2쪽','실제 실행 여부'),('ISS-002','EV-002 원본 1쪽','지시자 여부')]:
        r=t.add_row()
        for c,val in zip(r.cells,cells):
            c.text=val;c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.name=font;r.font.size=Pt(11)
    d.add_paragraph('작성일: [YYYY-MM-DD]    제출자: [서명 또는 날인 요구 확인]')
    foot=sec.footer.paragraphs[0]
    foot.alignment=WD_ALIGN_PARAGRAPH.CENTER
    rr=foot.add_run('교육용 템플릿 — 원본·법령·접수형식 검수 전 제출 금지')
    rr.font.name=font;rr.font.size=Pt(8)
    d.save(OUT/fname)
    return OUT/fname

if __name__=='__main__':
    for civil in (True,False): print(make_doc(civil))
