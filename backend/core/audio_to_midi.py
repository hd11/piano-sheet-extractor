"""
Audio to MIDI conversion using Basic Pitch.

This module provides functionality to convert audio files (MP3/WAV) to MIDI format
using Spotify's Basic Pitch model.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any

# Fix scipy compatibility issue with basic-pitch and librosa
# scipy 1.17+ moved window functions to scipy.signal.windows
import scipy.signal
import scipy.signal.windows as windows

if not hasattr(scipy.signal, "gaussian"):
    scipy.signal.gaussian = windows.gaussian
if not hasattr(scipy.signal, "hann"):
    scipy.signal.hann = windows.hann
if not hasattr(scipy.signal, "hamming"):
    scipy.signal.hamming = windows.hamming
if not hasattr(scipy.signal, "blackman"):
    scipy.signal.blackman = windows.blackman
if not hasattr(scipy.signal, "bartlett"):
    scipy.signal.bartlett = windows.bartlett

from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

logger = logging.getLogger(__name__)


def convert_audio_to_midi(audio_path: Path, output_path: Path) -> Dict[str, Any]:
    """
    Convert audio file to MIDI using Basic Pitch.

    Args:
        audio_path: Path to input audio file (MP3/WAV)
        output_path: Path to save MIDI file

    Returns:
        Dictionary with keys:
            - midi_path: Path to generated MIDI file
            - note_count: Number of notes in the MIDI
            - duration_seconds: Duration of the audio in seconds
            - processing_time: Time taken to process in seconds

    Raises:
        FileNotFoundError: If audio file does not exist
        ValueError: If audio file format is not supported
    """
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    # Validate input file exists
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Validate file extension
    supported_formats = {".mp3", ".wav", ".flac", ".ogg"}
    if audio_path.suffix.lower() not in supported_formats:
        raise ValueError(
            f"Unsupported audio format: {audio_path.suffix}. "
            f"Supported formats: {supported_formats}"
        )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting audio to MIDI conversion: {audio_path}")
    start_time = time.time()

    try:
        # Run Basic Pitch inference
        model_output, midi_data, note_events = predict(
            str(audio_path),
            model_or_model_path=ICASSP_2022_MODEL_PATH,
        )

        processing_time = time.time() - start_time
        logger.info(f"Basic Pitch inference completed in {processing_time:.2f}s")

        # Write MIDI file
        midi_data.write(str(output_path))
        logger.info(f"MIDI file written to: {output_path}")

        # Calculate metadata
        note_count = len(note_events) if note_events is not None else 0

        # Handle both old and new basic-pitch API
        # Newer versions return a dict, older versions return an array
        if isinstance(model_output, dict):
            # New API: model_output is a dict with keys like 'contour', 'onset', 'frame'
            # Use MIDI data duration as fallback
            duration_seconds = midi_data.get_end_time()
        else:
            # Old API: model_output is an array
            duration_seconds = (
                model_output.shape[0] / 50.0
            )  # Basic Pitch outputs at 50Hz

        logger.info(
            f"Conversion complete: {note_count} notes, "
            f"duration {duration_seconds:.2f}s, "
            f"processing time {processing_time:.2f}s"
        )

        return {
            "midi_path": str(output_path),
            "note_count": note_count,
            "duration_seconds": duration_seconds,
            "processing_time": processing_time,
        }

    except Exception as e:
        logger.error(f"Error during audio to MIDI conversion: {e}")
        raise
