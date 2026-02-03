"""
Job Management System

This module provides job creation, state management, and processing
for the piano sheet extraction pipeline.

Features:
- Job state enum: PENDING, PROCESSING, GENERATING, COMPLETED, FAILED
- Job data structure and storage
- Background processing with asyncio
- Regeneration with cancellation support
"""

import asyncio
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pretty_midi

from backend.core.progress import calculate_progress

logger = logging.getLogger(__name__)

# =============================================================================
# Constants and Configuration
# =============================================================================

# Job storage path (can be overridden by environment variable)
JOB_STORAGE_PATH = Path(os.environ.get("JOB_STORAGE_PATH", "/tmp/piano-sheet-jobs"))

# Job timeout in seconds (default: 5 minutes)
JOB_TIMEOUT_SECONDS = int(os.environ.get("JOB_TIMEOUT_SECONDS", "300"))

# Maximum concurrent jobs
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "3"))

# Thread pool for synchronous processing
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)

# =============================================================================
# Job State Enum
# =============================================================================


class JobStatus:
    """Job status constants"""

    PENDING = "pending"
    PROCESSING = "processing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Regeneration State (Module-level globals)
# =============================================================================

# job_id -> current regeneration task
_regeneration_tasks: Dict[str, asyncio.Task] = {}

# job_id -> cancellation flag
_cancellation_flags: Dict[str, bool] = {}


# =============================================================================
# Job Data Management
# =============================================================================


def _get_job_dir(job_id: str) -> Path:
    """Get the directory path for a job."""
    return JOB_STORAGE_PATH / job_id


def _get_job_file(job_id: str) -> Path:
    """Get the job metadata file path."""
    return _get_job_dir(job_id) / "job.json"


def create_job(source: str, **kwargs: Any) -> str:
    """
    Create a new job and return its ID.

    Args:
        source: Job source type ("upload" or "youtube")
        **kwargs: Additional metadata (e.g., url for YouTube, filename for upload)

    Returns:
        job_id: Unique job identifier (UUID)

    Job data structure:
        {
            "job_id": str,
            "status": str,  # PENDING, PROCESSING, GENERATING, COMPLETED, FAILED
            "progress": int,  # 0-100
            "current_stage": str,
            "source": str,  # "upload" or "youtube"
            "created_at": str,  # ISO 8601
            "updated_at": str,
            "error": Optional[dict],  # {"error": str, "code": str, "message": str}
            "analysis": Optional[dict],  # BPM, key, chords
            "metadata": dict,  # source-specific (e.g., video_title for YouTube)
        }
    """
    job_id = str(uuid.uuid4())
    job_dir = _get_job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow().isoformat() + "Z"

    job_data = {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "progress": 0,
        "current_stage": "",
        "source": source,
        "created_at": now,
        "updated_at": now,
        "error": None,
        "analysis": None,
        "metadata": kwargs,
    }

    _save_job(job_id, job_data)
    logger.info(f"Created job {job_id} with source={source}")

    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get job data by ID.

    Args:
        job_id: Job identifier

    Returns:
        Job data dictionary or None if not found
    """
    job_file = _get_job_file(job_id)
    if not job_file.exists():
        return None

    with open(job_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_job(job_id: str, job_data: Dict[str, Any]) -> None:
    """Save job data to file (internal)."""
    job_file = _get_job_file(job_id)
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, ensure_ascii=False, indent=2)


def update_job_status(job_id: str, status: str, progress: int, stage: str = "") -> None:
    """
    Update job status, progress, and current stage.

    Args:
        job_id: Job identifier
        status: New status (from JobStatus constants)
        progress: Progress percentage (0-100)
        stage: Current stage description (Korean for UI)
    """
    job_data = get_job(job_id)
    if job_data is None:
        logger.warning(f"Cannot update status for non-existent job: {job_id}")
        return

    job_data["status"] = status
    job_data["progress"] = progress
    job_data["current_stage"] = stage
    job_data["updated_at"] = datetime.utcnow().isoformat() + "Z"

    _save_job(job_id, job_data)
    logger.debug(f"Job {job_id}: status={status}, progress={progress}, stage={stage}")


def update_job_analysis(job_id: str, analysis: Dict[str, Any]) -> None:
    """
    Update job with analysis results.

    Args:
        job_id: Job identifier
        analysis: Analysis results (bpm, key, chords, etc.)
    """
    job_data = get_job(job_id)
    if job_data is None:
        logger.warning(f"Cannot update analysis for non-existent job: {job_id}")
        return

    job_data["analysis"] = analysis
    job_data["updated_at"] = datetime.utcnow().isoformat() + "Z"

    _save_job(job_id, job_data)
    logger.info(f"Job {job_id}: analysis updated (bpm={analysis.get('bpm')})")


def update_job_error(job_id: str, error: str, code: str, message: str) -> None:
    """
    Update job with error information.

    Args:
        job_id: Job identifier
        error: Error type/name
        code: Error code
        message: User-facing error message
    """
    job_data = get_job(job_id)
    if job_data is None:
        logger.warning(f"Cannot update error for non-existent job: {job_id}")
        return

    job_data["status"] = JobStatus.FAILED
    job_data["error"] = {"error": error, "code": code, "message": message}
    job_data["updated_at"] = datetime.utcnow().isoformat() + "Z"

    _save_job(job_id, job_data)
    logger.error(f"Job {job_id} failed: {error} - {message}")


# =============================================================================
# Note to MIDI Conversion
# =============================================================================


def save_notes_as_midi(notes: List, output_path: Path, bpm: float = 120.0) -> None:
    """
    Save Note list as MIDI file using pretty_midi.

    Args:
        notes: List of Note objects (from midi_parser)
        output_path: Path to save MIDI file
        bpm: Tempo in BPM (default: 120)
    """
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    piano = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano

    for note in notes:
        pm_note = pretty_midi.Note(
            velocity=note.velocity,
            pitch=note.pitch,
            start=note.onset,
            end=note.onset + note.duration,
        )
        piano.notes.append(pm_note)

    pm.instruments.append(piano)
    pm.write(str(output_path))
    logger.debug(f"Saved {len(notes)} notes to {output_path}")


# =============================================================================
# Background Processing
# =============================================================================


async def process_job_async(job_id: str) -> None:
    """
    Start job processing in background.

    This wraps the synchronous processing in a ThreadPoolExecutor
    to avoid blocking the event loop.

    Args:
        job_id: Job identifier
    """
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(_executor, _process_job_sync, job_id),
            timeout=JOB_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        update_job_error(
            job_id,
            error="ProcessingTimeout",
            code="PROCESSING_TIMEOUT",
            message=f"처리 시간이 {JOB_TIMEOUT_SECONDS}초를 초과했습니다.",
        )
    except Exception as e:
        logger.exception(f"Job {job_id} processing failed: {e}")
        update_job_error(
            job_id,
            error="ProcessingError",
            code="PROCESSING_ERROR",
            message=f"처리 중 오류가 발생했습니다: {str(e)}",
        )


def _process_job_sync(job_id: str) -> None:
    """
    Synchronous job processing (runs in ThreadPoolExecutor).

    Processing pipeline:
    1. YouTube download (if source=youtube): 0-20%
    2. Audio → MIDI (Basic Pitch): 20-50%
    3. Melody extraction (Skyline): 50-60%
    4. Analysis (BPM/Key/Chords): 60-70%
    5. Sheet generation (MusicXML): 70-100%
    """
    job_dir = _get_job_dir(job_id)
    job = get_job(job_id)

    if job is None:
        logger.error(f"Job {job_id} not found during processing")
        return

    try:
        # Stage 1: YouTube download (if source=youtube)
        if job["source"] == "youtube":
            update_job_status(job_id, JobStatus.PROCESSING, 0, "YouTube 다운로드 중")
            from backend.core.youtube_downloader import download_youtube_audio

            audio_path = download_youtube_audio(
                job["metadata"]["url"],
                job_dir,
                progress_callback=lambda p: update_job_status(
                    job_id,
                    JobStatus.PROCESSING,
                    calculate_progress("youtube_download", p / 0.2),  # p is 0-0.2
                    "YouTube 다운로드 중",
                ),
            )
        else:
            # For upload, audio file should already be at input.mp3
            audio_path = job_dir / "input.mp3"
            if not audio_path.exists():
                raise FileNotFoundError(f"Input audio file not found: {audio_path}")

        # Stage 2: Audio → MIDI (Basic Pitch)
        update_job_status(job_id, JobStatus.PROCESSING, 20, "Basic Pitch 변환 중")
        from backend.core.audio_to_midi import convert_audio_to_midi

        midi_result = convert_audio_to_midi(audio_path, job_dir / "full.mid")
        update_job_status(job_id, JobStatus.PROCESSING, 50, "Basic Pitch 완료")

        # Stage 3: Melody extraction (Skyline)
        update_job_status(job_id, JobStatus.PROCESSING, 50, "멜로디 추출 중")
        from backend.core.melody_extractor import extract_melody

        melody_notes = extract_melody(job_dir / "full.mid")

        # Save melody.mid
        melody_path = job_dir / "melody.mid"
        # Get BPM from analysis or use default for melody MIDI
        # We'll use a temporary default and update after analysis
        save_notes_as_midi(melody_notes, melody_path, bpm=120.0)
        update_job_status(job_id, JobStatus.PROCESSING, 60, "멜로디 추출 완료")

        # Stage 4: Analysis (BPM/Key/Chords)
        update_job_status(job_id, JobStatus.PROCESSING, 60, "음악 분석 중")
        from backend.core.audio_analysis import analyze_audio

        analysis = analyze_audio(audio_path)

        # Update melody.mid with correct BPM if significantly different
        actual_bpm = analysis.get("bpm", 120.0)
        if abs(actual_bpm - 120.0) > 1.0:
            save_notes_as_midi(melody_notes, melody_path, bpm=actual_bpm)

        update_job_analysis(job_id, analysis)
        update_job_status(job_id, JobStatus.PROCESSING, 70, "음악 분석 완료")

        # Stage 5: Sheet generation (MusicXML)
        update_job_status(job_id, JobStatus.GENERATING, 70, "악보 생성 중")
        from backend.core.difficulty_adjuster import generate_all_sheets

        sheets = generate_all_sheets(job_dir, melody_path, analysis)
        logger.info(f"Generated sheets: {list(sheets.keys())}")

        # Complete
        update_job_status(job_id, JobStatus.COMPLETED, 100, "완료")
        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        update_job_error(
            job_id,
            error=type(e).__name__,
            code="PROCESSING_ERROR",
            message=str(e),
        )


# =============================================================================
# Regeneration with Cancellation Support
# =============================================================================


async def regenerate_sheets_async(job_id: str, analysis: Dict[str, Any]) -> None:
    """
    Regenerate MusicXML with cancellation support.

    This function runs sheet regeneration in a ThreadPoolExecutor
    with checkpoint-based cancellation.

    Args:
        job_id: Job identifier
        analysis: Updated analysis results (bpm, key, chords)
    """
    _cancellation_flags[job_id] = False

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _executor,
            _regenerate_sheets_sync,
            job_id,
            analysis,
        )
    finally:
        _cancellation_flags.pop(job_id, None)
        _regeneration_tasks.pop(job_id, None)


def _regenerate_sheets_sync(job_id: str, analysis: Dict[str, Any]) -> None:
    """
    Sync regeneration with checkpoint cancellation.

    Checkpoints:
    1. Before each difficulty processing
    2. Before file save

    Args:
        job_id: Job identifier
        analysis: Updated analysis results
    """
    job_dir = _get_job_dir(job_id)
    melody_path = job_dir / "melody.mid"

    if not melody_path.exists():
        logger.error(f"Melody MIDI not found for job {job_id}")
        update_job_error(
            job_id,
            error="FileNotFound",
            code="MELODY_NOT_FOUND",
            message="멜로디 MIDI 파일을 찾을 수 없습니다.",
        )
        return

    from backend.core.difficulty_adjuster import (
        add_chord_symbols,
        adjust_difficulty,
        write_file_atomic,
    )
    from backend.core.midi_parser import parse_midi
    from backend.core.midi_to_musicxml import notes_to_stream, stream_to_musicxml

    # Load melody notes
    notes = parse_midi(melody_path)
    bpm = analysis.get("bpm", 120.0)
    key = analysis.get("key", "C major")
    chords = analysis.get("chords", [])

    progress_base = 70
    progress_per_level = 10  # 3 levels * 10 = 30 (70 to 100)

    for i, difficulty in enumerate(["easy", "medium", "hard"]):
        # Checkpoint 1: Before each difficulty processing
        if _cancellation_flags.get(job_id, False):
            logger.info(f"Regeneration cancelled for job {job_id} at {difficulty}")
            return

        current_progress = progress_base + (i * progress_per_level)
        update_job_status(
            job_id,
            JobStatus.GENERATING,
            current_progress,
            f"MusicXML 재생성 중 ({difficulty})",
        )

        # Adjust difficulty
        adjusted_notes = adjust_difficulty(notes, difficulty, bpm)

        # Create music21 Stream
        stream = notes_to_stream(adjusted_notes, bpm, key)

        # Add chord symbols
        add_chord_symbols(stream, chords, bpm)

        # Convert to MusicXML
        musicxml_str = stream_to_musicxml(stream)

        # Checkpoint 2: Before file save
        if _cancellation_flags.get(job_id, False):
            logger.info(
                f"Regeneration cancelled for job {job_id} before saving {difficulty}"
            )
            return

        # Atomic file replace
        output_path = job_dir / f"sheet_{difficulty}.musicxml"
        write_file_atomic(output_path, musicxml_str)
        logger.debug(f"Regenerated {difficulty} sheet for job {job_id}")

    # Update analysis in job data
    update_job_analysis(job_id, analysis)

    # Complete
    update_job_status(job_id, JobStatus.COMPLETED, 100, "완료")
    logger.info(f"Regeneration completed for job {job_id}")


async def handle_put_regeneration(job_id: str, new_analysis: Dict[str, Any]) -> None:
    """
    Handle PUT request - cancel existing regeneration and start new.

    This implements the "last-write-wins" policy for analysis updates.

    Args:
        job_id: Job identifier
        new_analysis: New analysis data from PUT request
    """
    # 1. Cancel existing task if running
    if job_id in _regeneration_tasks:
        _cancellation_flags[job_id] = True
        # Wait for checkpoint (max 100ms)
        await asyncio.sleep(0.1)
        logger.info(f"Cancelled existing regeneration for job {job_id}")

    # 2. Update status
    update_job_status(job_id, JobStatus.GENERATING, 70, "MusicXML 재생성 중")

    # 3. Start new regeneration task
    task = asyncio.create_task(regenerate_sheets_async(job_id, new_analysis))
    _regeneration_tasks[job_id] = task
    logger.info(f"Started new regeneration for job {job_id}")


# =============================================================================
# Cleanup and Utilities
# =============================================================================


def cleanup_job(job_id: str) -> bool:
    """
    Clean up job directory and data.

    Args:
        job_id: Job identifier

    Returns:
        True if cleanup succeeded, False otherwise
    """
    import shutil

    job_dir = _get_job_dir(job_id)
    if not job_dir.exists():
        return False

    try:
        shutil.rmtree(job_dir)
        logger.info(f"Cleaned up job {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup job {job_id}: {e}")
        return False


def list_jobs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all jobs, optionally filtered by status.

    Args:
        status: Filter by status (optional)

    Returns:
        List of job data dictionaries
    """
    jobs = []

    if not JOB_STORAGE_PATH.exists():
        return jobs

    for job_dir in JOB_STORAGE_PATH.iterdir():
        if not job_dir.is_dir():
            continue

        job_file = job_dir / "job.json"
        if not job_file.exists():
            continue

        try:
            with open(job_file, "r", encoding="utf-8") as f:
                job_data = json.load(f)

            if status is None or job_data.get("status") == status:
                jobs.append(job_data)
        except Exception as e:
            logger.warning(f"Failed to load job from {job_dir}: {e}")

    # Sort by created_at descending
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jobs
