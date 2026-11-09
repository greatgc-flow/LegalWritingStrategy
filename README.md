# LegalWritingStrategy — 법률문서 전략·작성·검증 마스터키트

**Version:** v5.2.3 · **Language:** 한국어 · **Scope:** 대한민국 민사·형사·경찰·검찰·법원 제출서면

조문 원문은 [월별 워크플로](.github/workflows/statute-recheck.yml)와 [재대조 스크립트](scripts/recheck_statutes.py)로 확인하며, 기록된 해시가 모두 일치할 때만 확인일·90일 재확인 기한을 PR로 갱신합니다. 변경·조회 실패는 이슈로 알립니다.

> 정확한 법률·증거 검증을 바탕으로 읽기 쉽고 인용하기 좋은 법률서면을 설계하기 위한 연구·프롬프트·자동검사 도구 모음입니다. **승소·기소·유죄를 보장하지 않으며**, 사건별 변호사 검토와 법령·원증거 확인을 대체하지 않습니다. 모든 `examples/`와 `templates/`의 사건은 가상 사례입니다.

## 첫 사건 최단 경로

1. [CASE_INDEX](templates/CASE_INDEX_빈양식.md)를 작성한다.
2. [P0](prompts/P0_원본동결_작업범위.md)에서 원본을 보존하고 작업 범위를 정한다.
3. [P1](prompts/P1_원문_사실_증거색인.md)에서 FACT/EV/LAW/ISS ID를 부여하고 미확인은 `UNVERIFIED`로 표시한다.
4. [P5](prompts/P5_사람다운문체_정확교정.md)에서 사실·법적 의미를 보존하며 문장을 다듬는다.
5. [P8](prompts/P8_독립감사_종횡_최종판정.md)에서 독립 검수하고 사건별 변호사 검토를 거친다.
S0~S6 전략 단계는 복잡한 사건에서 선택적으로 사용한다. 전체 기준은 [통합 기준본](docs/00_최종_통합마스터_V5.md)을 참조한다.

## 1. 빠른 시작 (3분)

1. **기준본 읽기:** [`docs/00_최종_통합마스터_V5.md`](docs/00_최종_통합마스터_V5.md) — 법리·증거·문체·전략·절차를 총괄하는 단일 기준본(SSOT).
2. **사건 목적 확인:** [`prompts/strategy/S0_절차_목적_기한.md`](prompts/strategy/S0_절차_목적_기한.md) — 경찰·검찰·민사·형사 절차와 시점·기한.
3. **사건 전략:** 필요에 따라 `S1`~`S6` 순서로 경쟁 사건이론·법률요건·원증거·불리한 증거·독자별 구조·독립검토.
4. **기존 문서 수정:** [`prompts/P0_원본동결_작업범위.md`](prompts/P0_원본동결_작업범위.md)부터 `P8`까지 단계별 실행. **원본 보존과 수정 이력은 필수.**
5. **검증:** 법령·판례·원증거 대조, [`qa/FINAL_REVIEW_CHECKLIST.md`](qa/FINAL_REVIEW_CHECKLIST.md), DOCX/PDF 렌더링 및 사람 검토. 미확인은 `UNVERIFIED`로 남긴다.

**중요한 구분:** `S0~S6`는 사건 전략, `P0~P8`은 문서 편집·검수입니다. 병렬 적용할 수 있지만 단계별 사실·법리 검증을 생략하지 않습니다.

## 2. 폴더 구조

| 경로 | 역할 | 처음에 볼 문서 |
|---|---|---|
| [`docs/`](docs/) | **V5 기준본**, 연구·법리·문체·전략·폰트·설치·QA 설명 | [`00_최종_통합마스터_V5.md`](docs/00_최종_통합마스터_V5.md) |
| [`prompts/strategy/`](prompts/strategy/) | 전략 S0~S6, 불리증거 ADVERSE-8, 독자별 인용 적합성 | [`S0_절차_목적_기한.md`](prompts/strategy/S0_절차_목적_기한.md) |
| [`prompts/`](prompts/) | 기존문서 수정 P0~P8, 공통 프롬프트 | [`00_공통규칙.md`](prompts/00_공통규칙.md) |
| [`references/`](references/) | 연구 메타데이터·요구사항 추적·이력 | [`research_register.csv`](references/research_register.csv) |
| [`templates/`](templates/) | DOCX 및 CSV 형식 예제, 가상 서면 | [`CASE_INDEX_빈양식.md`](templates/CASE_INDEX_빈양식.md) |
| [`examples/`](examples/) | 가상 데이터, 흐름도·그림 생성 예제 | [`synthetic_strategy_case.json`](examples/synthetic_strategy_case.json) |
| [`scripts/`](scripts/) | 부분 QA, 검증 스크립트, Windows 설치 안내 | [`verify_package.py`](scripts/verify_package.py) |
| [`qa/`](qa/) | 자동검사 결과, 렌더링 검수 기록 | [`V5_최종검증_보고서.md`](qa/V5_최종검증_보고서.md) |
| [`config/`](config/) | 문서 스타일 및 도구 목록 | [`style_profile.json`](config/style_profile.json) |

**AI CLI 초기 지침:** [`AGENTS.md`](AGENTS.md) (Codex 등) / [`CLAUDE.md`](CLAUDE.md) (Claude). 짧은 상시 규칙만 로딩하고 관련 `prompts/` 파일을 필요할 때 불러와 토큰을 절약합니다. 장문의 문서를 매 요청마다 붙여넣지 마세요.

## 3. Windows 설치 (기본 미리보기)

PowerShell에서 저장소 디렉터리로 이동 후:

```powershell
# 사전 점검 (설치하지 않음)
.\scripts\install_windows.ps1

# 명시적 동의를 받은 항목에만 설치 시도 (각 단계 YES 확인)
.\scripts\install_windows.ps1 -Apply

# Python 패키지는 가상환경에만 설치
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

설치 대상: Git, Pandoc, LibreOffice, Python 3.12, Graphviz, Zotero(선택). 한글 폰트는 자동 설치하지 않으며 [`docs/02_한글폰트_근거_추천_설치.md`](docs/02_한글폰트_근거_추천_설치.md)와 [`docs/04_도구_설치_설정_사용법.md`](docs/04_도구_설치_설정_사용법.md)를 따릅니다. Windows는 이 저장소에서 실기기 설치 검증되지 않았습니다.

## 4. 품질검사 실행

```bash
python -m pip install -r requirements.txt
python scripts/verify_package.py
python -m unittest discover -s scripts -p 'test_*.py' -v
python scripts/strategy_qa.py --record examples/synthetic_strategy_case.json
python scripts/legal_qa.py --record examples/synthetic_case.json
```

검증 프로그램은 **문서 연결성·기본 형식·합성 사례의 오류 탐지**를 위한 것입니다. 법령의 현행성, 판례의 진정성, 실제 증거의 적법성/증명력, 소송결과를 판단하지 않습니다.

사건 데이터는 [JSON 예제](examples/synthetic_strategy_case.json)와 [필드 계약](docs/00_최종_통합마스터_V5.md)의 SCHEMA 및 SCALAR_FIELDS를 기준으로 한 번 관리합니다. CSV 두 양식은 선택 입력 뷰입니다. 작성 후 다음 명령으로 새 JSON을 만들고 검사합니다(목록·불리언·수치 셀은 JSON 문법 사용).

```bash
python scripts/csv_to_record.py --strategy templates/STRATEGY_LINK_빈양식.csv --adverse templates/ADVERSE_MATRIX_빈양식.csv --out private/case_record.json
python scripts/legal_qa.py --docx private/brief.docx --kind civil
```

`--base`로 기존 JSON의 scope/unresolved 등 루트 메타데이터를 보존할 수 있으며 노드 컬렉션은 CSV 내용으로 교체됩니다. 원문 위치·발췌와 서면 문단 앵커를 입력하고 미해결 항목을 명시합니다. VIS/ATT/CHG/QA는 필요할 때만 만들지만 참조·변경이 있으면 검증합니다. DOCX는 `--kind criminal`로 형사 예시 프로필을 선택하며, 구역·run·사용/설정 스타일 오류가 종료코드에 반영됩니다. 실제 PDF 렌더·원본 진정성 검수는 별도입니다.

## 5. 실전 용도별 바로가기

| 필요할 때 | 바로 읽기 |
|---|---|
| 경찰/검사에게 인용하기 좋은 짧은 문장 | [`docs/12_독자별_인용문장_문서아키텍처.md`](docs/12_독자별_인용문장_문서아키텍처.md) |
| 불리한 문자·녹취·거래내역에 대응 | [`docs/11_불리한증거_대응과_양면논증.md`](docs/11_불리한증거_대응과_양면논증.md) |
| 주요 사건이론과 반대가설 비교 | [`docs/10_이기는_법률서면_전략_정직한논증.md`](docs/10_이기는_법률서면_전략_정직한논증.md) |
| 한국 민사·형사 작성·제출 기준 | [`docs/14_한국_민사형사_법령_판면_윤리_시점.md`](docs/14_한국_민사형사_법령_판면_윤리_시점.md) |
| 본문 vs 별첨 / 표·차트·폰트 | [`docs/02_한글폰트_근거_추천_설치.md`](docs/02_한글폰트_근거_추천_설치.md) |
| AI 사용 토큰 줄이기 | [`docs/03_AI_CLI_토큰절감_재현가능운영.md`](docs/03_AI_CLI_토큰절감_재현가능운영.md) |
| 연구 근거 및 한계 확인 | [`docs/05_논문_연구와_근거등급.md`](docs/05_논문_연구와_근거등급.md), [`references/research_register.csv`](references/research_register.csv) |

## 6. 자료 보안과 공개 범위

- **공개 저장소:** 실제 사건 이름·원증거·주민번호·계좌번호·녹취 원본·비공개 자료·토큰·API 키를 커밋하지 마세요. 합성 예제만 공개합니다.
- **증거 윤리:** 불리한 자료를 숨기거나 편집해 의미를 왜곡하지 않습니다. 원문·시점·다른 해석·추가 검증 필요성을 함께 검토합니다.
- **법령의 시간성:** 법령/판례의 적용 시점과 개별 사건 경과규정을 확인하고, 국가법령정보센터 등 공식 원문과 대조합니다.
- **연구:** 선별 문헌 및 서지/초록 검증을 포함하며 전수 PRISMA 메타분석이 아닙니다. 일부 연구는 전문 미확인으로 표시되어 있습니다.
- **저작권:** 폰트 파일이나 학술 논문의 유료 원문을 동봉하지 않습니다. 폰트는 공식 배포처에서 라이선스를 확인해 설치하세요.

## 7. 릴리즈와 재현성

- 릴리즈: **[`v5.2.3`](https://github.com/greatgc-flow/LegalWritingStrategy/releases/tag/v5.2.3)**. 릴리즈 자산은 저장소의 공개 자료만 묶습니다.
- 작업중 버전 변경 시 `docs/00_최종_통합마스터_V5.md`를 기준으로 다른 문서가 참조하는 파일 경로를 점검하고 QA를 실행합니다.
- [`MANIFEST_SHA256.txt`](MANIFEST_SHA256.txt)는 배포 자료 파일의 체크섬이며, 표준 Git 커밋 SHA와는 다릅니다.
- 자세한 차이: [`RELEASE_NOTES.md`](RELEASE_NOTES.md).

## 8. 점수 기준과 검증 이력

`score.py`의 100점은 내부 **구조·형식 점수**이며 실제 사건 정확성 검증이 아니다. Crossref/TEXT_MATCH 표시는 기록된 확인 진술이며 `score.py`가 원문 대조를 재실행하지 않는다.

- [동결 루브릭](docs/18_상호재귀_MECE_종횡감사_20261107.md): 구조·추적·검증·근거·재현성의 평가 기준입니다. `python scripts/score.py`로 계산하고, 날짜·작업 트리·축별 실행값은 [점수 이력](qa/SCORE_HISTORY.md)에 기록합니다.
- 원문 출처가 없는 인용·금액과 잘못된 검증 플래그를 탐지하는 테스트를 추가했습니다. PR에서 `Structural and synthetic QA`가 실행됩니다.
- 계산된 내부 구조 점수는 승소율·기소율이나 실제 제출 적합성 점수가 아닙니다. Windows·HWP 현장 검증, 문헌 전수 원문 평가, 사건별 법률·원증거 검증은 별도입니다.
