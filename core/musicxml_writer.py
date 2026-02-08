"""MusicXML writer for converting Note lists to sheet music."""

from pathlib import Path
from typing import List

import music21

from .types import Note


def _quantize_to_16th(quarter_length: float) -> float:
    """Quantize a quarter-note duration to the nearest 16th note.

    Args:
        quarter_length: Duration in quarter notes.

    Returns:
        Quantized duration rounded to nearest 16th note (0.25 grid).
        Minimum value is 0.25 (one 16th note).
    """
    quantized = round(quarter_length * 4) / 4
    return max(quantized, 0.25)


def notes_to_musicxml(
    notes: List[Note],
    title: str = "Melody",
    bpm: float = 120.0,
) -> str:
    """Convert a list of Note objects to a MusicXML string.

    Args:
        notes: List of Note objects with pitch, onset, duration, velocity.
        title: Title of the score.
        bpm: Tempo in beats per minute.

    Returns:
        MusicXML string representation of the score.

    Raises:
        ValueError: If notes list is empty.
    """
    if not notes:
        raise ValueError("Cannot create MusicXML from empty note list.")

    score = _build_score(notes, title, bpm)

    # Export to MusicXML string via GeneralObjectExporter
    exporter = music21.musicxml.m21ToXml.GeneralObjectExporter(score)
    xml_bytes = exporter.parse()
    return xml_bytes.decode("utf-8")


def save_musicxml(
    notes: List[Note],
    output_path: Path,
    title: str = "Melody",
    bpm: float = 120.0,
) -> Path:
    """Convert a list of Note objects and save as a MusicXML file.

    Args:
        notes: List of Note objects with pitch, onset, duration, velocity.
        output_path: Path where the MusicXML file will be saved.
        title: Title of the score.
        bpm: Tempo in beats per minute.

    Returns:
        Path to the saved MusicXML file.

    Raises:
        ValueError: If notes list is empty.
    """
    if not notes:
        raise ValueError("Cannot create MusicXML from empty note list.")

    score = _build_score(notes, title, bpm)
    output_path = Path(output_path)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # music21 write may append .musicxml extension; use fp to control
    written = score.write("musicxml", fp=str(output_path))
    return Path(written)


def _build_score(
    notes: List[Note],
    title: str,
    bpm: float,
) -> music21.stream.Score:
    """Build a music21 Score from Note objects.

    Args:
        notes: List of Note objects.
        title: Score title.
        bpm: Tempo in BPM.

    Returns:
        A music21 Score object with a single treble-clef Part.
    """
    seconds_per_quarter = 60.0 / bpm

    # Create score and part
    score = music21.stream.Score()
    score.metadata = music21.metadata.Metadata()
    score.metadata.title = title

    part = music21.stream.Part()
    part.partName = "Melody"

    # Add clef, tempo, and time signature
    part.append(music21.clef.TrebleClef())
    part.append(music21.tempo.MetronomeMark(number=bpm))
    part.append(music21.meter.TimeSignature("4/4"))

    # Convert each Note to a music21 note and insert at correct offset
    for n in notes:
        # Convert seconds to quarter-note units
        onset_quarters = n.onset / seconds_per_quarter
        duration_quarters = n.duration / seconds_per_quarter

        # Quantize to 16th-note grid
        quantized_onset = round(onset_quarters * 4) / 4
        quantized_duration = _quantize_to_16th(duration_quarters)

        m21_note = music21.note.Note(n.pitch, quarterLength=quantized_duration)
        m21_note.volume.velocity = n.velocity

        part.insert(quantized_onset, m21_note)

    # Create measures with bar lines
    part.makeMeasures(inPlace=True)

    score.append(part)
    return score
