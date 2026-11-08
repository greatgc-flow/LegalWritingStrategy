# v5.0.0 — Strategy MasterKit 초기 공개 릴리즈

- 대한민국 법률서면 연구·전략·문체·증거·시각화·AI 수정 절차 통합.
- V5 단일 기준본, S0~S6 사건전략, P0~P8 기존문서 교정 프롬프트.
- 불리한 증거 독립감사(ADVERSE-8)와 경찰·검사·법관별 인용 가능 문장 검증.
- 한글 폰트·Windows 설치 가이드, AI CLI 토큰 최적화, 재현 가능한 QA 스크립트.
- 자료는 가상 사례와 출처가 확인된 공개 메타정보 위주로만 제공. 실제 사건별 법률·원증거 검증은 별도.

**검증:** 가상 회귀시험의 현재 결과는 `python -m unittest discover -s scripts -p 'test_*.py'` 실행 로그와 CI `Structural and synthetic QA`에서 확인합니다. Windows 실제 설치 및 법률 전문가의 사건별 판단 검증은 포함되지 않습니다.
