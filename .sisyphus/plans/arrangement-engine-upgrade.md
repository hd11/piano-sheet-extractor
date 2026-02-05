# 피아노 편곡 엔진 전면 업그레이드 (v2)

## TL;DR

> **Quick Summary**: Music2MIDI 스파이크 검증 후 → 최적 모델(Music2MIDI or Pop2Piano) 통합 + 비교 알고리즘 전면 개편 + MIDI 레퍼런스 골든 테스트 통합 + MusicXML 폴리포닉 지원
>
> **핵심 전략 변경 (v2)**:
> - 전수 조사 결과 "피아노 편곡 생성" 모델이 전 세계에 5개 존재
> - **Music2MIDI** (MMM'25)가 Pop2Piano/PiCoGen 능가 + **난이도 컨디셔닝 내장**
> - Wave 0에서 Music2MIDI 스파이크 검증 → GO/NO-GO 판정
> - GO: Music2MIDI 주력 (난이도 시스템 근본 개선)
> - NO-GO: Pop2Piano 폴백 (기존 v1 플랜 경로)
>
> **Deliverables**:
> - 편곡 모델 통합 (`audio_to_midi.py` 교체 — Music2MIDI or Pop2Piano)
> - 비교 알고리즘 전면 교체 (`musicxml_comparator.py` → mir_eval + DTW + 다중 메트릭)
> - MIDI 레퍼런스 골든 테스트 데이터 통합 (원본/쉬운/다장조)
> - MusicXML 폴리포닉 지원 (`midi_to_musicxml.py` 양손 악보)
> - 난이도 시스템 (Music2MIDI: 네이티브 / Pop2Piano: 재설계)
> - 복합 테스트 체계 (MXL + MIDI 동시 비교)
> - 8곡 전체 유사도 측정 리포트
>
> **Estimated Effort**: Large (1-2주)
> **Parallel Execution**: YES - 4 waves (Wave 0 → 1 → 2 → 3)
> **Critical Path**: Task 0 → Task 2 → Task 5 → Task 6 → Task 8 → Task 9 → Task 10

---

## 핵심 정책 (CRITICAL - 모든 태스크에 적용)

### Git 커밋 정책 (MANDATORY)
```
모든 task 진행 시 변경사항 즉시 커밋 + 리모트 푸쉬
- 각 task 완료 시 반드시 커밋
- 커밋 메시지: conventional commits 형식
```

### 패러다임 이해 (MANDATORY - CRITICAL)
```
이 프로젝트는 "피아노 인식(Transcription)"이 아니라
"피아노 편곡 생성(Arrangement)"이다.

- ❌ "음원에서 피아노 소리만 추출" → 틀린 접근
- ✅ "전체 팝송을 피아노로 편곡" → 올바른 접근

편곡 생성 모델들:
- Music2MIDI: 최신 (MMM'25), Pop2Piano/PiCoGen 능가, 난이도+장르 컨디셔닝
- Pop2Piano: 최초 (2022), K-pop 특화, HuggingFace 통합
- ByteDance: ❌ "피아노 인식" 모델 — 사용 금지
```

### 비교 메트릭 정책 (MANDATORY)
```
단일 노트 매칭 유사도만으로 평가하지 않는다.
복합 메트릭(멜로디 + 코드 + 리듬 + 구조)으로 다각도 평가.

편곡은 "정답이 하나"가 아니므로:
- 같은 곡을 두 피아니스트가 편곡하면 노트 단위 50-70% 다를 수 있음
- 하지만 둘 다 "좋은 편곡"일 수 있음
- 따라서 코드 진행, 멜로디 컨투어, 구조적 유사도 등 복합 평가 필수
```

### 롤백 정책 (MANDATORY)
```
새 모델 통합 실패 시:
- 원본 audio_to_midi.py 백업에서 즉시 복원
- 롤백 기준: 새 모델이 MIDI 생성 자체를 실패하거나
  기존 대비 모든 메트릭에서 악화 시
```

---

## Context

### Original Request
- 팝송 오디오 → 피아노 편곡 악보 자동 생성 시스템 전면 업그레이드
- 공격적 접근: 모든 가능한 방법 시도
- MIDI 레퍼런스(원본/쉬운/다장조)도 골든 테스트에 포함

### 문제 진단
- 현재 ByteDance Piano Transcription은 "피아노 인식" 모델 → 팝 믹스에서 모든 소리를 피아노 노트로 변환 → 노이즈
- 편곡 생성 모델로 교체 필요 → 정확히 이 프로젝트의 목적에 맞음
- 비교 알고리즘(greedy matching)이 정확도를 실제보다 5-15% 낮게 보고

### 전수 조사 결과 (2026-02-05)

**"피아노 편곡 생성" 모델 — 전 세계 5개 발견:**

| # | 모델 | 발표 | 코드 | 품질 | 핵심 |
|---|------|------|------|------|------|
| 1 | **Etude** | Sep 2025 | ❌ 미공개 | 🥇 사람 수준 | 3-stage, beat-aware |
| 2 | **Music2MIDI** | Dec 2024 | ✅ MIT | 🥈 Pop2Piano 능가 | **난이도+장르 컨디셔닝** |
| 3 | **PiCoGen2** | Aug 2024 | ✅ MIT | 🥉 우수 | VRAM >16GB 필요 ❌ |
| 4 | **Pop2Piano** | Nov 2022 | ✅ HF 통합 | 4위 | K-pop 특화, 21 스타일 |
| 5 | **audio2midi** | NYU 연구 | ✅ | 미평가 | Style transfer |

**상용 서비스 중 "편곡 생성"을 하는 곳: 0개** (전부 "인식" or "코드 감지")

**Oracle 전략 분석 결론: Music2MIDI 주력 + Pop2Piano 폴백**

- Music2MIDI의 킬러 피처: **난이도 컨디셔닝 내장** (beginner/intermediate/advanced)
  - 현재: 풀 MIDI → 휴리스틱 노트 스트리핑 (기계적)
  - Music2MIDI: 난이도별 독립 생성 (음악적으로 지능적인 간소화)
- PiCoGen2: VRAM >16GB → 소비자 GPU에서 사용 불가 → 탈락
- Etude: 코드 미공개 → 사용 불가 → 탈락

### 현재 상태
- **현재 모델**: ByteDance Piano Transcription (piano_transcription_inference)
- **현재 유사도**: 평균 ~20% (melody similarity)
- **현재 비교**: greedy O(n×m) matching, ONSET_TOLERANCE=3.0s
- **테스트 데이터**: 8곡 MP3 + MXL + MIDI(원본/쉬운/다장조)

### 기술 세부사항 (조사 결과)

**Music2MIDI**:
- GitHub: https://github.com/ytinyui/music2midi (14★, MIT, MMM 2025)
- 모델: T5-small 기반 ~30M params → **2-4GB VRAM**
- 출력: `pretty_midi` 객체 (현재 파이프라인과 동일)
- 컨디셔닝: `cond_index=[genre_idx, difficulty_idx]` (pop=1, beginner=0/intermediate=1/advanced=2)
- 데이터셋: 3000 쌍, 180시간
- ⚠️ 리스크: CUDA 12.1로 개발됨 (우리는 11.8), 스타 14개

**Pop2Piano (폴백)**:
- HuggingFace: `transformers` 공식 통합
- 샘플레이트: **44100Hz** (현재 16kHz에서 변경 필요)
- composer_vocab_size = 21 (21개 스타일)
- 출력: `pretty_midi` 객체
- K-pop 특화 학습

**mir_eval**:
- pitches: **Hz 단위** (MIDI 번호 아님! → `mir_eval.util.midi_to_hz()` 변환 필요)
- `mir_eval.transcription.precision_recall_f1_overlap()` — 폴리포닉 지원
- 기본 tolerance: onset 50ms, pitch 50 cents

---

## Work Objectives

### Core Objective
최적의 편곡 모델(Music2MIDI or Pop2Piano)을 핵심 엔진으로 교체하고, MIDI 레퍼런스를 포함한 복합 테스트 체계를 구축하여 피아노 편곡 품질을 최대한 끌어올린다.

### Concrete Deliverables
- `backend/core/audio_to_midi.py` — 편곡 모델 기반으로 완전 교체
- `backend/core/musicxml_comparator.py` — mir_eval + DTW + 다중 메트릭
- `backend/core/midi_comparator.py` — MIDI 직접 비교 모듈 (신규)
- `backend/core/midi_to_musicxml.py` — 폴리포닉 양손 악보 지원
- `backend/core/difficulty_adjuster.py` — 모델에 맞는 난이도 시스템
- `backend/tests/golden/data/song_XX/` — MIDI 레퍼런스 추가
- `backend/tests/golden/test_golden.py` — MIDI 비교 테스트 추가

### Definition of Done
- [ ] 편곡 모델이 8곡 모두 MIDI 생성 성공
- [ ] 복합 메트릭으로 8곡 유사도 측정 완료
- [ ] MIDI 레퍼런스(원본/쉬운/다장조) 골든 테스트에 통합
- [ ] 양손 피아노 MusicXML 악보 생성 성공
- [ ] 난이도별(easy/medium/hard) 출력이 레퍼런스 변형과 비교 가능

### Must Have
- 함수 시그니처 유지 (`convert_audio_to_midi(audio_path, output_path)`)
- 기존 API 호환성 유지 (FastAPI 엔드포인트 변경 없음)
- 8곡 전부 MIDI 생성 가능
- MIDI 레퍼런스 골든 테스트 통합

### Must NOT Have (Guardrails)
- ❌ 소스 분리(Demucs)로 피아노만 추출하는 접근 금지 — 편곡 목적에 반함
- ❌ 기존 레퍼런스 MXL/MIDI 파일 수정 금지
- ❌ Frontend UI 변경 (별도 작업)
- ❌ 모델 fine-tuning 금지 (8곡 = 과적합 확실)
- ❌ ByteDance 코드 삭제 금지 — .bak으로 백업 유지

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: 기존 golden test 확장
- **Framework**: pytest

### Agent-Executed QA Scenarios

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **모델 MIDI 생성** | Bash | Python import + 단일 곡 MIDI 생성 |
| **MIDI 비교** | Bash | pytest 실행 + 유사도 수치 수집 |
| **MusicXML 생성** | Bash | 파일 존재 + music21 파싱 성공 |
| **골든 테스트** | Bash | `pytest -m golden` 실행 |

---

## Execution Strategy

### 조건부 실행 흐름 (CRITICAL)

```
Wave 0 (Gate):
└── Task 0: Music2MIDI 스파이크 검증 → GO / NO-GO 판정

    ┌─── GO (Music2MIDI 성공) ──────────────────────────────┐
    │                                                        │
    │  Wave 1 (Parallel):                                    │
    │  ├── Task 1: MIDI 레퍼런스 골든 테스트 통합             │
    │  └── Task 2-A: Music2MIDI 통합                         │
    │                                                        │
    │  Wave 2 (Parallel):                                    │
    │  ├── Task 4: 비교 알고리즘 전면 교체                    │
    │  ├── Task 5: MusicXML 폴리포닉 지원                    │
    │  └── Task 6-A: 난이도 — Music2MIDI 네이티브 활용        │
    │                                                        │
    └─── NO-GO (Music2MIDI 실패) ──────────────────────────┐
    │                                                        │
    │  Wave 1 (Parallel):                                    │
    │  ├── Task 1: MIDI 레퍼런스 골든 테스트 통합             │
    │  ├── Task 2-B: Pop2Piano 통합 (HuggingFace)            │
    │  └── Task 3: Pop2Piano composer 스타일 탐색             │
    │                                                        │
    │  Wave 2 (Parallel):                                    │
    │  ├── Task 4: 비교 알고리즘 전면 교체                    │
    │  ├── Task 5: MusicXML 폴리포닉 지원                    │
    │  └── Task 6-B: 난이도 — 휴리스틱 재설계                 │
    │                                                        │
    └────────────────────────────────────────────────────────┘

    (공통) Wave 3:
    ├── Task 7: MIDI 직접 비교 모듈 구현
    ├── Task 8: 복합 골든 테스트 구현
    └── Task 9: 8곡 전체 유사도 측정 + 리포트

    Wave 4:
    └── Task 10: 결과 평가 및 다음 단계 결정
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 0 | None | ALL | None (gate) |
| 1 | 0 (판정만) | 7, 8 | 2, 3 |
| 2 | 0 | 3(NO-GO만), 5, 6, 9 | 1 |
| 3 | 2 (NO-GO만) | 9 | 1 (NO-GO만) |
| 4 | 0 (판정만) | 7, 8, 9 | 5, 6 |
| 5 | 2 | 8, 9 | 4, 6 |
| 6 | 2 | 8, 9 | 4, 5 |
| 7 | 1, 4 | 8 | - |
| 8 | 1, 4, 5, 6, 7 | 9 | - |
| 9 | 2, 8 (+3 if NO-GO) | 10 | - |
| 10 | 9 | None | - |

---

## TODOs

- [ ] 0. Music2MIDI 스파이크 검증 (GO/NO-GO Gate)

  **What to do**:
  - Music2MIDI 체크포인트 다운로드 (GitHub Release tag `0.1.0`)
  - 의존성 설치: `music2midi` 패키지 + `omegaconf`, `pytorch-lightning`, `more-itertools`
  - CUDA 11.8 / torch 2.0.1 호환성 확인 (비호환 시 `torch==2.1.0+cu118` 시도)
  - song_01(Golden)에 대해 MIDI 생성 테스트
  - 생성된 MIDI를 reference.mid와 간단 비교 (노트 수, 피치 범위, 길이)
  - 난이도 컨디셔닝 테스트: beginner/intermediate/advanced 각각 생성
  - **GO/NO-GO 판정 기준** 결정

  **GO 기준 (ALL must pass)**:
  1. import 성공 + 모델 로딩 성공
  2. song_01에서 MIDI 생성 성공 (note_count > 0)
  3. 난이도별 노트 수 차이 확인 (beginner < intermediate < advanced)
  4. 생성 시간 5분 이내 (1곡 기준)

  **NO-GO 시**:
  - CUDA/torch 호환 불가 AND 우회 불가
  - 모델 로딩 실패 (체크포인트 손상 등)
  - MIDI 생성 실패 (빈 파일, 에러)
  → **Pop2Piano 경로로 진행** (Task 2-B, 3, 6-B)

  **Must NOT do**:
  - 8곡 전체 테스트 금지 (1곡만으로 판정)
  - 비교 알고리즘 구현 금지 (단순 노트 수/피치 범위만 비교)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: 새 라이브러리 설치 + 호환성 디버깅 + 판정 로직

  **Parallelization**:
  - **Can Run In Parallel**: NO (Gate task — 이후 모든 태스크의 전제)
  - **Blocks**: ALL subsequent tasks
  - **Blocked By**: None

  **References**:
  - Music2MIDI GitHub: https://github.com/ytinyui/music2midi
  - Music2MIDI 논문: https://link.springer.com/chapter/10.1007/978-981-96-2064-7_8
  - `backend/core/audio_to_midi.py` — 현재 구현 (시그니처 참고)
  - `backend/requirements.txt` — 현재 의존성 (torch==2.0.1)
  - `backend/Dockerfile` — CUDA 11.8, Python 3.11
  - `backend/tests/golden/data/song_01/input.mp3` — 테스트 입력

  **Acceptance Criteria**:

  ```
  Scenario: Music2MIDI 설치 + import
    Tool: Bash
    Steps:
      1. pip install 또는 git clone + setup
      2. docker compose run --rm backend python -c "
         from music2midi import Music2MIDI  # 또는 해당 import 경로
         print('Import OK')
         "
      3. Assert: "Import OK" 출력 또는 호환 가능한 import 경로 확인
    Expected Result: 라이브러리 정상 import
    Evidence: stdout

  Scenario: 단일 곡 MIDI 생성
    Tool: Bash
    Steps:
      1. 모델 로딩 + song_01 MIDI 생성
      2. pretty_midi로 결과 파싱
      3. Assert: note_count > 0, duration > 30s
    Expected Result: MIDI 파일 정상 생성
    Evidence: stdout (노트 수, 길이, 처리 시간)

  Scenario: 난이도 컨디셔닝 테스트
    Tool: Bash
    Steps:
      1. beginner, intermediate, advanced 각각 생성
      2. 각 결과의 노트 수 비교
      3. Assert: beginner_notes < intermediate_notes < advanced_notes
    Expected Result: 난이도별 노트 수 차이 확인
    Evidence: 3개 MIDI 파일 + 노트 수 비교

  Scenario: GO/NO-GO 판정
    Tool: Bash
    Steps:
      1. 위 3개 시나리오 결과 종합
      2. GO 기준 4개 항목 체크
      3. 판정 결과를 .sisyphus/notepads/music2midi-spike.md에 기록
    Expected Result: 명확한 GO 또는 NO-GO 판정
    Evidence: .sisyphus/notepads/music2midi-spike.md
  ```

  **Commit**: YES
  - Message: `spike(core): validate Music2MIDI compatibility and quality (GO/NO-GO)`
  - Files: `.sisyphus/notepads/music2midi-spike.md`, (설치 관련 파일)

---

- [ ] 1. MIDI 레퍼런스 골든 테스트 데이터 통합

  **What to do**:
  - `test/` 폴더의 MIDI 파일들을 `backend/tests/golden/data/song_XX/`로 복사
  - 파일명 규칙: `reference.mid`, `reference_easy.mid`, `reference_cmajor.mid`
  - `metadata.json` 업데이트: MIDI 변형 정보 추가
  - MIDI 파일 구조 분석 (트랙 수, 채널, 노트 수, 키/BPM 등)

  **파일 매핑**:
  ```
  test/Golden.mid → backend/tests/golden/data/song_01/reference.mid
  test/Golden 쉬운.mid → backend/tests/golden/data/song_01/reference_easy.mid
  test/IRIS OUT.mid → backend/tests/golden/data/song_02/reference.mid
  test/IRIS OUT 쉬운.mid → backend/tests/golden/data/song_02/reference_easy.mid
  test/꿈의 버스.mid → backend/tests/golden/data/song_03/reference.mid
  test/꿈의 버스 쉬운.mid → backend/tests/golden/data/song_03/reference_easy.mid
  test/꿈의 버스 다장조.mid → backend/tests/golden/data/song_03/reference_cmajor.mid
  test/너에게100퍼센트.mid → backend/tests/golden/data/song_04/reference.mid
  test/너에게100퍼센트 쉬운.mid → backend/tests/golden/data/song_04/reference_easy.mid
  test/너에게100퍼센트 다장조.mid → backend/tests/golden/data/song_04/reference_cmajor.mid
  test/달리 표현할 수 없어요.mid → backend/tests/golden/data/song_05/reference.mid
  test/달리 표현할 수 없어요 쉬운.mid → backend/tests/golden/data/song_05/reference_easy.mid
  test/달리 표현할 수 없어요 다장조.mid → backend/tests/golden/data/song_05/reference_cmajor.mid
  test/등불을 지키다.mid → backend/tests/golden/data/song_06/reference.mid
  test/등불을 지키다 쉬운.mid → backend/tests/golden/data/song_06/reference_easy.mid
  test/등불을 지키다 다장조.mid → backend/tests/golden/data/song_06/reference_cmajor.mid
  test/비비드라라러브.mid → backend/tests/golden/data/song_07/reference.mid
  test/비비드라라러브 쉬운.mid → backend/tests/golden/data/song_07/reference_easy.mid
  test/여름이었다.mid → backend/tests/golden/data/song_08/reference.mid
  test/여름이었다 쉬운.mid → backend/tests/golden/data/song_08/reference_easy.mid
  test/여름이었다 다장조.mid → backend/tests/golden/data/song_08/reference_cmajor.mid
  ```

  **Must NOT do**:
  - 원본 MIDI/MXL 파일 수정 금지
  - test/ 폴더의 원본 파일 삭제 금지 (복사만)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 파일 복사 + 간단한 분석 스크립트

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Task 0 (판정 결과만 필요, 어떤 경로든 실행)

  **References**:
  - `test/` 폴더 전체 파일 목록
  - `backend/tests/golden/data/song_01/metadata.json` — 기존 메타데이터 형식
  - `backend/tests/golden/conftest.py` — 골든 테스트 fixture

  **Acceptance Criteria**:

  ```
  Scenario: MIDI 레퍼런스 파일 복사 확인
    Tool: Bash
    Steps:
      1. ls backend/tests/golden/data/song_01/reference.mid
      2. ls backend/tests/golden/data/song_01/reference_easy.mid
      3. ls backend/tests/golden/data/song_03/reference_cmajor.mid
      4. 모든 8곡에 reference.mid, reference_easy.mid 존재 확인
      5. 다장조 파일 존재 확인 (해당 곡만)
    Expected Result: MIDI 파일 정상 복사
    Evidence: ls 출력

  Scenario: MIDI 파일 구조 분석
    Tool: Bash
    Steps:
      1. python -c "
         import pretty_midi
         pm = pretty_midi.PrettyMIDI('backend/tests/golden/data/song_01/reference.mid')
         print(f'Tracks: {len(pm.instruments)}, Notes: {sum(len(i.notes) for i in pm.instruments)}')
         "
      2. Assert: 트랙 수 >= 1, 노트 수 > 0
    Expected Result: 모든 MIDI 파일 정상 파싱
    Evidence: 분석 리포트 출력

  Scenario: metadata.json 업데이트 확인
    Tool: Bash
    Steps:
      1. python -c "import json; d=json.load(open('backend/tests/golden/data/song_03/metadata.json')); assert 'midi_variants' in d"
    Expected Result: 메타데이터에 MIDI 변형 정보 포함
    Evidence: JSON 출력
  ```

  **Commit**: YES
  - Message: `test(golden): add MIDI reference files (original, easy, cmajor variants)`
  - Files: `backend/tests/golden/data/song_*/reference*.mid`, `backend/tests/golden/data/song_*/metadata.json`

---

- [ ] 2. 편곡 모델 통합 (audio_to_midi.py 교체)

  > **⚠️ 조건부 태스크**: Task 0 결과에 따라 경로 A 또는 B 실행

  ### 경로 A: Music2MIDI 통합 (Task 0 = GO)

  **What to do**:
  - `backend/requirements.txt`에 Music2MIDI 의존성 추가
  - 원본 `audio_to_midi.py` 백업 (`audio_to_midi_bytedance.py.bak`)
  - Music2MIDI 모델로 완전 교체
  - 함수 시그니처 및 반환 형식 유지
  - GPU/CPU 자동 선택 로직 + 모델 캐시 (singleton)
  - **difficulty 파라미터 추가** (내부용, 외부 시그니처 유지)

  **구현 요구사항 (Music2MIDI)**:
  ```python
  # 유지해야 할 함수 시그니처
  def convert_audio_to_midi(audio_path: Path, output_path: Path) -> Dict[str, Any]:
      """Returns: {"midi_path": str, "note_count": int, "duration_seconds": float, "processing_time": float}"""

  # 새로 추가: 난이도별 생성 함수
  def convert_audio_to_midi_with_difficulty(
      audio_path: Path, output_path: Path, difficulty: str = "advanced"
  ) -> Dict[str, Any]:
      """difficulty: "beginner" | "intermediate" | "advanced" """

  # Music2MIDI 사용 패턴 (Task 0 스파이크에서 확인된 방식 따름)
  model = Music2MIDI.load_from_checkpoint(CKPT, config_path="config.yaml")
  model.to(device).eval()
  # cond_index=[genre_idx, difficulty_idx] → pop=1, beginner=0/intermediate=1/advanced=2
  midi_data = model.generate(audio_path, cond_index=[1, difficulty_idx])
  midi_data.write(str(output_path))
  ```

  ### 경로 B: Pop2Piano 통합 (Task 0 = NO-GO)

  **What to do**:
  - `backend/requirements.txt`에 `transformers` 추가
  - 원본 `audio_to_midi.py` 백업 (`audio_to_midi_bytedance.py.bak`)
  - Pop2Piano HuggingFace 모델로 완전 교체
  - 함수 시그니처 및 반환 형식 유지
  - **샘플레이트 44100Hz** (현재 16kHz에서 변경)

  **구현 요구사항 (Pop2Piano)**:
  ```python
  from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor

  model = Pop2PianoForConditionalGeneration.from_pretrained("sweetcocoa/pop2piano")
  processor = Pop2PianoProcessor.from_pretrained("sweetcocoa/pop2piano")

  inputs = processor(audio=audio_array, sampling_rate=44100, return_tensors="pt")
  outputs = model.generate(input_features=inputs["input_features"], composer="composer1")
  midi_output = processor.batch_decode(token_ids=outputs, feature_extractor_output=inputs)
  midi_output["pretty_midi_objects"][0].write(str(output_path))
  ```

  ### 공통 Must NOT do
  - 함수 시그니처 변경 금지 (`convert_audio_to_midi(audio_path, output_path)`)
  - 반환 dict 키 변경 금지
  - ByteDance 코드 삭제 금지 (.bak으로 보관)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 1)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 3(NO-GO만), 5, 6, 9
  - **Blocked By**: Task 0

  **References**:
  - `backend/core/audio_to_midi.py` — 현재 ByteDance 구현 (시그니처, singleton 패턴)
  - Task 0 결과: `.sisyphus/notepads/music2midi-spike.md`
  - Music2MIDI GitHub: https://github.com/ytinyui/music2midi
  - Pop2Piano HuggingFace: https://huggingface.co/docs/transformers/en/model_doc/pop2piano
  - `backend/requirements.txt` — 현재 의존성

  **Acceptance Criteria**:

  ```
  Scenario: 모델 import 성공
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "[모델별 import 코드]"
      2. Assert: "Import OK"
    Expected Result: 정상 import

  Scenario: 단일 곡 MIDI 생성
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from pathlib import Path
         from core.audio_to_midi import convert_audio_to_midi
         result = convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test_model.mid')
         )
         assert result['note_count'] > 0
         print(f'Notes: {result[\"note_count\"]}, Time: {result[\"processing_time\"]:.1f}s')
         "
      2. Assert: exit code 0, note_count > 0
    Expected Result: MIDI 생성 성공

  Scenario: 함수 시그니처 유지 확인
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         import inspect
         from core.audio_to_midi import convert_audio_to_midi
         sig = inspect.signature(convert_audio_to_midi)
         params = list(sig.parameters.keys())
         assert params == ['audio_path', 'output_path'], f'Unexpected: {params}'
         print('Signature OK')
         "
      2. Assert: "Signature OK"

  Scenario: 원본 백업 확인
    Tool: Bash
    Steps:
      1. ls backend/core/audio_to_midi_bytedance.py.bak
      2. Assert: 파일 존재
  ```

  **Commit**: YES
  - Message (GO): `feat(core): replace ByteDance with Music2MIDI for piano arrangement generation`
  - Message (NO-GO): `feat(core): replace ByteDance with Pop2Piano for piano arrangement generation`
  - Files: `backend/core/audio_to_midi.py`, `backend/core/audio_to_midi_bytedance.py.bak`, `backend/requirements.txt`

---

- [ ] 3. Pop2Piano composer 스타일 탐색 (NO-GO 경로만)

  > **⚠️ Task 0 = NO-GO일 때만 실행. GO일 때는 SKIP.**
  > Music2MIDI는 composer 스타일 대신 genre/difficulty 컨디셔닝을 사용하므로 이 태스크 불필요.

  **What to do**:
  - Pop2Piano의 21개 composer 스타일을 1곡(song_01)에 대해 전부 생성
  - 각 스타일의 MIDI를 reference.mid와 비교
  - 레퍼런스 편곡 스타일에 가장 가까운 composer 식별
  - 최적 composer를 기본값으로 설정

  **Must NOT do**:
  - 8곡 전체를 모든 스타일로 생성 금지 — 1-2곡만
  - 스타일 선택을 하드코딩 금지 — 설정 파일이나 파라미터로

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Task 2-B

  **References**:
  - `backend/core/audio_to_midi.py` — Pop2Piano 통합 코드 (Task 2-B 결과)
  - `backend/tests/golden/data/song_01/reference.mid` — 비교 대상
  - Pop2Piano: `composer_vocab_size = 21` (composer1 ~ composer21)

  **Acceptance Criteria**:

  ```
  Scenario: 21개 스타일 MIDI 생성
    Tool: Bash
    Steps:
      1. 21개 composer 스타일로 song_01의 MIDI 각각 생성
      2. 각 MIDI의 노트 수, 피치 범위, 길이 비교
    Expected Result: 모든 스타일의 MIDI 파일 생성
    Evidence: 스타일별 비교 테이블

  Scenario: 최적 스타일 식별
    Tool: Bash
    Steps:
      1. 각 스타일 MIDI를 reference.mid와 비교 (노트 매칭)
      2. 상위 3개 composer와 유사도 리포트
    Expected Result: 최적 composer 식별
    Evidence: .sisyphus/notepads/pop2piano-style-comparison.md
  ```

  **Commit**: YES
  - Message: `feat(core): optimize Pop2Piano composer style selection`

---

- [ ] 4. 비교 알고리즘 전면 교체 (mir_eval + DTW + 다중 메트릭)

  **What to do**:
  - `backend/requirements.txt`에 `mir_eval`, `dtw-python` 추가
  - `backend/core/musicxml_comparator.py`를 전면 개편:
    * mir_eval 표준 메트릭 (precision, recall, F1)
    * DTW 기반 시간 정렬
    * Pitch class (옥타브 무시) 비교
    * Chroma 유사도
    * 코드 진행 비교
  - 복합 메트릭 점수 체계 도입
  - 기존 `compare_musicxml()` API 유지 + 새 API 추가
  - **⚠️ mir_eval pitches는 Hz 단위** — MIDI pitch → Hz 변환 필수 (`mir_eval.util.midi_to_hz()`)

  **복합 메트릭 설계**:
  ```python
  {
      "melody_f1": float,          # mir_eval onset+pitch F1 (tolerance: 50ms, 50cents)
      "melody_f1_lenient": float,  # 넓은 tolerance (200ms)
      "pitch_class_f1": float,     # 옥타브 무시 F1
      "chroma_similarity": float,  # chroma 프로필 상관
      "onset_f1": float,           # onset만 비교 (pitch 무시)
      "structural_similarity": {
          "measure_count_match": bool,
          "key_match": bool,
          "time_sig_match": bool,
      },
      "composite_score": float,    # 가중 평균 종합 점수
  }
  ```

  **Must NOT do**:
  - 기존 `compare_musicxml()` 함수 삭제 금지 — 호환성 유지
  - mir_eval import 실패 시 graceful fallback 필수

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Tasks 7, 8, 9
  - **Blocked By**: Task 0 (판정만, 독립 개발 가능)

  **References**:
  - `backend/core/musicxml_comparator.py` — 현재 비교 로직 (561줄, greedy matching)
  - `backend/core/midi_parser.py` — Note 데이터 구조 (pitch: int = MIDI number)
  - mir_eval 문서: `mir_eval.transcription.precision_recall_f1_overlap()`
  - mir_eval 입력: intervals `[[onset, offset], ...]` + pitches `[Hz, ...]`

  **Acceptance Criteria**:

  ```
  Scenario: mir_eval import + Hz 변환
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         import mir_eval
         hz = mir_eval.util.midi_to_hz(60)
         assert abs(hz - 261.63) < 1.0
         print(f'C4 = {hz:.2f} Hz — OK')
         "
    Expected Result: mir_eval 정상, MIDI→Hz 변환 정상

  Scenario: 기존 API 호환
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from core.musicxml_comparator import compare_musicxml
         result = compare_musicxml(
             'tests/golden/data/song_01/reference.mxl',
             'tests/golden/data/song_01/reference.mxl'
         )
         assert result['similarity'] > 0.99
         print(f'Self-similarity: {result[\"similarity\"]:.2%}')
         "
    Expected Result: 기존 API 정상 동작

  Scenario: 복합 메트릭 출력 확인
    Tool: Bash
    Steps:
      1. 새 compare 함수로 song_01 reference.mxl 자기비교
      2. Assert: melody_f1, pitch_class_f1, chroma_similarity, composite_score 키 존재
    Expected Result: 복합 메트릭 모두 출력
  ```

  **Commit**: YES
  - Message: `feat(core): replace comparison algorithm with mir_eval + DTW + composite metrics`
  - Files: `backend/core/musicxml_comparator.py`, `backend/requirements.txt`

---

- [ ] 5. MusicXML 폴리포닉 양손 악보 지원

  **What to do**:
  - `backend/core/midi_to_musicxml.py` 수정:
    * 편곡 모델 출력 MIDI (폴리포닉) → 양손 피아노 악보
    * 높은음자리표 (RH: MIDI >= 60) + 낮은음자리표 (LH: MIDI < 60)
    * 2스태프 피아노 파트로 구성
  - 기존 모노포닉 모드도 유지 (fallback)

  **Must NOT do**:
  - 기존 단일 스태프 모드 제거 금지
  - RH/LH 분할 기준을 하드코딩하지 말 것 — 설정 가능하게

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Task 2

  **References**:
  - `backend/core/midi_to_musicxml.py` — 현재 모노포닉 구현 (270줄)
  - `backend/tests/golden/data/song_01/reference.mxl` — 레퍼런스 구조 (2스태프)
  - music21 문서: Part, Staff, Clef

  **Acceptance Criteria**:

  ```
  Scenario: 양손 악보 생성
    Tool: Bash
    Steps:
      1. 편곡 모델로 song_01 MIDI 생성
      2. midi_to_musicxml로 MusicXML 변환
      3. music21으로 파싱하여 Part 수 확인
      4. Assert: 2개 Staff (높은음/낮은음 자리표)
    Expected Result: 양손 피아노 악보
    Evidence: Part/Staff 구조 출력
  ```

  **Commit**: YES
  - Message: `feat(core): add polyphonic two-hand piano score support in MusicXML`
  - Files: `backend/core/midi_to_musicxml.py`

---

- [ ] 6. 난이도 시스템

  > **⚠️ 조건부 태스크**: Task 0 결과에 따라 경로 A 또는 B 실행

  ### 경로 A: Music2MIDI 네이티브 난이도 활용 (Task 0 = GO)

  **What to do**:
  - `backend/core/difficulty_adjuster.py`를 **경량 후처리**로 축소:
    * Music2MIDI가 난이도별 MIDI를 직접 생성 (beginner/intermediate/advanced)
    * `difficulty_adjuster.py`는 옥타브 정규화, 코드 심볼 삽입 등 후처리만
    * `melody_extractor.py`의 skyline 알고리즘은 **불필요** (모델이 처리)
  - `generate_all_sheets()` 수정:
    * 기존: 1회 MIDI 생성 → 3회 후처리
    * 변경: **3회 MIDI 생성** (각 난이도별) → 경량 후처리

  **구현 요구사항**:
  ```python
  def generate_all_sheets(job_dir: Path, audio_path: Path, analysis: Dict) -> Dict[str, Path]:
      """
      Music2MIDI: 난이도별 독립 MIDI 생성 → MusicXML 변환
      """
      sheets = {}
      for level, diff_name in [("beginner", "easy"), ("intermediate", "medium"), ("advanced", "hard")]:
          midi_result = convert_audio_to_midi_with_difficulty(audio_path, midi_path, difficulty=level)
          # 경량 후처리 (옥타브 정규화, 코드 심볼 등)
          musicxml = midi_to_musicxml(midi_path, ...)
          sheets[diff_name] = musicxml_path
      return sheets
  ```

  **이 경로의 핵심 이점**:
  - 모델이 음악적으로 지능적인 간소화를 수행
  - 기계적 노트 스트리핑 (피치 클램프, 동시음 제한) 대신 적절한 보이싱/리듬 간소화

  ### 경로 B: 휴리스틱 재설계 (Task 0 = NO-GO)

  **What to do**:
  - `backend/core/difficulty_adjuster.py` 수정:
    * **Easy**: 멜로디만 (RH skyline) — 레퍼런스의 "쉬운" MIDI와 비교 가능
    * **Medium**: 멜로디 + 간단한 코드 (RH + 간소화된 LH)
    * **Hard**: Pop2Piano 풀 편곡 그대로
  - Easy 추출 시 기존 `melody_extractor.py`의 skyline 알고리즘 활용

  ### 공통 Must NOT do
  - melody_extractor.py의 기존 로직 파괴 금지
  - 3단계 외 추가 난이도 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Task 2

  **References**:
  - `backend/core/difficulty_adjuster.py` — 현재 난이도 시스템 (265줄)
  - `backend/core/melody_extractor.py` — Skyline 알고리즘 (191줄)
  - `backend/tests/golden/data/song_01/reference_easy.mid` — Easy 레퍼런스

  **Acceptance Criteria**:

  ```
  Scenario: 3단계 난이도 생성
    Tool: Bash
    Steps:
      1. song_01에 대해 generate_all_sheets() 호출
      2. sheet_easy.musicxml, sheet_medium.musicxml, sheet_hard.musicxml 존재 확인
      3. Easy의 노트 수 < Medium < Hard 확인
    Expected Result: 3단계 파일 생성, 노트 수 단계적
    Evidence: 각 파일의 노트 수 출력

  Scenario (GO 경로): 난이도별 독립 MIDI 생성 확인
    Tool: Bash
    Steps:
      1. beginner/intermediate/advanced 각각 별도 MIDI 파일 확인
      2. 각 MIDI의 노트 패턴이 음악적으로 다른지 확인 (단순 노트 제거가 아님)
    Expected Result: 모델이 난이도별 다른 편곡을 생성
    Evidence: 노트 수 + 피치 범위 비교
  ```

  **Commit**: YES
  - Message (GO): `feat(core): integrate Music2MIDI native difficulty conditioning`
  - Message (NO-GO): `feat(core): redesign difficulty system for polyphonic piano arrangement`
  - Files: `backend/core/difficulty_adjuster.py`

---

- [ ] 7. MIDI 직접 비교 모듈 구현

  **What to do**:
  - `backend/core/midi_comparator.py` 신규 생성:
    * MIDI 파일 간 직접 비교 (MusicXML 변환 없이)
    * pretty_midi 기반 노트 추출
    * mir_eval 메트릭 적용 (**Hz 변환 필수**)
    * DTW 정렬 적용
    * 복합 메트릭 출력 (Task 4와 동일 구조)

  **Must NOT do**:
  - MusicXML comparator와 코드 중복 최소화 — 공통 로직 분리

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 1, 4

  **References**:
  - `backend/core/musicxml_comparator.py` — 비교 로직 패턴 (Task 4 결과)
  - `backend/core/midi_parser.py` — Note dataclass (pitch: int MIDI number)
  - `backend/tests/golden/data/song_01/reference.mid` — MIDI 레퍼런스

  **Acceptance Criteria**:

  ```
  Scenario: MIDI 자기비교
    Tool: Bash
    Steps:
      1. reference.mid를 자기 자신과 비교
      2. Assert: composite_score > 0.99

  Scenario: 원본 vs 쉬운 비교
    Tool: Bash
    Steps:
      1. reference.mid vs reference_easy.mid 비교
      2. Assert: composite_score < 1.0
      3. Assert: melody_f1 > 0.3 (멜로디는 유사)
    Expected Result: 의미 있는 차이 측정
  ```

  **Commit**: YES
  - Message: `feat(core): add MIDI direct comparison module with mir_eval metrics`
  - Files: `backend/core/midi_comparator.py`

---

- [ ] 8. 복합 골든 테스트 구현

  **What to do**:
  - `backend/tests/golden/test_golden.py` 확장:
    * `TestMIDIComparison` — MIDI 레퍼런스와 비교
    * `TestEasyDifficulty` — Easy 출력 vs reference_easy.mid
    * `TestCMajorVariant` — 다장조 변형 비교 (해당 곡만)
    * `TestCompositeMetrics` — 복합 메트릭 리포트

  **Must NOT do**:
  - 기존 TestGoldenSmoke, TestGoldenCompare, TestMelodyComparison 삭제 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 1, 4, 5, 6, 7

  **References**:
  - `backend/tests/golden/test_golden.py` — 기존 테스트 (399줄, 3 클래스)
  - `backend/tests/golden/conftest.py` — 테스트 fixture (4 마커: golden, smoke, compare, melody)
  - `backend/core/midi_comparator.py` — MIDI 비교 (Task 7 결과)

  **Acceptance Criteria**:

  ```
  Scenario: 전체 골든 테스트 실행
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -v --tb=short
      2. Assert: 기존 테스트 PASS 유지
      3. Assert: 새 MIDI 비교 테스트 실행됨
    Expected Result: 모든 테스트 실행

  Scenario: MIDI 비교 테스트 8곡 실행
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -m midi -v
      2. 각 곡별 composite_score 수집
    Expected Result: 8곡 모두 비교 결과 출력
  ```

  **Commit**: YES
  - Message: `test(golden): add comprehensive MIDI comparison tests with composite metrics`
  - Files: `backend/tests/golden/test_golden.py`

---

- [ ] 9. 8곡 전체 유사도 측정 + 리포트

  **What to do**:
  - 선택된 모델 (최적 설정)로 8곡 전체 처리
  - 모든 비교 수행 (MXL, MIDI 원본, MIDI 쉬운, MIDI 다장조)
  - 상세 리포트:
    * 곡별 복합 메트릭 테이블
    * 기존 ByteDance 대비 개선율
    * 메트릭별 분석
    * 다음 개선 방향 제안

  **Must NOT do**:
  - 결과 조작 금지
  - 실패해도 재시도 금지 (1회만)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 8 (+3 if NO-GO)

  **Acceptance Criteria**:

  ```
  Scenario: 8곡 전체 측정
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -v --tb=short
      2. 각 곡별 모든 메트릭 수집
      3. 평균 계산
    Expected Result: 8곡 모두 측정 완료
    Evidence: .sisyphus/notepads/arrangement-model-results.md
  ```

  **Commit**: YES
  - Message: `docs: add arrangement model comprehensive evaluation report for 8 songs`
  - Files: `.sisyphus/notepads/arrangement-model-results.md`

---

- [ ] 10. 결과 평가 및 다음 단계 결정

  **What to do**:
  - Task 9 결과 기반 의사결정
  - 결정 매트릭스에 따라 다음 액션 결정
  - 사용자에게 결과 보고

  **결정 매트릭스**:
  | 상황 | 판정 | 다음 단계 |
  |------|------|-----------|
  | composite >= 70% | GREAT | 최적화 + UI 통합 진행 |
  | 50% <= composite < 70% | GOOD | 후처리 파이프라인 추가 |
  | 30% <= composite < 50% | MODERATE | 다른 모델 시도 (Music2MIDI↔Pop2Piano 교차) |
  | composite < 30% | POOR | Hybrid (Demucs+Transcription) 또는 PiCoGen2 (고VRAM) 검토 |

  **Must NOT do**:
  - 사용자 승인 없이 다음 플랜 자동 생성 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Task 9

  **Acceptance Criteria**:

  ```
  Scenario: 결과 리포트 및 권장사항
    Tool: Agent
    Steps:
      1. 결과 분석
      2. 결정 매트릭스 적용
      3. 사용자에게 보고
    Expected Result: 명확한 결과 + 다음 단계 권장
  ```

  **Commit**: YES
  - Message: `docs: complete arrangement model evaluation and next steps`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 0 | `spike(core): validate Music2MIDI` | notepads/ | GO/NO-GO 판정 |
| 1 | `test(golden): add MIDI reference files` | golden/data/*/reference*.mid | ls + pretty_midi |
| 2 | `feat(core): replace ByteDance with [model]` | audio_to_midi.py, requirements.txt | 단일 곡 MIDI |
| 3 | `feat(core): optimize Pop2Piano composer` (NO-GO만) | audio_to_midi.py | 스타일 비교 |
| 4 | `feat(core): replace comparison with mir_eval+DTW` | musicxml_comparator.py | self-compare |
| 5 | `feat(core): add polyphonic two-hand MusicXML` | midi_to_musicxml.py | 2-staff 확인 |
| 6 | `feat(core): [difficulty approach]` | difficulty_adjuster.py | 3단계 노트 수 |
| 7 | `feat(core): add MIDI direct comparison` | midi_comparator.py | self-compare |
| 8 | `test(golden): add comprehensive MIDI tests` | test_golden.py | pytest 실행 |
| 9 | `docs: evaluation report` | notepads/ | 리포트 |
| 10 | `docs: complete evaluation` | plans/ | 상태 업데이트 |

---

## Success Criteria

### Final Checklist
- [ ] Task 0: Music2MIDI 스파이크 완료 (GO/NO-GO 판정)
- [ ] 편곡 모델 8곡 MIDI 생성 성공
- [ ] MIDI 레퍼런스 골든 테스트 통합
- [ ] 비교 알고리즘 mir_eval + DTW 교체
- [ ] 복합 메트릭 출력 (melody_f1, pitch_class_f1, chroma, composite)
- [ ] 양손 피아노 MusicXML 생성
- [ ] 3단계 난이도 생성 (Easy/Medium/Hard)
- [ ] MIDI 직접 비교 모듈
- [ ] 복합 골든 테스트 (MXL + MIDI 원본/쉬운/다장조)
- [ ] 8곡 전체 유사도 리포트
- [ ] 기존 ByteDance 대비 개선 확인
