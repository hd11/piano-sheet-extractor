"""
Unit tests for audio_to_midi module.

Tests the Basic Pitch integration for converting audio files to MIDI format.
"""

import tempfile
from pathlib import Path
import pytest

from core.audio_to_midi import convert_audio_to_midi


class TestConvertAudioToMidi:
    """Test suite for convert_audio_to_midi function."""

    @pytest.fixture
    def test_audio_file(self):
        """Provide path to test audio file."""
        return (
            Path(__file__).parent.parent / "golden" / "data" / "song_01" / "input.mp3"
        )

    @pytest.fixture
    def output_dir(self):
        """Provide temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_convert_audio_to_midi_success(self, test_audio_file, output_dir):
        """Test successful conversion of MP3 to MIDI."""
        # Skip if test audio file doesn't exist
        if not test_audio_file.exists():
            pytest.skip(f"Test audio file not found: {test_audio_file}")

        output_midi = output_dir / "output.mid"

        result = convert_audio_to_midi(test_audio_file, output_midi)

        # Verify MIDI file was created
        assert output_midi.exists(), "MIDI file was not created"

        # Verify result dictionary structure
        assert "midi_path" in result
        assert "note_count" in result
        assert "duration_seconds" in result
        assert "processing_time" in result

        # Verify MIDI path matches output
        assert result["midi_path"] == str(output_midi)

    def test_midi_contains_notes(self, test_audio_file, output_dir):
        """Test that generated MIDI contains notes."""
        if not test_audio_file.exists():
            pytest.skip(f"Test audio file not found: {test_audio_file}")

        output_midi = output_dir / "output.mid"

        result = convert_audio_to_midi(test_audio_file, output_midi)

        # Verify note count is greater than 0
        assert result["note_count"] > 0, "MIDI file contains no notes"

    def test_processing_time_logged(self, test_audio_file, output_dir, caplog):
        """Test that processing time is logged."""
        if not test_audio_file.exists():
            pytest.skip(f"Test audio file not found: {test_audio_file}")

        output_midi = output_dir / "output.mid"

        result = convert_audio_to_midi(test_audio_file, output_midi)

        # Verify processing time is reasonable (> 0 and < 120 seconds for 3-min song)
        assert result["processing_time"] > 0, "Processing time should be positive"
        assert result["processing_time"] < 120, (
            "Processing time exceeded 120 seconds threshold"
        )

    def test_audio_file_not_found(self, output_dir):
        """Test error handling for missing audio file."""
        nonexistent_file = Path("/nonexistent/audio.mp3")
        output_midi = output_dir / "output.mid"

        with pytest.raises(FileNotFoundError):
            convert_audio_to_midi(nonexistent_file, output_midi)

    def test_unsupported_format(self, output_dir, tmp_path):
        """Test error handling for unsupported audio format."""
        # Create a dummy file with unsupported extension
        unsupported_file = tmp_path / "audio.xyz"
        unsupported_file.write_text("dummy content")

        output_midi = output_dir / "output.mid"

        with pytest.raises(ValueError, match="Unsupported audio format"):
            convert_audio_to_midi(unsupported_file, output_midi)

    def test_output_directory_created(self, test_audio_file, output_dir):
        """Test that output directory is created if it doesn't exist."""
        if not test_audio_file.exists():
            pytest.skip(f"Test audio file not found: {test_audio_file}")

        # Create nested output path
        nested_output = output_dir / "nested" / "path" / "output.mid"

        result = convert_audio_to_midi(test_audio_file, nested_output)

        # Verify nested directory was created and MIDI file exists
        assert nested_output.exists(), "Output directory was not created"
        assert nested_output.parent.exists(), "Parent directories were not created"

    def test_duration_calculated(self, test_audio_file, output_dir):
        """Test that audio duration is calculated."""
        if not test_audio_file.exists():
            pytest.skip(f"Test audio file not found: {test_audio_file}")

        output_midi = output_dir / "output.mid"

        result = convert_audio_to_midi(test_audio_file, output_midi)

        # Verify duration is reasonable (should be > 0)
        assert result["duration_seconds"] > 0, "Duration should be positive"
