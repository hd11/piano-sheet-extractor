# 피아노 악보 추출 웹 애플리케이션

## Context

### Environment Prerequisites
- **Git Repository**: 이 프로젝트는 Git 저장소로 시작합니다. Task 1에서 `git init` 실행.
- **Node.js**: v18+ (Next.js 14 요구사항)
- **Python**: 3.11+ (Basic Pitch, music21 호환성)
- **Docker**: Docker Desktop 또는 Docker Engine + Compose v2

### Original Request
MP3 음원을 업로드하면 사람들이 취미로 칠 수 있는 정도 수준의 피아노 악보를 추출하는 웹 애플리케이션

**지원 장르**: 대중가요, 영화 OST, 클래식, 동요, 재즈, CCM 등 모든 장르
- 장르에 따른 특별한 처리 없음 (범용 멜로디 추출)
- 복잡한 클래식 곡의 경우 주요 멜로디 라인만 추출됨

### Interview Summary
**Key Discussions**:
- 프로그램 형태: 웹 애플리케이션 (브라우저에서 파일 업로드 → 결과 확인)
- 출력 형식: MIDI 파일, MusicXML 파일, 화면 악보 표시
- 음원 처리: 멜로디 중심 추출 (가장 두드러진 멜로디 라인)
- 난이도 조절: 음표 간소화 방식 (초급/중급/고급)
- 코드/BPM/조성: 자동 감지 + 수동 입력/수정 모두 지원
- 가사 싱크: 불필요
- 파일 제한: 50MB / 20분
- 처리 시간: 5분까지 허용
- 배포: 로컬 Docker

**Research Findings**:
- Basic Pitch: Spotify 개발, Apache-2.0, 폴리포닉 지원, 피치벤드 감지, CPU로 충분
- OpenSheetMusicDisplay: MusicXML 렌더링, VexFlow 기반, BSD-3-Clause
- music21: MIDI ↔ MusicXML 변환에 가장 성숙한 Python 라이브러리
- librosa: BPM/Key 감지에 널리 사용
- yt-dlp: YouTube 오디오 추출, ffmpeg 필요

---

## Work Objectives

### Core Objective
MP3 음원 또는 YouTube URL에서 멜로디를 추출하여 취미 연주자가 칠 수 있는 수준의 피아노 악보를 생성하고, 브라우저에서 확인 및 다운로드할 수 있는 웹 애플리케이션 개발

> **장르 무관**: 대중가요, 영화 OST, 클래식, 동요, 재즈 등 모든 음악 장르에서 멜로디 추출 가능

### Concrete Deliverables
- FastAPI 백엔드 서버 (Python 3.11)
- Next.js 프론트엔드 (React 18)
- Docker Compose 설정 (ffmpeg 포함)
- Playwright E2E 테스트 + Golden Test 시스템
- 10곡 이상의 테스트 데이터셋

### Definition of Done
- [ ] MP3 업로드 → MIDI/MusicXML 다운로드 전체 플로우 동작
- [ ] YouTube URL → MIDI/MusicXML 다운로드 전체 플로우 동작
- [ ] 브라우저에서 악보 렌더링 확인
- [ ] 코드/BPM/조성 자동 감지 및 수동 수정 가능
- [ ] 난이도 조절 (초급/중급/고급) 동작
- [ ] **다양한 장르 지원**: 대중가요, 영화 OST, 클래식, 동요 등 처리 가능
- [ ] Golden Test (Phase 1): 10곡 중 90% 이상 처리 성공 (Smoke 모드)
- [ ] Docker Compose로 원클릭 실행 가능

### Must Have
- MP3 업로드 (최대 50MB, 20분)
- YouTube URL 입력 (yt-dlp로 오디오 추출, 최대 20분)
- 멜로디 추출 및 MIDI 변환
- MIDI → MusicXML 변환
- 브라우저 악보 렌더링
- MIDI/MusicXML 다운로드
- 코드/BPM/조성 자동 감지
- 코드/BPM/조성 수동 입력/수정
- 난이도 조절 (초급/중급/고급)
- 처리 상태 표시 (프로그레스)
- 에러 핸들링

### Must NOT Have (Guardrails)
- ❌ 가사 싱크 기능
- ❌ 사용자 인증/로그인
- ❌ 변환 히스토리 저장 (DB 없음)
- ❌ Spotify URL 지원
- ❌ PDF 출력
- ❌ 실시간 오디오 재생 싱크
- ❌ 모바일 최적화
- ❌ 다중 트랙 분리/선택
- ❌ 악보 편집 기능 (읽기 전용)

---

## Backend Job Processing Architecture

### Job State Machine
```
PENDING → DOWNLOADING → PROCESSING → ANALYZING → GENERATING → COMPLETED
                ↓            ↓           ↓            ↓
              FAILED       FAILED      FAILED       FAILED
```

### Job State Enum
```python
class JobStatus(str, Enum):
    PENDING = "pending"           # 작업 생성됨
    DOWNLOADING = "downloading"   # YouTube 다운로드 중 (YouTube URL인 경우)
    PROCESSING = "processing"     # Basic Pitch 변환 중
    ANALYZING = "analyzing"       # BPM/Key/Chord 분석 중
    GENERATING = "generating"     # MusicXML/난이도별 생성 중
    COMPLETED = "completed"       # 완료
    FAILED = "failed"            # 실패
```

### Progress Definition
| Stage | Progress Range | Description |
|-------|---------------|-------------|
| PENDING | 0% | 작업 대기 |
| DOWNLOADING | 0-20% | YouTube 오디오 다운로드 (yt-dlp progress hook) |
| PROCESSING | 20-50% | Basic Pitch MIDI 변환 |
| ANALYZING | 50-70% | BPM/Key/Chord 분석 |
| GENERATING | 70-100% | MusicXML + 3단계 난이도 생성 |
| COMPLETED | 100% | 완료 |

### Progress 산정 방식 (각 Stage별)

> **핵심 원칙**: 모든 progress 값은 **전체 Job 기준 0-100%**입니다.
> 각 Stage 내부의 진행률은 해당 Stage의 범위로 변환됩니다.

| Stage | Progress Range | 산정 방식 |
|-------|---------------|----------|
| PENDING | 0% | 고정값 |
| DOWNLOADING | 0-20% | yt-dlp 내부 진행률(0-100%) × 0.2 |
| PROCESSING | 20-50% | Basic Pitch 시작=20%, 완료=50% (중간값 없음) |
| ANALYZING | 50-70% | BPM=55%, Key=60%, Chord=70% |
| GENERATING | 70-100% | melody.mid=75%, easy=80%, medium=90%, hard=100% |
| COMPLETED | 100% | 고정값 |

**진행률 계산 SSOT (Single Source of Truth):**

> ⚠️ **중요**: 진행률 계산은 반드시 `get_stage_ranges(source)`를 통해서만 수행합니다.
> 하드코딩된 range 값을 직접 사용하지 마세요.

```python
# backend/core/progress.py - 진행률 계산의 유일한 진실 소스

def get_stage_ranges(source: str) -> dict:
    """
    소스 타입에 따른 Stage 범위 반환 (SSOT)
    
    Args:
        source: "youtube" 또는 "upload"
    
    Returns:
        {stage_name: (start_percent, end_percent)}
    """
    if source == "youtube":
        return {
            "downloading": (0, 20),
            "processing": (20, 50),
            "analyzing": (50, 70),
            "generating": (70, 100),
        }
    else:  # upload
        # 업로드는 downloading 단계가 없음
        return {
            "processing": (0, 50),
            "analyzing": (50, 70),
            "generating": (70, 100),
        }

def convert_stage_progress(source: str, stage: str, internal_progress: float) -> int:
    """
    Stage 내부 진행률(0-100)을 전체 Job 진행률(0-100)로 변환
    
    Args:
        source: "youtube" 또는 "upload"
        stage: 현재 단계 이름
        internal_progress: 단계 내부 진행률 (0-100)
    
    Returns:
        전체 Job 진행률 (0-100)
    """
    ranges = get_stage_ranges(source)
    
    if stage not in ranges:
        return 0  # 알 수 없는 단계
    
    start, end = ranges[stage]
    return int(start + (internal_progress / 100) * (end - start))

# 예시:
# YouTube: convert_stage_progress("youtube", "downloading", 50) → 10
# Upload:  convert_stage_progress("upload", "processing", 50) → 25
```

**Progress Range 요약:**

| Stage | YouTube (0-100) | Upload (0-100) |
|-------|-----------------|----------------|
| PENDING | 0% | 0% |
| DOWNLOADING | 0-20% | (없음) |
| PROCESSING | 20-50% | **0-50%** |
| ANALYZING | 50-70% | 50-70% |
| GENERATING | 70-100% | 70-100% |
| COMPLETED | 100% | 100% |

**사용 예시 (Job Manager):**
```python
# job_manager.py
async def process_job(job_id: str, source: str):
    """Job 처리 - source에 따라 진행률 범위가 다름"""
    
    if source == "youtube":
        # YouTube: downloading 단계 있음
        update_job_status(job_id, {
            "status": "downloading",
            "progress": 0
        })
        # ... 다운로드 중 progress_hook에서 업데이트
    
    # Processing 단계
    update_job_status(job_id, {
        "status": "processing",
        "progress": convert_stage_progress(source, "processing", 0)  # YouTube: 20, Upload: 0
    })
    
    # Basic Pitch 실행...
    
    update_job_status(job_id, {
        "progress": convert_stage_progress(source, "processing", 100)  # YouTube: 50, Upload: 50
    })
    
    # Analyzing 단계
    update_job_status(job_id, {
        "status": "analyzing",
        "progress": convert_stage_progress(source, "analyzing", 0)  # 50
    })
    # ...
```

**yt-dlp progress_hooks (YouTube 전용):**
```python
def create_yt_dlp_progress_hook(job_id: str):
    """yt-dlp 진행률을 Job 진행률로 변환하는 hook 생성"""
    def hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            
            if total > 0:
                internal_progress = (downloaded / total) * 100
                job_progress = convert_stage_progress("youtube", "downloading", internal_progress)
                update_job_status(job_id, {"progress": job_progress})
        
        elif d['status'] == 'finished':
            # downloading 완료 → processing 시작
            update_job_status(job_id, {
                "progress": convert_stage_progress("youtube", "processing", 0),
                "status": "processing"
            })
    
    return hook
```

### Processing 구간 UX 가이드

> **문제**: Processing(Basic Pitch) 단계는 내부 진행률이 없어 20%→50% 한 번에 점프합니다.
> 사용자에게 "멈춘 것처럼" 보일 수 있습니다.

**해결책: Stage 텍스트 + Heartbeat 업데이트**

```python
# job_manager.py
async def run_basic_pitch(job_id: str, source: str):
    """Basic Pitch 실행 (heartbeat 포함)"""
    
    # 시작 시 stage 텍스트 업데이트
    update_job_status(job_id, {
        "status": "processing",
        "progress": convert_stage_progress(source, "processing", 0),
        "current_stage": "AI가 오디오를 분석하고 있습니다..."
    })
    
    # Basic Pitch는 내부 progress hook이 없으므로
    # 별도 스레드에서 실행하면서 heartbeat 업데이트
    async def heartbeat():
        stages = [
            "음악 구조를 파악하고 있습니다...",
            "멜로디를 추출하고 있습니다...",
            "음표를 정리하고 있습니다..."
        ]
        i = 0
        while True:
            await asyncio.sleep(5)  # 5초마다
            update_job_status(job_id, {
                "current_stage": stages[i % len(stages)]
            })
            i += 1
    
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        # Basic Pitch 실행 (블로킹 → to_thread)
        result = await asyncio.to_thread(basic_pitch.predict, audio_path)
    finally:
        heartbeat_task.cancel()
    
    return result
```

**프론트엔드 UI 권장사항:**

| 상태 | UI 표시 |
|------|---------|
| 진행률 변화 없음 (5초+) | 스피너 + `current_stage` 텍스트 표시 |
| 진행률 변화 있음 | 프로그레스 바 애니메이션 |
| `current_stage` 변경 | 부드러운 텍스트 전환 (fade) |

```typescript
// 프론트엔드 예시
function ProgressDisplay({ status, progress, currentStage }: JobStatus) {
  return (
    <div>
      <ProgressBar value={progress} />
      {/* Processing 중에는 스피너 + stage 표시 */}
      {status === "processing" && (
        <div className="flex items-center gap-2">
          <Spinner />
          <span className="animate-pulse">{currentStage}</span>
        </div>
      )}
    </div>
  );
}
```

### Job ID 보안 검증 (SSOT - CRITICAL)

> **경로 탐색 공격 방지**: 모든 job_id는 UUID 형식만 허용하고,
> 계산된 경로가 반드시 JOB_STORAGE_PATH 내부에 있는지 검증해야 합니다.

```python
# core/job_security.py
import uuid
from pathlib import Path
from config import JOB_STORAGE_PATH

class JobNotFoundError(Exception):
    """Job ID가 존재하지 않거나 유효하지 않음"""
    pass

class PathTraversalError(Exception):
    """경로 탐색 공격 감지"""
    pass

def validate_job_id(job_id: str) -> uuid.UUID:
    """
    Job ID 형식 검증 (SSOT 함수)
    
    Args:
        job_id: 검증할 Job ID 문자열
        
    Returns:
        uuid.UUID 객체 (유효한 경우)
        
    Raises:
        JobNotFoundError: 형식이 올바르지 않은 경우
    """
    try:
        return uuid.UUID(job_id, version=4)
    except (ValueError, TypeError):
        raise JobNotFoundError(f"Invalid job ID format: {job_id}")


def get_job_dir(job_id: str) -> Path:
    """
    안전한 Job 디렉토리 경로 반환 (SSOT 함수)
    
    1. UUID 형식 검증
    2. 경로 탐색 공격 방지 (resolved path 검증)
    
    Args:
        job_id: Job ID 문자열
        
    Returns:
        Job 디렉토리 Path 객체
        
    Raises:
        JobNotFoundError: 형식 오류 또는 존재하지 않음
        PathTraversalError: 경로 탐색 공격 감지
    """
    # 1. UUID 형식 검증
    validated_uuid = validate_job_id(job_id)
    
    # 2. 경로 계산
    job_dir = JOB_STORAGE_PATH / str(validated_uuid)
    
    # 3. 경로 탐색 공격 방지 (resolved path가 base 내부인지 확인)
    try:
        resolved = job_dir.resolve()
        base_resolved = JOB_STORAGE_PATH.resolve()
        
        # Windows/Linux 모두 호환되는 방식으로 검증
        if not str(resolved).startswith(str(base_resolved)):
            raise PathTraversalError(f"Path traversal detected: {job_id}")
    except (OSError, ValueError) as e:
        raise PathTraversalError(f"Invalid path: {job_id}") from e
    
    return job_dir


def get_job_dir_or_404(job_id: str) -> Path:
    """
    Job 디렉토리 반환 (존재 확인 포함)
    
    API 엔드포인트에서 사용 - 존재하지 않으면 404
    """
    job_dir = get_job_dir(job_id)
    
    if not job_dir.exists() or not (job_dir / "job.json").exists():
        raise JobNotFoundError(f"Job not found: {job_id}")
    
    return job_dir
```

**사용 예시:**

```python
# ✅ 올바른 사용 (SSOT 함수 사용)
@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job_dir = get_job_dir_or_404(job_id)  # 검증 + 존재 확인
    job = load_job(job_dir)
    return job

# ❌ 금지 (직접 경로 계산)
job_dir = JOB_STORAGE_PATH / job_id  # 경로 탐색 공격에 취약!
```

> **Must NOT do**:
> - `JOB_STORAGE_PATH / job_id` 직접 계산 (반드시 `get_job_dir()` 사용)
> - job_id를 검증 없이 파일 경로에 사용
> - UUID 외 형식의 job_id 허용

### Job Storage (In-Memory + File System)
```
/tmp/piano-sheet-jobs/
├── {job_id}/
│   ├── job.json           # 상태, 메타데이터
│   ├── input.mp3          # 입력 오디오
│   ├── raw.mid            # Basic Pitch 출력
│   ├── melody.mid         # 멜로디 추출 결과
│   ├── analysis.json      # BPM, Key, Chords
│   ├── sheet_easy.musicxml
│   ├── sheet_medium.musicxml
│   └── sheet_hard.musicxml
```

### 산출물 생성 규칙 (SSOT)

> 각 stage에서 어떤 파일을 언제 생성하고, 실패 시 어떻게 처리하는지 정의합니다.

#### Job 생성 시점 정책 (SSOT - 중요!)

> **핵심 원칙**: 검증 실패 시 job.json 미생성, 처리 중 실패 시 job.json 유지

| 실패 유형 | job.json 생성 | 디렉토리 생성 | 이유 |
|----------|--------------|--------------|------|
| **검증 실패** (업로드 전) | ❌ NO | ❌ NO | 유효하지 않은 요청, 기록 불필요 |
| **처리 중 실패** (업로드 후) | ✅ YES | ✅ YES | 에러 기록 유지, 디버깅 가능 |

**검증 실패 예시 (job.json 미생성):**
- 파일 크기 50MB 초과 (업로드 중 감지)
- 파일 형식 오류 (MP3 아님)
- YouTube URL 형식 오류
- YouTube 영상 20분 초과 (다운로드 전 감지)

**처리 중 실패 예시 (job.json 생성 후 status=failed):**
- MP3 길이 20분 초과 (파일 저장 후 librosa로 측정)
- Basic Pitch 변환 실패
- 멜로디 추출 실패
- YouTube 다운로드 실패 (네트워크 오류 등)

**구현 예시:**

> **업로드 흐름의 디렉토리 정책:**
> - **임시 디렉토리**: 스트리밍 저장 중 사용 (`{JOB_STORAGE_PATH}/_temp_{uuid}/`)
> - **Job 디렉토리**: 검증 통과 후 생성 (`{JOB_STORAGE_PATH}/{job_id}/`)
> - 검증 실패 시 임시 디렉토리는 즉시 삭제

```python
# api/upload.py
import tempfile
from pathlib import Path
from config import JOB_STORAGE_PATH

@router.post("/upload")
async def upload_file(file: UploadFile):
    # 임시 업로드 디렉토리 (검증 전)
    temp_dir = JOB_STORAGE_PATH / f"_temp_{uuid.uuid4()}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / "upload.tmp"
    
    try:
        # 1. 스트리밍 저장 + 크기 검증
        total_size = 0
        async with aiofiles.open(temp_file, 'wb') as f:
            async for chunk in file.stream():
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise AppError(
                        error="File too large",
                        code="FILE_TOO_LARGE",
                        message="파일이 너무 큽니다. 50MB 이하 파일만 업로드 가능합니다.",
                        status_code=413,
                        details={"max_size_mb": 50, "received_mb": total_size / (1024 * 1024)}
                    )
                await f.write(chunk)
        
        # 2. 파일 형식 검증 (MP3 전용)
        if not is_valid_audio(temp_file):
            raise AppError(
                error="Unsupported file type",
                code="UNSUPPORTED_FILE_TYPE",
                message="지원하지 않는 파일 형식입니다. MP3 파일만 업로드 가능합니다.",
                status_code=415
            )
        
        # 3. 검증 통과 → Job 생성 + 파일 이동
        job_id = str(uuid.uuid4())
        job_dir = JOB_STORAGE_PATH / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # 임시 파일 → Job 디렉토리로 이동
        target_path = job_dir / "input.mp3"
        temp_file.rename(target_path)
        
        # 4. job.json 생성 (이 시점에서만!)
        create_job(job_id, source="upload", input_filename=file.filename)
        
        # 5. 백그라운드 처리 시작
        asyncio.create_task(process_job(job_id))
        
        return {"job_id": job_id}
        
    except AppError:
        raise  # AppError는 그대로 전파
    finally:
        # 검증 실패 시 임시 디렉토리 정리
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
```

**디렉토리 생성 정책 요약:**

| 단계 | 디렉토리 | job.json | 실패 시 동작 |
|------|---------|----------|-------------|
| 스트리밍 저장 중 | `_temp_{uuid}/` ✅ | ❌ 없음 | `_temp_{uuid}/` 삭제 |
| 크기/형식 검증 중 | `_temp_{uuid}/` ✅ | ❌ 없음 | `_temp_{uuid}/` 삭제 |
| 검증 통과 후 | `{job_id}/` ✅ | ✅ 생성 | job.json에 에러 기록 |

> **SSOT**: `job.json`이 존재하면 "검증을 통과한 유효한 Job"입니다.
> `job.json`이 없으면 해당 디렉토리는 임시 또는 고아 디렉토리입니다.

### 오디오 검증 함수 (SSOT - H10)

```python
# core/audio_validation.py
import subprocess
from pathlib import Path
import librosa

class AudioValidationError(Exception):
    """오디오 검증 실패"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

def is_valid_audio(file_path: Path) -> bool:
    """
    오디오 파일 유효성 검증 (SSOT 함수)
    
    검증 항목:
    1. 파일 존재 + 크기 > 0
    2. ffprobe로 디코딩 가능 여부 확인
    3. librosa로 로드 가능 + duration 확인
    
    Returns:
        True if valid, False otherwise
    """
    try:
        validate_audio_file(file_path)
        return True
    except AudioValidationError:
        return False


def validate_audio_file(file_path: Path) -> dict:
    """
    오디오 파일 상세 검증 (에러 코드 반환용)
    
    Returns:
        {"duration": float, "sample_rate": int} if valid
        
    Raises:
        AudioValidationError with specific code
    """
    # 1. 파일 존재 확인
    if not file_path.exists():
        raise AudioValidationError("FILE_NOT_FOUND", "파일이 존재하지 않습니다")
    
    # 2. 파일 크기 확인
    if file_path.stat().st_size == 0:
        raise AudioValidationError("EMPTY_FILE", "파일이 비어있습니다")
    
    # 3. ffprobe로 디코딩 가능 여부 확인 (더 빠름)
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", 
             "format=duration", "-of", "csv=p=0", str(file_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise AudioValidationError(
                "DECODE_FAILED", 
                f"오디오 파일을 디코딩할 수 없습니다: {result.stderr[:100]}"
            )
    except subprocess.TimeoutExpired:
        raise AudioValidationError("DECODE_TIMEOUT", "오디오 분석 시간 초과")
    except FileNotFoundError:
        # ffprobe 없으면 librosa만 사용
        pass
    
    # 4. librosa로 실제 로드 테스트 + duration 확인
    try:
        duration = librosa.get_duration(path=str(file_path))
    except Exception as e:
        raise AudioValidationError(
            "DECODE_FAILED",
            f"오디오 파일을 로드할 수 없습니다: {str(e)[:100]}"
        )
    
    # 5. Duration 검증
    if duration <= 0:
        raise AudioValidationError("ZERO_DURATION", "오디오 길이가 0입니다")
    
    if duration < 1.0:
        raise AudioValidationError("TOO_SHORT", "오디오가 너무 짧습니다 (최소 1초)")
    
    if duration > 1200:  # 20분
        raise AudioValidationError("AUDIO_TOO_LONG", "오디오가 20분을 초과합니다")
    
    return {"duration": duration, "sample_rate": 22050}  # librosa 기본 sr
```

### 엣지 케이스 처리 정책 (H8, H9)

| 상황 | 에러 코드 | HTTP | 동작 |
|------|----------|------|------|
| 오디오 파일 손상 (디코딩 실패) | `DECODE_FAILED` | 400 | Job 생성 안 함 |
| 무음 오디오 (duration > 0, notes = 0) | `NO_NOTES_DETECTED` | 500 | Job FAILED |
| Basic Pitch 빈 결과 | `NO_NOTES_DETECTED` | 500 | Job FAILED |
| BPM 감지 실패 (0 또는 NaN) | - | - | 기본값 120 BPM 사용 + `bpm_confidence: 0` |
| Key 감지 실패 | - | - | 기본값 "C major" 사용 + `key_confidence: 0` |
| YouTube 오디오 없음 | `NO_AUDIO_TRACK` | 400 | Job 생성 안 함 |

**처리 코드 예시:**

```python
# core/processing.py

async def process_audio(job_id: str, audio_path: Path):
    """오디오 처리 (엣지 케이스 포함)"""
    
    # 1. Basic Pitch 실행
    midi_result = await run_basic_pitch(audio_path)
    
    # 2. Note 추출
    notes = parse_midi(midi_result.output_path)
    
    # 3. Empty notes 체크 (CRITICAL)
    if not notes or len(notes) == 0:
        update_job_status(job_id, {
            "status": "failed",
            "error": "음악에서 음표를 감지할 수 없습니다. 다른 파일을 시도해 주세요.",
            "error_code": "NO_NOTES_DETECTED"
        })
        raise ProcessingError("NO_NOTES_DETECTED")
    
    # 4. BPM 감지 (폴백 포함)
    bpm, bpm_confidence = detect_bpm(audio_path)
    if bpm is None or bpm <= 0 or math.isnan(bpm):
        bpm = 120.0  # 기본값
        bpm_confidence = 0.0
        logger.warning(f"BPM detection failed for {job_id}, using default 120")
    
    # 5. Key 감지 (폴백 포함)
    key, key_confidence = detect_key(audio_path)
    if key is None:
        key = "C major"  # 기본값
        key_confidence = 0.0
        logger.warning(f"Key detection failed for {job_id}, using default C major")
    
    return ProcessingResult(notes=notes, bpm=bpm, key=key, ...)
```

**YouTube 다운로드 후 검증:**

```python
# core/youtube.py

async def download_youtube_audio(job_id: str, url: str) -> Path:
    """YouTube 오디오 다운로드 + 검증"""
    
    output_path = get_job_dir(job_id) / "input.mp3"
    
    # 1. yt-dlp 다운로드
    await run_ytdlp(url, output_path)
    
    # 2. 다운로드 후 검증 (CRITICAL)
    try:
        info = validate_audio_file(output_path)
    except AudioValidationError as e:
        if e.code == "ZERO_DURATION":
            # 오디오 트랙 없음으로 처리
            update_job_status(job_id, {
                "status": "failed",
                "error": "이 영상에는 오디오 트랙이 없습니다.",
                "error_code": "NO_AUDIO_TRACK"
            })
        raise
    
    return output_path
```

> **SSOT**: 모든 오디오 파일은 처리 전 `validate_audio_file()`로 검증하고,
> 빈 결과 / 무음은 명확한 에러 메시지와 함께 FAILED 처리해야 합니다.

| Stage | 생성 파일 | 생성 시점 | 완료 조건 |
|-------|----------|----------|----------|
| PENDING | `job.json` | **검증 통과 후** Job 생성 시 | job.json 존재 |
| DOWNLOADING | `input.mp3` | yt-dlp 완료 후 | input.mp3 존재 + 크기 > 0 |
| PROCESSING | `raw.mid` | Basic Pitch 완료 후 | raw.mid 존재 |
| PROCESSING | `melody.mid` | 멜로디 추출 완료 후 | melody.mid 존재 |
| ANALYZING | `analysis.json` | 분석 완료 후 | analysis.json 존재 + 유효한 JSON |
| GENERATING | `sheet_*.musicxml` | 각 난이도 생성 완료 후 | 3개 파일 모두 존재 |
| COMPLETED | (없음) | 모든 파일 생성 완료 | 위 모든 파일 존재 |

**실패 시 정리 정책:**

| 실패 시점 | 남기는 파일 | 삭제하는 파일 | 이유 |
|----------|------------|--------------|------|
| 검증 실패 (업로드 전) | 없음 | 없음 (디렉토리 자체 없음) | job.json 미생성 |
| DOWNLOADING 실패 | `job.json` | 부분 다운로드 파일 | 재시도 불가, 에러 기록 유지 |
| PROCESSING 실패 | `job.json`, `input.mp3` | 부분 MIDI | 입력은 유지, 중간 산출물 삭제 |
| ANALYZING 실패 | `job.json`, `input.mp3`, `raw.mid`, `melody.mid` | 부분 analysis.json | MIDI까지는 유지 |
| GENERATING 실패 | 위 + `analysis.json` | 부분 musicxml | 분석까지는 유지 |

**파일 존재 확인 함수 (Golden Test/Smoke 검증용):**
```python
def verify_job_outputs(job_dir: Path, mode: str = "full") -> dict:
    """
    Job 산출물 존재 확인
    
    Args:
        job_dir: Job 디렉토리 경로
        mode: "full" (모든 파일) 또는 "smoke" (필수 파일만)
    
    Returns:
        {"valid": bool, "missing": list[str], "present": list[str]}
    """
    required_files = {
        "smoke": ["job.json", "input.mp3", "melody.mid"],
        "full": ["job.json", "input.mp3", "raw.mid", "melody.mid", 
                 "analysis.json", "sheet_easy.musicxml", 
                 "sheet_medium.musicxml", "sheet_hard.musicxml"]
    }
    
    files_to_check = required_files[mode]
    present = [f for f in files_to_check if (job_dir / f).exists()]
    missing = [f for f in files_to_check if f not in present]
    
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "present": present
    }
```

**불변 조건 (COMPLETED 상태에서):**
- `job.json`의 `status == "completed"`
- `job.json`의 `progress == 100`
- 위 표의 모든 파일이 존재
- `analysis.json`이 유효한 JSON이고 `AnalysisSchema`에 맞음
- `sheet_*.musicxml`이 유효한 XML

### job.json 스키마 (필수 필드 정의)

```python
# Pydantic 모델 정의
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class JobSchema(BaseModel):
    """job.json 파일 스키마"""
    
    # 필수 필드
    job_id: str                    # UUID v4
    status: Literal["pending", "downloading", "processing", "analyzing", "generating", "completed", "failed"]
    progress: int                  # 0-100 (전체 Job 기준)
    created_at: datetime           # ISO 8601 형식 (UTC, "Z" 접미사)
    updated_at: datetime           # ISO 8601 형식 (UTC, "Z" 접미사)
    
    # 입력 소스 (둘 중 하나만 존재)
    source: Literal["upload", "youtube"]
    input_filename: Optional[str] = None    # upload인 경우 원본 파일명
    youtube_url: Optional[str] = None       # youtube인 경우 URL
    youtube_title: Optional[str] = None     # youtube인 경우 영상 제목
    
    # 처리 정보
    duration_seconds: Optional[float] = None  # 오디오 길이 (초)
    current_stage: Optional[str] = None       # 현재 단계 설명 (UI 표시용)
    
    # 에러 정보 (status=failed인 경우)
    error: Optional[str] = None
    error_code: Optional[str] = None
    
    # 재생성 버전 (PUT 요청 레이스 컨디션 방지)
    regeneration_version: int = 0  # PUT 요청마다 +1 증가

# job.json 예시
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "progress": 35,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:31:00Z",
    "source": "upload",
    "input_filename": "my_song.mp3",
    "youtube_url": null,
    "youtube_title": null,
    "duration_seconds": 180.5,
    "current_stage": "Basic Pitch 변환 중",
    "error": null,
    "error_code": null,
    "regeneration_version": 0
}
```

**job.json 업데이트 규칙:**
- **원자적 쓰기**: 임시 파일에 쓴 후 `rename()`으로 교체 (읽기 중 깨진 파일 방지)
- **업데이트 시점**: 상태 변경, 진행률 변경, 에러 발생 시
- **동시성**: 단일 Job은 단일 Task에서만 처리 (락 불필요)

```python
def update_job_status(job_id: str, updates: dict):
    """
    원자적 job.json 업데이트 (SSOT 함수)
    
    Args:
        job_id: Job UUID 문자열
        updates: 업데이트할 필드 딕셔너리
                 예: {"status": "processing", "progress": 20}
    
    Note:
        - job_dir은 내부에서 JOB_STORAGE_PATH / job_id로 계산
        - 모든 job 상태 업데이트는 이 함수를 통해서만 수행
    """
    from config import JOB_STORAGE_PATH
    
    job_dir = JOB_STORAGE_PATH / job_id
    job_path = job_dir / "job.json"
    temp_path = job_dir / "job.json.tmp"
    
    # 현재 상태 읽기
    job = json.loads(job_path.read_text())
    
    # 업데이트 적용
    job.update(updates)
    job["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # 원자적 쓰기
    temp_path.write_text(json.dumps(job, indent=2))
    temp_path.replace(job_path)
```

### PUT 재생성 레이스 컨디션 방지 (CRITICAL)

PUT `/api/result/{job_id}` 요청으로 analysis.json 수정 → MusicXML 재생성 시, 
동시에 여러 요청이 들어오면 "이전 요청이 나중에 덮어쓰기" 문제가 발생할 수 있습니다.

**해결책: regeneration_version 기반 낙관적 락**

```python
# api/result.py

@router.put("/result/{job_id}")
async def update_result(job_id: str, data: AnalysisUpdateRequest):
    """
    analysis.json 수정 및 MusicXML 재생성
    
    레이스 컨디션 방지:
    1. PUT 요청 시 regeneration_version 증가
    2. 재생성 태스크가 시작 시점의 버전을 캡처
    3. 파일 쓰기 전 현재 버전과 비교 → 불일치 시 스킵
    """
    job = load_job(job_id)
    
    # 1. 버전 증가 (원자적)
    new_version = job.regeneration_version + 1
    update_job_status(job_id, {
        "regeneration_version": new_version,
        "status": "generating",
        "progress": convert_stage_progress("upload", "generating", 0)
    })
    
    # 2. 백그라운드 재생성 (버전 캡처)
    asyncio.create_task(regenerate_sheets(job_id, captured_version=new_version))
    
    return {"job_id": job_id, "regeneration_version": new_version}


async def regenerate_sheets(job_id: str, captured_version: int):
    """
    MusicXML 재생성 (버전 검증 포함)
    """
    try:
        # ... 재생성 로직 ...
        
        # 3. 파일 쓰기 전 버전 검증
        current_job = load_job(job_id)
        if current_job.regeneration_version != captured_version:
            # 새로운 PUT 요청이 들어왔으므로 현재 작업 스킵
            logger.info(f"Skipping stale regeneration: {captured_version} < {current_job.regeneration_version}")
            return
        
        # 버전 일치 → 파일 쓰기 진행
        for difficulty in ["easy", "medium", "hard"]:
            write_musicxml_atomic(job_id, difficulty, content, captured_version)
        
        update_job_status(job_id, {"status": "completed", "progress": 100})
        
    except Exception as e:
        update_job_status(job_id, {"status": "failed", "error": str(e)})


def write_musicxml_atomic(job_id: str, difficulty: str, content: str, expected_version: int):
    """
    MusicXML 원자적 쓰기 (버전 재검증)
    """
    job = load_job(job_id)
    if job.regeneration_version != expected_version:
        raise StaleVersionError(f"Version mismatch: {expected_version} != {job.regeneration_version}")
    
    job_dir = JOB_STORAGE_PATH / job_id
    target = job_dir / f"sheet_{difficulty}.musicxml"
    temp = job_dir / f"sheet_{difficulty}.musicxml.tmp"
    
    temp.write_text(content)
    temp.replace(target)
```

> **SSOT**: 모든 PUT 재생성 요청은 `regeneration_version`을 증가시키고, 
> 파일 쓰기 전 반드시 버전을 재검증해야 합니다.

### 원자적 파일 쓰기 정책 (SSOT - 모든 산출물 적용)

> **CRITICAL**: 모든 파일 생성은 `tmp → replace()` 패턴을 사용해야 합니다.
> 이는 부분 파일 / 손상된 파일 문제를 방지합니다.

| 파일 | 생성 시점 | 원자적 쓰기 적용 |
|------|----------|-----------------|
| `job.json` | Job 상태 변경 시 | ✅ 필수 (update_job_status 함수) |
| `raw.mid` | Basic Pitch 완료 후 | ✅ 필수 |
| `melody.mid` | 멜로디 추출 완료 후 | ✅ 필수 |
| `analysis.json` | 분석 완료 후 | ✅ 필수 |
| `sheet_*.musicxml` | 생성 완료 후 | ✅ 필수 |

```python
def write_file_atomic(target_path: Path, content: bytes | str):
    """
    원자적 파일 쓰기 (SSOT 함수)
    
    모든 파일 생성에 이 함수를 사용하세요.
    직접 file.write_bytes() / file.write_text() 사용 금지!
    
    Args:
        target_path: 최종 파일 경로
        content: 파일 내용 (bytes 또는 str)
    """
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    
    try:
        if isinstance(content, bytes):
            temp_path.write_bytes(content)
        else:
            temp_path.write_text(content)
        
        # 원자적 교체 (POSIX에서 보장)
        temp_path.replace(target_path)
    finally:
        # 실패 시 임시 파일 정리
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


# 사용 예시
write_file_atomic(job_dir / "raw.mid", midi_bytes)
write_file_atomic(job_dir / "analysis.json", json.dumps(analysis, indent=2))
write_file_atomic(job_dir / "sheet_easy.musicxml", musicxml_str)
```

> **Must NOT do**:
> - `path.write_bytes(content)` 직접 호출 (부분 쓰기 위험)
> - `path.write_text(content)` 직접 호출 (부분 쓰기 위험)
> - 원자적 쓰기 없이 파일 생성

### analysis.json 스키마

```python
class ChordInfo(BaseModel):
    time: float           # 시작 시간 (초)
    duration: float       # 길이 (초)
    chord: str            # 코드명 (예: "C", "Am", "G7")
    confidence: float     # 신뢰도 (0.0-1.0)

class AnalysisSchema(BaseModel):
    """analysis.json 파일 스키마 (= API 응답과 동일)"""
    
    bpm: float                    # 감지된 BPM
    bpm_confidence: float         # BPM 신뢰도 (0.0-1.0)
    key: str                      # 조성 (아래 Key 표기 규칙 참조)
    key_confidence: float         # Key 신뢰도 (0.0-1.0)
    chords: list[ChordInfo]       # 코드 진행

# analysis.json 예시
{
    "bpm": 120.0,
    "bpm_confidence": 0.85,
    "key": "C major",
    "key_confidence": 0.72,
    "chords": [
        {"time": 0.0, "duration": 2.0, "chord": "C", "confidence": 0.9},
        {"time": 2.0, "duration": 2.0, "chord": "Am", "confidence": 0.85},
        {"time": 4.0, "duration": 4.0, "chord": "F", "confidence": 0.78}
    ]
}
```

**analysis.json과 API 응답의 관계:**
- **analysis.json**: 파일 저장 포맷 (AnalysisSchema)
- **API 응답**: Wrapper 형태 (job 메타데이터 + analysis + 다운로드 URL 포함)
- **관계**: `GET /api/result/{job_id}`는 analysis.json을 읽어서 wrapper로 감싸 반환

```python
# API 응답 구조 (GET /api/result/{job_id})
{
    "job_id": str,
    "status": str,
    "analysis": AnalysisSchema,  # analysis.json 내용
    "available_difficulties": ["easy", "medium", "hard"],
    "musicxml_url": str,
    "midi_url": str
}
```

### Key 표기 규칙 (허용 포맷)

```python
# 허용되는 Key 문자열 목록
ALLOWED_KEYS = [
    # Major keys
    "C major", "C# major", "Db major", "D major", "D# major", "Eb major",
    "E major", "F major", "F# major", "Gb major", "G major", "G# major",
    "Ab major", "A major", "A# major", "Bb major", "B major",
    # Minor keys
    "C minor", "C# minor", "Db minor", "D minor", "D# minor", "Eb minor",
    "E minor", "F minor", "F# minor", "Gb minor", "G minor", "G# minor",
    "Ab minor", "A minor", "A# minor", "Bb minor", "B minor",
]

def normalize_key(key_str: str) -> str:
    """
    다양한 입력을 정규 포맷으로 변환
    예: "Am" → "A minor", "C" → "C major", "c#m" → "C# minor"
    """
    key_str = key_str.strip()
    
    # 축약형 처리
    if key_str.endswith('m') and not key_str.endswith('major') and not key_str.endswith('minor'):
        root = key_str[:-1]
        mode = "minor"
    else:
        root = key_str.replace(" major", "").replace(" minor", "")
        mode = "minor" if "minor" in key_str.lower() or key_str.endswith('m') else "major"
    
    # 대문자 정규화
    root = root[0].upper() + root[1:] if len(root) > 1 else root.upper()
    
    return f"{root} {mode}"

# music21 변환
def key_to_music21(key_str: str) -> music21.key.Key:
    """정규화된 key 문자열을 music21 Key 객체로 변환"""
    normalized = normalize_key(key_str)
    # music21은 "C major", "A minor" 형식을 직접 파싱 가능
    return music21.key.Key(normalized)
```

**API 입력 시 Key 처리:**
- 사용자가 "Am", "A minor", "a minor" 등 다양한 형태로 입력 가능
- 서버에서 `normalize_key()`로 정규화 후 저장
- 응답은 항상 정규 포맷 ("A minor")

### Job Lifecycle

**실행 모델 결정: `asyncio.create_task()` + `run_in_executor`**

> ⚠️ **주의**: FastAPI의 `BackgroundTasks`는 사용하지 않습니다.
> - `BackgroundTasks`는 응답 후 실행되어 진행률 추적이 어려움
> - `asyncio.create_task()`는 즉시 실행되어 상태 업데이트 가능

> ⚠️ **CRITICAL: 단일 워커 필수 (--workers 1)**
> - `asyncio.create_task()` 기반 Job 시스템은 **단일 프로세스**에서만 동작합니다.
> - 멀티 워커 사용 시 Job 상태가 프로세스 간 공유되지 않아 작업이 유실됩니다.
> - Docker CMD, 개발 환경 모두 `--workers 1` 또는 기본값(1) 사용 필수
> - 스케일 아웃이 필요하면 Celery + Redis로 아키텍처 변경 필요 (본 프로젝트 범위 외)

**구현 방식:**
```python
# job_manager.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

# CPU-bound 작업용 executor (Basic Pitch, librosa 등)
executor = ThreadPoolExecutor(max_workers=3)

# 동시 처리 제한
semaphore = asyncio.Semaphore(3)

async def process_job(job_id: str, source: str):
    """
    Job 처리 메인 함수
    
    Args:
        job_id: Job UUID
        source: "youtube" 또는 "upload" (progress 범위 결정)
    """
    async with semaphore:  # 최대 3개 동시 처리
        try:
            # CPU-bound 작업은 executor에서 실행
            loop = asyncio.get_event_loop()
            
            # 1. Basic Pitch (CPU-bound)
            # SSOT: convert_stage_progress() 사용 (하드코딩 금지!)
            update_job_status(job_id, {
                "status": "processing",
                "progress": convert_stage_progress(source, "processing", 0)
            })
            midi_path = await loop.run_in_executor(
                executor, 
                run_basic_pitch, 
                audio_path
            )
            
            # 2. 분석 (CPU-bound)
            update_job_status(job_id, {
                "status": "analyzing",
                "progress": convert_stage_progress(source, "analyzing", 0)
            })
            analysis = await loop.run_in_executor(
                executor,
                run_analysis,
                audio_path
            )
            
            # ... 나머지 단계
            
        except Exception as e:
            update_job_status(job_id, {"status": "failed", "error": str(e)})

# API에서 호출
@router.post("/upload")
async def upload_file(file: UploadFile):
    job_id = create_job(...)
    
    # 백그라운드 태스크 시작 (응답 전에 시작됨)
    asyncio.create_task(process_job(job_id))
    
    return {"job_id": job_id, "status": "pending"}
```

**왜 이 방식인가:**
| 방식 | 장점 | 단점 | 선택 |
|------|------|------|------|
| `BackgroundTasks` | 간단함 | 응답 후 실행, 진행률 추적 어려움 | ❌ |
| `asyncio.create_task()` | 즉시 실행, 상태 추적 용이 | 약간 복잡 | ✅ |
| Celery | 분산 처리, 재시도 | 과도한 복잡성 (Redis 필요) | ❌ |

**핵심 포인트:**
- **생성**: UUID v4로 job_id 생성, job.json 초기화
- **실행**: `asyncio.create_task()`로 즉시 백그라운드 실행
- **CPU-bound**: `run_in_executor()`로 이벤트 루프 블로킹 방지
- **동시성**: `asyncio.Semaphore(3)`으로 최대 3개 동시 처리
- **재시작**: 서버 재시작 시 `JOB_STORAGE_PATH` 스캔하여 `status != completed|failed`인 job은 FAILED로 마킹

### 단일 프로세스 아키텍처 (CRITICAL)

> **이 프로젝트는 단일 프로세스에서만 동작합니다.**
> 멀티 프로세스/워커 환경에서는 Job 상태 불일치가 발생합니다.

**운영 환경 (Docker):**
```bash
# ✅ 올바른 실행 방법 (단일 워커)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

# ❌ 금지: 멀티 워커 (Job 상태 불일치 발생)
uvicorn main:app --workers 4  # 절대 사용 금지!
```

**개발 환경 (로컬):**
```bash
# ✅ 허용: 리로드 없이 실행
uvicorn main:app --host 0.0.0.0 --port 8000

# ⚠️ 주의: 리로드 모드 (제한적 허용)
uvicorn main:app --reload
# --reload는 파일 변경 시 프로세스를 재시작합니다.
# 재시작 시점에 진행 중인 Job은 중단되며 FAILED로 마킹됩니다.
# Job 처리 중에는 파일 수정을 피하세요.

# ❌ 금지: 리로드 + 멀티 워커 조합
uvicorn main:app --reload --workers 2  # 절대 사용 금지!
```

**왜 단일 프로세스인가:**
| 아키텍처 | Job 상태 관리 | 복잡도 | 선택 |
|----------|--------------|--------|------|
| 단일 프로세스 | 메모리 내 상태 + 파일 (간단) | 낮음 | ✅ |
| 멀티 워커 | Redis/DB 필요 (동기화) | 높음 | ❌ |
| Celery 큐 | Redis + Worker 필요 | 매우 높음 | ❌ |

> **Escalation 조건**: 동시 처리 Job이 많아지거나 서버 재시작 시 작업 유실이 
> 용납되지 않을 때만 Celery/Redis 전환을 검토하세요.

### Job TTL (자동 삭제) 구현 방식

> **CRITICAL**: 파일 I/O는 동기 작업이므로 이벤트 루프를 블로킹합니다.
> 반드시 `asyncio.to_thread()`를 사용하여 별도 스레드에서 실행하세요.

```python
# 앱 시작 시 cleanup 루프 등록
@app.on_event("startup")
async def start_cleanup_loop():
    asyncio.create_task(cleanup_expired_jobs())

# 진행 중인 상태 목록 (삭제 대상에서 제외)
IN_PROGRESS_STATUSES = {"pending", "downloading", "processing", "analyzing", "generating"}

async def cleanup_expired_jobs():
    """10분마다 실행되는 청소 루프 (논블로킹)"""
    from config import JOB_STORAGE_PATH  # SSOT: 환경변수 기반 경로
    
    while True:
        await asyncio.sleep(600)  # 10분
        
        # 동기 I/O를 별도 스레드에서 실행 (이벤트 루프 블로킹 방지)
        await asyncio.to_thread(_cleanup_sync, JOB_STORAGE_PATH)


def _cleanup_sync(storage_path: Path):
    """
    실제 삭제 로직 (동기 함수, to_thread에서 실행)
    
    삭제 기준:
    1. updated_at 기준 1시간 경과 (created_at 아님!)
    2. 진행 중인 상태(IN_PROGRESS_STATUSES)는 스킵
    3. 배치 처리: 한 번에 최대 10개만 삭제 (과부하 방지)
    """
    if not storage_path.exists():
        return
    
    now = datetime.now(timezone.utc)
    deleted_count = 0
    max_deletions_per_cycle = 10  # 배치 상한
    
    for job_dir in storage_path.iterdir():
        if deleted_count >= max_deletions_per_cycle:
            break  # 다음 주기에 계속
        
        job_json = job_dir / "job.json"
        if not job_json.exists():
            # job.json 없는 고아 디렉토리 → 삭제
            shutil.rmtree(job_dir, ignore_errors=True)
            deleted_count += 1
            continue
        
        try:
            job = json.loads(job_json.read_text())
            
            # 진행 중인 job은 스킵
            if job.get("status") in IN_PROGRESS_STATUSES:
                continue
            
            # updated_at 기준 TTL 체크 (created_at 아님!)
            updated_str = job["updated_at"].replace("Z", "+00:00")
            updated = datetime.fromisoformat(updated_str)
            
            if (now - updated).total_seconds() > 3600:  # 1시간 경과
                shutil.rmtree(job_dir, ignore_errors=True)
                deleted_count += 1
                
        except (json.JSONDecodeError, KeyError):
            # 손상된 job.json → 삭제
            shutil.rmtree(job_dir, ignore_errors=True)
            deleted_count += 1
```

> **SSOT**: `JOB_STORAGE_PATH`는 `backend/config.py`에서 정의되며, 모든 Job 관련 경로는 이 변수를 참조해야 합니다.
> 하드코딩된 `/tmp/piano-sheet-jobs`는 사용하지 마세요.

**삭제 정책**:
- **updated_at 기준** 1시간 경과한 job 디렉토리 전체 삭제 (created_at 아님!)
- **진행 중 상태 스킵**: pending, downloading, processing, analyzing, generating 상태는 삭제하지 않음
- 삭제 실패 시 (파일 락 등) `ignore_errors=True`로 다음 주기에 재시도
- 삭제 순서: 디렉토리 전체를 `shutil.rmtree`로 원자적 삭제
- **배치 상한**: 한 주기에 최대 10개만 삭제 (시스템 과부하 방지)

---

## Time Unit Convention (시간 단위 표준)

### MIDI 라이브러리 책임 분리 (SSOT)

> **중요**: MIDI 읽기와 MusicXML 생성에 서로 다른 라이브러리를 사용합니다.
> 이는 각 라이브러리의 강점을 활용하기 위함입니다.

| 용도 | 라이브러리 | 이유 |
|------|-----------|------|
| **MIDI → Note 리스트** | `pretty_midi` | 빠름, 초 단위 직접 지원, tempo map 자동 처리 |
| **Note 리스트 → MusicXML** | `music21` | MusicXML 생성 전문, 악보 표기법 지원 |

```python
# core/midi_parser.py
import pretty_midi
from dataclasses import dataclass
from typing import List

@dataclass
class Note:
    pitch: int          # MIDI pitch (0-127, 60=C4)
    onset: float        # 시작 시간 (초)
    duration: float     # 길이 (초)
    velocity: int       # 세기 (0-127)

def parse_midi(midi_path: str) -> List[Note]:
    """
    MIDI 파일 → Note 리스트 변환 (SSOT 함수)
    
    사용 라이브러리: pretty_midi (music21 아님!)
    - pretty_midi는 tempo map을 자동으로 처리하여 초 단위로 반환
    - music21은 quarterLength 단위라 BPM 정보가 필요
    """
    pm = pretty_midi.PrettyMIDI(midi_path)
    notes = []
    
    for instrument in pm.instruments:
        if instrument.is_drum:
            continue  # 드럼 제외
        for note in instrument.notes:
            notes.append(Note(
                pitch=note.pitch,
                onset=note.start,      # 이미 초 단위
                duration=note.end - note.start,
                velocity=note.velocity
            ))
    
    # 시작 시간 기준 정렬
    notes.sort(key=lambda n: (n.onset, n.pitch))
    return notes
```

> **Must NOT do**:
> - MIDI 파싱에 `music21.converter.parse()` 사용 (BPM 종속성 문제)
> - MusicXML 생성에 `pretty_midi` 사용 (지원 안 함)

### 프로젝트 전체 표준: 초(seconds) 기반
모든 내부 데이터 모델은 **초(seconds, float)** 단위를 사용합니다.

### Note 데이터 모델
```python
@dataclass
class Note:
    pitch: int          # MIDI pitch (0-127, 60=C4)
    onset: float        # 시작 시간 (초)
    duration: float     # 길이 (초)
    velocity: int       # 세기 (0-127)
```

### 단위 변환 함수
```python
def seconds_to_quarter_length(seconds: float, bpm: float) -> float:
    """초 → quarterLength (music21용)"""
    beats_per_second = bpm / 60
    return seconds * beats_per_second

def quarter_length_to_seconds(ql: float, bpm: float) -> float:
    """quarterLength → 초"""
    beats_per_second = bpm / 60
    return ql / beats_per_second

def ms_to_seconds(ms: float) -> float:
    return ms / 1000

def seconds_to_ms(seconds: float) -> float:
    return seconds * 1000
```

### 변환 지점
| 모듈 | 입력 단위 | 내부 처리 | 출력 단위 |
|------|----------|----------|----------|
| Basic Pitch | - | 초 (note_events) | 초 |
| 멜로디 추출 | 초 | 초 | 초 |
| BPM/Key 분석 | - | 초 (librosa) | 초 |
| music21 변환 | 초 | quarterLength (변환) | MusicXML |
| Golden Test | 초 | 초 | 초 |
| API 응답 | 초 | - | 초 |

### music21 입출력 시 변환
```python
# MIDI → Note 리스트 (초 단위)
def midi_to_notes(midi_path: str, bpm: float) -> List[Note]:
    score = converter.parse(midi_path)
    notes = []
    for n in score.flat.notes:
        onset_seconds = quarter_length_to_seconds(n.offset, bpm)
        duration_seconds = quarter_length_to_seconds(n.duration.quarterLength, bpm)
        notes.append(Note(pitch=n.pitch.midi, onset=onset_seconds, duration=duration_seconds, velocity=n.volume.velocity or 64))
    return notes

# Note 리스트 → MusicXML (quarterLength 변환)
def notes_to_musicxml(notes: List[Note], bpm: float, key: str) -> str:
    stream = music21.stream.Stream()
    stream.append(music21.tempo.MetronomeMark(number=bpm))
    stream.append(music21.key.Key(key))
    for n in notes:
        m21_note = music21.note.Note(n.pitch)
        m21_note.offset = seconds_to_quarter_length(n.onset, bpm)
        m21_note.duration.quarterLength = seconds_to_quarter_length(n.duration, bpm)
        stream.append(m21_note)
    return stream.write('musicxml')
```

---

## API Schema Definition

### POST /api/upload
**Request**: `multipart/form-data`
```
file: MP3 파일 (max 50MB)
```

**Response 200**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job created successfully"
}
```

**Response 413**:
```json
{
  "error": "File too large",
  "code": "FILE_TOO_LARGE",
  "message": "업로드가 중단되었습니다. 50MB 이하 파일만 업로드 가능합니다.",
  "details": {"max_size_mb": 50}
}
```

**Response 415**:
```json
{
  "error": "Unsupported file type",
  "code": "UNSUPPORTED_FILE_TYPE",
  "message": "MP3 파일만 업로드 가능합니다.",
  "details": {"allowed": ["audio/mpeg", "audio/mp3"]}
}
```

### POST /api/youtube
**Request**: `application/json`
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response 200**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Job created successfully",
  "video_title": "Rick Astley - Never Gonna Give You Up",
  "duration_seconds": 213
}
```

**Response 400** (잘못된 URL):
```json
{
  "error": "Invalid YouTube URL",
  "code": "INVALID_YOUTUBE_URL",
  "message": "올바른 YouTube URL을 입력해주세요.",
  "details": null
}
```

**Response 400** (영상 길이 초과):
```json
{
  "error": "Video too long",
  "code": "VIDEO_TOO_LONG",
  "message": "영상이 너무 깁니다. 최대 20분까지 지원합니다.",
  "details": {"max_duration_minutes": 20, "actual_duration_minutes": 25}
}
```

**Response 403**:
```json
{
  "error": "Video is private or age-restricted",
  "code": "VIDEO_UNAVAILABLE",
  "message": "이 영상은 비공개이거나 연령 제한이 있어 다운로드할 수 없습니다.",
  "details": null
}
```

### GET /api/status/{job_id}
**Response 200**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 35,
  "current_stage": "Basic Pitch 변환 중",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:31:00Z"
}
```

**Response 404**:
```json
{
  "error": "Job not found",
  "code": "JOB_NOT_FOUND",
  "message": "요청한 작업을 찾을 수 없습니다.",
  "details": {"job_id": "{job_id}"}
}
```

### GET /api/result/{job_id}
**Response 200** (status=completed):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "analysis": {
    "bpm": 120,
    "bpm_confidence": 0.85,
    "key": "C major",
    "key_confidence": 0.72,
    "chords": [
      {"time": 0.0, "duration": 2.0, "chord": "C", "confidence": 0.9},
      {"time": 2.0, "duration": 2.0, "chord": "Am", "confidence": 0.85}
    ]
  },
  "available_difficulties": ["easy", "medium", "hard"],
  "musicxml_url": "/api/download/{job_id}/musicxml?difficulty=medium",
  "midi_url": "/api/download/{job_id}/midi"
}
```

**Response 200** (status=failed):
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": {
    "error": "Processing failed",
    "code": "PROCESSING_FAILED",
    "message": "멜로디 추출 실패: 유의미한 음표를 감지하지 못했습니다.",
    "details": null
  }
}
```

### PUT /api/result/{job_id}
**Request**: `application/json`
```json
{
  "bpm": 125,
  "key": "G major",
  "chords": [
    {"time": 0.0, "duration": 2.0, "chord": "G"},
    {"time": 2.0, "duration": 2.0, "chord": "Em"}
  ]
}
```

**Response 200**:
```json
{
  "message": "Analysis updated successfully",
  "regenerating": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 400**:
```json
{
  "error": "Job is not in completed state",
  "code": "JOB_NOT_COMPLETED",
  "message": "작업이 아직 완료되지 않았습니다. 완료 후 수정 가능합니다.",
  "details": {"current_status": "processing"}
}
```
**Response 404**:
```json
{
  "error": "Job not found",
  "code": "JOB_NOT_FOUND",
  "message": "요청한 작업을 찾을 수 없습니다.",
  "details": {"job_id": "{job_id}"}
}
```

#### PUT 수정 API 동작 정책

**수정 가능 조건**:
- `status == COMPLETED`일 때만 수정 가능
- 다른 상태에서는 400 에러 반환

**재생성 동작**:
1. 같은 job_id 유지 (새 job 생성 안 함)
2. 상태 전이: `COMPLETED → GENERATING → COMPLETED`
3. 기존 MusicXML 파일 덮어쓰기 (sheet_easy/medium/hard.musicxml)
4. analysis.json 업데이트
5. 재생성 중 다운로드 요청 시: 이전 버전 파일 반환 (락 없음)

**재생성 중 Progress/Status 규칙 (SSOT):**
- **status**: `GENERATING` (재생성 중)
- **progress**: `70` (GENERATING 시작점으로 리셋, 100에서 70으로 감소)
- **current_stage**: `"MusicXML 재생성 중"`
- **완료 시**: status=`COMPLETED`, progress=`100`, current_stage=`"완료"`
- **프론트 폴링**: status가 `GENERATING`이면 "재생성 중" UI 표시, `COMPLETED`가 되면 악보 새로고침

**동시 수정 정책 (SSOT):**
- 마지막 요청만 반영 (last-write-wins)
- 프론트엔드에서 debounce 권장 (500ms)
- **재생성 중 추가 PUT 요청 시**: 즉시 덮어쓰기 (현재 재생성 취소, 새 요청으로 대체)

**재생성 취소/대체 구현 메커니즘 (SSOT):**
```python
# backend/core/job_manager.py

import asyncio
from typing import Dict, Optional

# job_id → 현재 실행 중인 재생성 task 매핑 (전역 dict)
_regeneration_tasks: Dict[str, asyncio.Task] = {}

# job_id → cancellation flag (전역 dict)
_cancellation_flags: Dict[str, bool] = {}


async def regenerate_sheets(job_id: str, analysis: AnalysisSchema):
    """
    MusicXML 재생성 (취소 가능)
    
    취소 체크포인트:
    1. 각 난이도 처리 시작 전
    2. 파일 저장 전
    """
    _cancellation_flags[job_id] = False
    
    try:
        for difficulty in ["easy", "medium", "hard"]:
            # 체크포인트 1: 취소 확인
            if _cancellation_flags.get(job_id, False):
                return  # 조용히 종료 (새 task가 이어받음)
            
            # 난이도별 처리...
            adjusted_notes = adjust_difficulty(notes, difficulty, analysis.bpm)
            stream = notes_to_stream(adjusted_notes, analysis.bpm, analysis.key)
            add_chord_symbols(stream, analysis.chords, analysis.bpm)
            musicxml_str = stream_to_musicxml(stream)
            
            # 체크포인트 2: 파일 저장 전 취소 확인
            if _cancellation_flags.get(job_id, False):
                return
            
            # 원자적 파일 교체
            regenerate_musicxml(job_dir, difficulty, musicxml_str)
        
        # 완료
        update_job_status(job_id, "completed", progress=100)
    finally:
        # 정리
        _cancellation_flags.pop(job_id, None)
        _regeneration_tasks.pop(job_id, None)


async def handle_put_regeneration(job_id: str, new_analysis: AnalysisSchema):
    """
    PUT 요청 처리 - 기존 재생성 취소 후 새 재생성 시작
    """
    # 1. 기존 task가 있으면 취소 플래그 설정
    if job_id in _regeneration_tasks:
        _cancellation_flags[job_id] = True
        # 기존 task가 체크포인트에서 종료될 때까지 잠시 대기 (최대 100ms)
        await asyncio.sleep(0.1)
    
    # 2. 상태 업데이트
    update_job_status(job_id, "generating", progress=70)
    
    # 3. 새 재생성 task 시작
    task = asyncio.create_task(regenerate_sheets(job_id, new_analysis))
    _regeneration_tasks[job_id] = task
```

**핵심 규칙:**
- `_regeneration_tasks`: job_id별 실행 중인 task 추적
- `_cancellation_flags`: job_id별 취소 플래그 (bool)
- 체크포인트: 각 난이도 처리 시작 전, 파일 저장 전
- 취소 시: 조용히 종료 (에러 아님), 새 task가 이어받음
- 파일 교체: 원자적 교체로 중간 상태 파일 없음

**재생성 범위**:
- BPM 변경 시: 모든 MusicXML 재생성 (음표 길이 재계산)
- Key 변경 시: 모든 MusicXML 재생성 (조표 변경)
- Chords 변경 시: 모든 MusicXML 재생성 (코드 심볼 변경)
- MIDI 파일은 재생성하지 않음 (원본 유지)

**파일 교체 정책 (원자적 교체)**:
```python
# 재생성 시 파일 교체 전략
def regenerate_musicxml(job_dir: Path, difficulty: str, new_content: str):
    """
    원자적 파일 교체로 다운로드 중 깨진 파일 방지
    """
    final_path = job_dir / f"sheet_{difficulty}.musicxml"
    temp_path = job_dir / f"sheet_{difficulty}.musicxml.tmp"
    
    # 1. 임시 파일에 새 내용 작성
    temp_path.write_text(new_content)
    
    # 2. 원자적 교체 (rename은 같은 파일시스템에서 원자적)
    temp_path.replace(final_path)
```

**재생성 중 다운로드 동작**:
- 재생성 중 다운로드 요청 시: **현재 존재하는 파일 반환** (이전 버전)
- 원자적 교체 덕분에 부분 작성된 파일을 읽을 위험 없음
- 교체 완료 후 다운로드 요청 시: 새 버전 반환

### GET /api/download/{job_id}/{format}
**Query Parameters**:
- `difficulty`: easy | medium | hard (for musicxml only)

**Response 200**: Binary file with appropriate Content-Type
- MIDI: `audio/midi`
- MusicXML: `application/vnd.recordare.musicxml+xml`

**Response 404**: `{"error": "Job not found or not completed"}`

---

## Frontend-Backend Communication (프론트-백엔드 연결)

### 연결 방식 결정: Next.js API Route Proxy

> **선택**: Next.js의 API Route를 프록시로 사용하여 CORS 문제를 회피합니다.

**이유:**
- 개발/프로덕션 환경 모두 동일한 방식으로 동작
- 브라우저에서 CORS 에러 없음 (same-origin)
- FastAPI에 CORS 설정 불필요 (보안상 이점)

### 프록시 구현 (최종 버전 - 단일 레퍼런스)

> ⚠️ **중요**: 아래 코드가 유일한 정답 구현입니다. 다른 방식은 사용하지 마세요.

```typescript
// frontend/app/api/[...path]/route.ts (Next.js 14 App Router)

import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// ⚠️ CRITICAL: Node.js 런타임 강제 (Edge 런타임 사용 금지!)
// Edge 런타임에서는 request.body 스트림 전달이 제한됨
export const runtime = 'nodejs';

// ⚠️ 캐싱 방지: 모든 프록시 요청은 항상 동적으로 처리
export const dynamic = 'force-dynamic';
export const fetchCache = 'force-no-store';

/**
 * GET 프록시 (상태 조회, 다운로드 등)
 * - 캐싱 완전 비활성화 (폴링 지원)
 * - 응답 헤더 그대로 전달 (다운로드 지원)
 */
export async function GET(
  request: NextRequest, 
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/');
  const url = new URL(request.url);
  const backendUrl = `${BACKEND_URL}/api/${path}${url.search}`;
  
  const response = await fetch(backendUrl, {
    cache: 'no-store',  // 캐싱 완전 비활성화
  });
  
  // 응답 헤더를 그대로 복사 (Content-Type, Content-Disposition 보존)
  const headers = new Headers();
  response.headers.forEach((value, key) => {
    headers.set(key, value);
  });
  // 캐싱 방지 헤더 추가
  headers.set('Cache-Control', 'no-store, no-cache, must-revalidate');
  
  return new Response(response.body, {
    status: response.status,
    headers: headers,
  });
}

/**
 * POST 프록시 (업로드, YouTube 제출 등)
 * - 멀티파트/JSON 모두 지원
 * - 스트림 전달로 메모리 절약
 */
export async function POST(
  request: NextRequest, 
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/');
  const backendUrl = `${BACKEND_URL}/api/${path}`;
  
  // Content-Type 헤더를 그대로 전달 (boundary 포함)
  const contentType = request.headers.get('Content-Type');
  
  const response = await fetch(backendUrl, {
    method: 'POST',
    body: request.body,  // 스트림 그대로 전달
    headers: contentType ? { 'Content-Type': contentType } : {},
    // @ts-ignore - Next.js에서 body 스트림 전달 허용
    duplex: 'half',
    cache: 'no-store',
  });
  
  // 응답 헤더 그대로 전달
  const headers = new Headers();
  response.headers.forEach((value, key) => {
    headers.set(key, value);
  });
  
  return new Response(response.body, {
    status: response.status,
    headers: headers,
  });
}

/**
 * PUT 프록시 (분석 결과 수정)
 * - JSON 바디 전달
 */
export async function PUT(
  request: NextRequest, 
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join('/');
  const backendUrl = `${BACKEND_URL}/api/${path}`;
  
  const response = await fetch(backendUrl, {
    method: 'PUT',
    body: request.body,
    headers: {
      'Content-Type': request.headers.get('Content-Type') || 'application/json',
    },
    // @ts-ignore
    duplex: 'half',
    cache: 'no-store',
  });
  
  const headers = new Headers();
  response.headers.forEach((value, key) => {
    headers.set(key, value);
  });
  
  return new Response(response.body, {
    status: response.status,
    headers: headers,
  });
}
```

### 프록시 정책 요약

| 항목 | 정책 |
|------|------|
| **캐싱** | **완전 비활성화** (`force-dynamic`, `no-store`) |
| **요청 헤더** | `Content-Type`만 전달 |
| **응답 헤더** | **모두 그대로 전달** (Content-Type, Content-Disposition 포함) |
| **요청 바디** | `request.body` 스트림 전달 (메모리 절약) |
| **응답 바디** | `response.body` 스트림 그대로 전달 |
| **Runtime** | Node.js (Edge 아님) |

### 캐싱 방지가 중요한 이유

`/api/status/{job_id}` 폴링 시 캐싱이 활성화되면:
- 진행률이 업데이트되지 않는 것처럼 보임
- 사용자가 처리가 멈춘 것으로 오해

**해결책** (위 코드에 적용됨):
1. `export const dynamic = 'force-dynamic'` - 라우트 레벨 동적 처리
2. `export const fetchCache = 'force-no-store'` - fetch 캐시 비활성화
3. `cache: 'no-store'` - 개별 fetch 요청에도 명시
4. `Cache-Control: no-store` - 응답 헤더에도 추가

### Next.js 설정

```javascript
// next.config.js
module.exports = {
  // API routes는 Node.js runtime 사용 (스트림 전달 지원)
  // Edge runtime은 사용하지 않음
}
```

**URL 구조:**
| 프론트엔드 호출 | 실제 백엔드 |
|----------------|------------|
| `fetch('/api/upload')` | `http://backend:8000/api/upload` |
| `fetch('/api/status/123')` | `http://backend:8000/api/status/123` |
| `fetch('/api/download/123/midi')` | `http://backend:8000/api/download/123/midi` |

**환경 변수:**
```env
# frontend/.env.local (개발)
BACKEND_URL=http://localhost:8000

# frontend/.env.production (Docker)
BACKEND_URL=http://backend:8000
```

**Docker Compose 설정:**

> **정책**: 개발/테스트 편의를 위해 백엔드 포트도 노출합니다.

```yaml
# docker-compose.yml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - BACKEND_URL=http://backend:8000
    depends_on:
      - backend
    # 리소스 제한 (H11 - DoS 방지)
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
  
  backend:
    build: ./backend
    ports:
      - "8000:8000"  # 개발/테스트용 직접 접근 허용
    environment:
      - JOB_STORAGE_PATH=/tmp/piano-sheet-jobs
      - JOB_TIMEOUT_SECONDS=300     # 5분 타임아웃
      - MAX_CONCURRENT_JOBS=3       # 최대 동시 처리 Job 수
    volumes:
      - job-data:/tmp/piano-sheet-jobs
    # 리소스 제한 (H11 - DoS 방지)
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G        # Basic Pitch는 메모리를 많이 사용

volumes:
  job-data:
```

### 리소스 제한 및 타임아웃 정책 (H11 - DoS 방지)

> **CRITICAL**: 인증 없는 공개 엔드포인트는 리소스 고갈 공격에 취약합니다.
> 반드시 타임아웃과 동시성 제한을 적용하세요.

**환경 변수:**

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `JOB_TIMEOUT_SECONDS` | 300 | 단일 Job 처리 타임아웃 (5분) |
| `MAX_CONCURRENT_JOBS` | 3 | 최대 동시 처리 Job 수 |
| `MAX_PENDING_JOBS` | 10 | 대기열 최대 크기 |

**타임아웃 적용:**

```python
# core/job_manager.py
import asyncio
from config import JOB_TIMEOUT_SECONDS

async def process_job_with_timeout(job_id: str):
    """타임아웃 적용된 Job 처리"""
    try:
        await asyncio.wait_for(
            process_job(job_id),
            timeout=JOB_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        update_job_status(job_id, {
            "status": "failed",
            "error": f"처리 시간이 {JOB_TIMEOUT_SECONDS}초를 초과했습니다.",
            "error_code": "PROCESSING_TIMEOUT"
        })
        raise
```

**대기열 제한:**

```python
# core/job_queue.py
from config import MAX_CONCURRENT_JOBS, MAX_PENDING_JOBS

# 동시 처리 제한
processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# 대기열 크기 추적
pending_count = 0

async def submit_job(job_id: str):
    global pending_count
    
    # 대기열 가득 참 체크
    if pending_count >= MAX_PENDING_JOBS:
        raise AppError(
            error="Server busy",
            code="SERVER_BUSY",
            message="서버가 바쁩니다. 잠시 후 다시 시도해 주세요.",
            status_code=503,
            details={"retry_after": 60}
        )
    
    pending_count += 1
    try:
        async with processing_semaphore:
            await process_job_with_timeout(job_id)
    finally:
        pending_count -= 1
```

> **에러 코드 추가:**
> - `PROCESSING_TIMEOUT` (500): Job 처리 시간 초과
> - `SERVER_BUSY` (503): 대기열 가득 참

**포트 노출 정책:**
| 서비스 | 포트 | 용도 |
|--------|------|------|
| frontend | 3000 | 사용자 접근 (메인) |
| backend | 8000 | 개발자 직접 접근 (/docs, 디버깅) |

**프로덕션 배포 시:**
- 백엔드 포트 노출 제거 가능 (보안)
- 또는 docker-compose.prod.yml 별도 작성

---

## Download Contract (다운로드 계약)

### 파일명 규칙

| 포맷 | 파일명 패턴 | 예시 |
|------|------------|------|
| MIDI | `{원본이름}_melody.mid` | `my_song_melody.mid` |
| MusicXML (easy) | `{원본이름}_easy.musicxml` | `my_song_easy.musicxml` |
| MusicXML (medium) | `{원본이름}_medium.musicxml` | `my_song_medium.musicxml` |
| MusicXML (hard) | `{원본이름}_hard.musicxml` | `my_song_hard.musicxml` |

**원본이름 결정:**
- MP3 업로드: 업로드된 파일명 (확장자 제외)
- YouTube: 영상 제목 (특수문자 제거, 공백→언더스코어)

```python
import re

def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거"""
    # 특수문자 제거, 공백→언더스코어
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized[:100]  # 최대 100자
```

### 백엔드 응답 헤더

```python
# api/download.py
from fastapi.responses import FileResponse

@router.get("/download/{job_id}/{format}")
async def download_file(job_id: str, format: str, difficulty: str = None):
    job = load_job(job_id)
    
    # 원본 이름 결정
    if job.source == "youtube":
        base_name = sanitize_filename(job.youtube_title)
    else:
        base_name = sanitize_filename(Path(job.input_filename).stem)
    
    # 파일 경로 및 다운로드 이름 결정
    if format == "midi":
        file_path = job_dir / "melody.mid"
        download_name = f"{base_name}_melody.mid"
        media_type = "audio/midi"
    elif format == "musicxml":
        file_path = job_dir / f"sheet_{difficulty}.musicxml"
        download_name = f"{base_name}_{difficulty}.musicxml"
        media_type = "application/vnd.recordare.musicxml+xml"
    
    return FileResponse(
        path=file_path,
        filename=download_name,  # Content-Disposition 자동 설정
        media_type=media_type,
    )
```

**응답 헤더 예시:**
```
Content-Type: audio/midi
Content-Disposition: attachment; filename="my_song_melody.mid"
```

### 프론트엔드 다운로드 처리

```typescript
// 프론트엔드는 백엔드가 설정한 Content-Disposition을 그대로 사용
async function downloadFile(jobId: string, format: string, difficulty?: string) {
  const url = difficulty 
    ? `/api/download/${jobId}/${format}?difficulty=${difficulty}`
    : `/api/download/${jobId}/${format}`;
  
  const response = await fetch(url);
  const blob = await response.blob();
  
  // Content-Disposition에서 파일명 추출
  const contentDisposition = response.headers.get('Content-Disposition');
  const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
  const filename = filenameMatch ? filenameMatch[1] : `download.${format === 'midi' ? 'mid' : 'musicxml'}`;
  
  // 다운로드 트리거
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
```

---

## Error Response Contract (에러 응답 표준)

### HTTP Status 정책 (SSOT)

> **결정: 실패한 Job은 5xx 상태 코드를 반환합니다.**
> 
> 이유: HTTP 의미(semantic)를 보존하여 클라이언트가 상태 코드만으로 성공/실패를 판단할 수 있습니다.

| 상황 | HTTP Status | 응답 바디 |
|------|-------------|----------|
| Job 진행 중 | 200 | `{"status": "processing", ...}` |
| Job 성공 | 200 | `{"status": "completed", ...}` |
| Job 실패 (처리 오류) | **500** | `{"error": "...", "code": "...", ...}` |
| Job 실패 (입력 오류) | **4xx** | `{"error": "...", "code": "...", ...}` (에러 코드표 참조) |
| Job 없음 | **404** | `{"error": "Job not found", ...}` |

**API 별 상태 코드:**

| API | 정상 | 진행 중 | 실패 |
|-----|------|---------|------|
| `POST /api/upload` | 200 (job_id 반환) | N/A | 4xx (검증 오류) |
| `POST /api/youtube` | 200 (job_id 반환) | N/A | 4xx (검증 오류) |
| `GET /api/status/{job_id}` | 200 | 200 | 200 (status=failed) |
| `GET /api/result/{job_id}` | 200 | **202** (아직 처리 중) | **500** (처리 실패) |
| `PUT /api/result/{job_id}` | 200 | N/A | 4xx/5xx |
| `GET /api/download/{job_id}/{format}` | 200 (파일) | **202** | **500** |

> **`/api/status` vs `/api/result` 차이:**
> - `/api/status`: 항상 200, body의 status 필드로 상태 판단 (폴링용)
> - `/api/result`: HTTP 상태 코드가 의미를 가짐 (최종 결과 조회용)

### 공통 에러 스키마

모든 API 에러는 다음 스키마를 따릅니다:

```python
from pydantic import BaseModel
from typing import Optional, Any

class ErrorResponse(BaseModel):
    """공통 에러 응답 스키마"""
    error: str              # 에러 유형 (짧은 식별자)
    code: str               # 에러 코드 (프로그래밍용)
    message: str            # 사용자 표시용 메시지
    details: Optional[Any] = None  # 추가 정보 (선택)

# 예시
{
    "error": "File too large",
    "code": "FILE_TOO_LARGE",
    "message": "업로드가 중단되었습니다. 50MB 이하 파일만 업로드 가능합니다.",
    "details": {"max_size_mb": 50, "actual_size_mb": 75.3}
}
```

### YouTube URL 검증 (SSOT - SSRF 방지)

> **CRITICAL**: 정규식만으로는 SSRF 공격을 막을 수 없습니다.
> 반드시 호스트 allowlist 기반 검증을 수행하세요.

```python
# core/youtube.py
from urllib.parse import urlparse
import re

# 허용된 YouTube 호스트 (SSOT)
ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",
}

def validate_youtube_url(url: str) -> tuple[bool, str | None]:
    """
    YouTube URL 검증 (SSRF 방지)
    
    Returns:
        (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL 파싱 실패"
    
    # 1. 스키마 검증 (http/https만 허용)
    if parsed.scheme not in ("http", "https"):
        return False, f"지원하지 않는 프로토콜: {parsed.scheme}"
    
    # 2. 호스트 allowlist 검증 (핵심!)
    host = parsed.netloc.lower()
    # 포트가 포함된 경우 제거 (예: youtube.com:443)
    host_without_port = host.split(":")[0]
    
    if host_without_port not in ALLOWED_YOUTUBE_HOSTS:
        return False, f"허용되지 않은 호스트: {host}"
    
    # 3. Video ID 추출 및 형식 검증
    video_id = extract_video_id(url)
    if not video_id:
        return False, "YouTube 영상 ID를 찾을 수 없습니다"
    
    if not re.match(r'^[A-Za-z0-9_-]{11}$', video_id):
        return False, f"잘못된 영상 ID 형식: {video_id}"
    
    return True, None


def extract_video_id(url: str) -> str | None:
    """YouTube URL에서 Video ID 추출"""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([A-Za-z0-9_-]{11})',
        r'(?:embed/|shorts/)([A-Za-z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
```

**yt-dlp 안전 옵션 (SSOT):**

```python
# core/youtube.py
def get_ytdlp_options(job_id: str, output_path: str) -> dict:
    """yt-dlp 옵션 (보안 + 제한 적용)"""
    return {
        # 출력 설정
        'outtmpl': output_path,
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        
        # 보안 옵션 (SSOT)
        'noplaylist': True,           # 플레이리스트 다운로드 금지
        'extract_flat': False,        # 플레이리스트 메타데이터도 금지
        'age_limit': 18,              # 연령 제한 콘텐츠 허용 (합법적 사용)
        'geo_bypass': False,          # 지역 우회 금지
        
        # 길이 제한 (20분)
        'match_filter': 'duration < 1200',  # 20분 = 1200초
        
        # Progress hook
        'progress_hooks': [create_yt_dlp_progress_hook(job_id)],
        
        # 네트워크 설정
        'socket_timeout': 30,
        'retries': 3,
    }
```

**API 엔드포인트 사용:**

```python
# api/youtube.py
@router.post("/youtube")
async def process_youtube(request: YouTubeRequest):
    # 1. URL 검증 (SSRF 방지)
    is_valid, error_msg = validate_youtube_url(request.url)
    if not is_valid:
        raise AppError(
            error="Invalid YouTube URL",
            code="INVALID_YOUTUBE_URL",
            message=error_msg,
            status_code=400
        )
    
    # 2. Job 생성 및 처리
    job_id = create_job(source="youtube", youtube_url=request.url)
    asyncio.create_task(process_youtube_job(job_id, request.url))
    
    return {"job_id": job_id}
```

### 에러 코드 목록

| HTTP Status | code | error | 상황 |
|-------------|------|-------|------|
| 400 | `INVALID_YOUTUBE_URL` | Invalid YouTube URL | YouTube URL 형식 오류 |
| 400 | `VIDEO_TOO_LONG` | Video too long | YouTube 영상 20분 초과 |
| 400 | `AUDIO_TOO_LONG` | Audio too long | MP3 파일 20분 초과 |
| 400 | `JOB_NOT_COMPLETED` | Job is not in completed state | PUT 요청 시 Job 미완료 |
| 403 | `VIDEO_UNAVAILABLE` | Video is private or age-restricted | YouTube 접근 불가 |
| 404 | `JOB_NOT_FOUND` | Job not found | 존재하지 않는 Job ID |
| 413 | `FILE_TOO_LARGE` | File too large | 파일 50MB 초과 |
| 415 | `UNSUPPORTED_FILE_TYPE` | Unsupported file type | MP3 외 파일 형식 |
| 500 | `PROCESSING_FAILED` | Processing failed | 내부 처리 오류 |
| 500 | `YOUTUBE_DOWNLOAD_FAILED` | YouTube download failed | yt-dlp 다운로드 실패 |

### job.json과 API 에러 코드 관계

- `job.json`의 `error_code` 필드는 위 테이블의 `code` 값과 **동일**합니다.
- `job.json`의 `error` 필드는 위 테이블의 `message` 값과 **동일**합니다.

```python
# Job 실패 시 저장
update_job_status(job_id, {
    "status": "failed",
    "error": "YouTube 다운로드 실패: 이 영상은 다운로드할 수 없습니다.",
    "error_code": "YOUTUBE_DOWNLOAD_FAILED"
})

# API 응답 시 변환
@router.get("/result/{job_id}")
async def get_result(job_id: str):
    job = load_job(job_id)
    
    if job.status == "failed":
        return JSONResponse(
            status_code=500,
            content={
                "error": "Processing failed",
                "code": job.error_code,
                "message": job.error,
                "details": {"job_id": job_id}
            }
        )
```

### FastAPI 예외 핸들러

```python
# main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

class AppError(Exception):
    def __init__(self, error: str, code: str, message: str, status_code: int = 400, details: dict = None):
        self.error = error
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error,
            "code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )

# 사용 예시
raise AppError(
    error="File too large",
    code="FILE_TOO_LARGE",
    message="업로드가 중단되었습니다. 50MB 이하 파일만 업로드 가능합니다.",
    status_code=413,
    details={"max_size_mb": 50}
)
```

---

## Golden Test Comparison Algorithm

> **Phase 1 (현재)**: Smoke 모드 - Reference MIDI 없이 처리 성공 여부만 검증
> **Phase 2 (추후)**: Full 모드 - Reference MIDI 비교로 정확도 측정

### Phase 1: Smoke 모드 테스트 (현재 구현)

Reference MIDI 없이 다양한 장르의 곡에서 처리 성공 여부를 검증합니다.

```
backend/tests/golden/data/song_01/
├── input.mp3              # 입력 오디오
└── metadata.json          # 메타데이터 (장르, BPM, Key 등)
```

**metadata.json 형식 (Smoke 모드)**:
```json
{
  "title": "테스트 곡 1",
  "genre": "pop",
  "bpm": 120,
  "key": "C major",
  "duration_seconds": 180,
  "has_reference": false,
  "notes": "멜로디 추출 테스트용"
}
```

**지원 장르 목록** (테스트 데이터 다양성):
| 장르 | 예시 | 특성 |
|------|------|------|
| `pop` | 대중가요, K-pop | 명확한 멜로디 라인 |
| `ost` | 영화/드라마 OST | 감성적 멜로디 |
| `classical` | 클래식 피아노곡 | 복잡한 화성, 주요 멜로디만 추출 |
| `children` | 동요, 자장가 | 단순한 멜로디 |
| `jazz` | 재즈 스탠다드 | 즉흥 요소 있음 |
| `ccm` | CCM, 찬송가 | 명확한 멜로디 |

### Phase 2: Full 모드 테스트 (추후 구현)

> ⚠️ **추후 구현**: Reference MIDI 준비 후 정확도 측정 기능 추가 예정

```
backend/tests/golden/data/song_01/
├── input.mp3              # 입력 오디오
├── reference.mid          # 정답 MIDI (추후 추가)
├── metadata.json          # 메타데이터
└── reference.musicxml     # (선택) 정답 MusicXML
```

**metadata.json 형식 (Full 모드 - 추후)**:
```json
{
  "title": "테스트 곡 1",
  "genre": "pop",
  "bpm": 120,
  "key": "C major",
  "duration_seconds": 180,
  "has_reference": true,
  "source": "manual_transcription",
  "notes": "멜로디 라인만 포함, 반주 제외"
}
```

### 비교 전처리 (Normalization)

```python
def preprocess_for_comparison(notes: List[Note], reference_bpm: float, generated_bpm: float) -> List[Note]:
    """
    비교 전 정규화 단계:
    1. BPM 정규화: generated를 reference BPM 기준으로 스케일링
    2. Tempo map flattening: 템포 변화 무시, 단일 BPM으로 처리
    3. Quantize 없음: 원본 타이밍 유지
    
    ※ Sustain pedal 처리: 본 프로젝트에서는 미지원 (아래 설명 참조)
    """
    if generated_bpm != reference_bpm:
        scale_factor = reference_bpm / generated_bpm
        for note in notes:
            note.onset *= scale_factor
            note.duration *= scale_factor
    return notes
```

**Sustain Pedal 처리 정책:**

본 프로젝트에서는 Sustain Pedal을 **별도로 처리하지 않습니다**.

| 항목 | 정책 |
|------|------|
| Basic Pitch 출력 | Sustain pedal 정보 없음 (pitch/onset/duration만 출력) |
| Reference MIDI | Sustain pedal 없이 제작 권장 |
| 비교 알고리즘 | Note의 onset/duration만 비교, pedal 무시 |

**이유:**
1. Basic Pitch는 오디오에서 pitch를 추출하므로 pedal 정보가 없음
2. 취미 연주자용 악보에서 pedal 표기는 선택 사항
3. 복잡성 대비 효용이 낮음 (개인 학습/포트폴리오 목적)

**Reference MIDI 제작 가이드:**
- MuseScore에서 악보 입력 시 sustain pedal 없이 제작
- 또는 기존 MIDI에서 pedal 이벤트(CC64) 제거 후 사용
- 음표의 실제 길이(duration)로 표현

### Note Matching Strategy: Greedy Nearest-Neighbor (1:1 매칭)

```python
def compare_notes(generated: List[Note], reference: List[Note], bpm: float) -> ComparisonResult:
    """
    Greedy 1:1 매칭으로 다대일 방지
    """
    TIMING_TOLERANCE_SEC = 0.1  # ±100ms (초 단위)
    PITCH_TOLERANCE = 1  # ±1 반음
    
    # onset 기준 정렬
    gen_sorted = sorted(generated, key=lambda n: n.onset)
    ref_sorted = sorted(reference, key=lambda n: n.onset)
    
    matched_gen_indices = set()
    matched_count = 0
    missed_notes = []
    
    for ref_note in ref_sorted:
        best_match = None
        best_distance = float('inf')
        
        for i, gen_note in enumerate(gen_sorted):
            if i in matched_gen_indices:
                continue  # 이미 매칭된 음표 스킵
            
            time_diff = abs(gen_note.onset - ref_note.onset)
            pitch_diff = abs(gen_note.pitch - ref_note.pitch)
            
            if time_diff <= TIMING_TOLERANCE_SEC and pitch_diff <= PITCH_TOLERANCE:
                distance = time_diff + (pitch_diff * 0.01)  # 시간 우선
                if distance < best_distance:
                    best_distance = distance
                    best_match = i
        
        if best_match is not None:
            matched_gen_indices.add(best_match)
            matched_count += 1
        else:
            missed_notes.append({
                "time": ref_note.onset,
                "pitch": ref_note.pitch,
                "reason": "not_found"
            })
    
    # Extra notes (generated에만 있는 음표)
    extra_notes = [
        {"time": gen_sorted[i].onset, "pitch": gen_sorted[i].pitch}
        for i in range(len(gen_sorted)) if i not in matched_gen_indices
    ]
    
    # 스코어 계산 (Recall 기반, Extra notes는 기록만)
    recall = matched_count / len(reference) * 100 if reference else 100
    
    return ComparisonResult(
        similarity=recall,
        matched=matched_count,
        total_reference=len(reference),
        total_generated=len(generated),
        missed_notes=missed_notes,
        extra_notes=extra_notes
    )
```

### Core Melody Mode (장식음 필터링)

```python
def filter_ornaments(notes: List[Note], bpm: float) -> List[Note]:
    """
    장식음/빠른 패시지 제거 기준 (초 단위):
    1. 32분음표 이하: duration < (60/bpm) / 8
    2. Grace note 패턴: 짧은 음 + 큰 도약 (5도 이상)
    """
    beat_duration_sec = 60 / bpm
    min_duration = beat_duration_sec / 8  # 32분음표
    
    filtered = []
    for i, note in enumerate(notes):
        # 32분음표 이하 제외
        if note.duration < min_duration:
            # Grace note 체크: 다음 음과 5도 이상 차이
            if i + 1 < len(notes):
                interval = abs(notes[i + 1].pitch - note.pitch)
                if interval >= 7:  # 5도 = 7 반음
                    continue  # Grace note로 판정, 제외
            continue
        filtered.append(note)
    
    return filtered
```

### 최종 Pass/Fail 기준 (단일 기준)

**최종 합격 기준**: 핵심 멜로디 모드 recall ≥ 85%

```python
def evaluate_song(generated: List[Note], reference: List[Note], metadata: dict) -> TestResult:
    """
    Pass 조건 (단일 기준):
    - 핵심 멜로디 모드: recall >= 85% (장식음 제외 후)
    
    전체 모드는 참고용으로 기록만 함
    """
    bpm = metadata["bpm"]
    
    # 전체 모드 (참고용)
    full_result = compare_notes(generated, reference, bpm)
    
    # 핵심 멜로디 모드 (최종 판정 기준)
    filtered_gen = filter_ornaments(generated, bpm)
    filtered_ref = filter_ornaments(reference, bpm)
    core_result = compare_notes(filtered_gen, filtered_ref, bpm)
    
    # 최종 판정: 핵심 멜로디 모드 85% 이상
    passed = core_result.similarity >= 85
    
    return TestResult(
        song=metadata["title"],
        full_similarity=full_result.similarity,  # 참고용
        core_similarity=core_result.similarity,  # 최종 점수
        passed=passed,
        details={
            "full": full_result,
            "core": core_result
        }
    )
```

**프로젝트 전체 합격 기준** (Task 16 유연성 정책 적용):
- **Full 모드 곡**: 핵심 멜로디 모드 85% 이상
- **Smoke 모드 곡**: 처리 성공 + 출력 파일 생성
- **전체**: Full 모드 곡 중 90% 이상 통과 (예: 7곡 중 6곡 이상)
- 리포트의 "최종 점수"는 `core_similarity` 값
- Reference MIDI가 없는 곡은 Smoke 모드로 처리 (정확도 측정 제외)

### Test Report Format

```json
{
  "song": "test_song_01",
  "full_similarity": 92.5,
  "core_similarity": 95.2,
  "passed": true,
  "details": {
    "full": {
      "matched": 111,
      "total_reference": 120,
      "total_generated": 125,
      "missed_notes": [
        {"time": 15.2, "pitch": 72, "reason": "not_found"}
      ],
      "extra_notes": [
        {"time": 8.3, "pitch": 60}
      ]
    },
    "core": {
      "matched": 98,
      "total_reference": 103,
      "total_generated": 105
    }
  }
}
```

---

## Difficulty Adjustment Rules

### 난이도별 변환 규칙 (초 단위 기준)

| 규칙 | 초급 (Easy) | 중급 (Medium) | 고급 (Hard) |
|------|-------------|---------------|-------------|
| 퀀타이즈 그리드 | 1 beat (초) | 0.5 beat (초) | 0.25 beat (초) |
| 최소 음표 길이 | 0.5초 | 0.25초 | 0.125초 |
| 음역 범위 | C4-C5 (MIDI 60-72) | C4-G5 (MIDI 60-79) | 원본 유지 |
| 동시 발음 수 | 1 (단선율) | 2 | 원본 유지 |
| 빠른 패시지 | 제거 | 단순화 | 유지 |
| 장식음 | 제거 | 제거 | 유지 |

### 구현 로직 (초 단위)

```python
def adjust_difficulty(notes: List[Note], level: str, bpm: float) -> List[Note]:
    """
    Note 리스트를 받아 난이도에 맞게 조정
    모든 시간 단위는 초(seconds)
    """
    beat_sec = 60 / bpm  # 1박 = 초
    
    if level == "easy":
        quantize_grid = beat_sec  # 4분음표
        min_duration = 0.5  # 초
        octave_range = (60, 72)  # C4-C5
        max_simultaneous = 1
    elif level == "medium":
        quantize_grid = beat_sec / 2  # 8분음표
        min_duration = 0.25  # 초
        octave_range = (60, 79)  # C4-G5
        max_simultaneous = 2
    else:  # hard
        return notes  # 원본 유지
    
    # 1. 짧은 음표 제거
    filtered = [n for n in notes if n.duration >= min_duration]
    
    # 2. 퀀타이즈 (onset을 그리드에 맞춤)
    for note in filtered:
        note.onset = round(note.onset / quantize_grid) * quantize_grid
    
    # 3. 음역 조정 (옥타브 이동)
    for note in filtered:
        while note.pitch < octave_range[0]:
            note.pitch += 12
        while note.pitch > octave_range[1]:
            note.pitch -= 12
    
    # 4. 동시 발음 제한 (같은 onset에서 가장 높은 음 우선)
    if max_simultaneous < len(filtered):
        filtered = limit_simultaneous_notes(filtered, max_simultaneous)
    
    return filtered

def limit_simultaneous_notes(notes: List[Note], max_count: int) -> List[Note]:
    """동일 onset에서 max_count개만 유지 (높은 pitch 우선)"""
    from collections import defaultdict
    by_onset = defaultdict(list)
    for n in notes:
        by_onset[n.onset].append(n)
    
    result = []
    for onset, group in by_onset.items():
        sorted_group = sorted(group, key=lambda x: -x.pitch)  # 높은 음 우선
        result.extend(sorted_group[:max_count])
    
    return sorted(result, key=lambda x: x.onset)
```

---

## Docker Environment Requirements

### Backend Dockerfile
```dockerfile
FROM python:3.11-slim

# 시스템 의존성 설치
# - ffmpeg: yt-dlp 오디오 추출 필수
# - libsndfile1: librosa 오디오 로딩 필수
# - build-essential: 일부 Python 패키지 빌드 필요
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 환경 변수 설정
ENV JOB_STORAGE_PATH=/tmp/piano-sheet-jobs
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
# ⚠️ CRITICAL: --workers 1 필수!
# asyncio.create_task() 기반 Job 시스템은 단일 프로세스에서만 동작합니다.
# 멀티 워커 사용 시 Job 상태가 프로세스 간 공유되지 않아 작업이 유실됩니다.
```

### requirements.txt 핵심 의존성
```
fastapi>=0.109.0
uvicorn>=0.27.0
python-multipart>=0.0.6
basic-pitch>=0.3.0
music21>=9.1.0
librosa>=0.10.0
soundfile>=0.12.0
yt-dlp>=2024.1.0
mido>=1.3.0
pretty_midi>=0.2.10
pydantic>=2.5.0
```

### 시스템 의존성 설명
| 패키지 | 용도 | 필수 여부 |
|--------|------|----------|
| ffmpeg | yt-dlp 오디오 추출, librosa 일부 포맷 | 필수 |
| libsndfile1 | librosa/soundfile 오디오 로딩 | 필수 |
| build-essential | numpy/scipy 등 빌드 시 필요할 수 있음 | 권장 |

### yt-dlp YouTube 지원 정책 (제한적 지원)

**지원 범위 결정: 제한적 지원 (실패 허용)**

본 프로젝트는 YouTube 다운로드를 **"best effort"** 방식으로 지원합니다:
- 일반 공개 영상의 대부분은 ffmpeg만으로 다운로드 가능
- 일부 영상(DRM, 특수 포맷, 지역 제한 등)은 실패할 수 있음
- 실패 시 사용자에게 명확한 에러 메시지 제공 + MP3 업로드 대안 안내

**의존성 결정:**
- ffmpeg: 필수 (Docker 이미지에 포함)
- yt-dlp-ejs, JS runtime (deno/node): **포함하지 않음**
- 이유: 복잡성 증가 대비 커버리지 향상이 미미, 개인 학습/포트폴리오 목적에 과도함

**실패 시 동작:**
```python
# youtube_downloader.py
class YouTubeDownloadError(Exception):
    """YouTube 다운로드 실패 시 발생"""
    pass

def download_youtube_audio(url: str, output_path: Path) -> Path:
    try:
        # yt-dlp 다운로드 시도
        ...
    except Exception as e:
        raise YouTubeDownloadError(
            f"YouTube 다운로드 실패: {str(e)}. "
            "이 영상은 지원되지 않을 수 있습니다. "
            "MP3 파일을 직접 업로드해 주세요."
        )
```

**API 에러 응답:**
```json
{
  "error": "YouTube download failed",
  "message": "이 영상은 다운로드할 수 없습니다. MP3 파일을 직접 업로드해 주세요.",
  "code": "YOUTUBE_DOWNLOAD_FAILED"
}
```

**향후 확장 가능성:**
- 실패율이 높아지면 yt-dlp-ejs + Node.js 추가 검토
- 현재는 YAGNI 원칙 적용

### Job Storage 경로 설정
```python
# backend/config.py
import os
from pathlib import Path

# 환경 변수로 경로 설정 (Docker/로컬 모두 지원)
JOB_STORAGE_PATH = Path(os.getenv("JOB_STORAGE_PATH", "/tmp/piano-sheet-jobs"))

# 로컬 Windows 개발 시 예시:
# set JOB_STORAGE_PATH=C:\Users\{user}\AppData\Local\Temp\piano-sheet-jobs
```

**로컬 개발 (Windows)**:
- 환경 변수 `JOB_STORAGE_PATH` 설정 필요
- 또는 Docker로만 실행 권장

---

## File Size & Duration Limit Implementation (50MB / 20분 제한)

### 제한 정책 요약
| 제한 | 값 | 측정 방법 | 차단 레이어 |
|------|-----|----------|------------|
| 파일 크기 | 50MB | Content-Length 헤더 + 실제 바이트 수 | 프론트엔드 + 백엔드 |
| MP3 길이 | 20분 | librosa.get_duration() | 백엔드 (업로드 후) |
| YouTube 길이 | 20분 | yt-dlp extract_info() | 백엔드 (다운로드 전) |

### 1. 파일 크기 제한 (50MB)

**프론트엔드 선차단 (UX 향상):**
```typescript
// components/FileUpload.tsx
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

const onDrop = (files: File[]) => {
  const file = files[0];
  if (file.size > MAX_FILE_SIZE) {
    setError(`파일이 너무 큽니다. 최대 50MB까지 업로드 가능합니다. (현재: ${(file.size / 1024 / 1024).toFixed(1)}MB)`);
    return;
  }
  // 업로드 진행...
};
```

**백엔드 강제 차단 (보안):**

> **중요**: FastAPI의 `UploadFile.size`는 Python 3.11+에서 `Content-Length` 헤더 기반으로 제공되지만,
> 클라이언트가 헤더를 조작할 수 있으므로 **실제 바이트 수 체크가 필수**입니다.

```python
# api/upload.py
from fastapi import UploadFile, HTTPException, Request
from pathlib import Path
import aiofiles
import os

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
CHUNK_SIZE = 1024 * 1024  # 1MB 청크

@router.post("/upload")
async def upload_file(request: Request, file: UploadFile):
    """
    파일 업로드 처리
    - Content-Length 헤더로 사전 체크 (있는 경우)
    - 스트리밍 저장하면서 실제 바이트 수 체크
    - 초과 시 부분 파일 삭제
    """
    
    # 1. Content-Length 헤더 사전 체크 (선택적, 빠른 거부용)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail={"error": "File too large", "max_size_mb": 50}
                )
        except ValueError:
            pass  # 헤더 파싱 실패 시 무시, 실제 바이트로 체크
    
    # 2. Job 디렉토리 생성
    job_id = str(uuid.uuid4())
    job_dir = JOB_STORAGE_PATH / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. 스트리밍 저장 + 바이트 수 체크
    file_path = job_dir / "input.mp3"
    total_size = 0
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                total_size += len(chunk)
                
                # 크기 초과 체크
                if total_size > MAX_FILE_SIZE:
                    # 부분 파일 삭제
                    await f.close()
                    file_path.unlink(missing_ok=True)
                    job_dir.rmdir()  # 빈 디렉토리 삭제
                    
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "error": "File too large",
                            "max_size_mb": 50,
                            "message": "업로드가 중단되었습니다. 50MB 이하 파일만 업로드 가능합니다."
                        }
                    )
                
                await f.write(chunk)
        
        # 4. 파일 저장 완료, 길이 체크는 다음 단계에서...
        return {"job_id": job_id, "file_size": total_size}
        
    except HTTPException:
        raise
    except Exception as e:
        # 예외 발생 시 정리
        if file_path.exists():
            file_path.unlink()
        if job_dir.exists():
            job_dir.rmdir()
        raise HTTPException(status_code=500, detail={"error": f"Upload failed: {str(e)}"})
```

**구현 핵심 포인트:**
| 항목 | 구현 방식 |
|------|----------|
| Content-Length 체크 | 있으면 사전 거부, 없으면 무시 (조작 가능하므로 신뢰 안 함) |
| 실제 크기 체크 | 스트리밍 저장하면서 누적 바이트 수 체크 |
| 초과 시 처리 | 즉시 중단, 부분 파일 삭제, 413 반환 |
| 저장 방식 | 디스크에 직접 스트리밍 (메모리 절약) |
```

### 2. MP3 길이 제한 (20분) - 업로드 후 측정

**측정 도구: librosa.get_duration()**
```python
# core/audio_validator.py
import librosa

MAX_DURATION_SECONDS = 20 * 60  # 20분

def validate_audio_duration(file_path: Path) -> float:
    """
    오디오 파일 길이 검증
    Returns: duration in seconds
    Raises: AudioTooLongError if > 20분
    """
    try:
        duration = librosa.get_duration(path=str(file_path))
    except Exception as e:
        raise AudioValidationError(f"오디오 파일을 읽을 수 없습니다: {e}")
    
    if duration > MAX_DURATION_SECONDS:
        raise AudioTooLongError(
            f"오디오가 너무 깁니다. 최대 20분까지 지원합니다. "
            f"(현재: {duration / 60:.1f}분)"
        )
    
    return duration

class AudioTooLongError(Exception):
    pass

class AudioValidationError(Exception):
    pass
```

**API 통합:**
```python
# api/upload.py
@router.post("/upload")
async def upload_file(file: UploadFile):
    # 1. 파일 크기 체크 (위 코드)
    # 2. 파일 저장
    saved_path = save_uploaded_file(content, job_id)
    
    # 3. 길이 체크 (저장 후)
    try:
        duration = validate_audio_duration(saved_path)
    except AudioTooLongError as e:
        # 파일 삭제 후 에러 반환
        saved_path.unlink()
        raise HTTPException(status_code=400, detail={"error": str(e)})
    
    # 4. Job 생성...
```

### 3. YouTube 길이 제한 (20분) - 다운로드 전 측정

**측정 도구: yt-dlp extract_info()**
```python
# core/youtube_downloader.py
import yt_dlp

MAX_DURATION_SECONDS = 20 * 60  # 20분

def get_video_info(url: str) -> dict:
    """
    다운로드 전 메타데이터 조회
    Returns: {"title": str, "duration": float, "id": str}
    Raises: YouTubeValidationError
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,  # 전체 메타데이터 필요
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise YouTubeValidationError(f"YouTube 정보를 가져올 수 없습니다: {e}")
        
        duration = info.get('duration', 0)
        if duration > MAX_DURATION_SECONDS:
            raise VideoTooLongError(
                f"영상이 너무 깁니다. 최대 20분까지 지원합니다. (현재: {duration / 60:.1f}분)",
                duration_seconds=duration  # 예외에 duration 포함
            )
        
        return {
            "title": info.get('title', 'Unknown'),
            "duration": duration,
            "id": info.get('id'),
        }

class VideoTooLongError(Exception):
    """영상 길이 초과 예외"""
    def __init__(self, message: str, duration_seconds: float):
        super().__init__(message)
        self.duration_seconds = duration_seconds  # 실제 영상 길이 (초)

class YouTubeValidationError(Exception):
    """YouTube 검증 실패 예외"""
    pass
```

**API 통합:**
```python
# api/youtube.py
@router.post("/youtube")
async def submit_youtube(request: YouTubeRequest):
    # 1. URL 유효성 검증 (정규식)
    if not is_valid_youtube_url(request.url):
        raise AppError(
            error="Invalid YouTube URL",
            code="INVALID_YOUTUBE_URL",
            message="올바른 YouTube URL을 입력해주세요.",
            status_code=400
        )
    
    # 2. 메타데이터 조회 + 길이 체크 (다운로드 전!)
    try:
        video_info = get_video_info(request.url)
    except VideoTooLongError as e:
        raise AppError(
            error="Video too long",
            code="VIDEO_TOO_LONG",
            message=str(e),
            status_code=400,
            details={
                "max_duration_minutes": 20,
                "actual_duration_minutes": round(e.duration_seconds / 60, 1)
            }
        )
    except YouTubeValidationError as e:
        raise AppError(
            error="YouTube validation failed",
            code="YOUTUBE_DOWNLOAD_FAILED",
            message=str(e),
            status_code=400
        )
    
    # 3. Job 생성 (다운로드는 백그라운드에서)
    job_id = create_job(source="youtube", url=request.url, metadata=video_info)
    
    return {
        "job_id": job_id,
        "status": "pending",
        "video_title": video_info["title"],
        "duration_seconds": video_info["duration"]
    }
```

### 에러 응답 정리

| 상황 | HTTP Status | 응답 |
|------|-------------|------|
| 파일 50MB 초과 | 413 | `{"error": "File too large", "max_size_mb": 50}` |
| MP3 20분 초과 | 400 | `{"error": "Audio too long", "max_duration_minutes": 20, "actual_duration_minutes": 25.3}` |
| YouTube 20분 초과 | 400 | `{"error": "Video too long", "max_duration_minutes": 20, "actual_duration_minutes": 25.3}` |

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (새 프로젝트)
- **User wants tests**: YES (E2E + Golden Test)
- **Framework**: Playwright (E2E), pytest (백엔드), custom Golden Test

### E2E Test Scenarios
- [ ] MP3 업로드 → 처리 → MIDI 다운로드
- [ ] MP3 업로드 → 처리 → MusicXML 다운로드
- [ ] MP3 업로드 → 악보 렌더링 확인
- [ ] YouTube URL 입력 → 처리 → MIDI 다운로드
- [ ] YouTube URL 입력 → 악보 렌더링 확인
- [ ] 코드 자동 감지 → 수동 수정
- [ ] BPM 자동 감지 → 수동 수정
- [ ] 조성 자동 감지 → 수동 수정
- [ ] 난이도 변경 (초급 ↔ 중급 ↔ 고급)
- [ ] 에러 케이스 (파일 너무 큼, 잘못된 형식)
- [ ] 에러 케이스 (잘못된 YouTube URL, 20분 초과 영상)

### Golden Test Data Location
```
backend/tests/golden/
├── data/
│   ├── song_01/
│   │   ├── input.mp3
│   │   ├── reference.mid
│   │   ├── reference.musicxml  (선택)
│   │   └── metadata.json       (필수: bpm, key, title)
│   ├── song_02/
│   │   └── ...
│   └── ... (10곡 이상)
├── comparator.py
├── test_golden.py
└── conftest.py
```

> **Docker 빌드 컨텍스트**: 백엔드 Dockerfile의 빌드 컨텍스트가 `./backend`이므로,
> 모든 테스트 파일은 `backend/tests/` 하위에 위치해야 컨테이너에 포함됩니다.

**metadata.json 필수 필드**:
```json
{
  "title": "테스트 곡 1",
  "bpm": 120,
  "key": "C major",
  "duration_seconds": 180,
  "source": "manual_transcription"
}
```

**데이터 관리**:
- .gitignore에 `backend/tests/golden/data/` 추가 (저작권 보호)
- README에 테스트 데이터 준비 방법 문서화
- 정답 MIDI는 직접 제작 또는 검증된 악보에서 추출

**Golden Test 데이터 재현 경로**:

저작권 문제로 테스트 데이터를 Git에 포함하지 않으므로, 새 환경에서 Golden Test를 실행하려면 다음 절차 필요:

1. **테스트 데이터 준비 스크립트** (`backend/scripts/prepare_golden_data.py`):
   ```python
   """
   Golden Test 데이터 준비 가이드
   
   이 스크립트는 테스트 데이터 구조만 생성합니다.
   실제 MP3와 reference.mid는 수동으로 준비해야 합니다.
   """
   
   REQUIRED_SONGS = [
       {"id": "song_01", "title": "테스트곡 1", "bpm": 120, "key": "C major"},
       {"id": "song_02", "title": "테스트곡 2", "bpm": 100, "key": "G major"},
       # ... 10곡
   ]
   
    def create_directory_structure():
        for song in REQUIRED_SONGS:
            dir_path = Path(f"backend/tests/golden/data/{song['id']}")
           dir_path.mkdir(parents=True, exist_ok=True)
           
           # metadata.json 생성
           metadata = {
               "title": song["title"],
               "bpm": song["bpm"],
               "key": song["key"],
               "duration_seconds": None,  # 수동 입력 필요
               "source": "manual_transcription"
           }
           (dir_path / "metadata.json").write_text(json.dumps(metadata, indent=2))
           
           # 필요한 파일 목록 출력
           print(f"[{song['id']}] 다음 파일을 준비하세요:")
           print(f"  - {dir_path}/input.mp3")
           print(f"  - {dir_path}/reference.mid")
   ```

2. **README 문서화 내용**:
   ```markdown
   ## Golden Test 데이터 준비
   
   저작권 보호를 위해 테스트 데이터는 Git에 포함되지 않습니다.
   
   ### 준비 방법
   1. `docker-compose exec backend python scripts/prepare_golden_data.py` 실행 → 디렉토리 구조 생성
   2. 각 곡 디렉토리(`backend/tests/golden/data/song_XX/`)에 다음 파일 추가:
      - `input.mp3`: 테스트할 음원 (20분 이하)
      - `reference.mid`: 정답 MIDI (직접 제작 또는 검증된 악보에서 추출)
   3. `metadata.json`의 `duration_seconds` 필드 업데이트
   
   ### 정답 MIDI 제작 방법
   - MuseScore에서 악보 입력 후 MIDI 내보내기
   - 또는 기존 MIDI 파일에서 멜로디 트랙만 추출
   
   ### CI/CD 환경
   - Golden Test는 로컬 개발 환경에서만 실행
   - CI에서는 Golden Test 스킵 (`pytest -m "not golden"`)
   ```

3. **pytest 마커 설정** (`backend/tests/golden/conftest.py`):
   ```python
   import pytest
   from pathlib import Path
   
   def pytest_configure(config):
       config.addinivalue_line("markers", "golden: Golden Test (requires local data)")
   
   @pytest.fixture
   def golden_data_available():
       """Golden Test 데이터 존재 여부 확인"""
       # Docker 컨테이너 내부에서 실행되므로 /app 기준 경로
       data_dir = Path("/app/tests/golden/data")
       if not data_dir.exists() or not any(data_dir.iterdir()):
           pytest.skip("Golden Test 데이터가 없습니다. README 참조.")
   ```

---

## Task Flow

```
[Phase 1: 환경 설정]
    Task 1 (프로젝트 구조)
         ↓
[Phase 2: 백엔드 코어]
    Task 2 (Basic Pitch) ─────┬──→ Task 4 (멜로디 추출)
         ↓                    │          ↓
    Task 3 (YouTube yt-dlp) ──┘    Task 5 (MIDI→MusicXML)
         ↓                              ↓
    Task 6 (BPM/Key/Chord) ←───────────┘
         ↓
    Task 7 (난이도 조절)
         ↓
    Task 8 (FastAPI + Job System)
         ↓
[Phase 3: 프론트엔드]
    Task 9 (업로드 UI) ──┬──→ Task 10 (악보 렌더링)
                         │          ↓
                         └──→ Task 11 (수정 UI)
                                    ↓
                              Task 12 (다운로드)
         ↓
[Phase 4: 통합 & 테스트]
    Task 13 (Docker 완성)
         ↓
    Task 14 (Golden Test)
         ↓
    Task 15 (E2E 테스트)
         ↓
    Task 16 (튜닝 & 최적화)
```

## Parallelization

| Group | Tasks | Reason |
|-------|-------|--------|
| A | 2, 3 | 독립적인 입력 처리 모듈 |
| B | 9, 10, 11, 12 | 프론트엔드 컴포넌트들 |

| Task | Depends On | Reason |
|------|------------|--------|
| 2 | 1 | 프로젝트 구조 필요 |
| 3 | 1 | 프로젝트 구조 필요 |
| 4 | 2 | Basic Pitch 출력 필요 |
| 5 | 4 | 멜로디 MIDI 필요 |
| 6 | 2 | 오디오 분석 필요 |
| 7 | 5 | MusicXML 필요 |
| 8 | 3, 5, 6, 7 | 모든 코어 로직 필요 |
| 9-12 | 8 | API 필요 |
| 13 | 8, 12 | 전체 앱 필요 |
| 14 | 8 | API 필요 |
| 15 | 13 | Docker 환경 필요 |
| 16 | 14, 15 | 테스트 결과 필요 |

---

## TODOs

### Task 1: 프로젝트 구조 및 환경 설정

**What to do**:
- 모노레포 구조 생성:
  ```
  /
  ├── backend/
  │   ├── core/
  │   ├── api/
  │   ├── tests/
  │   │   ├── unit/           # 단위 테스트
  │   │   ├── e2e/            # E2E 테스트
  │   │   └── golden/         # Golden Test
  │   │       └── data/       # 테스트 데이터 (gitignore)
  │   ├── scripts/
  │   ├── requirements.txt
  │   ├── Dockerfile
  │   └── main.py
  ├── frontend/
  │   ├── components/
  │   ├── app/
  │   ├── package.json
  │   └── Dockerfile
  ├── docker-compose.yml
  └── README.md
  ```
  
  > **Docker 빌드 컨텍스트 정책**: 백엔드 Dockerfile은 `./backend`를 컨텍스트로 사용합니다.
  > 따라서 모든 백엔드 테스트와 스크립트는 `backend/` 하위에 위치해야 합니다.
- Docker Compose 기본 설정 (ffmpeg 포함)
- 프로젝트 파일 구조 생성 (호스트에서 파일 생성, 실행은 Docker)

**Must NOT do**:
- 실제 기능 구현 (구조만)
- 호스트에서 venv 생성 또는 npm install 실행 (Docker 빌드 시 자동 처리)

**Parallelizable**: NO (첫 번째 태스크)

**References**:

*외부 근거 (읽을 자료):*
- FastAPI 공식 문서: https://fastapi.tiangolo.com/
- Next.js 14 문서: https://nextjs.org/docs
- Docker Compose: https://docs.docker.com/compose/

*생성할 파일:*
- `backend/main.py` - FastAPI 앱 엔트리포인트
- `backend/requirements.txt` - Python 의존성
- `backend/Dockerfile` - 백엔드 Docker 이미지
- `frontend/package.json` - Next.js 프로젝트 설정
- `frontend/Dockerfile` - 프론트엔드 Docker 이미지
- `docker-compose.yml` - 전체 서비스 오케스트레이션

**Acceptance Criteria**:
- [ ] `docker-compose up --build` → 컨테이너 시작 (에러 없음)
- [ ] `docker-compose up` 후 localhost:8000/docs 접속 (FastAPI Swagger UI)
- [ ] `docker-compose up` 후 localhost:3000 접속 (Next.js 앱)

> ⚠️ **Docker-only 정책 (SSOT)**
> 
> **의미**: 프로젝트 파일 생성은 호스트에서, 실행/테스트는 Docker에서만
> 
> | 작업 | 실행 위치 | 방법 |
> |------|----------|------|
> | 파일 생성/편집 | 호스트 | IDE/에디터로 직접 편집 |
> | Python 의존성 설치 | Docker | `docker-compose build` 시 자동 |
> | npm 의존성 설치 | Docker | `docker-compose build` 시 자동 |
> | 백엔드 실행 | Docker | `docker-compose up` |
> | 프론트엔드 실행 | Docker | `docker-compose up` |
> | pytest 실행 | Docker | `docker-compose exec backend pytest` |
> | 스크립트 실행 | Docker | `docker-compose exec backend python scripts/...` |
> 
> **금지 사항**:
> - 호스트에서 `python -m venv` 또는 `pip install` 실행
> - 호스트에서 `npm install` 또는 `npm run dev` 실행
> - 호스트에서 `uvicorn main:app` 실행
> 
> **이유**: ffmpeg, libsndfile 등 시스템 의존성이 Docker 이미지에만 포함됨

**Commit**: `chore: initialize project structure`

---

### Task 2: Basic Pitch 통합 (MP3 → MIDI)

**What to do**:
- basic-pitch 설치 및 래퍼 함수 구현
- 입력: MP3/WAV 파일 경로
- 출력: MIDI 파일 경로
- 처리 시간 로깅

**Must NOT do**:
- 멜로디 추출 (Task 4)
- API 엔드포인트 (Task 8)

**Parallelizable**: YES (Task 3과 병렬)

**References**:

*외부 근거 (읽을 자료):*
- Basic Pitch GitHub: https://github.com/spotify/basic-pitch
- 사용법: `from basic_pitch.inference import predict`
- `predict(audio_path)` → `(model_output, midi_data, note_events)`

*생성할 파일:*
- `backend/core/audio_to_midi.py` - Basic Pitch 래퍼 함수

**Acceptance Criteria**:
- [x] 테스트 MP3 → MIDI 변환 성공
- [x] MIDI가 MuseScore에서 열림
- [x] 3분 곡 처리 시간 < 2분 (아래 측정 조건 참조)

**성능 측정 조건 (SSOT):**
- **측정 환경**: Docker 컨테이너 내부 (docker-compose 기본 설정)
- **리소스 제한**: Docker Desktop 기본값 (CPU 제한 없음, 메모리 8GB 이상 권장)
- **입력 파일**: 3분 길이 MP3 (44.1kHz, 128kbps 이상)
- **측정 방법**: `time.time()` 기반 로깅, Basic Pitch 호출 시작~완료
- **허용 범위**: 2분 이하 (120초)
- **참고**: GPU 없는 CPU-only 환경 기준. GPU 사용 시 더 빠름

**Commit**: `feat(backend): integrate Basic Pitch for audio to MIDI`

---

### Task 3: YouTube URL 오디오 추출 (yt-dlp)

**What to do**:
- yt-dlp 설치 및 래퍼 함수 구현
- URL 유효성 검증 (정규식)
- 메타데이터 조회 (제목, 길이) - 다운로드 전
- 20분 초과 시 거부
- 오디오만 추출 (bestaudio → mp3)
- 진행률 콜백 구현

**Must NOT do**:
- 영상 다운로드
- 플레이리스트 지원

**Parallelizable**: YES (Task 2와 병렬)

**References**:

*외부 근거 (읽을 자료):*
- yt-dlp GitHub: https://github.com/yt-dlp/yt-dlp
- Python API: `yt_dlp.YoutubeDL(opts).download([url])`
- 옵션 예시:
  ```python
  {
      'format': 'bestaudio/best',
      'postprocessors': [{
          'key': 'FFmpegExtractAudio',
          'preferredcodec': 'mp3',
      }],
      'progress_hooks': [progress_callback],
      'outtmpl': '%(id)s.%(ext)s',
  }
  ```

*생성할 파일:*
- `backend/core/youtube_downloader.py` - yt-dlp 래퍼 (get_video_info, download_youtube_audio)

*참조할 계획서 섹션:*
- "yt-dlp YouTube 지원 정책" - 제한적 지원 정책, 에러 처리 방식
- "File Size & Duration Limit Implementation" - 20분 제한 구현 방법

**Acceptance Criteria**:
- [x] YouTube URL → MP3 추출 성공
- [x] 20분 초과 영상 거부 (다운로드 전 체크, `extract_info()` 사용)
- [x] 비공개 영상 에러 처리
- [x] 진행률 콜백 동작 (yt-dlp 내부 0-100% → Job progress 0-20%로 변환)

**Commit**: `feat(backend): implement YouTube audio extraction with yt-dlp`

---

### Task 4: 멜로디 추출 (Polyphonic → Monophonic)

**What to do**:
- Basic Pitch 출력에서 멜로디 라인 추출
- Skyline Algorithm: 동시 발음 중 가장 높은 음 선택
- 옥타브 정규화 (C3-C6 범위로)
- 너무 짧은 음 제거 (< 50ms)

**Must NOT do**:
- 난이도 조절 (Task 7)

**Parallelizable**: NO (Task 2 필요)

---

### MIDI 파싱 SSOT: `pretty_midi` (Task 4/5/7/14/16 공통)

> ⚠️ **CRITICAL**: 프로젝트 전체에서 MIDI 파싱은 **`pretty_midi`만 사용**합니다.
> `mido`는 의존성에 포함되어 있지만, 직접 사용하지 않습니다 (pretty_midi 내부 의존성).

**왜 pretty_midi인가:**
| 라이브러리 | 장점 | 단점 | 선택 |
|------------|------|------|------|
| `mido` | 저수준 제어 | 시간 계산 직접 구현 필요 | ❌ |
| `pretty_midi` | 초 단위 시간 자동 계산, 직관적 API | 약간 무거움 | ✅ SSOT |
| `music21.converter.parse()` | 풍부한 기능 | MIDI 파싱 성능 낮음, 복잡 | ❌ |

**MIDI 파싱 표준 함수:**
```python
# backend/core/midi_parser.py

import pretty_midi
from dataclasses import dataclass
from typing import List
from pathlib import Path

@dataclass
class Note:
    pitch: int          # MIDI pitch (0-127, 60=C4)
    onset: float        # 시작 시간 (초)
    duration: float     # 길이 (초)
    velocity: int       # 세기 (0-127)


def parse_midi(midi_path: Path) -> List[Note]:
    """
    MIDI 파일을 Note 리스트로 파싱 (SSOT 함수)
    
    Args:
        midi_path: MIDI 파일 경로
    
    Returns:
        List[Note]: 초 단위 시간의 Note 리스트
    
    Note:
        - pretty_midi는 내부적으로 tempo map을 처리하여 초 단위 시간 반환
        - 본 프로젝트는 단일 BPM을 가정하므로 tempo 변화는 무시됨
        - 여러 트랙이 있으면 모든 트랙의 노트를 합침 (멜로디 추출은 별도 처리)
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    
    notes = []
    for instrument in pm.instruments:
        if instrument.is_drum:
            continue  # 드럼 트랙 제외
        
        for note in instrument.notes:
            notes.append(Note(
                pitch=note.pitch,
                onset=note.start,           # 이미 초 단위
                duration=note.end - note.start,  # 이미 초 단위
                velocity=note.velocity
            ))
    
    # onset 기준 정렬
    notes.sort(key=lambda n: n.onset)
    return notes
```

**시간 단위 규칙 (재확인):**
- `parse_midi()` 반환값: **초(seconds)** 단위
- `notes_to_stream()` 입력: **초(seconds)** 단위
- music21 내부: **quarterLength** 단위 (자동 변환)
- 변환 함수: `seconds_to_quarter_length(seconds, bpm)` (Task 5에서 제공)

---

### MIDI 이벤트 처리 규칙 (Task 4 핵심 정책)

> 이 규칙들은 Golden Test 튜닝 이전에 구현을 안정화하기 위한 정책입니다.

#### 1. 동일 onset 처리 (Skyline Algorithm)

```python
def apply_skyline(notes: List[Note]) -> List[Note]:
    """
    동일 onset에 여러 음표가 있을 때 최고음만 선택
    
    정책:
    - onset 차이가 ONSET_TOLERANCE 이내면 "동시 발음"으로 간주
    - 동시 발음 중 pitch가 가장 높은 음표만 유지
    - 나머지는 삭제
    """
    ONSET_TOLERANCE = 0.02  # 20ms 이내는 동시 발음으로 간주
    
    # onset 기준 정렬
    sorted_notes = sorted(notes, key=lambda n: (n.onset, -n.pitch))
    
    result = []
    i = 0
    while i < len(sorted_notes):
        current = sorted_notes[i]
        
        # 동시 발음 그룹 찾기
        group = [current]
        j = i + 1
        while j < len(sorted_notes) and abs(sorted_notes[j].onset - current.onset) <= ONSET_TOLERANCE:
            group.append(sorted_notes[j])
            j += 1
        
        # 최고음 선택 (이미 pitch 내림차순 정렬됨)
        highest = max(group, key=lambda n: n.pitch)
        result.append(highest)
        
        i = j
    
    return result
```

#### 2. Duration 산정 규칙

```python
def calculate_duration(note_on_time: float, note_off_time: float) -> float:
    """
    Note duration 계산
    
    정책:
    - duration = note_off_time - note_on_time
    - note_off가 없으면 (MIDI 오류): 기본값 0.5초 사용
    - duration이 음수면 (MIDI 오류): 기본값 0.5초 사용
    """
    DEFAULT_DURATION = 0.5  # 초
    
    if note_off_time is None or note_off_time <= note_on_time:
        return DEFAULT_DURATION
    
    return note_off_time - note_on_time
```

#### 3. 짧은 음표 제거 기준

```python
def filter_short_notes(notes: List[Note]) -> List[Note]:
    """
    너무 짧은 음표 제거
    
    정책:
    - MIN_DURATION (50ms) 미만인 음표는 제거
    - 이 기준은 "duration" 기준 (onset 간격 아님)
    """
    MIN_DURATION = 0.05  # 50ms
    
    return [n for n in notes if n.duration >= MIN_DURATION]
```

#### 4. Overlap/연속 음표 처리

```python
def resolve_overlaps(notes: List[Note]) -> List[Note]:
    """
    음표 겹침(overlap) 해결
    
    정책:
    - 이전 음표가 끝나기 전에 다음 음표가 시작되면
    - 이전 음표의 duration을 잘라서 겹침 제거
    - 연속 타이(tie)는 별도 처리 안 함 (단순화)
    """
    if not notes:
        return notes
    
    sorted_notes = sorted(notes, key=lambda n: n.onset)
    result = [sorted_notes[0]]
    
    for i in range(1, len(sorted_notes)):
        prev = result[-1]
        curr = sorted_notes[i]
        
        # 겹침 확인
        prev_end = prev.onset + prev.duration
        if prev_end > curr.onset:
            # 이전 음표 duration 조정
            prev.duration = curr.onset - prev.onset
            if prev.duration < 0.01:  # 너무 짧아지면 제거
                result.pop()
        
        result.append(curr)
    
    return result
```

#### 5. 전체 멜로디 추출 파이프라인

```python
def extract_melody(midi_path: Path) -> List[Note]:
    """
    MIDI에서 멜로디 추출 전체 파이프라인
    
    순서:
    1. MIDI 파싱 → Note 리스트
    2. Skyline 적용 (동시 발음 → 최고음)
    3. 짧은 음표 제거 (< 50ms)
    4. Overlap 해결
    5. 옥타브 정규화 (C3-C6)
    """
    # 1. MIDI 파싱
    notes = parse_midi(midi_path)
    
    # 2. Skyline
    notes = apply_skyline(notes)
    
    # 3. 짧은 음표 제거
    notes = filter_short_notes(notes)
    
    # 4. Overlap 해결
    notes = resolve_overlaps(notes)
    
    # 5. 옥타브 정규화
    notes = normalize_octave(notes, min_pitch=48, max_pitch=84)  # C3-C6
    
    return notes
```

---

**References**:

*외부 근거 (읽을 자료):*
- pretty_midi (SSOT): https://craffel.github.io/pretty-midi/
- Skyline Algorithm 참고: 동시 발음 시 max(pitch) 선택
- Note: mido는 pretty_midi 내부 의존성으로만 사용, 직접 호출 금지

*생성할 파일:*
- `backend/core/melody_extractor.py` - Skyline 알고리즘 및 위 정책 구현

**Acceptance Criteria**:
- [x] 폴리포닉 → 모노포닉 변환 성공
- [x] 단선율 MIDI 출력 (동시 발음 수 = 1)
- [x] 테스트 곡 3개 검증:
  - **객관적 기준**: Golden Test 입력 3곡에 대해 `core_similarity ≥ 70%` (최종 85% 전 중간 목표)
  - **청취 체크리스트** (보조):
    - [ ] 주요 멜로디 라인이 인식 가능한가?
    - [ ] 반주/화음이 제거되었는가?
    - [ ] 음정이 원곡과 대체로 일치하는가?

**Commit**: `feat(backend): implement melody extraction from polyphonic MIDI`

---

### Task 5: MIDI → MusicXML 변환 유틸리티

> **역할 정의**: Task 5는 **공통 유틸리티 모듈**입니다. Task 7이 이 모듈을 사용합니다.
> Task 5 자체는 독립 실행 가능한 변환기가 아니라, Task 7의 기반 함수를 제공합니다.

**What to do**:
- `notes_to_stream()` 함수 구현 (List[Note] → music21.stream.Stream)
- `stream_to_musicxml()` 함수 구현 (Stream → MusicXML 문자열)
- `notes_to_musicxml()` 편의 함수 (위 두 함수 조합)
- 박자표 설정 (4/4 고정)
- 조표 설정 (파라미터로 받음)
- 퀀타이즈 (16분음표 그리드)

**Task 5 ↔ Task 7 관계 (중요):**
```
Task 5 제공:
├── notes_to_stream(notes, bpm, key) → music21.stream.Stream  # 코드 심볼 추가 가능
├── stream_to_musicxml(stream) → str                          # 최종 문자열 변환
├── notes_to_musicxml(notes, bpm, key) → str                  # 편의 함수
├── seconds_to_quarter_length(seconds, bpm) → float
└── quantize_notes(notes, grid) → List[Note]

Task 7 사용 (코드 심볼 포함):
melody.mid ──→ parse_midi() ──→ List[Note]
                                    │
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
            adjust(easy)    adjust(medium)   adjust(hard)
                    ↓               ↓               ↓
            List[Note]      List[Note]       List[Note]
                    │               │               │
                    ↓               ↓               ↓
            notes_to_stream() ← Task 5 함수 (Stream 반환)
                    │               │               │
                    ↓               ↓               ↓
            add_chord_symbols(stream, chords) ← Task 7에서 Stream에 직접 추가
                    │               │               │
                    ↓               ↓               ↓
            stream_to_musicxml() ← Task 5 함수 (문자열 변환)
                    ↓               ↓               ↓
            sheet_easy.xml  sheet_medium.xml  sheet_hard.xml
```

**핵심 함수 (Task 5에서 구현):**
```python
# backend/core/midi_to_musicxml.py

def notes_to_stream(
    notes: List[Note], 
    bpm: float, 
    key: str,
    time_signature: str = "4/4"
) -> music21.stream.Stream:
    """
    Note 리스트를 music21 Stream 객체로 변환
    
    Args:
        notes: 초 단위 Note 리스트
        bpm: 템포
        key: 조성 (예: "C major")
        time_signature: 박자표 (기본 4/4)
    
    Returns:
        music21.stream.Stream 객체 (코드 심볼 추가 가능)
    """
    stream = music21.stream.Stream()
    
    # 메타데이터 설정
    stream.append(music21.tempo.MetronomeMark(number=bpm))
    stream.append(music21.key.Key(key))
    stream.append(music21.meter.TimeSignature(time_signature))
    
    # Note 변환 (초 → quarterLength)
    for n in notes:
        m21_note = music21.note.Note(n.pitch)
        m21_note.offset = seconds_to_quarter_length(n.onset, bpm)
        m21_note.duration.quarterLength = seconds_to_quarter_length(n.duration, bpm)
        m21_note.volume.velocity = n.velocity
        stream.append(m21_note)
    
    # 퀀타이즈 (16분음표 그리드)
    stream.quantize(quarterLengthDivisors=[4], inPlace=True)
    
    return stream


def stream_to_musicxml(stream: music21.stream.Stream) -> str:
    """
    music21 Stream을 MusicXML 문자열로 변환
    
    Args:
        stream: music21.stream.Stream 객체
    
    Returns:
        MusicXML 문자열
    """
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.musicxml', delete=False) as f:
        temp_path = f.name
    
    stream.write('musicxml', fp=temp_path)
    
    with open(temp_path, 'r', encoding='utf-8') as f:
        musicxml_str = f.read()
    
    Path(temp_path).unlink()  # 임시 파일 삭제
    return musicxml_str


def notes_to_musicxml(
    notes: List[Note], 
    bpm: float, 
    key: str,
    time_signature: str = "4/4"
) -> str:
    """
    Note 리스트를 MusicXML 문자열로 변환 (편의 함수)
    
    내부적으로 notes_to_stream() + stream_to_musicxml() 호출
    코드 심볼 추가가 필요하면 notes_to_stream()을 직접 사용
    """
    stream = notes_to_stream(notes, bpm, key, time_signature)
    return stream_to_musicxml(stream)
```

**박자표 정책 (단순화):**
- **4/4 고정**: 모든 곡을 4/4 박자로 생성
- 3/4, 6/8, 변박 등은 지원하지 않음
- 이유: 박자 감지의 복잡성 대비 취미 연주자에게 4/4가 가장 익숙함

**퀀타이즈 설정:**
- `quarterLengthDivisors=[4]`: 4분음표를 4등분 → 16분음표 그리드
- 셋잇단음표(`[3]`)는 제외: 단순화 목적

**Must NOT do**:
- 독립 실행 가능한 CLI/스크립트 (유틸리티 모듈만)
- 코드 심볼 추가 (Task 7에서 처리)

**Parallelizable**: NO (Task 4 필요)

**References**:

*외부 근거 (읽을 자료):*
- music21 공식: https://www.music21.org/music21docs/
- MIDI 파싱: `converter.parse('file.mid')`
- MusicXML 출력: `stream.write('musicxml', fp='output.musicxml')`

*퀀타이즈 설명:*
- `stream.quantize(quarterLengthDivisors=[4, 3])` 의미:
  - `4`: 4분음표를 4등분 → 16분음표 그리드
  - `3`: 4분음표를 3등분 → 셋잇단음표 그리드
  - 두 값 모두 지정하면 가장 가까운 그리드에 맞춤
- 본 프로젝트에서는 `[4]`만 사용 (16분음표 그리드, 셋잇단 제외)

*생성할 파일:*
- `backend/core/midi_to_musicxml.py` - music21 기반 변환 함수

*참조할 계획서 섹션:*
- "Time Unit Convention" - 초 ↔ quarterLength 변환 함수

**Acceptance Criteria**:
- [x] `notes_to_stream()` 함수 구현 완료
- [x] `stream_to_musicxml()` 함수 구현 완료
- [x] `notes_to_musicxml()` 편의 함수 구현 완료
- [ ] 테스트: 샘플 Note 리스트 → Stream → MusicXML 변환 성공
- [ ] 생성된 MusicXML이 MuseScore에서 정상 렌더링
- [ ] 음표가 16분음표 그리드에 정렬됨

**Commit**: `feat(backend): implement notes_to_stream and stream_to_musicxml utilities`

---

### Task 6: 코드/BPM/조성 자동 감지

**What to do**:
- librosa로 BPM 감지: `beat.beat_track()`
- librosa로 Key 감지: chroma + Krumhansl-Schmuckler 알고리즘
- **코드 감지: librosa chroma 기반 자체 구현** (외부 의존성 최소화)
- 신뢰도 점수 계산
- JSON 형태로 반환

---

**Key 감지 알고리즘 (Krumhansl-Schmuckler) - SSOT 구현:**

```python
import numpy as np
import librosa

# Krumhansl-Schmuckler 프로파일 (SSOT)
# 출처: Krumhansl, C. L. (1990). Cognitive Foundations of Musical Pitch
KS_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# 12개 루트 (C=0, C#=1, ..., B=11)
ROOT_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def detect_key(y, sr) -> tuple[str, float]:
    """
    Krumhansl-Schmuckler 알고리즘으로 Key 감지
    
    Args:
        y: 오디오 신호
        sr: 샘플레이트
    
    Returns:
        (key_name, confidence): 예) ("C major", 0.85)
    
    알고리즘:
    1. Chroma 특성 추출 (12개 피치 클래스)
    2. 전체 프레임 평균으로 chroma 벡터 생성
    3. 12개 루트 × 2 (major/minor) = 24개 후보에 대해 상관계수 계산
    4. 가장 높은 상관계수를 가진 key 선택
    """
    # 1. Chroma 추출 (CQT 기반, 더 정확함)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    
    # 2. 전체 프레임 평균
    chroma_mean = np.mean(chroma, axis=1)
    
    # 3. 24개 후보에 대해 상관계수 계산
    best_key = None
    best_corr = -1
    
    for root in range(12):
        # 프로파일을 root만큼 회전
        major_profile = np.roll(KS_MAJOR_PROFILE, root)
        minor_profile = np.roll(KS_MINOR_PROFILE, root)
        
        # Pearson 상관계수
        major_corr = np.corrcoef(chroma_mean, major_profile)[0, 1]
        minor_corr = np.corrcoef(chroma_mean, minor_profile)[0, 1]
        
        if major_corr > best_corr:
            best_corr = major_corr
            best_key = f"{ROOT_NAMES[root]} major"
        
        if minor_corr > best_corr:
            best_corr = minor_corr
            best_key = f"{ROOT_NAMES[root]} minor"
    
    # 4. confidence 정규화 (상관계수 범위: -1 ~ 1 → 0 ~ 1)
    confidence = (best_corr + 1) / 2
    
    return best_key, confidence
```

---

**코드 감지 알고리즘 (Chroma 템플릿 매칭) - SSOT 구현:**

```python
def detect_chords(y, sr, hop_length=512):
    """
    librosa chroma를 사용한 간단한 코드 감지
    - 외부 의존성 없음 (chord-extractor/Vamp 불필요)
    - 정확도는 낮지만 사용자가 수동 수정 가능
    """
    # Chroma 특성 추출
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    
    # 코드 템플릿 (major, minor) - 12개 루트 × 2 = 24개
    # 인덱스: C=0, C#=1, D=2, D#=3, E=4, F=5, F#=6, G=7, G#=8, A=9, A#=10, B=11
    CHORD_TEMPLATES = {
        # Major: root + major 3rd (4 semitones) + perfect 5th (7 semitones)
        'C': [1,0,0,0,1,0,0,1,0,0,0,0],
        'C#': [0,1,0,0,0,1,0,0,1,0,0,0],
        'D': [0,0,1,0,0,0,1,0,0,1,0,0],
        'D#': [0,0,0,1,0,0,0,1,0,0,1,0],
        'E': [0,0,0,0,1,0,0,0,1,0,0,1],
        'F': [1,0,0,0,0,1,0,0,0,1,0,0],
        'F#': [0,1,0,0,0,0,1,0,0,0,1,0],
        'G': [0,0,1,0,0,0,0,1,0,0,0,1],
        'G#': [1,0,0,1,0,0,0,0,1,0,0,0],
        'A': [0,1,0,0,1,0,0,0,0,1,0,0],
        'A#': [0,0,1,0,0,1,0,0,0,0,1,0],
        'B': [0,0,0,1,0,0,1,0,0,0,0,1],
        # Minor: root + minor 3rd (3 semitones) + perfect 5th (7 semitones)
        'Cm': [1,0,0,1,0,0,0,1,0,0,0,0],
        'C#m': [0,1,0,0,1,0,0,0,1,0,0,0],
        'Dm': [0,0,1,0,0,1,0,0,0,1,0,0],
        'D#m': [0,0,0,1,0,0,1,0,0,0,1,0],
        'Em': [0,0,0,0,1,0,0,1,0,0,0,1],
        'Fm': [1,0,0,0,0,1,0,0,1,0,0,0],
        'F#m': [0,1,0,0,0,0,1,0,0,1,0,0],
        'Gm': [0,0,1,0,0,0,0,1,0,0,1,0],
        'G#m': [0,0,0,1,0,0,0,0,1,0,0,1],
        'Am': [1,0,0,0,1,0,0,0,0,1,0,0],
        'A#m': [0,1,0,0,0,1,0,0,0,0,1,0],
        'Bm': [0,0,1,0,0,0,1,0,0,0,0,1],
    }
    
    # 각 프레임에서 가장 유사한 코드 찾기
    chords = []
    for i, frame in enumerate(chroma.T):
        best_chord, best_score = match_chord(frame, CHORD_TEMPLATES)
        time = librosa.frames_to_time(i, sr=sr, hop_length=hop_length)
        chords.append({"time": time, "chord": best_chord, "confidence": best_score})
    
    # 연속된 동일 코드 병합 + duration 계산
    return merge_consecutive_chords(chords, sr, hop_length)


def match_chord(frame: np.ndarray, templates: dict) -> tuple[str, float]:
    """
    단일 chroma 프레임과 템플릿 매칭
    
    Args:
        frame: 12차원 chroma 벡터 (정규화 전)
        templates: 코드명 → 템플릿 벡터 딕셔너리
    
    Returns:
        (best_chord, confidence): 가장 유사한 코드와 신뢰도
    
    매칭 방법:
    - 코사인 유사도 사용 (내적 / 노름 곱)
    - 신뢰도 = 코사인 유사도 (0~1 범위)
    """
    frame_norm = np.linalg.norm(frame)
    if frame_norm < 1e-6:  # 무음 프레임
        return "N", 0.0  # N = No chord
    
    frame_normalized = frame / frame_norm
    
    best_chord = "N"
    best_score = 0.0
    
    for chord_name, template in templates.items():
        template_arr = np.array(template, dtype=float)
        template_norm = np.linalg.norm(template_arr)
        template_normalized = template_arr / template_norm
        
        # 코사인 유사도
        similarity = np.dot(frame_normalized, template_normalized)
        
        if similarity > best_score:
            best_score = similarity
            best_chord = chord_name
    
    return best_chord, best_score


def merge_consecutive_chords(chords: list, sr: int, hop_length: int) -> list:
    """
    연속된 동일 코드를 병합하고 duration 계산
    
    Duration 산정 규칙 (SSOT):
    1. 연속된 동일 코드 프레임을 하나로 병합
    2. duration = 다음 코드의 time - 현재 코드의 time
    3. 마지막 코드의 duration = 남은 프레임 수 × hop_length / sr
    4. confidence = 병합된 프레임들의 confidence 평균
    """
    if not chords:
        return []
    
    merged = []
    current = chords[0].copy()
    confidence_sum = current["confidence"]
    frame_count = 1
    
    for next_chord in chords[1:]:
        if next_chord["chord"] == current["chord"]:
            # 동일 코드: 병합
            confidence_sum += next_chord["confidence"]
            frame_count += 1
        else:
            # 다른 코드: 현재 코드 저장
            current["duration"] = next_chord["time"] - current["time"]
            current["confidence"] = confidence_sum / frame_count
            merged.append(current)
            
            # 새 코드 시작
            current = next_chord.copy()
            confidence_sum = current["confidence"]
            frame_count = 1
    
    # 마지막 코드 처리
    frame_duration = hop_length / sr
    current["duration"] = frame_count * frame_duration
    current["confidence"] = confidence_sum / frame_count
    merged.append(current)
    
    return merged
```

**코드 표기 규칙 (SSOT):**

> **핵심 원칙**: 자동 감지는 단순, 수동 입력은 자유

| 구분 | 지원 범위 | 예시 |
|------|----------|------|
| **자동 감지** | Major/Minor 24개만 | "C", "Am", "F#m" |
| **수동 입력** | 모든 문자열 허용 | "C7", "Dm7", "Gsus4", "Bdim" |
| **렌더링** | 입력 그대로 표시 | MusicXML ChordSymbol에 그대로 전달 |

**자동 감지 코드 (librosa chroma 기반):**
- **Major**: 루트만 표기 (예: "C", "D", "E")
- **Minor**: 루트 + "m" (예: "Cm", "Dm", "Em")
- **지원 코드**: 12개 루트 × 2 (major/minor) = 24개만 감지
- **정확도 기대치**: ~60% (복잡한 코드는 감지 불가)

**수동 입력 코드 (API PUT 요청):**
- **제한 없음**: 사용자가 입력한 문자열을 그대로 저장
- **검증 없음**: "C7", "Dm7b5", "Gsus4" 등 자유 입력 허용
- **렌더링**: music21 ChordSymbol에 그대로 전달 (music21이 지원하는 범위 내 표시)

**API 예시:**
```json
// PUT /api/result/{job_id}
{
  "chords": [
    {"time": 0.0, "duration": 2.0, "chord": "C7"},      // 7th 코드 (수동 입력)
    {"time": 2.0, "duration": 2.0, "chord": "Dm7b5"},   // 복잡한 코드 (수동 입력)
    {"time": 4.0, "duration": 2.0, "chord": "G"}        // 단순 코드
  ]
}
```

**Must NOT do**:
- UI 구현
- 복잡한 코드 (7th, 9th, sus 등) - major/minor만 지원

**Parallelizable**: YES (Task 2 완료 후)

**References**:

*외부 근거 (읽을 자료):*
- librosa: https://librosa.org/doc/latest/
- BPM: `librosa.beat.beat_track(y=y, sr=sr)`
- Chroma: `librosa.feature.chroma_cqt(y=y, sr=sr)`
- Key detection: Krumhansl-Schmuckler 알고리즘 (librosa 예제 참고)

*생성할 파일:*
- `backend/core/audio_analysis.py` - BPM, Key, Chord 감지 함수

**Acceptance Criteria**:
- [x] BPM 감지 ±5 BPM 정확도 (알려진 BPM 곡 3개로 테스트)
- [x] Key 감지 (major/minor 구분)
- [x] 코드 진행 리스트 출력 (시간, 코드명, 신뢰도)
- [x] 코드 정확도 기대치: ~60% (사용자 수동 수정 전제)

**Commit**: `feat(backend): implement BPM, key, and chord detection`

---

### Task 7: 난이도 조절 시스템

**What to do**:
- 3단계 난이도 구현 (상단 "Difficulty Adjustment Rules" 참조)
- **입력**: melody.mid (Task 4 출력) + analysis.json (Task 6 출력)
- **처리**: MIDI → Note 리스트 → 난이도별 Note 리스트 → MusicXML
- **출력**: sheet_easy.musicxml, sheet_medium.musicxml, sheet_hard.musicxml (파일로 저장)
- 코드 심볼을 MusicXML에 추가 (analysis.json의 chords 사용)

**Task 5 ↔ Task 7 책임 분리:**
| 모듈 | 책임 | 반환값 |
|------|------|--------|
| Task 5 (`notes_to_stream`) | Note 리스트 → music21 Stream 변환 | `music21.stream.Stream` |
| Task 5 (`stream_to_musicxml`) | Stream → MusicXML 문자열 변환 | `str` (MusicXML 문자열) |
| Task 7 (`generate_sheets`) | 난이도 조절 + 코드 심볼 추가 + 파일 저장 | `dict[str, Path]` (저장된 파일 경로) |

**데이터 흐름 (Stream 기반 - SSOT)**:
```
melody.mid ──→ parse_midi() ──→ List[Note] (초 단위)
                                    │
                    ┌───────────────┼───────────────┐
                    ↓               ↓               ↓
            adjust(easy)    adjust(medium)   adjust(hard)
                    ↓               ↓               ↓
            List[Note]      List[Note]       List[Note]
                    │               │               │
                    ↓               ↓               ↓
            notes_to_stream() ← Task 5 함수 (Stream 반환)
                    │               │               │
                    ↓               ↓               ↓
            add_chord_symbols(stream, chords) ← Task 7에서 Stream에 직접 삽입
                    │               │               │
                    ↓               ↓               ↓
            stream_to_musicxml() ← Task 5 함수 (문자열 변환)
                    │               │               │
                    ↓               ↓               ↓
            save_to_file() ← Task 7에서 파일 저장
                    ↓               ↓               ↓
            sheet_easy.xml  sheet_medium.xml  sheet_hard.xml
```

**파일 저장 함수 (Task 7):**
```python
def generate_all_sheets(
    job_dir: Path,
    melody_mid: Path,
    analysis: AnalysisSchema
) -> dict[str, Path]:
    """
    3가지 난이도의 MusicXML 파일 생성 및 저장
    
    Returns:
        {"easy": Path, "medium": Path, "hard": Path}
    """
    # 1. MIDI → Note 리스트
    notes = parse_midi(melody_mid)  # SSOT: bpm 인자 없음, 초 단위 반환
    
    # 2. 난이도별 처리 및 저장
    result = {}
    for difficulty in ["easy", "medium", "hard"]:
        # 난이도 조절
        adjusted_notes = adjust_difficulty(notes, difficulty, analysis.bpm)
        
        # music21 Stream 생성 (Task 5 함수 호출)
        stream = notes_to_stream(
            adjusted_notes, 
            analysis.bpm, 
            analysis.key
        )
        
        # 코드 심볼을 Stream에 직접 추가 (MusicXML 파싱 없음!)
        add_chord_symbols(stream, analysis.chords, analysis.bpm)
        
        # Stream → MusicXML 문자열 변환 (Task 5 함수 호출)
        musicxml_str = stream_to_musicxml(stream)
        
        # 파일 저장 (SSOT: write_file_atomic 사용!)
        output_path = job_dir / f"sheet_{difficulty}.musicxml"
        write_file_atomic(output_path, musicxml_str)  # 원자적 쓰기!
        
        result[difficulty] = output_path
    
    return result
```

**Must NOT do**:
- UI 구현
- MusicXML 문자열 직접 파싱 (Stream 기반으로 처리)

**Parallelizable**: NO (Task 4, 5, 6 필요)

**References**:

*외부 근거 (읽을 자료):*
- pretty_midi (SSOT): MIDI → Note 리스트 파싱 (parse_midi 함수 참조)
- music21: Note 리스트 → Stream → MusicXML 생성
- Chord Symbol: `music21.harmony.ChordSymbol('C')`

*생성할 파일:*
- `backend/core/difficulty_adjuster.py` - 난이도별 Note 변환 함수

*참조할 계획서 섹션:*
- "Difficulty Adjustment Rules" - 난이도별 변환 규칙 상세
- "Time Unit Convention" - 초 단위 처리 방식

**코드 심볼 배치 규칙:**
```python
def add_chord_symbols(stream: music21.stream.Stream, chords: List[ChordInfo], bpm: float):
    """
    analysis.json의 코드 정보를 MusicXML에 추가
    
    배치 규칙:
    1. 코드의 time(초)을 quarterLength로 변환
    2. 해당 offset에 ChordSymbol 삽입
    3. 마디 경계와 무관하게 정확한 위치에 배치
    """
    for chord_info in chords:
        offset_ql = seconds_to_quarter_length(chord_info.time, bpm)
        
        # music21 ChordSymbol 생성
        cs = music21.harmony.ChordSymbol(chord_info.chord)
        cs.offset = offset_ql
        
        stream.insert(offset_ql, cs)
    
    return stream

# 예시: BPM=120, chord at time=2.0초
# offset_ql = 2.0 * (120/60) = 4.0 quarterLengths = 1마디 시작점
```

**Acceptance Criteria**:
- [x] 3가지 난이도 MusicXML 생성
- [x] 초급: 음표 수 ≤ 고급의 50%
- [x] 코드 심볼이 악보에 표시됨 (analysis.json 기반)
- [ ] 모든 MusicXML이 MuseScore에서 정상 렌더링

**Commit**: `feat(backend): implement difficulty adjustment system`

---

### Task 8: FastAPI 엔드포인트 + Job System

**What to do**:
- Job 상태 관리 시스템 구현 (상단 "Backend Job Processing Architecture" 참조)
- API 엔드포인트 구현 (상단 "API Schema Definition" 참조)
- Background task로 처리 실행
- 파일 크기/길이 제한 적용
- 에러 핸들링

**Must NOT do**:
- 사용자 인증
- 영구 저장 (DB)

**Parallelizable**: NO (Task 3, 5, 6, 7 필요)

**References**:

*외부 근거 (읽을 자료):*
- FastAPI File Upload: https://fastapi.tiangolo.com/tutorial/request-files/
- Pydantic v2: https://docs.pydantic.dev/latest/

*생성할 파일:*
- `backend/api/upload.py` - POST /api/upload 엔드포인트
- `backend/api/youtube.py` - POST /api/youtube 엔드포인트
- `backend/api/status.py` - GET /api/status/{job_id}
- `backend/api/result.py` - GET/PUT /api/result/{job_id}
- `backend/api/download.py` - GET /api/download/{job_id}/{format}
- `backend/core/job_manager.py` - Job 상태 관리, 백그라운드 실행
- `backend/core/progress.py` - **진행률 계산 SSOT** (`get_stage_ranges()` 함수 포함, 하드코딩 금지)

*참조할 계획서 섹션:*
- "Backend Job Processing Architecture" - 상태 머신, 진행률, TTL
- "Job Lifecycle" - `asyncio.create_task()` + `run_in_executor` 패턴 (BackgroundTasks 사용 안 함!)
- "API Schema Definition" - 요청/응답 형식
- "File Size & Duration Limit Implementation" - 50MB/20분 제한 구현

**Acceptance Criteria**:
- [x] POST /api/upload → job_id 반환
- [x] POST /api/youtube → job_id 반환
- [x] GET /api/status/{job_id} → progress 0-100%
- [x] GET /api/result/{job_id} → 분석 결과 + 다운로드 URL
- [x] PUT /api/result/{job_id} → 수정 후 재생성
- [x] GET /api/download/{job_id}/{format} → 파일 다운로드

**Commit**: `feat(backend): implement FastAPI endpoints with job system`

---

### Task 9: 프론트엔드 - 업로드 UI

**What to do**:
- 탭 UI: "파일 업로드" / "YouTube URL"
- 드래그 앤 드롭 파일 업로드
- YouTube URL 입력 필드
- 진행률 표시 (업로드 + 처리)
- 에러 메시지 표시
- 면책 조항 (YouTube 사용 시)

**Must NOT do**:
- 악보 렌더링 (Task 10)

**Parallelizable**: YES (Task 10, 11, 12와 병렬)

**References**:

*외부 근거 (읽을 자료):*
- react-dropzone: https://react-dropzone.js.org/
- TanStack Query: https://tanstack.com/query/latest
- YouTube URL 정규식: `^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$`

*생성할 파일:*
- `frontend/components/FileUpload.tsx` - 드래그 앤 드롭 업로드 컴포넌트
- `frontend/components/YouTubeInput.tsx` - YouTube URL 입력 컴포넌트
- `frontend/components/ProgressBar.tsx` - 진행률 표시 컴포넌트

*참조할 계획서 섹션:*
- "File Size & Duration Limit Implementation" - 프론트엔드 선차단 (50MB)

*업로드 진행률 구현 결정:*
- 업로드 진행률: **생략** (fetch API 제한)
- 서버 처리 진행률만 표시 (GET /api/status 폴링)
- 이유: XHR/axios 없이 fetch만 사용, 복잡성 감소

**Acceptance Criteria**:
- [ ] 파일 드래그 앤 드롭 동작
- [ ] 50MB 초과 파일 선차단 (업로드 전 에러 표시)
- [ ] YouTube URL 입력 및 제출
- [ ] 서버 처리 진행률 바 표시 (0-100%)
- [ ] 에러 메시지 표시
- [ ] **프록시 검증**: 아래 curl 명령으로 멀티파트 업로드가 프록시를 통해 백엔드로 전달되는지 확인
  ```bash
  # 프록시 경유 업로드 테스트 (docker-compose up 상태에서)
  # 먼저 테스트 오디오 복사: docker cp $(docker-compose ps -q backend):/app/tests/fixtures/test_audio.mp3 ./
  curl -X POST http://localhost:3000/api/upload \
    -F "file=@test_audio.mp3" \
    -v
  # 기대 응답: {"job_id": "...", "status": "pending"}
  # 실패 시: 502 Bad Gateway 또는 CORS 에러
  ```

**Commit**: `feat(frontend): implement upload UI with file and YouTube support`

---

### Task 10: 프론트엔드 - 악보 렌더링

**What to do**:
- OpenSheetMusicDisplay 통합
- MusicXML 로드 및 렌더링
- 줌 인/아웃
- 반응형 레이아웃

**Must NOT do**:
- 악보 편집

**Parallelizable**: YES (Task 9와 병렬)

**References**:

*외부 근거 (읽을 자료):*
- OSMD: https://opensheetmusicdisplay.org/
- npm: `opensheetmusicdisplay`
- React 통합 패턴:
  ```tsx
  useEffect(() => {
    const osmd = new OpenSheetMusicDisplay(containerRef.current);
    osmd.load(musicxmlString).then(() => osmd.render());
  }, [musicxmlString]);
  ```
- SSR 회피: `dynamic(() => import('./SheetViewer'), { ssr: false })`

*생성할 파일:*
- `frontend/components/SheetViewer.tsx` - OSMD 래퍼 컴포넌트

**Acceptance Criteria**:
- [x] MusicXML 렌더링 성공
- [x] 코드 심볼 표시
- [x] 줌 동작

**Commit**: `feat(frontend): integrate OpenSheetMusicDisplay for sheet rendering`

---

### Task 11: 프론트엔드 - 수정 UI

**What to do**:
- BPM 입력 필드 (숫자 입력, 40-240 범위)
- Key 선택 드롭다운 (12 major + 12 minor = 24개 옵션)
- 코드 진행 편집 (시간별)
- 난이도 선택 (탭/드롭다운)
- 수정 시 API 호출 → 악보 새로고침

**코드 시간 입력 UX (SSOT):**
> 백엔드 `ChordInfo.time`은 **초(float)** 단위입니다.
> 프론트엔드에서는 사용자 친화적인 **mm:ss.ms** 형식으로 표시/입력합니다.

| 필드 | 표시 형식 | 입력 형식 | 백엔드 변환 |
|------|----------|----------|------------|
| 코드 시간 | `01:23.5` | `mm:ss.s` (분:초.소수점) | `83.5` (초) |

**시간 변환 함수 (프론트엔드):**
```typescript
// 초 → mm:ss.s 표시
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  return `${mins.toString().padStart(2, '0')}:${secs.padStart(4, '0')}`;
}

// mm:ss.s → 초 변환
function parseTime(timeStr: string): number {
  const [mins, secs] = timeStr.split(':');
  return parseInt(mins) * 60 + parseFloat(secs);
}
```

**코드 편집 UI 구성:**
- 기존 코드 목록 표시 (시간순 정렬)
- 각 코드: [시간 입력] [코드명 입력] [삭제 버튼]
- [+ 코드 추가] 버튼
- 저장 시 PUT `/api/result/{job_id}`로 전송 (API Schema 참조)

**Must NOT do**:
- 음표 단위 편집
- 마디 기반 시간 입력 (초 단위만 지원)
- 자동 스냅 (정확한 시간 입력 필요)

**Parallelizable**: YES (Task 9, 10과 병렬)

**References**:

*외부 근거 (읽을 자료):*
- React Hook Form: https://react-hook-form.com/
- Headless UI: https://headlessui.com/

*생성할 파일:*
- `frontend/components/EditPanel.tsx` - BPM/Key/Chord 수정 패널
- `frontend/components/DifficultySelector.tsx` - 난이도 선택 UI
- `frontend/utils/timeFormat.ts` - 시간 변환 유틸리티

**Acceptance Criteria**:
- [ ] BPM 수정 → 저장 → 반영
- [ ] Key 수정 → 저장 → 반영
- [ ] 코드 시간 입력: `01:30.0` 입력 → 백엔드에 `90.0` 전송
- [ ] 코드 시간 표시: 백엔드 `90.0` → UI에 `01:30.0` 표시
- [ ] 난이도 변경 → 악보 변경

**Commit**: `feat(frontend): implement editing UI for BPM, key, chords, difficulty`

---

### Task 12: 프론트엔드 - 다운로드 기능

**What to do**:
- MIDI 다운로드 버튼
- MusicXML 다운로드 버튼
- 파일명: `{원본이름}_{난이도}.{확장자}`

**Parallelizable**: YES (Task 9, 10, 11과 병렬)

**References**:

*외부 근거 (읽을 자료):*
- file-saver 또는 native `<a download>`

*생성할 파일:*
- `frontend/components/DownloadButtons.tsx` - MIDI/MusicXML 다운로드 버튼

**Acceptance Criteria**:
- [ ] MIDI 다운로드 → .mid 파일
- [ ] MusicXML 다운로드 → .musicxml 파일
- [ ] 파일이 MuseScore에서 열림

**Commit**: `feat(frontend): implement download functionality`

---

### Task 13: Docker 설정 완성

**What to do**:
- backend Dockerfile 완성 (ffmpeg 포함)
- frontend Dockerfile 완성
- docker-compose.yml 완성
- 볼륨 설정 (/tmp/piano-sheet-jobs)
- 헬스체크

**Parallelizable**: NO (Task 8, 12 필요)

**References**:

*외부 근거 (읽을 자료):*
- Next.js Docker: https://nextjs.org/docs/pages/building-your-application/deploying#docker-image

*수정할 파일:*
- `backend/Dockerfile` - 완성 (ffmpeg, libsndfile1 포함)
- `frontend/Dockerfile` - 완성
- `docker-compose.yml` - 볼륨, 헬스체크 추가

*참조할 계획서 섹션:*
- "Docker Environment Requirements" - Dockerfile 템플릿, 시스템 의존성

**Acceptance Criteria**:
- [ ] `docker-compose up --build` 한 번에 실행
- [ ] localhost:3000 → 프론트엔드
- [ ] localhost:8000 → 백엔드 API
- [ ] 전체 플로우 동작

**Commit**: `chore(docker): complete Docker setup`

---

### Task 14: Golden Test 시스템 구축 (Phase 1: Smoke 모드)

> **현재 범위**: Reference MIDI 없이 Smoke 모드로 처리 성공 여부만 검증
> **추후 확장**: Reference MIDI 준비 후 Full 모드(정확도 측정) 추가

**What to do**:
- Smoke 모드 테스트 프레임워크 구현
- 다양한 장르(대중가요, OST, 클래식, 동요 등) 테스트 데이터 구조 설정
- pytest 통합
- 리포트 생성 (JSON + HTML)
- (추후) Full 모드 비교 알고리즘은 Reference MIDI 준비 후 구현

**Parallelizable**: YES (Task 8 완료 후)

**References**:

*외부 근거 (읽을 자료):*
- pytest: https://docs.pytest.org/
- pytest-html: https://pytest-html.readthedocs.io/

*생성할 파일:*
- `backend/tests/golden/test_golden.py` - Smoke 모드 pytest 테스트 케이스
- `backend/tests/golden/conftest.py` - pytest fixtures
- `backend/tests/golden/comparator.py` - (추후) Note 비교 알고리즘 (Full 모드용)

*참조할 계획서 섹션:*
- "Golden Test Comparison Algorithm" - Phase 1/2 구분, Smoke 모드 검증 기준

**Acceptance Criteria (Phase 1 - Smoke 모드)**:
- [ ] `docker-compose exec backend pytest tests/golden/` 실행 가능
- [ ] 테스트 곡 5개 이상 (다양한 장르: pop, ost, classical, children 등)
- [ ] 각 곡에서 처리 성공 (status=completed) 확인
- [ ] 출력 파일 존재 확인 (melody.mid, sheet_*.musicxml)
- [ ] 리포트에 각 곡 처리 결과 및 소요 시간 기록

**추후 구현 (Phase 2 - Full 모드)**:
- [ ] Reference MIDI 준비 후 정확도 측정 기능 추가
- [ ] 핵심 멜로디 모드 85% 기준 적용

**Commit**: `feat(tests): implement Golden Test smoke mode framework`

---

### Task 15: Playwright MCP 기반 E2E 테스트

> **테스트 방식**: Playwright MCP (Model Context Protocol)를 사용하여 E2E 테스트를 수행합니다.
> 별도의 테스트 스크립트 파일 대신, AI 에이전트가 Playwright MCP 도구를 직접 호출하여 테스트합니다.

**What to do**:
- Playwright MCP 도구를 사용한 E2E 테스트 시나리오 문서화
- 테스트용 샘플 오디오 생성 스크립트 작성
- 테스트 실행 가이드 작성

**Parallelizable**: NO (Task 13 필요)

**References**:

*외부 근거 (읽을 자료):*
- Playwright MCP: `mcp_playwright_*` 도구들 (browser_navigate, browser_snapshot, browser_click, browser_file_upload 등)

*생성할 파일:*
- `backend/scripts/generate_test_audio.py` - 테스트용 오디오 생성
- `backend/tests/e2e/README.md` - E2E 테스트 실행 가이드

*참조할 계획서 섹션:*
- "E2E Test Scenarios" - 테스트 시나리오 목록

---

## Playwright MCP E2E 테스트 가이드

### 테스트 방식 설명

본 프로젝트의 E2E 테스트는 **Playwright MCP**를 사용합니다:
- 전통적인 `*.spec.ts` 파일 대신, AI 에이전트가 MCP 도구를 직접 호출
- 테스트 시나리오는 문서로 정의하고, 실행은 대화형으로 수행
- 스크린샷과 스냅샷으로 결과 검증

**장점:**
- 테스트 코드 유지보수 불필요
- UI 변경에 유연하게 대응
- 자연어로 테스트 시나리오 정의 가능

### 테스트용 오디오 생성

```python
# backend/scripts/generate_test_audio.py
"""
E2E 테스트용 샘플 오디오 생성
- 저작권 문제 없는 합성 오디오
- 단순한 멜로디 (C major scale)
"""
import numpy as np
from scipy.io import wavfile
import subprocess
from pathlib import Path

def generate_test_audio():
    output_dir = Path('/app/tests/fixtures')  # Docker 컨테이너 내 경로
    output_dir.mkdir(parents=True, exist_ok=True)
    
    sr = 44100
    duration = 10  # 10초
    
    # C major scale (C4-C5)
    frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
    
    audio = np.array([], dtype=np.float32)
    for freq in frequencies:
        t = np.linspace(0, duration/8, int(sr * duration/8), False)
        note = np.sin(2 * np.pi * freq * t) * 0.5
        # Envelope (fade in/out)
        envelope = np.ones_like(note)
        fade_len = int(sr * 0.05)
        envelope[:fade_len] = np.linspace(0, 1, fade_len)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)
        audio = np.concatenate([audio, note * envelope])
    
    # WAV 저장
    wav_path = output_dir / 'test_audio.wav'
    wavfile.write(str(wav_path), sr, (audio * 32767).astype(np.int16))
    
    # MP3 변환 (ffmpeg)
    mp3_path = output_dir / 'test_audio.mp3'
    subprocess.run([
        'ffmpeg', '-y', '-i', str(wav_path),
        '-codec:a', 'libmp3lame', '-qscale:a', '2',
        str(mp3_path)
    ], check=True)
    
    # WAV 삭제 (MP3만 필요)
    wav_path.unlink()
    
    print(f"Generated: {mp3_path} (10초, C major scale)")
    return mp3_path

if __name__ == "__main__":
    generate_test_audio()
```

### E2E 테스트 시나리오 (Playwright MCP 사용)

각 시나리오는 AI 에이전트가 다음 MCP 도구들을 순차적으로 호출하여 실행합니다:

#### 시나리오 1: MP3 업로드 → 처리 → 결과 확인

```
1. browser_navigate: http://localhost:3000
2. browser_snapshot: 초기 화면 확인
3. browser_file_upload: tests/fixtures/test_audio.mp3 업로드
4. browser_snapshot: 업로드 후 상태 확인
5. browser_wait_for: 처리 완료 대기 (progress 100% 또는 완료 메시지)
6. browser_snapshot: 결과 화면 확인
7. browser_click: 악보 렌더링 영역 확인
8. browser_take_screenshot: 최종 결과 스크린샷 저장
```

**검증 포인트 (관찰 가능한 UI 조건):**
- [ ] 파일 업로드 UI가 정상 표시되는가 → 화면에 "파일 업로드" 또는 "드래그 앤 드롭" 텍스트 존재
- [ ] 업로드 후 진행률이 표시되는가 → 프로그레스 바 또는 "처리 중" 텍스트 존재
- [ ] 처리 완료 후 악보가 렌더링되는가 → OSMD 컨테이너에 `<svg>` 또는 `<canvas>` 요소 존재
- [ ] 다운로드 버튼이 활성화되는가 → "MIDI 다운로드", "MusicXML 다운로드" 버튼이 `disabled` 아님

#### 시나리오 2: 난이도 변경

```
1. (시나리오 1 완료 후)
2. browser_snapshot: 현재 상태 확인
3. browser_click: 난이도 선택 드롭다운/탭
4. browser_click: "초급" 선택
5. browser_wait_for: 악보 변경 대기
6. browser_snapshot: 초급 악보 확인
7. browser_click: "고급" 선택
8. browser_wait_for: 악보 변경 대기
9. browser_snapshot: 고급 악보 확인 (음표 수 증가)
```

**검증 포인트 (관찰 가능한 UI 조건):**
- [ ] 난이도 선택 UI가 동작하는가 → "초급", "중급", "고급" 탭/버튼 존재 및 클릭 가능
- [ ] 난이도 변경 시 악보가 업데이트되는가 → OSMD 컨테이너 내용 변경 (SVG 재렌더링)
- [ ] 초급 악보가 고급보다 단순한가 → 스크린샷 비교 (음표 수 시각적 차이)

#### 시나리오 3: BPM/Key 수정

```
1. (시나리오 1 완료 후)
2. browser_snapshot: 현재 분석 결과 확인
3. browser_click: BPM 입력 필드
4. browser_type: 새 BPM 값 입력 (예: 140)
5. browser_click: 저장/적용 버튼
6. browser_wait_for: 재생성 완료 대기
7. browser_snapshot: 변경된 결과 확인
```

**검증 포인트 (관찰 가능한 UI 조건):**
- [ ] BPM 수정 UI가 동작하는가 → BPM 입력 필드에 값 입력 가능
- [ ] 수정 후 재생성이 트리거되는가 → "재생성 중" 또는 "저장 중" 텍스트/스피너 표시
- [ ] 변경된 값이 반영되는가 → 저장 후 BPM 필드에 새 값 표시, 악보 재렌더링

#### 시나리오 4: 다운로드

```
1. (시나리오 1 완료 후)
2. browser_snapshot: 다운로드 버튼 확인
3. browser_click: MIDI 다운로드 버튼
4. browser_snapshot: 다운로드 시작 확인
5. browser_click: MusicXML 다운로드 버튼
6. browser_snapshot: 다운로드 시작 확인
```

**검증 포인트 (관찰 가능한 UI 조건):**
- [ ] 다운로드 버튼이 클릭 가능한가 → "MIDI 다운로드", "MusicXML 다운로드" 버튼 `disabled` 아님
- [ ] 파일 다운로드가 트리거되는가 → 브라우저 다운로드 시작 (파일 저장 다이얼로그 또는 자동 다운로드)

#### 시나리오 5: 에러 케이스 - 파일 크기 초과

```
1. browser_navigate: http://localhost:3000
2. browser_file_upload: 50MB 초과 파일 (또는 시뮬레이션)
3. browser_snapshot: 에러 메시지 확인
```

**검증 포인트 (관찰 가능한 UI 조건):**
- [ ] 50MB 초과 시 에러 메시지가 표시되는가 → 화면에 "파일 크기 초과" 또는 "50MB" 포함 에러 텍스트 존재
- [ ] 업로드가 차단되는가

#### 시나리오 6: YouTube URL (선택적)

> ⚠️ YouTube 테스트는 외부 의존성이므로 **수동 테스트 권장**

```
1. browser_navigate: http://localhost:3000
2. browser_click: YouTube 탭
3. browser_type: YouTube URL 입력
4. browser_click: 제출 버튼
5. browser_wait_for: 처리 완료 대기
6. browser_snapshot: 결과 확인
```

### 테스트 실행 방법

```bash
# 1. Docker 환경 실행
docker-compose up -d

# 2. 테스트 오디오 생성 (최초 1회, Docker 내부에서 실행)
docker-compose exec backend python scripts/generate_test_audio.py

# 3. AI 에이전트에게 테스트 요청
# 예: "E2E 테스트 시나리오 1번을 실행해줘"
```

### 테스트 결과 저장 (증거물 산출 규칙)

**스크린샷 저장 규칙:**
- 위치: `.sisyphus/evidence/e2e/`
- 파일명 패턴: `scenario{N}_{step}_{description}.png`
- 예시:
  - `scenario1_01_initial_page.png`
  - `scenario1_02_after_upload.png`
  - `scenario1_03_processing_50percent.png`
  - `scenario1_04_completed_result.png`
  - `scenario1_05_sheet_rendered.png`

**필수 스크린샷 (시나리오별 최소 요건):**
| 시나리오 | 필수 스크린샷 수 | 필수 단계 |
|----------|-----------------|----------|
| 1 (업로드) | 5장 | 초기화면, 업로드후, 처리중, 완료, 악보렌더링 |
| 2 (난이도) | 3장 | 현재상태, 초급선택후, 고급선택후 |
| 3 (수정) | 3장 | 수정전, 수정중, 수정후 |
| 4 (다운로드) | 2장 | 다운로드버튼, 다운로드시작 |
| 5 (에러) | 2장 | 에러발생전, 에러메시지 |

**스냅샷 로그:**
- 각 `browser_snapshot` 호출 결과를 `.sisyphus/evidence/e2e/snapshots/` 에 저장
- 파일명: `scenario{N}_{step}_snapshot.md`

**콘솔 로그 (실패 시):**
- `browser_console_messages` 호출하여 에러 로그 캡처
- 저장: `.sisyphus/evidence/e2e/console_scenario{N}.txt`

**테스트 통과 기준:**
- 모든 필수 스크린샷이 존재
- 각 시나리오의 검증 포인트가 스크린샷/스냅샷으로 확인 가능
- 에러 시나리오(5번)에서 에러 메시지가 화면에 표시됨

**Acceptance Criteria**:
- [ ] `docker-compose exec backend python scripts/generate_test_audio.py` → 테스트 오디오 생성
- [ ] Playwright MCP로 시나리오 1~5 실행 성공
- [ ] 필수 스크린샷 15장 이상 저장 (`.sisyphus/evidence/e2e/`)
- [ ] 모든 검증 포인트가 스크린샷으로 확인 가능

**Commit**: `feat(tests): add E2E test scenarios for Playwright MCP`

---

### Task 16: Golden Test 실행 및 튜닝

**What to do (Phase 1 - Smoke 모드)**:
- 10곡 이상 테스트 데이터 준비 (MP3 + metadata.json, 다양한 장르)
- Golden Test Smoke 모드 전체 실행
- 처리 실패 곡 분석 및 파라미터 튜닝
- 전체 곡 처리 성공 (status=completed) 달성

**추후 구현 (Phase 2 - Full 모드)**:
- Reference MIDI 준비 후 정확도 측정 기능 추가
- 핵심 멜로디 모드 85% 달성까지 튜닝

**Parallelizable**: NO (Task 14, 15 필요)

---

## Golden Test 데이터 정책

> **Phase 1 (현재)**: Smoke 모드 - Reference MIDI 없이 처리 성공 여부만 검증
> **Phase 2 (추후)**: Full 모드 - Reference MIDI 비교로 정확도 측정

### 테스트 데이터 모드

| 모드 | 필요 파일 | 검증 방식 | 현재 상태 |
|------|----------|----------|----------|
| **Smoke** | MP3 + metadata.json | 처리 성공 여부만 확인 | ✅ Phase 1 (현재) |
| **Full** | MP3 + reference.mid + metadata.json | 정량 비교 (85% 기준) | ⏳ Phase 2 (추후) |

### 테스트 데이터 구조 (Phase 1)

```
backend/tests/golden/data/
├── pop_01/                     # 대중가요
│   ├── input.mp3
│   └── metadata.json           # genre: "pop", has_reference: false
├── ost_01/                     # 영화 OST
│   ├── input.mp3
│   └── metadata.json           # genre: "ost"
├── classical_01/               # 클래식
│   ├── input.mp3
│   └── metadata.json           # genre: "classical"
├── children_01/                # 동요
│   ├── input.mp3
│   └── metadata.json           # genre: "children"
└── ...
```

### metadata.json (Phase 1 - Smoke 모드)

```json
{
  "title": "테스트 곡 1",
  "genre": "pop",
  "bpm": 120,
  "key": "C major",
  "duration_seconds": 180,
  "has_reference": false,
  "skip_reason": null
}
```

### 테스트 실행 로직 (Phase 1 - Smoke 모드)

```python
# backend/tests/golden/test_golden.py

def test_golden_song(song_dir: Path):
    """Golden Test 단일 곡 실행 (Smoke 모드)"""
    metadata_path = song_dir / "metadata.json"
    input_path = song_dir / "input.mp3"
    
    # 1. 입력 파일 확인
    if not input_path.exists():
        pytest.skip(f"입력 파일 없음: {input_path}")
    
    # 2. 메타데이터 로드
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("skip_reason"):
            pytest.skip(metadata["skip_reason"])
    else:
        metadata = {"title": song_dir.name, "genre": "unknown"}
    
    # 3. 처리 실행
    result = process_audio(input_path)
    assert result.status == "completed", f"처리 실패: {result.error}"
    
    # 4. Smoke 모드 검증 (Phase 1): 출력 파일 존재 확인
    # Phase 1에서는 모든 곡을 Smoke 모드로 검증
    assert result.melody_mid.exists(), "melody.mid 생성 실패"
    assert result.sheet_easy.exists(), "sheet_easy.musicxml 생성 실패"
    assert result.sheet_medium.exists(), "sheet_medium.musicxml 생성 실패"
    assert result.sheet_hard.exists(), "sheet_hard.musicxml 생성 실패"
    
    # 기본 sanity check
    notes = parse_midi(result.melody_mid)
    assert len(notes) > 0, f"추출된 음표가 없음 (장르: {metadata.get('genre', 'unknown')})"
    assert len(notes) < 10000, "비정상적으로 많은 음표"
    
    # 장르별 메모 (리포트용)
    return {
        "title": metadata.get("title", song_dir.name),
        "genre": metadata.get("genre", "unknown"),
        "note_count": len(notes),
        "passed": True
    }
    
    # --- Phase 2 (추후 구현): Full 모드 정량 비교 ---
    # has_reference = metadata.get("has_reference", False)
    # if has_reference and reference_path.exists():
    #     generated_notes = parse_midi(result.melody_mid)
    #     reference_notes = parse_midi(reference_path)
    #     comparison = evaluate_song(generated_notes, reference_notes, metadata)
    #     assert comparison.passed, f"Core similarity: {comparison.core_similarity:.1f}%"
```

### 테스트 리포트 (Phase 1 - Smoke 모드)

```json
{
  "summary": {
    "total": 10,
    "passed": 9,
    "failed": 1,
    "skipped": 0,
    "genres": {
      "pop": 3,
      "ost": 2,
      "classical": 2,
      "children": 2,
      "jazz": 1
    }
  },
  "results": [
    {
      "song": "pop_01",
      "genre": "pop",
      "passed": true,
      "note_count": 245
    },
    {
      "song": "classical_01",
      "genre": "classical",
      "passed": true,
      "note_count": 512,
      "note": "복잡한 화성, 주요 멜로디 라인 추출"
    }
  ]
}
```

### 합격 기준 (Phase 1 - Smoke 모드)

**Phase 1 프로젝트 전체 합격 기준**:
- **모든 곡**: Smoke 모드로 처리 성공 + 출력 파일 생성
- **장르 다양성**: 최소 4개 장르 이상 (pop, ost, classical, children 등)
- **전체**: 10곡 중 90% 이상 처리 성공 (예: 10곡 중 9곡 이상)

**Phase 2 합격 기준 (추후 구현)**:
- Reference MIDI 준비 후 핵심 멜로디 모드 85% 기준 적용

---

**Acceptance Criteria (Phase 1)**:
- [ ] 테스트 데이터 준비 (10곡 이상, 다양한 장르)
- [ ] 모든 곡 처리 성공 (status=completed)
- [ ] 출력 파일 존재 확인 (melody.mid, sheet_*.musicxml)
- [ ] 장르별 처리 결과 리포트 작성
- [ ] 처리 실패 곡 분석 및 파라미터 튜닝

**Acceptance Criteria (Phase 2 - 추후)**:
- [ ] Reference MIDI 준비 (최소 5곡)
- [ ] Full 모드 곡 중 90% 이상 핵심 멜로디 모드 85% 달성

**Commit**: `feat(tests): tune algorithm parameters for multi-genre support`

---

## Commit Strategy

| Task | Message | Key Files |
|------|---------|-----------|
| 1 | `chore: initialize project structure` | 전체 구조 |
| 2 | `feat(backend): integrate Basic Pitch` | audio_to_midi.py |
| 3 | `feat(backend): implement YouTube extraction` | youtube_downloader.py |
| 4 | `feat(backend): implement melody extraction` | melody_extractor.py |
| 5 | `feat(backend): implement notes_to_musicxml utility` | midi_to_musicxml.py |
| 6 | `feat(backend): implement audio analysis` | audio_analysis.py |
| 7 | `feat(backend): implement difficulty adjustment` | difficulty_adjuster.py |
| 8 | `feat(backend): implement FastAPI with job system` | api/, job_manager.py |
| 9 | `feat(frontend): implement upload UI` | FileUpload.tsx |
| 10 | `feat(frontend): implement sheet rendering` | SheetViewer.tsx |
| 11 | `feat(frontend): implement editing UI` | EditPanel.tsx |
| 12 | `feat(frontend): implement download` | DownloadButtons.tsx |
| 13 | `chore(docker): complete Docker setup` | Dockerfile, compose |
| 14 | `feat(tests): implement Golden Test` | tests/golden/ |
| 15 | `feat(tests): implement E2E tests` | tests/e2e/ |
| 16 | `feat(tests): tune for 85% core melody accuracy` | config, data |

---

## Success Criteria

### Verification Commands

> ⚠️ **Docker-only 정책**: 모든 테스트/스크립트는 Docker 컨테이너 내부에서 실행합니다.
> 호스트에서 직접 `pytest`, `python scripts/...` 실행은 지원하지 않습니다.
> 모든 테스트/스크립트는 `backend/` 하위에 위치합니다 (Docker 빌드 컨텍스트).

```bash
# 전체 시스템 실행
docker-compose up --build

# 백엔드 단위 테스트 (Docker 내부)
docker-compose exec backend pytest tests/unit/

# Golden Test (Docker 내부)
docker-compose exec backend pytest tests/golden/ --html=report.html

# 테스트 오디오 생성 (Docker 내부)
docker-compose exec backend python scripts/generate_test_audio.py

# E2E 테스트 (Playwright MCP 대화형)
# AI 에이전트에게 요청: "E2E 테스트 시나리오 1~5번을 실행해줘"
# 결과: .sisyphus/evidence/e2e/ 디렉토리에 스크린샷 저장

# 수동 전체 플로우
# 1. localhost:3000 접속
# 2. MP3 업로드 또는 YouTube URL 입력
# 3. 처리 완료 대기 (프로그레스 바 확인)
# 4. 악보 렌더링 확인
# 5. BPM/Key/코드 수정
# 6. 난이도 변경
# 7. MIDI/MusicXML 다운로드
```

### Final Checklist
- [ ] 모든 Must Have 기능 구현
- [ ] 모든 Must NOT Have 미구현 확인
- [ ] **다양한 장르 지원** (대중가요, 영화 OST, 클래식, 동요 등)
- [ ] E2E 테스트 통과 (Playwright MCP로 시나리오 1~5 실행, 스크린샷 증거 저장)
- [ ] Golden Test (Phase 1): 10곡 중 9곡 이상 처리 성공 (Smoke 모드)
- [ ] Docker 원클릭 실행
- [ ] README 문서화 완료
