# Reference Matching V2: 사람 악보와 동일한 악보 생성

## TL;DR

> **Quick Summary**: 노트 손실 해결 → **멜로디 85%** (1차) → **전체 85%** (2차) → E2E + CI/CD
> 
> **Deliverables**:
> - `scripts/measure_note_loss.py` - 노트 손실 측정 도구
> - `core/musicxml_melody_extractor.py` - Reference 멜로디 추출
> - 8곡 **85% 멜로디** 유사도 달성 (1차 목표)
> - 8곡 **85% 전체** 유사도 달성 (2차 목표)
> - `.github/workflows/golden-tests.yml` - CI/CD (E2E 단계에서)
> 
> **Estimated Effort**: Large (3-4주)
> **Parallel Execution**: YES - 6 waves
> **Critical Path**: Task 1 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9

---

## 핵심 정책 (CRITICAL - 모든 태스크에 적용)

### Git 커밋 정책 (MANDATORY)
```
모든 task 진행 시 변경사항 즉시 커밋 + 리모트 푸쉬
- 급작스러운 종료에 대비
- 각 task 완료 시 반드시 커밋
- 중간 진행 상황도 의미 있는 단위로 커밋
- 커밋 메시지: conventional commits 형식
```

### Threshold 정책 (MANDATORY)
```
점진적 Threshold 상향 방식 채택
- ✅ 낮은 threshold에서 시작 → 점진적으로 85%까지 상향
- ✅ 최종 목표: 85% (멜로디), 이후 85% (전체)
- ❌ 최종 목표 85%를 낮추는 것은 금지 (결과 보고용 임계점 조작 금지)
- 한 번에 85%는 안 나옴 → 반복적 개선 + 테스트 사이클
```

### 기술적 유연성 (ALLOWED)
```
문제 해결을 위한 접근 방식 변경 허용:
- 라이브러리 문제 시 → 다른 라이브러리 사용 가능
- 근본적 한계 시 → 신규 ML 알고리즘 개발 가능
- 불필요한 파이프라인 단계 → 제거/수정 가능
```

### 진행 원칙
```
- 모든 테스트 및 진행은 점진적으로
- E2E 테스트: 멜로디 85% 달성 후
- CI/CD: E2E 단계에서 구현 (시간 단축)
- E2E 전까지: 내부 악보 작성 테스트로 검증
```

---

## Context

### Original Request
- 사람이 만든 악보(reference.mxl)와 동일한 악보를 생성하는 프로그램
- 점진적 목표: 50% → 70% → 85% → 95%+
- 완전 자동화 (CI/CD 통합)

### Atlas 완료 사항 (Handoff)
- ✅ MusicXML Comparator 구현 (`backend/core/musicxml_comparator.py`)
- ✅ Golden Test Compare 모드 (`backend/tests/golden/test_golden.py`)
- ✅ 기준선 테스트: 3/8 통과 (0.1% threshold)
- ⚠️ MusicXML export 85-95% 노트 손실 (미해결)
- ⚠️ Reference(전체 편곡) vs Generated(멜로디만) 불일치 (미해결)

### Metis Review
**Identified Gaps** (addressed):
- Phase 1 분할: 측정 도구 먼저, 수정은 그 다음
- Phase 2 검증: Reference 구조 분석 후 멜로디 추출
- 가드레일 필요: 노트 손실 20% 이하, 동일 skyline 알고리즘
- 범위 고정: Phase 5(전체 편곡)는 Phase 4 완료 후
- CI/CD 단순화: GitHub Actions + pytest만

---

## Work Objectives

### Core Objective
**2단계 목표**:
1. **1차 목표**: 멜로디 85% 유사도 달성 (Reference 멜로디 vs Generated 멜로디)
2. **2차 목표**: 전체 85% 유사도 달성 (Reference 전체 vs Generated 전체)

### Concrete Deliverables
- `backend/scripts/measure_note_loss.py` - 노트 손실 측정 스크립트
- `backend/core/musicxml_melody_extractor.py` - MusicXML 멜로디 추출 모듈
- 8곡 모두 **85% 멜로디** 유사도 통과 (1차)
- 8곡 모두 **85% 전체** 유사도 통과 (2차)
- `.github/workflows/golden-tests.yml` - CI 파이프라인 (E2E 단계)

### Definition of Done
- [ ] 노트 손실률 < 20% (현재 85-95%)
- [ ] Reference 멜로디 추출 동작 확인
- [ ] 8곡 모두 **85% 멜로디** 유사도 달성 (1차 완료)
- [ ] 8곡 모두 **85% 전체** 유사도 달성 (2차 완료)
- [ ] E2E 테스트 통과
- [ ] CI/CD 파이프라인 동작

### Must Have
- 노트 손실 측정 도구
- Reference 멜로디 추출
- 멜로디 vs 멜로디 비교 (85%)
- 전체 vs 전체 비교 (85%)
- E2E 테스트 (멜로디 85% 후)
- CI/CD (E2E 단계)
- 매 task Git 커밋 + 리모트 푸쉬

### Must NOT Have (Guardrails)
- ❌ reference.mxl 파일 수정 금지
- ❌ **테스트 임계값 낮추기 금지** (0.1% 같은 비현실적 값)
- ❌ 복잡한 CI 대시보드/DB 금지 (단순 GitHub Actions만)
- ❌ E2E 선행 구현 금지 (멜로디 85% 후)

### ALLOWED (기술적 유연성)
- ✅ 라이브러리 교체 가능 (music21 외 다른 라이브러리)
- ✅ 신규 ML 알고리즘 개발 가능 (필요시)
- ✅ 불필요한 파이프라인 단계 제거/수정 가능
- ✅ Basic Pitch 관련 수정 가능

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: Tests-after (구현 후 테스트)
- **Framework**: pytest + GitHub Actions

### Agent-Executed QA Scenarios

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Note Loss** | Bash (python) | `scripts/measure_note_loss.py` 실행, JSON 출력 확인 |
| **Melody Extraction** | Bash (pytest) | pytest 실행, exit code 0 확인 |
| **CI/CD** | Bash (gh) | GitHub Actions workflow 상태 확인 |
| **Similarity** | Bash (pytest) | golden test 실행, threshold 통과 확인 |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: 노트 손실 측정 도구 구현
└── Task 2: Reference 구조 분석

Wave 2 (After Wave 1):
├── Task 3: MusicXML Export 노트 손실 수정 (라이브러리 교체 가능)
└── Task 4: Reference 멜로디 추출 구현

Wave 3 (After Wave 2):
└── Task 5: 멜로디 비교 시스템 구축

Wave 4 (After Wave 3):
└── Task 6: 멜로디 85% 유사도 달성 (1차 목표)

Wave 5 (After Wave 4 - 멜로디 85% 달성 후):
└── Task 7: 전체 85% 유사도 달성 (2차 목표)

Wave 6 (After Wave 5 - 전체 85% 달성 후):
├── Task 8: E2E 테스트
└── Task 9: CI/CD 자동화

Critical Path: Task 1 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 3 | 2 |
| 2 | None | 4 | 1 |
| 3 | 1 | 4, 5 | None |
| 4 | 2, 3 | 5 | None |
| 5 | 3, 4 | 6 | None |
| 6 | 5 | 7 | None |
| 7 | 6 | 8, 9 | None |
| 8 | 7 | None | 9 |
| 9 | 7 | None | 8 |

---

## TODOs

- [x] 1. 노트 손실 측정 도구 구현

  **What to do**:
  - `backend/scripts/measure_note_loss.py` 신규 생성
  - MIDI → MusicXML → 재임포트 → 노트 수 비교
  - JSON 형식 출력: `{input_notes, output_notes, loss_rate}`
  - 8곡 테스트 데이터로 현재 손실률 측정

  **Must NOT do**:
  - 손실 수정 시도 (측정만)
  - reference.mxl 사용 (생성 파이프라인 측정용)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 단순 스크립트 작성, 기존 패턴 참고
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 3
  - **Blocked By**: None

  **References**:
  - `backend/core/midi_to_musicxml.py` - MusicXML 변환 로직
  - `backend/core/midi_parser.py` - MIDI 파싱 패턴
  - `backend/scripts/diagnose_alignment.py` - 진단 스크립트 패턴

  **Acceptance Criteria**:

  ```
  Scenario: 측정 도구 실행 성공
    Tool: Bash (python)
    Steps:
      1. cd backend && python scripts/measure_note_loss.py tests/golden/data/song_01/
      2. Assert: JSON 출력 포함 {"input_notes": N, "output_notes": M, "loss_rate": X}
      3. Assert: exit code 0
    Expected Result: 손실률 측정 완료
    Evidence: stdout JSON 캡처

  Scenario: 8곡 전체 측정
    Tool: Bash (python)
    Steps:
      1. for song in song_01..song_08: python scripts/measure_note_loss.py
      2. 각 곡 loss_rate 기록
    Expected Result: 8곡 모두 측정 완료
    Evidence: 측정 결과 JSON 저장
  ```

  **Commit**: YES
  - Message: `feat(scripts): add note loss measurement tool`
  - Files: `backend/scripts/measure_note_loss.py`

---

- [x] 2. Reference 구조 분석

  **What to do**:
  - 8곡 reference.mxl 파일 구조 분석
  - 파트(part) 수, 보이스(voice) 구조 확인
  - 멜로디가 어느 파트에 있는지 식별
  - 분석 결과 문서화 (`.sisyphus/notepads/reference-structure.md`)

  **분석 항목**:
  - 총 파트 수
  - 각 파트 음역대 (pitch range)
  - 각 파트 노트 밀도 (notes per measure)
  - 멜로디 파트 식별 기준: 최고 음역, 단선율

  **Must NOT do**:
  - reference.mxl 수정
  - 자동 추출 구현 (분석만)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: 분석 및 문서화 작업
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 4
  - **Blocked By**: None

  **References**:
  - `backend/tests/golden/data/song_*/reference.mxl` - 8곡 레퍼런스
  - `backend/core/musicxml_comparator.py` - MusicXML 파싱 패턴

  **Acceptance Criteria**:

  ```
  Scenario: Reference 구조 분석 완료
    Tool: Bash (python)
    Steps:
      1. cd backend && python -c "
         import music21
         for i in range(1, 9):
             score = music21.converter.parse(f'tests/golden/data/song_0{i}/reference.mxl')
             parts = score.parts
             print(f'song_0{i}: {len(parts)} parts')
             for p in parts:
                 notes = list(p.flatten().notes)
                 pitches = [n.pitch.midi for n in notes if hasattr(n, 'pitch')]
                 print(f'  - {p.partName}: {len(notes)} notes, pitch {min(pitches)}-{max(pitches)}')"
    Expected Result: 8곡 모두 파트 구조 출력
    Evidence: 분석 결과 .sisyphus/notepads에 저장
  ```

  **Commit**: NO (분석 결과 문서만)

---

- [x] 3. MusicXML Export 노트 손실 수정

  **What to do**:
  - `backend/core/midi_to_musicxml.py` 수정
  - "Cannot convert inexpressible durations" 에러 해결
  - 양자화 전략 개선 (16th → finer grid 또는 snap 전략)
  - 목표: 노트 손실률 < 20% (현재 85-95%)

  **수정 전략 (우선순위)**:
  1. music21 내에서 해결 시도:
     - 허용 가능한 duration만 사용 (1/16, 1/8, 1/4, 1/2, 1)
     - 복잡한 duration은 가장 가까운 허용 값으로 snap
     - 타이(tie)를 사용하여 복잡한 길이 표현
     - makeMeasures() 전에 duration 검증
  2. **music21로 해결 불가 시** (ALLOWED):
     - 다른 MusicXML 라이브러리 검토 (python-musicxml 등)
     - 직접 MusicXML 생성 로직 구현
     - 필요시 신규 ML 알고리즘 적용

  **Must NOT do**:
  - 노트 단순 삭제 (변환 실패 시)
  - 임계값 낮추기로 문제 회피

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: music21 내부 동작 이해 필요, 복잡한 디버깅
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (단독)
  - **Blocks**: Task 4, Task 5
  - **Blocked By**: Task 1

  **References**:
  - `backend/core/midi_to_musicxml.py:128-148` - 현재 양자화 로직
  - `backend/scripts/measure_note_loss.py` - 측정 도구 (Task 1)
  - music21 documentation: duration quantization

  **Acceptance Criteria**:

  ```
  Scenario: 노트 손실률 20% 이하
    Tool: Bash (python)
    Steps:
      1. cd backend && python scripts/measure_note_loss.py tests/golden/data/song_01/
      2. Assert: loss_rate < 0.20
      3. 8곡 모두 반복
    Expected Result: 모든 곡 손실률 < 20%
    Evidence: 측정 결과 JSON

  Scenario: "inexpressible duration" 경고 없음
    Tool: Bash (pytest)
    Steps:
      1. docker compose exec backend pytest tests/golden/ -m compare -v 2>&1 | grep -c "inexpressible"
      2. Assert: count == 0
    Expected Result: 경고 없음
    Evidence: pytest 출력 캡처
  ```

  **Commit**: YES
  - Message: `fix(musicxml): reduce note loss in MusicXML export to <20%`
  - Files: `backend/core/midi_to_musicxml.py`

---

- [x] 4. Reference 멜로디 추출 구현

  **What to do**:
  - `backend/core/musicxml_melody_extractor.py` 신규 생성
  - MusicXML/MXL 파일에서 멜로디 추출
  - 기존 `melody_extractor.py`의 skyline 알고리즘 재사용
  - Task 2 분석 결과 기반으로 파트 선택 로직 구현

  **구현 요구사항**:
  - 입력: MusicXML/MXL 파일 경로
  - 출력: `List[Note]` (melody_extractor와 동일 형식)
  - 알고리즘: skyline (onset별 최고 pitch)
  - 필터: MIN_DURATION=50ms, pitch range C3-C6

  **Must NOT do**:
  - 수동으로 멜로디 정의
  - skyline 외 다른 알고리즘 사용

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: music21 + 기존 패턴 통합
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after Task 2, 3)
  - **Blocks**: Task 5
  - **Blocked By**: Task 2, Task 3

  **References**:
  - `backend/core/melody_extractor.py` - skyline 알고리즘 (재사용)
  - `backend/core/musicxml_comparator.py` - MusicXML 파싱 패턴
  - `.sisyphus/notepads/reference-structure.md` - Task 2 분석 결과

  **Acceptance Criteria**:

  ```
  Scenario: Reference 멜로디 추출 성공
    Tool: Bash (python)
    Steps:
      1. cd backend && python -c "
         from core.musicxml_melody_extractor import extract_melody_from_musicxml
         melody = extract_melody_from_musicxml('tests/golden/data/song_01/reference.mxl')
         print(f'Extracted {len(melody)} melody notes')
         assert len(melody) > 100, 'Too few melody notes'
         assert len(melody) < 500, 'Too many notes (not melody)'
         print('PASS')"
    Expected Result: 멜로디 노트 추출 (100-500개 범위)
    Evidence: stdout 캡처

  Scenario: 멜로디 비율 검증 (전체의 10-30%)
    Tool: Bash (python)
    Steps:
      1. 전체 노트 수 대비 멜로디 노트 비율 확인
      2. Assert: 0.10 < melody_ratio < 0.30
    Expected Result: 멜로디가 전체의 10-30%
    Evidence: 비율 계산 결과
  ```

  **Commit**: YES
  - Message: `feat(core): add MusicXML melody extractor using skyline algorithm`
  - Files: `backend/core/musicxml_melody_extractor.py`

---

- [x] 5. 멜로디 비교 시스템 구축

  **What to do**:
  - `backend/tests/golden/test_golden.py` 수정
  - 멜로디 vs 멜로디 비교 테스트 추가 (`@pytest.mark.melody`)
  - Reference 멜로디 ↔ Generated 멜로디 비교
  - **목표 threshold: 85%** (비현실적 임계값 금지)

  **비교 로직**:
  1. Reference에서 멜로디 추출 (Task 4)
  2. Generated에서 멜로디 추출 (기존 melody_extractor)
  3. 동일한 matching 알고리즘 적용
  4. similarity = matched / max(ref_melody, gen_melody)

  **Must NOT do**:
  - 기존 compare 모드 삭제/수정 (신규 추가만)
  - ❌ **0.1% 같은 비현실적 임계값 사용 금지**
  - ❌ 결과 보고용으로 임계값 낮추기 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 기존 패턴 따라 테스트 추가
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (단독)
  - **Blocks**: Task 6, Task 7
  - **Blocked By**: Task 3, Task 4

  **References**:
  - `backend/tests/golden/test_golden.py:TestGoldenCompare` - 기존 비교 테스트
  - `backend/core/musicxml_melody_extractor.py` - Task 4 결과
  - `backend/core/musicxml_comparator.py` - matching 알고리즘

  **Acceptance Criteria**:

  ```
  Scenario: melody 마커 테스트 수집
    Tool: Bash (pytest)
    Steps:
      1. docker compose exec backend pytest tests/golden/ --collect-only -m melody
      2. Assert: "8 tests collected" 출력
    Expected Result: 8곡 멜로디 비교 테스트 수집
    Evidence: pytest 출력 캡처

  Scenario: 초기 멜로디 비교 실행
    Tool: Bash (pytest)
    Steps:
      1. docker compose exec backend pytest tests/golden/ -m melody -v --tb=short
      2. 각 곡별 similarity 확인
      3. Assert: exit code 0 (threshold 10%로 대부분 통과 예상)
    Expected Result: 8곡 멜로디 비교 완료
    Evidence: pytest 출력, similarity 값 기록
  ```

  **Commit**: YES
  - Message: `test(golden): add melody-vs-melody comparison tests`
  - Files: `backend/tests/golden/test_golden.py`

---

- [ ] 6. 멜로디 85% 유사도 달성 (1차 목표)

  **What to do**:
  - 점진적으로 멜로디 유사도 향상
  - 파이프라인 개선 (라이브러리 변경/ML 도입 가능)
  - 목표: **8곡 모두 85% 멜로디 유사도 달성**

  **개선 전략 (유연하게 적용)**:
  1. **tolerance 조정**:
     - onset tolerance: 0.1 → 0.15 → 0.2 quarterLength
     - duration tolerance: 20% → 25% → 30%
  2. **파이프라인 개선** (필요시):
     - 불필요한 단계 제거/수정
     - 양자화 전략 변경
  3. **라이브러리 변경** (music21 한계 시):
     - 다른 MusicXML 라이브러리 도입
     - 직접 구현
  4. **ML 접근** (근본적 한계 시):
     - 신규 ML 알고리즘 개발
     - 후처리 모델 도입

  **Must NOT do**:
  - ❌ **임계값 85% 미만으로 낮추기**
  - ❌ 다른 곡 회귀 > 2% 허용

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 반복적 실험, 깊은 분석, 다양한 접근 필요
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (단독)
  - **Blocks**: Task 7
  - **Blocked By**: Task 5

  **References**:
  - `backend/core/musicxml_comparator.py` - tolerance 설정
  - `backend/core/midi_to_musicxml.py` - 파이프라인
  - Task 5 테스트 결과

  **Acceptance Criteria**:

  ```
  Scenario: 8곡 모두 85% 멜로디 유사도 달성
    Tool: Bash (pytest)
    Steps:
      1. docker compose exec backend pytest tests/golden/ -m melody -v
      2. Assert: 8곡 모두 similarity >= 0.85
      3. Assert: 회귀 없음 (이전 대비 -2% 이하 감소 없음)
    Expected Result: 8곡 모두 85% 이상
    Evidence: pytest 출력, similarity 값 기록
  ```

  **Commit**: YES (각 개선마다)
  - Message: `feat(golden): improve melody similarity to X%`
  - Files: 변경된 파일들

---

- [ ] 7. 전체 85% 유사도 달성 (2차 목표)

  **What to do**:
  - 멜로디 85% 달성 후 전체 편곡 비교로 확장
  - Reference 전체 vs Generated 전체 비교
  - 목표: **8곡 모두 85% 전체 유사도 달성**

  **구현 요구사항**:
  - 기존 compare 테스트 threshold를 85%로 설정
  - 전체 노트 비교 (멜로디 + 반주)
  - 필요시 전체 편곡 생성 파이프라인 개선

  **개선 전략**:
  1. 멜로디 외 반주 노트 정확도 향상
  2. 파트 분리 및 정렬
  3. 필요시 Basic Pitch 파라미터 조정

  **Must NOT do**:
  - ❌ **임계값 85% 미만으로 낮추기**
  - ❌ 멜로디 85% 회귀 허용

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 복잡한 전체 편곡 비교
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (멜로디 85% 후)
  - **Blocks**: Task 8, Task 9
  - **Blocked By**: Task 6

  **References**:
  - `backend/core/musicxml_comparator.py` - 전체 비교 로직
  - `backend/tests/golden/test_golden.py:TestGoldenCompare` - 기존 compare 테스트
  - Task 6 결과

  **Acceptance Criteria**:

  ```
  Scenario: 8곡 모두 85% 전체 유사도 달성
    Tool: Bash (pytest)
    Steps:
      1. docker compose exec backend pytest tests/golden/ -m compare -v
      2. Assert: 8곡 모두 similarity >= 0.85
      3. Assert: 멜로디 테스트 여전히 85%+ (회귀 없음)
    Expected Result: 8곡 모두 전체 85% 이상
    Evidence: pytest 출력, similarity 값 기록
  ```

  **Commit**: YES
  - Message: `feat(golden): achieve 85% full similarity`
  - Files: 변경된 파일들

---

- [ ] 8. E2E 테스트 (Playwright)

  **What to do**:
  - 전체 85% 달성 후 E2E 테스트 실행
  - Playwright MCP 사용
  - 8곡 업로드 → 처리 → 다운로드 검증

  **E2E 시나리오**:
  1. http://localhost:3000 접속
  2. MP3 파일 업로드
  3. 처리 완료 대기 (progress 100%)
  4. 결과 페이지 확인
  5. MIDI/MusicXML 다운로드 검증
  6. 다운로드된 MusicXML과 reference 비교 (85%+ 확인)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Playwright 브라우저 자동화
  - **Skills**: [`playwright`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 6 (with Task 9)
  - **Blocks**: None
  - **Blocked By**: Task 7

  **References**:
  - `.sisyphus/evidence/golden-e2e/` - 기존 E2E 증거
  - Playwright MCP documentation

  **Acceptance Criteria**:

  ```
  Scenario: 8곡 E2E 테스트 성공
    Tool: Playwright MCP
    Steps:
      1. 각 곡(song_01~08)에 대해:
         - Navigate to http://localhost:3000
         - Upload input.mp3
         - Wait for 처리 완료 (timeout: 180s)
         - Assert: 결과 페이지 표시
         - Assert: Download 버튼 존재
         - Screenshot 캡처
    Expected Result: 8곡 모두 E2E 성공
    Evidence: .sisyphus/evidence/golden-e2e/song_*_result.png
  ```

  **Commit**: YES
  - Message: `test(e2e): complete Playwright golden tests for 8 songs`
  - Files: evidence 스크린샷

---

- [ ] 9. CI/CD 자동화 구현

  **What to do**:
  - E2E 완료 후 CI/CD 구축
  - `.github/workflows/golden-tests.yml` 신규 생성
  - push to main, PR to main 시 트리거

  **CI 구조**:
  ```yaml
  jobs:
    test:
      steps:
        - Build Docker image
        - Run unit tests
        - Run golden melody tests (85% threshold)
        - Run golden compare tests (85% threshold)
        - Upload results artifact (JSON)
  ```

  **Must NOT do**:
  - 복잡한 대시보드 구축
  - 히스토리 DB 구현

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 표준 GitHub Actions 패턴
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 6 (with Task 8)
  - **Blocks**: None
  - **Blocked By**: Task 7

  **References**:
  - `docker-compose.yml` - Docker 구성
  - GitHub Actions documentation

  **Acceptance Criteria**:

  ```
  Scenario: CI workflow 동작 확인
    Tool: Bash (gh)
    Steps:
      1. cat .github/workflows/golden-tests.yml
      2. Assert: pytest 명령어 포함 (85% threshold)
      3. gh workflow run golden-tests.yml
      4. gh run list --workflow=golden-tests.yml
      5. Assert: 최근 실행 성공
    Expected Result: CI 파이프라인 동작 확인
    Evidence: gh 출력 캡처
  ```

  **Commit**: YES
  - Message: `ci: add GitHub Actions workflow for golden tests (85% threshold)`
  - Files: `.github/workflows/golden-tests.yml`

---

## Commit Strategy

> **CRITICAL**: 모든 task 완료 시 즉시 커밋 + 리모트 푸쉬 (급작스러운 종료 대비)

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(scripts): add note loss measurement tool` | `scripts/measure_note_loss.py` | python 실행 |
| 2 | `docs: add reference structure analysis` | `.sisyphus/notepads/reference-structure.md` | 문서 확인 |
| 3 | `fix(musicxml): reduce note loss to <20%` | `midi_to_musicxml.py` 등 | measure_note_loss.py |
| 4 | `feat(core): add MusicXML melody extractor` | `musicxml_melody_extractor.py` | python import |
| 5 | `test(golden): add melody comparison tests` | `test_golden.py` | pytest --collect-only |
| 6 | `feat(golden): achieve 85% melody similarity` | 비교 설정 파일 | pytest -m melody |
| 7 | `feat(golden): achieve 85% full similarity` | 비교 설정 파일 | pytest -m compare |
| 8 | `test(e2e): complete Playwright golden tests` | evidence 스크린샷 | 스크린샷 확인 |
| 9 | `ci: add GitHub Actions workflow (85% threshold)` | `.github/workflows/*.yml` | gh workflow view |

---

## Success Criteria

### Verification Commands
```bash
# 1. 노트 손실 측정
docker compose exec backend python scripts/measure_note_loss.py tests/golden/data/song_01/
# Expected: {"loss_rate": 0.XX} where XX < 20

# 2. 멜로디 추출 확인
docker compose exec backend python -c "from core.musicxml_melody_extractor import extract_melody_from_musicxml; print('OK')"
# Expected: OK

# 3. 멜로디 85% 유사도 (1차 목표)
docker compose exec backend pytest tests/golden/ -m melody -v
# Expected: 8 passed, all similarity >= 0.85

# 4. 전체 85% 유사도 (2차 목표)
docker compose exec backend pytest tests/golden/ -m compare -v
# Expected: 8 passed, all similarity >= 0.85

# 5. E2E 증거 확인
ls .sisyphus/evidence/golden-e2e/
# Expected: song_01_result.png ~ song_08_result.png (8개)

# 6. CI 상태 확인
gh workflow view golden-tests.yml
# Expected: workflow exists and enabled
```

### Final Checklist
- [ ] 노트 손실률 < 20%
- [ ] Reference 멜로디 추출 동작
- [ ] **8곡 85% 멜로디 유사도 달성 (1차)**
- [ ] **8곡 85% 전체 유사도 달성 (2차)**
- [ ] E2E 테스트 8곡 성공
- [ ] CI/CD 파이프라인 동작 (85% threshold)
- [ ] 기존 smoke 테스트 정상 동작 유지
- [ ] 모든 task 커밋 + 리모트 푸쉬 완료

---

## 향후 계획: 추가 레퍼런스 검증

> **이 플랜의 모든 테스트(Task 1-9) 완료 후 진행**

### 추가 레퍼런스 제공 및 전체 테스트

**시점**: Task 9 (CI/CD) 완료 후

**절차**:
1. 사용자가 추가 레퍼런스 제공 (규모 미정)
2. `backend/tests/golden/data/`에 추가 레퍼런스 통합
3. 전체 테스트 재실행:
   - 기존 8곡 + 추가 레퍼런스 모두 멜로디 85% 검증
   - 기존 8곡 + 추가 레퍼런스 모두 전체 85% 검증
   - E2E 테스트 전체 실행
4. CI/CD 파이프라인에 추가 레퍼런스 반영

**성공 기준**:
- 기존 8곡 회귀 없음 (85% 유지)
- 추가 레퍼런스 모두 85% 달성 (멜로디 + 전체)

**Note**: 추가 레퍼런스 제공 시점은 미정. 이 플랜 완료 후 별도 계획으로 진행.
