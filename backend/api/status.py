"""
Status endpoint for checking job processing status.

GET /api/status/{job_id} - Get current job status and progress.
"""

from fastapi import APIRouter, HTTPException

from backend.core.job_manager import get_job

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """
    Get current status of a job.

    Args:
        job_id: Unique job identifier

    Returns:
        Job status with progress and timestamps

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

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "current_stage": job["current_stage"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }
