import pytest
from pathlib import Path
import sys

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "golden: Golden Test (smoke mode)")
    config.addinivalue_line(
        "markers", "smoke: Smoke test - checks processing success only"
    )


@pytest.fixture(scope="session")
def test_audio_dir():
    """Test audio files directory"""
    # In Docker: /app/test/
    test_dir = Path("/app/test")
    if not test_dir.exists():
        # Fallback for local testing
        test_dir = Path(__file__).parent.parent.parent.parent / "test"

    if not test_dir.exists():
        pytest.skip("Test audio directory not found")

    return test_dir


@pytest.fixture(scope="session")
def test_audio_files(test_audio_dir):
    """List of test audio files"""
    mp3_files = list(test_audio_dir.glob("*.mp3"))

    if not mp3_files:
        pytest.skip("No test audio files found")

    return sorted(mp3_files)


@pytest.fixture
def job_storage_path(tmp_path):
    """Temporary job storage for tests"""
    storage = tmp_path / "test_jobs"
    storage.mkdir(exist_ok=True)
    return storage
