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
    min_note_duration: float = 0.05,
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

    # Bridge small unvoiced gaps between same-pitch frames
    # Only same-pitch bridging (pitch tolerance has zero effect per ablation)
    i = 0
    while i < len(midi):
        if midi[i] == 0:
            gap_start = i
            while i < len(midi) and midi[i] == 0:
                i += 1
            gap_len = i - gap_start
            if gap_start > 0 and i < len(midi):
                left_pitch = midi[gap_start - 1]
                right_pitch = midi[i]
                if left_pitch == right_pitch and left_pitch > 0 and gap_len <= max_gap_frames:
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


def segment_notes_quantized(
    contour: F0Contour,
    bpm: float,
    subdivisions: int = 4,
    min_voiced_ratio: float = 0.3,
) -> List[Note]:
    """Segment F0 contour into notes quantized to a BPM-based grid.

    Instead of grouping consecutive same-MIDI frames (which creates note
    boundaries at pitch transitions), this function:
    1. Creates a uniform time grid at the given BPM and subdivision
    2. For each grid cell, computes the dominant MIDI pitch (mode)
    3. Merges adjacent cells with the same pitch into single notes
    4. Cells with insufficient voiced frames become rests

    This produces notes naturally aligned to musical time, matching how
    sheet music represents melodies. The grid resolution is one beat
    divided by `subdivisions` (e.g., subdivisions=4 → 16th notes).

    Args:
        contour: F0Contour from pitch extractor.
        bpm: Estimated tempo in beats per minute.
        subdivisions: Grid cells per beat (4 = 16th notes).
        min_voiced_ratio: Minimum fraction of voiced frames in a cell
            for it to be considered pitched (vs rest).

    Returns:
        List of Note objects aligned to beat grid.
    """
    freqs = contour.frequencies.copy()
    times = contour.times

    if len(freqs) == 0:
        return []

    step = float(times[1] - times[0]) if len(times) > 1 else 0.01

    # Hz -> MIDI (0 for unvoiced)
    voiced = freqs > 0
    midi = np.zeros(len(freqs), dtype=int)
    midi[voiced] = np.round(
        12.0 * np.log2(freqs[voiced] / 440.0) + 69.0
    ).astype(int)

    # Grid cell duration in seconds
    cell_dur = 60.0 / bpm / subdivisions
    total_dur = float(times[-1]) + step if len(times) > 0 else 0.0
    n_cells = int(total_dur / cell_dur) + 1

    logger.info(
        "Quantized segmentation: bpm=%.0f, subdiv=%d, cell=%.0fms, %d cells",
        bpm, subdivisions, cell_dur * 1000, n_cells,
    )

    # For each grid cell, determine the dominant pitch
    cell_pitches = []
    for c in range(n_cells):
        t_start = c * cell_dur
        t_end = (c + 1) * cell_dur

        # Find F0 frames in this cell
        frame_start = int(t_start / step)
        frame_end = int(t_end / step)
        frame_end = min(frame_end, len(midi))

        if frame_start >= frame_end:
            cell_pitches.append(0)
            continue

        cell_midi = midi[frame_start:frame_end]
        voiced_midi = cell_midi[cell_midi > 0]

        if len(voiced_midi) < len(cell_midi) * min_voiced_ratio:
            cell_pitches.append(0)  # rest
        else:
            # Use mode (most frequent MIDI value) for robustness
            counts = np.bincount(voiced_midi)
            cell_pitches.append(int(np.argmax(counts)))

    # Merge adjacent cells with same pitch into notes
    notes: List[Note] = []
    i = 0
    while i < len(cell_pitches):
        if cell_pitches[i] == 0:
            i += 1
            continue

        pitch = cell_pitches[i]
        start_cell = i
        i += 1
        while i < len(cell_pitches) and cell_pitches[i] == pitch:
            i += 1

        onset = start_cell * cell_dur
        duration = (i - start_cell) * cell_dur

        if 21 <= pitch <= 108:
            notes.append(
                Note(
                    pitch=pitch,
                    onset=round(onset, 4),
                    duration=round(duration, 4),
                )
            )

    logger.info(
        "Quantized: %d notes from %d cells (%.1fs)",
        len(notes), n_cells, total_dur,
    )

    if notes:
        pitches_arr = [n.pitch for n in notes]
        logger.info(
            "Pitch range: MIDI %d-%d, median=%d",
            min(pitches_arr), max(pitches_arr), int(np.median(pitches_arr)),
        )

    return notes
