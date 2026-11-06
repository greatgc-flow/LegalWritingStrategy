#!/usr/bin/env python3
"""Limited, deterministic legal-document QA. NOT a legal reasoning engine.

Checks synthetic fact/evidence links and optional DOCX/PDF formatting indicators.
Does NOT verify real laws, cases, evidence authenticity, or human comprehension.
"""
import argparse, json, sys
from pathlib import Path


def check_record(record):
    issues = []
    ev = {x['id']: x for x in record.get('evidence', [])}
    facts = {x['id']: x for x in record.get('facts', [])}
    for f in record.get('facts', []):
        if not f.get('evidence_ids'):
            issues.append(f"{f['id']}: NO_EVIDENCE_LINK")
        for eid in f.get('evidence_ids', []):
            if eid not in ev:
                issues.append(f"{f['id']}: MISSING_EVIDENCE {eid}")
            elif not ev[eid].get('verified'):
                issues.append(f"{f['id']}: EVIDENCE_NOT_VERIFIED {eid}")
    for p in record.get('paragraphs', []):
        for fid in p.get('fact_ids', []):
            if fid not in facts:
                issues.append(f"{p['id']}: MISSING_FACT {fid}")
        for eid in p.get('evidence_ids', []):
            if eid not in ev:
                issues.append(f"{p['id']}: MISSING_EVIDENCE {eid}")
            else:
                if 'quote' in p and 'exact_quote' in ev[eid] and p['quote'] != ev[eid]['exact_quote']:
                    issues.append(f"{p['id']}: QUOTE_MISMATCH {eid}")
                if 'amount_krw' in p and 'amount_krw' in ev[eid] and p['amount_krw'] != ev[eid]['amount_krw']:
                    issues.append(f"{p['id']}: AMOUNT_MISMATCH {eid}")
    return sorted(set(issues))


def check_docx(path):
    from docx import Document
    d = Document(str(path))
    s = d.sections[0]
    mm = lambda x: round(x.mm, 1)
    return {
       'paragraphs': len(d.paragraphs), 'tables': len(d.tables),
       'margins_mm': {'top': mm(s.top_margin), 'bottom': mm(s.bottom_margin),
                      'left': mm(s.left_margin), 'right': mm(s.right_margin)},
       'normal_font_pt': d.styles['Normal'].font.size.pt if d.styles['Normal'].font.size else None,
       'normal_line_spacing': d.styles['Normal'].paragraph_format.line_spacing,
       'warning': 'Styles only; other runs/sections and output render require inspection'
    }


def check_pdf(path):
    import fitz
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
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    result = {'tool': 'legal_qa.py', 'scope': 'deterministic cross-file checks only',
              'legal_merits': 'NOT_TESTED', 'original_authenticity': 'NOT_TESTED'}
    if args.record:
        result['record_issues'] = check_record(json.loads(args.record.read_text(encoding='utf-8')))
    if args.docx:
        result['docx'] = check_docx(args.docx)
    if args.pdf:
        result['pdf'] = check_pdf(args.pdf)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding='utf-8')
    print(text)
    return 1 if result.get('record_issues') else 0

if __name__ == '__main__':
    sys.exit(main())
