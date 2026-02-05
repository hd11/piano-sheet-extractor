"""
MIDI 직접 비교 모듈

두 MIDI 파일을 직접 비교하여 복합 메트릭을 계산합니다.
MusicXML 변환 없이 pretty_midi로 노트를 추출하고 mir_eval + DTW로 비교합니다.

comparison_utils.py의 공통 로직을 사용합니다.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List

import pretty_midi

from core.comparison_utils import (
    NoteEvent,
    compute_composite_metrics,
)

logger = logging.getLogger(__name__)


def _extract_notes_from_midi(midi_path: str) -> List[NoteEvent]:
    """
    Extract NoteEvent list from a MIDI file using pretty_midi.

    Args:
        midi_path: Path to MIDI file

    Returns:
        List of NoteEvent (seconds-based)

    Raises:
        FileNotFoundError: If MIDI file doesn't exist
        ValueError: If MIDI file has no notes
    """
    path = Path(midi_path)
    if not path.exists():
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")

    pm = pretty_midi.PrettyMIDI(str(path))

    events = []
    for instrument in pm.instruments:
        if instrument.is_drum:
            continue
        for note in instrument.notes:
            events.append(
                NoteEvent(
                    pitch=note.pitch,
                    onset=note.start,
                    offset=note.end,
                )
            )

    # Sort by onset, then pitch
    events.sort(key=lambda n: (n.onset, n.pitch))
    return events


def compare_midi(
    ref_path: str,
    gen_path: str,
) -> Dict[str, Any]:
    """
    Compare two MIDI files using composite metrics (mir_eval + DTW + chroma).

    Args:
        ref_path: Reference MIDI file path
        gen_path: Generated/comparison MIDI file path

    Returns:
        Dict with composite metrics:
        {
            "melody_f1": float,
            "melody_f1_lenient": float,
            "melody_precision": float,
            "melody_recall": float,
            "pitch_class_f1": float,
            "chroma_similarity": float,
            "onset_f1": float,
            "pitch_contour_similarity": float,
            "composite_score": float,
            "note_counts": {"ref": int, "gen": int},
        }

    Raises:
        FileNotFoundError: If either MIDI file doesn't exist
    """
    ref_events = _extract_notes_from_midi(ref_path)
    gen_events = _extract_notes_from_midi(gen_path)

    if not ref_events:
        logger.warning(f"Reference MIDI has no notes: {ref_path}")

    return compute_composite_metrics(ref_events, gen_events)


def compare_midi_detailed(
    ref_path: str,
    gen_path: str,
) -> Dict[str, Any]:
    """
    Compare two MIDI files with additional detail (note lists, duration info).

    Args:
        ref_path: Reference MIDI file path
        gen_path: Generated/comparison MIDI file path

    Returns:
        Dict with composite metrics plus:
        - ref_duration: float (seconds)
        - gen_duration: float (seconds)
        - ref_pitch_range: (min, max)
        - gen_pitch_range: (min, max)
    """
    ref_events = _extract_notes_from_midi(ref_path)
    gen_events = _extract_notes_from_midi(gen_path)

    result = compute_composite_metrics(ref_events, gen_events)

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
