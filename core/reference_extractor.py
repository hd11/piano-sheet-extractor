"""Extract reference melody from MusicXML piano arrangements.

Used only for evaluation — never in the extraction pipeline.
Applies skyline algorithm: for each onset, take the highest note.
"""

import logging
from pathlib import Path
from typing import List

import music21

from .types import Note

logger = logging.getLogger(__name__)


def extract_reference_melody(mxl_path: Path) -> List[Note]:
    """Extract melody from .mxl piano arrangement using skyline algorithm.

    Takes the treble clef (Part 0 = right hand) and for each onset keeps
    only the highest note. This extracts the melody line from arrangements
    that include inner voices and chord tones.

    Args:
        mxl_path: Path to .mxl file.

    Returns:
        List of Note objects representing the reference melody.
    """
    mxl_path = Path(mxl_path)
    if not mxl_path.exists():
        raise FileNotFoundError(f"MusicXML file not found: {mxl_path}")

    score = music21.converter.parse(str(mxl_path))
    if not score.parts:
        raise ValueError("Score has no parts")

    treble_part = score.parts[0]
    tempo_map = _build_tempo_map(treble_part)

    # Collect notes with skyline (highest pitch per onset)
    onset_to_notes = {}

    for element in treble_part.flatten().notesAndRests:
        if isinstance(element, music21.harmony.ChordSymbol):
            continue
        if isinstance(element, music21.note.Rest):
            continue

        onset_seconds = _offset_to_seconds(element.offset, tempo_map)
        duration_seconds = element.seconds

        if isinstance(element, music21.note.Note):
            pitch = element.pitch.midi
        elif isinstance(element, music21.chord.Chord):
            pitch = element.pitches[-1].midi
        else:
            continue

        onset_key = round(onset_seconds, 3)
        if onset_key not in onset_to_notes:
            onset_to_notes[onset_key] = {
                "pitch": pitch,
                "duration": duration_seconds,
                "onset_exact": onset_seconds,
                "velocity": element.volume.velocity if element.volume else 80,
            }
        else:
            if pitch > onset_to_notes[onset_key]["pitch"]:
                onset_to_notes[onset_key]["pitch"] = pitch
                onset_to_notes[onset_key]["duration"] = duration_seconds

    notes = []
    for onset_key in sorted(onset_to_notes.keys()):
        d = onset_to_notes[onset_key]
        notes.append(
            Note(
                pitch=d["pitch"],
                onset=d.get("onset_exact", onset_key),
                duration=d["duration"],
                velocity=d["velocity"] or 80,
            )
        )

    logger.info(
        "Reference extracted: %s (%d notes)",
        mxl_path.name,
        len(notes),
    )
    return notes


def get_reference_bpm(mxl_path: Path) -> float:
    """Get the primary BPM from a reference .mxl file."""
    score = music21.converter.parse(str(mxl_path))
    if not score.parts:
        return 120.0
    tempo_map = _build_tempo_map(score.parts[0])
    return tempo_map[0][1] if tempo_map else 120.0


def _build_tempo_map(part: music21.stream.Part) -> list:
    """Build a tempo map from MetronomeMarkBoundaries.

    Returns effective quarter-note BPM accounting for referent duration.
    """
    try:
        boundaries = part.metronomeMarkBoundaries()
        if boundaries:
            result = []
            for start, _end, mm in boundaries:
                referent_ql = mm.referent.quarterLength if mm.referent else 1.0
                effective_bpm = mm.number * referent_ql
                result.append((start, effective_bpm))
            return result
    except Exception:
        pass

    tempos = list(part.flatten().getElementsByClass(music21.tempo.MetronomeMark))
    if tempos:
        result = []
        for tm in tempos:
            referent_ql = tm.referent.quarterLength if tm.referent else 1.0
            effective_bpm = tm.number * referent_ql
            result.append((float(tm.offset), effective_bpm))
        return result

    return [(0.0, 120)]


def _offset_to_seconds(offset: float, tempo_map: list) -> float:
    """Convert offset in quarter notes to seconds using tempo map."""
    seconds = 0.0
    prev_offset = 0.0
    prev_bpm = tempo_map[0][1] if tempo_map else 120

    for tm_offset, bpm in tempo_map:
        if tm_offset >= offset:
            break
        seconds += (tm_offset - prev_offset) * (60.0 / prev_bpm)
        prev_offset = tm_offset
        prev_bpm = bpm

    seconds += (offset - prev_offset) * (60.0 / prev_bpm)
    return seconds
