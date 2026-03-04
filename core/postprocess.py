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
    bpm: Optional[float] = None,
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
        bpm: Estimated BPM (for adaptive grid resolution).

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
    # Adaptive subdivisions: fast songs (>=140 BPM) use 16th notes, slow songs use 8th notes
    if audio is not None and sr is not None:
        subdivisions = 4 if (bpm is not None and bpm >= 140) else 2
        notes = _snap_to_beats(notes, audio, sr, subdivisions=subdivisions)

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
    """Shift notes by whole octaves using sectional analysis.

    CREPE on separated vocals often detects pitch one octave too low
    (subharmonic locking). Instead of a single global shift, this
    analyzes notes in overlapping time windows and determines the
    best octave shift per section to bring the median into the
    expected vocal range.

    Strategy:
    1. First pass: determine dominant octave shift from overall median
    2. Second pass: for each section (~30 notes), verify the shift and
       apply per-section correction if needed

    This is entirely self-contained — NO reference data used.
    """
    if len(notes) < 5:
        return notes

    # Target vocal range: most vocals sit in MIDI 60-84 (C4-C6)
    # Center biased to 75 (Eb5) because CREPE consistently locks on
    # subharmonics — we want to favor shifting UP over not shifting.
    vocal_target_low = 60
    vocal_target_high = 84
    vocal_center = 75  # Eb5 — bias toward octave-up correction

    pitches = np.array([n.pitch for n in notes])
    global_median = float(np.median(pitches))

    # Determine best global shift to bring median closest to vocal center
    best_shift = 0
    best_dist = abs(global_median - vocal_center)
    for shift in [-24, -12, 12, 24]:
        candidate = global_median + shift
        dist = abs(candidate - vocal_center)
        if dist < best_dist and vocal_target_low <= candidate <= vocal_target_high:
            best_dist = dist
            best_shift = shift

    # Apply sectional octave correction
    section_size = 30  # notes per section
    result = list(notes)

    if best_shift != 0:
        # Apply global shift first
        result = [
            Note(pitch=n.pitch + best_shift, onset=n.onset,
                 duration=n.duration, velocity=n.velocity)
            for n in result
        ]
        new_median = float(np.median([n.pitch for n in result]))
        logger.info(
            "Global octave adjust: shift=%+d (median %d -> %d)",
            best_shift, int(global_median), int(new_median),
        )
    else:
        # Even if global shift is 0, check sections for local anomalies
        # Some sections may be an octave off while global median is fine
        section_shifts = 0
        for start in range(0, len(result), section_size // 2):
            end = min(start + section_size, len(result))
            if end - start < 5:
                continue
            section_pitches = np.array([result[i].pitch for i in range(start, end)])
            section_median = float(np.median(section_pitches))

            sec_best_shift = 0
            sec_best_dist = abs(section_median - vocal_center)
            for shift in [-12, 12]:
                candidate = section_median + shift
                dist = abs(candidate - vocal_center)
                if dist < sec_best_dist and vocal_target_low <= candidate <= vocal_target_high:
                    sec_best_dist = dist
                    sec_best_shift = shift

            if sec_best_shift != 0:
                for i in range(start, end):
                    old_pitch = result[i].pitch
                    new_pitch = old_pitch + sec_best_shift
                    if vocal_target_low <= new_pitch <= vocal_target_high:
                        result[i] = Note(
                            pitch=new_pitch, onset=result[i].onset,
                            duration=result[i].duration, velocity=result[i].velocity,
                        )
                        section_shifts += 1

        if section_shifts > 0:
            new_median = float(np.median([n.pitch for n in result]))
            logger.info(
                "Sectional octave adjust: %d notes shifted (median %d -> %d)",
                section_shifts, int(global_median), int(new_median),
            )

    return result


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
    subdivisions: int = 2,
) -> List[Note]:
    """Snap note onsets to nearest beat subdivision.

    Uses librosa beat tracking to build a beat grid, then subdivides
    each beat interval (e.g. subdivisions=2 for 8th notes).
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
