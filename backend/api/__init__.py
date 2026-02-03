"""API endpoints package for piano sheet extraction service."""

from backend.api.upload import router as upload_router
from backend.api.youtube import router as youtube_router
from backend.api.status import router as status_router
from backend.api.result import router as result_router
from backend.api.download import router as download_router

__all__ = [
    "upload_router",
    "youtube_router",
    "status_router",
    "result_router",
    "download_router",
]
