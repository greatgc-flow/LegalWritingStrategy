#!/usr/bin/env python3
"""Frozen structural rubric; stdlib only. No legal or scientific certification.

--probe is an internal determinism worker: it explicitly defers unit-suite and
determinism checks to its parent, earns neither row, and can never exit zero.
This bounds self-reference without treating unexecuted checks as successful.
"""
import argparse
import ast
import contextlib
import csv
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FINAL_STATES = {'READY_FOR_HUMAN_REVIEW', 'NEEDS_VERIFICATION', 'SUBMISSION_BLOCKED'}
EXCLUDED = [
    'Full tracing of real-case facts and evidence',
    'Legal expert and police/prosecutor/judge reader evaluation',
    'HWP desktop installation on physical hardware',
    'Full-text methodology appraisal of all 53 papers',
    'Judgment outcomes',
]


class Audit:
    def __init__(self, root=ROOT, probe=False):
        self.root, self.probe = Path(root).resolve(), probe
        self.cache = {}

    def text(self, relative):
        return (self.root / relative).read_text(encoding='utf-8-sig')

    def rows(self, relative):
        return list(csv.DictReader(io.StringIO(self.text(relative))))

    def files(self):
        verifier = self.module('verify_package')
        return sorted(p for p in self.root.rglob('*') if p.is_file()
                      and verifier.tracked(p.relative_to(self.root)))

    def module(self, name):
        if name not in self.cache:
            spec = importlib.util.spec_from_file_location(name, self.root / 'scripts' / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.cache[name] = module
        return self.cache[name]

    def run(self, arguments, timeout=60, unit_worker=False):
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PIP_NO_INPUT='1')
        if unit_worker:
            env['LWS_SCORE_UNIT_WORKER'] = '1'
        return subprocess.run([sys.executable, *arguments], cwd=self.root, env=env,
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=timeout)

    def package_issues(self):
        if 'package_issues' not in self.cache:
            verifier = self.module('verify_package')
            with contextlib.redirect_stdout(io.StringIO()):
                verifier.main([])
            self.cache['package_issues'] = list(verifier.issues)
        return self.cache['package_issues']

    def fixtures(self):
        base = json.loads(self.text('examples/synthetic_strategy_case.json'))
        result = []
        for path in sorted((self.root / 'examples/adversarial_strategy').glob('*.json')):
            if path.name == 'expected_codes.json':
                continue
            fixture = json.loads(path.read_text(encoding='utf-8'))
            value = json.loads(json.dumps(base))
            for operation in fixture['operations']:
                keys = operation['path']
                if not keys:
                    value = operation['value']
                    continue
                parent = value
                for key in keys[:-1]:
                    parent = parent[key]
                if operation.get('remove'):
                    del parent[keys[-1]]
                else:
                    parent[keys[-1]] = operation['value']
            errors = self.module('strategy_qa').check(value)
            result.append((path.name, fixture['expected_code'], {e.split(':', 1)[0] for e in errors}))
        return result


def single_ssot(a):
    documents = sorted((a.root / 'docs').rglob('*.md'))
    problems, contents = [], []
    for path in a.files():
        relative = path.relative_to(a.root)
        if any(re.search(r'(?:^|[_-])V[34](?:[._-]|$)', part, re.I) for part in relative.parts):
            problems.append('obsolete name: ' + relative.as_posix())
    for path in documents:
        relative = path.relative_to(a.root).as_posix()
        lines = {line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()}
        for previous, other in contents:
            if lines and other and len(lines & other) / min(len(lines), len(other)) >= .9:
                problems.append(f'90% duplicate: {previous} / {relative}')
        contents.append((relative, lines))
    if len(list((a.root / 'docs').glob('00_*.md'))) != 1:
        problems.append('exactly one docs/00 master required')
    return problems


def stage_ids(a):
    problems = []
    for directory, letter, count in [('prompts', 'P', 9), ('prompts/strategy', 'S', 7)]:
        for number in range(count):
            if len(list((a.root / directory).glob(f'{letter}{number}_*.md'))) != 1:
                problems.append(f'{letter}{number}: expected one stage')
    trace = [p.relative_to(a.root).as_posix() for p in sorted((a.root / 'references').glob('*.csv'))
             if 'Requirement_ID' in next(csv.reader(io.StringIO(a.text(p.relative_to(a.root)))), [])]
    if len(trace) != 1:
        problems.append('exactly one Requirement_ID ledger required')
    for relative, column in [('references/research_register.csv', 'id'),
                             ('references/statute_ledger.csv', 'id'),
                             *[(path, 'Requirement_ID') for path in trace]]:
        ids = [row.get(column, '').strip() for row in a.rows(relative)]
        if not ids or not all(ids) or len(ids) != len(set(ids)):
            problems.append('empty/duplicate IDs: ' + relative)
    return problems


def links_paths(a):
    return [p for p in a.package_issues() if p.startswith(('BROKEN_MARKDOWN_LINK:', 'BROKEN_REPO_PATH:'))]


def reachability(a):
    """Follow explicit file paths; mentioning a directory never links its contents."""
    required = {p.relative_to(a.root).as_posix() for folder in ('docs', 'prompts', 'templates', 'config')
                for p in (a.root / folder).rglob('*') if p.is_file()}
    paths = {p.relative_to(a.root).as_posix() for p in a.files()}
    pending = ['README.md', 'AGENTS.md', *sorted(p for p in required if p.startswith('docs/00_'))]
    seen = set()
    while pending:
        relative = pending.pop()
        if relative in seen:
            continue
        seen.add(relative)
        path = a.root / relative
        if path.suffix.lower() not in ('.md', '.txt', '.json', '.csv'):
            continue
        text = a.text(relative)
        # Full repo paths in prose/code, plus ordinary relative Markdown links.
        for target in re.findall(r'(?:docs|prompts|templates|config)/[^\s`<>|()\[\]"\']+', text):
            if target in paths:
                pending.append(target)
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            target = unquote(target.strip('<>').split('#', 1)[0].split('?', 1)[0])
            dest = (path.parent / target).resolve()
            if dest.is_relative_to(a.root) and dest.is_file():
                pending.append(dest.relative_to(a.root).as_posix())
    return ['unreachable: ' + p for p in sorted(required - seen)]


def synthetic_cases(a):
    strategy = a.module('strategy_qa').check(json.loads(a.text('examples/synthetic_strategy_case.json')))
    legal = a.module('legal_qa').check_record(json.loads(a.text('examples/synthetic_case.json')))
    return ['strategy: ' + p for p in strategy] + ['legal: ' + p for p in legal]


def error_codes(a):
    module = a.module('strategy_qa')
    expected = set(module.LINK_ERRORS.values())
    tree = ast.parse(a.text('scripts/strategy_qa.py'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'add':
            argument = node.args[0]
            if isinstance(argument, ast.Call):
                argument = argument.args[-1]  # LINK_ERRORS.get(..., default)
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                expected.add(argument.value)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.List):
            for item in node.value.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str) and ':' in item.value:
                    expected.add(item.value.split(':', 1)[0])
    fixtures = a.fixtures()
    declared = [code for _, code, _ in fixtures]
    manifest = json.loads(a.text('examples/adversarial_strategy/expected_codes.json'))['cases']
    names = {name for name, _, _ in fixtures}
    problems = ['missing fixture: ' + code for code in sorted(expected - set(declared))]
    if names != set(manifest):
        problems.append('expected-codes manifest does not cover exactly the fixture files')
    for name, code, actual in fixtures:
        codes = manifest.get(name, [])
        if not isinstance(codes, list) or not all(isinstance(value, str) for value in codes):
            problems.append('invalid expected code list: ' + name)
            continue
        if len(codes) != len(set(codes)) or actual != set(codes) or code not in actual:
            problems.append('exact expected code set differs: ' + name)
    problems.extend('unknown fixture code: ' + code for code in sorted(set(declared) - expected))
    return problems


def node_schema(a):
    schema = a.module('strategy_qa').SCHEMA
    expected = {'R', 'ISS', 'LAW', 'FACT', 'EV', 'ARG', 'PAR', 'VIS', 'ATT', 'CHG', 'QA'}
    kinds = {kind for kind, _ in schema.values()}
    problems = ['missing node kind: ' + kind for kind in sorted(expected - kinds)]
    connected = set()
    for table, (kind, fields) in schema.items():
        for field, (target, required, direction) in fields.items():
            if target != '*' and target not in schema:
                problems.append(f'invalid target: {table}.{field}')
            if required:
                connected.add(kind)
                if target in schema:
                    connected.add(schema[target][0])
    problems.extend('no required connection: ' + kind for kind in sorted(expected - connected))
    return problems


def recursive_termination(a):
    required = {'CHANGE_PROPAGATION_GAP', 'CHANGE_NOT_REAUDITED', 'TERMINATION_STATE_MISSING',
                'TERMINATION_NO_EXIT', 'CYCLE_WITHOUT_EXIT'}
    fixtures = a.fixtures()
    tested = {code for _, code, actual in fixtures if code in actual}
    problems = ['missing failing recursive fixture: ' + code for code in sorted(required - tested)]
    if not any(name == 'rollback_incomplete.json' and 'TERMINATION_STATE_MISSING' in actual
               for name, _, actual in fixtures):
        problems.append('missing failing rollback_incomplete.json fixture')
    return problems


def unit_tests(a):
    if a.probe:
        return ['NOT_TESTED: parent runs the complete unit suite']
    result = a.run(['-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_*.py'],
                   timeout=240, unit_worker=True)
    failures = re.findall(r'^(?:FAIL|ERROR): (.+)$', result.stderr, re.M)
    return [] if result.returncode == 0 else [
        f'unit suite failed (exit={result.returncode}): ' + ', '.join(sorted(failures))]


def rule_test_mapping(a):
    rules = dict(re.findall(r'^([1-7])\.\s+(.+)$', a.text('AGENTS.md'), re.M))
    covered, problems = set(), []
    for row in a.rows('references/rule_test_map.csv'):
        rid = row.get('rule_id', '').removeprefix('R')
        name, location = row.get('test_or_gate', ''), row.get('location', '')
        if rid not in rules or row.get('rule') != rules.get(rid):
            problems.append('rule text mismatch: ' + rid)
        tree = ast.parse(a.text(location))
        if name in GATES or name in CRITERIA:
            function = (GATES.get(name) or CRITERIA.get(name)).__name__
            exists = any(isinstance(n, ast.FunctionDef) and n.name == function for n in tree.body)
        else:
            parts = name.split('.')
            exists = len(parts) == 3 and parts[0] == Path(location).stem and any(
                isinstance(n, ast.ClassDef) and n.name == parts[1] and any(
                    isinstance(m, ast.FunctionDef) and m.name == parts[2] for m in n.body)
                for n in tree.body)
        if not exists:
            problems.append('missing test/gate: ' + name)
        else:
            covered.add(rid)
    problems.extend('unmapped rule: ' + rid for rid in sorted(set('1234567') - covered))
    return problems


ITEM_RESULTS = {'PASS', 'FAIL', 'REVIEW', 'NOT_TESTED'}  # per-check results, not final states (docs/18)


def markdown_tables(text):
    """Yield (line number, header cells, row cells) for ordinary pipe tables."""
    lines = text.splitlines()
    def cells(line):
        return [cell.strip() for cell in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
    for index in range(len(lines)-1):
        if not lines[index].lstrip().startswith('|'):
            continue
        headers, separator = cells(lines[index]), cells(lines[index+1])
        if len(headers) != len(separator) or not all(re.fullmatch(r':?-+:?', v) for v in separator):
            continue
        number = index+2
        while number < len(lines) and lines[number].lstrip().startswith('|'):
            yield number+1, headers, cells(lines[number])
            number += 1


def final_states(a):
    problems, found = [], set()
    marker = re.compile(r'상태|판정|결과|등급')
    token = r'[A-Z][A-Z0-9_]{1,}'
    run = re.compile(r'`?' + token + r'`?(?:\s*[/,]\s*`?' + token + r'`?)+')
    table_run = re.compile(r'`?' + token + r'`?(?:\s*\|\s*`?' + token + r'`?)+')
    nonstates = {kind for kind, _ in a.module('strategy_qa').SCHEMA.values()} | {
        'REQ', 'ID', 'AI', 'API', 'OCR', 'PDF', 'DOCX', 'HWP', 'XLSX',
        'SHA', 'EXIF', 'DOI', 'TACL', 'ELM', 'CGP', 'PNAS'}
    for path in a.files():
        if path.suffix not in ('.md', '.py', '.json'):
            continue
        relative = path.relative_to(a.root).as_posix()
        content = relative.split('/')[0] in ('docs', 'qa', 'prompts')
        headings = {}
        text = a.text(relative)
        lines = text.splitlines()
        if content:
            for number, headers, cells in markdown_tables(text):
                for index, header in enumerate(headers):
                    if re.search(r'결과|판정|상태', header):
                        value = cells[index].strip('`* ') if index < len(cells) else ''
                        tag = (not value or re.fullmatch(r'[\w/.-]+', value) or
                               re.fullmatch(r'[A-Z0-9_/ .()-]+', value) or
                               re.match(r'^[A-Z][A-Z0-9_]*\s*\(', value) or
                               re.match(r'^\d+\s*/\s*\d+', value))
                        identifier = value in nonstates or re.fullmatch(r'[A-Z]{1,4}\d+', value)
                        if tag and not identifier and value not in ITEM_RESULTS | FINAL_STATES:
                            problems.append(f'invalid result cell: {relative}:{number}: {value}')
        for number, line in enumerate(lines, 1):
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                headings = {depth: title for depth, title in headings.items() if depth < level}
                headings[level] = line
            nearest = list(headings.values())[-1] if headings else ''
            context = ' '.join(lines[max(0, number-3):number+1]) + ' ' + ' '.join(headings.values())
            groups = [set(re.findall(token, match[0])) for match in run.finditer(line)]
            if marker.search(line.strip('|').split('|')[0]):
                groups.extend(set(re.findall(token, match[0])) for match in table_run.finditer(line))
            quoted = [part for part in re.findall(r'`([^`]+)`', line)
                      if re.fullmatch(token, part)]
            if len(quoted) >= 2:
                groups.append(set(quoted))
            listed = marker.search(nearest) and re.match(r'\s*\d+[.)]\s+`', line)
            if listed:
                groups.append(set(quoted))
            if content and marker.search(context):
                for states in groups:
                    # File formats, bibliographic acronyms and ID columns are
                    # not state values; every other uppercase enum is checked.
                    states = {v for v in states if v not in nonstates and not v.endswith('_ID')
                              and not re.fullmatch(r'[A-Z]{1,4}\d+', v)}
                    if not states or (len(states) < 2 and not listed):
                        continue
                    found.update(states & FINAL_STATES)
                    extra = states - FINAL_STATES - ITEM_RESULTS
                    if extra:
                        problems.append(f'competing status enum: {relative}:{number}: ' +
                                        ','.join(sorted(extra)))
            if re.search(r'최종\s*(?:상태|판정값)[\s*`]*(?:은|는|:|=)|["\']?final_status["\']?\s*[:=]', line, re.I):
                states = set(re.findall(token, line.split('. 실제')[0]))
                if line.startswith('#'):
                    continue
                found.update(states & FINAL_STATES)
                if states - FINAL_STATES:
                    problems.append(f'invalid final state: {relative}:{number}: ' +
                                    ','.join(sorted(states - FINAL_STATES)))
    if found != FINAL_STATES:
        problems.append('final-state declarations incomplete')
    return problems


def bibliography_identity(a):
    rows = a.rows('references/research_register.csv')
    return ['bad doi_check: ' + row.get('id', '') for row in rows
            if not (re.fullmatch(r'crossref_\d{4}-\d{2}-\d{2}', row.get('doi_check', ''))
                    if row.get('doi', '').strip() else row.get('doi_check') == 'no_doi')]


def grade_scope(a):
    document = next((a.root / 'docs').glob('05_*.md')).relative_to(a.root)
    definition = next(line for line in a.text(document).splitlines() if '허용값:' in line)
    scopes = set(re.findall(r'`([A-Za-z_]+)`', definition.split('허용값:', 1)[1].split('등급 A', 1)[0]))
    return ['invalid grade/scope: ' + row.get('id', '') for row in a.rows('references/research_register.csv')
            if row.get('evidence_grade') not in set('ABCD') or row.get('verification_scope') not in scopes]


def statute_citations(a):
    article = r'제\s*\d+\s*조(?:\s*의\s*\d+)?'
    citation = re.compile(r'([가-힣]+(?:법|규칙|령))」?\s*(' + article + r'(?:\s*[/·,]\s*' + article + r')*)')
    citations = {}
    for directory, pattern in [('docs', '*.md'), ('prompts', '*.md'), ('qa', '*.md'), ('config', '*.json')]:
        for path in sorted((a.root / directory).rglob(pattern)):
            relative = path.relative_to(a.root).as_posix()
            for law, articles in citation.findall(a.text(relative)):
                for value in re.findall(article, articles):
                    citations.setdefault((law, re.sub(r'\s+', '', value)), set()).add(relative)
    return citations


def statute_ledger(a):
    available = {}
    problems = []
    today = date.today()
    for row in a.rows('references/statute_ledger.csv'):
        value = row.get('recheck_by', '')
        try:
            recheck_by = date.fromisoformat(value)
            if recheck_by.isoformat() != value:
                raise ValueError('expected YYYY-MM-DD')
        except (TypeError, ValueError):
            problems.append(f'NEEDS_VERIFICATION: invalid recheck_by: {row.get("id")}: {value}')
            continue
        if recheck_by < today:
            problems.append(f'NEEDS_VERIFICATION: expired recheck_by: {row.get("id")}: {value}')
            continue
        if re.search(r'not\s+reproduced|absent|재현\s*안', row.get('note', ''), re.I):
            problems.append(f'not reproduced: {row.get("law")} {row.get("article")}')
            continue
        try:
            date.fromisoformat(row.get('checked_on', ''))
        except ValueError:
            continue
        if row.get('status') == 'TEXT_MATCH':
            key = row.get('law'), row.get('article')
            available.setdefault(key, set()).update(part.strip() for part in row.get('cited_in', '').split(';') if part.strip())
    for (law, article), files in sorted(statute_citations(a).items()):
        if (law, article) not in available:
            problems.append(f'missing TEXT_MATCH/date: {law} {article}')
        else:
            for relative in sorted(files - available[law, article]):
                problems.append(f'missing cited_in: {law} {article}: {relative}')
    return sorted(set(problems))


def transfer_limits(a):
    problems = ['missing transfer_limit: ' + row.get('id', '')
                for row in a.rows('references/research_register.csv') if not row.get('transfer_limit', '').strip()]
    paths = [*sorted((a.root / 'docs').glob('14_*.md')), *sorted((a.root / 'prompts').glob('P2_*.md'))]
    text = '\n'.join(a.text(p.relative_to(a.root)) for p in paths)
    if not re.search(r'제출\s*(?:직전|시점)[^\n]{0,100}(?:재확인|다시 확인)', text):
        problems.append('no submission-time legal currency recheck instruction in docs/14 or prompts/P2')
    return problems


def package_integrity(a):
    return a.package_issues() + tool_catalog(a)


def tool_catalog(a):
    """Validate catalog structure and declared tools in documentation tables."""
    entries = json.loads(a.text('config/tool_catalog.json')).get('entries', [])
    if not isinstance(entries, list) or not entries:
        return ['invalid/empty tool catalog entries']
    problems, ids, aliases = [], set(), {}
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append('invalid tool catalog entry')
            continue
        name = entry.get('id', '')
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', name):
            problems.append('invalid tool id: ' + str(name))
            continue
        if name in ids:
            problems.append('duplicate tool id: ' + name)
        ids.add(name)
        if not isinstance(entry.get('verify'), str) or not entry['verify'].strip():
            problems.append('missing tool verify command: ' + name)
        names = entry.get('aliases', [])
        if not isinstance(names, list) or any(not isinstance(v, str) or not v.strip() for v in names):
            problems.append('invalid tool aliases: ' + name)
            names = []
        for alias in [name, *names]:
            key = alias.casefold()
            if key in aliases and aliases[key] != name:
                problems.append('ambiguous tool alias: ' + alias)
            aliases[key] = name
    for path in sorted((a.root / 'docs').rglob('*.md')):
        relative = path.relative_to(a.root).as_posix()
        text = a.text(relative)
        mentions = []
        for number, headers, cells in markdown_tables(text):
            for index, header in enumerate(headers):
                if ('도구' in header or re.search(r'\btools?\b', header, re.I)) and index < len(cells):
                    mentions.append((number, cells[index]))
        for number, line in enumerate(text.splitlines(), 1):
            mentions.extend((number, name) for name in re.findall(
                r'(?:도구|tool)(?:\s*ID)?\s*[:=]\s*`?([A-Za-z][A-Za-z0-9_.-]*)', line, re.I))
        for number, names in mentions:
            names = re.sub(r'https?://[^\s;]+|`[^`]*[/\\][^`]*`', '', names)
            for alias in sorted(aliases, key=lambda v: (-len(v), v)):
                names = re.sub(r'(?<![\w-])' + re.escape(alias) + r'(?![\w-])', '', names, flags=re.I)
            for name in re.findall(r'[A-Za-z][A-Za-z0-9_.-]*', names):
                if name not in {'CLI', 'LTS', 'HWP', 'HWPX', 'Markdown', 'diff'}:
                    problems.append(f'uncatalogued doc tool: {relative}:{number}: {name}')
    return sorted(set(problems))


def ci_matrix(a):
    text = a.text('.github/workflows/qa.yml')
    commands = ['scripts/verify_package.py', 'unittest discover', 'scripts/strategy_qa.py', 'scripts/legal_qa.py',
                'scripts/score.py']
    valid = (re.search(r'os:\s*\[[^\]\n]*ubuntu-latest[^\]\n]*windows-latest[^\]\n]*\]', text)
             and 'runs-on: ${{ matrix.os }}' in text and 'shell: bash' in text
             and all(command in text for command in commands) and not re.search(r'^\s*if:', text, re.M))
    return [] if valid else ['both OS runners must execute the same QA commands without conditions']


def determinism(a):
    if a.probe:
        return ['NOT_TESTED: parent compares two independent score.py probes']
    results = [a.run(['scripts/score.py', '--json', '--probe'], timeout=120) for _ in range(2)]
    if any(result.returncode != 1 for result in results):
        return ['determinism worker did not exit with its expected deferred-check status']
    for result in results:
        json.loads(result.stdout)
    return [] if results[0].stdout == results[1].stdout else ['score.py probe outputs differ']


def dependencies(a):
    problems = []
    result = a.run(['-m', 'pip', 'check'])
    if result.returncode:
        problems.append('pip check failed: ' + result.stdout.strip())
    if not a.text('requirements.txt').strip():
        problems.append('requirements.txt is empty')
    try:
        result = a.run(['-m', 'pip', 'install', '--dry-run', '--upgrade', '-r', 'requirements.txt',
                        '--disable-pip-version-check', '--retries', '0', '--timeout', '12'], timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        problems.append('NOT_TESTED: resolver unavailable')
        return problems
    if result.returncode and re.search(r'Permission denied|Access is denied|WinError 5',
                                       (result.stdout or '') + (result.stderr or ''), re.I):
        problems.append('NOT_TESTED: resolver filesystem access denied')
    elif result.returncode:
        problems.append('requirements.txt does not resolve on this interpreter: ' + result.stdout.strip()[-300:])
    elif re.search(r'^Would install ', result.stdout, re.M):
        problems.append('not latest resolvable: ' + re.search(r'^Would install .*', result.stdout, re.M)[0])
    return problems


def gate_secrets(a):
    patterns = [re.compile(r'(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{24,}|AKIA[A-Z0-9]{16})'),
                re.compile(r'(?<!\d)\d{6}-[1-4]\d{6}(?!\d)'),
                re.compile(r'(?<!\d)\d{3,6}-\d{2,6}-\d{4,8}(?!\d)')]
    problems = []
    for path in a.files():
        data = path.read_bytes()
        if path.suffix == '.docx':
            with zipfile.ZipFile(path) as archive:
                data += b'\n'.join(archive.read(n) for n in archive.namelist() if n.endswith('.xml'))
        text = data.decode('utf-8', errors='replace')
        # Hyphenated article identifiers inside DOIs are not bank accounts.
        numeric_text = re.sub(r'10\.\d{4,9}/[^\s<>"`\])]+', '[DOI]', text)
        if patterns[0].search(text) or any(pattern.search(numeric_text) for pattern in patterns[1:]):
            problems.append('secret/personal-data pattern: ' + path.relative_to(a.root).as_posix())
    return problems


def gate_disclaimer(a):
    text = a.text('README.md')
    return [] if all(term in text for term in ('승소', '기소', '유죄', '보장하지', '변호사 검토')) else ['missing outcome disclaimer/lawyer review']


def gate_guarantees(a):
    problems = []
    for path in a.files():
        if path.suffix != '.md':
            continue
        for line in a.text(path.relative_to(a.root)).splitlines():
            if re.search(r'(?:승소|기소|유죄).{0,8}보장|(?:반드시|100%).{0,8}승소', line):
                # Negated claims and rules prohibiting guarantees are not promises.
                if not re.search(r'보장하지|보장.*(?:없|금지|부재)|아니|금지|부재|비보장', line):
                    problems.append('outcome guarantee: ' + path.relative_to(a.root).as_posix())
    return sorted(set(problems))


def gate_fictional(a):
    problems = []
    for path in sorted((a.root / 'examples').rglob('*.json')):
        record = json.loads(a.text(path.relative_to(a.root)))
        label = ' '.join(str(record.get(k, '')) for k in ('scope', 'document_type'))
        if not re.search(r'fictional|synthetic|가상', label, re.I):
            problems.append('unlabeled synthetic record: ' + path.relative_to(a.root).as_posix())
    if not re.search(r'모든[^\n]*examples/[^\n]*가상', a.text('README.md')):
        problems.append('missing blanket fictional label for example assets/templates')
    return problems


CRITERIA = dict(zip([
    'A1.single_ssot', 'A1.stage_ids', 'A1.links_paths', 'A1.reachability',
    'A2.synthetic_cases', 'A2.error_codes', 'A2.node_schema', 'A2.recursive_termination',
    'A3.unit_tests', 'A3.rule_test_mapping', 'A3.final_states',
    'A4.bibliography_identity', 'A4.grade_scope', 'A4.statute_ledger', 'A4.transfer_limits',
    'A5.package_integrity', 'A5.ci_matrix', 'A5.determinism', 'A5.dependencies',
], [single_ssot, stage_ids, links_paths, reachability, synthetic_cases, error_codes,
    node_schema, recursive_termination, unit_tests, rule_test_mapping, final_states,
    bibliography_identity, grade_scope, statute_ledger, transfer_limits, package_integrity,
    ci_matrix, determinism, dependencies]))
GATES = {'SG1': gate_secrets, 'SG2': gate_disclaimer, 'SG3': gate_guarantees, 'SG4': gate_fictional}


def rubric(a):
    paths = sorted((a.root / 'docs').glob('18_*.md'))
    if len(paths) != 1:
        raise ValueError('exactly one frozen rubric required')
    rows, axis = [], ''
    for line in a.text(paths[0].relative_to(a.root)).splitlines():
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if len(cells) != 3 or not re.search(r'\((\d+)\)', cells[1]):
            continue
        if cells[0]:
            axis = cells[0].split()[0]
        label, points = re.fullmatch(r'(.+)\((\d+)\)', cells[1]).groups()
        rows.append((axis, label, int(points)))
    if len(rows) != len(CRITERIA) or sum(row[2] for row in rows) != 100 or any(
            row[0] != key.split('.')[0] for row, key in zip(rows, CRITERIA)):
        raise ValueError('rubric rows/axes/denominator differ from the frozen contract')
    return rows


def checked(predicate, a):
    try:
        return sorted(set(predicate(a)))
    except (OSError, ValueError, KeyError, TypeError, StopIteration, SyntaxError,
            subprocess.TimeoutExpired, zipfile.BadZipFile) as error:
        return ['NOT_TESTED: ' + type(error).__name__ + ': ' + str(error).replace(str(a.root), '<root>')]


def evaluate(a):
    rows = rubric(a)
    criteria, axes = [], {f'A{i}': 0 for i in range(1, 6)}
    for (key, predicate), (axis, label, points) in zip(CRITERIA.items(), rows):
        details = checked(predicate, a)
        earned = points if not details else 0
        axes[axis] += earned
        criteria.append(dict(id=key, label=label, points=points, earned=earned, passed=not details, details=details))
    gates = {}
    for key, predicate in GATES.items():
        details = checked(predicate, a)
        gates[key] = dict(passed=not details, details=details)
    total = sum(axes.values())
    released = total == 100 and all(g['passed'] for g in gates.values())
    status = 'READY_FOR_HUMAN_REVIEW' if released else (
        'NEEDS_VERIFICATION' if all(g['passed'] for g in gates.values()) else 'SUBMISSION_BLOCKED')
    return dict(total=total, axes=axes, criteria=criteria, gates=gates, status=status,
                EXCLUDED=[dict(item=item, status='NOT_TESTED') for item in EXCLUDED])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--probe', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    result = evaluate(Audit(probe=args.probe))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print('total={total}/100; status={status}'.format(**result))
        print(' '.join(f'{key}={value}/20' for key, value in result['axes'].items()))
        for row in result['criteria']:
            print(f'{row["id"]}: {row["earned"]}/{row["points"]}' + (' PASS' if row['passed'] else ' FAIL'))
            for detail in row['details']:
                print('  ' + detail)
        for key, gate in result['gates'].items():
            print(key + ': ' + ('PASS' if gate['passed'] else 'FAIL') +
                  ('; ' + '; '.join(gate['details']) if gate['details'] else ''))
        for item in result['EXCLUDED']:
            print('EXCLUDED NOT_TESTED: ' + item['item'])
    return 0 if result['total'] == 100 and all(g['passed'] for g in result['gates'].values()) else 1


if __name__ == '__main__':
    sys.exit(main())
