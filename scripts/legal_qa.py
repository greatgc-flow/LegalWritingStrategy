#!/usr/bin/env python3
"""Limited, deterministic legal-document QA. NOT a legal reasoning engine.

Checks synthetic fact/evidence links and optional DOCX/PDF formatting indicators.
Does NOT verify real laws, cases, evidence authenticity, or human comprehension.
"""
import argparse, json, re, sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check_record(record):
    from strategy_qa import check
    return check(record)


def check_docx(path, kind='civil', profile=None):
    """Inspect all sections/text runs and configured/used styles; no rendering QA.

    Body minimums cover text runs unless common.<story>_pt_min overrides them.
    Configured Title/Heading sizes are exact targets. Font preferences are advice.
    """
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.oxml.ns import qn
    from docx.shared import Length
    from docx.text.paragraph import Paragraph
    from docx.text.run import Run
    profile = profile or json.loads((ROOT/'config/style_profile.json').read_text(encoding='utf-8'))
    settings, common = profile[kind], profile['common']
    margins = settings['margin_mm' if kind == 'civil' else 'illustrative_margin_mm']
    minimum = settings['body_pt_min' if kind == 'civil' else 'illustrative_body_pt']
    targets = {'Title':common['title_pt'], 'Heading 1':common['heading1_pt'], 'Heading 2':common['heading2_pt']}
    spacing_policy = settings.get('line_spacing', common.get('line_spacing'))
    match = re.search(r'>=([0-9.]+)', spacing_policy or '')
    spacing_min = float(match[1]) if match else common.get('body_line_spacing_min')
    document, issues = Document(str(path)), []

    def add(code, location, actual, expected):
        issues.append(dict(code=code, location=location, actual=actual, expected=expected))

    paper = settings.get('paper', 'A4 portrait')
    expected_size = {'A4 portrait':[210,297], 'A4 landscape':[297,210]}.get(paper)
    if expected_size is None:
        add('PROFILE_PAPER', 'profile.'+kind+'.paper', paper, ['A4 portrait','A4 landscape'])

    def inherited(style, group, field):
        seen = set()
        while style is not None and style.style_id not in seen:
            seen.add(style.style_id)
            value = getattr(getattr(style, group, None), field, None)
            if value is not None:
                return value
            style = getattr(style, 'base_style', None)
        return None

    defaults = document.styles.element.xpath('./w:docDefaults/w:rPrDefault/w:rPr/w:sz')
    default_pt = float(defaults[0].get(qn('w:val')))/2 if defaults else 11

    def role(style):
        seen = set()
        while style is not None and style.style_id not in seen:
            seen.add(style.style_id)
            if style.name in targets:
                return style.name
            style = getattr(style, 'base_style', None)
        return None

    def check_size(points, location, style, context_min):
        name = role(style)
        expected = targets[name] if name else context_min
        if points is None or (abs(points-expected) > .05 if name else points < expected):
            add('FONT_SIZE', location, points, expected)

    def spacing_target(style, label=''):
        key = ('heading_line_spacing_min' if role(style) else 'header_line_spacing_min' if 'header' in label
               else 'footer_line_spacing_min' if 'footer' in label else 'body_line_spacing_min')
        return common.get(key, spacing_min)

    def check_spacing(value, location, required):
        if required is None:
            return
        if isinstance(value, Length):
            add('LINE_SPACING_RULE', location, value.pt, f'>={required} lines')
        elif (value if value is not None else 1.0) < required:
            add('LINE_SPACING', location, value, required)

    sections, stories = [], [('body', document, document.element.body)]
    for number, section in enumerate(document.sections, 1):
        label = f'section[{number}]'
        actual = {side: round(getattr(section, side+'_margin').mm, 2)
                  if getattr(section, side+'_margin') is not None else None for side in margins}
        for side, expected in margins.items():
            if actual[side] is None or abs(actual[side]-expected) > .2:
                add('MARGIN', label+'.'+side+'_margin', actual[side], expected)
        size = [round(value.mm, 2) if value is not None else None
                for value in (section.page_width, section.page_height)]
        if expected_size is not None and any(value is None or abs(value-expected) > .2 for value, expected in zip(size, expected_size)):
            add('PAGE_SIZE', label, size, expected_size)
        sections.append(dict(location=label, margins_mm=actual, size_mm=size))
        for name in ('header','first_page_header','even_page_header','footer','first_page_footer','even_page_footer'):
            story = getattr(section, name)
            stories.append((label+'.'+name, story, story._element))

    seen, runs, used, used_min, used_spacing = set(), [], set(), {}, {}
    for label, container, element in stories:
        if element in seen:
            continue
        seen.add(element)
        context_min = common.get('header_pt_min' if 'header' in label else
                                 'footer_pt_min' if 'footer' in label else 'body_pt_min', minimum)
        for number, p in enumerate(element.iter(qn('w:p')), 1):
            paragraph = Paragraph(p, container)
            if not any(r.find(qn('w:t')) is not None or r.find(qn('w:instrText')) is not None
                       for r in p.iter(qn('w:r'))):
                continue
            location = f'{label}.paragraph[{number}]'
            paragraph_min = common.get('table_pt_min', context_min) if any(
                parent.tag == qn('w:tbl') for parent in p.iterancestors()) else context_min
            for table in (parent for parent in p.iterancestors() if parent.tag == qn('w:tbl')):
                declared = table.xpath('./w:tblPr/w:tblStyle')
                table_style = document.styles.get_by_id(declared[0].get(qn('w:val')) if declared else None,
                                                         WD_STYLE_TYPE.TABLE)
                used.add(table_style.style_id)
                used_min[table_style.style_id] = paragraph_min
            used.add(paragraph.style.style_id)
            used_min[paragraph.style.style_id] = max(used_min.get(paragraph.style.style_id, 0), paragraph_min)
            spacing = paragraph.paragraph_format.line_spacing
            if spacing is None:
                spacing = inherited(paragraph.style, 'paragraph_format', 'line_spacing')
            spacing_required = spacing_target(paragraph.style, label)
            used_spacing[paragraph.style.style_id] = max(used_spacing.get(paragraph.style.style_id, 0), spacing_required or 0)
            check_spacing(spacing, location, spacing_required)
            for index, r in enumerate(p.iter(qn('w:r')), 1):
                # Nested text boxes have their own paragraph; inspect each run once.
                parent = r.getparent()
                while parent is not None and parent.tag != qn('w:p'):
                    parent = parent.getparent()
                if parent is not p:
                    continue
                run = Run(r, paragraph)
                if not run.text.strip() and r.find(qn('w:instrText')) is None:
                    continue
                used.add(run.style.style_id)
                used_min[run.style.style_id] = max(used_min.get(run.style.style_id, 0), paragraph_min)
                size = run.font.size
                if size is None:
                    size = inherited(run.style, 'font', 'size')
                if size is None:
                    size = inherited(paragraph.style, 'font', 'size')
                points = size.pt if size is not None else default_pt
                run_location = location+f'.run[{index}]'
                check_size(points, run_location, paragraph.style, paragraph_min)
                runs.append(dict(location=run_location, font_pt=points,
                                 font=run.font.name or inherited(run.style,'font','name') or
                                      inherited(paragraph.style,'font','name'), style=run.style.name))

    styles = []
    for style in document.styles:
        size = inherited(style, 'font', 'size')
        points = size.pt if size is not None else None
        styles.append(dict(name=style.name, font_pt=points, used=style.style_id in used))
        if style.name in {'Normal', *targets} or style.style_id in used:
            if points is not None or style.type == WD_STYLE_TYPE.PARAGRAPH:
                check_size(points if points is not None else default_pt, 'style['+style.name+']', style,
                           minimum if style.name == 'Normal' else used_min.get(style.style_id, minimum))
            if style.type == WD_STYLE_TYPE.PARAGRAPH:
                check_spacing(inherited(style,'paragraph_format','line_spacing'), 'style['+style.name+']',
                              used_spacing.get(style.style_id, spacing_target(style)))
    return dict(status='FAIL' if issues else 'PASS', sections=sections, runs=runs, styles=styles,
                issues=issues, scope='Profile checks for all sections/text runs and configured/used styles; unused styles inventoried. Rendering NOT_TESTED.')


def check_pdf(path):
    import pymupdf as fitz
    doc = fitz.open(str(path))
    mm = lambda x: round(x * 25.4 / 72, 1)
    pages = []
    for i, page in enumerate(doc):
        fonts = sorted({f[3] for f in page.get_fonts()})
        pages.append({'page': i+1, 'size_mm': [mm(page.rect.width), mm(page.rect.height)],
                      'text_chars': len(page.get_text()), 'fonts': fonts})
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', type=Path)
    ap.add_argument('--docx', type=Path)
    ap.add_argument('--pdf', type=Path)
    ap.add_argument('--kind', choices=['civil','criminal'], default='civil')
    ap.add_argument('--profile', type=Path)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    result = {'tool': 'legal_qa.py', 'scope': 'deterministic cross-file checks only',
              'legal_merits': 'NOT_TESTED', 'original_authenticity': 'NOT_TESTED'}
    if args.record:
        result['record_issues'] = check_record(json.loads(args.record.read_text(encoding='utf-8')))
    if args.docx:
        result['docx'] = check_docx(args.docx, args.kind, json.loads(args.profile.read_text(encoding='utf-8')) if args.profile else None)
    if args.pdf:
        result['pdf'] = check_pdf(args.pdf)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding='utf-8')
    print(text)
    return int(bool(result.get('record_issues') or result.get('docx', {}).get('issues')))

if __name__ == '__main__':
    sys.exit(main())
