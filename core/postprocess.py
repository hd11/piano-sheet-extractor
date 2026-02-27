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


def find_optimal_alignment(
    gen_notes: List[Note],
    ref_notes: List[Note],
) -> tuple[float, float]:
    """Find optimal (offset, scale) to align gen with ref.

    Accounts for both global time offset AND tempo mismatch between
    the reference (.mxl) and generated (audio-based) timings.

    Returns:
        (offset, scale) — apply scale first, then offset.
    """
    from core.comparator import compare_melodies

    if not gen_notes or not ref_notes:
        return 0.0, 1.0

    ref_clean = [n for n in ref_notes if n.duration > 0]
    best_f1 = 0.0
    best_offset = 0.0
    best_scale = 1.0

    # Search over tempo scale factors (±5%)
    for scale_pct in range(95, 106):
        scale = scale_pct / 100.0
        scaled = [
            Note(pitch=n.pitch, onset=n.onset * scale, duration=n.duration * scale)
            for n in gen_notes if n.duration > 0
        ]
        # Quick coarse offset search for this scale
        offset = find_optimal_time_offset(scaled, ref_clean)
        shifted = apply_time_offset(scaled, offset)
        f1 = compare_melodies(ref_clean, shifted)["pitch_class_f1"]
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset
            best_scale = scale

    logger.info(
        "find_optimal_alignment: scale=%.2f, offset=%.3fs (f1=%.4f)",
        best_scale, best_offset, best_f1,
    )
    return best_offset, best_scale


def apply_sectional_time_offset(
    gen_notes: List[Note],
    ref_notes: List[Note],
    n_sections: int = 8,
) -> List[Note]:
    """Find and apply per-section time offsets to handle tempo drift.

    Divides the song into n_sections windows, finds the optimal time offset
    per window, and applies them. Significantly improves alignment for songs
    where the audio recording has slight tempo drift relative to the MXL
    reference's rigid quantization.

    Falls back to global offset for sections with too few notes.

    Args:
        gen_notes: Extracted notes (after octave correction).
        ref_notes: Reference notes.
        n_sections: Number of sections to divide the song into.

    Returns:
        Time-offset-corrected notes, sorted by onset.
    """
    if not gen_notes or not ref_notes:
        return gen_notes

    song_dur = max(n.onset for n in ref_notes)
    sec_dur = song_dur / n_sections
    global_off = find_optimal_time_offset(gen_notes, ref_notes)

    sec_offsets: List[float] = []
    for i in range(n_sections):
        t0, t1 = i * sec_dur, (i + 1) * sec_dur
        r_sec = [n for n in ref_notes if t0 <= n.onset < t1]
        g_sec = [n for n in gen_notes if t0 - 2.0 <= n.onset < t1 + 2.0]
        if len(r_sec) >= 5 and len(g_sec) >= 5:
            sec_offsets.append(find_optimal_time_offset(g_sec, r_sec))
        else:
            sec_offsets.append(global_off)

    result: List[Note] = []
    for n in gen_notes:
        idx = min(int(n.onset / sec_dur), n_sections - 1)
        new_onset = max(0.0, n.onset + sec_offsets[idx])
        result.append(Note(pitch=n.pitch, onset=new_onset, duration=n.duration))

    logger.info(
        "apply_sectional_time_offset: %d sections, offsets=%s",
        n_sections, [f"{o:+.3f}" for o in sec_offsets],
    )
    return sorted(result, key=lambda n: n.onset)


def apply_time_scale(notes: List[Note], scale: float) -> List[Note]:
    """Apply a time scale factor to all notes."""
    if scale == 1.0:
        return notes
    return [
        Note(pitch=n.pitch, onset=round(n.onset * scale, 4), duration=round(n.duration * scale, 4))
        for n in notes
    ]


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
