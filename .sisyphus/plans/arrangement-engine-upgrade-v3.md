# 피아노 편곡 엔진 업그레이드 v3 — Music2MIDI 재도전 + Pop2Piano 폴백

## TL;DR

> **Quick Summary**: 새 Docker 환경(CUDA 12.1, torch >=2.2.0)에서 Music2MIDI 재시도 → GO 시 난이도 컨디셔닝 활용 / NO-GO 시 Pop2Piano(이미 코딩 완료) 검증 후 진행 + 비교 알고리즘 전면 개편 + MIDI 레퍼런스 골든 테스트 통합
>
> **v3 핵심 변경 (vs v2)**:
> - v2 스파이크는 **구 환경**(CUDA 11.8, torch 2.0.1)에서 실행 → NO-GO
> - **Docker 이미지가 이미 `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`으로 업그레이드**됨
> - 이전 NO-GO의 4가지 원인 중 3개가 해소됨 (CUDA ✅, torch ✅, torchaudio ✅)
> - 남은 리스크: Python 3.11 호환성만 검증 필요
> - Pop2Piano 코드가 이미 작성되어 있으므로 NO-GO 경로가 빠름
> - **Metis 가르드레일**: Pop2Piano 먼저 검증 → Music2MIDI 정찰 → 3단계 에스컬레이션 → 4시간 타임박스
>
> **Deliverables**:
> - 편곡 모델 통합 (`audio_to_midi.py` — Music2MIDI or Pop2Piano 검증 완료)
> - 비교 알고리즘 전면 교체 (`musicxml_comparator.py` → mir_eval + DTW + 다중 메트릭)
> - MIDI 레퍼런스 골든 테스트 데이터 통합 (원본/쉬운/다장조)
> - MusicXML 폴리포닉 지원 (`midi_to_musicxml.py` 양손 악보)
> - 난이도 시스템 (Music2MIDI: 네이티브 / Pop2Piano: 휴리스틱 재설계)
> - MIDI 직접 비교 모듈 (`midi_comparator.py` 신규)
> - 복합 골든 테스트 체계 (MXL + MIDI 동시 비교)
> - 8곡 전체 유사도 측정 리포트
>
> **Estimated Effort**: Large (1-2주)
> **Parallel Execution**: YES — 4 waves (Wave 0 → 1 → 2 → 3)
> **Critical Path**: Task 0 → Task 2 → Task 5 → Task 6 → Task 8 → Task 9 → Task 10

---

## 핵심 정책 (CRITICAL - 모든 태스크에 적용)

### Git 커밋 정책 (MANDATORY)
```
모든 task 진행 시 변경사항 즉시 커밋 + 리모트 푸쉬
- 각 task 완료 시 반드시 커밋
- 커밋 메시지: conventional commits 형식
- Music2MIDI 스파이크 전 반드시 새 브랜치 생성
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
- git branch에서 작업 → 실패 시 브랜치 폐기
- Pop2Piano 코드(현재 audio_to_midi.py)가 기본 폴백
- 원본 ByteDance 백업: audio_to_midi_bytedance.py.bak
- 원본 Basic Pitch 백업: audio_to_midi_basic_pitch.py.bak
```

### Music2MIDI 스파이크 정책 (MANDATORY - NEW in v3)
```
1. Pop2Piano를 먼저 검증한다 (이미 코딩된 코드가 동작하는지)
2. Music2MIDI 코드를 먼저 읽는다 (설치 전 API 확인)
3. 최대 3단계 에스컬레이션만 시도한다
4. 4시간 타임박스를 초과하지 않는다
5. 스파이크는 별도 git 브랜치에서 수행한다
6. 실패 시 모든 변경 사항을 되돌린다
```

---

## Context

### Original Request
- 팝송 오디오 → 피아노 편곡 악보 자동 생성 시스템 전면 업그레이드
- Music2MIDI를 더 적극적으로 시도, 진짜 안 되면 Pop2Piano 폴백
- MIDI 레퍼런스(원본/쉬운/다장조) 골든 테스트 통합

### v2 → v3 변경 근거
- v2 스파이크(2026-02-05): CUDA 11.8, torch 2.0.1 환경에서 NO-GO 판정
- **현재 Dockerfile이 이미 `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`으로 변경됨**
- 이전 NO-GO 원인 4개 중 3개 해소:

| # | 실패 원인 | v2 당시 | v3 현재 | 해소? |
|---|----------|---------|---------|-------|
| 1 | CUDA 11.8 vs 12.1 필요 | CUDA 11.8 | **CUDA 12.1** | ✅ |
| 2 | torch 2.0.1 vs 2.1+ 필요 | torch 2.0.1 | **torch >=2.2.0** | ✅ |
| 3 | torchaudio 호환성 | torchaudio 2.0.2 | **torchaudio >=2.2.0** | ✅ |
| 4 | Python 3.11 vs 3.9 | Python 3.11 | Python 3.11 | ⚠️ 미확인 |

### 기술 세부사항

**Music2MIDI**:
- GitHub: https://github.com/ytinyui/music2midi (14★, MIT, MMM 2025)
- 모델: T5-small 기반 ~30M params → 2-4GB VRAM
- 출력: `pretty_midi` 객체
- 컨디셔닝: `cond_index=[genre_idx, difficulty_idx]` (pop=1, beginner=0/intermediate=1/advanced=2)
- 체크포인트: `epoch.799-step.119200.ckpt` (119MB)
- 의존성: pytorch-lightning, omegaconf, more-itertools, mir_eval

**Pop2Piano (현재 코드 — 이미 작성됨, 미테스트)**:
- HuggingFace: `sweetcocoa/pop2piano`
- Import: `from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor`
- 샘플레이트: 44100Hz
- composer_vocab_size = 21 (21개 스타일)
- 코드: `backend/core/audio_to_midi.py` (185줄, Pop2Piano 구현)

**mir_eval**:
- pitches: Hz 단위 (MIDI 번호 아님! → `mir_eval.util.midi_to_hz()` 변환 필요)
- `mir_eval.transcription.precision_recall_f1_overlap()` — 폴리포닉 지원
- 기본 tolerance: onset 50ms, pitch 50 cents

### 현재 코드베이스 상태
- `backend/core/audio_to_midi.py` — **Pop2Piano 구현 (185줄, 미테스트)**
- `backend/core/audio_to_midi_bytedance.py.bak` — ByteDance 백업
- `backend/core/audio_to_midi_basic_pitch.py.bak` — Basic Pitch 백업
- `backend/Dockerfile` — `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`
- `backend/requirements.txt` — torch>=2.2.0, torchaudio>=2.2.0, transformers>=4.35.0
- `backend/core/musicxml_comparator.py` — 현재 greedy matching (ONSET_TOLERANCE=3.0s)
- `backend/core/midi_to_musicxml.py` — 모노포닉 단일 스태프
- `backend/core/difficulty_adjuster.py` — 휴리스틱 노트 스트리핑
- `backend/tests/golden/test_golden.py` — smoke + compare + melody 테스트
- `test/spike_music2midi.py` — 이전 스파이크 스크립트 (구 환경용)

---

## Work Objectives

### Core Objective
새 Docker 환경(CUDA 12.1)에서 Music2MIDI를 최대한 시도하고, 불가능 시 Pop2Piano를 검증하여 최적의 편곡 모델을 확정한 뒤, 복합 테스트 체계를 구축하여 피아노 편곡 품질을 최대한 끌어올린다.

### Concrete Deliverables
- `backend/core/audio_to_midi.py` — 편곡 모델 확정 (Music2MIDI or Pop2Piano 검증)
- `backend/core/musicxml_comparator.py` — mir_eval + DTW + 다중 메트릭
- `backend/core/midi_comparator.py` — MIDI 직접 비교 모듈 (신규)
- `backend/core/midi_to_musicxml.py` — 폴리포닉 양손 악보 지원
- `backend/core/difficulty_adjuster.py` — 모델에 맞는 난이도 시스템
- `backend/tests/golden/data/song_XX/` — MIDI 레퍼런스 추가
- `backend/tests/golden/test_golden.py` — MIDI 비교 테스트 추가

### Definition of Done
- [ ] 편곡 모델(Music2MIDI or Pop2Piano)이 8곡 모두 MIDI 생성 성공
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
- ❌ ByteDance/Basic Pitch .bak 파일 삭제 금지
- ❌ 별도 Docker 컨테이너(마이크로서비스) 구성 금지 — 단일 컨테이너만
- ❌ Dockerfile 베이스 이미지 변경 금지 (`pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime` 유지)
- ❌ Music2MIDI 스파이크 3단계 에스컬레이션 초과 시도 금지
- ❌ Music2MIDI 스파이크 4시간 타임박스 초과 금지

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
| **모델 MIDI 생성** | Bash (`docker compose run`) | Python import + 단일 곡 MIDI 생성 |
| **MIDI 비교** | Bash | pytest 실행 + 유사도 수치 수집 |
| **MusicXML 생성** | Bash | 파일 존재 + music21 파싱 성공 |
| **골든 테스트** | Bash | `pytest -m golden` 실행 |
| **난이도 확인** | Bash | 3파일 생성 + 노트 수 비교 |

---

## Execution Strategy

### 조건부 실행 흐름 (CRITICAL)

```
Wave 0 (Gate — 단일 태스크, 3개 내부 Phase):
└── Task 0: Pop2Piano 검증 → Music2MIDI 정찰 → Music2MIDI 스파이크
    │
    ├── Phase A: Pop2Piano 베이스라인 검증 (Docker 빌드 + 기존 코드 테스트)
    │   → 실패 시: Pop2Piano 수정부터
    │   → 성공 시: 베이스라인 기록 후 Phase B로
    │
    ├── Phase B: Music2MIDI 정찰 (코드 읽기, API 확인, 설치 없이)
    │   → 난이도 API 없으면: 즉시 NO-GO
    │   → API 확인되면: Phase C로
    │
    └── Phase C: Music2MIDI 스파이크 (3단계 에스컬레이션, 4시간 타임박스)
        ├── Approach 1: 직접 pip install
        ├── Approach 2: 의존성 수동 해결
        └── Approach 3: 소스 설치 + 호환성 패치
            → 성공: GO
            → 실패: NO-GO (Pop2Piano로 진행)

    ┌─── GO (Music2MIDI 성공) ──────────────────────────────┐
    │                                                        │
    │  Wave 1 (Parallel):                                    │
    │  ├── Task 1: MIDI 레퍼런스 골든 테스트 통합             │
    │  └── Task 2-A: Music2MIDI 본격 통합                    │
    │                                                        │
    │  Wave 2 (Parallel):                                    │
    │  ├── Task 4: 비교 알고리즘 전면 교체                    │
    │  ├── Task 5: MusicXML 폴리포닉 지원                    │
    │  └── Task 6-A: 난이도 — Music2MIDI 네이티브 활용        │
    │                                                        │
    └────────────────────────────────────────────────────────┘

    ┌─── NO-GO (Music2MIDI 실패) ───────────────────────────┐
    │                                                        │
    │  Wave 1 (Parallel):                                    │
    │  ├── Task 1: MIDI 레퍼런스 골든 테스트 통합             │
    │  ├── Task 2-B: Pop2Piano 검증 완료 확인 + 최적화       │
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

### Agent Dispatch Summary

| Wave | Tasks | Recommended |
|------|-------|-------------|
| 0 | 0 | `deep` — 의존성 디버깅 + 판정 |
| 1 | 1, 2 (,3) | `quick` (Task 1), `unspecified-high` (Task 2, 3) |
| 2 | 4, 5, 6 | `unspecified-high` × 3 (parallel) |
| 3 | 7, 8, 9 | `unspecified-high` (7, 8), `unspecified-low` (9) |
| 4 | 10 | `unspecified-low` |

---

## TODOs

- [x] 0. Pop2Piano 검증 + Music2MIDI 재스파이크 (Gate — v3 핵심 변경)

  **Overview**: 3개 내부 Phase로 구성. Pop2Piano 먼저 검증 → Music2MIDI 정찰 → Music2MIDI 스파이크.

  ### Phase A: Pop2Piano 베이스라인 검증 (30분)

  **What to do**:
  - Docker 이미지 빌드 (`docker compose build backend`)
  - 현재 `audio_to_midi.py`(Pop2Piano 코드, 185줄)가 실제로 동작하는지 테스트
  - song_01로 MIDI 생성 테스트
  - 생성된 MIDI의 노트 수, 피치 범위, 길이 기록
  - 처리 시간 기록 (베이스라인)

  **Phase A 결과 분기**:
  - Pop2Piano 동작 ✅ → 베이스라인 기록, Phase B로 진행
  - Pop2Piano 실패 ❌ → Pop2Piano 수정 먼저 (에러 메시지 기반 디버깅)
    - Pop2Piano 수정 불가 시 → ByteDance 복원 (.bak), Phase B로 직접 진행

  ### Phase B: Music2MIDI 정찰 (30분, 설치 없이)

  **What to do**:
  - Music2MIDI GitHub 레포 클론 (`/tmp/music2midi`)
  - 소스 코드를 **읽기만** 한다 (설치 X):
    * `requirements.txt` 또는 `setup.py`의 의존성 목록 확인
    * Python 3.11과 호환되지 않는 구문이 있는지 확인 (e.g., `match-case` 반대 방향)
    * 난이도 컨디셔닝 API 확인: `cond_index` 파라미터가 `generate()` 메서드에 존재하는지
    * 모델 체크포인트 크기 확인 (119MB — 이미 확인됨)
  - `config.yaml` 구조 확인

  **Phase B GO/NO-GO 기준** (설치 전 판정):
  - 난이도 API(`cond_index`)가 `generate()` 메서드에 없으면 → **즉시 NO-GO** (킬러 피처 불가)
  - 의존성 중 Python 3.9 전용 패키지가 있으면 → 리스크 기록, Phase C에서 확인
  - 모델이 10GB 이상이면 → **즉시 NO-GO**

  ### Phase C: Music2MIDI 스파이크 (최대 4시간, 3단계 에스컬레이션)

  **⚠️ 필수 사전 조건**: 별도 git 브랜치 생성
  ```bash
  git checkout -b spike/music2midi-v3-cuda12
  ```

  **Approach 1: 직접 pip install (타임아웃 30분)**
  ```bash
  docker compose run --rm backend bash -c "
    pip install pytorch-lightning omegaconf more-itertools mir_eval
    pip install git+https://github.com/ytinyui/music2midi.git
    python -c 'import sys; sys.path.insert(0, \"/tmp\"); from music2midi.model import Music2MIDI; print(\"Import OK\")'
  "
  ```
  - 성공: Approach 1 OK → MIDI 생성 테스트로
  - 실패: Approach 2로

  **Approach 2: 의존성 수동 해결 (타임아웃 30분)**
  ```bash
  docker compose run --rm backend bash -c "
    # pytorch-lightning 버전 고정 (호환성 높은 버전)
    pip install 'pytorch-lightning>=2.0,<2.3' omegaconf more-itertools mir_eval
    git clone https://github.com/ytinyui/music2midi.git /tmp/music2midi
    cd /tmp/music2midi && pip install -e .
    python -c 'from music2midi.model import Music2MIDI; print(\"Import OK\")'
  "
  ```
  - 성공: Approach 2 OK → MIDI 생성 테스트로
  - 실패: Approach 3로

  **Approach 3: 소스 설치 + 호환성 패치 (타임아웃 1시간)**
  ```bash
  docker compose run --rm backend bash -c "
    git clone https://github.com/ytinyui/music2midi.git /tmp/music2midi
    cd /tmp/music2midi
    # setup.py/pyproject.toml에서 Python 버전 제한 제거 (있을 경우)
    # 호환성 패치 적용 (구체적 에러 메시지에 따라)
    pip install -e . --no-deps
    pip install pytorch-lightning omegaconf more-itertools mir_eval
    python -c 'from music2midi.model import Music2MIDI; print(\"Import OK\")'
  "
  ```
  - 성공: Approach 3 OK → MIDI 생성 테스트로
  - 실패: **NO-GO 확정** → git 브랜치 폐기, Pop2Piano 경로

  **MIDI 생성 + 난이도 테스트 (import 성공 후)**:
  ```python
  # 1. 단일 곡 MIDI 생성
  model = Music2MIDI.load_from_checkpoint(CKPT, config_path="config.yaml")
  model.to(device).eval()
  midi_data = model.generate("tests/golden/data/song_01/input.mp3", cond_index=[1, 2])
  midi_data.write("/tmp/test_advanced.mid")
  # Assert: note_count > 0, duration > 30s

  # 2. 난이도 컨디셔닝 테스트
  for diff_idx, name in [(0, "beginner"), (1, "intermediate"), (2, "advanced")]:
      midi = model.generate(audio_path, cond_index=[1, diff_idx])
      midi.write(f"/tmp/test_{name}.mid")
  # Assert: beginner_notes < intermediate_notes < advanced_notes

  # 3. 처리 시간 확인 (1곡 5분 이내)
  ```

  **GO 기준 (ALL must pass)**:
  1. import 성공 + 모델 로딩 성공
  2. song_01에서 MIDI 생성 성공 (note_count > 0)
  3. 난이도별 노트 수 차이 확인 (beginner < intermediate < advanced)
  4. 생성 시간 5분 이내 (1곡 기준)
  5. Pop2Piano 베이스라인이 깨지지 않음 (회귀 없음)

  **NO-GO 기준 (ANY triggers)**:
  - 3단계 에스컬레이션 모두 실패
  - 4시간 타임박스 초과
  - 난이도 API가 존재하지 않음 (Phase B에서 확인)
  - 모델 다운로드 실패 또는 10GB 초과
  - MIDI 생성 자체가 실패 (빈 파일, 에러)

  **NO-GO 시 복구**:
  ```bash
  git checkout master  # 또는 main
  git branch -D spike/music2midi-v3-cuda12
  ```
  Pop2Piano 코드(현재 `audio_to_midi.py`)를 그대로 사용. Phase A에서 검증 완료된 상태.

  **Must NOT do**:
  - 8곡 전체 테스트 금지 (1곡만으로 판정)
  - 비교 알고리즘 구현 금지 (단순 노트 수/피치 범위만 비교)
  - 4시간 넘게 시도 금지
  - 3단계 에스컬레이션 외 추가 시도 금지
  - Dockerfile 베이스 이미지 변경 금지

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: 새 라이브러리 설치 + 의존성 디버깅 + 호환성 패치 + 판정 로직. 자율적 문제 해결 능력 필요.

  **Parallelization**:
  - **Can Run In Parallel**: NO (Gate task — 이후 모든 태스크의 전제)
  - **Blocks**: ALL subsequent tasks
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `backend/core/audio_to_midi.py:42-65` — Singleton 모델 로딩 패턴 (Pop2Piano), 이 패턴을 Music2MIDI에도 적용
  - `backend/core/audio_to_midi.py:68-184` — 함수 시그니처, 반환 형식, 에러 처리 패턴
  - `backend/core/audio_to_midi.py:15-27` — scipy 호환성 패치 패턴 (비슷한 호환성 이슈 발생 시 참고)

  **API/Type References**:
  - Music2MIDI GitHub: https://github.com/ytinyui/music2midi — `model.py`의 `generate()` 메서드, `cond_index` 파라미터
  - Music2MIDI Release: https://github.com/ytinyui/music2midi/releases/tag/0.1.0 — 체크포인트 다운로드
  - `test/spike_music2midi.py` — 이전 스파이크 스크립트 (구 환경용, 참고용)

  **Documentation References**:
  - `.sisyphus/notepads/arrangement-engine-upgrade/spike-result.md` — 이전 NO-GO 상세 원인 (회피해야 할 실수들)
  - `.sisyphus/notepads/arrangement-engine-upgrade/issues.md` — Pop2Piano PyTorch 호환성 이슈 기록

  **Infrastructure References**:
  - `backend/Dockerfile` — 현재 Docker 이미지 (`pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`)
  - `backend/requirements.txt` — 현재 의존성 (torch>=2.2.0, transformers>=4.35.0)
  - `docker-compose.yml` — 서비스 설정, 볼륨 마운트, GPU 없음

  **Acceptance Criteria**:

  ```
  Scenario: Docker 빌드 성공
    Tool: Bash
    Preconditions: Docker Desktop 정상 작동
    Steps:
      1. docker compose build backend
      2. Assert: exit code 0
      3. docker compose run --rm backend python -c "import torch; print(f'torch {torch.__version__}, CUDA: {torch.cuda.is_available()}')"
      4. Assert: torch 2.2+ 출력
    Expected Result: Docker 이미지 빌드 및 Python 환경 정상
    Evidence: stdout 캡처

  Scenario: Pop2Piano 베이스라인 검증 (Phase A)
    Tool: Bash
    Preconditions: Docker 이미지 빌드 완료
    Steps:
      1. docker compose run --rm backend python -c "
         from core.audio_to_midi import convert_audio_to_midi
         from pathlib import Path
         result = convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test_pop2piano.mid')
         )
         assert result['note_count'] > 0, f'No notes: {result}'
         print(f'Pop2Piano OK: {result[\"note_count\"]} notes, {result[\"duration_seconds\"]:.1f}s, {result[\"processing_time\"]:.1f}s')
         "
      2. Assert: exit code 0, note_count > 0
    Expected Result: Pop2Piano MIDI 생성 성공
    Failure Indicators: ImportError, RuntimeError, note_count == 0
    Evidence: stdout (노트 수, 길이, 처리 시간)

  Scenario: Music2MIDI 정찰 — 난이도 API 확인 (Phase B)
    Tool: Bash
    Preconditions: Music2MIDI 레포 클론
    Steps:
      1. git clone https://github.com/ytinyui/music2midi.git /tmp/music2midi
      2. grep -n "cond_index" /tmp/music2midi/music2midi/model.py
      3. grep -n "def generate" /tmp/music2midi/music2midi/model.py
      4. Assert: cond_index 파라미터가 generate() 메서드에 존재
    Expected Result: 난이도 컨디셔닝 API 확인
    Failure Indicators: cond_index 없음 → 즉시 NO-GO
    Evidence: grep 출력

  Scenario: Music2MIDI 스파이크 — import + MIDI 생성 (Phase C)
    Tool: Bash
    Preconditions: Phase B 통과, git 브랜치 생성
    Steps:
      1. [Approach 1, 2, 또는 3 중 성공한 방법]
      2. docker compose run --rm backend python -c "
         import sys; sys.path.insert(0, '/tmp/music2midi')
         from music2midi.model import Music2MIDI
         print('Import OK')
         "
      3. Assert: "Import OK"
    Expected Result: Music2MIDI 정상 import
    Evidence: stdout

  Scenario: Music2MIDI 난이도 컨디셔닝 테스트 (Phase C — import 성공 후)
    Tool: Bash
    Steps:
      1. 3개 난이도(beginner/intermediate/advanced)로 song_01 MIDI 각각 생성
      2. pretty_midi로 각 파일의 노트 수 파싱
      3. Assert: beginner_notes < intermediate_notes < advanced_notes
    Expected Result: 난이도별 노트 수 단조 증가
    Failure Indicators: 노트 수 역전, 생성 실패
    Evidence: 3개 MIDI 파일 + 노트 수 비교 출력

  Scenario: GO/NO-GO 판정 기록
    Tool: Bash
    Steps:
      1. 위 시나리오 결과 종합
      2. GO/NO-GO 판정
      3. 결과를 .sisyphus/notepads/arrangement-engine-upgrade/music2midi-spike-v3.md에 기록
    Expected Result: 명확한 판정 + 근거
    Evidence: .sisyphus/notepads/arrangement-engine-upgrade/music2midi-spike-v3.md
  ```

  **Evidence to Capture:**
  - [ ] Pop2Piano 베이스라인 결과 (노트 수, 처리 시간)
  - [ ] Music2MIDI 정찰 결과 (API 존재 여부)
  - [ ] 각 Approach 시도 결과 (성공/실패 + 에러 메시지)
  - [ ] GO 시: 난이도별 노트 수 비교
  - [ ] 판정 문서: `.sisyphus/notepads/arrangement-engine-upgrade/music2midi-spike-v3.md`

  **Commit**: YES
  - Message (GO): `spike(core): Music2MIDI validated on CUDA 12.1 — GO for integration`
  - Message (NO-GO): `spike(core): Music2MIDI re-spike on CUDA 12.1 — NO-GO, proceeding with Pop2Piano`
  - Files: `.sisyphus/notepads/arrangement-engine-upgrade/music2midi-spike-v3.md`, (+ 브랜치 병합 or 폐기)
  - Pre-commit: Pop2Piano 베이스라인 재검증

---

- [x] 1. MIDI 레퍼런스 골든 테스트 데이터 통합

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
  - `test/` 폴더 전체 파일 목록 — MIDI 원본 파일들
  - `backend/tests/golden/data/song_01/metadata.json` — 기존 메타데이터 형식 (새 키 `midi_variants` 추가)
  - `backend/tests/golden/conftest.py` — 골든 테스트 fixture (마커: golden, smoke, compare, melody)

  **Acceptance Criteria**:

  ```
  Scenario: MIDI 레퍼런스 파일 복사 확인
    Tool: Bash
    Steps:
      1. ls backend/tests/golden/data/song_01/reference.mid
      2. ls backend/tests/golden/data/song_01/reference_easy.mid
      3. ls backend/tests/golden/data/song_03/reference_cmajor.mid
      4. 모든 8곡에 reference.mid, reference_easy.mid 존재 확인
      5. 다장조 파일 존재 확인: song_03, 04, 05, 06, 08 (해당 곡만)
    Expected Result: MIDI 파일 정상 복사
    Evidence: ls 출력

  Scenario: MIDI 파일 구조 분석
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         import pretty_midi
         pm = pretty_midi.PrettyMIDI('tests/golden/data/song_01/reference.mid')
         notes = sum(len(i.notes) for i in pm.instruments)
         print(f'Tracks: {len(pm.instruments)}, Notes: {notes}, Duration: {pm.get_end_time():.1f}s')
         assert notes > 0, 'No notes in MIDI'
         "
      2. Assert: 트랙 수 >= 1, 노트 수 > 0
    Expected Result: 모든 MIDI 파일 정상 파싱
    Evidence: 분석 리포트 출력

  Scenario: metadata.json 업데이트 확인
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         import json
         d = json.load(open('tests/golden/data/song_03/metadata.json'))
         assert 'midi_variants' in d, 'Missing midi_variants key'
         print(f'Variants: {d[\"midi_variants\"]}')
         "
    Expected Result: 메타데이터에 MIDI 변형 정보 포함
    Evidence: JSON 출력
  ```

  **Commit**: YES
  - Message: `test(golden): add MIDI reference files (original, easy, cmajor variants)`
  - Files: `backend/tests/golden/data/song_*/reference*.mid`, `backend/tests/golden/data/song_*/metadata.json`

---

- [x] 2. 편곡 모델 통합 (audio_to_midi.py 확정)

  > **⚠️ 조건부 태스크**: Task 0 결과에 따라 경로 A 또는 B 실행

  ### 경로 A: Music2MIDI 본격 통합 (Task 0 = GO)

  **What to do**:
  - Task 0에서 검증된 Music2MIDI 코드를 프로덕션 수준으로 정리
  - 현재 Pop2Piano `audio_to_midi.py`를 `audio_to_midi_pop2piano.py.bak`으로 백업
  - Music2MIDI 기반으로 `audio_to_midi.py` 재작성
  - `requirements.txt`에 Music2MIDI 의존성 추가
  - **spike 브랜치를 master로 병합**
  - 함수 시그니처 유지 + 난이도 함수 추가:

  ```python
  # 유지해야 할 함수 시그니처
  def convert_audio_to_midi(audio_path: Path, output_path: Path) -> Dict[str, Any]:
      """Returns: {"midi_path": str, "note_count": int, "duration_seconds": float, "processing_time": float}"""

  # 새로 추가: 난이도별 생성 함수
  def convert_audio_to_midi_with_difficulty(
      audio_path: Path, output_path: Path, difficulty: str = "advanced"
  ) -> Dict[str, Any]:
      """difficulty: "beginner" | "intermediate" | "advanced" """
  ```

  ### 경로 B: Pop2Piano 검증 완료 + 최적화 (Task 0 = NO-GO)

  **What to do**:
  - Task 0 Phase A에서 이미 검증된 Pop2Piano 코드 유지
  - 추가 최적화:
    * OOM(Out of Memory) 에러 시 CPU 폴백 확인 (코드 이미 있음: line 134-146)
    * 3곡 이상 테스트 (song_01, song_04, song_08)
    * 처리 시간 벤치마크 기록
  - **Music2MIDI 실패 사유를 `.sisyphus/notepads/`에 기록** (미래 재시도용)

  ### 공통 Must NOT do
  - 함수 시그니처 변경 금지 (`convert_audio_to_midi(audio_path, output_path)`)
  - 반환 dict 키 변경 금지
  - .bak 파일 삭제 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 모델 통합 + Docker 환경 + 에러 처리

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 1)
  - **Parallel Group**: Wave 1
  - **Blocks**: Tasks 3(NO-GO만), 5, 6, 9
  - **Blocked By**: Task 0

  **References**:
  - `backend/core/audio_to_midi.py:1-185` — 현재 Pop2Piano 구현 (시그니처, singleton 패턴, 에러 처리)
  - `backend/core/audio_to_midi.py:42-65` — Singleton 모델 로딩 패턴 (Music2MIDI에서도 동일하게 적용)
  - `backend/core/audio_to_midi.py:128-146` — GPU OOM 폴백 로직 (Music2MIDI에서도 적용)
  - Task 0 결과: `.sisyphus/notepads/arrangement-engine-upgrade/music2midi-spike-v3.md`
  - Music2MIDI GitHub: https://github.com/ytinyui/music2midi
  - Pop2Piano HuggingFace: https://huggingface.co/docs/transformers/en/model_doc/pop2piano
  - `backend/requirements.txt` — 현재 의존성

  **Acceptance Criteria**:

  ```
  Scenario: 모델 import 성공
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from core.audio_to_midi import convert_audio_to_midi
         print('Import OK')
         "
      2. Assert: "Import OK"
    Expected Result: 정상 import

  Scenario: song_01 MIDI 생성
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from pathlib import Path
         from core.audio_to_midi import convert_audio_to_midi
         result = convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test_model.mid')
         )
         assert result['note_count'] > 0, f'No notes: {result}'
         print(f'Notes: {result[\"note_count\"]}, Duration: {result[\"duration_seconds\"]:.1f}s, Time: {result[\"processing_time\"]:.1f}s')
         "
      2. Assert: exit code 0, note_count > 0
    Expected Result: MIDI 생성 성공

  Scenario: 3곡 벤치마크 (song_01, song_04, song_08)
    Tool: Bash
    Steps:
      1. 3곡 각각 MIDI 생성
      2. 노트 수, 처리 시간 기록
    Expected Result: 3곡 모두 MIDI 생성 성공
    Evidence: 벤치마크 테이블

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
      2. ls backend/core/audio_to_midi_basic_pitch.py.bak
      3. (GO 경로) ls backend/core/audio_to_midi_pop2piano.py.bak
      4. Assert: 모든 백업 파일 존재
  ```

  **Commit**: YES
  - Message (GO): `feat(core): integrate Music2MIDI for piano arrangement generation with difficulty conditioning`
  - Message (NO-GO): `feat(core): verify and optimize Pop2Piano integration for piano arrangement generation`
  - Files: `backend/core/audio_to_midi.py`, `backend/requirements.txt`, (GO: `audio_to_midi_pop2piano.py.bak`)

---

- [x] 3. Pop2Piano composer 스타일 탐색 (NO-GO 경로만)

  > **⚠️ Task 0 = NO-GO일 때만 실행. GO일 때는 SKIP.**

  **What to do**:
  - Pop2Piano의 21개 composer 스타일을 song_01에 대해 전부 생성
  - 각 스타일의 MIDI를 reference.mid와 비교 (노트 수, 피치 범위)
  - 레퍼런스 편곡 스타일에 가장 가까운 composer 식별
  - 최적 composer를 기본값으로 설정

  **Must NOT do**:
  - 8곡 전체를 모든 스타일로 생성 금지 — 1곡만
  - 스타일 선택을 하드코딩 금지 — 파라미터로

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1, NO-GO path)
  - **Blocks**: Task 9
  - **Blocked By**: Task 2-B

  **References**:
  - `backend/core/audio_to_midi.py:130-133` — 현재 composer="composer1" 하드코딩 (변경 대상)
  - `backend/tests/golden/data/song_01/reference.mid` — 비교 대상

  **Acceptance Criteria**:

  ```
  Scenario: 21개 스타일 MIDI 생성
    Tool: Bash
    Steps:
      1. 21개 composer 스타일(composer1~composer21)로 song_01의 MIDI 각각 생성
      2. 각 MIDI의 노트 수, 피치 범위 비교
      3. Assert: 21개 파일 모두 생성 성공
    Expected Result: 모든 스타일의 MIDI 파일 생성
    Evidence: 스타일별 비교 테이블

  Scenario: 최적 스타일 식별
    Tool: Bash
    Steps:
      1. 각 스타일 MIDI를 reference.mid와 비교 (노트 수 유사도, 피치 범위 오버랩)
      2. 상위 3개 composer와 유사도 리포트
      3. 최적 composer를 audio_to_midi.py에 반영
    Expected Result: 최적 composer 식별 + 기본값 변경
    Evidence: .sisyphus/notepads/arrangement-engine-upgrade/pop2piano-style-comparison.md
  ```

  **Commit**: YES
  - Message: `feat(core): optimize Pop2Piano composer style selection based on reference comparison`
  - Files: `backend/core/audio_to_midi.py`

---

- [x] 4. 비교 알고리즘 전면 교체 (mir_eval + DTW + 다중 메트릭)

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
  - `backend/core/musicxml_comparator.py:1-30` — 현재 비교 로직 (greedy matching, ONSET_TOLERANCE=3.0s)
  - `backend/core/midi_parser.py` — Note dataclass (pitch: int = MIDI number)
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
         assert abs(hz - 261.63) < 1.0, f'Wrong Hz: {hz}'
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
         assert result['similarity'] > 0.99, f'Self-similarity too low: {result}'
         print(f'Self-similarity: {result[\"similarity\"]:.2%}')
         "
    Expected Result: 기존 API 정상 동작

  Scenario: 복합 메트릭 출력 확인
    Tool: Bash
    Steps:
      1. 새 compare 함수로 song_01 reference.mxl 자기비교
      2. Assert: melody_f1, pitch_class_f1, chroma_similarity, composite_score 키 존재
      3. Assert: 자기비교 시 composite_score > 0.95
    Expected Result: 복합 메트릭 모두 출력
  ```

  **Commit**: YES
  - Message: `feat(core): replace comparison algorithm with mir_eval + DTW + composite metrics`
  - Files: `backend/core/musicxml_comparator.py`, `backend/requirements.txt`

---

- [x] 5. MusicXML 폴리포닉 양손 악보 지원

  **What to do**:
  - `backend/core/midi_to_musicxml.py` 수정:
    * 편곡 모델 출력 MIDI (폴리포닉) → 양손 피아노 악보
    * 높은음자리표 (RH: MIDI >= 60) + 낮은음자리표 (LH: MIDI < 60)
    * 2스태프 피아노 파트로 구성
  - 기존 모노포닉 모드도 유지 (fallback)
  - RH/LH 분할 기준을 설정 가능하게 (기본값 60)

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
  - `backend/core/midi_to_musicxml.py:1-30` — 현재 모노포닉 구현 (seconds_to_quarter_length, notes_to_stream)
  - `backend/core/midi_parser.py` — Note dataclass (pitch: int MIDI number)
  - `backend/tests/golden/data/song_01/reference.mxl` — 레퍼런스 MXL 구조 (2스태프 참조)
  - music21 문서: Part, Staff, Clef

  **Acceptance Criteria**:

  ```
  Scenario: 양손 악보 생성
    Tool: Bash
    Steps:
      1. 편곡 모델로 song_01 MIDI 생성
      2. midi_to_musicxml로 MusicXML 변환 (polyphonic=True)
      3. music21으로 파싱하여 Part 수 확인
      4. Assert: 2개 Part 또는 2개 Staff
    Expected Result: 양손 피아노 악보
    Evidence: Part/Staff 구조 출력

  Scenario: 기존 모노포닉 모드 유지
    Tool: Bash
    Steps:
      1. midi_to_musicxml로 MusicXML 변환 (polyphonic=False 또는 기본)
      2. Assert: 기존 단일 스태프 모드 동작
    Expected Result: 하위 호환성 유지
  ```

  **Commit**: YES
  - Message: `feat(core): add polyphonic two-hand piano score support in MusicXML`
  - Files: `backend/core/midi_to_musicxml.py`

---

- [x] 6. 난이도 시스템

  > **⚠️ 조건부 태스크**: Task 0 결과에 따라 경로 A 또는 B 실행

  ### 경로 A: Music2MIDI 네이티브 난이도 활용 (Task 0 = GO)

  **What to do**:
  - `backend/core/difficulty_adjuster.py`를 경량 후처리로 축소
  - Music2MIDI가 난이도별 MIDI를 직접 생성 (beginner/intermediate/advanced)
  - `difficulty_adjuster.py`는 옥타브 정규화, 코드 심볼 삽입 등 후처리만
  - `generate_all_sheets()` 수정: 3회 MIDI 생성 (각 난이도별) → 경량 후처리

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
  - `backend/core/difficulty_adjuster.py:1-30` — 현재 난이도 시스템 (Easy/Medium/Hard 규칙 테이블)
  - `backend/core/melody_extractor.py` — Skyline 알고리즘 (NO-GO 경로 B에서 활용)
  - `backend/tests/golden/data/song_01/reference_easy.mid` — Easy 레퍼런스

  **Acceptance Criteria**:

  ```
  Scenario: 3단계 난이도 생성
    Tool: Bash
    Steps:
      1. song_01에 대해 generate_all_sheets() 호출
      2. sheet_easy.musicxml, sheet_medium.musicxml, sheet_hard.musicxml 존재 확인
      3. 각 파일의 노트 수 파싱
      4. Assert: Easy 노트 수 < Medium 노트 수 < Hard 노트 수
    Expected Result: 3단계 파일 생성, 노트 수 단계적
    Evidence: 각 파일의 노트 수 출력

  Scenario (GO 경로만): 난이도별 독립 MIDI 확인
    Tool: Bash
    Steps:
      1. beginner/intermediate/advanced 각각 별도 MIDI 파일 확인
      2. Assert: 각 MIDI의 노트 패턴이 다름 (단순 노트 제거가 아님)
    Expected Result: 모델이 난이도별 다른 편곡을 생성
    Evidence: 노트 수 + 피치 범위 비교
  ```

  **Commit**: YES
  - Message (GO): `feat(core): integrate Music2MIDI native difficulty conditioning`
  - Message (NO-GO): `feat(core): redesign difficulty system for polyphonic piano arrangement`
  - Files: `backend/core/difficulty_adjuster.py`

---

- [x] 7. MIDI 직접 비교 모듈 구현

  **What to do**:
  - `backend/core/midi_comparator.py` 신규 생성:
    * MIDI 파일 간 직접 비교 (MusicXML 변환 없이)
    * pretty_midi 기반 노트 추출
    * mir_eval 메트릭 적용 (**Hz 변환 필수**: `mir_eval.util.midi_to_hz()`)
    * DTW 정렬 적용
    * 복합 메트릭 출력 (Task 4와 동일 구조)
  - Task 4의 `musicxml_comparator.py`와 공통 로직을 유틸 함수로 분리

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
      1. docker compose run --rm backend python -c "
         from core.midi_comparator import compare_midi
         result = compare_midi(
             'tests/golden/data/song_01/reference.mid',
             'tests/golden/data/song_01/reference.mid'
         )
         assert result['composite_score'] > 0.99, f'Self-compare too low: {result}'
         print(f'Self-compare: {result[\"composite_score\"]:.2%}')
         "
      2. Assert: composite_score > 0.99

  Scenario: 원본 vs 쉬운 비교
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from core.midi_comparator import compare_midi
         result = compare_midi(
             'tests/golden/data/song_01/reference.mid',
             'tests/golden/data/song_01/reference_easy.mid'
         )
         print(f'Original vs Easy: composite={result[\"composite_score\"]:.2%}, melody_f1={result[\"melody_f1\"]:.2%}')
         assert result['composite_score'] < 1.0, 'Should not be identical'
         assert result['melody_f1'] > 0.1, 'Melody should have some similarity'
         "
      2. Assert: 0.1 < composite_score < 1.0
    Expected Result: 의미 있는 차이 측정
  ```

  **Commit**: YES
  - Message: `feat(core): add MIDI direct comparison module with mir_eval composite metrics`
  - Files: `backend/core/midi_comparator.py`

---

- [x] 8. 복합 골든 테스트 구현

  **What to do**:
  - `backend/tests/golden/test_golden.py` 확장:
    * `TestMIDIComparison` — MIDI 레퍼런스와 생성 결과 비교
    * `TestEasyDifficulty` — Easy 출력 vs reference_easy.mid
    * `TestCMajorVariant` — 다장조 변형 비교 (해당 곡만)
    * `TestCompositeMetrics` — 복합 메트릭 리포트
  - 새 pytest 마커 추가: `@pytest.mark.midi`

  **Must NOT do**:
  - 기존 TestGoldenSmoke, TestGoldenCompare, TestMelodyComparison 삭제 금지
  - 기존 마커(golden, smoke, compare, melody) 변경 금지

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 1, 4, 5, 6, 7

  **References**:
  - `backend/tests/golden/test_golden.py:1-30` — 기존 테스트 구조 (TestGoldenSmoke 클래스)
  - `backend/tests/golden/conftest.py` — 테스트 fixture (4 마커)
  - `backend/core/midi_comparator.py` — MIDI 비교 (Task 7 결과)

  **Acceptance Criteria**:

  ```
  Scenario: 전체 골든 테스트 실행
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -v --tb=short 2>&1 | tail -30
      2. Assert: 기존 테스트 PASS 유지
      3. Assert: 새 MIDI 비교 테스트 실행됨
    Expected Result: 모든 테스트 실행

  Scenario: MIDI 비교 테스트 8곡 실행
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -m midi -v
      2. 각 곡별 composite_score 수집
    Expected Result: 8곡 모두 비교 결과 출력
    Evidence: pytest 출력
  ```

  **Commit**: YES
  - Message: `test(golden): add comprehensive MIDI comparison tests with composite metrics`
  - Files: `backend/tests/golden/test_golden.py`, `backend/tests/golden/conftest.py`

---

- [x] 9. 8곡 전체 유사도 측정 + 리포트

  **What to do**:
  - 확정된 모델 (최적 설정)로 8곡 전체 처리
  - 모든 비교 수행 (MXL, MIDI 원본, MIDI 쉬운, MIDI 다장조)
  - 상세 리포트:
    * 곡별 복합 메트릭 테이블
    * 기존 ByteDance 대비 개선율
    * 메트릭별 분석
    * Pop2Piano vs Music2MIDI 비교 (GO 시)
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

  **References**:
  - Task 8 결과 (골든 테스트 실행)
  - `.sisyphus/session-summary.md:124-134` — 기존 ByteDance 성적 (비교 기준선)

  **Acceptance Criteria**:

  ```
  Scenario: 8곡 전체 측정
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -v --tb=short
      2. 각 곡별 모든 메트릭 수집
      3. 평균 계산
    Expected Result: 8곡 모두 측정 완료
    Evidence: .sisyphus/notepads/arrangement-engine-upgrade/evaluation-report-v3.md

  Scenario: 기존 대비 개선 확인
    Tool: Bash
    Steps:
      1. 기존 ByteDance 평균 (20.31%)과 새 모델 평균 비교
      2. 리포트에 개선율 기록
    Expected Result: 개선율 수치 확인
  ```

  **Commit**: YES
  - Message: `docs: add arrangement model comprehensive evaluation report v3`
  - Files: `.sisyphus/notepads/arrangement-engine-upgrade/evaluation-report-v3.md`

---

- [ ] 10. 결과 평가 및 다음 단계 결정

  **What to do**:
  - Task 9 결과 기반 의사결정
  - 결정 매트릭스에 따라 다음 액션 결정
  - 사용자에게 결과 보고

  **결정 매트릭스**:
  | composite score | 판정 | 다음 단계 |
  |-----------------|------|-----------|
  | ≥ 70% | GREAT | 최적화 + UI 통합 진행 |
  | 50-70% | GOOD | 후처리 파이프라인 추가 |
  | 30-50% | MODERATE | 다른 모델 시도 (Music2MIDI↔Pop2Piano 교차) |
  | < 30% | POOR | Hybrid (Demucs+Transcription) 또는 PiCoGen2 검토 |

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
      1. Task 9 결과 분석
      2. 결정 매트릭스 적용
      3. 사용자에게 보고
    Expected Result: 명확한 결과 + 다음 단계 권장
  ```

  **Commit**: YES
  - Message: `docs: complete arrangement engine v3 evaluation and next steps`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 0 | `spike(core): [GO/NO-GO message]` | notepads/, (branch merge/delete) | 판정 기록 |
| 1 | `test(golden): add MIDI reference files` | golden/data/*/reference*.mid | ls + pretty_midi |
| 2 | `feat(core): [model] integration` | audio_to_midi.py, requirements.txt | 3곡 MIDI |
| 3 | `feat(core): optimize Pop2Piano composer` (NO-GO만) | audio_to_midi.py | 스타일 비교 |
| 4 | `feat(core): replace comparison with mir_eval+DTW` | musicxml_comparator.py | self-compare |
| 5 | `feat(core): add polyphonic two-hand MusicXML` | midi_to_musicxml.py | 2-staff 확인 |
| 6 | `feat(core): [difficulty approach]` | difficulty_adjuster.py | 3단계 노트 수 |
| 7 | `feat(core): add MIDI direct comparison` | midi_comparator.py | self-compare |
| 8 | `test(golden): add comprehensive MIDI tests` | test_golden.py | pytest 실행 |
| 9 | `docs: evaluation report v3` | notepads/ | 리포트 |
| 10 | `docs: complete evaluation v3` | notepads/ | 상태 업데이트 |

---

## Success Criteria

### Final Checklist
- [ ] Task 0: Music2MIDI 재스파이크 완료 (GO/NO-GO 판정) — Pop2Piano 베이스라인 검증 포함
- [ ] 편곡 모델 8곡 MIDI 생성 성공
- [ ] MIDI 레퍼런스 골든 테스트 통합
- [ ] 비교 알고리즘 mir_eval + DTW 교체
- [ ] 복합 메트릭 출력 (melody_f1, pitch_class_f1, chroma, composite)
- [ ] 양손 피아노 MusicXML 생성
- [ ] 3단계 난이도 생성 (Easy/Medium/Hard)
- [ ] MIDI 직접 비교 모듈
- [ ] 복합 골든 테스트 (MXL + MIDI 원본/쉬운/다장조)
- [ ] 8곡 전체 유사도 리포트
- [ ] 기존 ByteDance(20.31%) 대비 개선 확인
