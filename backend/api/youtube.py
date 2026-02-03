"""
YouTube endpoint for processing YouTube video URLs.

POST /api/youtube - Submit a YouTube URL for audio extraction and processing.
"""

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.job_manager import create_job, process_job_async
from backend.core.youtube_downloader import (
    MAX_DURATION_SECONDS,
    get_video_info,
    validate_youtube_url,
)

router = APIRouter(prefix="/api", tags=["youtube"])


class YouTubeRequest(BaseModel):
    """Request body for YouTube URL submission."""

    url: str


@router.post("/youtube")
async def process_youtube(request: YouTubeRequest):
    """
    Submit a YouTube URL for piano sheet extraction.

    Args:
        request: YouTubeRequest with URL

    Returns:
        Job creation response with job_id, video_title, and duration

    Raises:
        HTTPException 400: Invalid YouTube URL or video too long
        HTTPException 403: Video is private or age-restricted
    """
    # Validate URL format
    if not validate_youtube_url(request.url):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid YouTube URL",
                "code": "INVALID_YOUTUBE_URL",
                "message": "올바른 YouTube URL을 입력해주세요.",
                "details": None,
            },
        )

    # Get video info and validate duration
    try:
        video_info = get_video_info(request.url)
    except ValueError as e:
        error_message = str(e)

        # Check if it's a duration error
        if (
            "exceeds maximum" in error_message.lower()
            or "duration" in error_message.lower()
        ):
            # Extract actual duration from error message if possible
            actual_duration_minutes = None
            try:
                # Try to parse duration from error message
                import re

                match = re.search(r"\((\d+)s\)", error_message)
                if match:
                    actual_seconds = int(match.group(1))
                    actual_duration_minutes = round(actual_seconds / 60, 1)
            except Exception:
                pass

            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Video too long",
                    "code": "VIDEO_TOO_LONG",
                    "message": "영상이 너무 깁니다. 최대 20분까지 지원합니다.",
                    "details": {
                        "max_duration_minutes": MAX_DURATION_SECONDS // 60,
                        "actual_duration_minutes": actual_duration_minutes,
                    },
                },
            )

        # Check if video is unavailable or private
        if "unavailable" in error_message.lower() or "private" in error_message.lower():
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Video is private or age-restricted",
                    "code": "VIDEO_UNAVAILABLE",
                    "message": "이 영상은 비공개이거나 연령 제한이 있어 다운로드할 수 없습니다.",
                    "details": None,
                },
            )

        # Generic error
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid YouTube URL",
                "code": "INVALID_YOUTUBE_URL",
                "message": "올바른 YouTube URL을 입력해주세요.",
                "details": {"reason": error_message},
            },
        )

    # Create job with YouTube metadata
    job_id = create_job(
        source="youtube",
        url=request.url,
        video_title=video_info["title"],
        duration_seconds=video_info["duration_seconds"],
    )

    # Start background processing
    asyncio.create_task(process_job_async(job_id))

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job created successfully",
        "video_title": video_info["title"],
        "duration_seconds": video_info["duration_seconds"],
    }
