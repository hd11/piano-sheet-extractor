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
VOCAL_RANGE_HIGH = 96  # C7


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
    notes = _merge_same_pitch(notes, audio=audio, sr=sr)
    notes = _global_octave_adjust(notes)
    notes = _self_octave_correction(notes)
    notes = _clip_vocal_range(notes)
    notes = _diatonic_gate(notes)

    # Beat-aligned onset snapping (self-contained, uses audio only)
    # Adaptive subdivisions based on BPM
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


def _consolidate_short_notes(
    notes: List[Note],
    min_dur: float = 0.12,
) -> List[Note]:
    """Merge very short same-pitch notes into adjacent neighbors.

    F0 extractors produce pitch jitter that causes the note segmenter
    to fragment single notes into many tiny pieces. This pass absorbs
    notes shorter than min_dur into same-pitch temporal neighbors.
    Different-pitch short notes are kept as-is to preserve pitch content.

    Self-contained: uses only note list, no reference data.
    """
    if len(notes) < 3:
        return notes

    merged = list(notes)
    changed = True

    while changed:
        changed = False
        new_list = []
        i = 0
        while i < len(merged):
            n = merged[i]
            if n.duration >= min_dur:
                new_list.append(n)
                i += 1
                continue

            # Short note — merge only with same-pitch neighbor
            prev = new_list[-1] if new_list else None
            nxt = merged[i + 1] if i + 1 < len(merged) else None

            if prev and prev.pitch == n.pitch:
                end = n.onset + n.duration
                new_list[-1] = Note(
                    pitch=prev.pitch, onset=prev.onset,
                    duration=round(end - prev.onset, 4), velocity=prev.velocity,
                )
                changed = True
                i += 1
                continue

            if nxt and nxt.pitch == n.pitch:
                new_end = nxt.onset + nxt.duration
                new_list.append(Note(
                    pitch=n.pitch, onset=n.onset,
                    duration=round(new_end - n.onset, 4), velocity=n.velocity,
                ))
                changed = True
                i += 2
                continue

            # Different pitch — keep as-is
            new_list.append(n)
            i += 1

        merged = new_list

    if len(merged) < len(notes):
        logger.info(
            "Short note consolidation: %d -> %d notes (min_dur=%.0fms)",
            len(notes), len(merged), min_dur * 1000,
        )
    return merged


def _merge_same_pitch(
    notes: List[Note],
    max_gap: float = 0.15,
    audio: Optional[np.ndarray] = None,
    sr: Optional[int] = None,
) -> List[Note]:
    """Merge consecutive notes with the same pitch and small gap.

    If audio is provided, detects re-attacks using amplitude envelope
    analysis. Re-attacked notes are NOT merged even if the gap is small.

    Args:
        notes: Input notes sorted by onset.
        max_gap: Maximum gap in seconds to merge across.
        audio: Source audio for re-attack detection (self-contained).
        sr: Sample rate of audio.

    Returns:
        Notes with same-pitch consecutive notes merged (except re-attacks).
    """
    if len(notes) < 2:
        return notes

    merged = [notes[0]]
    reattacks = 0
    for i in range(1, len(notes)):
        prev = merged[-1]
        curr = notes[i]
        gap = curr.onset - (prev.onset + prev.duration)
        if curr.pitch == prev.pitch and gap < max_gap:
            # Check for re-attack using amplitude envelope
            if (audio is not None and sr is not None
                    and gap >= 0.02
                    and _detect_reattack(prev, curr, audio, sr)):
                merged.append(curr)
                reattacks += 1
            else:
                new_dur = (curr.onset + curr.duration) - prev.onset
                merged[-1] = Note(
                    pitch=prev.pitch,
                    onset=prev.onset,
                    duration=new_dur,
                    velocity=prev.velocity,
                )
        else:
            merged.append(curr)

    merges = len(notes) - len(merged)
    if merges > 0 or reattacks > 0:
        logger.info(
            "Same-pitch merge: %d -> %d notes (%d merged, %d re-attacks kept)",
            len(notes),
            len(merged),
            merges,
            reattacks,
        )

    return merged


def _detect_reattack(
    prev: Note,
    curr: Note,
    audio: np.ndarray,
    sr: int,
    dip_threshold: float = 0.4,
) -> bool:
    """Detect if transition between two same-pitch notes is a re-attack.

    Analyzes the amplitude envelope in the gap between notes.
    A re-attack is indicated by a significant amplitude dip in the gap
    compared to the surrounding note amplitudes.

    Self-contained: uses only note timing and source audio.

    Args:
        prev: Previous note.
        curr: Current note (same pitch as prev).
        audio: Audio signal.
        sr: Sample rate.
        dip_threshold: If gap RMS / surrounding RMS < this, it's a re-attack.

    Returns:
        True if a re-attack is detected.
    """
    prev_end_sample = int((prev.onset + prev.duration) * sr)
    curr_start_sample = int(curr.onset * sr)

    if curr_start_sample <= prev_end_sample or curr_start_sample > len(audio):
        return False

    # Context windows: 30ms from end of prev note, 30ms from start of curr note
    margin_samples = int(0.03 * sr)

    prev_region_start = max(0, prev_end_sample - margin_samples)
    prev_region = audio[prev_region_start:prev_end_sample]

    gap_region = audio[prev_end_sample:min(curr_start_sample, len(audio))]

    curr_region_end = min(curr_start_sample + margin_samples, len(audio))
    curr_region = audio[curr_start_sample:curr_region_end]

    if len(prev_region) < 2 or len(gap_region) < 2 or len(curr_region) < 2:
        return False

    prev_rms = np.sqrt(np.mean(prev_region ** 2)) + 1e-10
    gap_rms = np.sqrt(np.mean(gap_region ** 2)) + 1e-10
    curr_rms = np.sqrt(np.mean(curr_region ** 2)) + 1e-10

    surrounding_rms = max(prev_rms, curr_rms)
    dip_ratio = gap_rms / surrounding_rms

    return dip_ratio < dip_threshold


def _harmonic_correction(
    notes: List[Note],
    context_window: int = 5,
    max_duration: float = 0.3,
) -> List[Note]:
    """Correct CREPE harmonic confusion (4th/5th lock).

    CREPE sometimes locks onto the 2nd or 3rd harmonic partial instead
    of the fundamental, causing pitch errors of exactly +5st (perfect 4th),
    +7st (perfect 5th), -5st, or -7st. This function detects such jumps
    by comparing each note to its surrounding context and reverses
    the harmonic shift if it brings the note closer to the local median.

    Only short notes (< max_duration) are corrected to avoid changing
    intentional melodic leaps.

    Self-contained: uses only extracted notes, no reference data.

    Args:
        notes: Input notes.
        context_window: Half-window for local median computation.
        max_duration: Only correct notes shorter than this (seconds).

    Returns:
        Notes with harmonic errors corrected.
    """
    if len(notes) < 5:
        return notes

    harmonic_intervals = [5, 7, -5, -7]
    pitches = np.array([n.pitch for n in notes])
    corrected = pitches.copy()
    corrections = 0

    for i in range(len(notes)):
        if notes[i].duration >= max_duration:
            continue

        # Compute local median excluding current note
        lo = max(0, i - context_window)
        hi = min(len(notes), i + context_window + 1)
        context_pitches = np.concatenate([pitches[lo:i], pitches[i+1:hi]])
        if len(context_pitches) < 3:
            continue
        local_median = float(np.median(context_pitches))

        current_dist = abs(pitches[i] - local_median)
        if current_dist < 4:
            # Already close to context, skip
            continue

        # Try reversing each harmonic interval
        best_pitch = pitches[i]
        best_dist = current_dist
        for interval in harmonic_intervals:
            candidate = pitches[i] - interval  # reverse the suspected shift
            dist = abs(candidate - local_median)
            if dist < best_dist and VOCAL_RANGE_LOW <= candidate <= VOCAL_RANGE_HIGH:
                best_dist = dist
                best_pitch = candidate

        if best_pitch != pitches[i]:
            corrected[i] = best_pitch
            corrections += 1

    if corrections > 0:
        logger.info(
            "Harmonic correction: %d/%d notes corrected (4th/5th lock)",
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


def _cqt_octave_verify(
    notes: List[Note],
    audio: np.ndarray,
    sr: int,
) -> List[Note]:
    """Verify/correct octave using CQT spectral energy.

    CREPE's chroma (note name) is generally accurate but octave register
    is often wrong due to subharmonic locking. CQT gives correct pitch
    register because it measures actual spectral energy at each frequency.

    For each note, compute CQT energy at the current octave and ±1 octave,
    then pick the octave with the highest energy. Only the octave changes;
    the chroma (note name) is preserved.

    Self-contained: uses only extracted notes and source audio.

    Args:
        notes: Input notes (after global octave adjust).
        audio: Vocal audio signal.
        sr: Sample rate.

    Returns:
        Notes with octave verified/corrected by CQT energy.
    """
    if len(notes) < 5 or len(audio) == 0:
        return notes

    # Compute CQT: 6 octaves from C2 (MIDI 36) to B7 (MIDI 107)
    # This covers the full vocal range
    n_bins = 72  # 6 octaves * 12 bins/octave
    fmin = librosa.midi_to_hz(36)  # C2
    C = np.abs(librosa.cqt(
        y=audio.astype(np.float32),
        sr=sr,
        hop_length=512,
        fmin=fmin,
        n_bins=n_bins,
        bins_per_octave=12,
    ))

    cqt_times = librosa.frames_to_time(np.arange(C.shape[1]), sr=sr, hop_length=512)
    corrections = 0
    result = []

    for n in notes:
        # Find CQT frames for this note's time span
        t_start = n.onset
        t_end = n.onset + n.duration
        frame_start = np.searchsorted(cqt_times, t_start)
        frame_end = np.searchsorted(cqt_times, t_end)
        if frame_end <= frame_start:
            frame_end = frame_start + 1
        frame_end = min(frame_end, C.shape[1])
        frame_start = min(frame_start, C.shape[1] - 1)

        # Get average CQT energy for this time span
        segment = C[:, frame_start:frame_end]
        if segment.size == 0:
            result.append(n)
            continue
        avg_energy = segment.mean(axis=1)

        # Current pitch -> CQT bin index
        current_midi = n.pitch
        chroma = current_midi % 12
        base_midi = 36  # CQT starts at MIDI 36

        # Check energy at current octave and ±1 octave (same chroma)
        best_midi = current_midi
        best_energy = -1.0

        for shift in [-12, 0, 12]:
            candidate_midi = current_midi + shift
            bin_idx = candidate_midi - base_midi
            if 0 <= bin_idx < n_bins and VOCAL_RANGE_LOW <= candidate_midi <= VOCAL_RANGE_HIGH:
                energy = float(avg_energy[bin_idx])
                if energy > best_energy:
                    best_energy = energy
                    best_midi = candidate_midi

        if best_midi != current_midi:
            corrections += 1

        result.append(Note(
            pitch=best_midi,
            onset=n.onset,
            duration=n.duration,
            velocity=n.velocity,
        ))

    if corrections > 0:
        logger.info(
            "CQT octave verify: %d/%d notes corrected",
            corrections,
            len(notes),
        )

    return result


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


def _diatonic_gate(
    notes: List[Note],
    max_chromatic_duration: float = 0.15,
) -> List[Note]:
    """Remove short out-of-key notes (likely CREPE artifacts).

    Estimates key from note chroma histogram, then removes notes that
    are both chromatic (out-of-key) and short. Longer chromatic notes
    are kept as they may be intentional accidentals.

    Self-contained: uses only extracted notes, no reference data.

    Args:
        notes: Input notes.
        max_chromatic_duration: Max duration (seconds) for a chromatic note
            to be considered an artifact and removed.

    Returns:
        Filtered notes with short chromatic artifacts removed.
    """
    if len(notes) < 10:
        return notes

    # Estimate key from chroma histogram (weighted by duration)
    chroma_weight = np.zeros(12)
    for n in notes:
        chroma_weight[n.pitch % 12] += n.duration

    # Major scale template matching (Krumhansl-Kessler simplified)
    major_intervals = [0, 2, 4, 5, 7, 9, 11]
    best_root = 0
    best_score = -1.0
    for root in range(12):
        score = sum(chroma_weight[(root + iv) % 12] for iv in major_intervals)
        if score > best_score:
            best_score = score
            best_root = root

    key_chromas = {(best_root + iv) % 12 for iv in major_intervals}
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    logger.info("Diatonic gate: estimated key = %s major", note_names[best_root])

    filtered = []
    removed = 0
    for n in notes:
        if n.pitch % 12 not in key_chromas and n.duration < max_chromatic_duration:
            removed += 1
            continue
        filtered.append(n)

    if removed > 0:
        logger.info("Diatonic gate: %d/%d short chromatic notes removed", removed, len(notes))

    return filtered


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
