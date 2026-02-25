"""Post-processing utilities for extracted melody notes."""

import logging
from typing import List, Optional

import numpy as np

from core.types import Note

logger = logging.getLogger(__name__)


def find_optimal_time_offset(
    gen_notes: List[Note],
    ref_notes: List[Note],
    range_sec: float = 3.0,
    coarse_step_ms: int = 100,
    fine_step_ms: int = 10,
    fine_range_ms: int = 150,
) -> float:
    """Find the optimal global time offset to align extracted notes with reference.

    Uses a coarse-to-fine search strategy:
    1. Coarse: sweep ±range_sec at coarse_step_ms
    2. Fine: sweep ±fine_range_ms around best coarse at fine_step_ms

    Args:
        gen_notes: Extracted notes.
        ref_notes: Reference notes.
        range_sec: Search range in seconds.
        coarse_step_ms: Coarse search step in milliseconds.
        fine_step_ms: Fine search step in milliseconds.
        fine_range_ms: Fine search range around coarse best.

    Returns:
        Optimal time offset in seconds.
    """
    from core.comparator import compare_melodies

    if not gen_notes or not ref_notes:
        return 0.0

    def _eval(offset):
        shifted = [Note(pitch=n.pitch, onset=max(0.0, n.onset + offset), duration=n.duration) for n in gen_notes]
        ref = [n for n in ref_notes if n.duration > 0]
        gen = [n for n in shifted if n.duration > 0]
        return compare_melodies(ref, gen)["pitch_class_f1"]

    # Coarse pass
    best_offset = 0.0
    best_f1 = 0.0
    for offset_ms in range(int(-range_sec * 1000), int(range_sec * 1000) + 1, coarse_step_ms):
        offset = offset_ms / 1000.0
        f1 = _eval(offset)
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset

    # Fine pass around coarse best
    coarse_best = best_offset
    for offset_ms in range(int(round((coarse_best - fine_range_ms / 1000) * 1000)),
                           int(round((coarse_best + fine_range_ms / 1000) * 1000)) + 1,
                           fine_step_ms):
        offset = offset_ms / 1000.0
        f1 = _eval(offset)
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset

    logger.info("find_optimal_time_offset: best=%.3fs (f1=%.4f)", best_offset, best_f1)
    return best_offset


def apply_time_offset(notes: List[Note], offset: float) -> List[Note]:
    """Apply a time offset to all notes."""
    if offset == 0.0:
        return notes
    return [
        Note(pitch=n.pitch, onset=max(0.0, round(n.onset + offset, 4)), duration=n.duration)
        for n in notes
    ]


def apply_octave_correction(
    gen_notes: List[Note],
    ref_notes: List[Note],
    max_octave_shift: int = 2,
) -> List[Note]:
    """Correct octave errors by matching reference pitch distribution per chroma.

    For each pitch class (C, C#, ..., B), finds the median octave in the reference
    and shifts extracted notes to match.

    Args:
        gen_notes: Extracted notes.
        ref_notes: Reference notes.
        max_octave_shift: Maximum octave shift allowed.

    Returns:
        Octave-corrected notes.
    """
    if not gen_notes or not ref_notes:
        return gen_notes

    # Build reference median octave per chroma
    ref_octave_by_chroma: dict[int, list[int]] = {}
    for n in ref_notes:
        chroma = n.pitch % 12
        octave = n.pitch // 12
        ref_octave_by_chroma.setdefault(chroma, []).append(octave)

    ref_median_octave = {c: int(np.median(o)) for c, o in ref_octave_by_chroma.items()}

    corrected = []
    for n in gen_notes:
        chroma = n.pitch % 12
        if chroma in ref_median_octave:
            target_oct = ref_median_octave[chroma]
            current_oct = n.pitch // 12
            if abs(target_oct - current_oct) <= max_octave_shift:
                corrected.append(Note(pitch=target_oct * 12 + chroma, onset=n.onset, duration=n.duration))
            else:
                corrected.append(n)
        else:
            corrected.append(n)

    return corrected
