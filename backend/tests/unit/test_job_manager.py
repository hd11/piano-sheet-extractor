"""
Job Manager Unit Tests

Tests for core job management functions:
- create_job() — job creation with unique ID generation
- get_job() — job retrieval and error handling
- update_job_status() — status transitions and progress tracking
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime

from core.job_manager import (
    create_job,
    get_job,
    update_job_status,
    JobStatus,
)


class TestCreateJob:
    """Tests for create_job() function"""

    @patch("core.job_manager.uuid.uuid4")
    @patch("core.job_manager._save_job")
    @patch("core.job_manager._get_job_dir")
    def test_create_job_generates_unique_id(self, mock_get_dir, mock_save, mock_uuid):
        """Test that create_job generates a unique job_id"""
        # Setup
        test_uuid = "test-uuid-1234"
        mock_uuid.return_value = test_uuid
        mock_dir = MagicMock()
        mock_get_dir.return_value = mock_dir

        # Execute
        job_id = create_job("upload", filename="test.mp3")

        # Verify
        assert job_id == test_uuid
        mock_uuid.assert_called_once()
        mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("core.job_manager.uuid.uuid4")
    @patch("core.job_manager._save_job")
    @patch("core.job_manager._get_job_dir")
    def test_create_job_initializes_status_pending(
        self, mock_get_dir, mock_save, mock_uuid
    ):
        """Test that create_job initializes status as PENDING"""
        # Setup
        test_uuid = "test-uuid-1234"
        mock_uuid.return_value = test_uuid
        mock_dir = MagicMock()
        mock_get_dir.return_value = mock_dir

        # Execute
        create_job("upload", filename="test.mp3")

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data["status"] == JobStatus.PENDING
        assert saved_data["progress"] == 0

    @patch("core.job_manager.uuid.uuid4")
    @patch("core.job_manager._save_job")
    @patch("core.job_manager._get_job_dir")
    def test_create_job_stores_source_and_metadata(
        self, mock_get_dir, mock_save, mock_uuid
    ):
        """Test that create_job stores source and metadata"""
        # Setup
        test_uuid = "test-uuid-1234"
        mock_uuid.return_value = test_uuid
        mock_dir = MagicMock()
        mock_get_dir.return_value = mock_dir

        # Execute
        create_job(
            "youtube", url="https://youtube.com/watch?v=abc123", title="Test Video"
        )

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data["source"] == "youtube"
        assert saved_data["metadata"]["url"] == "https://youtube.com/watch?v=abc123"
        assert saved_data["metadata"]["title"] == "Test Video"

    @patch("core.job_manager.uuid.uuid4")
    @patch("core.job_manager._save_job")
    @patch("core.job_manager._get_job_dir")
    def test_create_job_sets_timestamps(self, mock_get_dir, mock_save, mock_uuid):
        """Test that create_job sets created_at and updated_at timestamps"""
        # Setup
        test_uuid = "test-uuid-1234"
        mock_uuid.return_value = test_uuid
        mock_dir = MagicMock()
        mock_get_dir.return_value = mock_dir

        # Execute
        create_job("upload", filename="test.mp3")

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert "created_at" in saved_data
        assert "updated_at" in saved_data
        assert saved_data["created_at"].endswith("Z")
        assert saved_data["updated_at"].endswith("Z")

    @patch("core.job_manager.uuid.uuid4")
    @patch("core.job_manager._save_job")
    @patch("core.job_manager._get_job_dir")
    def test_create_job_initializes_optional_fields(
        self, mock_get_dir, mock_save, mock_uuid
    ):
        """Test that create_job initializes optional fields to None/empty"""
        # Setup
        test_uuid = "test-uuid-1234"
        mock_uuid.return_value = test_uuid
        mock_dir = MagicMock()
        mock_get_dir.return_value = mock_dir

        # Execute
        create_job("upload", filename="test.mp3")

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data["error"] is None
        assert saved_data["analysis"] is None
        assert saved_data["current_stage"] == ""

    @patch("core.job_manager.uuid.uuid4")
    @patch("core.job_manager._save_job")
    @patch("core.job_manager._get_job_dir")
    def test_create_job_multiple_calls_unique_ids(
        self, mock_get_dir, mock_save, mock_uuid
    ):
        """Test that multiple create_job calls generate unique IDs"""
        # Setup
        mock_dir = MagicMock()
        mock_get_dir.return_value = mock_dir
        mock_uuid.side_effect = ["uuid-1", "uuid-2", "uuid-3"]

        # Execute
        id1 = create_job("upload", filename="test1.mp3")
        id2 = create_job("upload", filename="test2.mp3")
        id3 = create_job("youtube", url="https://youtube.com/watch?v=xyz")

        # Verify
        assert id1 == "uuid-1"
        assert id2 == "uuid-2"
        assert id3 == "uuid-3"
        assert id1 != id2 != id3


class TestGetJob:
    """Tests for get_job() function"""

    @patch("core.job_manager._get_job_file")
    def test_get_job_returns_existing_job(self, mock_get_file):
        """Test that get_job returns job data when file exists"""
        # Setup
        job_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PENDING,
            "progress": 0,
        }
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_get_file.return_value = mock_file

        # Mock file reading
        with patch("builtins.open", mock_open(read_data=json.dumps(job_data))):
            # Execute
            result = get_job("test-uuid")

        # Verify
        assert result == job_data
        assert result["job_id"] == "test-uuid"
        assert result["status"] == JobStatus.PENDING

    @patch("core.job_manager._get_job_file")
    def test_get_job_returns_none_when_not_found(self, mock_get_file):
        """Test that get_job returns None when job file doesn't exist"""
        # Setup
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_get_file.return_value = mock_file

        # Execute
        result = get_job("nonexistent-uuid")

        # Verify
        assert result is None
        mock_file.exists.assert_called_once()

    @patch("core.job_manager._get_job_file")
    def test_get_job_parses_json_correctly(self, mock_get_file):
        """Test that get_job correctly parses JSON data"""
        # Setup
        job_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PROCESSING,
            "progress": 50,
            "current_stage": "음성 분석 중",
            "source": "youtube",
            "metadata": {"url": "https://youtube.com/watch?v=abc"},
            "error": None,
            "analysis": None,
        }
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_get_file.return_value = mock_file

        # Mock file reading
        with patch("builtins.open", mock_open(read_data=json.dumps(job_data))):
            # Execute
            result = get_job("test-uuid")

        # Verify
        assert result["job_id"] == "test-uuid"
        assert result["status"] == JobStatus.PROCESSING
        assert result["progress"] == 50
        assert result["current_stage"] == "음성 분석 중"
        assert result["metadata"]["url"] == "https://youtube.com/watch?v=abc"

    @patch("core.job_manager._get_job_file")
    def test_get_job_handles_empty_metadata(self, mock_get_file):
        """Test that get_job handles jobs with empty metadata"""
        # Setup
        job_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PENDING,
            "progress": 0,
            "metadata": {},
        }
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_get_file.return_value = mock_file

        # Mock file reading
        with patch("builtins.open", mock_open(read_data=json.dumps(job_data))):
            # Execute
            result = get_job("test-uuid")

        # Verify
        assert result["metadata"] == {}

    @patch("core.job_manager._get_job_file")
    def test_get_job_handles_completed_job_with_analysis(self, mock_get_file):
        """Test that get_job handles completed jobs with analysis data"""
        # Setup
        job_data = {
            "job_id": "test-uuid",
            "status": JobStatus.COMPLETED,
            "progress": 100,
            "analysis": {
                "bpm": 120,
                "key": "C major",
                "chords": ["C", "F", "G"],
            },
        }
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_get_file.return_value = mock_file

        # Mock file reading
        with patch("builtins.open", mock_open(read_data=json.dumps(job_data))):
            # Execute
            result = get_job("test-uuid")

        # Verify
        assert result["status"] == JobStatus.COMPLETED
        assert result["analysis"]["bpm"] == 120
        assert result["analysis"]["key"] == "C major"


class TestUpdateJobStatus:
    """Tests for update_job_status() function"""

    @patch("core.job_manager._save_job")
    @patch("core.job_manager.get_job")
    def test_update_job_status_changes_status(self, mock_get_job, mock_save):
        """Test that update_job_status changes the job status"""
        # Setup
        original_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PENDING,
            "progress": 0,
            "current_stage": "",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_get_job.return_value = original_data.copy()

        # Execute
        update_job_status("test-uuid", JobStatus.PROCESSING, 25, "음성 분석 중")

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data["status"] == JobStatus.PROCESSING
        assert saved_data["progress"] == 25
        assert saved_data["current_stage"] == "음성 분석 중"

    @patch("core.job_manager._save_job")
    @patch("core.job_manager.get_job")
    def test_update_job_status_updates_timestamp(self, mock_get_job, mock_save):
        """Test that update_job_status updates the updated_at timestamp"""
        # Setup
        original_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PENDING,
            "progress": 0,
            "current_stage": "",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_get_job.return_value = original_data.copy()

        # Execute
        update_job_status("test-uuid", JobStatus.PROCESSING, 50)

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data["updated_at"] != "2024-01-01T00:00:00Z"
        assert saved_data["updated_at"].endswith("Z")

    @patch("core.job_manager._save_job")
    @patch("core.job_manager.get_job")
    def test_update_job_status_handles_nonexistent_job(self, mock_get_job, mock_save):
        """Test that update_job_status handles non-existent jobs gracefully"""
        # Setup
        mock_get_job.return_value = None

        # Execute
        update_job_status("nonexistent-uuid", JobStatus.PROCESSING, 50)

        # Verify
        mock_save.assert_not_called()

    @patch("core.job_manager._save_job")
    @patch("core.job_manager.get_job")
    def test_update_job_status_preserves_other_fields(self, mock_get_job, mock_save):
        """Test that update_job_status preserves other job fields"""
        # Setup
        original_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PENDING,
            "progress": 0,
            "current_stage": "",
            "source": "youtube",
            "metadata": {"url": "https://youtube.com/watch?v=abc"},
            "error": None,
            "analysis": None,
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_get_job.return_value = original_data.copy()

        # Execute
        update_job_status("test-uuid", JobStatus.PROCESSING, 50, "처리 중")

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data["source"] == "youtube"
        assert saved_data["metadata"]["url"] == "https://youtube.com/watch?v=abc"
        assert saved_data["error"] is None
        assert saved_data["analysis"] is None

    @patch("core.job_manager._save_job")
    @patch("core.job_manager.get_job")
    def test_update_job_status_progress_transitions(self, mock_get_job, mock_save):
        """Test that update_job_status handles progress transitions correctly"""
        # Setup
        original_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PENDING,
            "progress": 0,
            "current_stage": "",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_get_job.return_value = original_data.copy()

        # Execute multiple status updates
        update_job_status("test-uuid", JobStatus.PROCESSING, 25)
        update_job_status("test-uuid", JobStatus.GENERATING, 75)
        update_job_status("test-uuid", JobStatus.COMPLETED, 100)

        # Verify
        assert mock_save.call_count == 3

        # Check first call
        first_call = mock_save.call_args_list[0][0][1]
        assert first_call["status"] == JobStatus.PROCESSING
        assert first_call["progress"] == 25

    @patch("core.job_manager._save_job")
    @patch("core.job_manager.get_job")
    def test_update_job_status_with_empty_stage(self, mock_get_job, mock_save):
        """Test that update_job_status handles empty stage parameter"""
        # Setup
        original_data = {
            "job_id": "test-uuid",
            "status": JobStatus.PENDING,
            "progress": 0,
            "current_stage": "이전 단계",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_get_job.return_value = original_data.copy()

        # Execute
        update_job_status("test-uuid", JobStatus.PROCESSING, 50)

        # Verify
        mock_save.assert_called_once()
        saved_data = mock_save.call_args[0][1]
        assert saved_data["current_stage"] == ""


class TestJobStatusConstants:
    """Tests for JobStatus constants"""

    def test_job_status_constants_exist(self):
        """Test that all required JobStatus constants are defined"""
        assert hasattr(JobStatus, "PENDING")
        assert hasattr(JobStatus, "PROCESSING")
        assert hasattr(JobStatus, "GENERATING")
        assert hasattr(JobStatus, "COMPLETED")
        assert hasattr(JobStatus, "FAILED")

    def test_job_status_values(self):
        """Test that JobStatus constants have correct string values"""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.GENERATING == "generating"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
