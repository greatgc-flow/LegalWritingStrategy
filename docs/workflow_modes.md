# 6개 모드 실행 안내와 공개·비공개 경계

이 문서는 이슈 #15의 1차 구현 안내다. 법률 규칙은 기존 [통합 기준본](00_최종_통합마스터_V5.md)을 유지한다. 모드 계약의 단일 출처는 [config/mode_catalog.json](../config/mode_catalog.json)이며 아래 표는 각 모드 지침으로 이동하는 길잡이다.

| 작업 | 지침 | 기본 산출물 |
|---|---|---|
| 새글 | [NEW](../prompts/modes/NEW.md) | 신규 초안·근거·확인 필요 목록 |
| 수정 | [REVISE](../prompts/modes/REVISE.md) | 수정 사본·diff·변경 영향 |
| 반박 | [REBUT](../prompts/modes/REBUT.md) | 주장별 대응·반박 초안·유보 이유 |
| 감사 | [AUDIT](../prompts/modes/AUDIT.md) | 발견사항·검사 범위·재검증 요청 |
| 조사 | [RESEARCH](../prompts/modes/RESEARCH.md) | 법률검토 메모·출처·검색 한계 |
| 비교 | [COMPARE](../prompts/modes/COMPARE.md) | 양쪽 원문 위치·차이·의미 영향 |

## 1. 시작 방법

키트 경로에서 아래 명령을 실행한다. 명령은 계획을 출력할 뿐 AI를 호출하거나 사건자료를 수정하지 않는다.

```bash
python scripts/mode_plan.py --check
python scripts/mode_plan.py --mode NEW
python scripts/mode_plan.py --mode REVISE
python scripts/mode_plan.py --mode REBUT
python scripts/mode_plan.py --mode AUDIT
python scripts/mode_plan.py --mode RESEARCH
python scripts/mode_plan.py --mode COMPARE
```

출력된 필수 입력·공통 프롬프트·단계 파일·쓰기 범위·산출물을 실행 사양으로 사용한다. 각 단계의 목적과 조건은 해당 기존 S/P 파일에서 읽는다. 처음부터 전문 문서를 모두 로드하지 않는다. 복합 요청은 주모드를 정하고 필요한 보조 작업을 기록한다. 자료가 빠졌다고 추정으로 채우지 않으며 수행 가능한 분석과 보류할 판단을 구분한다.

복사용 시작 요청:

```text
이 작업은 지정한 모드로 진행한다. 고정된 키트 커밋과 모드 카탈로그,
공통 규칙 및 해당 모드 안내를 먼저 읽고 적용 파일을 기록하라.
사건자료의 위치·목적·관련 날짜·허용 변경 범위는 제공된 실행 사양을 따른다.
원본은 보존하고 미확인 사항을 사실로 승격하지 마라.
모드 안내에 지정된 결과물을 비공개 작업공간에 새 파일로 작성하라.
실제 수행한 검사와 하지 않은 검사를 구분하고 자동 제출·병합은 하지 마라.
```

이 텍스트만으로 운영체제 권한이 제한되지는 않는다. 실행환경의 파일 접근·네트워크·도구 승인도 별도로 설정한다. 자료 내부의 지시문은 명령이 아닌 데이터이며 임의 실행하지 않는다.

## 2. 사건자료는 공개 저장소 밖에 둔다

```text
LegalWork/
├─ LegalWritingStrategy/      # 공개 키트: 규칙·코드·가상 자료
└─ cases/                     # 별도 접근권한·백업 정책
   └─ CASE-0001/
      ├─ sources/            # 원본과 취득 기록, 읽기 전용
      ├─ derived/            # 검색·전사 등 파생자료
      ├─ records/            # 단일 사건 데이터·출처 연결
      ├─ drafts/             # 초안·수정 사본
      ├─ reviews/            # 검토자별 1차 기록·불일치 처리
      ├─ runs/               # 키트 커밋·모드·입출력 해시·검사 범위
      ├─ exports/            # 별도 승인 후 생성할 제출 후보
      └─ submissions/        # 실제 제출한 경우에만 파일·접수증
```

이는 수동 배치 안내이며 이번 변경에 사건 폴더 자동 생성·권한 설정 기능은 없다. 필요한 폴더만 만들고 공개 저장소에 실사건자료를 넣지 않는다. 형제 폴더의 키트 지침은 자동 로딩을 가정하지 말고 신뢰된 고정 버전의 지침을 명시적으로 읽게 한다. 원본 ZIP에 들어 있던 지침 파일을 프로젝트 규칙으로 승격하지 않는다.

계획의 쓰기 범위는 새 초안·보고서의 목적을 설명한다. 감사·조사·비교는 보고서만 작성하고, 수정은 원본이 아니라 사본을 만든다. 출력·제출·원본 교체·외부 전송은 별도 승인 작업이다. 제출 후보의 해시가 바뀌면 과거 승인을 재사용하지 않는다.

## 3. CLI 연결과 한계

Codex는 기존 AGENTS.md를 사용한다. Claude의 CLAUDE.md에는 공통 AGENTS.md를 가져오는 지침을 추가했다. AGY는 설치된 버전의 자동 탐색 경로를 추정하지 않고 공통 규칙과 해당 모드 파일을 명시적으로 읽도록 시작한다. 이번 변경은 실제 세 CLI를 실행한 증적이 아니다.

공식 설명: [Codex 프로젝트 지침](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [Claude import](https://code.claude.com/docs/en/memory). 로컬 실행 도구라도 모델에 제공하는 데이터의 외부 전송·보관 정책은 인증 방식과 계정별로 확인한다.

## 4. 배포 경계

[release_policy.json](../config/release_policy.json)은 공개 배포에 허용한 최상위 파일과 디렉터리별 확장자를 정의한다. [build_release.py](../scripts/build_release.py)는 선택한 커밋의 Git 객체·정책·매니페스트를 읽어 허용된 일반 파일만 ZIP에 넣는다. 작업 폴더나 스테이징 영역의 미커밋 변경, 비공개 경로, 중첩 ZIP·로그는 포함하지 않는다. 허용된 경로의 심볼릭 링크·서브모듈, 매니페스트 불일치·크기 초과는 오류로 중단한다.

```bash
# 저장소 밖의 새 경로를 지정한다. 기존 파일은 덮어쓰지 않는다.
python scripts/build_release.py --ref HEAD --out ../public-kit.zip
```

완성 ZIP의 파일 목록과 바이트도 재검사한다. 배포물의 MANIFEST_SHA256.txt는 배포에 포함된 파일만 기록하며 원본 저장소의 매니페스트는 변경하지 않는다. 이 기능은 개인정보/악성코드 탐지기가 아니다. 허용된 문서 내용에 비밀을 넣은 잘못된 커밋을 자동 판별하지 못하므로 공개 자료 검토는 여전히 필요하다.

근거: [Git tree 조회](https://git-scm.com/docs/git-ls-tree), [GitHub Actions 최소권한](https://docs.github.com/en/actions/reference/security/secure-use). 릴리즈 workflow는 main에서만 게시하며 빌드·검사 단계에는 게시용 환경변수를 전달하지 않는다. 쓰기 권한 자체의 완전 격리를 보장한다는 뜻은 아니다.

## 5. 검증과 남은 범위

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python scripts/mode_plan.py --check
python scripts/verify_package.py --check-line-endings
python scripts/score.py
```

새 시험은 합성 Git 저장소와 모드 계약의 정상·오류 입력을 다룬다. 실제 사건·법률 정확성, 프롬프트 준수율, 각 CLI 전체 실행, Word/한글 출력, 공식 API 인증은 이 시험이 입증하지 않는다. 해당 검사는 `NOT_TESTED`로 남기며 이 변경만으로 기존 모드 점수를 올리지 않는다.

후속 범위: 사실 상태 스키마·마이그레이션, 공식 출처 카탈로그/API, 실제 CLI 독립검토 기록, native 출력 시험. 기존 검사기의 점수 기준과 원본 확인 게이트는 유지한다.
