# Essentia 단독 멜로디 파이프라인 - Note F1 평가

## TL;DR

> **Quick Summary**: Essentia 단독 멜로디 추출의 실제 성능을 mir_eval Note F1 (50ms tolerance)로 측정하고, 8곡 모두 70% 이상 달성 여부를 검증한다.
> 
> **Deliverables**:
> - 새로운 테스트 클래스 `TestEssentiaNoteF1` 추가
> - 8곡 개별 Note F1 결과 보고
> - 기준선 측정 (70% 달성 가능성 조기 판단)
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential (baseline 결과에 따라 진행)
> **Critical Path**: Task 1 → Task 2 → Task 3

---

## Context

### Original Request
Essentia 단독 사용으로 멜로디 추출 파이프라인을 구현하고, Note F1 >= 70% 달성 여부를 검증한다.

### Interview Summary
**Key Discussions**:
- **접근법**: Essentia 단독 사용 (Oracle 권장 하이브리드 방식 거부)
- **평가 지표**: Note F1 (mir_eval, 50ms onset tolerance, 50 cents pitch tolerance)
- **목표**: 8곡 모두 개별적으로 Note F1 >= 70%
- **개선 없음**: Essentia 파라미터 튜닝/F0→Note 변환 개선 없이 현재 상태로 진행
- **실패 시**: 결과 보고 (폴백/목표 하향 없음)

**Research Findings (Oracle)**:
- pitch_class_similarity는 시간/리듬 무시, 옥타브 무시로 과대평가
- 이전 스파이크의 "31%"는 3000ms onset tolerance 사용한 pitch_class_similarity
- mir_eval Note F1 (50ms)로 측정 시 훨씬 낮을 가능성 높음

### Metis Review
**Identified Gaps** (addressed):
- mir_eval 이미 `comparison_utils.py`에 구현됨 → 재사용
- onset tolerance 결정 필요 → 50ms로 확정
- reference 파일 결정 필요 → reference.mid로 확정
- 기준선 측정 필요 → Task 1로 선행 실행
- Essentia 0 notes 출력 시 처리 → F1=0으로 보고

---

## Work Objectives

### Core Objective
Essentia 단독 멜로디 추출의 실제 품질을 업계 표준 지표(mir_eval Note F1)로 측정하고, 70% 목표 달성 가능성을 객관적으로 평가한다.

### Concrete Deliverables
- `backend/tests/golden/test_golden.py`에 `TestEssentiaNoteF1` 클래스 추가
- `.sisyphus/evidence/essentia-note-f1-baseline.json` 결과 파일

### Definition of Done
- [ ] `pytest tests/golden/test_golden.py::TestEssentiaNoteF1 -v` 실행 완료 (pass/fail 무관)
- [ ] 8곡 모두 Note F1 수치 보고됨
- [ ] 70% 달성 곡 수 및 평균 보고됨

### Must Have
- mir_eval Note F1 사용 (50ms onset, 50 cents pitch)
- reference.mid를 ground truth로 사용
- 8곡 개별 결과 보고 (song_01 ~ song_08)
- Essentia WSL 호출하여 멜로디 추출

### Must NOT Have (Guardrails)
- Essentia 파라미터 튜닝 (CONFIDENCE_THRESHOLD, HOP_SIZE 등 변경 금지)
- F0→Note 변환 알고리즘 수정 금지
- Basic Pitch 하이브리드 접근법 구현 금지
- 새로운 TDD 테스트 추가 금지 (기존 골든 테스트 패턴만 사용)
- 목표 threshold 하향 금지 (70% 유지)
- tolerance 변경 실험 금지 (50ms 고정)

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> 모든 검증은 agent가 직접 실행한다. 사용자 수동 테스트/확인 불필요.

### Test Decision
- **Infrastructure exists**: YES (`pytest` + `mir_eval` 이미 설치됨)
- **Automated tests**: 기존 골든 테스트만 사용
- **Framework**: pytest

### Agent-Executed QA Scenarios (MANDATORY)

**Verification Tool**: Bash (pytest)

```
Scenario: Essentia Note F1 테스트 실행
  Tool: Bash (pytest in WSL)
  Preconditions: WSL 실행 가능, Essentia 설치됨, 테스트 데이터 존재
  Steps:
    1. cd /mnt/c/Users/handuk.lee/projects/mk-pinano-sheet/backend
    2. pytest tests/golden/test_golden.py::TestEssentiaNoteF1 -v --tb=short 2>&1
    3. Assert: 출력에 "song_01" ~ "song_08" 각각의 Note F1 수치 포함
    4. Assert: "PASSED" 또는 "FAILED" 상태 표시
    5. 결과를 .sisyphus/evidence/essentia-note-f1-result.txt에 저장
  Expected Result: 8곡 모두 테스트 실행 완료 (pass/fail 무관)
  Evidence: .sisyphus/evidence/essentia-note-f1-result.txt

Scenario: Essentia 출력 0개 노트 처리
  Tool: Bash
  Preconditions: 특정 곡에서 Essentia가 0개 노트 반환할 수 있음
  Steps:
    1. 테스트 실행 중 0개 노트 시 F1=0.0으로 보고
    2. Assert: 테스트가 crash하지 않고 0.0 보고
  Expected Result: 에러 없이 0.0 보고
  Evidence: 테스트 출력에 "F1 = 0.00" 또는 유사 표현
```

---

## Execution Strategy

### Sequential Execution (기준선 결과에 따라 진행)

```
Task 1: 기준선 측정 (Essentia Note F1 실제 수치)
    ↓
Task 2: TestEssentiaNoteF1 클래스 구현
    ↓
Task 3: 최종 결과 보고
```

**Critical Path**: Task 1 → Task 2 → Task 3

### Dependency Matrix

| Task | Depends On | Blocks | Note |
|------|------------|--------|------|
| 1 | None | 2, 3 | 기준선 없이 진행 불가 |
| 2 | 1 | 3 | 기준선 수치 확인 후 구현 |
| 3 | 2 | None | 최종 보고 |

---

## TODOs

- [x] 1. 기준선 측정: Essentia Note F1 (50ms) 실제 수치 측정 — avg 0.49%, max 1.03%

  **What to do**:
  - WSL에서 Essentia로 8곡 멜로디 추출
  - reference.mid와 mir_eval Note F1 비교 (50ms onset, 50 cents pitch)
  - 각 곡별 F1, Precision, Recall 수치 기록
  - 평균 F1 및 70% 달성 곡 수 보고

  **Must NOT do**:
  - Essentia 파라미터 변경 (CONFIDENCE_THRESHOLD=0.3 유지)
  - tolerance 변경 (50ms 고정)
  - 결과가 낮아도 개선 시도 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: 단순 스크립트 실행 및 결과 수집
  - **Skills**: []
    - 추가 스킬 불필요 (bash 실행만)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 2, Task 3
  - **Blocked By**: None

  **References**:
  
  **Pattern References**:
  - `backend/scripts/spike_essentia.py` - Essentia 호출 패턴 (단, 3000ms tolerance 사용 - 참고만)
  - `backend/core/comparison_utils.py:128-191` - `compute_mir_eval_metrics()` 함수 - mir_eval 호출 방법
  
  **API/Type References**:
  - `backend/core/comparison_utils.py:45-56` - `NoteEvent` 데이터 클래스 정의
  - `backend/scripts/essentia_melody_extractor.py:78-165` - Essentia 출력 형식 `{"pitch", "onset", "duration"}`
  
  **Test Data References**:
  - `backend/tests/golden/data/song_01/input.mp3` ~ `song_08/input.mp3` - 입력 오디오
  - `backend/tests/golden/data/song_01/reference.mid` ~ `song_08/reference.mid` - Ground truth
  
  **External References**:
  - mir_eval docs: `https://craffel.github.io/mir_eval/#mir_eval.transcription.precision_recall_f1_overlap`

  **WHY Each Reference Matters**:
  - `compute_mir_eval_metrics()`: 이 함수를 그대로 사용. onset_tolerance=0.05 전달
  - `NoteEvent`: Essentia 출력을 이 형식으로 변환 필요
  - `essentia_melody_extractor.py`: WSL 호출 시 JSON 파싱 방법 확인

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: 8곡 기준선 측정 완료
    Tool: Bash (WSL)
    Preconditions: WSL 환경, Essentia 설치, 테스트 데이터 존재
    Steps:
      1. 기준선 측정 스크립트 작성 및 실행
         - 입력: song_01~08의 input.mp3
         - Essentia 호출 → 멜로디 노트 추출
         - reference.mid 로드 → NoteEvent 변환
         - compute_mir_eval_metrics(ref, gen, onset_tolerance=0.05) 호출
      2. 결과 JSON 파일 생성:
         {
           "results": [
             {"song_id": "song_01", "f1": 0.XX, "precision": 0.XX, "recall": 0.XX, "ref_notes": N, "gen_notes": M},
             ...
           ],
           "summary": {
             "average_f1": 0.XX,
             "songs_above_70pct": N,
             "min_f1": 0.XX,
             "max_f1": 0.XX
           }
         }
      3. Assert: results 배열에 8개 항목 존재
      4. Assert: 각 항목에 f1, precision, recall 키 존재
    Expected Result: .sisyphus/evidence/essentia-note-f1-baseline.json 생성
    Evidence: .sisyphus/evidence/essentia-note-f1-baseline.json

  Scenario: 70% 달성 불가능 조기 감지
    Tool: Bash (cat + jq)
    Preconditions: baseline.json 생성 완료
    Steps:
      1. cat .sisyphus/evidence/essentia-note-f1-baseline.json | jq '.summary.average_f1'
      2. 평균이 30% 미만이면 조기 경고 출력
      3. 최대값도 70% 미만이면 "70% 목표 달성 불가능" 보고
    Expected Result: 조기 판단 정보 제공
    Evidence: 콘솔 출력

  Scenario: Essentia 0개 노트 반환 시 처리
    Tool: Bash
    Steps:
      1. 특정 곡에서 Essentia가 빈 배열 [] 반환 시
      2. F1=0.0, Precision=0.0, Recall=0.0으로 기록
      3. Assert: 스크립트 crash 없음
    Expected Result: 0.0으로 정상 기록
    Evidence: baseline.json에 해당 곡 f1=0.0 기록
  ```

  **Commit**: NO (스크립트 실행만, 코드 변경 없음)

---

- [x] 2. TestEssentiaNoteF1 클래스 구현

  **What to do**:
  - `backend/tests/golden/test_golden.py`에 `TestEssentiaNoteF1` 클래스 추가
  - 기존 `TestMIDIComparison` 패턴 따르기
  - Essentia WSL 호출 → reference.mid와 mir_eval Note F1 비교
  - 70% threshold assertion (모든 곡 개별)

  **Must NOT do**:
  - 기존 테스트 클래스 수정 (`TestMelodyComparison`, `TestMIDIComparison` 등)
  - tolerance 파라미터화 (50ms 하드코딩)
  - 새로운 comparison 함수 작성 (기존 `compute_mir_eval_metrics` 사용)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: 기존 패턴 복사하여 수정하는 단순 작업
  - **Skills**: []
    - 추가 스킬 불필요

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 3
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `backend/tests/golden/test_golden.py:401-494` - `TestMIDIComparison` 클래스 - 테스트 구조 패턴
  - `backend/tests/golden/test_golden.py:303-398` - `TestMelodyComparison` 클래스 - 멜로디 비교 패턴
  - `backend/core/melody_extractor.py:extract_melody_with_audio()` - Essentia 호출 방법

  **API/Type References**:
  - `backend/core/comparison_utils.py:128-191` - `compute_mir_eval_metrics()` - 사용할 함수
  - `backend/core/comparison_utils.py:45-56` - `NoteEvent` - 변환 대상 타입

  **Test References**:
  - `backend/tests/golden/conftest.py` - pytest fixtures (`golden_data_dir`, `job_storage_path`)

  **WHY Each Reference Matters**:
  - `TestMIDIComparison`: 이 클래스 구조를 그대로 복사하여 Essentia용으로 수정
  - `compute_mir_eval_metrics()`: onset_tolerance=0.05 전달하여 호출
  - conftest.py: fixture 이름 확인 (`golden_data_dir` 등)

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: TestEssentiaNoteF1 테스트 실행
    Tool: Bash (pytest in WSL)
    Preconditions: 테스트 클래스 구현 완료
    Steps:
      1. cd /mnt/c/Users/handuk.lee/projects/mk-pinano-sheet/backend
      2. pytest tests/golden/test_golden.py::TestEssentiaNoteF1 -v --tb=short 2>&1
      3. Assert: 출력에 "test_essentia_note_f1[song_01]" ~ "[song_08]" 포함
      4. Assert: 각 테스트에 "Note F1 = X.XX%" 출력
      5. 결과 저장: > .sisyphus/evidence/essentia-note-f1-result.txt
    Expected Result: 8개 테스트 모두 실행 (pass/fail 기록)
    Evidence: .sisyphus/evidence/essentia-note-f1-result.txt

  Scenario: 70% 미달 시 테스트 실패 확인
    Tool: Bash
    Preconditions: 기준선에서 70% 미달 확인됨
    Steps:
      1. pytest 실행 결과에서 FAILED 테스트 확인
      2. Assert: assertion message에 "below threshold 70%" 포함
    Expected Result: 명확한 실패 메시지
    Evidence: pytest 출력

  Scenario: 기존 테스트 영향 없음 확인
    Tool: Bash
    Preconditions: TestEssentiaNoteF1 추가 후
    Steps:
      1. pytest tests/golden/test_golden.py::TestMIDIComparison -v --tb=short
      2. pytest tests/golden/test_golden.py::TestMelodyComparison -v --tb=short
      3. Assert: 기존 테스트 결과 변경 없음
    Expected Result: 기존 테스트 정상 작동
    Evidence: pytest 출력
  ```

  **Commit**: YES
  - Message: `test(golden): add TestEssentiaNoteF1 class for Essentia standalone evaluation`
  - Files: `backend/tests/golden/test_golden.py`
  - Pre-commit: `pytest tests/golden/test_golden.py::TestEssentiaNoteF1 -v --tb=short`

---

- [x] 3. 최종 결과 보고

  **What to do**:
  - 기준선 측정 결과 + 테스트 결과 종합
  - 70% 목표 달성 여부 명확히 보고
  - 각 곡별 상세 수치 테이블 형식으로 정리
  - 사용자 요청대로 "결과 보고" 수행

  **Must NOT do**:
  - 목표 달성 실패 시 개선 제안 금지 (사용자 요청: 결과만 보고)
  - 추가 실험 제안 금지

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 결과 정리 및 보고서 작성
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 1, Task 2

  **References**:

  **Evidence References**:
  - `.sisyphus/evidence/essentia-note-f1-baseline.json` - 기준선 측정 결과
  - `.sisyphus/evidence/essentia-note-f1-result.txt` - pytest 실행 결과

  **WHY Each Reference Matters**:
  - baseline.json: 상세 수치 추출
  - result.txt: pass/fail 상태 확인

  **Acceptance Criteria**:

  **Agent-Executed QA Scenarios:**

  ```
  Scenario: 최종 보고서 생성
    Tool: Bash (cat)
    Steps:
      1. .sisyphus/evidence/essentia-note-f1-baseline.json 읽기
      2. 다음 형식으로 요약:
         | Song | Note F1 | Precision | Recall | Status |
         |------|---------|-----------|--------|--------|
         | song_01 | XX.X% | XX.X% | XX.X% | PASS/FAIL |
         ...
         | AVERAGE | XX.X% | - | - | X/8 PASS |
      3. 70% 달성 여부 결론 명시
    Expected Result: 보고서 출력
    Evidence: 콘솔 출력 또는 .sisyphus/evidence/final-report.md

  Scenario: 목표 달성 실패 시 명확한 결론
    Tool: Bash
    Preconditions: 평균 F1 < 70% 또는 일부 곡 < 70%
    Steps:
      1. "목표 미달: X곡이 70% 미만" 출력
      2. 가장 낮은 곡, 가장 높은 곡 명시
    Expected Result: 실패 사실 명확히 전달
    Evidence: 보고서 내용
  ```

  **Commit**: NO (보고서만, 코드 변경 없음)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | (no commit) | - | baseline.json 생성 확인 |
| 2 | `test(golden): add TestEssentiaNoteF1 for Essentia standalone evaluation` | `test_golden.py` | pytest 실행 |
| 3 | (no commit) | - | 보고서 출력 확인 |

---

## Success Criteria

### Verification Commands
```bash
# 기준선 확인
cat .sisyphus/evidence/essentia-note-f1-baseline.json | jq '.summary'

# 테스트 실행
cd /mnt/c/Users/handuk.lee/projects/mk-pinano-sheet/backend
pytest tests/golden/test_golden.py::TestEssentiaNoteF1 -v --tb=short
```

### Final Checklist
- [ ] 8곡 모두 Note F1 수치 측정됨
- [ ] 70% 달성 곡 수 보고됨
- [ ] 테스트 클래스 추가됨 (TestEssentiaNoteF1)
- [ ] 기존 테스트 영향 없음 확인됨
- [ ] Essentia 파라미터 변경 없음 (CONFIDENCE_THRESHOLD=0.3 유지)
- [ ] tolerance 50ms 고정 유지됨
