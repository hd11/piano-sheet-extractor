"""Convert F0 contour to discrete Note list.

Groups stable pitch regions from the continuous F0 contour into
individual Note objects with MIDI pitch, onset, and duration.
"""

import logging
from typing import List

import numpy as np

from .types import F0Contour, Note

logger = logging.getLogger(__name__)


def segment_notes(
    contour: F0Contour,
    min_note_duration: float = 0.06,
    max_gap_frames: int = 5,
) -> List[Note]:
    """Convert an F0 contour into a list of discrete Note objects.

    Algorithm:
    1. Convert F0 (Hz) to rounded MIDI note numbers per frame
    2. Bridge small unvoiced gaps between same-pitch frames
    3. Group consecutive frames with the same MIDI pitch
    4. Filter out notes shorter than min_note_duration

    Args:
        contour: F0Contour from pitch_extractor.
        min_note_duration: Minimum note duration in seconds (default 80ms).
        max_gap_frames: Maximum unvoiced gap to bridge within a note.

    Returns:
        List of Note objects sorted by onset time.
    """
    freqs = contour.frequencies.copy()
    times = contour.times

    if len(freqs) == 0:
        return []

    step = float(times[1] - times[0]) if len(times) > 1 else 0.01

    # Hz -> MIDI (0 for unvoiced)
    voiced = freqs > 0
    midi = np.zeros(len(freqs), dtype=int)
    midi[voiced] = np.round(12.0 * np.log2(freqs[voiced] / 440.0) + 69.0).astype(int)

    # Bridge small gaps: fill short unvoiced spans when surrounded by same pitch
    i = 0
    while i < len(midi):
        if midi[i] == 0:
            gap_start = i
            while i < len(midi) and midi[i] == 0:
                i += 1
            gap_len = i - gap_start
            if gap_len <= max_gap_frames and gap_start > 0 and i < len(midi):
                left_pitch = midi[gap_start - 1]
                right_pitch = midi[i]
                if left_pitch == right_pitch and left_pitch > 0:
                    midi[gap_start:i] = left_pitch
        else:
            i += 1

    # Group consecutive same-pitch frames into notes
    notes: List[Note] = []
    i = 0
    while i < len(midi):
        if midi[i] == 0:
            i += 1
            continue

        pitch = int(midi[i])
        start = i
        i += 1
        while i < len(midi) and midi[i] == pitch:
            i += 1

        onset = float(times[start])
        duration = (i - start) * step

        if duration >= min_note_duration and 21 <= pitch <= 108:
            notes.append(
                Note(
                    pitch=pitch,
                    onset=round(onset, 4),
                    duration=round(duration, 4),
                )
            )

    logger.info(
        "Segmented %d notes from %d frames (%.1fs, step=%.1fms)",
        len(notes),
        len(freqs),
        len(freqs) * step,
        step * 1000,
    )

    if notes:
        pitches = [n.pitch for n in notes]
        logger.info(
            "Pitch range: MIDI %d-%d, median=%d",
            min(pitches),
            max(pitches),
            int(np.median(pitches)),
        )

    return notes
