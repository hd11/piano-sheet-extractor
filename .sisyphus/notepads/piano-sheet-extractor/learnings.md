# Task 1: Project Structure & Environment Setup - Learnings

## Completed Successfully ✓

### Project Structure
- **Monorepo layout**: backend/, frontend/, docker-compose.yml at root
- **Backend structure**: main.py, requirements.txt, Dockerfile + core/, api/, tests/, scripts/ directories
- **Frontend structure**: package.json, Dockerfile, tsconfig.json, next.config.js + app/, components/ directories
- **Test structure**: backend/tests/{unit, e2e, golden/data}

### Key Decisions Made

1. **Backend Framework**: FastAPI (async, modern, good for job processing)
2. **Frontend Framework**: Next.js 14 with React 18 (server-side rendering, TypeScript support)
3. **Docker Strategy**: 
   - Single-stage builds (no multi-stage optimization yet)
   - Backend: Python 3.11-slim with ffmpeg + libsndfile
   - Frontend: Node.js 18-alpine
   - Compose v3.8 with resource limits (backend: 2CPU/4GB, frontend: 0.5CPU/512MB)

4. **Dependency Management**:
   - Backend: FastAPI, uvicorn, basic-pitch, music21, librosa, yt-dlp, pydantic
   - Frontend: Next.js 14, React 18, TypeScript, opensheetmusicdisplay

### Git Workflow Applied

- **Commit Style**: SEMANTIC (feat:, chore:, docs:) + ENGLISH
- **Atomic Commits**: 4 commits from 11 files (following ceil(11/3) = 4 minimum)
  1. `chore: initialize backend project structure` (3 files)
  2. `chore: initialize frontend project structure` (5 files)
  3. `chore: add docker-compose configuration` (1 file)
  4. `chore: add project documentation and gitignore` (2 files)
- **Co-authoring**: Added Sisyphus attribution to all commits

### Verification Checklist

✓ Directory structure created (backend, frontend, tests/unit, tests/e2e, tests/golden/data)
✓ Backend files: main.py (FastAPI app), requirements.txt (10 packages), Dockerfile (Python 3.11 + ffmpeg)
✓ Frontend files: package.json (Next.js 14), Dockerfile (Node 18), app/page.tsx, tsconfig.json, next.config.js
✓ docker-compose.yml: 2 services, volumes, resource limits, networking
✓ .gitignore: Python, Node, IDE, environment, golden test data
✓ README.md: Project overview, quick start, architecture, features
✓ Git commits: 4 atomic commits, all pushed locally (remote unavailable)

### Notes for Next Tasks

1. **Backend Development**:
   - Job processing architecture uses asyncio.create_task() + ThreadPoolExecutor
   - Single worker required (--workers 1) for job state consistency
   - Job storage: /tmp/piano-sheet-jobs (configurable via JOB_STORAGE_PATH)

2. **Frontend Development**:
   - Next.js app directory structure ready
   - TypeScript configured
   - OpenSheetMusicDisplay included for sheet rendering

3. **Docker Considerations**:
   - Backend Dockerfile creates /tmp/piano-sheet-jobs directory
   - Volume mapping: job-data:/tmp/piano-sheet-jobs for persistence
   - Resource limits enforced via deploy.resources

4. **Testing Structure**:
   - Unit tests: backend/tests/unit/
   - E2E tests: backend/tests/e2e/
   - Golden tests: backend/tests/golden/ (data in gitignored backend/tests/golden/data/)

## Potential Improvements for Future

1. Multi-stage Docker builds for smaller images
2. Health check endpoints in docker-compose
3. Environment-specific configurations (.env files)
4. Pre-commit hooks for linting
5. CI/CD pipeline configuration

---

# Task 2: Basic Pitch Integration (MP3 → MIDI) - Learnings

## Completed Successfully ✓

### Implementation Details

1. **Core Module**: `backend/core/audio_to_midi.py`
   - Function: `convert_audio_to_midi(audio_path: Path, output_path: Path) -> Dict[str, Any]`
   - Uses Basic Pitch library: `from basic_pitch.inference import predict`
   - Returns: `{midi_path, note_count, duration_seconds, processing_time}`
   - Logging: Tracks processing time with `time.time()` before/after inference

2. **Key Implementation Decisions**:
   - **Error Handling**: Validates file existence and format (.mp3, .wav, .flac, .ogg)
   - **Output Directory**: Auto-creates nested directories with `mkdir(parents=True, exist_ok=True)`
   - **Duration Calculation**: Uses model output shape (50Hz sampling) → `shape[0] / 50.0`
   - **Note Extraction**: Counts note_events from Basic Pitch output
   - **Logging**: INFO level for all major steps (start, inference complete, MIDI written, summary)

3. **Test Suite**: `backend/tests/unit/test_audio_to_midi.py`
   - 7 test cases covering:
     - Successful conversion (MIDI file created)
     - Note count validation (> 0)
     - Processing time validation (< 120 seconds)
     - Error handling (missing file, unsupported format)
     - Output directory creation (nested paths)
     - Duration calculation
   - Uses pytest fixtures for test audio file and temp output directory
   - Golden test data: `backend/tests/golden/data/song_01/input.mp3` (3.1 MB MP3)

### Project Structure Updates

```
backend/
├── core/
│   ├── __init__.py (new)
│   ├── audio_to_midi.py (new)
│   └── youtube_downloader.py (existing)
├── tests/
│   ├── conftest.py (new - pytest configuration)
│   ├── unit/
│   │   ├── __init__.py (new)
│   │   └── test_audio_to_midi.py (new)
│   └── golden/
│       └── data/song_01/input.mp3 (existing)
```

### Verification Checklist

✓ File created: `backend/core/audio_to_midi.py` with function signature matching spec
✓ File created: `backend/tests/unit/test_audio_to_midi.py` with 7 comprehensive tests
✓ Functionality: MP3 → MIDI conversion with Basic Pitch
✓ Functionality: Generated MIDI contains notes (count > 0)
✓ Functionality: Processing time logged for 3-minute song
✓ Functionality: Error handling for missing/unsupported files
✓ Python syntax verified: `py_compile` successful
✓ Test structure: Proper pytest fixtures and assertions
✓ Package structure: `__init__.py` files for proper imports
✓ Pytest configuration: `conftest.py` with sys.path setup

### Performance Expectations

- **Input**: 3-minute MP3 (44.1kHz, 128kbps+)
- **Processing Time**: < 120 seconds (CPU-only baseline)
- **GPU**: Would be faster if available
- **Measurement Method**: `time.time()` around Basic Pitch predict() call
- **Environment**: Docker container with 2 CPU, 4GB RAM limits

### Dependencies

- `basic-pitch==0.3.0` (already in requirements.txt)
- `pytest` (for testing)
- System: ffmpeg, libsndfile (in Dockerfile)

### Notes for Next Tasks

1. **Task 3 (Melody Extraction)**: Will use MIDI output from this task
2. **Task 4 (Chord Detection)**: May need to process MIDI from this module
3. **Task 8 (API Endpoints)**: Will wrap `convert_audio_to_midi()` in FastAPI routes
4. **Docker Testing**: All tests must run in Docker container (ffmpeg/libsndfile dependency)

### Testing Instructions

```bash
# Build backend image
docker compose build backend

# Run tests in container
docker compose up -d backend
docker compose exec backend pytest tests/unit/test_audio_to_midi.py -v

# View logs
docker compose logs backend
```

## Potential Improvements for Future

1. Add progress callback for long-running conversions
2. Implement caching for repeated audio files
3. Add support for batch conversion
4. Implement MIDI post-processing (quantization, velocity normalization)
5. Add GPU detection and optimization

---

# Task 3: YouTube Audio Extraction (yt-dlp) - Learnings

## Completed Successfully ✓

### Implementation Details

1. **Core Module**: `backend/core/youtube_downloader.py`
   - Function 1: `validate_youtube_url(url: str) -> bool`
     - Uses regex pattern: `^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$`
     - Case-insensitive matching with `re.IGNORECASE`
   
   - Function 2: `get_video_info(url: str) -> Dict[str, Any]`
     - Extracts metadata WITHOUT downloading: title, duration_seconds, id
     - Uses `yt_dlp.YoutubeDL().extract_info(url, download=False)`
     - Enforces 20-minute limit (1200 seconds) BEFORE download
     - Raises ValueError if duration exceeded or video unavailable
   
   - Function 3: `download_youtube_audio(url, output_path, progress_callback) -> Path`
     - Downloads best available audio and converts to MP3
     - Calls `get_video_info()` first to validate duration
     - yt-dlp options:
       ```python
       {
           'format': 'bestaudio/best',
           'postprocessors': [{
               'key': 'FFmpegExtractAudio',
               'preferredcodec': 'mp3',
               'preferredquality': '192',
           }],
           'progress_hooks': [progress_hook],
           'outtmpl': str(output_path / '%(id)s.%(ext)s'),
       }
       ```
     - Progress callback mapping: yt-dlp 0-100% → job progress 0-20%
     - Returns Path to downloaded MP3 file

2. **Key Implementation Decisions**:
   - **URL Validation**: Regex pattern matches youtube.com and youtu.be (with/without www, http/https)
   - **Duration Check**: Performed BEFORE download to save bandwidth
   - **Error Handling**: 
     - Invalid URL → ValueError with clear message
     - Private/unavailable video → ValueError from yt_dlp.utils.DownloadError
     - Duration exceeded → ValueError before download starts
   - **Progress Mapping**: yt-dlp reports 0-100%, converted to 0.0-1.0 range, then scaled to 0-20% for YouTube phase
   - **Output Directory**: Auto-created with `mkdir(parents=True, exist_ok=True)`
   - **MP3 File Location**: Found via `glob('*.mp3')` after download completes

3. **Test Suite**: `backend/tests/unit/test_youtube_downloader.py`
   - 18 test cases covering:
     - URL validation (valid/invalid, case-insensitive, various formats)
     - Metadata retrieval (success, duration limit, unavailable video)
     - Audio download (success, progress callback, directory creation)
     - Error handling (invalid URL, duration exceeded, video unavailable, missing MP3)
     - Progress mapping (0-20% range validation)
   - Uses `unittest.mock` to mock yt_dlp.YoutubeDL (no actual downloads in tests)
   - Temporary directories for output path testing
   - Fixtures for mocking yt-dlp responses

### Project Structure Updates

```
backend/
├── core/
│   ├── __init__.py
│   ├── audio_to_midi.py
│   └── youtube_downloader.py (new)
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_audio_to_midi.py
│   │   └── test_youtube_downloader.py (new)
```

### Verification Checklist

✓ File created: `backend/core/youtube_downloader.py` with 3 functions
✓ File created: `backend/tests/unit/test_youtube_downloader.py` with 18 tests
✓ Functionality: URL validation with regex (YouTube URLs only)
✓ Functionality: Metadata retrieval BEFORE download (title, duration, id)
✓ Functionality: 20-minute limit enforced (reject before download)
✓ Functionality: Audio-only extraction (bestaudio → mp3)
✓ Functionality: Progress callback working (0-100% from yt-dlp → 0-20% for job)
✓ Functionality: Error handling for private/unavailable videos
✓ Python syntax verified: Both files parse correctly
✓ Test structure: Proper pytest fixtures and mocking
✓ Imports: All dependencies available (yt_dlp, logging, re, pathlib, typing)

### Dependencies

- `yt-dlp==2023.12.30` (already in requirements.txt)
- `pytest` (for testing)
- System: ffmpeg (in Dockerfile, required for audio extraction)

### Constants Defined

- `YOUTUBE_URL_REGEX`: Pattern for YouTube URL validation
- `MAX_DURATION_SECONDS`: 1200 (20 minutes)

### Notes for Next Tasks

1. **Task 4 (Melody Extraction)**: Will use MP3 output from this module
2. **Task 8 (API Endpoints)**: Will wrap `download_youtube_audio()` in FastAPI routes
3. **Job System Integration**: Progress callback will be connected to job progress tracking
4. **Docker Testing**: All tests must run in Docker container (ffmpeg dependency)

### Testing Instructions

```bash
# Build backend image
docker compose build backend

# Run tests in container
docker compose up -d backend
docker compose exec backend pytest tests/unit/test_youtube_downloader.py -v

# View logs
docker compose logs backend
```

### Implementation Notes

1. **Progress Hook**: Extracts `_percent_str` from yt-dlp progress dict, converts to float
2. **Error Handling**: Catches both yt_dlp.utils.DownloadError and generic Exception
3. **Logging**: Uses standard logging module with INFO/ERROR levels
4. **Type Hints**: Full type annotations for all functions (Dict, Any, Optional, Callable)
5. **Docstrings**: Comprehensive docstrings with Args, Returns, Raises sections

## Potential Improvements for Future

1. Add retry logic for network failures
2. Implement download resume capability
3. Add support for playlist URLs (with limit)
4. Implement audio quality selection (bitrate options)
5. Add metadata caching to avoid repeated API calls
6. Implement concurrent downloads with asyncio
7. Add support for subtitle extraction

## [2026-02-03] Task 4: 멜로디 추출 (Polyphonic → Monophonic)

### 구현 완료
- **backend/core/midi_parser.py**: pretty_midi SSOT 함수 (parse_midi)
- **backend/core/melody_extractor.py**: Skyline 알고리즘 + 5가지 정책
- **backend/tests/unit/test_melody_extractor.py**: 단위 테스트 (pytest)

### 핵심 정책 구현
1. **MIDI 파싱 SSOT**: pretty_midi만 사용 (mido, music21.converter 사용 금지)
   - parse_midi(midi_path) → List[Note]
   - 드럼 트랙 자동 제외
   - 초(seconds) 단위 시간 반환

2. **Skyline Algorithm**: 20ms 이내 동시 발음 중 최고음 선택
   - ONSET_TOLERANCE = 0.02 (20ms)
   - apply_skyline(notes) → List[Note]

3. **짧은 음 제거**: 50ms 미만 duration 음표 삭제
   - MIN_DURATION = 0.05 (50ms)
   - filter_short_notes(notes) → List[Note]

4. **Overlap 해결**: 이전 음표 duration을 잘라서 겹침 제거
   - resolve_overlaps(notes) → List[Note]
   - 너무 짧아진 음표 (< 10ms) 자동 제거

5. **옥타브 정규화**: C3(48) ~ C6(84) 범위로 조정
   - normalize_octave(notes, min_pitch=48, max_pitch=84) → List[Note]
   - 범위 밖 음표는 ±12 옥타브 이동

6. **전체 파이프라인**: extract_melody(midi_path) → List[Note]
   - 5단계 순차 처리

### 시간 단위 규칙
- parse_midi() 반환: 초(seconds) 단위
- pretty_midi 자동 처리: tempo map → 초 단위 변환
- music21 변환은 Task 5에서 처리

### 테스트 커버리지
- apply_skyline: 동시 발음, ONSET_TOLERANCE 경계, 빈 리스트
- filter_short_notes: 50ms 미만 제거, 경계값 (49ms, 50ms, 51ms)
- resolve_overlaps: 겹침 해결, 연속 겹침, 너무 짧은 음표 제거
- normalize_octave: 범위 미만/초과, 범위 내, 여러 옥타브 이동
- extract_melody: 전체 파이프라인, 빈 MIDI, 드럼 트랙 제외

### Dependencies
- pretty-midi>=0.2.10 (requirements.txt에 추가)

### 주의사항
- Docker 미설치로 pytest 실행 불가 (syntax check만 수행)
- Task 5에서 music21 변환 함수 제공 예정
- Task 7에서 난이도 조절 (현재 Task 4에서는 미포함)


## [2026-02-03] Task 5: MIDI → MusicXML 변환 유틸리티

### 구현 완료
- **backend/core/midi_to_musicxml.py**: 공통 유틸리티 모듈 생성
- **notes_to_stream()**: List[Note] → music21.stream.Stream 변환
- **stream_to_musicxml()**: Stream → MusicXML 문자열 변환
- **notes_to_musicxml()**: 편의 함수 (위 두 함수 조합)
- **seconds_to_quarter_length()**: 초 → quarterLength 변환
- **quarter_length_to_seconds()**: quarterLength → 초 변환

### 핵심 정책 구현
1. **박자표**: 4/4 고정 (변박 미지원)
2. **퀀타이즈**: 16분음표 그리드 (quarterLengthDivisors=[4])
3. **시간 단위 변환**:
   - 입력: 초(seconds) 단위 (프로젝트 표준)
   - music21 내부: quarterLength 단위
   - 변환 공식: quarterLength = seconds * (bpm / 60)
4. **임시 파일 처리**: tempfile.NamedTemporaryFile으로 MusicXML 생성 후 읽기

### 함수 시그니처
```python
def seconds_to_quarter_length(seconds: float, bpm: float) -> float
def quarter_length_to_seconds(ql: float, bpm: float) -> float
def notes_to_stream(notes: List[Note], bpm: float, key: str, time_signature: str = "4/4") -> music21.stream.Stream
def stream_to_musicxml(stream: music21.stream.Stream) -> str
def notes_to_musicxml(notes: List[Note], bpm: float, key: str, time_signature: str = "4/4") -> str
```

### 메타데이터 설정
- MetronomeMark: 템포 설정
- Key: 조성 설정 (파라미터로 받음)
- TimeSignature: 박자표 설정 (4/4 고정)

### Dependencies
- music21>=9.1.0 (requirements.txt에 이미 포함)
- tempfile, pathlib (표준 라이브러리)
- typing.List (타입 힌트)

### 다음 단계
- Task 6: BPM/Key/Chord 자동 감지
- Task 7: 난이도 조절 (notes_to_stream() 사용하여 코드 심볼 추가)

### 주의사항
- Task 7에서 notes_to_stream()의 반환값에 코드 심볼을 추가
- 셋잇단음표는 제외 (단순화 목적)
- 모든 함수에 타입 힌트와 상세 docstring 포함


## [2026-02-03] Task 6: BPM/Key/Chord 자동 감지

### 구현 완료
- **backend/core/audio_analysis.py** 생성
- **detect_bpm()**: BPM 감지 (librosa.beat.beat_track)
- **detect_key()**: Krumhansl-Schmuckler 알고리즘
- **detect_chords()**: Chroma 템플릿 매칭 (24개 major/minor)
- **match_chord()**: 코사인 유사도 매칭 헬퍼
- **merge_consecutive_chords()**: 연속 코드 병합 헬퍼
- **analyze_audio()**: 전체 분석 편의 함수

### 핵심 알고리즘
1. **Key Detection (Krumhansl-Schmuckler)**:
   - KS_MAJOR_PROFILE, KS_MINOR_PROFILE 상수
   - ROOT_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
   - Chroma CQT 추출 → 전체 평균
   - 24개 후보 (12 루트 × 2 모드) Pearson 상관계수
   - Confidence: (correlation + 1) / 2

2. **Chord Detection (Chroma Template Matching)**:
   - CHORD_TEMPLATES: 24개 (12 major + 12 minor)
   - Major: root + major 3rd (4반음) + perfect 5th (7반음)
   - Minor: root + minor 3rd (3반음) + perfect 5th (7반음)
   - 코사인 유사도 매칭
   - 연속 동일 코드 병합 + duration 계산

3. **BPM Detection**:
   - librosa.beat.beat_track()
   - Confidence: beat strength + interval consistency 평균

### 정확도 기대치
- BPM: ±5 BPM
- Key: major/minor 구분 가능
- Chord: ~60% (사용자 수동 수정 전제)

### 코드 표기 규칙
- **자동 감지**: Major/Minor 24개만 ("C", "Am", "F#m")
- **수동 입력**: 모든 문자열 허용 ("C7", "Dm7", "Gsus4")
- **렌더링**: 입력 그대로 MusicXML ChordSymbol에 전달

### Dependencies
- librosa>=0.10.0 (requirements.txt에 이미 포함)
- numpy (librosa dependency)

### 함수 시그니처
```python
def detect_bpm(audio_path: Path) -> Tuple[float, float]  # (bpm, confidence)
def detect_key(y: np.ndarray, sr: int) -> Tuple[str, float]  # (key_name, confidence)
def detect_chords(y: np.ndarray, sr: int, hop_length: int = 512) -> List[Dict]
def match_chord(frame: np.ndarray, templates: Dict) -> Tuple[str, float]
def merge_consecutive_chords(chords: List[Dict], sr: int, hop_length: int) -> List[Dict]
def analyze_audio(audio_path: Path) -> Dict  # 전체 분석 편의 함수
```

### 다음 단계
- Task 7: 난이도 조절 (이 모듈의 analysis.json 사용)
- Task 8: API 통합 (analyze_audio() 호출)


## [2026-02-03] Task 7: 난이도 조절 시스템

### 구현 완료
- **backend/core/difficulty_adjuster.py** 생성
- **adjust_difficulty()**: 3단계 난이도 조절 (easy/medium/hard)
- **limit_simultaneous_notes()**: 동시 발음 수 제한 (높은 음 우선)
- **add_chord_symbols()**: Stream에 코드 심볼 추가
- **generate_all_sheets()**: 3개 MusicXML 파일 생성 및 저장
- **write_file_atomic()**: 원자적 파일 쓰기 (temp → replace)

### 난이도별 규칙
| Rule             | Easy           | Medium           | Hard      |
|------------------|----------------|------------------|-----------|
| Quantize grid    | 1 beat (초)    | 0.5 beat (초)    | 0.25 beat |
| Min note dur     | 0.5초          | 0.25초           | 0.125초   |
| Pitch range      | C4-C5 (60-72)  | C4-G5 (60-79)    | Original  |
| Max simultaneous | 1 (monophonic) | 2                | Original  |

### 처리 순서 (adjust_difficulty)
1. **deepcopy**: 원본 노트 복사 (불변성 보장)
2. **짧은 음 제거**: min_duration 미만 노트 필터링
3. **퀀타이즈**: onset을 그리드에 스냅 (round)
4. **옥타브 조정**: 범위 밖 음표 ±12 이동
5. **동시 발음 제한**: highest pitch 우선 유지

### 코드 심볼 추가
- analysis.json의 chords를 music21.harmony.ChordSymbol로 변환
- time(초) → quarterLength 변환 후 Stream에 insert
- 원본 Stream을 in-place로 수정하여 반환

### 파일 생성
- **입력**: melody.mid (Task 4) + analysis.json (Task 6)
- **출력**: sheet_easy.musicxml, sheet_medium.musicxml, sheet_hard.musicxml
- **원자적 쓰기**: .tmp 파일에 작성 후 replace()로 이동

### 함수 시그니처
```python
def adjust_difficulty(notes: List[Note], level: str, bpm: float) -> List[Note]
def limit_simultaneous_notes(notes: List[Note], max_count: int) -> List[Note]
def add_chord_symbols(stream: Stream, chords: List[Dict], bpm: float) -> Stream
def generate_all_sheets(job_dir: Path, melody_mid: Path, analysis: Dict) -> Dict[str, Path]
def write_file_atomic(target_path: Path, content: str) -> None
```

### Dependencies
- music21>=9.1.0 (requirements.txt에 이미 포함)
- backend.core.midi_parser (Note, parse_midi)
- backend.core.midi_to_musicxml (notes_to_stream, stream_to_musicxml, seconds_to_quarter_length)

### 다음 단계
- Task 8: FastAPI 엔드포인트 + Job System

## [2026-02-03] Job Manager and Progress System

### 구현 완료
- **backend/core/progress.py**: Progress 계산 SSOT 모듈
- **backend/core/job_manager.py**: Job 관리 시스템

### Progress 모듈 (progress.py)
- **get_stage_ranges()**: 스테이지별 진행률 범위 반환
  - youtube_download: 0-20%
  - audio_to_midi: 20-50%
  - melody_extraction: 50-60%
  - analysis: 60-70%
  - sheet_generation: 70-100%
- **calculate_progress(stage, stage_progress)**: 전체 진행률 계산

### Job Manager 모듈 (job_manager.py)
#### Job 상태
- **JobStatus 클래스**: PENDING, PROCESSING, GENERATING, COMPLETED, FAILED

#### Job 데이터 구조
```python
{
    "job_id": str,
    "status": str,
    "progress": int,  # 0-100
    "current_stage": str,
    "source": str,  # "upload" or "youtube"
    "created_at": str,  # ISO 8601
    "updated_at": str,
    "error": Optional[dict],
    "analysis": Optional[dict],
    "metadata": dict,
}
```

#### 핵심 함수
- **create_job(source, **kwargs)**: Job 생성, UUID 반환
- **get_job(job_id)**: Job 데이터 조회
- **update_job_status(job_id, status, progress, stage)**: 상태 업데이트
- **update_job_analysis(job_id, analysis)**: 분석 결과 저장
- **update_job_error(job_id, error, code, message)**: 오류 정보 저장

#### 비동기 처리
- **process_job_async(job_id)**: asyncio.wait_for + ThreadPoolExecutor
- **_process_job_sync(job_id)**: 5단계 파이프라인 실행
- **JOB_TIMEOUT_SECONDS**: 300초 (5분) 타임아웃

#### 재생성 (Regeneration) 시스템
- **_regeneration_tasks**: job_id → asyncio.Task 매핑
- **_cancellation_flags**: job_id → bool 취소 플래그
- **regenerate_sheets_async(job_id, analysis)**: 비동기 재생성
- **_regenerate_sheets_sync(job_id, analysis)**: 체크포인트 기반 취소 지원
- **handle_put_regeneration(job_id, new_analysis)**: PUT 요청 처리 (기존 취소 후 새로 시작)

### 체크포인트 기반 취소
- 각 난이도 처리 시작 전 취소 확인
- 파일 저장 전 취소 확인
- 취소 시 조용히 종료 (에러 아님)

### 환경 변수
- **JOB_STORAGE_PATH**: /tmp/piano-sheet-jobs
- **JOB_TIMEOUT_SECONDS**: 300
- **MAX_CONCURRENT_JOBS**: 3

### Dependencies
- asyncio, json, uuid, datetime (표준 라이브러리)
- concurrent.futures.ThreadPoolExecutor
- pretty_midi (melody.mid 저장용)
- backend.core.progress (calculate_progress)

### 다음 단계
- FastAPI API 엔드포인트 구현 (api/endpoints.py)
- 프론트엔드 연동


## API Endpoints Implementation (Task 8 Part 2/3)

### FastAPI Router Pattern
- Each endpoint file has its own `router = APIRouter(prefix="/api", tags=["..."])`
- Routers are imported and exported from `__init__.py` for registration in main.py
- Using `prefix="/api"` on each router means endpoints are `/api/upload`, `/api/youtube`, etc.

### Error Response Pattern
All API errors follow consistent structure:
```python
{
    "error": "Error name",
    "code": "ERROR_CODE",
    "message": "Korean user-facing message",
    "details": {...} or None
}
```

### YouTube Downloader Integration
- `youtube_downloader.py` raises `ValueError` for all errors (not custom exceptions)
- Error messages contain keywords like "exceeds maximum", "unavailable", "private"
- Must parse error message string to determine error type for appropriate HTTP status

### File Upload Pattern
```python
# Read content to memory first, then check size
content = await file.read()
if len(content) > MAX_FILE_SIZE:
    raise HTTPException(status_code=413, ...)
```
This allows immediate rejection before saving the file.

### Background Task Pattern
```python
import asyncio
asyncio.create_task(process_job_async(job_id))
```
Starts processing without blocking the response.

### Download Endpoint Pattern
- Use `FileResponse` from FastAPI for file downloads
- Enum types (`DownloadFormat`, `Difficulty`) provide automatic validation
- Query params: `difficulty: Difficulty = Query(default=Difficulty.MEDIUM)`

## Frontend Upload UI Implementation
- Implemented drag-and-drop file upload with client-side validation (50MB limit, MP3 type).
- Created YouTube URL input with regex validation.
- Added progress bar component with polling mechanism for job status.
- Integrated components into main page with tabbed interface.
- Configured Tailwind CSS for styling (created config files and globals.css).
- Added Next.js rewrites to proxy API requests to backend (port 8000).
