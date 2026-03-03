"""MusicXML writer and reader for round-trip note identity.

Key guarantee: save_musicxml() followed by load_musicxml_notes() must
produce notes that faithfully represent the saved melody. The evaluation
pipeline relies on this round-trip to ensure Output = Evaluation Identity.
"""

import logging
from pathlib import Path
from typing import List

import music21

from .types import Note

logger = logging.getLogger(__name__)


def save_musicxml(
    notes: List[Note],
    path: Path,
    title: str = "Melody",
    bpm: float = 120.0,
) -> Path:
    """Save a list of Note objects as a MusicXML file.

    Processing steps:
    1. Strip leading silence (shift so melody starts near beat 0)
    2. Convert seconds to quarter-note positions using BPM
    3. Quantize onsets and durations to 16th-note grid
    4. Handle overlaps (monophonic constraint)
    5. Write MusicXML via music21

    Args:
        notes: List of Note objects.
        path: Output file path.
        title: Score title.
        bpm: Tempo in beats per minute.

    Returns:
        Path to the saved MusicXML file.
    """
    if not notes:
        raise ValueError("Cannot save empty note list")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    spq = 60.0 / bpm  # seconds per quarter note

    # Sort by onset
    sorted_notes = sorted(notes, key=lambda n: n.onset)

    # Strip leading silence
    first_onset = sorted_notes[0].onset

    # Convert to quantized (onset_q, dur_q, pitch) tuples
    quantized = []
    for n in sorted_notes:
        onset_q = (n.onset - first_onset) / spq
        dur_q = n.duration / spq

        # Quantize to 16th-note grid
        onset_q = round(onset_q * 4) / 4
        dur_q = max(0.25, round(dur_q * 4) / 4)

        quantized.append([onset_q, dur_q, n.pitch, n.velocity])

    # Deduplicate same-onset notes (keep highest pitch for melody)
    quantized.sort(key=lambda x: (x[0], -x[2]))
    deduped = []
    for q in quantized:
        if deduped and abs(q[0] - deduped[-1][0]) < 0.01:
            continue
        deduped.append(q)

    # Truncate overlapping durations (monophonic constraint)
    for i in range(len(deduped) - 1):
        gap = deduped[i + 1][0] - deduped[i][0]
        if gap > 0 and deduped[i][1] > gap:
            deduped[i][1] = gap

    # Build music21 score
    score = music21.stream.Score()
    score.metadata = music21.metadata.Metadata()
    score.metadata.title = title

    part = music21.stream.Part()
    part.partName = "Melody"
    part.append(music21.clef.TrebleClef())
    part.append(music21.tempo.MetronomeMark(number=bpm))
    part.append(music21.meter.TimeSignature("4/4"))

    for onset_q, dur_q, pitch, vel in deduped:
        m21_note = music21.note.Note(pitch, quarterLength=dur_q)
        m21_note.volume.velocity = vel
        part.insert(onset_q, m21_note)

    part.makeMeasures(inPlace=True)
    score.append(part)

    written = score.write("musicxml", fp=str(path))
    logger.info(
        "Saved MusicXML: %s (%d notes, bpm=%.0f)",
        path.name,
        len(deduped),
        bpm,
    )
    return Path(written)


def load_musicxml_notes(path: Path) -> List[Note]:
    """Load notes from a MusicXML file for round-trip evaluation.

    Parses the MusicXML file and reconstructs Note objects with timing
    converted back to seconds using the score's tempo marking.

    Args:
        path: Path to MusicXML file.

    Returns:
        List of Note objects sorted by onset time.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"MusicXML file not found: {path}")

    score = music21.converter.parse(str(path))
    if not score.parts:
        return []

    part = score.parts[0]

    # Find BPM from tempo mark
    bpm = 120.0
    for el in part.flatten():
        if isinstance(el, music21.tempo.MetronomeMark):
            bpm = el.number
            break

    spq = 60.0 / bpm

    notes = []
    for el in part.flatten().notesAndRests:
        if isinstance(el, music21.note.Rest):
            continue
        if isinstance(el, music21.harmony.ChordSymbol):
            continue

        if isinstance(el, music21.note.Note):
            onset = float(el.offset) * spq
            duration = float(el.quarterLength) * spq
            velocity = el.volume.velocity if el.volume and el.volume.velocity else 80
            notes.append(
                Note(
                    pitch=el.pitch.midi,
                    onset=round(onset, 4),
                    duration=round(duration, 4),
                    velocity=velocity,
                )
            )

    notes.sort(key=lambda n: n.onset)
    logger.info(
        "Loaded MusicXML: %s (%d notes, bpm=%.0f)",
        path.name,
        len(notes),
        bpm,
    )
    return notes
