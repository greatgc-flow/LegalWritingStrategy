#!/usr/bin/env python3
"""Deterministic synthetic linkage QA, NOT legal/evidentiary verification.

Input schema: issues,laws,evidence,facts,adverse,paragraphs (lists of dictionaries).
Alerts only to missing record references, unverified sources, mismatched explicit values,
and adversarial analysis blanks. Does not establish evidentiary admissibility or legal merits.
"""
import argparse,copy,json,sys
from pathlib import Path

def check(x):
    faults=[]
    def add(code,where): faults.append(f'{code}:{where}')
    def idx(k):
        es=x.get(k,[])
        if not isinstance(es,list):
            add('INVALID_COLLECTION',k);return {}
        ids={}
        for v in es:
            if not isinstance(v,dict) or not v.get('id'):add('INVALID_RECORD',k);continue
            if v['id'] in ids:add('DUPLICATE_ID',f'{k}:{v["id"]}')
            ids[v['id']]=v
        return ids
    d={k:idx(k) for k in ('issues','laws','evidence','facts','adverse','paragraphs')}
    for id_,i in d['issues'].items():
        for k,table in [('rule_ids','laws'),('fact_ids','facts'),('adverse_ids','adverse')]:
            for v in i.get(k,[]):
                if v not in d[table]:add('MISSING_REF',f'{id_}:{k}:{v}')
        if not i.get('adverse_ids'):add('NO_ADVERSE_REVIEW',id_)
    for id_,l in d['laws'].items():
        if not l.get('verified'): add('UNVERIFIED_LAW',id_)
    for id_,f in d['facts'].items():
        if not f.get('evidence_ids'):add('NO_EVIDENCE_LINK',id_)
        for k in f.get('evidence_ids',[]):
            if k not in d['evidence']:add('MISSING_REF',f'{id_}:evidence:{k}')
            elif not d['evidence'][k].get('verified'):add('UNVERIFIED_EVIDENCE',f'{id_}:{k}')
    for id_,a in d['adverse'].items():
        k=a.get('evidence_id')
        if k not in d['evidence']:add('MISSING_REF',f'{id_}:evidence:{k}')
        for name in ['strongest_reading','admitted_fact','response']:
            if not str(a.get(name,'')).strip():add('ADVERSE_FIELD_EMPTY',f'{id_}:{name}')
        if a.get('verification_state') != 'VERIFIED_SOURCE':add('ADVERSE_UNVERIFIED',id_)
    for id_,p in d['paragraphs'].items():
        for k,table in [('fact_ids','facts'),('evidence_ids','evidence'),('adverse_ids','adverse')]:
            for v in p.get(k,[]):
                if v not in d[table]:add('MISSING_REF',f'{id_}:{k}:{v}')
        if not p.get('adverse_ids'): add('PARAGRAPH_ADVERSE_UNREVIEWED',id_)
        if 'quote' in p:
            valid=[d['evidence'].get(z,{}).get('exact_quote') for z in p.get('evidence_ids',[])]
            if valid and p['quote'] not in valid:add('QUOTE_MISMATCH',id_)
        if 'amount_krw' in p:
            valid=[d['evidence'].get(z,{}).get('amount_krw') for z in p.get('evidence_ids',[]) if 'amount_krw' in d['evidence'].get(z,{})]
            if valid and p['amount_krw'] not in valid:add('AMOUNT_MISMATCH',id_)
    return sorted(set(faults))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--record',type=Path,required=True)
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    record=json.loads(a.record.read_text(encoding='utf-8'))
    faults=check(record)
    result={'status':'PASS_SYNTHETIC_LINKAGE' if not faults else 'FAIL_SYNTHETIC_LINKAGE',
           'issues':faults,'scope':'Only structural/synthetic checks. No proof of laws, actual evidence or legal merits.'}
    txt=json.dumps(result,ensure_ascii=False,indent=2)
    if a.out:
        a.out.parent.mkdir(exist_ok=True,parents=True)
        a.out.write_text(txt+'\n',encoding='utf-8')
    print(txt)
    return int(bool(faults))
if __name__=='__main__':sys.exit(main())
