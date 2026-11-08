#!/usr/bin/env python3
"""Offline packaging integrity and navigation QA (not legal or scientific validation)."""
import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {"MANIFEST_SHA256.txt"}
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
CODE_PATH = re.compile(r"\b(?:docs|prompts|templates|qa|scripts|references|examples|config)/[\w가-힣./+~-]+\.(?:md|py|json|csv|docx|pdf|png|ps1|svg|txt|dot|mmd|yml)\b")
issues = []

def normalized_bytes(path):
    """Normalize UTF-8 text only; preserve binary formats declared in .gitattributes."""
    data = path.read_bytes()
    if path.suffix.lower() in {'.docx', '.pdf', '.png'} or b'\0' in data:
        return data
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    return data.replace(b'\r\n', b'\n')


def digest(path):
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def write_manifest(root, files):
    lines = ['# SHA256 of distributable source files; UTF-8 text normalized to LF; excludes itself.']
    lines.extend(f'{digest(root / relative)}  {relative}' for relative in sorted(files))
    (root / 'MANIFEST_SHA256.txt').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))

def report(code, detail):
    issues.append(f"{code}: {detail}")

def tracked(path):
    parts = path.parts
    return not any(x in {".git", ".venv", "__pycache__", ".pytest_cache"} for x in parts) and path.suffix != ".pyc" and path.as_posix() not in EXCLUDE

def main(argv=None):
    issues.clear()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-manifest', action='store_true', help='Regenerate sorted LF-normalized hashes, then exit.')
    parser.add_argument('--check-line-endings', action='store_true', help='Fail on CRLF text even when normalized hashes match.')
    args = parser.parse_args(argv)
    files = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and tracked(p.relative_to(ROOT))}
    if args.check_line_endings:
        for relative in sorted(files | {'MANIFEST_SHA256.txt'}):
            path = ROOT / relative
            if path.exists() and path.read_bytes() != normalized_bytes(path):
                report('LINE_ENDING_DRIFT', relative)
    if args.write_manifest:
        if issues:
            for issue in issues:
                print('FAIL', issue)
            return 1
        write_manifest(ROOT, files)
        print(f'Wrote MANIFEST_SHA256.txt; files={len(files)}')
        return 0
    manifest = ROOT / "MANIFEST_SHA256.txt"
    entries = {}
    if not manifest.exists():
        report("MISSING_MANIFEST", manifest.name)
    else:
        for no, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            pair = line.split("  ", 1)
            if len(pair) != 2 or not re.fullmatch(r"[a-f0-9]{64}", pair[0]):
                report("BAD_MANIFEST_LINE", str(no))
                continue
            expected_digest, relative = pair
            if relative in entries:
                report("DUPLICATE_MANIFEST", relative)
            entries[relative] = expected_digest
            if relative not in files:
                report("MANIFEST_MISSING_FILE", relative)
                continue
            actual = digest(ROOT / relative)
            if actual != expected_digest:
                report("HASH_MISMATCH", relative)
    for extra in sorted(files - set(entries)):
        report("UNTRACKED_IN_MANIFEST", extra)

    for path in ROOT.rglob("*.md"):
        rel = path.relative_to(ROOT)
        if not tracked(rel):
            continue
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for target in LINK.findall(line):
                target = target.strip().split("#", 1)[0].split("?", 1)[0]
                if not target or target.startswith(("http:", "https:", "mailto:", "data:", "#")):
                    continue
                target = unquote(target.split(" ", 1)[0])
                dest = (path.parent / target).resolve()
                if not dest.is_relative_to(ROOT) or not dest.exists():
                    report("BROKEN_MARKDOWN_LINK", f"{rel}:{no}:{target}")
            for target in CODE_PATH.findall(line):
                if not (ROOT / target).exists():
                    report("BROKEN_REPO_PATH", f"{rel}:{no}:{target}")

    register = ROOT / "references/research_register.csv"
    if not register.exists():
        report("MISSING_REGISTER", register.name)
        research_ids = []
    else:
        with register.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        research_ids = [r.get("id", "") for r in rows]
        if len(research_ids) != len(set(research_ids)):
            report("DUPLICATE_RESEARCH_ID", "research_register.csv")
        if len(research_ids) < 42:
            report("RESEARCH_BELOW_BASELINE", str(len(research_ids)))

    for phase in range(9):
        count = len(list((ROOT / "prompts").glob(f"P{phase}_*.md")))
        if count != 1:
            report("BAD_P_STAGE", f"P{phase}={count}")
    for phase in range(7):
        count = len(list((ROOT / "prompts/strategy").glob(f"S{phase}_*.md")))
        if count != 1:
            report("BAD_S_STAGE", f"S{phase}={count}")
    if not (ROOT / "docs/00_최종_통합마스터_V5.md").exists():
        report("MISSING_SSOT", "docs/00_최종_통합마스터_V5.md")

    print(f"files={len(files)}; manifest_entries={len(entries)}; research={len(research_ids)}; problems={len(issues)}")
    for issue in issues:
        print("FAIL", issue)
    return int(bool(issues))


if __name__ == "__main__":
    sys.exit(main())
