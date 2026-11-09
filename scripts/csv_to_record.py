#!/usr/bin/env python3
"""Import CSV editing views into canonical SCHEMA JSON; never infer missing data.

STRATEGY_LINK uses collection,id and the union of canonical node field names.
ADVERSE_MATRIX contains adverse fields only. Lists, Booleans, integers, null,
and dictionaries use JSON cell syntax; strings retain their literal contents.
--base preserves root metadata (e.g. scope/unresolved), not old node collections.
"""
import argparse
import csv
import json
from pathlib import Path

from strategy_qa import SCHEMA, check, field_types, valid_type


def convert(strategy_path, adverse_path, base=None):
    if base is not None and not isinstance(base, dict):
        raise ValueError('--base must contain a JSON object')
    record = {key:value for key,value in (base or {}).items() if key not in SCHEMA}
    record.setdefault('unresolved', [])
    record.update({table:[] for table in SCHEMA})
    known = set().union(*(set(field_types(table)) for table in SCHEMA if table != 'adverse')) | {'collection'}
    for path, adverse in [(Path(strategy_path), False), (Path(adverse_path), True)]:
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            allowed = set(field_types('adverse')) if adverse else known
            required = {'id'} if adverse else {'collection', 'id'}
            if not reader.fieldnames or set(reader.fieldnames)-allowed or not required <= set(reader.fieldnames):
                raise ValueError(f'{path.name}: headers must use canonical SCHEMA field names')
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError(f'{path.name}: duplicate headers')
            for number, row in enumerate(reader, 2):
                if None in row:
                    raise ValueError(f'{path.name}:{number}: extra CSV cells')
                if not any(value and value.strip() for value in row.values()):
                    continue
                table = 'adverse' if adverse else (row.pop('collection', '') or '').strip()
                if table not in SCHEMA or (not adverse and table == 'adverse'):
                    raise ValueError(f'{path.name}:{number}: unknown collection')
                types, node = field_types(table), {}
                for field, value in row.items():
                    if value is None or not value.strip():
                        continue
                    if field not in types:
                        raise ValueError(f'{path.name}:{number}: {field} does not belong to {table}')
                    kind = types[field]
                    parsed = value if kind == 'str' else json.loads(value)
                    if not valid_type(parsed, kind):
                        raise ValueError(f'{path.name}:{number}: invalid type for {field}')
                    node[field] = parsed
                record[table].append(node)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strategy', type=Path, required=True)
    parser.add_argument('--adverse', type=Path, required=True)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = [args.strategy, args.adverse] + ([args.base] if args.base else [])
    if args.out.resolve() in {path.resolve() for path in inputs}:
        parser.error('--out must be distinct from the input files')
    try:
        base = json.loads(args.base.read_text(encoding='utf-8')) if args.base else None
        record = convert(args.strategy, args.adverse, base)
        faults = check(record)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.error(str(error))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'issues':faults, 'unresolved':record['unresolved']}, ensure_ascii=False, indent=2))
    return int(bool(faults))


if __name__ == '__main__':
    raise SystemExit(main())
