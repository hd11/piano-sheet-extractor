"""
Unit tests for youtube_downloader module.

Tests YouTube URL validation, metadata retrieval, and audio download functionality.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from core.youtube_downloader import (
    validate_youtube_url,
    get_video_info,
    download_youtube_audio,
    YOUTUBE_URL_REGEX,
    MAX_DURATION_SECONDS,
)


class TestValidateYoutubeUrl:
    """Test suite for validate_youtube_url function."""

    def test_valid_youtube_com_url(self):
        """Test validation of standard youtube.com URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert validate_youtube_url(url) is True

    def test_valid_youtu_be_url(self):
        """Test validation of youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert validate_youtube_url(url) is True

    def test_valid_youtube_url_without_https(self):
        """Test validation of YouTube URL without https."""
        url = "http://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert validate_youtube_url(url) is True

    def test_valid_youtube_url_without_www(self):
        """Test validation of YouTube URL without www."""
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        assert validate_youtube_url(url) is True

    def test_valid_youtube_url_case_insensitive(self):
        """Test that URL validation is case-insensitive."""
        url = "HTTPS://WWW.YOUTUBE.COM/WATCH?V=dQw4w9WgXcQ"
        assert validate_youtube_url(url) is True

    def test_invalid_url_not_youtube(self):
        """Test rejection of non-YouTube URL."""
        url = "https://www.google.com/search?q=test"
        assert validate_youtube_url(url) is False

    def test_invalid_url_empty_string(self):
        """Test rejection of empty string."""
        url = ""
        assert validate_youtube_url(url) is False

    def test_invalid_url_malformed(self):
        """Test rejection of malformed URL."""
        url = "not a url"
        assert validate_youtube_url(url) is False


class TestGetVideoInfo:
    """Test suite for get_video_info function."""

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_get_video_info_success(self, mock_ydl_class):
        """Test successful retrieval of video metadata."""
        # Mock yt_dlp.YoutubeDL
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "title": "Test Video",
            "duration": 300,
            "id": "test_video_id",
        }

        url = "https://www.youtube.com/watch?v=test_video_id"
        result = get_video_info(url)

        assert result["title"] == "Test Video"
        assert result["duration_seconds"] == 300
        assert result["id"] == "test_video_id"

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_get_video_info_duration_limit_exceeded(self, mock_ydl_class):
        """Test rejection of video exceeding 20-minute limit."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        # 25 minutes = 1500 seconds (exceeds 20-minute limit)
        mock_ydl.extract_info.return_value = {
            "title": "Long Video",
            "duration": 1500,
            "id": "long_video_id",
        }

        url = "https://www.youtube.com/watch?v=long_video_id"

        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            get_video_info(url)

    def test_get_video_info_invalid_url(self):
        """Test error handling for invalid URL."""
        url = "https://www.google.com/search?q=test"

        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            get_video_info(url)

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_get_video_info_video_unavailable(self, mock_ydl_class):
        """Test error handling for unavailable video."""
        import yt_dlp

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError(
            "Video unavailable"
        )

        url = "https://www.youtube.com/watch?v=unavailable_video"

        with pytest.raises(ValueError, match="Video unavailable or private"):
            get_video_info(url)

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_get_video_info_duration_exactly_20_minutes(self, mock_ydl_class):
        """Test acceptance of video exactly at 20-minute limit."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        # Exactly 20 minutes = 1200 seconds
        mock_ydl.extract_info.return_value = {
            "title": "Exactly 20 Minutes",
            "duration": 1200,
            "id": "exact_20_min_video",
        }

        url = "https://www.youtube.com/watch?v=exact_20_min_video"
        result = get_video_info(url)

        assert result["duration_seconds"] == 1200
        assert result["title"] == "Exactly 20 Minutes"

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_get_video_info_short_video(self, mock_ydl_class):
        """Test retrieval of short video metadata."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            "title": "Short Video",
            "duration": 30,
            "id": "short_video_id",
        }

        url = "https://www.youtube.com/watch?v=short_video_id"
        result = get_video_info(url)

        assert result["duration_seconds"] == 30


class TestDownloadYoutubeAudio:
    """Test suite for download_youtube_audio function."""

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_download_youtube_audio_success(self, mock_ydl_class):
        """Test successful audio download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)

            # Mock yt_dlp.YoutubeDL
            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl

            # Mock extract_info for get_video_info call
            mock_ydl.extract_info.return_value = {
                "title": "Test Video",
                "duration": 300,
                "id": "test_video_id",
            }

            # Create a dummy MP3 file to simulate download
            def create_mp3(*args, **kwargs):
                (output_path / "test_video_id.mp3").write_text("dummy mp3")

            mock_ydl.download.side_effect = create_mp3

            url = "https://www.youtube.com/watch?v=test_video_id"
            result = download_youtube_audio(url, output_path)

            assert result.exists()
            assert result.suffix == ".mp3"

    def test_download_youtube_audio_invalid_url(self):
        """Test error handling for invalid URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)
            url = "https://www.google.com/search?q=test"

            with pytest.raises(ValueError, match="Invalid YouTube URL"):
                download_youtube_audio(url, output_path)

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_download_youtube_audio_duration_limit_exceeded(self, mock_ydl_class):
        """Test rejection of video exceeding duration limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)

            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            # 25 minutes = 1500 seconds
            mock_ydl.extract_info.return_value = {
                "title": "Long Video",
                "duration": 1500,
                "id": "long_video_id",
            }

            url = "https://www.youtube.com/watch?v=long_video_id"

            with pytest.raises(ValueError, match="exceeds maximum allowed"):
                download_youtube_audio(url, output_path)

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_download_youtube_audio_with_progress_callback(self, mock_ydl_class):
        """Test progress callback is called during download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)

            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl

            # Mock extract_info
            mock_ydl.extract_info.return_value = {
                "title": "Test Video",
                "duration": 300,
                "id": "test_video_id",
            }

            # Create dummy MP3
            def create_mp3(*args, **kwargs):
                (output_path / "test_video_id.mp3").write_text("dummy mp3")

            mock_ydl.download.side_effect = create_mp3

            # Track progress callback calls
            progress_values = []

            def progress_callback(progress):
                progress_values.append(progress)

            url = "https://www.youtube.com/watch?v=test_video_id"
            result = download_youtube_audio(url, output_path, progress_callback)

            # Verify callback was called with final progress (0.2 = 20%)
            assert 0.2 in progress_values
            assert result.exists()

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_download_youtube_audio_creates_output_directory(self, mock_ydl_class):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "path"

            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl

            mock_ydl.extract_info.return_value = {
                "title": "Test Video",
                "duration": 300,
                "id": "test_video_id",
            }

            def create_mp3(*args, **kwargs):
                (output_path / "test_video_id.mp3").write_text("dummy mp3")

            mock_ydl.download.side_effect = create_mp3

            url = "https://www.youtube.com/watch?v=test_video_id"
            result = download_youtube_audio(url, output_path)

            # Verify nested directory was created
            assert output_path.exists()
            assert result.exists()

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_download_youtube_audio_video_unavailable(self, mock_ydl_class):
        """Test error handling for unavailable video."""
        import yt_dlp

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)

            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl
            mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError(
                "Video unavailable"
            )

            url = "https://www.youtube.com/watch?v=unavailable_video"

            with pytest.raises(ValueError, match="Video unavailable or private"):
                download_youtube_audio(url, output_path)

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_download_youtube_audio_no_mp3_found(self, mock_ydl_class):
        """Test error handling when MP3 file is not created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)

            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl

            mock_ydl.extract_info.return_value = {
                "title": "Test Video",
                "duration": 300,
                "id": "test_video_id",
            }

            # Don't create any MP3 file
            mock_ydl.download.return_value = None

            url = "https://www.youtube.com/watch?v=test_video_id"

            with pytest.raises(FileNotFoundError, match="MP3 file not found"):
                download_youtube_audio(url, output_path)

    @patch("core.youtube_downloader.yt_dlp.YoutubeDL")
    def test_download_youtube_audio_progress_mapping(self, mock_ydl_class):
        """Test that progress is correctly mapped to 0-20% range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir)

            mock_ydl = MagicMock()
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl

            mock_ydl.extract_info.return_value = {
                "title": "Test Video",
                "duration": 300,
                "id": "test_video_id",
            }

            def create_mp3(*args, **kwargs):
                (output_path / "test_video_id.mp3").write_text("dummy mp3")

            mock_ydl.download.side_effect = create_mp3

            progress_values = []

            def progress_callback(progress):
                progress_values.append(progress)

            url = "https://www.youtube.com/watch?v=test_video_id"
            download_youtube_audio(url, output_path, progress_callback)

            # Verify final progress is 0.2 (20% of total pipeline)
            assert progress_values[-1] == 0.2
            # Verify all progress values are within 0-0.2 range
            assert all(0 <= p <= 0.2 for p in progress_values)
