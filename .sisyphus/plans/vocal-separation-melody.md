# 보컬 분리 기반 멜로디 추출 파이프라인

## TL;DR

> **Quick Summary**: 보컬이 포함된 원곡 MP3에서 audio-separator로 보컬을 분리한 뒤, librosa.pyin으로 멜로디 pitch를 추출하여 악보를 생성. 레퍼런스 .mxl에서 추출한 멜로디와 비교하여 품질 측정.
>
> **핵심 변경**:
> - 기존: Basic Pitch (전체 음) → Skyline (최고음=멜로디) → **엉뚱한 멜로디**
> - 신규: audio-separator (보컬 분리) → pyin (vocal pitch) → **정확한 멜로디**
> - 진짜 데이터 사용: `test/` 폴더의 원본 파일 (보컬 원곡 + 피아노 편곡 레퍼런스)
>
> **Deliverables**:
> - `backend/core/vocal_melody_pipeline.py` — 보컬 분리 + pitch 추출 + note segmentation
> - `backend/scripts/run_vocal_pipeline.py` — 단일 곡 테스트 CLI
> - `backend/scripts/compare_melodies.py` — 8곡 전체 비교 스크립트
> - `test/cache/` — 분리된 보컬 캐시 (gitignored)
> - 비교 결과 JSON + 요약 리포트
>
> **Estimated Effort**: Medium (2-3일)
> **Parallel Execution**: YES — 2 waves
> **Critical Path**: Task 0 → Task 1 → Task 2 → Task 3 → Task 5 → Task 6

---

## Context

### Original Request
보컬이 포함된 원곡에서 멜로디만 정확하게 추출하여 악보로 생성. 피아노 편곡 레퍼런스(.mxl)에서 멜로디를 추출해 비교 평가.

### 핵심 발견 (이전 세션에서)
- `test/` 폴더의 .mp3 파일은 **보컬이 포함된 원곡** (AI가 만든 게 아님)
- `backend/tests/golden/data/`는 **AI가 만든 가공물** — 이전 테스트 결과 무의미
- 기존 Skyline 접근법은 본질적으로 틀림 (피아노 아르페지오가 멜로디보다 높음)
- Essentia PredominantPitchMelodia는 이미 실패 검증됨 (F1 = 0.49%)

### Interview Summary
**Key Discussions**:
- 보컬 분리 가능 확인 → audio-separator[cpu] Windows 네이티브 지원
- Docker/WSL 불필요 — 로컬 Python으로 가능
- 레퍼런스 .mxl = 피아노 편곡 (멜로디 + 화음) → treble clef skyline으로 멜로디 추출
- 유닛 테스트 없음, 레퍼런스 비교만
- 난이도 조절 없음, 멜로디만

**Research Findings**:
- audio-separator: pip install "audio-separator[cpu]", UVR 모델, CPU 2-5분/곡
- librosa.pyin: 이미 의존성에 있음, monophonic vocal에 최적, voiced/unvoiced 판별
- `musicxml_melody_extractor.py`: 이미 treble + skyline + filter + normalize 구현됨 — 재사용 가능

### Oracle 권고
- Pipeline A 선택: vocal separation → monophonic pitch (pyin) → MIDI
- pyin 먼저 시도, 정확도 부족 시 torchcrepe 추가
- 레퍼런스: treble + onset별 skyline + smoothing
- 캐싱 필수 (분리 5-15분/곡)
- 1곡 먼저 테스트 후 8곡 확장

### Metis Review
**Identified Gaps** (addressed):
- 한글 파일명 + 공백 경로 처리 → Python API 사용 (CLI subprocess 아님)
- 피아노 편곡 vs 보컬 멜로디 비교 → pitch-class F1 (옥타브 무시) + 200ms onset tolerance
- midi_to_musicxml.py 미커밋 버그 수정 → Task 0에서 먼저 커밋
- audio-separator 모델 다운로드 → 명시적 다운로드 + 검증 단계
- requirements.txt 의존성 충돌 가능 → 설치 시 검증

---

## Work Objectives

### Core Objective
보컬 원곡에서 보컬을 분리하고 pitch를 추출하여, 레퍼런스 피아노 편곡의 멜로디와 비교 가능한 수준의 멜로디 악보를 생성

### Concrete Deliverables
- `backend/core/vocal_melody_pipeline.py` — 메인 파이프라인 모듈
- `backend/scripts/run_vocal_pipeline.py` — 단일 곡 CLI 테스트
- `backend/scripts/compare_melodies.py` — 8곡 비교 스크립트
- `test/cache/.gitignore` — 캐시 디렉토리
- 비교 결과: `backend/results/comparison.json`

### Definition of Done
- [ ] 8곡 모두에서 보컬 분리 + 멜로디 추출 성공 (노트 수 > 10)
- [ ] 레퍼런스 대비 pitch_class_f1 평균 ≥ 0.30 (옥타브 무시, 200ms tolerance)
- [ ] 비교 결과 JSON 생성 (8곡 모두 포함)
- [ ] 기존 코드 변경 없음 (새 모듈만 추가)

### Must Have
- 보컬 분리 (audio-separator)
- Pitch 추출 (librosa.pyin)
- Pitch → Note 변환 (segmentation)
- 레퍼런스 멜로디 추출 (기존 `musicxml_melody_extractor.py` 재사용)
- 비교 메트릭 (기존 `comparison_utils.py` 재사용)
- 보컬 캐싱

### Must NOT Have (Guardrails)
- ❌ 기존 `melody_extractor.py`, `audio_to_midi.py`, `musicxml_melody_extractor.py` 수정 금지
- ❌ API 레이어 (`backend/api/`), job_manager, difficulty_adjuster 수정 금지
- ❌ 유닛 테스트 작성 금지 — 비교 스크립트만
- ❌ Docker/WSL 사용 금지
- ❌ GPU 가속 시도 금지
- ❌ `audio-separator[cpu]` 외 추가 의존성 금지 (정당한 사유 없이)
- ❌ 새 비교 메트릭 발명 금지 — 기존 `comparison_utils.py` 사용
- ❌ AI가 만든 `backend/tests/golden/data/` 파일 사용 금지 — `test/` 폴더만 사용

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.

### Test Decision
- **Infrastructure exists**: YES (pytest, comparison_utils)
- **Automated tests**: 비교 스크립트만 (유닛 테스트 없음)
- **Framework**: 직접 실행 스크립트

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **라이브러리 설치** | Bash | pip install + import 확인 |
| **보컬 분리** | Bash | Python 스크립트 실행 + 출력 파일 확인 |
| **멜로디 추출** | Bash | 파이프라인 실행 + 노트 수 확인 |
| **비교** | Bash | 비교 스크립트 실행 + JSON 출력 검증 |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (사전 정리):
└── Task 0: midi_to_musicxml.py 버그 수정 커밋

Wave 1 (Start Immediately after Wave 0):
├── Task 1: 로컬 환경 설정 + audio-separator 설치
└── Task 2: 레퍼런스 멜로디 추출 검증 (기존 모듈)

Wave 2 (After Wave 1):
├── Task 3: vocal_melody_pipeline.py 구현 (1곡 테스트)
└── Task 4: 비교 스크립트 구현

Wave 3 (After Wave 2):
├── Task 5: 8곡 전체 테스트 + 결과 분석
└── Task 6: 품질 개선 (필요시)

Critical Path: Task 0 → Task 1 → Task 3 → Task 5 → Task 6
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 0 | None | 1, 2 | None |
| 1 | 0 | 3 | 2 |
| 2 | 0 | 4 | 1 |
| 3 | 1 | 5 | 4 |
| 4 | 2 | 5 | 3 |
| 5 | 3, 4 | 6 | None |
| 6 | 5 (조건부) | None | None |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 0 | 0 | quick + git-master |
| 1 | 1, 2 | quick (설치), quick (검증) |
| 2 | 3, 4 | unspecified-high (파이프라인), unspecified-low (스크립트) |
| 3 | 5, 6 | unspecified-low (테스트), deep (튜닝) |

---

## TODOs

### Task 0: midi_to_musicxml.py 버그 수정 커밋

**What to do**:
1. `backend/core/midi_to_musicxml.py`의 미커밋 버그 수정을 커밋
2. 이 수정은 `stream.flatten().notes`가 Part 구조를 파괴하던 버그를 수정한 것
3. 커밋 후 깨끗한 상태에서 새 작업 시작

**Must NOT do**:
- 다른 파일 변경
- 이 커밋에 새 기능 포함

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 단순 git 커밋 작업
- **Skills**: [`git-master`]
  - `git-master`: git 커밋 작업에 필수

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 0 (순차)
- **Blocks**: Tasks 1, 2
- **Blocked By**: None

**References**:
- `backend/core/midi_to_musicxml.py` — 현재 미커밋 수정 사항
- 버그: `stream.flatten().notes`가 Score의 Part 구조를 파괴함
- 수정: 각 Part를 개별적으로 `part.makeMeasures(inPlace=True)` 처리

**Acceptance Criteria**:

```
Scenario: 버그 수정 커밋 확인
  Tool: Bash
  Steps:
    1. git status → backend/core/midi_to_musicxml.py가 modified 상태 확인
    2. git add backend/core/midi_to_musicxml.py
    3. git commit -m "fix(musicxml): preserve Part structure in stream_to_musicxml"
    4. git log -1 --oneline → 커밋 메시지 확인
    5. git status → 해당 파일이 clean 상태
  Expected Result: 커밋 성공, working tree clean
  Evidence: git log 출력

Scenario: 다른 미커밋 변경 정리
  Tool: Bash
  Steps:
    1. git status → 나머지 미커밋 파일 확인
    2. 새 작업과 무관한 파일들은 적절히 커밋 또는 stash
  Expected Result: clean working tree로 새 작업 시작 가능
```

**Commit**: YES
- Message: `fix(musicxml): preserve Part structure in stream_to_musicxml`
- Files: `backend/core/midi_to_musicxml.py`

---

### Task 1: 로컬 환경 설정 + audio-separator 설치

**What to do**:
1. 로컬 Python 가상환경 확인 또는 생성 (backend/.venv)
2. `audio-separator[cpu]` 설치:
   ```bash
   pip install "audio-separator[cpu]"
   ```
3. 기존 의존성과 충돌 없는지 확인 (특히 torch 버전)
4. audio-separator 모델 다운로드 검증:
   ```python
   from audio_separator.separator import Separator
   separator = Separator()
   # 모델 목록 확인
   ```
5. `test/cache/` 디렉토리 생성 + `.gitignore` 추가
6. requirements.txt 업데이트 (audio-separator[cpu] 추가)

**Must NOT do**:
- GPU 버전 설치
- Docker 사용
- 기존 코드 수정

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 패키지 설치 + 환경 확인
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Task 2)
- **Blocks**: Task 3
- **Blocked By**: Task 0

**References**:
- `backend/requirements.txt` — 현재 의존성 목록
- audio-separator 공식 문서: https://github.com/karaokenerds/python-audio-separator
- 기존 torch 버전: `torch>=2.2.0` in requirements.txt

**Acceptance Criteria**:

```
Scenario: audio-separator 설치 검증
  Tool: Bash
  Preconditions: Python 가상환경 활성화됨
  Steps:
    1. pip install "audio-separator[cpu]"
    2. python -c "from audio_separator.separator import Separator; print('import OK')"
    3. Assert: "import OK" 출력, exit code 0
  Expected Result: audio-separator import 성공
  Evidence: .sisyphus/evidence/task-1-install.txt

Scenario: torch 버전 충돌 없음
  Tool: Bash
  Steps:
    1. python -c "import torch; print(f'torch {torch.__version__}')"
    2. python -c "import librosa; print(f'librosa {librosa.__version__}')"
    3. python -c "import music21; print(f'music21 {music21.__version__}')"
    4. Assert: 모든 import 성공
  Expected Result: 기존 라이브러리 정상 작동
  Evidence: 버전 출력 캡처

Scenario: 캐시 디렉토리 생성
  Tool: Bash
  Steps:
    1. mkdir test\cache (없으면 생성)
    2. test\cache\.gitignore 생성 (내용: *)
    3. Assert: 디렉토리 존재
  Expected Result: 캐시 디렉토리 준비 완료

Scenario: 테스트 곡으로 보컬 분리 테스트 (Golden.mp3)
  Tool: Bash
  Steps:
    1. python -c "
       from audio_separator.separator import Separator
       sep = Separator(output_dir='test/cache')
       sep.load_model()
       result = sep.separate('test/Golden.mp3')
       print(f'Output files: {result}')
       "
    2. Assert: test/cache/ 에 vocal 파일 생성됨
    3. Assert: 파일 크기 > 10KB
  Expected Result: 보컬 분리 성공
  Evidence: .sisyphus/evidence/task-1-separation.txt
```

**Commit**: YES
- Message: `feat(deps): add audio-separator for vocal separation pipeline`
- Files: `backend/requirements.txt`, `test/cache/.gitignore`

---

### Task 2: 레퍼런스 멜로디 추출 검증

**What to do**:
1. 기존 `musicxml_melody_extractor.py`로 `test/` 폴더의 .mxl 파일에서 멜로디 추출 테스트
2. 8곡 모두 테스트하여 추출되는 노트 수, 피치 범위 확인
3. 한글 파일명 + 공백 경로 처리 확인
4. 결과를 로그로 기록

**주의**: 한글 파일명에 공백이 포함됨 (예: `달리 표현할 수 없어요.mxl`).
- Path 객체 사용 필수
- subprocess 대신 Python API 직접 호출

**Must NOT do**:
- musicxml_melody_extractor.py 수정
- 새 비교 메트릭 추가

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 기존 모듈 검증만
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Task 1)
- **Blocks**: Task 4
- **Blocked By**: Task 0

**References**:
- `backend/core/musicxml_melody_extractor.py` — 이미 구현된 treble + skyline + filter + normalize
- `backend/core/musicxml_melody_extractor.py:182` — `extract_melody_from_musicxml(filepath: str)` 함수
- `backend/core/midi_parser.py:14-21` — Note dataclass (pitch, onset, duration, velocity)
- `test/*.mxl` — 8곡 레퍼런스 파일

**Acceptance Criteria**:

```
Scenario: 8곡 레퍼런스 멜로디 추출
  Tool: Bash
  Preconditions: 가상환경 활성화, music21 설치됨
  Steps:
    1. cd backend && python -c "
       import glob
       from core.musicxml_melody_extractor import extract_melody_from_musicxml
       mxl_files = glob.glob('../test/*.mxl')
       for f in sorted(mxl_files):
           try:
               notes = extract_melody_from_musicxml(f)
               pitches = [n.pitch for n in notes]
               print(f'{f}: {len(notes)} notes, pitch {min(pitches)}-{max(pitches)}')
           except Exception as e:
               print(f'{f}: ERROR - {e}')
       "
    2. Assert: 8곡 모두 "notes" 출력 (ERROR 없음)
    3. Assert: 각 곡 노트 수 > 10
  Expected Result: 8곡 모두 멜로디 추출 성공
  Evidence: .sisyphus/evidence/task-2-reference-extraction.txt

Scenario: 한글 파일명 경로 처리 확인
  Tool: Bash
  Steps:
    1. python -c "
       from core.musicxml_melody_extractor import extract_melody_from_musicxml
       notes = extract_melody_from_musicxml('../test/달리 표현할 수 없어요.mxl')
       print(f'Korean path OK: {len(notes)} notes')
       "
    2. Assert: 에러 없이 노트 추출 성공
  Expected Result: 한글 + 공백 경로 정상 처리
```

**Commit**: NO (검증만)

---

### Task 3: vocal_melody_pipeline.py 구현

**What to do**:
1. `backend/core/vocal_melody_pipeline.py` 신규 생성
2. 구현할 함수들:

```python
# === 모듈 구조 ===

def separate_vocals(mp3_path: Path, cache_dir: Path) -> Path:
    """
    보컬 분리. 캐시된 결과 있으면 재사용.
    
    Args:
        mp3_path: 원곡 MP3 경로
        cache_dir: 캐시 디렉토리 (test/cache/)
    
    Returns:
        분리된 보컬 WAV 파일 경로
    
    캐시 키: mp3 파일의 hash + 모델명
    """

def extract_pitch_with_pyin(vocal_path: Path, 
                              fmin_hz: float = 130.8,  # C3
                              fmax_hz: float = 1046.5  # C6
                              ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    librosa.pyin으로 pitch 추출.
    
    Returns:
        (f0, voiced_flag, voiced_probs) 
        - f0: Hz 단위 pitch (NaN = unvoiced)
        - voiced_flag: bool 배열
        - voiced_probs: voicing probability
    """

def pitch_to_notes(f0: np.ndarray, 
                    voiced_flag: np.ndarray,
                    sr: int, 
                    hop_length: int,
                    min_duration: float = 0.05  # 50ms
                    ) -> List[Note]:
    """
    Pitch contour → Note 리스트 변환.
    
    규칙:
    1. voiced_flag가 True인 연속 프레임을 하나의 노트로 병합
    2. 노트의 pitch = 구간 내 median Hz → nearest MIDI note
    3. min_duration 미만 노트 제거
    4. 피아노 범위 (MIDI 21-108) 필터링
    """

def extract_vocal_melody(mp3_path: Path, 
                          cache_dir: Path
                          ) -> List[Note]:
    """
    메인 파이프라인: MP3 → 보컬 분리 → pitch 추출 → Note 리스트
    
    Pipeline:
    1. separate_vocals() — 보컬 분리 (캐시 활용)
    2. extract_pitch_with_pyin() — pitch 추출
    3. pitch_to_notes() — Note 변환
    4. filter_short_notes() — 짧은 음표 제거 (기존 함수 재사용)
    5. resolve_overlaps() — 오버랩 해결 (기존 함수 재사용)
    
    Returns:
        List[Note] — midi_parser.Note 데이터클래스 리스트
    """
```

3. 1곡(Golden.mp3)으로 end-to-end 테스트
4. 로그로 각 단계별 처리 시간 출력

**Must NOT do**:
- melody_extractor.py 수정
- audio_to_midi.py 수정
- musicxml_melody_extractor.py 수정
- normalize_octave 적용하지 않음 (보컬 pitch는 이미 실제 옥타브)
- subprocess로 CLI 호출 — Python API만 사용

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: 핵심 파이프라인 구현, 여러 라이브러리 통합
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Task 4)
- **Blocks**: Task 5
- **Blocked By**: Task 1

**References**:

**Pattern References** (기존 코드 패턴):
- `backend/core/midi_parser.py:14-21` — Note dataclass 정의 (pitch, onset, duration, velocity). 이 데이터클래스를 반환해야 기존 comparison_utils와 호환됨
- `backend/core/melody_extractor.py` — `filter_short_notes()`, `resolve_overlaps()` 함수 재사용. import하여 후처리에 적용
- `backend/core/musicxml_melody_extractor.py:182-238` — extract_melody_from_musicxml의 파이프라인 구조 참고 (추출 → skyline → filter → resolve → normalize 패턴)

**API References** (사용할 라이브러리):
- audio-separator Python API: `from audio_separator.separator import Separator`
  - `Separator(output_dir=str)` → `load_model()` → `separate(input_path)` → 파일 경로 리스트 반환
- librosa.pyin: `librosa.pyin(y, fmin=, fmax=, sr=)` → `(f0, voiced_flag, voiced_probs)`
  - f0은 Hz 단위, NaN = unvoiced, hop_length 기본값 512

**경로 처리 주의사항**:
- `test/` 폴더의 파일명에 한글 + 공백 포함 (예: `달리 표현할 수 없어요.mp3`)
- audio-separator에 경로 전달 시 str(path) 사용, subprocess 아닌 Python API 직접 호출
- 캐시 파일명: 원본 파일의 MD5 hash 사용 (한글 파일명 문제 회피)

**Acceptance Criteria**:

```
Scenario: Golden.mp3 보컬 분리 성공
  Tool: Bash
  Preconditions: Task 1 완료, audio-separator 설치됨
  Steps:
    1. cd backend && python -c "
       from pathlib import Path
       from core.vocal_melody_pipeline import separate_vocals
       vocal_path = separate_vocals(Path('../test/Golden.mp3'), Path('../test/cache'))
       print(f'Vocal file: {vocal_path}')
       print(f'Size: {vocal_path.stat().st_size} bytes')
       assert vocal_path.exists()
       assert vocal_path.stat().st_size > 10000
       print('PASS')
       "
    2. Assert: "PASS" 출력
  Expected Result: 보컬 WAV 파일 생성 (>10KB)
  Evidence: .sisyphus/evidence/task-3-separation.txt

Scenario: Golden.mp3 전체 파이프라인 (end-to-end)
  Tool: Bash
  Steps:
    1. cd backend && python -c "
       from pathlib import Path
       from core.vocal_melody_pipeline import extract_vocal_melody
       notes = extract_vocal_melody(Path('../test/Golden.mp3'), Path('../test/cache'))
       pitches = [n.pitch for n in notes]
       print(f'Notes: {len(notes)}')
       print(f'Pitch range: {min(pitches)}-{max(pitches)}')
       print(f'Duration: {notes[-1].onset + notes[-1].duration:.1f}s')
       assert len(notes) > 10, f'Too few notes: {len(notes)}'
       print('PASS')
       "
    2. Assert: "PASS" 출력
    3. Assert: Notes > 10
  Expected Result: 멜로디 노트 리스트 생성 성공
  Evidence: .sisyphus/evidence/task-3-pipeline.txt

Scenario: 캐시 재사용 확인 (두 번째 실행이 빠름)
  Tool: Bash
  Steps:
    1. cd backend && python -c "
       import time
       from pathlib import Path
       from core.vocal_melody_pipeline import extract_vocal_melody
       t = time.time()
       notes = extract_vocal_melody(Path('../test/Golden.mp3'), Path('../test/cache'))
       elapsed = time.time() - t
       print(f'Cached run: {elapsed:.1f}s, {len(notes)} notes')
       assert elapsed < 60, f'Too slow for cached run: {elapsed:.1f}s'
       print('PASS')
       "
    2. Assert: elapsed < 60초 (분리 단계 스킵됨)
  Expected Result: 캐시 활용으로 빠른 실행
  Evidence: .sisyphus/evidence/task-3-cache.txt

Scenario: 한글 파일명 처리 확인
  Tool: Bash
  Steps:
    1. cd backend && python -c "
       from pathlib import Path
       from core.vocal_melody_pipeline import extract_vocal_melody
       notes = extract_vocal_melody(Path('../test/달리 표현할 수 없어요.mp3'), Path('../test/cache'))
       print(f'Korean filename OK: {len(notes)} notes')
       assert len(notes) > 10
       print('PASS')
       "
    2. Assert: "PASS" 출력
  Expected Result: 한글 + 공백 경로 정상 처리
```

**Commit**: YES
- Message: `feat(core): add vocal separation melody extraction pipeline`
- Files: `backend/core/vocal_melody_pipeline.py`
- Pre-commit: `cd backend && python -c "from core.vocal_melody_pipeline import extract_vocal_melody; print('import ok')"`

---

### Task 4: 비교 스크립트 구현

**What to do**:
1. `backend/scripts/run_vocal_pipeline.py` — 단일 곡 테스트 CLI
   ```python
   # Usage: python scripts/run_vocal_pipeline.py ../test/Golden.mp3
   # 보컬 분리 → 멜로디 추출 → 노트 정보 출력
   ```

2. `backend/scripts/compare_melodies.py` — 8곡 전체 비교
   ```python
   # Usage: python scripts/compare_melodies.py --input-dir ../test --cache-dir ../test/cache --output results/comparison.json
   
   # 각 곡에 대해:
   # 1. extract_vocal_melody(곡.mp3) → generated melody
   # 2. extract_melody_from_musicxml(곡.mxl) → reference melody  
   # 3. Note → NoteEvent 변환
   # 4. compute_composite_metrics() → 비교
   # 5. 결과를 JSON으로 저장
   
   # Note → NoteEvent 변환:
   # NoteEvent(pitch=note.pitch, onset=note.onset, offset=note.onset + note.duration)
   ```

3. 출력 형식:
   ```json
   {
     "summary": {
       "total_songs": 8,
       "avg_pitch_class_f1": 0.XX,
       "avg_chroma_similarity": 0.XX,
       "avg_composite_score": 0.XX
     },
     "songs": {
       "Golden": {
         "melody_f1": 0.XX,
         "pitch_class_f1": 0.XX,
         "chroma_similarity": 0.XX,
         "composite_score": 0.XX,
         "note_counts": {"ref": N, "gen": M},
         "processing_time_sec": X.X
       },
       ...
     }
   }
   ```
4. 터미널에 사람이 읽기 쉬운 테이블도 출력

**Must NOT do**:
- comparison_utils.py 수정
- 새 메트릭 발명
- musicxml_melody_extractor.py 수정

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: 기존 모듈 조합 + CLI 스크립트
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Task 3)
- **Blocks**: Task 5
- **Blocked By**: Task 2

**References**:

**Pattern References**:
- `backend/core/comparison_utils.py:516-624` — `compute_composite_metrics(ref_notes, gen_notes)` 함수. NoteEvent 리스트를 받아 모든 메트릭을 한번에 계산. 반환값에 melody_f1, pitch_class_f1, chroma_similarity, composite_score, note_counts 포함
- `backend/core/comparison_utils.py:48-67` — NoteEvent dataclass. `pitch: int, onset: float, offset: float`. Note → NoteEvent 변환 필요: `NoteEvent(pitch=n.pitch, onset=n.onset, offset=n.onset + n.duration)`
- `backend/core/musicxml_melody_extractor.py:182` — `extract_melody_from_musicxml(filepath: str) -> List[Note]`

**파일 매칭 로직**:
- `test/` 폴더에서 같은 이름의 .mp3와 .mxl을 매칭
- 예: `Golden.mp3` ↔ `Golden.mxl`
- `glob.glob('../test/*.mp3')` → 확장자 제거 → `{name}.mxl` 존재 확인

**Acceptance Criteria**:

```
Scenario: 단일 곡 테스트 CLI
  Tool: Bash
  Preconditions: Task 3 완료
  Steps:
    1. cd backend && python scripts/run_vocal_pipeline.py ../test/Golden.mp3 --cache-dir ../test/cache
    2. Assert: 노트 수, 피치 범위, 처리 시간 출력됨
  Expected Result: 단일 곡 파이프라인 실행 성공
  Evidence: 터미널 출력 캡처

Scenario: 8곡 비교 스크립트 실행
  Tool: Bash
  Steps:
    1. cd backend && python scripts/compare_melodies.py --input-dir ../test --cache-dir ../test/cache --output results/comparison.json
    2. Assert: results/comparison.json 파일 생성됨
    3. Assert: JSON에 8곡 모두 포함
    4. Assert: 각 곡에 melody_f1, pitch_class_f1, chroma_similarity, composite_score, note_counts 키 존재
  Expected Result: 8곡 비교 완료, JSON 결과 저장
  Evidence: .sisyphus/evidence/task-4-comparison.json

Scenario: 비교 결과 JSON 스키마 검증
  Tool: Bash
  Steps:
    1. cd backend && python -c "
       import json
       d = json.load(open('results/comparison.json'))
       assert 'summary' in d
       assert 'songs' in d
       assert d['summary']['total_songs'] == 8
       song = list(d['songs'].values())[0]
       required = ['melody_f1','pitch_class_f1','chroma_similarity','composite_score','note_counts']
       assert all(k in song for k in required), f'Missing keys: {set(required) - set(song.keys())}'
       print('Schema OK')
       "
    2. Assert: "Schema OK" 출력
  Expected Result: JSON 스키마 정확
```

**Commit**: YES
- Message: `feat(scripts): add vocal melody comparison scripts for 8 test songs`
- Files: `backend/scripts/run_vocal_pipeline.py`, `backend/scripts/compare_melodies.py`

---

### Task 5: 8곡 전체 테스트 + 결과 분석

**What to do**:
1. 8곡 모두에 대해 전체 파이프라인 실행
2. 비교 결과 분석:
   - 곡별 pitch_class_f1 확인
   - 노트 수 비율 (generated/reference) 확인
   - 처리 시간 기록
3. 결과 테이블 생성 + 로그 저장
4. 품질 평가:
   - pitch_class_f1 ≥ 0.30 → 성공
   - pitch_class_f1 < 0.30 → Task 6 진행 필요
5. 결과를 `.sisyphus/evidence/` 에 저장

**Must NOT do**:
- 결과에 따라 코드 자동 수정
- 임계값 조정

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: 스크립트 실행 + 결과 분석
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3 (sequential)
- **Blocks**: Task 6
- **Blocked By**: Tasks 3, 4

**References**:
- Task 4 결과물: `backend/scripts/compare_melodies.py`
- `test/*.mp3` — 8곡 원곡
- `test/*.mxl` — 8곡 레퍼런스

**Acceptance Criteria**:

```
Scenario: 8곡 전체 파이프라인 실행 성공
  Tool: Bash
  Preconditions: Tasks 3, 4 완료
  Steps:
    1. cd backend && python scripts/compare_melodies.py --input-dir ../test --cache-dir ../test/cache --output results/comparison.json
    2. Assert: 8곡 모두 처리됨 (에러 없음)
    3. Assert: results/comparison.json에 8곡 데이터
    4. 결과 복사: cp results/comparison.json ../.sisyphus/evidence/task-5-results.json
  Expected Result: 8곡 모두 성공
  Evidence: .sisyphus/evidence/task-5-results.json

Scenario: 결과 요약 출력
  Tool: Bash
  Steps:
    1. cd backend && python -c "
       import json
       d = json.load(open('results/comparison.json'))
       print(f'=== 8곡 비교 결과 ===')
       print(f'평균 pitch_class_f1: {d[\"summary\"][\"avg_pitch_class_f1\"]:.3f}')
       print(f'평균 chroma_similarity: {d[\"summary\"][\"avg_chroma_similarity\"]:.3f}')
       print(f'평균 composite_score: {d[\"summary\"][\"avg_composite_score\"]:.3f}')
       print()
       for name, song in d['songs'].items():
           pf = song['pitch_class_f1']
           nc = song['note_counts']
           status = 'OK' if pf >= 0.30 else 'LOW'
           print(f'{name:30s} | pc_f1={pf:.3f} | ref={nc[\"ref\"]:4d} gen={nc[\"gen\"]:4d} | {status}')
       "
    2. 결과를 .sisyphus/evidence/task-5-summary.txt에 캡처
  Expected Result: 정량적 결과 확인 가능
  Evidence: .sisyphus/evidence/task-5-summary.txt

Scenario: 품질 평가
  Tool: Bash
  Steps:
    1. cd backend && python -c "
       import json
       d = json.load(open('results/comparison.json'))
       avg_f1 = d['summary']['avg_pitch_class_f1']
       low_songs = [n for n,s in d['songs'].items() if s['pitch_class_f1'] < 0.30]
       if avg_f1 >= 0.30:
           print(f'QUALITY OK: avg pitch_class_f1 = {avg_f1:.3f}')
       else:
           print(f'QUALITY LOW: avg pitch_class_f1 = {avg_f1:.3f}')
           print(f'Low quality songs: {low_songs}')
           print('Task 6 (튜닝) 진행 필요')
       "
    2. 결과에 따라 Task 6 진행 여부 결정
  Expected Result: 품질 판단 기준 명확
```

**Commit**: YES
- Message: `feat(results): add 8-song vocal melody comparison results`
- Files: `backend/results/comparison.json`

---

### Task 6: 품질 개선 (조건부 — Task 5에서 avg pitch_class_f1 < 0.30인 경우)

**What to do**:
1. Task 5 결과 분석하여 문제점 파악:
   - 보컬 분리 품질 확인: 분리된 vocal.wav를 직접 분석
   - pyin 파라미터 튜닝: fmin, fmax, frame_length, hop_length
   - note segmentation 파라미터: min_duration, confidence threshold
2. 튜닝 방향:
   - **보컬 분리 모델 변경**: audio-separator의 다른 UVR 모델 시도
   - **pyin 파라미터 조정**: 
     - `frame_length` 증가 (더 안정적인 pitch)
     - `fmin/fmax` 범위 조정 (불필요한 고역/저역 제거)
   - **후처리 강화**: 
     - median filtering (vibrato 안정화)
     - minimum gap merging (짧은 쉼표 무시)
     - pitch quantization tolerance 조정
3. 개선 후 다시 8곡 비교 실행
4. 폴백 경로 (pyin 자체가 부족한 경우):
   - torchcrepe 설치 + 테스트
   - HPSS (Harmonic/Percussive Separation) + pyin 조합

**Must NOT do**:
- 기존 모듈 수정 (vocal_melody_pipeline.py만 수정)
- 레퍼런스 추출 방식 변경
- 비교 메트릭 변경

**Recommended Agent Profile**:
- **Category**: `deep`
  - Reason: 파라미터 튜닝, 문제 진단, 대안 탐색
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3 (sequential, after Task 5)
- **Blocks**: None (최종 태스크)
- **Blocked By**: Task 5

**References**:
- `backend/core/vocal_melody_pipeline.py` — 수정 대상
- Task 5 결과: `backend/results/comparison.json`
- librosa.pyin 파라미터: https://librosa.org/doc/latest/generated/librosa.pyin.html
- audio-separator 모델 목록: `audio-separator --list_models`

**Acceptance Criteria**:

```
Scenario: 개선 후 결과 비교
  Tool: Bash
  Preconditions: Task 5 결과 확인됨
  Steps:
    1. cd backend && python scripts/compare_melodies.py --input-dir ../test --cache-dir ../test/cache --output results/comparison_v2.json
    2. python -c "
       import json
       v1 = json.load(open('results/comparison.json'))
       v2 = json.load(open('results/comparison_v2.json'))
       f1_v1 = v1['summary']['avg_pitch_class_f1']
       f1_v2 = v2['summary']['avg_pitch_class_f1']
       print(f'Before: {f1_v1:.3f}')
       print(f'After:  {f1_v2:.3f}')
       print(f'Change: {f1_v2 - f1_v1:+.3f}')
       assert f1_v2 > f1_v1, 'No improvement!'
       print('IMPROVED')
       "
    3. Assert: "IMPROVED" 출력
  Expected Result: 개선된 결과
  Evidence: .sisyphus/evidence/task-6-improvement.txt

Scenario: 폴백 — torchcrepe 시도 (pyin 부족시)
  Tool: Bash
  Steps:
    1. pip install torchcrepe
    2. vocal_melody_pipeline.py에 torchcrepe 옵션 추가
    3. 1곡으로 비교: pyin vs torchcrepe
    4. 더 나은 쪽 선택
  Expected Result: pitch tracker 최적 선택
  Evidence: .sisyphus/evidence/task-6-tracker-comparison.txt
```

**Commit**: YES
- Message: `feat(core): tune vocal melody pipeline parameters for better accuracy`
- Files: `backend/core/vocal_melody_pipeline.py`, `backend/results/comparison_v2.json`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 0 | `fix(musicxml): preserve Part structure in stream_to_musicxml` | midi_to_musicxml.py | git status clean |
| 1 | `feat(deps): add audio-separator for vocal separation pipeline` | requirements.txt, test/cache/.gitignore | pip install 성공 |
| 3 | `feat(core): add vocal separation melody extraction pipeline` | vocal_melody_pipeline.py | import 성공 |
| 4 | `feat(scripts): add vocal melody comparison scripts` | run_vocal_pipeline.py, compare_melodies.py | 스크립트 실행 성공 |
| 5 | `feat(results): add 8-song vocal melody comparison results` | results/comparison.json | JSON 유효 |
| 6 | `feat(core): tune vocal melody pipeline parameters` | vocal_melody_pipeline.py | 개선 확인 |

---

## Success Criteria

### Verification Commands
```bash
# 1. audio-separator 설치 확인
cd backend && python -c "from audio_separator.separator import Separator; print('OK')"

# 2. 단일 곡 파이프라인
cd backend && python -c "
from pathlib import Path
from core.vocal_melody_pipeline import extract_vocal_melody
notes = extract_vocal_melody(Path('../test/Golden.mp3'), Path('../test/cache'))
print(f'Notes: {len(notes)}')
assert len(notes) > 10
"

# 3. 레퍼런스 추출
cd backend && python -c "
from core.musicxml_melody_extractor import extract_melody_from_musicxml
notes = extract_melody_from_musicxml('../test/Golden.mxl')
print(f'Ref notes: {len(notes)}')
"

# 4. 8곡 비교
cd backend && python scripts/compare_melodies.py --input-dir ../test --cache-dir ../test/cache --output results/comparison.json

# 5. 결과 확인
cd backend && python -c "
import json
d = json.load(open('results/comparison.json'))
print(f'Songs: {d[\"summary\"][\"total_songs\"]}')
print(f'Avg pitch_class_f1: {d[\"summary\"][\"avg_pitch_class_f1\"]:.3f}')
"
```

### Final Checklist
- [ ] midi_to_musicxml.py 버그 수정 커밋됨
- [ ] audio-separator[cpu] 설치 + 작동 확인
- [ ] vocal_melody_pipeline.py 구현 완료
- [ ] 8곡 모두 보컬 분리 + 멜로디 추출 성공 (노트 > 10)
- [ ] 8곡 비교 결과 JSON 생성
- [ ] pitch_class_f1 평균 ≥ 0.30
- [ ] 기존 코드 수정 없음 (새 모듈만 추가)
- [ ] 캐시 작동 확인 (두 번째 실행 빠름)
- [ ] 한글 파일명 + 공백 경로 처리 정상
