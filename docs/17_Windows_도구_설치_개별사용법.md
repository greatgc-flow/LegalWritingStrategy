# 제17장. Windows AI CLI 법률문서 도구 설치·확인·사용법

기본 원칙: 회사 PC라면 설치권한·보안정책 우선. 패키지의 스크립트는 **기본 미리보기**, `-Apply`에서도 앱별 승인 필요. 도구의 설치 성공 여부는 **사용자 PC에서 직접 확인**. 플러그인·패키지 버전·라이선스는 설치 시 공식 출처로 확인.

| 도구 | 역할 | 권장 설치경로 | 확인명령 | 사용예 |
|---|---|---|---|---|
| Python 3.12 | QA/문서생성 | `winget install --id Python.Python.3.12 -e` | `py -3.12 --version` | `py -3.12 -m venv .venv` |
| Pandoc | Markdown→DOCX/HTML | `winget install --id JohnMacFarlane.Pandoc -e` | `pandoc --version` | `pandoc draft.md -o draft.docx` |
| LibreOffice | DOCX→PDF 렌더 | `winget install --id TheDocumentFoundation.LibreOffice -e` | `soffice --version` (PATH 설정 필요할 수 있음) | `soffice --headless --convert-to pdf --outdir out draft.docx` |
| Git | 원문·diff·버전관리 | `winget install --id Git.Git -e` | `git --version` | `git diff --word-diff` |
| Graphviz | 관계·자금 흐름도 | `winget install --id Graphviz.Graphviz -e` | `dot -V` | `dot -Tsvg map.dot -o map.svg` |
| Zotero | 학술서지·Word 인용 | `winget install --id DigitalScholar.Zotero -e` (ID 확인) | 앱 실행 | Word Zotero 메뉴로 참고문헌 |
| Node.js LTS | Mermaid CLI 전제 | `winget install --id OpenJS.NodeJS.LTS -e` | `node -v; npm -v` | `npm install -g @mermaid-js/mermaid-cli` |
| Mermaid CLI | 흐름도/절차 | 공식 https://github.com/mermaid-js/mermaid-cli | `mmdc -h` | `mmdc -i flow.mmd -o flow.svg` |
| PyMuPDF | PDF 텍스트·페이지 검사 | `.venv` 안 `python -m pip install pymupdf` | `python -c "import fitz;print('OK')"` | `python scripts/legal_qa.py --pdf file.pdf` |
| python-docx | Word 자동작성 | `.venv` 안 `python -m pip install python-docx` | `python -c "import docx;print('OK')"` | 표, 스타일, 쪽설정 |
| matplotlib | 시계열·비교차트 | `.venv` 안 `python -m pip install matplotlib` | `python -c "import matplotlib"` | `examples/plot_transaction.py` |

**PowerShell 예시:**

```powershell
# 1. 미리보기 후 앱별 동의 설치
.\scripts\install_windows.ps1
.\scripts\install_windows.ps1 -Apply

# 2. 프로젝트 독립 환경
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 기본 QA
.\.venv\Scripts\python.exe -m unittest discover -s scripts -p 'test_qa.py' -v
.\.venv\Scripts\python.exe scripts\legal_qa.py --record examples\synthetic_case.json
.\.venv\Scripts\python.exe scripts\strategy_qa.py --record examples\synthetic_strategy_case.json
```

**새 자료는 사용자 승인 없이 외부로 올리거나 공개 AI 서비스에 붙여 넣지 않는다.** `README.md` → `AGENTS.md` → `config/tool_catalog.json` → 현재 단계 프롬프트만 읽으면 긴 도구 설명의 반복 전송을 줄일 수 있다.

**Mac/Linux:** 명령 및 보안 동작이 다름; Windows PowerShell 스크립트 그대로 실행 금지.

## 공식 출처

https://pandoc.org/installing.html

https://www.libreoffice.org/download/

https://graphviz.org/download/

https://github.com/mermaid-js/mermaid-cli

https://python-docx.readthedocs.io/

https://pymupdf.readthedocs.io/en/latest/installation.html

https://www.zotero.org/support/word_processor_integration
