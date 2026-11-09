#!/usr/bin/env python3
"""Structural synthetic QA only; never verifies legal merits or real evidence.

SCHEMA is the node/link contract. Link tuples are (target, required, forward).
SCALAR_FIELDS completes the typed canonical JSON fields. VIS/ATT/CHG/QA are
optional collections; references are always checked. FACT/EV needs_visual and
needs_attachment require their corresponding links. Plain traces end at PAR.
Locations/excerpts and paragraph anchors are required; text, quotes and amounts
must match supplied excerpts literally. A null paragraph amount needs a reason
and must not conceal a source amount. unresolved is an explicit string list;
it never suppresses errors. These checks do not authenticate external sources.
Unknown node fields are rejected. Independent QA requires terminal PASS; audit
revision-map keys must refer to existing changes.
False reverses a link for the R -> QA graph; 'support' contributes only to
semantic impact propagation; None is audit metadata.
CHG.changed_ids seeds an undirected semantic impact walk; affected_ids must
cover that walk. PASS audits must cover each affected ID at the CHG revision.
Workflow cycles are allowed only when every change can reach a closed PASS
audit. rollback_state records whether rollback was unnecessary or completed.

Accepted local states (not final case-disposition states):
  adverse.verification_state: VERIFIED_SOURCE only.
  changes.state: OPEN / CLOSED / ROLLED_BACK.
  changes.rollback_state: NOT_REQUIRED / PENDING / COMPLETED; CLOSED requires
    NOT_REQUIRED and ROLLED_BACK requires COMPLETED.
  audits.state: PASS / FAIL / REVIEW; terminal is a Boolean. A current PASS audit
    is required for re-audit coverage and a terminal PASS for a closed exit.
  laws.verified / evidence.verified: Boolean true only.
  facts.status: unvalidated metadata (no accepted-value restriction).
  CLI status: PASS_SYNTHETIC_LINKAGE / FAIL_SYNTHETIC_LINKAGE, diagnostic only.
"""
import argparse
import json
import re
import sys
from pathlib import Path


SCHEMA = {
    'requirements': ('R', {'issue_ids': ('issues', True, True)}),
    'issues': ('ISS', {'rule_ids': ('laws', True, True),
                       'fact_ids': ('facts', True, 'support'),
                       'adverse_ids': ('adverse', True, True)}),
    'laws': ('LAW', {'fact_ids': ('facts', True, True)}),
    'facts': ('FACT', {'evidence_ids': ('evidence', True, True),
                       'visual_ids': ('visuals', False, True), 'attachment_ids': ('attachments', False, True)}),
    'evidence': ('EV', {'visual_ids': ('visuals', False, True), 'attachment_ids': ('attachments', False, True)}),
    'arguments': ('ARG', {'evidence_ids': ('evidence', True, False),
                           'rule_ids': ('laws', True, 'support'),
                           'paragraph_ids': ('paragraphs', True, True)}),
    'paragraphs': ('PAR', {'fact_ids': ('facts', True, 'support'),
                            'evidence_ids': ('evidence', True, 'support'),
                            'adverse_ids': ('adverse', True, 'support'),
                            'visual_ids': ('visuals', False, True),
                            'attachment_ids': ('attachments', False, True),
                            'change_ids': ('changes', False, True)}),
    'visuals': ('VIS', {'change_ids': ('changes', False, True)}),
    'attachments': ('ATT', {'change_ids': ('changes', False, True)}),
    'changes': ('CHG', {'changed_ids': ('*', True, False),
                         'affected_ids': ('*', True, None),
                         'qa_ids': ('audits', True, True),
                         'next_change_ids': ('changes', False, True)}),
    'audits': ('QA', {'target_ids': ('*', True, False)}),
    # Ancillary adversarial analysis retained from the original record format.
    'adverse': ('ADV', {'evidence_id': ('evidence', True, True)}),
}
OPTIONAL_COLLECTIONS = {'visuals', 'attachments', 'changes', 'audits', 'adverse'}
# Scalar fields complete the canonical JSON schema and drive CSV conversion.
SCALAR_FIELDS = {
    'requirements': {}, 'issues': {},
    'laws': {'verified':'bool', 'source':'str', 'source_location':'str', 'source_excerpt':'str'},
    'facts': {'text':'str', 'status':'str', 'needs_visual':'bool', 'needs_attachment':'bool'},
    'evidence': {'verified':'bool', 'source_location':'str', 'source_excerpt':'str',
                 'exact_quote':'str', 'amount_krw':'nullable_int', 'needs_visual':'bool', 'needs_attachment':'bool'},
    'arguments': {},
    'paragraphs': {'quote':'str', 'amount_krw':'nullable_int', 'amount_not_applicable_reason':'str', 'draft_anchor':'str'},
    'visuals': {}, 'attachments': {},
    'changes': {'revision':'int', 'state':'str', 'rollback_state':'str'},
    'audits': {'state':'str', 'terminal':'bool', 'change_revisions':'dict'},
    'adverse': {'strongest_reading':'str', 'admitted_fact':'str', 'response':'str', 'verification_state':'str'},
}


def field_types(collection):
    return {'id':'str', **{field:('str' if field == 'evidence_id' else 'list')
                          for field in SCHEMA[collection][1]}, **SCALAR_FIELDS[collection]}


def valid_type(value, kind):
    return ((kind == 'nullable_int' and (value is None or type(value) is int)) or
            (kind == 'int' and type(value) is int) or
            (kind == 'bool' and type(value) is bool) or
            (kind in ('str', 'list', 'dict') and isinstance(value, {'str':str,'list':list,'dict':dict}[kind])))


def literal_amount(value, excerpt):
    return type(value) is int and any(re.search(r'(?<![\d,.\-])' + re.escape(text) +
        r'(?!\d|[,.]\d|[eE][+-]?\d)', excerpt) is not None for text in {str(value),format(value, ',')})
LINK_ERRORS = {
    ('issues', 'adverse_ids'): 'NO_ADVERSE_REVIEW',
    ('facts', 'evidence_ids'): 'NO_EVIDENCE_LINK',
    ('paragraphs', 'adverse_ids'): 'PARAGRAPH_ADVERSE_UNREVIEWED',
}


def walk(graph, starts):
    seen, pending = set(), list(starts)
    while pending:
        node = pending.pop()
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, ()))
    return seen


def check(record):
    faults = []

    def add(code, where):
        faults.append(f'{code}:{where}')

    if not isinstance(record, dict) or not record:
        return ['EMPTY_RECORD:root']
    tables, nodes, kinds = {}, {}, {}
    for table, (kind, _) in SCHEMA.items():
        rows = record.get(table, [])
        tables[table] = {}
        if not isinstance(rows, list):
            add('INVALID_COLLECTION', table)
            continue
        if not rows and table not in OPTIONAL_COLLECTIONS:
            add('MISSING_NODE_TYPE', kind)
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
                add('INVALID_RECORD', table)
                continue
            rid = row['id']
            for field in row.keys() - field_types(table).keys():
                add('INVALID_RECORD', f'{rid}:unknown:{field}')
            for field, kind in SCALAR_FIELDS[table].items():
                if field in row and not valid_type(row[field], kind):
                    add('INVALID_RECORD', f'{rid}:{field}')
            if rid in nodes:
                add('DUPLICATE_ID', rid)
                continue
            nodes[rid], kinds[rid], tables[table][rid] = row, table, row

    graph = {rid: set() for rid in nodes}
    impacts = {rid: set() for rid in nodes}
    links = {}
    for table, (_, fields) in SCHEMA.items():
        for rid, row in tables[table].items():
            for field, (target, required, direction) in fields.items():
                values = row.get(field, [] if field != 'evidence_id' else '')
                if field == 'evidence_id':
                    values = [values] if values else []
                if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                    add('INVALID_LINK', f'{rid}:{field}')
                    values = []
                if required and not values:
                    add(LINK_ERRORS.get((table, field), 'REQUIRED_LINK_MISSING'), f'{rid}:{field}')
                valid = set()
                for ref in values:
                    if ref not in (nodes if target == '*' else tables[target]):
                        add('MISSING_REF', f'{rid}:{field}:{ref}')
                        continue
                    valid.add(ref)
                    if direction in (True, False):
                        src, dst = (rid, ref) if direction else (ref, rid)
                        graph[src].add(dst)
                    if direction is not None and kinds[rid] not in ('changes', 'audits') and kinds[ref] not in ('changes', 'audits'):
                        impacts[rid].add(ref)
                        impacts[ref].add(rid)
                links[rid, field] = valid

    def refs(rid, field):
        return links.get((rid, field), set())

    unresolved = record.get('unresolved', [])
    if not isinstance(unresolved, list) or any(not isinstance(v, str) or not v.strip() for v in unresolved):
        add('INVALID_RECORD', 'unresolved')

    def nonblank(row, field):
        return isinstance(row.get(field), str) and bool(row[field].strip())

    for table in ('laws', 'evidence'):
        for rid, source in tables[table].items():
            if not nonblank(source, 'source_location'):
                add('SOURCE_LOCATION_MISSING', rid)
            if not nonblank(source, 'source_excerpt'):
                add('SOURCE_EXCERPT_MISSING', rid)
    for table in ('facts', 'evidence'):
        for rid, row in tables[table].items():
            if row.get('needs_visual') is True and not refs(rid, 'visual_ids'):
                add('VISUAL_REQUIRED', rid)
            if row.get('needs_attachment') is True and not refs(rid, 'attachment_ids'):
                add('ATTACHMENT_REQUIRED', rid)

    for rid, law in tables['laws'].items():
        if law.get('verified') is not True:
            add('UNVERIFIED_LAW', rid)
        if not nonblank(law, 'source'):
            add('LAW_SOURCE_MISSING', rid)
        elif not isinstance(law.get('source_excerpt'), str) or law['source'] not in law['source_excerpt']:
            add('LAW_SOURCE_MISMATCH', rid)
    for rid, evidence in tables['evidence'].items():
        if evidence.get('verified') is not True:
            add('UNVERIFIED_EVIDENCE', rid)
        excerpt = evidence.get('source_excerpt', '')
        if not isinstance(excerpt, str):
            excerpt = ''
        if 'exact_quote' in evidence and (not nonblank(evidence, 'exact_quote') or evidence['exact_quote'] not in excerpt):
            add('EVIDENCE_QUOTE_MISMATCH', rid)
        if evidence.get('amount_krw') is not None and not literal_amount(evidence['amount_krw'], excerpt):
            add('EVIDENCE_AMOUNT_MISMATCH', rid)
    for rid, fact in tables['facts'].items():
        sources = [nodes[e].get('source_excerpt', '') for e in refs(rid, 'evidence_ids')]
        if not nonblank(fact, 'text'):
            add('FACT_TEXT_MISSING', rid)
        elif not any(isinstance(text, str) and fact['text'] in text for text in sources):
            add('FACT_TEXT_MISMATCH', rid)
    for rid, adverse in tables['adverse'].items():
        for name in ('strongest_reading', 'admitted_fact', 'response'):
            value = adverse.get(name)
            if not isinstance(value, str) or not value.strip():
                add('ADVERSE_FIELD_EMPTY', f'{rid}:{name}')
        if adverse.get('verification_state') != 'VERIFIED_SOURCE':
            add('ADVERSE_UNVERIFIED', rid)
    for rid, paragraph in tables['paragraphs'].items():
        if not nonblank(paragraph, 'draft_anchor'):
            add('DRAFT_ANCHOR_MISSING', rid)
        fact_sources = set().union(*(refs(f, 'evidence_ids') for f in refs(rid, 'fact_ids')))
        if not refs(rid, 'fact_ids') or not fact_sources or fact_sources != refs(rid, 'evidence_ids'):
            add('REVERSE_COVERAGE_GAP', rid)
        sources = [nodes[e] for e in refs(rid, 'evidence_ids')]
        if not nonblank(paragraph, 'quote'):
            add('PARAGRAPH_QUOTE_MISSING', rid)
        else:
            values = [e['exact_quote'] for e in sources if isinstance(e.get('exact_quote'), str) and e['exact_quote']]
            if not values:
                add('NO_QUOTE_SOURCE', rid)
            elif paragraph['quote'] not in values:
                add('QUOTE_MISMATCH', rid)
            if not any(isinstance(e.get('source_excerpt'), str) and paragraph['quote'] in e['source_excerpt'] for e in sources):
                add('QUOTE_EXCERPT_MISMATCH', rid)
        if 'amount_krw' not in paragraph:
            add('PARAGRAPH_AMOUNT_MISSING', rid)
        elif paragraph['amount_krw'] is None:
            if not nonblank(paragraph, 'amount_not_applicable_reason'):
                add('AMOUNT_APPLICABILITY_MISSING', rid)
            if any(e.get('amount_krw') is not None or (isinstance(e.get('source_excerpt'), str) and
                   re.search(r'\d[\d,]*\s*(?:원|KRW)', e['source_excerpt'])) for e in sources):
                add('AMOUNT_MISMATCH', rid)
        else:
            values = [e['amount_krw'] for e in sources if 'amount_krw' in e]
            if not values:
                add('NO_AMOUNT_SOURCE', rid)
            elif paragraph['amount_krw'] not in values:
                add('AMOUNT_MISMATCH', rid)
            if not any(isinstance(e.get('source_excerpt'), str) and literal_amount(paragraph['amount_krw'], e['source_excerpt']) for e in sources):
                add('AMOUNT_EXCERPT_MISMATCH', rid)

    reverse = {rid: set() for rid in nodes}
    for src, destinations in graph.items():
        for dst in destinations:
            reverse[dst].add(src)
    reached = walk(graph, tables['requirements'])
    drafted = walk(reverse, tables['paragraphs'])
    for rid in tables['requirements']:
        if rid not in drafted:
            add('FORWARD_COVERAGE_GAP', rid)
    for rid in nodes:
        if rid not in reached or (kinds[rid] not in OPTIONAL_COLLECTIONS and rid not in drafted):
            add('ORPHAN_NODE', rid)

    semantic = {rid for rid in nodes if kinds[rid] not in ('changes', 'audits')}
    workflow = {rid: refs(rid, 'next_change_ids') for rid in tables['changes']}
    exits = set()
    linked_audits = set().union(*(refs(rid, 'qa_ids') for rid in tables['changes']))
    for rid, audit in tables['audits'].items():
        if audit.get('state') not in ('PASS', 'FAIL', 'REVIEW') or type(audit.get('terminal')) is not bool:
            add('TERMINATION_STATE_MISSING', rid)
        if rid not in linked_audits and (audit.get('state') != 'PASS' or audit.get('terminal') is not True):
            add('AUDIT_NOT_CLOSED', rid)
        revisions = audit.get('change_revisions', {})
        if isinstance(revisions, dict):
            for change_id in revisions:
                if change_id not in tables['changes']:
                    add('MISSING_REF', f'{rid}:change_revisions:{change_id}')
    for rid, change in tables['changes'].items():
        state, rollback = change.get('state'), change.get('rollback_state')
        if (state not in ('OPEN', 'CLOSED', 'ROLLED_BACK') or
                rollback not in ('NOT_REQUIRED', 'PENDING', 'COMPLETED') or
                (state == 'CLOSED' and rollback != 'NOT_REQUIRED') or
                (state == 'ROLLED_BACK' and rollback != 'COMPLETED')):
            add('TERMINATION_STATE_MISSING', rid)
        seeds, affected = refs(rid, 'changed_ids'), refs(rid, 'affected_ids')
        if not seeds or not affected or (seeds | affected) - semantic:
            add('CHANGE_SCOPE_INVALID', rid)
        expected = walk(impacts, seeds & semantic)
        if expected - affected:
            add('CHANGE_PROPAGATION_GAP', f'{rid}:{",".join(sorted(expected - affected))}')
        revision = change.get('revision')
        revision_valid = type(revision) is int and revision > 0
        covered = set()
        for qid in refs(rid, 'qa_ids'):
            audit = nodes[qid]
            revisions = audit.get('change_revisions', {})
            version = revisions.get(rid) if isinstance(revisions, dict) else None
            current = revision_valid and type(version) is int and version == revision
            if current and audit.get('state') == 'PASS':
                covered.update(refs(qid, 'target_ids'))
                if audit.get('terminal') is True and ((state == 'CLOSED' and rollback == 'NOT_REQUIRED') or
                                                        (state == 'ROLLED_BACK' and rollback == 'COMPLETED')):
                    exits.add(rid)
        if not revision_valid or not affected or affected - covered:
            add('CHANGE_NOT_REAUDITED', rid)
    for rid in workflow:
        reachable = walk(workflow, [rid])
        if not reachable & exits:
            add('TERMINATION_NO_EXIT', rid)
            if any(rid in walk(workflow, [n]) for n in workflow[rid]):
                add('CYCLE_WITHOUT_EXIT', rid)
    return sorted(set(faults))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding='utf-8'))
    faults = check(record)
    result = {'status': 'PASS_SYNTHETIC_LINKAGE' if not faults else 'FAIL_SYNTHETIC_LINKAGE',
              'issues': faults,
              'unresolved': record.get('unresolved', []) if isinstance(record, dict) else [],
              'scope': 'Only structural/synthetic checks. No proof of laws, actual evidence or legal merits.'}
    txt = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(exist_ok=True, parents=True)
        args.out.write_text(txt + '\n', encoding='utf-8')
    print(txt)
    return int(bool(faults))


if __name__ == '__main__':
    sys.exit(main())
