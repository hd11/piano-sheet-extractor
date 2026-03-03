"""Melody comparison metrics.

Compares generated and reference melodies using tolerance-based matching only.
NO transformations (time offset, octave correction, etc.) are applied.
Primary metric: melody_f1_strict (exact pitch, 50ms onset tolerance).
"""

from typing import List

import mir_eval.onset
import mir_eval.transcription
import mir_eval.util
import numpy as np

from .types import Note


def compare_melodies(ref_notes: List[Note], gen_notes: List[Note]) -> dict:
    """Compare two melodies and return evaluation metrics.

    Args:
        ref_notes: Reference melody notes.
        gen_notes: Generated/extracted melody notes.

    Returns:
        Dictionary with metrics:
        - melody_f1_strict: Exact pitch F1, 50ms onset (PRIMARY)
        - melody_f1_lenient: Exact pitch F1, 200ms onset
        - pitch_class_f1: Octave-agnostic F1, 200ms onset
        - onset_f1: Onset-only F1, 100ms window
        - chroma_similarity: 12-bin chroma cosine similarity
        - contour_similarity: Melodic direction match rate
        - note_count_ratio: gen_count / ref_count
        - note_counts: {"ref": int, "gen": int}
    """
    empty = {
        "melody_f1_strict": 0.0,
        "melody_f1_lenient": 0.0,
        "pitch_class_f1": 0.0,
        "pitch_class_precision": 0.0,
        "pitch_class_recall": 0.0,
        "onset_f1": 0.0,
        "chroma_similarity": 0.0,
        "contour_similarity": 0.0,
        "note_count_ratio": 0.0,
        "note_counts": {"ref": len(ref_notes), "gen": len(gen_notes)},
    }

    if not ref_notes or not gen_notes:
        return empty

    ref_intervals, ref_hz = _notes_to_mir_eval(ref_notes)
    gen_intervals, gen_hz = _notes_to_mir_eval(gen_notes)

    # melody_f1_strict: exact pitch, 50ms onset
    melody_f1_strict = _transcription_f1(
        ref_intervals, ref_hz, gen_intervals, gen_hz,
        onset_tolerance=0.05, pitch_tolerance=50.0,
    )

    # melody_f1_lenient: exact pitch, 200ms onset
    melody_f1_lenient = _transcription_f1(
        ref_intervals, ref_hz, gen_intervals, gen_hz,
        onset_tolerance=0.2, pitch_tolerance=50.0,
    )

    # pitch_class_f1: octave-agnostic, 200ms onset
    pc_metrics = _pitch_class_f1(ref_notes, gen_notes)

    # onset_f1: onset only, 100ms
    onset_f1 = _onset_f1(ref_notes, gen_notes)

    # chroma_similarity
    chroma_sim = _chroma_similarity(ref_notes, gen_notes)

    # contour_similarity
    contour_sim = _contour_similarity(ref_notes, gen_notes)

    # note_count_ratio
    ratio = len(gen_notes) / len(ref_notes) if ref_notes else 0.0

    return {
        "melody_f1_strict": melody_f1_strict,
        "melody_f1_lenient": melody_f1_lenient,
        "pitch_class_f1": pc_metrics["f1"],
        "pitch_class_precision": pc_metrics["precision"],
        "pitch_class_recall": pc_metrics["recall"],
        "onset_f1": onset_f1,
        "chroma_similarity": chroma_sim,
        "contour_similarity": contour_sim,
        "note_count_ratio": round(ratio, 3),
        "note_counts": {"ref": len(ref_notes), "gen": len(gen_notes)},
    }


def _notes_to_mir_eval(notes: List[Note]):
    """Convert Note list to mir_eval format (intervals, pitches_hz)."""
    intervals = np.array([[n.onset, n.onset + n.duration] for n in notes])
    midi = np.array([n.pitch for n in notes])
    hz = mir_eval.util.midi_to_hz(midi)
    return intervals, hz


def _transcription_f1(
    ref_intervals, ref_hz, gen_intervals, gen_hz,
    onset_tolerance=0.05, pitch_tolerance=50.0,
) -> float:
    """Calculate transcription F1 with given tolerances."""
    if len(ref_intervals) == 0 or len(gen_intervals) == 0:
        return 0.0
    _, _, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals, ref_hz,
        gen_intervals, gen_hz,
        onset_tolerance=onset_tolerance,
        pitch_tolerance=pitch_tolerance,
        offset_ratio=None,
    )
    return float(f1)


def _pitch_class_f1(ref_notes: List[Note], gen_notes: List[Note]) -> dict:
    """Octave-agnostic F1: normalize all pitches to octave 5 before matching."""
    ref_intervals = np.array([[n.onset, n.onset + n.duration] for n in ref_notes])
    ref_pc = np.array([60 + (n.pitch % 12) for n in ref_notes])
    ref_hz = mir_eval.util.midi_to_hz(ref_pc)

    gen_intervals = np.array([[n.onset, n.onset + n.duration] for n in gen_notes])
    gen_pc = np.array([60 + (n.pitch % 12) for n in gen_notes])
    gen_hz = mir_eval.util.midi_to_hz(gen_pc)

    precision, recall, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals, ref_hz,
        gen_intervals, gen_hz,
        onset_tolerance=0.2,
        pitch_tolerance=50.0,
        offset_ratio=None,
    )
    return {"precision": float(precision), "recall": float(recall), "f1": float(f1)}


def _onset_f1(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Onset-only F1 (pitch ignored), 100ms window."""
    ref_onsets = np.array([n.onset for n in ref_notes])
    gen_onsets = np.array([n.onset for n in gen_notes])
    f1, _, _ = mir_eval.onset.f_measure(ref_onsets, gen_onsets, window=0.1)
    return float(f1)


def _chroma_similarity(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Duration-weighted 12-bin chroma cosine similarity."""
    ref_chroma = np.zeros(12)
    for n in ref_notes:
        ref_chroma[n.pitch % 12] += n.duration

    gen_chroma = np.zeros(12)
    for n in gen_notes:
        gen_chroma[n.pitch % 12] += n.duration

    ref_chroma /= np.sum(ref_chroma) + 1e-10
    gen_chroma /= np.sum(gen_chroma) + 1e-10

    sim = np.dot(ref_chroma, gen_chroma) / (
        np.linalg.norm(ref_chroma) * np.linalg.norm(gen_chroma) + 1e-10
    )
    return float(np.clip(sim, 0.0, 1.0))


def _contour_similarity(ref_notes: List[Note], gen_notes: List[Note]) -> float:
    """Melodic direction similarity at 50ms time steps."""
    step = 0.05
    t_start = min(ref_notes[0].onset, gen_notes[0].onset)
    t_end = max(
        ref_notes[-1].onset + ref_notes[-1].duration,
        gen_notes[-1].onset + gen_notes[-1].duration,
    )
    if t_end <= t_start:
        return 0.0

    times = np.arange(t_start, t_end, step)
    if len(times) < 10:
        return 0.0

    def _pitch_contour(notes):
        contour = np.full(len(times), np.nan)
        for n in notes:
            mask = (times >= n.onset) & (times < n.onset + n.duration)
            contour[mask] = n.pitch
        return contour

    def _direction(contour):
        direction = np.full(len(contour), np.nan)
        prev = np.nan
        for i in range(len(contour)):
            if np.isnan(contour[i]):
                continue
            if not np.isnan(prev):
                direction[i] = np.sign(contour[i] - prev)
            prev = contour[i]
        return direction

    ref_dir = _direction(_pitch_contour(ref_notes))
    gen_dir = _direction(_pitch_contour(gen_notes))

    valid = ~np.isnan(ref_dir) & ~np.isnan(gen_dir)
    if np.sum(valid) < 10:
        return 0.0

    return float(np.mean(ref_dir[valid] == gen_dir[valid]))
