# 전면 재구축: 보컬 분리 멜로디 추출기

## TL;DR

> **Quick Summary**: 기존 코드 전부 폐기. test/ 폴더의 진짜 데이터만 남기고, 보컬 분리 기반 멜로디 추출 파이프라인을 최소 구조로 처음부터 새로 구축.
>
> **왜 전면 재구축?**:
> - 기존 코드는 가짜 데이터(AI 생성)로 개발됨 — 전부 잘못된 방향
> - 10개 이상의 플랜을 실행했지만 핵심 문제 미해결
> - 불필요한 복잡성 (Docker, WSL, Essentia, difficulty levels, frontend, API 등)
> - 깨끗한 시작이 더 빠르고 정확함
>
> **Deliverables**:
> - 깨끗한 프로젝트 (test/ + 새 코드만)
> - `core/vocal_separator.py` — 보컬 분리
> - `core/pitch_extractor.py` — pitch 추출 + note segmentation
> - `core/reference_extractor.py` — .mxl에서 멜로디 추출
> - `core/comparator.py` — 비교 메트릭
> - `scripts/extract_melody.py` — 단일 곡 멜로디 추출 CLI
> - `scripts/evaluate_all.py` — 8곡 전체 평가
> - `requirements.txt` — 최소 의존성
>
> **Estimated Effort**: Medium (2-3일)
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 0 → Task 1 → Task 2 → Task 3 → Task 4 → Task 6 → Task 7

---

## Context

### Original Request
보컬이 포함된 원곡 MP3에서 멜로디만 추출하여 악보(MusicXML)로 생성. 피아노 편곡 레퍼런스(.mxl)에서 멜로디를 추출해 비교.

### 이전 작업의 문제점
| 문제 | 원인 |
|------|------|
| 가짜 데이터로 테스트 | `backend/tests/golden/data/`는 AI가 생성한 파일 |
| Skyline 실패 | 피아노 아르페지오가 멜로디보다 높아서 최고음≠멜로디 |
| Essentia 실패 | F1 = 0.49%, 완전 무용 |
| 과도한 복잡성 | Docker, WSL, 3단계 난이도, frontend, API, job manager 등 불필요 |
| 10+개 플랜 낭비 | 잘못된 방향에 시간 소모 |

### 진짜 데이터 구조 (test/ 폴더)
```
test/
├── Golden.mp3, Golden.mid, Golden.mxl, Golden 쉬운.mid
├── IRIS OUT.mp3, IRIS OUT.mid, IRIS OUT.mxl, IRIS OUT 쉬운.mid
├── 꿈의 버스.mp3, .mid, .mxl, 쉬운.mid, 다장조.mid
├── 너에게100퍼센트.mp3, .mid, .mxl, 쉬운.mid, 다장조.mid
├── 달리 표현할 수 없어요.mp3, .mid, .mxl, 쉬운.mid, 다장조.mid
├── 등불을 지키다.mp3, .mid, .mxl, 쉬운.mid, 다장조.mid
├── 비비드라라러브.mp3, .mid, .mxl, 쉬운.mid
└── 여름이었다.mp3, .mid, .mxl, 쉬운.mid, 다장조.mid
```

파일 설명:
- `.mp3` = **보컬이 포함된 원곡** (입력)
- `.mxl` = **피아노 편곡 악보** (레퍼런스, 멜로디 + 화음)
- `.mid` = 피아노 편곡 MIDI (레퍼런스)
- `쉬운.mid` = 쉬운 버전 편곡
- `다장조.mid` = 다장조 전조 버전 (일부 곡)

### 새 파이프라인 (Oracle 검증 완료)
```
input.mp3 (보컬 원곡)
  → audio-separator (보컬 분리) → vocal.wav
  → librosa.pyin (monophonic pitch 추출) → f0, voiced
  → note segmentation (voiced mask + median pitch + quantize) → List[Note]
  → MusicXML 생성 (music21) → 멜로디 악보
```

### 기술 스택 결정 (리서치 완료)
| 역할 | 라이브러리 | 이유 |
|------|-----------|------|
| 보컬 분리 | audio-separator[cpu] | Windows 네이티브, UVR 모델, 활발 유지 |
| Pitch 추출 | librosa.pyin | 이미 의존성, monophonic 최적, voiced/unvoiced |
| MIDI 처리 | pretty_midi | 경량, 표준 |
| 악보 생성 | music21 | MusicXML 생성 표준 |
| 비교 | mir_eval | 음악 정보 검색 표준 메트릭 |

### 환경 제약
- Windows 10/11
- CPU only (내장 그래픽카드)
- Python 3.11
- Docker/WSL 없음

---

## Work Objectives

### Core Objective
test/ 폴더의 진짜 데이터를 사용하여, 보컬 분리 기반으로 원곡에서 멜로디를 정확하게 추출하는 최소한의 파이프라인 구축

### Concrete Deliverables
```
piano-sheet-extractor/
├── test/                          # [유지] 원본 데이터
│   ├── cache/                     # [신규] 분리된 보컬 캐시
│   └── *.mp3, *.mid, *.mxl       # [유지] 원본 파일
├── core/                          # [신규] 핵심 로직
│   ├── __init__.py
│   ├── types.py                   # Note dataclass
│   ├── vocal_separator.py         # 보컬 분리
│   ├── pitch_extractor.py         # pitch 추출 + note segmentation
│   ├── reference_extractor.py     # .mxl에서 멜로디 추출
│   ├── comparator.py              # 비교 메트릭
│   └── musicxml_writer.py         # MusicXML 생성
├── scripts/                       # [신규] CLI 스크립트
│   ├── extract_melody.py          # 단일 곡 추출
│   └── evaluate_all.py            # 8곡 전체 평가
├── requirements.txt               # [신규] 최소 의존성
├── .gitignore                     # [신규]
└── README.md                      # [신규] 최소 문서
```

### Definition of Done
- [ ] 기존 코드 전부 삭제됨 (test/ 폴더 제외)
- [ ] 새 프로젝트 구조 생성됨
- [ ] 8곡 모두 보컬 분리 + 멜로디 추출 성공 (노트 > 10)
- [ ] 레퍼런스 대비 pitch_class_f1 측정 완료
- [ ] 평가 결과 JSON 생성

### Must Have
- 보컬 분리 (audio-separator)
- Pitch 추출 (librosa.pyin)
- Pitch → Note 변환
- .mxl에서 레퍼런스 멜로디 추출
- 비교 메트릭 (pitch_class_f1, chroma_similarity)
- 보컬 캐싱 (곡당 2-5분이므로)
- 한글 파일명 + 공백 경로 처리

### Must NOT Have (Guardrails)
- ❌ Docker, WSL
- ❌ Frontend (웹 UI)
- ❌ API 레이어 (FastAPI)
- ❌ Job manager / 비동기 처리
- ❌ 난이도 조절 (Easy/Medium/Hard)
- ❌ 유닛 테스트
- ❌ GPU 가속
- ❌ 불필요한 추상화 계층
- ❌ 이전 코드 재사용 (전부 새로 작성)

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.

### Test Decision
- **Infrastructure exists**: NO (새로 시작)
- **Automated tests**: 평가 스크립트만 (유닛 테스트 없음)
- **Framework**: 없음 — 직접 실행 스크립트

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **파일 삭제/생성** | Bash | ls, dir로 확인 |
| **라이브러리 설치** | Bash | pip install + import 확인 |
| **보컬 분리** | Bash | Python 실행 + 출력 파일 크기 확인 |
| **멜로디 추출** | Bash | 스크립트 실행 + 노트 수 확인 |
| **비교** | Bash | 평가 스크립트 + JSON 검증 |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (정리):
└── Task 0: 기존 코드 전부 삭제 + 새 프로젝트 구조 생성

Wave 1 (기반):
├── Task 1: 의존성 설치 + 환경 설정
├── Task 2: types.py + reference_extractor.py (레퍼런스 추출)
└── Task 3: comparator.py (비교 메트릭)

Wave 2 (핵심):
├── Task 4: vocal_separator.py (보컬 분리)
├── Task 5: pitch_extractor.py (pitch 추출 + note segmentation)
└── Task 6: musicxml_writer.py (MusicXML 생성)

Wave 3 (통합):
├── Task 7: scripts/extract_melody.py (단일 곡 CLI)
├── Task 8: scripts/evaluate_all.py (8곡 평가)
└── Task 9: 8곡 전체 실행 + 결과 분석
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 0 | None | 1, 2, 3 | None |
| 1 | 0 | 4, 5 | 2, 3 |
| 2 | 0 | 8 | 1, 3 |
| 3 | 0 | 8 | 1, 2 |
| 4 | 1 | 7 | 5, 6 |
| 5 | 1 | 7 | 4, 6 |
| 6 | 1 | 7 | 4, 5 |
| 7 | 4, 5, 6 | 9 | 8 |
| 8 | 2, 3 | 9 | 7 |
| 9 | 7, 8 | None | None |

---

## TODOs

### Task 0: 기존 코드 전부 삭제 + 새 프로젝트 구조 생성

**What to do**:
1. test/ 폴더 내 AI 생성물 삭제:
   - `test/spike_music2midi.py` 삭제
   - `test/spike_output.log` 삭제
2. 기존 디렉토리/파일 전부 삭제 (test/ 와 .git/ 제외):
   - `backend/` 전체 삭제
   - `frontend/` 전체 삭제
   - `.sisyphus/` 전체 삭제 (이 계획 파일 실행 후)
   - `.ruff_cache/` 삭제
   - 루트 파일 삭제: `README.md`, `DEPLOYMENT.md`, `docker-compose.yml`, `.gitignore`, `melody_baseline.txt`, `melody_baseline_results.txt`, `song_02_result.txt`, `test_large.mp3`, `test_invalid.txt`, `NUL`
3. 새 프로젝트 구조 생성:
   ```
   core/__init__.py
   scripts/ (빈 디렉토리)
   test/cache/.gitignore (내용: *)
   requirements.txt
   .gitignore
   ```
4. `.gitignore` 생성:
   ```
   __pycache__/
   *.pyc
   .venv/
   venv/
   test/cache/
   *.egg-info/
   dist/
   build/
   .ruff_cache/
   results/
   ```
5. `requirements.txt` 생성:
   ```
   audio-separator[cpu]
   librosa>=0.10.0
   pretty-midi>=0.2.10
   music21>=9.1
   mir-eval>=0.7
   numpy>=1.24
   ```

**⚠️ 중요**: `.sisyphus/plans/full-rebuild.md` (이 파일)은 실행 시작 전에 읽어야 하므로, 삭제 순서 주의. 실행 에이전트가 이 플랜을 먼저 읽은 뒤 삭제 진행.

**Must NOT do**:
- test/ 폴더의 .mp3, .mid, .mxl 파일 삭제
- .git/ 삭제
- git history 초기화

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 파일 삭제 + 디렉토리 생성
- **Skills**: [`git-master`]
  - `git-master`: 삭제 커밋 관리

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 0 (순차)
- **Blocks**: Tasks 1, 2, 3
- **Blocked By**: None

**References**:
- 탐색 에이전트 결과: 전체 파일 목록 + KEEP/DELETE 분류
- `test/` 폴더: 8곡 데이터 (보존 대상)

**Acceptance Criteria**:

```
Scenario: 기존 코드 삭제 확인
  Tool: Bash
  Steps:
    1. dir /b → backend 없음 확인
    2. dir /b → frontend 없음 확인
    3. dir /b → .sisyphus 없음 확인
    4. dir test → .mp3, .mid, .mxl 파일들 존재 확인
    5. dir test → spike_music2midi.py 없음 확인
  Expected Result: test/와 .git/만 남음
  Evidence: dir 출력 캡처

Scenario: 새 프로젝트 구조 확인
  Tool: Bash
  Steps:
    1. dir core\__init__.py → 존재
    2. dir requirements.txt → 존재
    3. dir .gitignore → 존재
    4. dir test\cache → 존재
    5. type requirements.txt → audio-separator, librosa, pretty-midi, music21, mir-eval 포함
  Expected Result: 최소 프로젝트 구조 생성됨
```

**Commit**: YES
- Message: `refactor: clean slate — remove all AI-generated code, keep only test data`
- Files: 삭제된 모든 파일 + 새 구조 파일

---

### Task 1: 의존성 설치 + 환경 설정

**What to do**:
1. Python 가상환경 생성: `python -m venv .venv`
2. 가상환경 활성화: `.venv\Scripts\activate`
3. 의존성 설치: `pip install -r requirements.txt`
4. audio-separator 모델 다운로드 확인
5. 각 라이브러리 import 테스트

**Must NOT do**:
- GPU 버전 설치
- 불필요한 패키지 설치

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 패키지 설치
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2, 3)
- **Blocks**: Tasks 4, 5, 6
- **Blocked By**: Task 0

**References**:
- `requirements.txt` — Task 0에서 생성

**Acceptance Criteria**:

```
Scenario: 의존성 설치 확인
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "from audio_separator.separator import Separator; print('audio-separator OK')"
    2. .venv\Scripts\python -c "import librosa; print(f'librosa {librosa.__version__} OK')"
    3. .venv\Scripts\python -c "import pretty_midi; print('pretty_midi OK')"
    4. .venv\Scripts\python -c "import music21; print(f'music21 {music21.__version__} OK')"
    5. .venv\Scripts\python -c "import mir_eval; print('mir_eval OK')"
    6. .venv\Scripts\python -c "import numpy; print(f'numpy {numpy.__version__} OK')"
    7. Assert: 모든 import 성공 (exit code 0)
  Expected Result: 모든 라이브러리 사용 가능
  Evidence: .sisyphus/evidence/task-1-deps.txt (참고: .sisyphus 삭제 후이므로 터미널에 출력만)
```

**Commit**: NO (환경 설정만)

---

### Task 2: types.py + reference_extractor.py

**What to do**:
1. `core/types.py` — 공통 데이터 타입 정의:
   ```python
   from dataclasses import dataclass
   
   @dataclass
   class Note:
       """음표 표현 (초 단위)"""
       pitch: int      # MIDI pitch (0-127, 60=C4)
       onset: float    # 시작 시간 (초)
       duration: float  # 길이 (초)
       velocity: int = 80  # 세기 (0-127)
   ```

2. `core/reference_extractor.py` — .mxl에서 멜로디 추출:
   ```python
   def extract_reference_melody(mxl_path: Path) -> List[Note]:
       """
       피아노 편곡 MXL에서 멜로디(오른손 최고음) 추출.
       
       파이프라인:
       1. music21로 .mxl 파싱
       2. 첫 번째 파트 (오른손/treble) 선택
       3. 각 onset에서 최고음 선택 (skyline)
       4. ChordSymbol 제외
       5. quarterLength → 초 변환 (tempo 기반)
       
       Returns:
           List[Note] — 멜로디 음표 리스트
       """
   ```

**핵심 로직**:
- music21로 .mxl 파싱 → `score.parts[0]` = 오른손 (treble)
- Note: `element.pitch.midi`, Chord: `element.pitches[-1].midi` (최고음)
- `ChordSymbol` (화성 기호) 제외
- BPM 추출: `MetronomeMark` → `seconds_per_quarter = 60 / bpm`
- onset/duration 변환: `quarterLength * seconds_per_quarter`

**Must NOT do**:
- 복잡한 멜로디 추출 알고리즘 (단순 skyline으로 충분)
- 옥타브 정규화 (레퍼런스는 원래 옥타브 유지)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 단순한 데이터 타입 + music21 API 호출
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 3)
- **Blocks**: Task 8
- **Blocked By**: Task 0

**References**:

**Pattern References**:
- music21 Part 접근: `score.parts[0]` = 오른손(treble), `score.parts[1]` = 왼손(bass)
- music21 Note: `element.pitch.midi` → MIDI pitch
- music21 Chord: `element.pitches[-1].midi` → 최고음 (pitches는 낮음→높음 정렬)
- music21 Tempo: `score.flatten().getElementsByClass(music21.tempo.MetronomeMark)`
- music21 ChordSymbol: `isinstance(element, music21.harmony.ChordSymbol)` → 건너뜀

**테스트 데이터**:
- `test/Golden.mxl` — 가장 짧은 ASCII 이름, 테스트용
- `test/달리 표현할 수 없어요.mxl` — 한글 + 공백, 경로 처리 테스트용

**Acceptance Criteria**:

```
Scenario: 8곡 레퍼런스 멜로디 추출
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       import glob
       from core.reference_extractor import extract_reference_melody
       from pathlib import Path
       for f in sorted(glob.glob('test/*.mxl')):
           notes = extract_reference_melody(Path(f))
           pitches = [n.pitch for n in notes]
           print(f'{Path(f).stem}: {len(notes)} notes, pitch {min(pitches)}-{max(pitches)}')
       "
    2. Assert: 8곡 모두 출력됨 (ERROR 없음)
    3. Assert: 각 곡 노트 수 > 10
  Expected Result: 8곡 멜로디 추출 성공
  Evidence: 터미널 출력 캡처

Scenario: 한글 파일명 처리
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       from core.reference_extractor import extract_reference_melody
       from pathlib import Path
       notes = extract_reference_melody(Path('test/달리 표현할 수 없어요.mxl'))
       print(f'OK: {len(notes)} notes')
       "
    2. Assert: 에러 없이 성공
  Expected Result: 한글 + 공백 경로 정상 처리
```

**Commit**: YES
- Message: `feat(core): add types and reference melody extractor`
- Files: `core/types.py`, `core/reference_extractor.py`

---

### Task 3: comparator.py (비교 메트릭)

**What to do**:
1. `core/comparator.py` — 멜로디 비교 메트릭:
   ```python
   def compare_melodies(ref_notes: List[Note], gen_notes: List[Note]) -> dict:
       """
       레퍼런스 멜로디와 생성된 멜로디를 비교.
       
       Returns:
           {
               "pitch_class_f1": float,      # 옥타브 무시 F1 (200ms tolerance)
               "chroma_similarity": float,    # 12-bin chroma cosine similarity
               "melody_f1_strict": float,     # 정확한 pitch F1 (50ms tolerance)
               "melody_f1_lenient": float,    # 느슨한 pitch F1 (200ms tolerance)
               "onset_f1": float,             # onset만 F1 (pitch 무시)
               "note_counts": {"ref": int, "gen": int},
           }
       """
   ```

**핵심 로직**:
- Note → mir_eval 포맷 변환: `intervals = [[onset, onset+duration], ...]`, `pitches_hz = 440 * 2^((midi-69)/12)`
- `mir_eval.transcription.precision_recall_f1_overlap()` — 기본 F1
- pitch_class_f1: 모든 pitch를 `60 + (pitch % 12)`로 정규화 후 비교 (옥타브 무시, **onset_tolerance=0.2**)
- chroma: 12-bin histogram, duration 가중, cosine similarity
- onset_f1: `mir_eval.onset.f_measure(window=0.1)` — 100ms tolerance
- **tolerance 설정 근거** (Oracle 검증): 피아노 편곡 레퍼런스와 보컬 멜로디 간 본질적 차이 존재 → 느슨한 tolerance 필수
  - strict F1: onset 50ms, pitch 50cents (참고용)
  - lenient F1: onset 200ms, pitch 50cents (주요 지표)
  - pitch_class F1: onset 200ms, 옥타브 무시 (핵심 지표)

**Must NOT do**:
- DTW (불필요한 복잡성)
- 새로운 메트릭 발명
- 복잡한 가중 composite score

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: mir_eval API 래핑
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 2)
- **Blocks**: Task 8
- **Blocked By**: Task 0

**References**:

**API References**:
- mir_eval.transcription: `precision_recall_f1_overlap(ref_intervals, ref_pitches_hz, est_intervals, est_pitches_hz, onset_tolerance=0.05, pitch_tolerance=50.0)`
- mir_eval.onset: `f_measure(ref_onsets, est_onsets, window=0.05)` → (f, precision, recall)
- mir_eval.util: `midi_to_hz(midi_pitches)` → Hz 배열

**데이터 변환**:
- Note → intervals: `np.array([[n.onset, n.onset + n.duration] for n in notes])`
- Note → pitches_hz: `mir_eval.util.midi_to_hz(np.array([n.pitch for n in notes]))`
- chroma histogram: `chroma[pitch % 12] += duration`, 정규화

**Acceptance Criteria**:

```
Scenario: 비교 함수 동작 테스트
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       from core.types import Note
       from core.comparator import compare_melodies
       ref = [Note(60, 0.0, 0.5, 80), Note(62, 0.5, 0.5, 80), Note(64, 1.0, 0.5, 80)]
       gen = [Note(60, 0.0, 0.5, 80), Note(62, 0.55, 0.5, 80), Note(65, 1.0, 0.5, 80)]
       result = compare_melodies(ref, gen)
       print(f'pitch_class_f1: {result[\"pitch_class_f1\"]:.3f}')
       print(f'chroma_similarity: {result[\"chroma_similarity\"]:.3f}')
       assert 0.0 <= result['pitch_class_f1'] <= 1.0
       assert 0.0 <= result['chroma_similarity'] <= 1.0
       print('PASS')
       "
    2. Assert: "PASS" 출력
  Expected Result: 비교 함수 정상 작동
```

**Commit**: YES
- Message: `feat(core): add melody comparison metrics`
- Files: `core/comparator.py`

---

### Task 4: vocal_separator.py (보컬 분리)

**What to do**:
1. `core/vocal_separator.py` — 보컬 분리 + 캐싱:
   ```python
   def separate_vocals(mp3_path: Path, cache_dir: Path) -> Path:
       """
       MP3에서 보컬을 분리. 캐시된 결과 있으면 재사용.
       
       Args:
           mp3_path: 원곡 MP3 파일 경로
           cache_dir: 캐시 디렉토리 (test/cache/)
       
       Returns:
           분리된 보컬 WAV 파일 경로
       
       캐시:
           - 키: MP3 파일의 MD5 hash
           - 형식: {cache_dir}/{hash}_vocals.wav
           - 캐시 hit → 분리 건너뜀 (2-5분 절약)
       """
   ```

**핵심 로직**:
- audio-separator Python API 사용 (subprocess 아님):
  ```python
  from audio_separator.separator import Separator
  separator = Separator(output_dir=str(temp_dir))
  separator.load_model()
  output_files = separator.separate(str(mp3_path))
  # output_files에서 vocal 파일 찾기
  ```
- 캐시 키: `hashlib.md5(mp3_path.read_bytes()).hexdigest()` 
  - 한글 파일명 문제 회피 (hash는 항상 ASCII)
- 캐시 hit/miss 로깅
- 분리된 vocal 파일 찾기: output에서 "vocal" 또는 "Vocals" 이름 포함 파일

**⚠️ 한글 파일명 처리**:
- `test/달리 표현할 수 없어요.mp3` 같은 경로
- audio-separator에 `str(mp3_path)` 전달
- 출력은 `cache_dir/{hash}_vocals.wav`로 저장 (ASCII 파일명)

**Must NOT do**:
- CLI subprocess로 audio-separator 호출
- GPU 모드 사용
- 모델 선택 옵션 추가 (기본 모델 사용)

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: 외부 라이브러리 통합, 캐싱 구현
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 5, 6)
- **Blocks**: Task 7
- **Blocked By**: Task 1

**References**:

**API References**:
- audio-separator: `from audio_separator.separator import Separator`
  - `Separator(output_dir=str)` — 출력 디렉토리 지정
  - `.load_model()` — 기본 모델 로드 (자동 다운로드)
  - `.separate(input_path: str)` — 분리 실행, 파일 경로 리스트 반환
- hashlib: `hashlib.md5(data).hexdigest()` — 캐시 키 생성

**Acceptance Criteria**:

```
Scenario: 보컬 분리 성공 (Golden.mp3)
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       from pathlib import Path
       from core.vocal_separator import separate_vocals
       vocal = separate_vocals(Path('test/Golden.mp3'), Path('test/cache'))
       print(f'Vocal: {vocal}')
       print(f'Size: {vocal.stat().st_size} bytes')
       assert vocal.exists() and vocal.stat().st_size > 10000
       print('PASS')
       "
    2. Assert: "PASS" 출력
  Expected Result: 보컬 WAV 생성 (>10KB)

Scenario: 캐시 재사용 (두 번째 실행 빠름)
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       import time
       from pathlib import Path
       from core.vocal_separator import separate_vocals
       t = time.time()
       vocal = separate_vocals(Path('test/Golden.mp3'), Path('test/cache'))
       elapsed = time.time() - t
       print(f'Cached: {elapsed:.1f}s')
       assert elapsed < 5, f'Too slow: {elapsed:.1f}s'
       print('PASS')
       "
    2. Assert: elapsed < 5초 (캐시 히트)
  Expected Result: 캐시 정상 작동

Scenario: 한글 파일명 처리
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       from pathlib import Path
       from core.vocal_separator import separate_vocals
       vocal = separate_vocals(Path('test/달리 표현할 수 없어요.mp3'), Path('test/cache'))
       assert vocal.exists()
       print('Korean path PASS')
       "
    2. Assert: "Korean path PASS" 출력
  Expected Result: 한글 + 공백 경로 정상 처리
```

**Commit**: YES
- Message: `feat(core): add vocal separator with caching`
- Files: `core/vocal_separator.py`

---

### Task 5: pitch_extractor.py (pitch 추출 + note segmentation)

**What to do**:
1. `core/pitch_extractor.py` — vocal WAV에서 멜로디 Note 추출:
   ```python
   def extract_melody_from_vocal(vocal_path: Path) -> List[Note]:
       """
       분리된 보컬 오디오에서 멜로디 음표 추출.
       
       파이프라인:
       1. librosa로 오디오 로드
       2. librosa.pyin으로 pitch + voiced 추출
       3. voiced 구간에서 연속 프레임 → Note 변환
       4. 짧은 음표 제거 (< 50ms)
       
       Returns:
           List[Note] — 멜로디 음표 리스트
       """
   ```

**핵심 로직** (Oracle 검증 반영 — 음 누락 방지 파라미터):
- `librosa.load(vocal_path, sr=22050)` — 표준 sample rate
- `librosa.pyin(y, fmin=75.0, fmax=1500.0, sr=22050, hop_length=256, frame_length=2048)` 
  - **fmin=75 Hz (D2)**: 남성 저음 커버 (기존 C3=130.8은 너무 높음)
  - **fmax=1500 Hz (F#6)**: K-pop 고음 벨팅 커버 (기존 C6=1046.5는 부족)
  - **hop_length=256**: 더 세밀한 시간 해상도 (~11.6ms, 기존 23ms의 절반). 빠른 멜리스마 캡처
  - **frame_length=2048**: 안정적 pitch 추정
  - 반환: `(f0, voiced_flag, voiced_probs)`
  - `f0` = Hz (NaN = unvoiced)
  - `voiced_flag` = bool 배열
  - `voiced_probs` = voicing 확률 (0~1)
- **Voiced probability gating**: `voiced_probs >= 0.7`인 프레임만 유효 (artifacts 억제)
- Note segmentation:
  1. `voiced_probs >= 0.7`인 연속 프레임 그룹핑
  2. **Gap bridging**: 40ms 이하의 짧은 unvoiced 구간은 무시하고 노트 이어붙이기 (숨쉬기로 인한 불필요한 분리 방지)
  3. 각 그룹의 pitch = median(f0 값들, log-frequency 도메인) → nearest MIDI note
  4. onset = 그룹 시작 프레임 × hop_length / sr
  5. duration = 그룹 길이 × hop_length / sr
  6. Hz → MIDI: `round(12 * log2(hz / 440) + 69)`
  7. min_duration < 0.03초인 노트 제거 (기존 50ms → **30ms로 하향**, 그레이스 노트 보존)
  8. MIDI 21-108 범위 외 노트 제거

**Oracle 음 누락 분석 TOP 5** (반영됨):
1. 보컬 분리 시 백킹 보컬/악기 간섭 → 캐시 후 수동 확인 가능
2. pyin 범위 부족 (남성 저음, 여성 고음) → **fmin=75Hz, fmax=1500Hz로 확대**
3. 숨쉬기로 인한 노트 분리 → **gap bridging 40ms**
4. 그레이스 노트 손실 → **min_duration 30ms로 하향**
5. 피아노 편곡 vs 보컬 차이 → 비교 시 onset tolerance 200ms, pitch class (옥타브 무시) 사용

**현실적 F1 기대치** (Oracle 평가):
- 깨끗한 멜로디 구간: 0.65-0.80
- 곡 전체 (랩, 이펙트 포함): **0.45-0.65**
- 피아노 편곡 레퍼런스와의 차이가 가장 큰 패널티 요인

**Must NOT do**:
- 옥타브 정규화 (보컬 pitch는 실제 옥타브)
- torchcrepe 사용 (pyin 먼저, 부족하면 Task 9에서 추가)

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: 신호 처리 + note segmentation 알고리즘
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 4, 6)
- **Blocks**: Task 7
- **Blocked By**: Task 1

**References**:

**API References**:
- `librosa.load(path, sr=22050)` → `(y, sr)` — 오디오 로드
- `librosa.pyin(y, fmin=130.8, fmax=1046.5, sr=22050, hop_length=512)` → `(f0, voiced_flag, voiced_probs)`
  - `hop_length=512` → 프레임 간격 = 512/22050 ≈ 0.023초
  - `f0` shape: (n_frames,), Hz 단위, NaN=unvoiced
  - `voiced_flag` shape: (n_frames,), bool
- Hz → MIDI: `round(12 * log2(hz / 440) + 69)`
- numpy: `np.nanmedian()` — NaN 무시 median

**Note segmentation 상세 알고리즘**:
```
for each contiguous group of voiced frames:
    pitches_hz = f0[start:end] (NaN 제외)
    median_hz = np.nanmedian(pitches_hz)
    midi_note = round(12 * log2(median_hz / 440) + 69)
    onset_sec = start * hop_length / sr
    duration_sec = (end - start) * hop_length / sr
    if duration_sec >= 0.05 and 21 <= midi_note <= 108:
        notes.append(Note(midi_note, onset_sec, duration_sec, 80))
```

**Acceptance Criteria**:

```
Scenario: 보컬에서 멜로디 추출 (Golden)
  Tool: Bash
  Preconditions: Task 4 완료, test/cache/에 Golden 보컬 있음
  Steps:
    1. .venv\Scripts\python -c "
       from pathlib import Path
       from core.vocal_separator import separate_vocals
       from core.pitch_extractor import extract_melody_from_vocal
       vocal = separate_vocals(Path('test/Golden.mp3'), Path('test/cache'))
       notes = extract_melody_from_vocal(vocal)
       pitches = [n.pitch for n in notes]
       print(f'Notes: {len(notes)}')
       print(f'Pitch: {min(pitches)}-{max(pitches)}')
       print(f'Duration: {notes[-1].onset + notes[-1].duration:.1f}s')
       assert len(notes) > 10
       print('PASS')
       "
    2. Assert: "PASS" 출력
    3. Assert: Notes > 10
  Expected Result: 멜로디 노트 추출 성공

Scenario: 노트 범위 합리성 확인
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       from pathlib import Path
       from core.vocal_separator import separate_vocals
       from core.pitch_extractor import extract_melody_from_vocal
       vocal = separate_vocals(Path('test/Golden.mp3'), Path('test/cache'))
       notes = extract_melody_from_vocal(vocal)
       pitches = [n.pitch for n in notes]
       durations = [n.duration for n in notes]
       # 보컬 멜로디는 보통 C3(48) ~ C6(84) 범위
       assert min(pitches) >= 36, f'Too low: {min(pitches)}'
       assert max(pitches) <= 96, f'Too high: {max(pitches)}'
       assert min(durations) >= 0.05, f'Too short: {min(durations)}'
       print(f'Range OK: MIDI {min(pitches)}-{max(pitches)}')
       print('PASS')
       "
    2. Assert: "PASS" 출력
  Expected Result: 합리적인 pitch 및 duration 범위
```

**Commit**: YES
- Message: `feat(core): add pitch extractor with pyin and note segmentation`
- Files: `core/pitch_extractor.py`

---

### Task 6: musicxml_writer.py (MusicXML 생성)

**What to do**:
1. `core/musicxml_writer.py` — Note 리스트를 MusicXML로 변환:
   ```python
   def notes_to_musicxml(notes: List[Note], 
                          title: str = "Melody",
                          bpm: float = 120.0) -> str:
       """
       Note 리스트를 MusicXML 문자열로 변환.
       
       Args:
           notes: 멜로디 음표 리스트
           title: 곡 제목
           bpm: 템포
       
       Returns:
           MusicXML 문자열
       """
   
   def save_musicxml(notes: List[Note], 
                      output_path: Path,
                      title: str = "Melody",
                      bpm: float = 120.0) -> Path:
       """MusicXML 파일 저장."""
   ```

**핵심 로직**:
- music21로 Score 생성
- 단일 Part (treble clef, 멜로디만)
- Note 리스트 → music21 Note 객체 변환
  - onset/duration: 초 → quarterLength (`seconds * bpm / 60`)
  - 16분음표 단위로 quantize (`round(ql * 4) / 4`)
- `makeMeasures()` → `makeNotation()` → `makeRests()`
- `.write('musicxml')` 또는 `.write('xml')`로 출력

**Must NOT do**:
- 2-staff (양손) 악보 생성 (멜로디만, 단일 파트)
- 난이도 조절
- 복잡한 quantization

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: music21 API 활용, quantization 처리
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 4, 5)
- **Blocks**: Task 7
- **Blocked By**: Task 1

**References**:

**API References**:
- music21 Score/Part 생성:
  ```python
  score = music21.stream.Score()
  part = music21.stream.Part()
  part.append(music21.clef.TrebleClef())
  part.append(music21.tempo.MetronomeMark(number=bpm))
  part.append(music21.meter.TimeSignature('4/4'))
  ```
- music21 Note: `music21.note.Note(pitch=midi_pitch, quarterLength=ql)`
  - `note.offset = onset_ql`
- `part.makeMeasures(inPlace=True)` — 마디 생성
- `score.write('musicxml', fp=str(output_path))` — 파일 저장

**Acceptance Criteria**:

```
Scenario: MusicXML 생성 + 검증
  Tool: Bash
  Steps:
    1. .venv\Scripts\python -c "
       from core.types import Note
       from core.musicxml_writer import save_musicxml
       from pathlib import Path
       notes = [Note(60, 0.0, 0.5, 80), Note(62, 0.5, 0.5, 80), Note(64, 1.0, 1.0, 80)]
       out = save_musicxml(notes, Path('test_output.musicxml'), title='Test', bpm=120)
       content = out.read_text(encoding='utf-8')
       assert '<pitch>' in content
       assert '<score-partwise' in content
       print(f'MusicXML generated: {out.stat().st_size} bytes')
       import os; os.remove(str(out))
       print('PASS')
       "
    2. Assert: "PASS" 출력
  Expected Result: 유효한 MusicXML 생성
```

**Commit**: YES
- Message: `feat(core): add MusicXML melody writer`
- Files: `core/musicxml_writer.py`

---

### Task 7: scripts/extract_melody.py (단일 곡 CLI)

**What to do**:
1. 단일 곡에 대해 전체 파이프라인 실행하는 CLI:
   ```
   python scripts/extract_melody.py test/Golden.mp3 --output output/Golden.musicxml --cache-dir test/cache
   ```
2. 단계별 처리 시간 로깅
3. 결과 요약 출력 (노트 수, 피치 범위, 처리 시간)

**Must NOT do**:
- argparse 외 CLI 프레임워크 사용
- 복잡한 옵션 추가

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 기존 모듈 조합 + argparse
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 3 (with Task 8)
- **Blocks**: Task 9
- **Blocked By**: Tasks 4, 5, 6

**References**:
- `core/vocal_separator.py` — `separate_vocals()`
- `core/pitch_extractor.py` — `extract_melody_from_vocal()`
- `core/musicxml_writer.py` — `save_musicxml()`

**Acceptance Criteria**:

```
Scenario: Golden.mp3 전체 파이프라인
  Tool: Bash
  Steps:
    1. .venv\Scripts\python scripts/extract_melody.py test/Golden.mp3 --output output/Golden.musicxml --cache-dir test/cache
    2. Assert: output/Golden.musicxml 생성됨
    3. Assert: 처리 시간, 노트 수 출력됨
  Expected Result: MusicXML 파일 생성 성공

Scenario: 한글 파일명
  Tool: Bash
  Steps:
    1. .venv\Scripts\python scripts/extract_melody.py "test/달리 표현할 수 없어요.mp3" --output "output/달리 표현할 수 없어요.musicxml" --cache-dir test/cache
    2. Assert: 출력 파일 생성됨
  Expected Result: 한글 경로 정상 처리
```

**Commit**: YES
- Message: `feat(scripts): add single-song melody extraction CLI`
- Files: `scripts/extract_melody.py`

---

### Task 8: scripts/evaluate_all.py (8곡 평가)

**What to do**:
1. 8곡 모두에 대해 파이프라인 실행 + 레퍼런스 비교:
   ```
   python scripts/evaluate_all.py --input-dir test --cache-dir test/cache --output results/evaluation.json
   ```
2. 각 곡: extract_vocal_melody → compare_melodies(ref, gen)
3. 결과: JSON + 터미널 테이블

   출력 형식:
   ```json
   {
     "summary": {
       "total_songs": 8,
       "avg_pitch_class_f1": 0.XX,
       "avg_chroma_similarity": 0.XX
     },
     "songs": {
       "Golden": { "pitch_class_f1": 0.XX, ... },
       ...
     }
   }
   ```

4. 터미널 테이블:
   ```
   Song                           | pc_f1  | chroma | ref_notes | gen_notes | time
   Golden                         | 0.XXX  | 0.XXX  |       NNN |       NNN | XX.Xs
   ...
   AVERAGE                        | 0.XXX  | 0.XXX  |           |           |
   ```

**Must NOT do**:
- 외부 테이블 라이브러리 사용 (f-string으로 충분)
- 실패한 곡 건너뛰기 (에러 발생 시 메시지와 함께 기록)

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: 기존 모듈 조합 + 결과 포맷팅
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 3 (with Task 7)
- **Blocks**: Task 9
- **Blocked By**: Tasks 2, 3

**References**:
- `core/vocal_separator.py` — `separate_vocals()`
- `core/pitch_extractor.py` — `extract_melody_from_vocal()`
- `core/reference_extractor.py` — `extract_reference_melody()`
- `core/comparator.py` — `compare_melodies()`
- `test/*.mp3` + `test/*.mxl` — 매칭: 같은 stem 이름

**Acceptance Criteria**:

```
Scenario: 8곡 전체 평가
  Tool: Bash
  Steps:
    1. .venv\Scripts\python scripts/evaluate_all.py --input-dir test --cache-dir test/cache --output results/evaluation.json
    2. Assert: results/evaluation.json 생성됨
    3. Assert: JSON에 8곡 데이터
    4. .venv\Scripts\python -c "
       import json
       d = json.load(open('results/evaluation.json'))
       assert d['summary']['total_songs'] == 8
       for name, song in d['songs'].items():
           assert 'pitch_class_f1' in song
           assert song['note_counts']['gen'] > 0
       print('Schema OK')
       "
    5. Assert: "Schema OK" 출력
  Expected Result: 8곡 평가 완료
```

**Commit**: YES
- Message: `feat(scripts): add 8-song evaluation script`
- Files: `scripts/evaluate_all.py`

---

### Task 9: 8곡 전체 실행 + 결과 분석

**What to do**:
1. evaluate_all.py 실행하여 8곡 결과 수집
2. 결과 분석:
   - 평균 pitch_class_f1
   - 곡별 분포
   - 노트 수 비율 (gen/ref)
3. 결과가 낮으면 (avg pitch_class_f1 < 0.20):
   - pyin 파라미터 조정 시도
   - 보컬 분리 모델 변경 시도
   - torchcrepe 대안 테스트
4. 결과 저장 + 커밋

**Must NOT do**:
- 자동 튜닝 (수동 분석 후 결정)
- 레퍼런스 추출 방식 변경

**Recommended Agent Profile**:
- **Category**: `deep`
  - Reason: 결과 분석, 문제 진단, 파라미터 튜닝
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3 (sequential)
- **Blocks**: None (최종)
- **Blocked By**: Tasks 7, 8

**References**:
- Task 8 결과: `results/evaluation.json`
- librosa.pyin 파라미터: fmin, fmax, frame_length, hop_length
- audio-separator 모델 목록: `audio-separator --list_models`

**Acceptance Criteria**:

```
Scenario: 최종 결과 확인
  Tool: Bash
  Steps:
    1. .venv\Scripts\python scripts/evaluate_all.py --input-dir test --cache-dir test/cache --output results/evaluation.json
    2. .venv\Scripts\python -c "
       import json
       d = json.load(open('results/evaluation.json'))
       print(f'=== FINAL RESULTS ===')
       print(f'Songs: {d[\"summary\"][\"total_songs\"]}')
       print(f'Avg pitch_class_f1: {d[\"summary\"][\"avg_pitch_class_f1\"]:.3f}')
       print(f'Avg chroma_similarity: {d[\"summary\"][\"avg_chroma_similarity\"]:.3f}')
       "
  Expected Result: 정량적 결과 확인

Scenario: 결과 분석 후 판단
  Tool: Bash
  Steps:
    1. 결과 JSON 분석
    2. pitch_class_f1 < 0.20인 곡 식별
    3. 문제 원인 분석 (보컬 분리 품질? pyin 정확도?)
    4. 필요시 파라미터 조정 후 재실행
  Expected Result: 품질 판단 + 개선 방향 도출
```

**Commit**: YES
- Message: `feat(results): add final evaluation results for 8 test songs`
- Files: `results/evaluation.json`

---

## Commit Strategy

| After Task | Message | Files |
|------------|---------|-------|
| 0 | `refactor: clean slate — remove all AI-generated code, keep only test data` | 삭제 + 새 구조 |
| 2 | `feat(core): add types and reference melody extractor` | types.py, reference_extractor.py |
| 3 | `feat(core): add melody comparison metrics` | comparator.py |
| 4 | `feat(core): add vocal separator with caching` | vocal_separator.py |
| 5 | `feat(core): add pitch extractor with pyin` | pitch_extractor.py |
| 6 | `feat(core): add MusicXML melody writer` | musicxml_writer.py |
| 7 | `feat(scripts): add single-song melody extraction CLI` | extract_melody.py |
| 8 | `feat(scripts): add 8-song evaluation script` | evaluate_all.py |
| 9 | `feat(results): add final evaluation results` | evaluation.json |

---

## Success Criteria

### Verification Commands
```bash
# 1. 프로젝트 구조 확인
dir /b  # core/, scripts/, test/, requirements.txt, .gitignore

# 2. 단일 곡 파이프라인
.venv\Scripts\python scripts\extract_melody.py test\Golden.mp3 --output output\Golden.musicxml --cache-dir test\cache

# 3. 8곡 평가
.venv\Scripts\python scripts\evaluate_all.py --input-dir test --cache-dir test\cache --output results\evaluation.json

# 4. 결과 확인
.venv\Scripts\python -c "import json; d=json.load(open('results/evaluation.json')); print(f'Avg pc_f1: {d[\"summary\"][\"avg_pitch_class_f1\"]:.3f}')"
```

### Final Checklist
- [ ] 기존 코드 전부 삭제됨 (test/ 제외)
- [ ] 새 최소 프로젝트 구조 생성됨
- [ ] 의존성 설치 성공 (audio-separator, librosa, music21, mir-eval, pretty-midi)
- [ ] 8곡 모두 보컬 분리 성공
- [ ] 8곡 모두 멜로디 추출 성공 (노트 > 10)
- [ ] 8곡 레퍼런스 멜로디 추출 성공
- [ ] 비교 메트릭 계산 완료 (pitch_class_f1, chroma_similarity)
- [ ] 평가 결과 JSON 생성
- [ ] 한글 파일명 + 공백 경로 정상 처리
- [ ] MusicXML 악보 생성 가능
