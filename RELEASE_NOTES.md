# v5.1.1 — 첫 사건 경로·서식 설정·재확인 기한 개선

- CASE_INDEX → P0 → P1 → P5 → P8의 짧은 시작 경로와 선택적 전략 단계를 안내한다.
- 템플릿 생성기가 스타일 프로필의 민사·형사 여백을 읽으며 A4 판면은 유지한다.
- 조문 장부에 확인일+90일의 `recheck_by`를 추가하고 만료 시 `NEEDS_VERIFICATION`으로 표시한다.
- 100점은 구조·형식 점수이며 Crossref/TEXT_MATCH 확인 진술을 자동 재검증하지 않음을 명시한다.

# v5.1.0 — 상호 재귀 MECE·종/횡 폐쇄성 감사 릴리즈

- **계산되는 완결도 루브릭**: `docs/18`(동결판 5축×20점 + 비상쇄 게이트 SG1~SG4)과 `python scripts/score.py`. 사람이 점수를 쓰지 않는다. 결과 100/100, 점수 제외 5항목은 NOT_TESTED로만 보고.
- **종/횡 추적 검사 강화**: `strategy_qa`가 R·ISS·LAW·FACT·EV·ARG·PAR·VIS·ATT·CHG·QA 전 노드의 정·역방향 도달성, 고아 노드, 변경 전파·재감사, 롤백·종료를 검사. 오류코드마다 정확한 기대코드를 가진 적대 픽스처.
- **근거 장부**: 연구 등재부 53건 Crossref 서지 대조(`doi_check`, 제목·연도 정정), 조문 장부 `references/statute_ledger.csv`(인용 조문 전부 legalize-kr 원문 대조, 인용 파일 추적).
- **단순화**: 중복된 V3/V4 문서·V4.1 정정기록·구 시드 스크립트 삭제(이력은 git), 상태값 어휘 통일(최종 3값 + 항목 4값), 게이트 표 단일화.
- **재현성**: LF 고정(`.gitattributes`), `verify_package.py --write-manifest`, CI ubuntu·windows에서 score.py 실행.
- 독립 감사(fable) 3회: 1차 15건, 2차 10건 지적 → 3차 "NO BLOCKER/MAJOR".

# v5.0.0 — Strategy MasterKit 초기 공개 릴리즈

- 대한민국 법률서면 연구·전략·문체·증거·시각화·AI 수정 절차 통합.
- V5 단일 기준본, S0~S6 사건전략, P0~P8 기존문서 교정 프롬프트.
- 불리한 증거 독립감사(ADVERSE-8)와 경찰·검사·법관별 인용 가능 문장 검증.
- 한글 폰트·Windows 설치 가이드, AI CLI 토큰 최적화, 재현 가능한 QA 스크립트.
- 자료는 가상 사례와 출처가 확인된 공개 메타정보 위주로만 제공. 실제 사건별 법률·원증거 검증은 별도.

**검증:** 가상 회귀시험의 현재 결과는 `python -m unittest discover -s scripts -p 'test_*.py'` 실행 로그와 CI `Structural and synthetic QA`에서 확인합니다. Windows 실제 설치 및 법률 전문가의 사건별 판단 검증은 포함되지 않습니다.
