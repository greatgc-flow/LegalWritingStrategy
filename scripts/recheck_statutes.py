#!/usr/bin/env python3
"""Reproduce recorded article hashes; never accept changed law text automatically.

Hashes cover NFC UTF-8 Markdown from the article heading to the next article
heading (or supplementary provisions/end of file), with LF and one final newline.
This detects upstream text changes, not legal applicability or official currency.
--update renews dates only after every recorded hash and TEXT_MATCH status passes.
"""
import argparse
import csv
import hashlib
import io
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://raw.githubusercontent.com/legalize-kr/legalize-kr/main/'
ARTICLE = re.compile(r'^#{1,6}[ \t]+(제\d+조(?:의\d+)?)(?=[ \t(（]|$)[^\n]*', re.M)


def source_path(source):
    if not isinstance(source, str):
        raise ValueError('invalid upstream source path')
    match = re.search(r'(?:^|\s)(kr/[^\r\n]+\.md)$', source)
    if not match or any(part in ('.', '..') for part in match[1].split('/')):
        raise ValueError('invalid upstream source path')
    path = match[1]
    if '\\' in path or PurePosixPath(path).is_absolute():
        raise ValueError('invalid upstream source path')
    return path


def fetch(path):
    request = Request(UPSTREAM + quote(path, safe='/'), headers={'User-Agent': 'LegalWritingStrategy-statute-recheck'})
    with urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8-sig')


def article_hash(text, article):
    if not isinstance(article, str) or not article:
        raise ValueError('missing article')
    text = unicodedata.normalize('NFC', text.replace('\r\n', '\n').replace('\r', '\n'))
    # Supplementary provisions can repeat main-law article numbers.
    text = re.split(r'^#{1,6}[ \t]+부칙\b', text, maxsplit=1, flags=re.M)[0]
    headings = list(ARTICLE.finditer(text))
    found = [index for index, heading in enumerate(headings) if heading[1] == unicodedata.normalize('NFC', article)]
    if len(found) != 1:
        raise ValueError('missing or ambiguous article: ' + article)
    index = found[0]
    end = headings[index+1].start() if index+1 < len(headings) else len(text)
    block = text[headings[index].start():end].strip() + '\n'
    return hashlib.sha256(block.encode('utf-8')).hexdigest()


def verify_rows(rows, fetcher=fetch):
    errors, sources = [], {}
    for row in rows:
        rid = row.get('id') or '<missing id>'
        try:
            expected = row.get('text_sha256', '')
            if not re.fullmatch(r'[0-9a-fA-F]{64}', expected or ''):
                raise ValueError('invalid text_sha256')
            if row.get('status') != 'TEXT_MATCH':
                raise ValueError('status must already be TEXT_MATCH')
            path = source_path(row.get('source', ''))
            if path not in sources:
                try:
                    sources[path] = fetcher(path)
                except (OSError, ValueError, UnicodeError) as error:
                    sources[path] = error
            if isinstance(sources[path], Exception):
                raise ValueError('fetch failed: ' + str(sources[path]))
            actual = article_hash(sources[path], row.get('article', ''))
            if actual != expected.lower():
                raise ValueError(f'hash mismatch: expected={expected} actual={actual}')
        except (OSError, ValueError, UnicodeError) as error:
            errors.append(f'FAIL {rid}: {error}')
    return errors


def run(ledger, update=False, fetcher=fetch, today=None):
    with ledger.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    required = {'id', 'source', 'article', 'text_sha256', 'checked_on', 'recheck_by', 'status'}
    if not fields or not required <= set(fields) or not rows:
        print('FAIL ledger: missing columns or rows')
        return 1
    errors = verify_rows(rows, fetcher)
    if errors:
        print('\n'.join(errors))
        return 1
    if update:
        checked = today or date.today()
        for row in rows:
            row.update(checked_on=checked.isoformat(), recheck_by=(checked+timedelta(days=90)).isoformat())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        temporary = ledger.with_name(ledger.name + '.tmp')
        with temporary.open('xb') as handle:
            handle.write(output.getvalue().encode('utf-8'))
        try:
            temporary.replace(ledger)
        finally:
            temporary.unlink(missing_ok=True)
    for row in rows:
        print('PASS ' + row['id'] + (' dates renewed' if update else ' hash matched'))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--ledger', type=Path, default=ROOT/'references/statute_ledger.csv')
    args = parser.parse_args(argv)
    try:
        return run(args.ledger, args.update)
    except (OSError, ValueError, csv.Error) as error:
        print('FAIL ledger: ' + str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
