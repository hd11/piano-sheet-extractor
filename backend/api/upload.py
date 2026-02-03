"""
Upload endpoint for MP3 file uploads.

POST /api/upload - Upload an MP3 file for processing.
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from core.job_manager import (
    JOB_STORAGE_PATH,
    create_job,
    process_job_async,
)

router = APIRouter(prefix="/api", tags=["upload"])

# Maximum file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# Allowed content types
ALLOWED_CONTENT_TYPES = ["audio/mpeg", "audio/mp3"]


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload an MP3 file for piano sheet extraction.

    Args:
        file: MP3 file (max 50MB)

    Returns:
        Job creation response with job_id

    Raises:
        HTTPException 413: File too large
        HTTPException 415: Unsupported file type
    """
    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "Unsupported file type",
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": "MP3 파일만 업로드 가능합니다.",
                "details": {"allowed": ALLOWED_CONTENT_TYPES},
            },
        )

    # Read file content and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "File too large",
                "code": "FILE_TOO_LARGE",
                "message": "업로드가 중단되었습니다. 50MB 이하 파일만 업로드 가능합니다.",
                "details": {"max_size_mb": 50},
            },
        )

    # Create job
    job_id = create_job(source="upload", filename=file.filename)

    # Save file to job directory
    job_dir = JOB_STORAGE_PATH / job_id
    input_path = job_dir / "input.mp3"
    input_path.write_bytes(content)

    # Start background processing
    asyncio.create_task(process_job_async(job_id))

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job created successfully",
    }
