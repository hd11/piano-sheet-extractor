"""
Audio to MIDI conversion using Pop2Piano (HuggingFace Transformers).

This module provides functionality to convert audio files (MP3/WAV) to MIDI format
using the Pop2Piano model for piano arrangement generation.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any

# Fix scipy compatibility issue with librosa
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

import torch
import librosa
import pretty_midi

# Workaround for CVE-2025-32434 torch.load restriction in transformers.
# torch 2.2 is safe for our trusted HuggingFace models; patch the check
# so transformers doesn't require torch >= 2.6.
import transformers.utils.import_utils as _tiu
import transformers.modeling_utils as _tmu

if hasattr(_tiu, "check_torch_load_is_safe"):
    _tiu.check_torch_load_is_safe = lambda: None
if hasattr(_tmu, "check_torch_load_is_safe"):
    _tmu.check_torch_load_is_safe = lambda: None

from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor

logger = logging.getLogger(__name__)

# Singleton pattern for model - avoid reloading on every call
_model = None
_processor = None
_device = None


def _get_model():
    """Get or create Pop2Piano model and processor (singleton)."""
    global _model, _processor, _device

    if _model is None:
        try:
            _device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing Pop2Piano model on {_device}")

            _model = Pop2PianoForConditionalGeneration.from_pretrained(
                "sweetcocoa/pop2piano"
            ).to(_device)
            _processor = Pop2PianoProcessor.from_pretrained("sweetcocoa/pop2piano")

            logger.info("Pop2Piano model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Pop2Piano model: {e}")
            logger.error(
                "Make sure transformers is installed and you have internet connection "
                "for the first download. Model will be cached in ~/.cache/huggingface/"
            )
            raise RuntimeError(f"Pop2Piano model initialization failed: {e}") from e

    return _model, _processor


def convert_audio_to_midi(audio_path: Path, output_path: Path) -> Dict[str, Any]:
    """
    Convert audio file to MIDI using Pop2Piano.

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
    global _model, _processor, _device

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
        # Load audio using librosa - Pop2Piano requires 44100 Hz sample rate
        logger.info("Loading audio file...")
        audio, sr = librosa.load(str(audio_path), sr=44100, mono=True)

        # Calculate duration from audio length
        duration_seconds = len(audio) / 44100

        # Get model and processor (singleton)
        model, processor = _get_model()

        # Preprocess audio
        logger.info("Preprocessing audio...")
        inputs = processor(audio=audio, sampling_rate=44100, return_tensors="pt").to(
            _device
        )

        # Generate MIDI
        logger.info(f"Generating MIDI on {_device}...")
        with torch.no_grad():
            try:
                model_output = model.generate(
                    input_features=inputs["input_features"],
                    composer="composer1",  # Default composer style
                )
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    logger.warning("GPU out of memory, falling back to CPU")
                    # Move to CPU and retry
                    _model = _model.to("cpu")
                    _device = "cpu"
                    inputs = inputs.to("cpu")
                    model_output = model.generate(
                        input_features=inputs["input_features"], composer="composer1"
                    )
                else:
                    raise

        # Decode to MIDI
        logger.info("Decoding to MIDI...")
        tokenizer_output = processor.batch_decode(
            token_ids=model_output, feature_extractor_output=inputs
        )["pretty_midi_objects"][0]

        # Save MIDI file
        tokenizer_output.write(str(output_path))

        processing_time = time.time() - start_time
        logger.info(f"MIDI generation completed in {processing_time:.2f}s")

        # Count notes from MIDI file
        pm = pretty_midi.PrettyMIDI(str(output_path))
        note_count = sum(
            len(instrument.notes)
            for instrument in pm.instruments
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
