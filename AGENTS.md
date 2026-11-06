# LegalWriting Strategy MasterKit V5 — Codex 상시규칙

SSOT = `docs/00_최종_통합마스터_V5.md`. 과거 V4.1 문서의 '최종본' 문구는 참고 이력이다.
1. 법원/수사기관 제출서면의 법리·증거·기한·진정성·반대자료를 임의 창작·변형·은폐 금지. 확인되지 않으면 `UNVERIFIED`.
2. 전략 작업은 `prompts/strategy/S0..S6` 중 현재 단계, 기존서면 수정은 `prompts/P0..P8` 중 해당 단계만 열람. 전체 파일을 매번 통째로 읽지 않는다.
3. 판단자의 유죄/기소/승소 결과를 보장하지 않고, 불리한 증거의 최강 해석·반론을 공정하게 검토한다.
4. 조문/판례는 해당 시점 원문을 검증한다. 사람·날짜·금액·인용·도표 관계는 원증거에 역추적.
5. 원본은 읽기 전용, 변경은 diff와 새 파일로. 기밀 자료 외부 전송·기관 제출·공개 커밋·main 병합은 명시 승인 없이 금지.
6. 도구 기본명령은 `config/tool_catalog.json`에 있으며 실제 설치/렌더 결과가 없으면 PASS 단정 금지.
7. 최종 상태는 `READY_FOR_HUMAN_REVIEW`, `NEEDS_VERIFICATION`, `SUBMISSION_BLOCKED` 중 하나. 사건별 법률가의 검토가 필요하다.
