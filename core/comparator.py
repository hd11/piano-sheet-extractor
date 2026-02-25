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
            "chroma_similarity": 0.0,
            "melody_f1_strict": 0.0,
            "melody_f1_lenient": 0.0,
            "onset_f1": 0.0,
            "note_counts": {"ref": len(ref_notes), "gen": len(gen_notes)},
        }

    # Convert notes to mir_eval format
    ref_intervals, ref_pitches_hz = _notes_to_mir_eval(ref_notes)
    gen_intervals, gen_pitches_hz = _notes_to_mir_eval(gen_notes)

    # Calculate pitch_class_f1 (PRIMARY METRIC - octave-agnostic)
    pitch_class_f1 = _calculate_pitch_class_f1(ref_notes, gen_notes)

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

    return {
        "pitch_class_f1": pitch_class_f1,
        "chroma_similarity": chroma_similarity,
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


def _calculate_pitch_class_f1(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Calculate octave-agnostic F1 score (PRIMARY METRIC).

    Normalizes all pitches to octave 5 (60 + (pitch % 12)) before comparison.
    Uses 200ms onset tolerance.
    """
    if not ref_notes or not gen_notes:
        return 0.0

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

    return float(f1)


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
