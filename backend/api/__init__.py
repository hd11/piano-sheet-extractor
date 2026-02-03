"""API endpoints package for piano sheet extraction service."""

from api.upload import router as upload_router
from api.youtube import router as youtube_router
from api.status import router as status_router
from api.result import router as result_router
from api.download import router as download_router

__all__ = [
    "upload_router",
    "youtube_router",
    "status_router",
    "result_router",
    "download_router",
]
