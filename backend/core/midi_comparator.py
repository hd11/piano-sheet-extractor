"""
MIDI 직접 비교 모듈

두 MIDI 파일을 직접 비교하여 복합 유사도 메트릭을 계산합니다.
MusicXML 변환 없이 parse_midi() SSOT로 파싱 → mir_eval + DTW 기반 비교.

comparison_utils.py의 공유 로직을 사용하여 musicxml_comparator.py와
동일한 메트릭 구조를 반환합니다.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List

from core.midi_parser import Note, parse_midi
from core.comparison_utils import (
    NoteEvent,
    compute_composite_metrics,
)

logger = logging.getLogger(__name__)


class MidiComparisonError(Exception):
    """MIDI 비교 중 발생하는 오류"""

    pass


def _notes_to_noteevents(notes: List[Note]) -> List[NoteEvent]:
    """
    Convert midi_parser.Note list to NoteEvent list for comparison.

    midi_parser.Note already has onset/duration in seconds
    (pretty_midi handles tempo map internally), so no BPM conversion needed.

    Args:
        notes: Note list from parse_midi()

    Returns:
        List of NoteEvent with onset/offset in seconds, sorted by (onset, pitch)
    """
    events = [
        NoteEvent(
            pitch=n.pitch,
            onset=n.onset,
            offset=n.onset + n.duration,
        )
        for n in notes
    ]
    events.sort(key=lambda e: (e.onset, e.pitch))
    return events


def compare_midi(
    ref_midi_path: str,
    gen_midi_path: str,
) -> Dict[str, Any]:
    """
    Compare two MIDI files directly using mir_eval composite metrics.

    Parses both MIDI files with parse_midi() (pretty_midi-based SSOT),
    converts to NoteEvent format, and computes composite metrics via
    shared comparison_utils.

    Returns same structure as compare_musicxml_composite() for consistency:
    {
        "melody_f1": float,
        "melody_f1_lenient": float,
        "melody_precision": float,
        "melody_recall": float,
        "pitch_class_f1": float,
        "chroma_similarity": float,
        "onset_f1": float,
        "pitch_contour_similarity": float,
        "structural_similarity": {},  # Empty dict for MIDI (no structural metadata)
        "composite_score": float,
        "note_counts": {"ref": int, "gen": int},
    }

    Args:
        ref_midi_path: Path to reference MIDI file
        gen_midi_path: Path to generated/estimated MIDI file

    Returns:
        Dict with composite metrics

    Raises:
        MidiComparisonError: If files not found or parsing fails
    """
    ref_path = Path(ref_midi_path)
    gen_path = Path(gen_midi_path)

    if not ref_path.exists():
        raise MidiComparisonError(f"Reference MIDI file not found: {ref_midi_path}")
    if not gen_path.exists():
        raise MidiComparisonError(f"Generated MIDI file not found: {gen_midi_path}")

    # Parse MIDI files using SSOT parse_midi()
    try:
        ref_notes = parse_midi(ref_path)
    except Exception as e:
        raise MidiComparisonError(f"Failed to parse reference MIDI: {e}")

    try:
        gen_notes = parse_midi(gen_path)
    except Exception as e:
        raise MidiComparisonError(f"Failed to parse generated MIDI: {e}")

    if not ref_notes:
        raise MidiComparisonError(f"Reference MIDI file has no notes: {ref_midi_path}")

    logger.info(
        f"Comparing MIDI: ref={len(ref_notes)} notes, gen={len(gen_notes)} notes"
    )

    # Convert to NoteEvent (already seconds-based from parse_midi)
    ref_events = _notes_to_noteevents(ref_notes)
    gen_events = _notes_to_noteevents(gen_notes)

    # Compute composite metrics (no structural_match for MIDI)
    # When structural_match is None, comparison_utils renormalizes weights
    # to exclude the structural 10% component
    result = compute_composite_metrics(ref_events, gen_events, structural_match=None)

    # Add empty structural_similarity for API consistency with musicxml_comparator
    if "structural_similarity" not in result:
        result["structural_similarity"] = {}

    return result


def compare_midi_detailed(
    ref_midi_path: str,
    gen_midi_path: str,
) -> Dict[str, Any]:
    """
    Compare two MIDI files with additional detail (duration, pitch range).

    Args:
        ref_midi_path: Reference MIDI file path
        gen_midi_path: Generated/comparison MIDI file path

    Returns:
        Dict with composite metrics plus:
        - ref_duration: float (seconds)
        - gen_duration: float (seconds)
        - ref_pitch_range: (min, max)
        - gen_pitch_range: (min, max)

    Raises:
        MidiComparisonError: If files not found or parsing fails
    """
    result = compare_midi(ref_midi_path, gen_midi_path)

    # Parse again for extra metadata (cheap operation)
    ref_notes = parse_midi(Path(ref_midi_path))
    gen_notes = parse_midi(Path(gen_midi_path))

    ref_events = _notes_to_noteevents(ref_notes)
    gen_events = _notes_to_noteevents(gen_notes)

    # Add duration info
    if ref_events:
        result["ref_duration"] = max(n.offset for n in ref_events)
        result["ref_pitch_range"] = (
            min(n.pitch for n in ref_events),
            max(n.pitch for n in ref_events),
        )
    else:
        result["ref_duration"] = 0.0
        result["ref_pitch_range"] = (0, 0)

    if gen_events:
        result["gen_duration"] = max(n.offset for n in gen_events)
        result["gen_pitch_range"] = (
            min(n.pitch for n in gen_events),
            max(n.pitch for n in gen_events),
        )
    else:
        result["gen_duration"] = 0.0
        result["gen_pitch_range"] = (0, 0)

    return result
