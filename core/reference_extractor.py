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

        # Calculate onset and duration in seconds using music21's tempo-aware .seconds attribute
        # This automatically handles tempo changes and time signature changes
        onset_seconds = element.seconds
        duration_seconds = element.duration.seconds

        # Get the highest pitch
        if isinstance(element, music21.note.Note):
            pitch = element.pitch.midi
        elif isinstance(element, music21.chord.Chord):
            # For chords, take the highest pitch
            pitch = element.pitches[-1].midi
        else:
            continue

        # Apply skyline: keep only the highest note at each onset
        if onset_seconds not in onset_to_notes:
            onset_to_notes[onset_seconds] = {
                "pitch": pitch,
                "duration": duration_seconds,
                "velocity": element.volume.velocity if element.volume else 80,
            }
        else:
            # If we already have a note at this onset, keep the higher pitch
            if pitch > onset_to_notes[onset_seconds]["pitch"]:
                onset_to_notes[onset_seconds]["pitch"] = pitch

    # Convert to sorted list of Note objects
    notes = []
    for onset_seconds in sorted(onset_to_notes.keys()):
        note_data = onset_to_notes[onset_seconds]
        notes.append(
            Note(
                pitch=note_data["pitch"],
                onset=onset_seconds,
                duration=note_data["duration"],
                velocity=note_data["velocity"] or 80,
            )
        )

    return notes
