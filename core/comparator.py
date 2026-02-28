"""Melody comparison metrics using mir_eval library."""

from typing import List
import numpy as np
import mir_eval.transcription
import mir_eval.onset
import mir_eval.util
from core.types import Note


def compare_melodies(ref_notes: List[Note], gen_notes: List[Note]) -> dict:
    """Compare two melodies and return comparison metrics.

    Args:
        ref_notes: Reference melody (List[Note])
        gen_notes: Generated/estimated melody (List[Note])

    Returns:
        Dictionary with metrics:
        - pitch_class_f1: Octave-agnostic F1 (PRIMARY METRIC)
        - chroma_similarity: 12-bin chroma cosine similarity
        - melody_f1_strict: Exact pitch F1 (50ms tolerance)
        - melody_f1_lenient: Loose pitch F1 (200ms tolerance)
        - onset_f1: Onset-only F1 (pitch ignored)
        - note_counts: {"ref": int, "gen": int}
    """

    # Handle empty cases
    if not ref_notes or not gen_notes:
        return {
            "pitch_class_f1": 0.0,
            "pitch_class_precision": 0.0,
            "pitch_class_recall": 0.0,
            "chroma_similarity": 0.0,
            "contour_similarity": 0.0,
            "pitch_class_match_rate": 0.0,
            "melody_f1_strict": 0.0,
            "melody_f1_lenient": 0.0,
            "onset_f1": 0.0,
            "note_counts": {"ref": len(ref_notes), "gen": len(gen_notes)},
        }

    # Convert notes to mir_eval format
    ref_intervals, ref_pitches_hz = _notes_to_mir_eval(ref_notes)
    gen_intervals, gen_pitches_hz = _notes_to_mir_eval(gen_notes)

    # Calculate pitch_class_f1 (PRIMARY METRIC - octave-agnostic)
    pitch_class_metrics = _calculate_pitch_class_f1(ref_notes, gen_notes)

    # Calculate chroma_similarity
    chroma_similarity = _calculate_chroma_similarity(ref_notes, gen_notes)

    # Calculate melody_f1_strict (50ms tolerance, exact pitch)
    melody_f1_strict = _calculate_melody_f1(
        ref_intervals,
        ref_pitches_hz,
        gen_intervals,
        gen_pitches_hz,
        onset_tolerance=0.05,
        pitch_tolerance=50.0,
    )

    # Calculate melody_f1_lenient (200ms tolerance, exact pitch)
    melody_f1_lenient = _calculate_melody_f1(
        ref_intervals,
        ref_pitches_hz,
        gen_intervals,
        gen_pitches_hz,
        onset_tolerance=0.2,
        pitch_tolerance=50.0,
    )

    # Calculate onset_f1 (pitch ignored)
    onset_f1 = _calculate_onset_f1(ref_notes, gen_notes)

    # Calculate melody contour similarity (direction-based: up/down/same)
    contour_similarity = _calculate_contour_similarity(ref_notes, gen_notes)

    # Calculate pitch class match rate (old contour metric, renamed)
    pitch_class_match_rate = _calculate_pitch_class_match_rate(ref_notes, gen_notes)

    # Calculate interval pattern similarity
    interval_similarity = _calculate_interval_similarity(ref_notes, gen_notes)

    return {
        "pitch_class_f1": pitch_class_metrics["f1"],
        "pitch_class_precision": pitch_class_metrics["precision"],
        "pitch_class_recall": pitch_class_metrics["recall"],
        "chroma_similarity": chroma_similarity,
        "contour_similarity": contour_similarity,
        "pitch_class_match_rate": pitch_class_match_rate,
        "interval_similarity": interval_similarity,
        "melody_f1_strict": melody_f1_strict,
        "melody_f1_lenient": melody_f1_lenient,
        "onset_f1": onset_f1,
        "note_counts": {"ref": len(ref_notes), "gen": len(gen_notes)},
    }


def _notes_to_mir_eval(notes: List[Note]) -> tuple:
    """Convert Note list to mir_eval format.

    Returns:
        (intervals, pitches_hz) where:
        - intervals: np.array of shape (n, 2) with [onset, offset]
        - pitches_hz: np.array of shape (n,) with frequencies in Hz
    """
    if not notes:
        return np.array([]).reshape(0, 2), np.array([])

    intervals = np.array([[n.onset, n.onset + n.duration] for n in notes])
    midi_pitches = np.array([n.pitch for n in notes])
    pitches_hz = mir_eval.util.midi_to_hz(midi_pitches)

    return intervals, pitches_hz


def _calculate_pitch_class_f1(ref_notes: List[Note], gen_notes: List[Note]) -> dict:
    """Calculate octave-agnostic precision, recall, and F1 score (PRIMARY METRIC).

    Normalizes all pitches to octave 5 (60 + (pitch % 12)) before comparison.
    Uses 200ms onset tolerance.

    Returns:
        dict with keys: precision, recall, f1
    """
    if not ref_notes or not gen_notes:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Normalize pitches to octave 5 (60-71)
    ref_intervals = np.array([[n.onset, n.onset + n.duration] for n in ref_notes])
    ref_pitches_normalized = np.array([60 + (n.pitch % 12) for n in ref_notes])
    ref_pitches_hz = mir_eval.util.midi_to_hz(ref_pitches_normalized)

    gen_intervals = np.array([[n.onset, n.onset + n.duration] for n in gen_notes])
    gen_pitches_normalized = np.array([60 + (n.pitch % 12) for n in gen_notes])
    gen_pitches_hz = mir_eval.util.midi_to_hz(gen_pitches_normalized)

    # Use 200ms onset tolerance, 50 cents pitch tolerance
    # offset_ratio=None disables note-offset matching (standard for melody evaluation)
    precision, recall, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals,
        ref_pitches_hz,
        gen_intervals,
        gen_pitches_hz,
        onset_tolerance=0.2,
        pitch_tolerance=50.0,
        offset_ratio=None,
    )

    return {"precision": float(precision), "recall": float(recall), "f1": float(f1)}


def _calculate_chroma_similarity(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Calculate 12-bin chroma cosine similarity.

    Creates duration-weighted chroma histograms and computes cosine similarity.
    """
    if not ref_notes or not gen_notes:
        return 0.0

    # Create chroma histograms (12 pitch classes)
    ref_chroma = np.zeros(12)
    for note in ref_notes:
        ref_chroma[note.pitch % 12] += note.duration

    gen_chroma = np.zeros(12)
    for note in gen_notes:
        gen_chroma[note.pitch % 12] += note.duration

    # Normalize
    ref_chroma = ref_chroma / (np.sum(ref_chroma) + 1e-10)
    gen_chroma = gen_chroma / (np.sum(gen_chroma) + 1e-10)

    # Cosine similarity
    similarity = np.dot(ref_chroma, gen_chroma) / (
        np.linalg.norm(ref_chroma) * np.linalg.norm(gen_chroma) + 1e-10
    )

    return float(np.clip(similarity, 0.0, 1.0))


def _calculate_melody_f1(
    ref_intervals: np.ndarray,
    ref_pitches_hz: np.ndarray,
    gen_intervals: np.ndarray,
    gen_pitches_hz: np.ndarray,
    onset_tolerance: float = 0.05,
    pitch_tolerance: float = 50.0,
) -> float:
    """Calculate melody F1 score with specified tolerances.

    Args:
        onset_tolerance: Onset tolerance in seconds
        pitch_tolerance: Pitch tolerance in cents
    """
    if len(ref_intervals) == 0 or len(gen_intervals) == 0:
        return 0.0

    precision, recall, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals,
        ref_pitches_hz,
        gen_intervals,
        gen_pitches_hz,
        onset_tolerance=onset_tolerance,
        pitch_tolerance=pitch_tolerance,
        offset_ratio=None,
    )

    return float(f1)


def _calculate_pitch_class_match_rate(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Calculate pitch class match rate via time-quantized pitch class comparison.

    Converts both melodies to dense pitch class contours (50ms steps), then
    computes fraction of time steps where pitch classes match. This is the
    original contour_similarity metric, renamed for clarity.
    """
    if not ref_notes or not gen_notes:
        return 0.0

    step = 0.05  # 50ms time steps
    t_start = min(ref_notes[0].onset, gen_notes[0].onset)
    t_end = max(ref_notes[-1].onset + ref_notes[-1].duration,
                gen_notes[-1].onset + gen_notes[-1].duration)

    if t_end <= t_start:
        return 0.0

    times = np.arange(t_start, t_end, step)
    if len(times) < 10:
        return 0.0

    def _to_contour(notes: List[Note]) -> np.ndarray:
        """Convert notes to pitch contour (pitch class at each time step)."""
        contour = np.full(len(times), np.nan)
        for n in notes:
            mask = (times >= n.onset) & (times < n.onset + n.duration)
            contour[mask] = n.pitch % 12
        return contour

    ref_contour = _to_contour(ref_notes)
    gen_contour = _to_contour(gen_notes)

    # Only compare time steps where both have notes
    valid = ~np.isnan(ref_contour) & ~np.isnan(gen_contour)
    if np.sum(valid) < 10:
        return 0.0

    rc = ref_contour[valid]
    gc = gen_contour[valid]

    # Compute fraction of time steps with matching pitch class
    match_rate = float(np.mean(rc == gc))
    return match_rate


def _calculate_contour_similarity(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Calculate melodic direction similarity.

    Measures whether both melodies go up/down/same at the same times.
    Uses full MIDI pitch (not pitch class) at 50ms time steps.
    Computes sign(pitch[t] - pitch[t-1]) for direction, then compares.
    """
    if not ref_notes or not gen_notes:
        return 0.0

    step = 0.05  # 50ms
    t_start = min(ref_notes[0].onset, gen_notes[0].onset)
    t_end = max(ref_notes[-1].onset + ref_notes[-1].duration,
                gen_notes[-1].onset + gen_notes[-1].duration)
    if t_end <= t_start:
        return 0.0

    times = np.arange(t_start, t_end, step)
    if len(times) < 10:
        return 0.0

    def _to_pitch_contour(notes: List[Note]) -> np.ndarray:
        """Convert notes to MIDI pitch contour at each time step."""
        contour = np.full(len(times), np.nan)
        for n in notes:
            mask = (times >= n.onset) & (times < n.onset + n.duration)
            contour[mask] = n.pitch  # Full MIDI pitch, NOT % 12
        return contour

    ref_contour = _to_pitch_contour(ref_notes)
    gen_contour = _to_pitch_contour(gen_notes)

    def _to_direction(contour: np.ndarray) -> np.ndarray:
        """Compute direction at each step: +1 up, -1 down, 0 same."""
        direction = np.full(len(contour), np.nan)
        prev_valid = np.nan
        for i in range(len(contour)):
            if np.isnan(contour[i]):
                continue
            if not np.isnan(prev_valid):
                diff = contour[i] - prev_valid
                direction[i] = np.sign(diff)
            prev_valid = contour[i]
        return direction

    ref_dir = _to_direction(ref_contour)
    gen_dir = _to_direction(gen_contour)

    # Compare where both have valid directions
    valid = ~np.isnan(ref_dir) & ~np.isnan(gen_dir)
    if np.sum(valid) < 10:
        return 0.0

    return float(np.mean(ref_dir[valid] == gen_dir[valid]))


def _calculate_interval_similarity(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Calculate melodic interval pattern similarity.

    Compares the sequence of pitch intervals (semitone changes between
    consecutive notes) using cosine similarity of interval histograms.
    This captures whether the melody moves by the same intervals regardless
    of absolute pitch or timing.
    """
    if len(ref_notes) < 2 or len(gen_notes) < 2:
        return 0.0

    def _interval_histogram(notes: List[Note]) -> np.ndarray:
        """Build histogram of pitch class intervals (-6 to +6 semitones mod 12)."""
        hist = np.zeros(13)  # indices 0-12 represent intervals -6 to +6
        for i in range(1, len(notes)):
            interval = (notes[i].pitch % 12) - (notes[i - 1].pitch % 12)
            # Wrap to -6..+6
            interval = ((interval + 6) % 12) - 6
            hist[interval + 6] += 1
        return hist

    ref_hist = _interval_histogram(ref_notes)
    gen_hist = _interval_histogram(gen_notes)

    # Normalize
    ref_norm = ref_hist / (np.sum(ref_hist) + 1e-10)
    gen_norm = gen_hist / (np.sum(gen_hist) + 1e-10)

    # Cosine similarity
    sim = np.dot(ref_norm, gen_norm) / (
        np.linalg.norm(ref_norm) * np.linalg.norm(gen_norm) + 1e-10
    )
    return float(np.clip(sim, 0.0, 1.0))


def _calculate_onset_f1(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Calculate onset-only F1 score (pitch ignored).

    Uses 100ms window for onset matching.
    """
    if not ref_notes or not gen_notes:
        return 0.0

    ref_onsets = np.array([n.onset for n in ref_notes])
    gen_onsets = np.array([n.onset for n in gen_notes])

    f1, precision, recall = mir_eval.onset.f_measure(ref_onsets, gen_onsets, window=0.1)

    return float(f1)
