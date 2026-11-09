#!/usr/bin/env python3
"""Structural synthetic QA only; never verifies legal merits or real evidence.

SCHEMA is the node/link contract. Link tuples are (target, required, forward).
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
import sys
from pathlib import Path


SCHEMA = {
    'requirements': ('R', {'issue_ids': ('issues', True, True)}),
    'issues': ('ISS', {'rule_ids': ('laws', True, True),
                       'fact_ids': ('facts', True, 'support'),
                       'adverse_ids': ('adverse', True, True)}),
    'laws': ('LAW', {'fact_ids': ('facts', True, True)}),
    'facts': ('FACT', {'evidence_ids': ('evidence', True, True)}),
    'evidence': ('EV', {}),
    'arguments': ('ARG', {'evidence_ids': ('evidence', True, False),
                           'rule_ids': ('laws', True, 'support'),
                           'paragraph_ids': ('paragraphs', True, True)}),
    'paragraphs': ('PAR', {'fact_ids': ('facts', True, 'support'),
                            'evidence_ids': ('evidence', True, 'support'),
                            'adverse_ids': ('adverse', True, 'support'),
                            'visual_ids': ('visuals', True, True),
                            'attachment_ids': ('attachments', True, True)}),
    'visuals': ('VIS', {'change_ids': ('changes', True, True)}),
    'attachments': ('ATT', {'change_ids': ('changes', True, True)}),
    'changes': ('CHG', {'changed_ids': ('*', True, None),
                         'affected_ids': ('*', True, None),
                         'qa_ids': ('audits', True, True),
                         'next_change_ids': ('changes', False, True)}),
    'audits': ('QA', {'target_ids': ('*', True, None)}),
    # Ancillary adversarial analysis retained from the original record format.
    'adverse': ('ADV', {'evidence_id': ('evidence', True, True)}),
}
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
        if not rows and table != 'adverse':
            add('MISSING_NODE_TYPE', kind)
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
                add('INVALID_RECORD', table)
                continue
            rid = row['id']
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

    for rid, law in tables['laws'].items():
        if law.get('verified') is not True:
            add('UNVERIFIED_LAW', rid)
    for rid, evidence in tables['evidence'].items():
        if evidence.get('verified') is not True:
            add('UNVERIFIED_EVIDENCE', rid)
    for rid, adverse in tables['adverse'].items():
        for name in ('strongest_reading', 'admitted_fact', 'response'):
            value = adverse.get(name)
            if not isinstance(value, str) or not value.strip():
                add('ADVERSE_FIELD_EMPTY', f'{rid}:{name}')
        if adverse.get('verification_state') != 'VERIFIED_SOURCE':
            add('ADVERSE_UNVERIFIED', rid)
    for rid, paragraph in tables['paragraphs'].items():
        fact_sources = set().union(*(refs(f, 'evidence_ids') for f in refs(rid, 'fact_ids')))
        if not refs(rid, 'fact_ids') or not fact_sources or fact_sources != refs(rid, 'evidence_ids'):
            add('REVERSE_COVERAGE_GAP', rid)
        sources = [nodes[e] for e in refs(rid, 'evidence_ids')]
        if 'quote' in paragraph:
            values = [e['exact_quote'] for e in sources if isinstance(e.get('exact_quote'), str) and e['exact_quote']]
            if not values:
                add('NO_QUOTE_SOURCE', rid)
            elif paragraph['quote'] not in values:
                add('QUOTE_MISMATCH', rid)
        if 'amount_krw' in paragraph:
            values = [e['amount_krw'] for e in sources if 'amount_krw' in e]
            if not values:
                add('NO_AMOUNT_SOURCE', rid)
            elif paragraph['amount_krw'] not in values:
                add('AMOUNT_MISMATCH', rid)

    reverse = {rid: set() for rid in nodes}
    for src, destinations in graph.items():
        for dst in destinations:
            reverse[dst].add(src)
    reached = walk(graph, tables['requirements'])
    audited = walk(reverse, tables['audits'])
    for rid in tables['requirements']:
        if rid not in audited:
            add('FORWARD_COVERAGE_GAP', rid)
    for rid in nodes:
        if rid not in reached or rid not in audited:
            add('ORPHAN_NODE', rid)

    semantic = {rid for rid in nodes if kinds[rid] not in ('changes', 'audits')}
    workflow = {rid: refs(rid, 'next_change_ids') for rid in tables['changes']}
    exits = set()
    for rid, audit in tables['audits'].items():
        if audit.get('state') not in ('PASS', 'FAIL', 'REVIEW') or type(audit.get('terminal')) is not bool:
            add('TERMINATION_STATE_MISSING', rid)
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
    faults = check(json.loads(args.record.read_text(encoding='utf-8')))
    result = {'status': 'PASS_SYNTHETIC_LINKAGE' if not faults else 'FAIL_SYNTHETIC_LINKAGE',
              'issues': faults,
              'scope': 'Only structural/synthetic checks. No proof of laws, actual evidence or legal merits.'}
    txt = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(exist_ok=True, parents=True)
        args.out.write_text(txt + '\n', encoding='utf-8')
    print(txt)
    return int(bool(faults))


if __name__ == '__main__':
    sys.exit(main())
