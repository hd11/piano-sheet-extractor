"""Multi-model note selection: choose more pitch-stable notes from two models."""

import logging
from typing import List

import numpy as np

from .types import F0Contour, Note

logger = logging.getLogger(__name__)


def _pitch_variance_for_note(note: Note, contour: F0Contour) -> float:
    """Compute pitch variance of F0 frames within a note's time span.

    Lower variance = more stable pitch = more reliable note.
    Returns a large value (999.0) if no voiced frames found in span.
    """
    times = contour.times
    freqs = contour.frequencies
    step = float(times[1] - times[0]) if len(times) > 1 else 0.01

    frame_start = int(note.onset / step)
    frame_end = int((note.onset + note.duration) / step)
    frame_end = min(frame_end, len(freqs))

    if frame_start >= frame_end:
        return 999.0

    segment_freqs = freqs[frame_start:frame_end]
    voiced = segment_freqs[segment_freqs > 0]

    if len(voiced) == 0:
        return 999.0

    # Convert to MIDI for variance (log-scale better for pitch)
    midi_voiced = 12.0 * np.log2(voiced / 440.0) + 69.0
    return float(np.var(midi_voiced))


def select_notes_multi_model(
    notes_a: List[Note],
    contour_a: F0Contour,
    notes_b: List[Note],
    contour_b: F0Contour,
    onset_tolerance: float = 0.05,
    priority_model: str = "a",
) -> List[Note]:
    """Select better notes from two model outputs using pitch variance.

    Algorithm:
    1. Match notes from A and B by onset proximity (within tolerance)
    2. For matched pairs: select the note with lower pitch variance
    3. For unmatched notes (only in A or only in B): keep them
    4. Sort by onset and return

    Args:
        notes_a: Notes from model A (e.g., FCPE).
        contour_a: F0Contour from model A.
        notes_b: Notes from model B (e.g., RMVPE).
        contour_b: F0Contour from model B.
        onset_tolerance: Max onset difference (seconds) to consider notes matched.
        priority_model: Tie-breaking preference ("a" or "b").

    Returns:
        Merged list of best notes, sorted by onset.
    """
    if not notes_a:
        return list(notes_b)
    if not notes_b:
        return list(notes_a)

    # Match notes greedily by onset proximity
    used_b: set = set()
    result: List[Note] = []

    for note_a in notes_a:
        # Find closest unmatched note in B within tolerance
        best_b_idx = None
        best_dist = onset_tolerance + 1.0
        for j, note_b in enumerate(notes_b):
            if j in used_b:
                continue
            dist = abs(note_a.onset - note_b.onset)
            if dist <= onset_tolerance and dist < best_dist:
                best_dist = dist
                best_b_idx = j

        if best_b_idx is not None:
            # Matched pair: compare pitch variance
            used_b.add(best_b_idx)
            note_b = notes_b[best_b_idx]
            var_a = _pitch_variance_for_note(note_a, contour_a)
            var_b = _pitch_variance_for_note(note_b, contour_b)

            if var_b < var_a:
                result.append(note_b)
            elif var_a < var_b:
                result.append(note_a)
            else:
                # Tie: use priority model
                result.append(note_a if priority_model == "a" else note_b)
        else:
            # Only in A: keep
            result.append(note_a)

    # Add unmatched notes from B
    for j, note_b in enumerate(notes_b):
        if j not in used_b:
            result.append(note_b)

    result.sort(key=lambda n: n.onset)

    logger.info(
        "Multi-model selection: %d (A) + %d (B) -> %d notes (onset_tol=%.0fms)",
        len(notes_a),
        len(notes_b),
        len(result),
        onset_tolerance * 1000,
    )

    return result
