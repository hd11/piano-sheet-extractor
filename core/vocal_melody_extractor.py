"""Integrated vocal melody extraction pipeline.

Chains vocal separation, F0 extraction, and note segmentation into a single
end-to-end function that extracts melody from MP3 files.

Pipeline:
    separate_vocals() → extract_f0() → f0_to_notes()
"""

import logging
from pathlib import Path
from typing import Optional

from core.f0_extractor import extract_f0, f0_to_notes
from core.types import Note
from core.vocal_separator import separate_vocals

logger = logging.getLogger(__name__)


def extract_melody(mp3_path: Path, cache_dir: Optional[Path] = None) -> list[Note]:
    """End-to-end melody extraction from an MP3 file.

    Chains the vocal melody extraction pipeline:
    separate_vocals -> extract_f0 -> f0_to_notes

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for cached .npz files. Defaults to None (no caching).

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
    f0, periodicity = extract_f0(vocals, sr, hop_ms=10.0)

    # Handle edge case: no F0 data
    if f0 is None or len(f0) == 0:
        logger.warning("extract_melody: no F0 extracted")
        return []

    # Step 3: Convert F0 contour to note segments
    # hop_sec = 10ms (0.01 seconds) matches the 10ms hop_ms from extract_f0
    notes = f0_to_notes(f0, periodicity, hop_sec=0.01)

    # Handle edge case: no voiced frames
    if not notes:
        logger.warning("extract_melody: no voiced frames detected")
        return []

    logger.info("extract_melody: pipeline complete, %d notes", len(notes))
    return notes
