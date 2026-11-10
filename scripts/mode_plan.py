#!/usr/bin/env python3
"""Validate the six-mode routing contract and print a plan; never runs an AI.

This command performs no case-file writes, network calls, evidence verification,
permission enforcement or submission. Required-input names are a checklist, not
proof that the user supplied or verified the corresponding evidence.
"""
import argparse
import json
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CATALOG = 'config/mode_catalog.json'
MODES = {'NEW', 'REVISE', 'REBUT', 'AUDIT', 'RESEARCH', 'COMPARE'}
REPORT_ONLY = {'AUDIT', 'RESEARCH', 'COMPARE'}
FIELDS = {'id', 'label', 'prompt', 'required_inputs', 'default_steps', 'write_scopes', 'outputs', 'editing'}


def strings(value):
    return (isinstance(value, list) and bool(value)
            and all(isinstance(v, str) and bool(v.strip()) for v in value)
            and len(value) == len(set(value)))


def require_path(root, value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('invalid local prompt path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != value:
        raise ValueError('prompt path escapes toolkit')
    target = root / value
    if not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError('missing/escaping prompt: ' + value)
    if target.suffix != '.md':
        raise ValueError('prompt must be Markdown')


def validate(catalog, root=ROOT):
    root = Path(root)
    if (not isinstance(catalog, dict) or set(catalog) != {'version', 'common_prompt', 'stages', 'modes'}
            or type(catalog['version']) is not int or catalog['version'] != 1):
        raise ValueError('invalid mode catalog contract')
    require_path(root, catalog['common_prompt'])
    stages = catalog['stages']
    expected = {f'P{i}' for i in range(9)} | {f'S{i}' for i in range(7)}
    if not isinstance(stages, dict) or set(stages) != expected:
        raise ValueError('stage map must contain P0..P8 and S0..S6')
    for value in stages.values():
        require_path(root, value)
    if len(set(stages.values())) != len(stages):
        raise ValueError('stage paths must be unique')
    rows = catalog['modes']
    if not isinstance(rows, list) or len(rows) != len(MODES):
        raise ValueError('exactly six modes required')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError('invalid mode fields')
        key = row['id']
        if not isinstance(key, str) or key not in MODES or key in seen:
            raise ValueError('unknown/duplicate mode')
        seen.add(key)
        if not isinstance(row['label'], str) or not row['label'].strip():
            raise ValueError('mode label required')
        if row['prompt'] != 'prompts/modes/' + key + '.md':
            raise ValueError('mode prompt mapping mismatch')
        require_path(root, row['prompt'])
        for field in ('required_inputs', 'default_steps', 'write_scopes', 'outputs'):
            if not strings(row[field]):
                raise ValueError('nonempty unique string list required: ' + field)
        if set(row['default_steps']) - stages.keys():
            raise ValueError('unknown stage')
        if not set(row['write_scopes']) <= {'drafts', 'reviews', 'runs'}:
            raise ValueError('unsafe case write scope')
        if key in REPORT_ONLY:
            if row['editing'] != 'report_only' or set(row['write_scopes']) != {'reviews', 'runs'}:
                raise ValueError('read-oriented mode may only create reports')
        elif (row['editing'] != ('copy_only' if key == 'REVISE' else 'new_draft')
              or set(row['write_scopes']) != {'drafts', 'reviews', 'runs'}):
            raise ValueError('draft mode must preserve original files')
        if key not in ('RESEARCH',) and 'P0' not in row['default_steps']:
            raise ValueError('original freeze stage missing')
        if not {'P8', 'S6'} & set(row['default_steps']):
            raise ValueError('final review stage missing')
    return catalog


def plan(catalog, mode):
    row = next((r for r in catalog['modes'] if r['id'] == mode), None)
    if row is None:
        raise ValueError('unknown mode')
    return {**row, 'common_prompt': catalog['common_prompt'],
            'stage_files': [catalog['stages'][step] for step in row['default_steps']],
            'plan_only': True, 'execution_result': 'NOT_TESTED',
            'scope': 'Routing plan only. No AI, case writes, legal verification or permission enforcement.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--mode', choices=sorted(MODES))
    args = parser.parse_args(argv)
    try:
        catalog = validate(json.loads((ROOT / CATALOG).read_text(encoding='utf-8')), ROOT)
        result = {'catalog_check': 'PASS', 'modes': sorted(MODES),
                  'scope': 'File links and routing contract only.'} if args.check else plan(catalog, args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print('FAIL mode plan: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
