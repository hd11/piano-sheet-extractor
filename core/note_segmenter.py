"""Convert F0 contour to discrete Note list.

Groups stable pitch regions from the continuous F0 contour into
individual Note objects with MIDI pitch, onset, and duration.
"""

import logging
from typing import List

import librosa
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


def segment_notes_onset(
    contour: F0Contour,
    audio: np.ndarray,
    sr: int,
    min_note_duration: float = 0.05,
    min_voiced_ratio: float = 0.25,
    onset_delta: float = 0.07,
) -> List[Note]:
    """Syllable-onset based note segmentation.

    Instead of grouping consecutive same-pitch F0 frames, this function:
    1. Detects vocal syllable onsets from the audio signal
    2. For each onset interval, computes the median voiced MIDI pitch
    3. Skips intervals with insufficient voiced frames (rests)

    This produces notes aligned to actual vocal articulations rather than
    F0 pitch changes, which tends to match sheet music note boundaries better.

    Args:
        contour: F0Contour from pitch extractor.
        audio: Mono audio array (vocals) at sample rate sr.
        sr: Sample rate of audio.
        min_note_duration: Minimum note duration in seconds.
        min_voiced_ratio: Minimum fraction of voiced F0 frames in interval.
        onset_delta: Onset detection sensitivity (higher = fewer onsets).

    Returns:
        List of Note objects aligned to vocal onsets.
    """
    freqs = contour.frequencies.copy()
    times = contour.times

    if len(freqs) == 0:
        return []

    step = float(times[1] - times[0]) if len(times) > 1 else 0.01
    total_dur = float(times[-1]) + step

    # Hz -> MIDI (0 for unvoiced)
    voiced = freqs > 0
    midi = np.zeros(len(freqs), dtype=int)
    midi[voiced] = np.round(12.0 * np.log2(freqs[voiced] / 440.0) + 69.0).astype(int)

    # Detect vocal onsets from audio amplitude envelope
    onset_frames = librosa.onset.onset_detect(
        y=audio,
        sr=sr,
        delta=onset_delta,
        backtrack=True,  # snap to nearest local minimum before peak
        units="frames",
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # Add implicit start and end boundaries
    boundaries = np.concatenate([[0.0], onset_times, [total_dur]])
    boundaries = np.unique(boundaries)

    logger.info(
        "Onset segmentation: %d onsets detected (delta=%.2f)",
        len(onset_times), onset_delta,
    )

    notes: List[Note] = []
    for i in range(len(boundaries) - 1):
        t_start = float(boundaries[i])
        t_end = float(boundaries[i + 1])
        duration = t_end - t_start

        if duration < min_note_duration:
            continue

        # F0 frames in this interval
        frame_start = int(t_start / step)
        frame_end = int(t_end / step)
        frame_end = min(frame_end, len(midi))

        if frame_start >= frame_end:
            continue

        segment_midi = midi[frame_start:frame_end]
        voiced_midi = segment_midi[segment_midi > 0]

        if len(voiced_midi) < len(segment_midi) * min_voiced_ratio:
            continue  # rest

        # Median pitch of voiced frames
        pitch = int(np.round(np.median(voiced_midi)))

        if 21 <= pitch <= 108:
            notes.append(Note(
                pitch=pitch,
                onset=round(t_start, 4),
                duration=round(duration, 4),
            ))

    logger.info(
        "Onset segmented %d notes from %d intervals (%.1fs)",
        len(notes), len(boundaries) - 1, total_dur,
    )

    if notes:
        pitches = [n.pitch for n in notes]
        logger.info(
            "Pitch range: MIDI %d-%d, median=%d",
            min(pitches), max(pitches), int(np.median(pitches)),
        )

    return notes

def segment_notes_hybrid(
    contour: F0Contour,
    audio: np.ndarray,
    sr: int,
    min_note_duration: float = 0.05,
    max_gap_frames: int = 5,
    onset_delta: float = 0.07,
    min_voiced_ratio: float = 0.25,
) -> List[Note]:
    """Hybrid segmentation: FCPE pitch accuracy + onset syllable boundaries.

    Combines the best of both approaches:
    1. Run standard segment_notes() for pitch-accurate note detection
    2. Detect vocal onset boundaries (syllable starts)
    3. Within each onset interval, merge notes into one using dominant pitch
    4. For intervals with no FCPE notes, fall back to raw F0 median (gap fill)

    Args:
        contour: F0Contour from pitch extractor.
        audio: Mono audio array (vocals) at sample rate sr.
        sr: Sample rate of audio.
        min_note_duration: Minimum note duration for initial segmentation.
        max_gap_frames: Gap bridging for initial segmentation.
        onset_delta: Onset detection sensitivity (higher = fewer onsets).

    Returns:
        List of Note objects with syllable-level density and FCPE pitch accuracy.
    """
    # Step 1: Get pitch-accurate notes from standard segmentation
    detailed_notes = segment_notes(
        contour,
        min_note_duration=min_note_duration,
        max_gap_frames=max_gap_frames,
    )

    # Step 2: Prepare raw F0 MIDI for gap fallback
    freqs = contour.frequencies.copy()
    times = contour.times
    step = float(times[1] - times[0]) if len(times) > 1 else 0.01
    voiced_mask = freqs > 0
    midi_raw = np.zeros(len(freqs), dtype=int)
    midi_raw[voiced_mask] = np.round(
        12.0 * np.log2(freqs[voiced_mask] / 440.0) + 69.0
    ).astype(int)

    # Step 3: Detect vocal syllable onsets
    onset_frames = librosa.onset.onset_detect(
        y=audio,
        sr=sr,
        delta=onset_delta,
        backtrack=True,
        units="frames",
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    total_dur = float(times[-1]) + step if len(times) > 0 else 0.0
    boundaries = np.concatenate([[0.0], onset_times, [total_dur]])
    boundaries = np.unique(boundaries)

    logger.info(
        "Hybrid segmentation: %d detailed notes, %d onset boundaries (delta=%.2f)",
        len(detailed_notes), len(onset_times), onset_delta,
    )

    # Step 4: Assign each note to its onset interval, merge within interval
    notes: List[Note] = []
    note_idx = 0
    fallback_count = 0

    for i in range(len(boundaries) - 1):
        t_start = float(boundaries[i])
        t_end = float(boundaries[i + 1])
        interval_dur = t_end - t_start

        if interval_dur < min_note_duration:
            continue

        # Collect notes whose onset falls in this interval
        interval_notes: List[Note] = []
        while note_idx < len(detailed_notes) and detailed_notes[note_idx].onset < t_end:
            if detailed_notes[note_idx].onset >= t_start:
                interval_notes.append(detailed_notes[note_idx])
            note_idx += 1

        if interval_notes:
            # Normal path: merge FCPE notes using dominant pitch
            pitch_dur: dict = {}
            for n in interval_notes:
                pitch_dur[n.pitch] = pitch_dur.get(n.pitch, 0.0) + n.duration
            dominant_pitch = max(pitch_dur, key=pitch_dur.get)

            first_onset = interval_notes[0].onset
            last_end = max(n.onset + n.duration for n in interval_notes)
            duration = last_end - first_onset

            if duration >= min_note_duration and 21 <= dominant_pitch <= 108:
                notes.append(Note(
                    pitch=dominant_pitch,
                    onset=round(first_onset, 4),
                    duration=round(duration, 4),
                ))
        else:
            # Gap fallback: check raw F0 contour for voiced frames
            frame_start = int(t_start / step)
            frame_end = min(int(t_end / step), len(midi_raw))
            if frame_start >= frame_end:
                continue

            segment_midi = midi_raw[frame_start:frame_end]
            voiced_midi = segment_midi[segment_midi > 0]

            if len(voiced_midi) >= len(segment_midi) * min_voiced_ratio:
                pitch = int(np.round(np.median(voiced_midi)))
                if 21 <= pitch <= 108:
                    notes.append(Note(
                        pitch=pitch,
                        onset=round(t_start, 4),
                        duration=round(interval_dur, 4),
                    ))
                    fallback_count += 1

    if fallback_count > 0:
        logger.info("Hybrid gap fill: %d notes from raw F0 fallback", fallback_count)

    logger.info(
        "Hybrid: %d -> %d notes (%.0f%% reduction)",
        len(detailed_notes), len(notes),
        (1 - len(notes) / max(len(detailed_notes), 1)) * 100,
    )

    if notes:
        pitches = [n.pitch for n in notes]
        logger.info(
            "Pitch range: MIDI %d-%d, median=%d",
            min(pitches), max(pitches), int(np.median(pitches)),
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
