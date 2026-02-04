# MusicXML 기준 골드 테스트 시스템 구축

## TL;DR

> **Quick Summary**: 기존 reference.mxl 파일과 생성된 MusicXML을 비교하여 85% 이상 유사도를 검증하는 골드 테스트 시스템 구축. Playwright E2E로 전체 플로우 검증.
> 
> **Deliverables**:
> - `core/musicxml_comparator.py` - MusicXML 비교 모듈
> - `tests/golden/test_golden.py` 확장 - compare 모드 추가
> - Playwright E2E 골드 테스트 스크립트
> - 8곡 비교 테스트 실행 및 결과
> 
> **Estimated Effort**: Medium (4-6시간)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4

---

## Context

### Original Request
- Phase 2는 진행하지 않음
- 제공된 MusicXML 기준으로 골드 테스트 로직 추가
- E2E 골드 테스트 진행

### Interview Summary
**Key Discussions**:
- 비교 방식: 음표 기반 (pitch, onset, duration) + 구조적 비교 (마디, 박자, 조성) 둘 다
- 통과 기준: 85% 이상 유사도
- 난이도: medium 기준, 개선 방향 없으면 hard도 고려
- E2E 방식: Playwright MCP 브라우저 테스트

**Research Findings**:
- 8곡 모두 `backend/tests/golden/data/song_XX/reference.mxl` 존재
- metadata.json에 `has_reference: true, source: manual_transcription`
- music21이 프로젝트에서 이미 사용 중
- MXL = 압축된 MusicXML (music21이 직접 파싱 가능)

### Metis Review
**Identified Gaps** (addressed):
- Tolerance 미정의 → 기본값 적용 (onset ±100ms, duration ±20%)
- 유사도 계산 방식 → Note matching rate (matched / max(ref, gen))
- E2E 시나리오 미정의 → Playwright MCP 액션으로 구체화
- Reference 구조 미검증 → 파싱 시 검증 로직 추가
- 실패 시 출력 형식 → JSON (similarity, passed, details)

---

## Work Objectives

### Core Objective
기존 reference.mxl 파일과 시스템이 생성한 sheet_medium.musicxml을 비교하여 85% 이상 유사도를 달성하는지 검증하는 자동화된 골드 테스트 시스템 구축

### Concrete Deliverables
- `backend/core/musicxml_comparator.py` - MusicXML 비교 모듈
- `backend/tests/golden/test_golden.py` - compare 모드 추가 (`@pytest.mark.compare`)
- Playwright E2E 테스트 스크립트 (8곡 업로드 → 처리 → 비교)
- 테스트 실행 결과 리포트

### Definition of Done
- [ ] `pytest tests/golden/ -m compare -v` → 8곡 모두 PASSED
- [ ] 각 곡별 similarity >= 0.85 확인
- [ ] Playwright E2E로 전체 플로우 검증 완료
- [ ] 비교 결과 JSON 출력 확인

### Must Have
- MusicXML 비교 로직 (음표 + 구조)
- 85% threshold 검증
- 8곡 전체 테스트
- E2E 브라우저 테스트

### Must NOT Have (Guardrails)
- ❌ 기존 `core/*.py` 모듈 수정 금지 (신규 파일만)
- ❌ reference.mxl 파일 수정 금지 (읽기 전용)
- ❌ 자동 수정(auto-fix) 기능 금지 (비교만)
- ❌ Phase 2 정확도 측정 기능 (Reference MIDI 기반) 금지
- ❌ easy/hard 난이도 비교 (medium만)
- ❌ CI 통합 (이번 범위 아님)

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: Tests-after (비교 모듈 구현 후 테스트)
- **Framework**: pytest

### Agent-Executed QA Scenarios (MANDATORY)

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Backend Unit Test** | Bash (pytest) | pytest 실행, exit code 0 확인 |
| **MusicXML Comparison** | Bash (python) | 비교 스크립트 실행, JSON 출력 확인 |
| **E2E Test** | Playwright MCP | 브라우저 조작, 파일 다운로드, 비교 |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
└── Task 1: MusicXML Comparator 모듈 구현

Wave 2 (After Wave 1):
├── Task 2: Golden Test compare 모드 추가
└── Task 3: 8곡 비교 기준선 테스트 (초기 실행)

Wave 3 (After Wave 2):
└── Task 4: Playwright E2E 골드 테스트

Critical Path: Task 1 → Task 2 → Task 4
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3 | None |
| 2 | 1 | 4 | 3 |
| 3 | 1 | 4 | 2 |
| 4 | 2, 3 | None | None (final) |

---

## TODOs

- [x] 1. MusicXML Comparator 모듈 구현

  **What to do**:
  - `backend/core/musicxml_comparator.py` 신규 생성
  - music21을 사용하여 MusicXML/MXL 파싱
  - 음표 기반 비교: pitch, onset, duration
  - 구조적 비교: 마디 수, 박자표, 조성
  - 유사도 계산 및 threshold 검증
  - JSON 형식 결과 반환

  **비교 알고리즘 상세**:
  ```python
  # 허용 오차 (Tolerance)
  ONSET_TOLERANCE = 0.1   # 100ms
  DURATION_TOLERANCE_RATIO = 0.2  # 20%
  SIMILARITY_THRESHOLD = 0.85  # 85%
  
  # 유사도 계산
  # matched_notes = reference와 generated 중 일치하는 노트 수
  # similarity = matched_notes / max(len(ref_notes), len(gen_notes))
  ```

  **Must NOT do**:
  - 기존 core/*.py 파일 수정
  - 자동 수정 기능 구현

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 음악 도메인 지식 + music21 라이브러리 활용 필요
  - **Skills**: []
    - 특별한 스킬 불필요

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (단독)
  - **Blocks**: Task 2, Task 3
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `backend/core/midi_to_musicxml.py` - music21 사용 패턴 참조
  - `backend/core/midi_parser.py` - Note 데이터 구조 참조

  **API/Type References**:
  - `backend/core/midi_parser.py:Note` - onset, duration, pitch 필드

  **External References**:
  - music21 documentation: MXL 파싱, Note 비교

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Comparator 모듈 import 성공
    Tool: Bash (python)
    Preconditions: backend 디렉토리에서 실행
    Steps:
      1. cd backend && python -c "from core.musicxml_comparator import compare_musicxml; print('OK')"
    Expected Result: "OK" 출력, exit code 0
    Evidence: stdout 캡처

  Scenario: 동일 파일 비교 시 100% 유사도
    Tool: Bash (python)
    Preconditions: reference.mxl 파일 존재
    Steps:
      1. cd backend && python -c "
         from core.musicxml_comparator import compare_musicxml
         result = compare_musicxml(
             'tests/golden/data/song_01/reference.mxl',
             'tests/golden/data/song_01/reference.mxl'
         )
         assert result['similarity'] == 1.0
         assert result['passed'] == True
         print('PASS: identical files = 100%')
         "
    Expected Result: "PASS: identical files = 100%" 출력
    Evidence: stdout 캡처

  Scenario: 빈 파일/잘못된 형식 처리
    Tool: Bash (python)
    Preconditions: None
    Steps:
      1. cd backend && python -c "
         from core.musicxml_comparator import compare_musicxml, ComparisonError
         try:
             compare_musicxml('nonexistent.mxl', 'nonexistent.mxl')
             print('FAIL: should raise error')
         except (ComparisonError, FileNotFoundError):
             print('PASS: error handled correctly')
         "
    Expected Result: "PASS: error handled correctly" 출력
    Evidence: stdout 캡처
  ```

  **Commit**: YES
  - Message: `feat(golden): add MusicXML comparator module`
  - Files: `backend/core/musicxml_comparator.py`

---

- [x] 2. Golden Test compare 모드 추가

  **What to do**:
  - `backend/tests/golden/test_golden.py`에 새 테스트 클래스 추가
  - `@pytest.mark.compare` 마커 등록
  - 8곡 각각에 대해 비교 테스트 parametrize
  - conftest.py에 golden_data_dir fixture 추가
  - 기존 smoke 모드는 100% 유지

  **테스트 플로우**:
  1. golden data에서 input.mp3 로드
  2. 전체 파이프라인 실행 (audio → MIDI → MusicXML)
  3. 생성된 sheet_medium.musicxml과 reference.mxl 비교
  4. similarity >= 0.85 검증

  **Must NOT do**:
  - 기존 TestGoldenSmoke 클래스 수정
  - /app/test/ 경로 하드코딩

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 기존 패턴 따라 테스트 클래스 추가하는 단순 작업
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 3)
  - **Blocks**: Task 4
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `backend/tests/golden/test_golden.py:TestGoldenSmoke` - 기존 테스트 구조
  - `backend/tests/golden/conftest.py` - fixture 패턴

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: compare 마커 등록 확인
    Tool: Bash (pytest)
    Preconditions: Docker 컨테이너 실행 중
    Steps:
      1. docker compose exec backend pytest tests/golden/ --collect-only -m compare
    Expected Result: "8 tests collected" 또는 유사 출력
    Evidence: stdout 캡처

  Scenario: smoke 모드 여전히 동작
    Tool: Bash (pytest)
    Preconditions: Docker 컨테이너 실행 중
    Steps:
      1. docker compose exec backend pytest tests/golden/ --collect-only -m smoke
    Expected Result: 기존 smoke 테스트 수집됨
    Evidence: stdout 캡처
  ```

  **Commit**: YES
  - Message: `test(golden): add compare mode for MusicXML comparison`
  - Files: `backend/tests/golden/test_golden.py`, `backend/tests/golden/conftest.py`

---

- [x] 3. 8곡 비교 기준선 테스트 실행

  **What to do**:
  - Docker 환경에서 8곡 처리 실행
  - 각 곡의 sheet_medium.musicxml 생성
  - reference.mxl과 비교하여 기준선 유사도 측정
  - 85% 미만인 곡 식별 및 분석
  - medium에서 개선 어려우면 hard 난이도 고려

  **Must NOT do**:
  - reference.mxl 수정
  - threshold 임의 조정

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: 테스트 실행 및 결과 분석
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Task 2)
  - **Blocks**: Task 4
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `backend/tests/golden/data/song_*/` - 8곡 테스트 데이터

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: 8곡 전체 비교 테스트 실행
    Tool: Bash (pytest)
    Preconditions: Docker 컨테이너 실행 중, Task 1, 2 완료
    Steps:
      1. docker compose exec backend pytest tests/golden/test_golden.py -m compare -v --tb=short
      2. 결과에서 각 곡별 similarity 확인
    Expected Result: 테스트 실행 완료, 각 곡별 결과 출력
    Evidence: pytest 출력 캡처

  Scenario: 기준선 리포트 생성
    Tool: Bash (python)
    Preconditions: 8곡 테스트 완료
    Steps:
      1. 각 곡의 similarity 값을 JSON으로 정리
      2. 85% 미만인 곡 목록 출력
    Expected Result: JSON 형식 리포트, 개선 필요한 곡 식별
    Evidence: JSON 파일 저장
  ```

  **Commit**: NO (테스트 실행 결과만)

---

- [ ] 4. Playwright E2E 골드 테스트

  **What to do**:
  - Playwright MCP를 사용한 브라우저 E2E 테스트
  - 8곡 각각에 대해:
    1. http://localhost:3000 접속
    2. MP3 파일 업로드 (input.mp3)
    3. 처리 완료 대기 (progress 100%)
    4. 결과 페이지에서 MIDI/MusicXML 다운로드 가능 확인
    5. (선택) 다운로드한 MusicXML과 reference 비교

  **E2E 시나리오 상세**:
  ```
  1. Navigate to http://localhost:3000
  2. Wait for file upload area visible
  3. Upload: backend/tests/golden/data/song_XX/input.mp3
  4. Wait for processing complete (progress bar 100% 또는 결과 페이지)
  5. Assert: "Your Sheet Music" 또는 결과 페이지 요소 visible
  6. Assert: Download MIDI button exists
  7. Assert: Download MusicXML button exists
  8. Screenshot: .sisyphus/evidence/golden-e2e/song_XX_result.png
  ```

  **Must NOT do**:
  - 실제 YouTube URL 테스트 (MP3 업로드만)
  - 수동 브라우저 조작 요청

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Playwright 브라우저 자동화
  - **Skills**: [`playwright`]
    - playwright: Playwright MCP 사용

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (final)
  - **Blocks**: None
  - **Blocked By**: Task 2, Task 3

  **References**:

  **Pattern References**:
  - `.sisyphus/evidence/e2e/` - 기존 E2E 테스트 증거 패턴

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: Song 01 E2E 업로드 및 처리
    Tool: Playwright MCP
    Preconditions: Docker 서비스 실행 중 (localhost:3000, localhost:8000)
    Steps:
      1. Navigate to: http://localhost:3000
      2. Wait for: 파일 업로드 영역 visible (timeout: 10s)
      3. Upload file: backend/tests/golden/data/song_01/input.mp3
      4. Wait for: 처리 완료 (progress 100% 또는 결과 페이지, timeout: 180s)
      5. Assert: 결과 페이지 요소 visible
      6. Assert: MIDI 다운로드 버튼 존재
      7. Screenshot: .sisyphus/evidence/golden-e2e/song_01_result.png
    Expected Result: 처리 완료, 결과 페이지 표시, 다운로드 버튼 존재
    Evidence: .sisyphus/evidence/golden-e2e/song_01_result.png

  Scenario: 8곡 전체 E2E 테스트
    Tool: Playwright MCP
    Preconditions: Docker 서비스 실행 중
    Steps:
      1. song_01 ~ song_08 각각에 대해:
         - Navigate to http://localhost:3000
         - Upload input.mp3
         - Wait for 처리 완료
         - Screenshot 캡처
      2. 모든 곡 처리 완료 확인
    Expected Result: 8곡 모두 처리 완료, 8개 스크린샷 저장
    Evidence: .sisyphus/evidence/golden-e2e/song_*_result.png (8개)

  Scenario: E2E 실패 케이스 (존재하지 않는 파일)
    Tool: Playwright MCP
    Preconditions: Docker 서비스 실행 중
    Steps:
      1. Navigate to http://localhost:3000
      2. Try to upload non-existent file
      3. Assert: 에러 없이 처리 (파일 선택 대화상자만 표시)
    Expected Result: 브라우저 크래시 없음
    Evidence: 콘솔 에러 없음
  ```

  **Commit**: YES
  - Message: `test(e2e): add Playwright golden test for 8 songs`
  - Files: `.sisyphus/evidence/golden-e2e/*.png`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(golden): add MusicXML comparator module` | `backend/core/musicxml_comparator.py` | python import 테스트 |
| 2 | `test(golden): add compare mode for MusicXML comparison` | `test_golden.py`, `conftest.py` | pytest --collect-only |
| 4 | `test(e2e): add Playwright golden test for 8 songs` | evidence 스크린샷 | 스크린샷 존재 확인 |

---

## Success Criteria

### Verification Commands
```bash
# 1. Comparator 모듈 테스트
docker compose exec backend python -c "from core.musicxml_comparator import compare_musicxml; print('OK')"
# Expected: OK

# 2. Golden compare 테스트 실행
docker compose exec backend pytest tests/golden/ -m compare -v
# Expected: 8 passed (또는 일부 실패 시 similarity 값 확인)

# 3. E2E 증거 파일 확인
ls .sisyphus/evidence/golden-e2e/
# Expected: song_01_result.png ~ song_08_result.png (8개)
```

### Final Checklist
- [ ] MusicXML comparator 모듈 동작
- [ ] 8곡 비교 테스트 실행 완료
- [ ] 85% 이상 유사도 달성 여부 확인
- [ ] Playwright E2E 8곡 모두 처리 완료
- [ ] 증거 스크린샷 8개 저장
- [ ] 기존 smoke 모드 정상 동작 유지
