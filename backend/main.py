"""FastAPI backend for Piano Sheet Extractor"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    upload_router,
    youtube_router,
    status_router,
    result_router,
    download_router,
)

app = FastAPI(
    title="Piano Sheet Extractor API",
    description="Extract piano sheet music from audio files",
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(upload_router)
app.include_router(youtube_router)
app.include_router(status_router)
app.include_router(result_router)
app.include_router(download_router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Piano Sheet Extractor API"}


@app.get("/docs")
async def docs():
    """Swagger UI documentation"""
    return {"message": "Swagger UI available at /docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
