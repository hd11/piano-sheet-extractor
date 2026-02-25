"""Integrated vocal melody extraction pipeline.

Chains vocal separation, F0 extraction, and note segmentation into a single
end-to-end function that extracts melody from MP3 files.

Pipeline:
    separate_vocals() → extract_f0() → f0_to_notes()
"""

import logging
from pathlib import Path
from typing import Optional

import librosa
import numpy as np

from core.f0_extractor import extract_f0, f0_to_notes
from core.types import Note
from core.vocal_separator import separate_vocals

logger = logging.getLogger(__name__)

_DEFAULT_BPM = 120.0


def detect_bpm(audio: np.ndarray, sr: int) -> float:
    """Detect BPM from an audio signal using librosa.

    Args:
        audio: Mono audio waveform (float32).
        sr: Sample rate.

    Returns:
        Detected BPM as float. Falls back to 120.0 on failure.
    """
    try:
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])
        if bpm <= 0:
            logger.warning("detect_bpm: invalid tempo %.1f, falling back to %.1f", bpm, _DEFAULT_BPM)
            return _DEFAULT_BPM
        logger.info("detect_bpm: detected %.1f BPM", bpm)
        return bpm
    except Exception as e:
        logger.warning("detect_bpm: failed (%s), falling back to %.1f", e, _DEFAULT_BPM)
        return _DEFAULT_BPM


def extract_melody(
    mp3_path: Path,
    cache_dir: Optional[Path] = None,
    periodicity_threshold: Optional[float] = None,
    min_note_dur: Optional[float] = None,
    model: str = "full",
) -> list[Note]:
    """End-to-end melody extraction from an MP3 file.

    Chains the vocal melody extraction pipeline:
    separate_vocals -> extract_f0 -> f0_to_notes

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for cached .npz files. Defaults to None (no caching).
        periodicity_threshold: Minimum periodicity confidence for voiced frames.
            None uses the default (0.6).
        min_note_dur: Minimum note duration in seconds.
            None uses the default (0.04).
        model: torchcrepe model size (default 'full').

    Returns:
        List of Note objects representing the extracted melody.
        Returns empty list if no voiced frames are detected.
    """
    logger.info("extract_melody: starting pipeline for %s", mp3_path)

    # Step 1: Separate vocals from the MP3
    vocals, sr = separate_vocals(mp3_path, cache_dir)

    # Handle edge case: empty vocals
    if vocals is None or len(vocals) == 0:
        logger.warning("extract_melody: no vocals extracted")
        return []

    # Step 2: Extract F0 (fundamental frequency) and periodicity
    f0, periodicity = extract_f0(vocals, sr, hop_ms=10.0, model=model)

    # Handle edge case: no F0 data
    if f0 is None or len(f0) == 0:
        logger.warning("extract_melody: no F0 extracted")
        return []

    # Step 3: Convert F0 contour to note segments
    # hop_sec = 10ms (0.01 seconds) matches the 10ms hop_ms from extract_f0
    kwargs: dict = {"hop_sec": 0.01}
    if periodicity_threshold is not None:
        kwargs["periodicity_threshold"] = periodicity_threshold
    if min_note_dur is not None:
        kwargs["min_note_dur"] = min_note_dur
    notes = f0_to_notes(f0, periodicity, **kwargs)

    # Handle edge case: no voiced frames
    if not notes:
        logger.warning("extract_melody: no voiced frames detected")
        return []

    logger.info("extract_melody: pipeline complete, %d notes", len(notes))
    return notes


def extract_melody_with_bpm(
    mp3_path: Path,
    cache_dir: Optional[Path] = None,
    periodicity_threshold: Optional[float] = None,
    min_note_dur: Optional[float] = None,
    model: str = "full",
) -> tuple[list[Note], float]:
    """Extract melody and auto-detect BPM from an MP3 file.

    Same as extract_melody but also runs BPM detection on the separated vocals.

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for cached .npz files. Defaults to None (no caching).
        periodicity_threshold: Minimum periodicity confidence for voiced frames.
            None uses the default (0.6).
        min_note_dur: Minimum note duration in seconds.
            None uses the default (0.04).
        model: torchcrepe model size (default 'full').

    Returns:
        Tuple of (notes, bpm).
    """
    logger.info("extract_melody_with_bpm: starting pipeline for %s", mp3_path)

    # Step 1: Separate vocals
    vocals, sr = separate_vocals(mp3_path, cache_dir)

    if vocals is None or len(vocals) == 0:
        logger.warning("extract_melody_with_bpm: no vocals extracted")
        return [], _DEFAULT_BPM

    # Step 2: Detect BPM from vocals
    bpm = detect_bpm(vocals, sr)

    # Step 3: Extract F0
    f0, periodicity = extract_f0(vocals, sr, hop_ms=10.0, model=model)

    if f0 is None or len(f0) == 0:
        logger.warning("extract_melody_with_bpm: no F0 extracted")
        return [], bpm

    # Step 4: Convert F0 to notes
    kwargs: dict = {"hop_sec": 0.01}
    if periodicity_threshold is not None:
        kwargs["periodicity_threshold"] = periodicity_threshold
    if min_note_dur is not None:
        kwargs["min_note_dur"] = min_note_dur
    notes = f0_to_notes(f0, periodicity, **kwargs)

    if not notes:
        logger.warning("extract_melody_with_bpm: no voiced frames detected")
        return [], bpm

    logger.info("extract_melody_with_bpm: pipeline complete, %d notes, %.1f BPM", len(notes), bpm)
    return notes, bpm
