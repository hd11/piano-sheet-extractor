"""
Result endpoint for retrieving and updating analysis results.

GET /api/result/{job_id} - Get analysis results for a completed job.
PUT /api/result/{job_id} - Update analysis and trigger sheet regeneration.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.job_manager import (
    JobStatus,
    get_job,
    handle_put_regeneration,
)

router = APIRouter(prefix="/api", tags=["result"])


class ChordInfo(BaseModel):
    """Chord information."""

    time: float
    duration: float
    chord: str
    confidence: Optional[float] = None


class UpdateAnalysisRequest(BaseModel):
    """Request body for analysis update."""

    bpm: Optional[float] = None
    key: Optional[str] = None
    chords: Optional[List[Dict]] = None


@router.get("/result/{job_id}")
async def get_result(job_id: str):
    """
    Get analysis results for a job.

    Args:
        job_id: Unique job identifier

    Returns:
        Analysis results if job is completed, or error if job failed

    Raises:
        HTTPException 404: Job not found
    """
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

    # Handle failed job
    if job["status"] == JobStatus.FAILED:
        return {
            "job_id": job_id,
            "status": "failed",
            "error": job.get(
                "error",
                {
                    "error": "Processing failed",
                    "code": "PROCESSING_FAILED",
                    "message": "처리 중 오류가 발생했습니다.",
                    "details": None,
                },
            ),
        }

    # Handle completed job
    if job["status"] == JobStatus.COMPLETED:
        return {
            "job_id": job_id,
            "status": "completed",
            "analysis": job.get("analysis", {}),
            "available_difficulties": ["easy", "medium", "hard"],
            "musicxml_url": f"/api/download/{job_id}/musicxml?difficulty=medium",
            "midi_url": f"/api/download/{job_id}/midi",
        }

    # Handle jobs still processing or generating
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "current_stage": job["current_stage"],
    }


@router.put("/result/{job_id}")
async def update_result(job_id: str, request: UpdateAnalysisRequest):
    """
    Update analysis and trigger sheet regeneration.

    This endpoint allows users to modify the BPM, key, or chord progression.
    When updated, the MusicXML sheets will be regenerated with the new values.

    Args:
        job_id: Unique job identifier
        request: UpdateAnalysisRequest with optional bpm, key, chords

    Returns:
        Confirmation that regeneration has started

    Raises:
        HTTPException 400: Job is not in completed state
        HTTPException 404: Job not found
    """
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

    # Check if job is in completed state
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Job is not in completed state",
                "code": "JOB_NOT_COMPLETED",
                "message": "작업이 아직 완료되지 않았습니다. 완료 후 수정 가능합니다.",
                "details": {"current_status": job["status"]},
            },
        )

    # Merge request data with existing analysis
    current_analysis = job.get("analysis", {})
    new_analysis = current_analysis.copy()

    if request.bpm is not None:
        new_analysis["bpm"] = request.bpm
    if request.key is not None:
        new_analysis["key"] = request.key
    if request.chords is not None:
        new_analysis["chords"] = request.chords

    # Start regeneration
    await handle_put_regeneration(job_id, new_analysis)

    return {
        "message": "Analysis updated successfully",
        "regenerating": True,
        "job_id": job_id,
    }
