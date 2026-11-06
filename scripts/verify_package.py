#!/usr/bin/env python3
"""Read-only package completeness audit: checks file references and SHA256 manifest.
It does not validate Korean laws, evidence authenticity, or any research claims.
"""
import hashlib, re, sys, csv
from pathlib import Path
root=Path(__file__).resolve().parents[1]
problems=[]
manifest=root/'MANIFEST_SHA256.txt'
if not manifest.exists(): problems.append('missing manifest')
else:
  for line in manifest.read_text(encoding='utf-8').splitlines():
    if not line or line.startswith('#'): continue
    checksum, path=line.split('  ',1)
    target=root/path
    if not target.is_file(): problems.append('MISSING FILE: '+path); continue
    actual=hashlib.sha256(target.read_bytes()).hexdigest()
    if checksum!=actual: problems.append('BAD SHA256: '+path)
all_files={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
for p in root.rglob('*.md'):
  for i,line in enumerate(p.read_text(encoding='utf-8').splitlines(),1):
    for hit in re.findall(r'(?:prompts|templates|qa)/[\w가-힣.~-]+\.(?:md|docx|pdf)',line):
      if hit not in all_files:
        problems.append(f'BROKEN REF {p.relative_to(root)}:{i}: {hit}')
ids=[]
with (root/'references/research_register.csv').open(encoding='utf-8-sig',newline='') as f:
  ids=[row['id'] for row in csv.DictReader(f)]
if len(set(ids))!=len(ids):problems.append('duplicate research ids')
if len(ids)<42:problems.append(f'research count below inherited minimum 42, found {len(ids)}')
for phase in range(9):
  fs=list((root/'prompts').glob(f'P{phase}_*.md'))
  if len(fs)!=1: problems.append(f'phase P{phase} expected one file, found {len(fs)}')
for phase in range(7):
  fs=list((root/'prompts'/'strategy').glob(f'S{phase}_*.md'))
  if len(fs)!=1: problems.append(f'strategy S{phase} expected one file, found {len(fs)}')
if not (root/'docs/00_최종_통합마스터_V5.md').is_file():problems.append('missing V5 SSOT')
print(f'Files checked: {len(all_files)}; research: {len(ids)}; findings: {len(problems)}')
for msg in problems: print('FAIL',msg)
sys.exit(1 if problems else 0)
