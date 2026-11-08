# 최종 검토 체크리스트 V4.1

- [x] ZIP 무결성, 상대경로 매니페스트 SHA-256
- [x] README, 마스터 SSOT, P0~P8 경로 일치
- [x] 단계별 프롬프트 파일 9개 + 공통 1개
- [ ] 자동 테스트 현재 결과 확인: `python -m unittest discover -s scripts -p 'test_*.py'` 실행 로그 또는 CI `Structural and synthetic QA`
- [x] 민사·형사 DOCX 2종 PDF 예제 시각 재검토
- [x] 민사 A4 45/30/20/20mm·12pt·1.5줄 구조 확인
- [x] PDF 한글 텍스트 추출 및 글꼴 포함 기록 확인
- [x] 공식법령: 민사소송규칙 제4조/제69조의4, 형사소송법 제245조의7 조문 재확인
- [x] 핵심 서지 수정: L06/L14/L20/L28/L32/L35/L40, L41/L42 추가
- [ ] 나머지 문헌의 모든 전문과 방법론 독립 검토 (NOT_TESTED)
- [ ] 실제 Windows 11 및 설치 스크립트 작동 시험 (NOT_TESTED)
- [ ] HWP/HWPX 렌더 및 실제 기관 접수 (NOT_TESTED)
- [ ] 사건별 법률시점·원증거 진정성·상대방 자료 검증 (NOT_TESTED)
- [ ] 경찰/검사/법관 독자 대상 통제 실험 (NOT_TESTED)

**최종 판정:** `NEEDS_VERIFICATION`. 과거 패키지 구조·상호참조·가상 테스트 기록은 현재 작업 트리에서 재확인한다. 실제 사건 적용 전 법률가의 검토가 필요하다. 허용 최종 판정값은 `READY_FOR_HUMAN_REVIEW / NEEDS_VERIFICATION / SUBMISSION_BLOCKED`이다.

항목별 미실시 검사는 `NOT_TESTED`로 기록한다.
