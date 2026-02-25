"""Extract reference melody from MusicXML piano arrangements."""

from pathlib import Path
from typing import List

import music21

from .types import Note


def extract_reference_melody(mxl_path: Path) -> List[Note]:
    """Extract melody from .mxl piano arrangement using skyline algorithm.

    Extracts the melody from the treble clef (right hand, score.parts[0]) by
    applying a skyline algorithm: for each onset, take the highest note.
    Excludes ChordSymbol elements (harmony annotations).

    Args:
        mxl_path: Path to .mxl file (supports Korean filenames)

    Returns:
        List of Note objects representing the extracted melody, sorted by onset

    Raises:
        FileNotFoundError: If .mxl file does not exist
        Exception: If music21 cannot parse the file
    """
    mxl_path = Path(mxl_path)

    if not mxl_path.exists():
        raise FileNotFoundError(f"MusicXML file not found: {mxl_path}")

    # Parse the MusicXML file
    score = music21.converter.parse(str(mxl_path))

    # Get the treble clef part (right hand)
    if not score.parts:
        raise ValueError("Score has no parts")

    treble_part = score.parts[0]

    # Build tempo map from MetronomeMarkBoundaries for accurate offset->seconds conversion
    # This handles tempo changes (e.g., Golden.mxl: 122 BPM throughout)
    tempo_map = _build_tempo_map(treble_part)

    # Collect all notes with their onsets and pitches
    # Using a dictionary to implement skyline: onset -> highest_pitch
    onset_to_notes = {}

    for element in treble_part.flatten().notesAndRests:
        # Skip ChordSymbol elements (harmony annotations)
        if isinstance(element, music21.harmony.ChordSymbol):
            continue

        # Skip rests
        if isinstance(element, music21.note.Rest):
            continue

        # Convert offset (quarter notes) to seconds using tempo map
        onset_seconds = _offset_to_seconds(element.offset, tempo_map)
        # Duration: element.seconds gives the duration in seconds (tempo-aware)
        duration_seconds = element.seconds

        # Get the highest pitch
        if isinstance(element, music21.note.Note):
            pitch = element.pitch.midi
        elif isinstance(element, music21.chord.Chord):
            # For chords, take the highest pitch
            pitch = element.pitches[-1].midi
        else:
            continue

        # Apply skyline: keep only the highest note at each onset
        # Round onset to avoid floating-point key collision issues
        onset_key = round(onset_seconds, 3)
        if onset_key not in onset_to_notes:
            onset_to_notes[onset_key] = {
                "pitch": pitch,
                "duration": duration_seconds,
                "onset_exact": onset_seconds,
                "velocity": element.volume.velocity if element.volume else 80,
            }
        else:
            # If we already have a note at this onset, keep the higher pitch
            if pitch > onset_to_notes[onset_key]["pitch"]:
                onset_to_notes[onset_key]["pitch"] = pitch
                onset_to_notes[onset_key]["duration"] = duration_seconds

    # Convert to sorted list of Note objects
    notes = []
    for onset_key in sorted(onset_to_notes.keys()):
        note_data = onset_to_notes[onset_key]
        notes.append(
            Note(
                pitch=note_data["pitch"],
                onset=note_data.get("onset_exact", onset_key),
                duration=note_data["duration"],
                velocity=note_data["velocity"] or 80,
            )
        )

    return notes


def _build_tempo_map(part: music21.stream.Part) -> list:
    """Build a tempo map from MetronomeMarkBoundaries.

    Args:
        part: music21 Part to extract tempo marks from.

    Returns:
        List of (offset_in_quarters, bpm) tuples, sorted by offset.
        Falls back to [(0.0, 120)] if no tempo marks found.
    """
    try:
        boundaries = part.metronomeMarkBoundaries()
        if boundaries:
            return [(start, mm.number) for start, _end, mm in boundaries]
    except Exception:
        pass

    # Fallback: check for MetronomeMarks in flattened stream
    tempos = list(part.flatten().getElementsByClass(music21.tempo.MetronomeMark))
    if tempos:
        return [(float(tm.offset), tm.number) for tm in tempos]

    # Default to 120 BPM
    return [(0.0, 120)]


def _offset_to_seconds(offset: float, tempo_map: list) -> float:
    """Convert an offset in quarter notes to seconds using a tempo map.

    Walks through the tempo map segments, accumulating time for each
    segment until reaching the target offset.

    Args:
        offset: Position in quarter notes.
        tempo_map: List of (offset_in_quarters, bpm) tuples from _build_tempo_map.

    Returns:
        Time in seconds corresponding to the given offset.
    """
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
