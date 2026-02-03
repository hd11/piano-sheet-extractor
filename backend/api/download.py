"""
Download endpoint for retrieving generated files.

GET /api/download/{job_id}/{format} - Download MIDI or MusicXML files.
"""

from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from core.job_manager import JOB_STORAGE_PATH, get_job

router = APIRouter(prefix="/api", tags=["download"])


class DownloadFormat(str, Enum):
    """Supported download formats."""

    MIDI = "midi"
    MUSICXML = "musicxml"


class Difficulty(str, Enum):
    """Available difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@router.get("/download/{job_id}/{format}")
async def download_file(
    job_id: str,
    format: DownloadFormat,
    difficulty: Difficulty = Query(default=Difficulty.MEDIUM),
):
    """
    Download generated MIDI or MusicXML file.

    Args:
        job_id: Unique job identifier
        format: File format ("midi" or "musicxml")
        difficulty: Difficulty level for MusicXML (default: "medium")

    Returns:
        FileResponse with the requested file

    Raises:
        HTTPException 404: Job not found or file not found
    """
    # Check if job exists
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Job not found",
                "code": "JOB_NOT_FOUND",
                "message": "요청한 작업을 찾을 수 없습니다.",
                "details": {"job_id": job_id},
            },
        )

    job_dir = JOB_STORAGE_PATH / job_id

    if format == DownloadFormat.MIDI:
        file_path = job_dir / "melody.mid"
        media_type = "audio/midi"
        filename = f"{job_id}.mid"
    else:  # musicxml
        file_path = job_dir / f"sheet_{difficulty.value}.musicxml"
        media_type = "application/vnd.recordare.musicxml+xml"
        filename = f"{job_id}_{difficulty.value}.musicxml"

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "error": "File not found",
                "code": "FILE_NOT_FOUND",
                "message": "요청한 파일을 찾을 수 없습니다. 처리가 완료되지 않았을 수 있습니다.",
                "details": {
                    "format": format.value,
                    "difficulty": difficulty.value
                    if format == DownloadFormat.MUSICXML
                    else None,
                },
            },
        )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )
