"""Self-contained postprocessing for extracted melody notes.

ARCHITECTURE GUARD: No function in this module accepts ref_notes or any
reference data as a parameter. All corrections are self-contained using
only the extracted notes and optionally the source audio.
"""

import logging
from typing import List, Optional

import librosa
import numpy as np

from .types import Note

logger = logging.getLogger(__name__)

# Vocal range limits (MIDI)
VOCAL_RANGE_LOW = 48   # C3
VOCAL_RANGE_HIGH = 84  # C6


def postprocess_notes(
    notes: List[Note],
    audio: Optional[np.ndarray] = None,
    sr: Optional[int] = None,
) -> List[Note]:
    """Apply self-contained postprocessing to extracted notes.

    Steps:
    1. Remove outliers (notes far from local pitch median)
    2. Merge consecutive same-pitch notes with small gaps
    3. Self-octave correction (pull outliers toward local median)
    4. Clip to vocal range
    5. Beat-aligned onset snapping (if audio provided)

    Args:
        notes: Raw extracted Note list.
        audio: Source audio signal (for beat tracking). No reference data.
        sr: Sample rate of audio.

    Returns:
        Cleaned Note list.
    """
    if len(notes) < 2:
        return notes

    original_count = len(notes)

    notes = _remove_outliers(notes)
    notes = _merge_same_pitch(notes)
    notes = _global_octave_adjust(notes)
    notes = _self_octave_correction(notes)
    notes = _clip_vocal_range(notes)

    # Beat-aligned onset snapping (self-contained, uses audio only)
    if audio is not None and sr is not None:
        notes = _snap_to_beats(notes, audio, sr)

    logger.info(
        "Postprocessing: %d -> %d notes",
        original_count,
        len(notes),
    )

    return notes


def _remove_outliers(
    notes: List[Note],
    window: int = 15,
    threshold: int = 9,
) -> List[Note]:
    """Remove notes that are far from their local pitch median.

    A note is considered an outlier if its pitch is more than `threshold`
    semitones away from the median pitch of the surrounding window.

    Args:
        notes: Input notes.
        window: Half-window size for local median computation.
        threshold: Maximum allowed distance from local median in semitones.

    Returns:
        Filtered notes with outliers removed.
    """
    if len(notes) < 5:
        return notes

    pitches = np.array([n.pitch for n in notes])
    keep = []

    for i, n in enumerate(notes):
        lo = max(0, i - window)
        hi = min(len(notes), i + window + 1)
        local_median = np.median(pitches[lo:hi])
        if abs(n.pitch - local_median) <= threshold:
            keep.append(n)

    removed = len(notes) - len(keep)
    if removed > 0:
        logger.info("Outlier removal: %d/%d notes removed", removed, len(notes))

    return keep if keep else notes


def _merge_same_pitch(
    notes: List[Note],
    max_gap: float = 0.15,
) -> List[Note]:
    """Merge consecutive notes with the same pitch and small gap.

    Args:
        notes: Input notes sorted by onset.
        max_gap: Maximum gap in seconds to merge across.

    Returns:
        Notes with same-pitch consecutive notes merged.
    """
    if len(notes) < 2:
        return notes

    merged = [notes[0]]
    for i in range(1, len(notes)):
        prev = merged[-1]
        curr = notes[i]
        gap = curr.onset - (prev.onset + prev.duration)
        if curr.pitch == prev.pitch and gap < max_gap:
            new_dur = (curr.onset + curr.duration) - prev.onset
            merged[-1] = Note(
                pitch=prev.pitch,
                onset=prev.onset,
                duration=new_dur,
                velocity=prev.velocity,
            )
        else:
            merged.append(curr)

    if len(merged) < len(notes):
        logger.info(
            "Same-pitch merge: %d -> %d notes",
            len(notes),
            len(merged),
        )

    return merged


def _self_octave_correction(
    notes: List[Note],
    window: int = 15,
    jump_threshold: int = 7,
) -> List[Note]:
    """Correct octave errors by pulling outliers toward local median.

    If a note is more than `jump_threshold` semitones away from the local
    median pitch, try shifting it by octaves (+-12, +-24) and pick the
    shift that brings it closest to the median while staying in vocal range.

    Args:
        notes: Input notes.
        window: Half-window size for local median.
        jump_threshold: Minimum distance from median to trigger correction.

    Returns:
        Notes with octave errors corrected.
    """
    if len(notes) < 5:
        return notes

    pitches = np.array([n.pitch for n in notes])
    corrected = pitches.copy()
    corrections = 0

    for i in range(len(pitches)):
        lo = max(0, i - window)
        hi = min(len(pitches), i + window + 1)
        local_median = float(np.median(pitches[lo:hi]))

        if abs(pitches[i] - local_median) > jump_threshold:
            best_pitch = pitches[i]
            best_dist = abs(pitches[i] - local_median)
            for shift in [-24, -12, 12, 24]:
                candidate = pitches[i] + shift
                dist = abs(candidate - local_median)
                if dist < best_dist and VOCAL_RANGE_LOW <= candidate <= VOCAL_RANGE_HIGH:
                    best_dist = dist
                    best_pitch = candidate
            if best_pitch != pitches[i]:
                corrected[i] = best_pitch
                corrections += 1

    if corrections > 0:
        logger.info(
            "Self-octave correction: %d/%d notes corrected",
            corrections,
            len(notes),
        )

    return [
        Note(
            pitch=int(corrected[i]),
            onset=n.onset,
            duration=n.duration,
            velocity=n.velocity,
        )
        for i, n in enumerate(notes)
    ]


def _global_octave_adjust(notes: List[Note]) -> List[Note]:
    """Shift all notes by whole octaves to match expected vocal range.

    CREPE on separated vocals often detects pitch one octave too low
    (subharmonic locking). This corrects by checking if the median pitch
    falls below the typical vocal center and shifting up by 12 if so.

    Uses a vocal range prior (center C5=72, threshold 6 semitones):
    - median < 66 (F#4): shift up +12 (likely subharmonic)
    - median > 78 (F#5): shift down -12 (unlikely but handled)
    - 66 <= median <= 78: no shift (normal vocal range)

    This is entirely self-contained — NO reference data used.
    """
    if len(notes) < 5:
        return notes

    vocal_center = 72  # C5 — typical K-pop vocal center
    threshold = 6      # semitones from center to trigger shift

    median_pitch = float(np.median([n.pitch for n in notes]))

    if median_pitch < vocal_center - threshold:
        shift = 12
    elif median_pitch > vocal_center + threshold:
        shift = -12
    else:
        return notes

    shifted = [
        Note(
            pitch=n.pitch + shift,
            onset=n.onset,
            duration=n.duration,
            velocity=n.velocity,
        )
        for n in notes
    ]

    new_median = float(np.median([n.pitch for n in shifted]))
    logger.info(
        "Global octave adjust: shift=%+d (median %d -> %d)",
        shift,
        int(median_pitch),
        int(new_median),
    )

    return shifted


def _clip_vocal_range(notes: List[Note]) -> List[Note]:
    """Remove notes outside typical vocal range."""
    clipped = [n for n in notes if VOCAL_RANGE_LOW <= n.pitch <= VOCAL_RANGE_HIGH]
    removed = len(notes) - len(clipped)
    if removed > 0:
        logger.info(
            "Vocal range clip: %d/%d notes removed (range MIDI %d-%d)",
            removed,
            len(notes),
            VOCAL_RANGE_LOW,
            VOCAL_RANGE_HIGH,
        )
    return clipped


def _snap_to_beats(
    notes: List[Note],
    audio: np.ndarray,
    sr: int,
    subdivisions: int = 4,
) -> List[Note]:
    """Snap note onsets to nearest beat subdivision.

    Uses librosa beat tracking to build a beat grid, then subdivides
    each beat interval (e.g. subdivisions=4 for 16th notes).
    Each note onset is moved to the nearest grid point within a
    maximum snap distance (half a subdivision).

    Self-contained: uses audio only, no reference data.

    Args:
        notes: Input notes.
        audio: Source audio signal.
        sr: Sample rate.
        subdivisions: Number of subdivisions per beat (4 = 16th notes).

    Returns:
        Notes with onsets snapped to beat grid.
    """
    if len(notes) == 0:
        return notes

    _, beats = librosa.beat.beat_track(y=audio, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)

    if len(beat_times) < 2:
        logger.warning("Beat tracking found < 2 beats, skipping snap")
        return notes

    # Build subdivision grid from beat times
    grid = []
    for i in range(len(beat_times) - 1):
        beat_dur = beat_times[i + 1] - beat_times[i]
        sub_dur = beat_dur / subdivisions
        for s in range(subdivisions):
            grid.append(beat_times[i] + s * sub_dur)
    grid.append(beat_times[-1])
    grid = np.array(grid)

    # Max snap distance = half a subdivision interval
    sub_intervals = np.diff(grid)
    max_snap = float(np.median(sub_intervals)) * 0.5

    snapped_count = 0
    snapped = []
    for n in notes:
        idx = np.argmin(np.abs(grid - n.onset))
        dist = abs(grid[idx] - n.onset)
        if dist <= max_snap:
            new_onset = round(float(grid[idx]), 4)
            snapped_count += 1
        else:
            new_onset = n.onset
        snapped.append(Note(
            pitch=n.pitch,
            onset=new_onset,
            duration=n.duration,
            velocity=n.velocity,
        ))

    logger.info(
        "Beat snap: %d/%d notes snapped (max_snap=%.0fms, grid=%d points)",
        snapped_count,
        len(notes),
        max_snap * 1000,
        len(grid),
    )

    return snapped
