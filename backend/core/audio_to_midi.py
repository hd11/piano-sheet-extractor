"""
Audio to MIDI conversion using Basic Pitch (Spotify).

This module provides functionality to convert audio files (MP3/WAV) to MIDI format
using the Basic Pitch model for polyphonic music transcription.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any

# Fix scipy compatibility issue with librosa
# scipy 1.14+ moved window functions to scipy.signal.windows
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

import librosa
import pretty_midi
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

logger = logging.getLogger(__name__)

# Model path cached for potential future use (Basic Pitch handles model loading internally)
_model_path = None


def _get_model_path():
    """Get Basic Pitch model path (singleton-like pattern for consistency)."""
    global _model_path

    if _model_path is None:
        _model_path = ICASSP_2022_MODEL_PATH
        logger.info(f"Using Basic Pitch model: {_model_path}")

    return _model_path


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
        RuntimeError: If model loading or generation fails
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
        # Get model path (logs once on first call)
        model_path = _get_model_path()

        # Calculate duration using librosa
        logger.info("Loading audio to calculate duration...")
        duration_seconds = librosa.get_duration(path=str(audio_path))
        logger.info(f"Audio duration: {duration_seconds:.2f}s")

        # Run Basic Pitch prediction
        logger.info("Running Basic Pitch transcription...")
        model_output, midi_data, note_events = predict(
            str(audio_path),
            model_path,
        )

        # Save MIDI file
        # midi_data is a pretty_midi.PrettyMIDI object
        midi_data.write(str(output_path))

        processing_time = time.time() - start_time
        logger.info(f"MIDI generation completed in {processing_time:.2f}s")

        # Count notes from MIDI
        note_count = sum(
            len(instrument.notes)
            for instrument in midi_data.instruments
            if not instrument.is_drum
        )

        logger.info(f"MIDI file written to: {output_path}")
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
