"""
Shared comparison utilities for MusicXML and MIDI comparators.

Provides mir_eval-based metrics, chroma similarity, and composite scoring.
Both musicxml_comparator.py and midi_comparator.py use these functions.

IMPORTANT: mir_eval pitches are in Hz, not MIDI numbers.
Always convert with mir_eval.util.midi_to_hz() before calling mir_eval functions.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Try importing mir_eval; graceful fallback if unavailable
try:
    import mir_eval
    import mir_eval.transcription
    import mir_eval.util

    HAS_MIR_EVAL = True
except ImportError:
    HAS_MIR_EVAL = False
    logger.warning("mir_eval not installed. Composite metrics will be unavailable.")

# Try importing dtw; graceful fallback
try:
    from dtw import dtw as dtw_func

    HAS_DTW = True
except ImportError:
    HAS_DTW = False
    logger.warning("dtw-python not installed. DTW alignment will be unavailable.")


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class NoteEvent:
    """Universal note representation for comparison (seconds-based)."""

    pitch: int  # MIDI pitch (0-127)
    onset: float  # Start time in seconds
    offset: float  # End time in seconds

    @property
    def duration(self) -> float:
        return self.offset - self.onset


# ============================================================================
# Conversion Helpers
# ============================================================================


def notes_to_intervals_and_pitches(
    notes: List[NoteEvent],
) -> tuple:
    """
    Convert NoteEvent list to mir_eval format.

    Returns:
        (intervals, pitches_hz) where:
        - intervals: np.ndarray shape (N, 2) of [onset, offset] in seconds
        - pitches_hz: np.ndarray shape (N,) of pitches in Hz

    IMPORTANT: mir_eval requires Hz pitches, not MIDI numbers.
    """
    if not notes:
        return np.zeros((0, 2)), np.zeros(0)

    intervals = np.array([[n.onset, n.offset] for n in notes])
    pitches_midi = np.array([n.pitch for n in notes])

    if HAS_MIR_EVAL:
        pitches_hz = mir_eval.util.midi_to_hz(pitches_midi)
    else:
        # Manual conversion: Hz = 440 * 2^((midi - 69) / 12)
        pitches_hz = 440.0 * (2.0 ** ((pitches_midi - 69.0) / 12.0))

    return intervals, pitches_hz


def notes_to_pitch_class_sequence(notes: List[NoteEvent]) -> np.ndarray:
    """Extract pitch class sequence (0-11) from notes, sorted by onset."""
    if not notes:
        return np.array([], dtype=int)
    sorted_notes = sorted(notes, key=lambda n: n.onset)
    return np.array([n.pitch % 12 for n in sorted_notes])


def notes_to_chroma_vector(
    notes: List[NoteEvent], duration: float = None
) -> np.ndarray:
    """
    Compute a 12-bin chroma histogram from notes, weighted by duration.

    Returns:
        np.ndarray shape (12,) normalized to sum=1 (or zeros if no notes)
    """
    chroma = np.zeros(12)
    if not notes:
        return chroma

    for n in notes:
        pc = n.pitch % 12
        chroma[pc] += n.duration

    total = chroma.sum()
    if total > 0:
        chroma /= total

    return chroma


# ============================================================================
# mir_eval Metrics
# ============================================================================


def compute_mir_eval_metrics(
    ref_notes: List[NoteEvent],
    gen_notes: List[NoteEvent],
    onset_tolerance: float = 0.05,
    pitch_tolerance: float = 50.0,
    offset_ratio: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute mir_eval transcription metrics (precision, recall, F1).

    Args:
        ref_notes: Reference notes
        gen_notes: Generated/estimated notes
        onset_tolerance: Onset tolerance in seconds (default 50ms)
        pitch_tolerance: Pitch tolerance in cents (default 50 cents)
        offset_ratio: If set, also checks offset overlap ratio

    Returns:
        Dict with precision, recall, f1 keys
    """
    if not HAS_MIR_EVAL:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    ref_intervals, ref_pitches = notes_to_intervals_and_pitches(ref_notes)
    gen_intervals, gen_pitches = notes_to_intervals_and_pitches(gen_notes)

    if len(ref_intervals) == 0 or len(gen_intervals) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    try:
        if offset_ratio is not None:
            precision, recall, f1, _ = (
                mir_eval.transcription.precision_recall_f1_overlap(
                    ref_intervals,
                    ref_pitches,
                    gen_intervals,
                    gen_pitches,
                    onset_tolerance=onset_tolerance,
                    pitch_tolerance=pitch_tolerance,
                    offset_ratio=offset_ratio,
                )
            )
        else:
            # Onset-only matching (no offset check)
            precision, recall, f1, _ = (
                mir_eval.transcription.precision_recall_f1_overlap(
                    ref_intervals,
                    ref_pitches,
                    gen_intervals,
                    gen_pitches,
                    onset_tolerance=onset_tolerance,
                    pitch_tolerance=pitch_tolerance,
                    offset_ratio=None,
                )
            )
    except Exception as e:
        logger.warning(f"mir_eval computation failed: {e}")
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def compute_onset_only_f1(
    ref_notes: List[NoteEvent],
    gen_notes: List[NoteEvent],
    onset_tolerance: float = 0.05,
) -> float:
    """
    Compute onset-only F1 (ignoring pitch).

    Uses mir_eval onset detection metrics.
    """
    if not HAS_MIR_EVAL:
        return 0.0

    if not ref_notes or not gen_notes:
        return 0.0

    ref_onsets = np.array(sorted(n.onset for n in ref_notes))
    gen_onsets = np.array(sorted(n.onset for n in gen_notes))

    try:
        result = mir_eval.onset.f_measure(
            ref_onsets, gen_onsets, window=onset_tolerance
        )
        # mir_eval.onset.f_measure returns (f_measure, precision, recall) tuple
        if isinstance(result, tuple):
            return float(result[0])
        return float(result)
    except Exception as e:
        logger.warning(f"Onset F1 computation failed: {e}")
        return 0.0


# ============================================================================
# Chroma & Pitch Class Metrics
# ============================================================================


def compute_chroma_similarity(
    ref_notes: List[NoteEvent],
    gen_notes: List[NoteEvent],
) -> float:
    """
    Compute cosine similarity between chroma histograms.

    Returns:
        float in [0, 1] where 1 = identical chroma distribution
    """
    ref_chroma = notes_to_chroma_vector(ref_notes)
    gen_chroma = notes_to_chroma_vector(gen_notes)

    dot = np.dot(ref_chroma, gen_chroma)
    norm_ref = np.linalg.norm(ref_chroma)
    norm_gen = np.linalg.norm(gen_chroma)

    if norm_ref == 0 or norm_gen == 0:
        return 0.0

    return float(dot / (norm_ref * norm_gen))


def compute_pitch_class_f1(
    ref_notes: List[NoteEvent],
    gen_notes: List[NoteEvent],
    onset_tolerance: float = 0.05,
) -> Dict[str, float]:
    """
    Compute F1 using pitch class (octave-agnostic).

    Shifts all pitches to octave 5 (MIDI 60-71) before mir_eval comparison.
    """
    if not HAS_MIR_EVAL:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # Normalize to same octave (C5 = MIDI 60)
    ref_normalized = [
        NoteEvent(pitch=60 + (n.pitch % 12), onset=n.onset, offset=n.offset)
        for n in ref_notes
    ]
    gen_normalized = [
        NoteEvent(pitch=60 + (n.pitch % 12), onset=n.onset, offset=n.offset)
        for n in gen_notes
    ]

    return compute_mir_eval_metrics(
        ref_normalized,
        gen_normalized,
        onset_tolerance=onset_tolerance,
        pitch_tolerance=50.0,
    )


# ============================================================================
# DTW-based Metrics
# ============================================================================


def compute_pitch_contour_similarity(
    ref_notes: List[NoteEvent],
    gen_notes: List[NoteEvent],
) -> float:
    """
    Compute pitch contour similarity using DTW on pitch sequences.

    Measures how similar the melodic shape is, regardless of exact timing.

    Returns:
        float in [0, 1] where 1 = identical contour
    """
    if not HAS_DTW:
        return 0.0

    if not ref_notes or not gen_notes:
        return 0.0

    ref_pitches = np.array(
        [n.pitch for n in sorted(ref_notes, key=lambda n: n.onset)], dtype=float
    )
    gen_pitches = np.array(
        [n.pitch for n in sorted(gen_notes, key=lambda n: n.onset)], dtype=float
    )

    try:
        alignment = dtw_func(ref_pitches, gen_pitches)
        # Normalize distance by path length and pitch range
        path_len = len(alignment.index1)
        if path_len == 0:
            return 0.0

        avg_dist = alignment.distance / path_len
        # Convert to similarity: use sigmoid-like mapping
        # avg_dist of 0 → similarity 1.0
        # avg_dist of 12 (one octave) → similarity ~0.5
        similarity = 1.0 / (1.0 + avg_dist / 6.0)
        return float(similarity)
    except Exception as e:
        logger.warning(f"DTW computation failed: {e}")
        return 0.0


# ============================================================================
# Composite Score
# ============================================================================


def compute_composite_metrics(
    ref_notes: List[NoteEvent],
    gen_notes: List[NoteEvent],
    structural_match: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """
    Compute full composite metrics suite.

    Args:
        ref_notes: Reference notes (NoteEvent list)
        gen_notes: Generated notes (NoteEvent list)
        structural_match: Optional structural comparison dict

    Returns:
        Dict with all metrics:
        {
            "melody_f1": float,           # mir_eval onset+pitch F1 (50ms, 50cents)
            "melody_f1_lenient": float,   # mir_eval with 200ms tolerance
            "melody_precision": float,
            "melody_recall": float,
            "pitch_class_f1": float,      # Octave-agnostic F1
            "chroma_similarity": float,   # Chroma histogram cosine similarity
            "onset_f1": float,            # Onset-only F1 (pitch ignored)
            "pitch_contour_similarity": float,  # DTW pitch contour
            "structural_similarity": {...},     # Structural match (if provided)
            "composite_score": float,     # Weighted average
            "note_counts": {
                "ref": int,
                "gen": int,
            }
        }
    """
    # Standard mir_eval (50ms onset, 50 cents pitch)
    strict_metrics = compute_mir_eval_metrics(
        ref_notes, gen_notes, onset_tolerance=0.05, pitch_tolerance=50.0
    )

    # Lenient mir_eval (200ms onset, 50 cents pitch)
    lenient_metrics = compute_mir_eval_metrics(
        ref_notes, gen_notes, onset_tolerance=0.2, pitch_tolerance=50.0
    )

    # Pitch class F1 (octave-agnostic)
    pc_metrics = compute_pitch_class_f1(ref_notes, gen_notes, onset_tolerance=0.2)

    # Chroma similarity
    chroma_sim = compute_chroma_similarity(ref_notes, gen_notes)

    # Onset-only F1
    onset_f1 = compute_onset_only_f1(ref_notes, gen_notes, onset_tolerance=0.05)

    # Pitch contour similarity (DTW)
    contour_sim = compute_pitch_contour_similarity(ref_notes, gen_notes)

    # Composite score: weighted average
    # Weights reflect importance for arrangement quality assessment:
    # - melody_f1_lenient (30%): primary quality indicator with reasonable tolerance
    # - pitch_class_f1 (20%): captures harmonic correctness ignoring octave
    # - chroma_similarity (20%): overall harmonic profile match
    # - onset_f1 (15%): rhythmic accuracy
    # - pitch_contour_similarity (15%): melodic shape
    composite = (
        0.30 * lenient_metrics["f1"]
        + 0.20 * pc_metrics["f1"]
        + 0.20 * chroma_sim
        + 0.15 * onset_f1
        + 0.15 * contour_sim
    )

    result = {
        "melody_f1": strict_metrics["f1"],
        "melody_precision": strict_metrics["precision"],
        "melody_recall": strict_metrics["recall"],
        "melody_f1_lenient": lenient_metrics["f1"],
        "pitch_class_f1": pc_metrics["f1"],
        "chroma_similarity": chroma_sim,
        "onset_f1": onset_f1,
        "pitch_contour_similarity": contour_sim,
        "composite_score": composite,
        "note_counts": {
            "ref": len(ref_notes),
            "gen": len(gen_notes),
        },
    }

    if structural_match is not None:
        result["structural_similarity"] = structural_match

    return result
