"""
YouTube audio extraction using yt-dlp.

This module provides functionality to download audio from YouTube videos
and convert them to MP3 format.
"""

import logging
import re
from pathlib import Path
from typing import Callable, Dict, Any, Optional

import yt_dlp

logger = logging.getLogger(__name__)

# YouTube URL regex pattern
YOUTUBE_URL_REGEX = r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$"

# Maximum video duration: 20 minutes
MAX_DURATION_SECONDS = 20 * 60


def validate_youtube_url(url: str) -> bool:
    """
    Validate if the provided URL is a valid YouTube URL.

    Args:
        url: URL string to validate

    Returns:
        True if URL matches YouTube pattern, False otherwise
    """
    return bool(re.match(YOUTUBE_URL_REGEX, url, re.IGNORECASE))


def get_video_info(url: str) -> Dict[str, Any]:
    """
    Get video metadata from YouTube URL without downloading.

    This function extracts metadata (title, duration, video ID) from a YouTube URL
    without downloading the video. It also validates that the video duration does
    not exceed the 20-minute limit.

    Args:
        url: YouTube URL

    Returns:
        Dictionary with keys:
            - title: Video title
            - duration_seconds: Duration in seconds
            - id: YouTube video ID

    Raises:
        ValueError: If URL is invalid, video is unavailable, or duration exceeds limit
    """
    # Validate URL format
    if not validate_youtube_url(url):
        raise ValueError(f"Invalid YouTube URL: {url}")

    logger.info(f"Fetching video info for: {url}")

    try:
        # Extract info without downloading
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Check duration
        duration = info.get("duration", 0)
        if duration > MAX_DURATION_SECONDS:
            raise ValueError(
                f"Video duration ({duration}s) exceeds maximum allowed "
                f"({MAX_DURATION_SECONDS}s / 20 minutes)"
            )

        video_info = {
            "title": info.get("title", "Unknown"),
            "duration_seconds": duration,
            "id": info.get("id", "unknown"),
        }

        logger.info(
            f"Video info retrieved: {video_info['title']} "
            f"({video_info['duration_seconds']}s)"
        )

        return video_info

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Video unavailable or private: {e}")
        raise ValueError(f"Video unavailable or private: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching video info: {e}")
        raise ValueError(f"Error fetching video info: {str(e)}")


def download_youtube_audio(
    url: str,
    output_path: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Path:
    """
    Download audio from YouTube URL and convert to MP3.

    This function downloads the best available audio from a YouTube video
    and converts it to MP3 format. The video duration is checked before
    downloading to ensure it doesn't exceed the 20-minute limit.

    Args:
        url: YouTube URL
        output_path: Directory where MP3 file will be saved
        progress_callback: Optional callback function to report progress (0.0-1.0).
                          Progress is mapped to 0-20% of total pipeline.

    Returns:
        Path to the downloaded MP3 file

    Raises:
        ValueError: If URL is invalid, video is unavailable, or duration exceeds limit
        FileNotFoundError: If output directory cannot be created
    """
    output_path = Path(output_path)

    # Validate URL
    if not validate_youtube_url(url):
        raise ValueError(f"Invalid YouTube URL: {url}")

    # Check video info and duration before downloading
    try:
        video_info = get_video_info(url)
    except ValueError as e:
        logger.error(f"Cannot download video: {e}")
        raise

    # Create output directory
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create output directory: {e}")
        raise FileNotFoundError(f"Cannot create output directory: {output_path}")

    logger.info(f"Starting download: {video_info['title']}")

    def progress_hook(d: Dict[str, Any]) -> None:
        """
        Progress hook for yt-dlp.

        Converts yt-dlp progress (0-100%) to job progress (0-20%).
        """
        if progress_callback is None:
            return

        if d["status"] == "downloading":
            # yt-dlp reports progress as percentage (0-100)
            # Map to 0-20% for YouTube download phase
            yt_dlp_progress = d.get("_percent_str", "0%").strip().rstrip("%")
            try:
                yt_dlp_percent = float(yt_dlp_progress)
                # Convert to 0.0-1.0 range and map to 0-20% of total pipeline
                job_progress = (yt_dlp_percent / 100.0) * 0.2
                progress_callback(job_progress)
            except (ValueError, AttributeError):
                pass

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "progress_hooks": [progress_hook],
            "outtmpl": str(output_path / "%(id)s.%(ext)s"),
            "quiet": False,
            "no_warnings": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the downloaded MP3 file
        mp3_files = list(output_path.glob("*.mp3"))
        if not mp3_files:
            raise FileNotFoundError("MP3 file not found after download")

        mp3_path = mp3_files[0]
        logger.info(f"Audio downloaded successfully: {mp3_path}")

        # Call progress callback with 100% completion
        if progress_callback:
            progress_callback(0.2)  # 20% of total pipeline

        return mp3_path

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
        raise ValueError(f"Failed to download video: {str(e)}")
    except Exception as e:
        logger.error(f"Error during audio download: {e}")
        raise
