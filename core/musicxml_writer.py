"""MusicXML writer and reader for round-trip note identity.

Key guarantee: save_musicxml() followed by load_musicxml_notes() must
produce notes that faithfully represent the saved melody. The evaluation
pipeline relies on this round-trip to ensure Output = Evaluation Identity.

Uses explicit measure construction (no makeMeasures) and 8th-note
quantization grid for optimal round-trip consistency.
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
    3. Quantize onsets and durations to 8th-note grid
    4. Handle overlaps (monophonic constraint)
    5. Build explicit measures with tie handling at bar lines
    6. Write MusicXML via music21

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
    beats_per_measure = 4.0  # 4/4 time

    # Sort by onset
    sorted_notes = sorted(notes, key=lambda n: n.onset)

    # Strip leading silence
    first_onset = sorted_notes[0].onset

    # Adaptive quantization grid based on BPM
    # Fast songs (>=140 BPM): 16th-note grid for rhythmic detail
    # Slow songs (<140 BPM): 8th-note grid to avoid fragmentation
    if bpm >= 140:
        grid_mult = 4  # 16th notes (0.25 quarter notes)
        min_dur = 0.25
    else:
        grid_mult = 2  # 8th notes (0.5 quarter notes)
        min_dur = 0.5

    # Convert to quantized (onset_q, dur_q, pitch, velocity) tuples
    quantized = []
    for n in sorted_notes:
        onset_q = (n.onset - first_onset) / spq
        dur_q = n.duration / spq

        # Quantize to adaptive grid
        onset_q = round(onset_q * grid_mult) / grid_mult
        dur_q = max(min_dur, round(dur_q * grid_mult) / grid_mult)

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

    # Build music21 score with explicit measures
    score = music21.stream.Score()
    score.metadata = music21.metadata.Metadata()
    score.metadata.title = title

    part = music21.stream.Part()
    part.partName = "Melody"

    # Determine total measures needed
    last_end = max(q[0] + q[1] for q in deduped) if deduped else 0
    total_measures = int(last_end / beats_per_measure) + 1

    # Create explicit measures
    measures = []
    for m_idx in range(total_measures):
        m = music21.stream.Measure(number=m_idx + 1)
        if m_idx == 0:
            m.append(music21.clef.TrebleClef())
            m.append(music21.tempo.MetronomeMark(number=bpm))
            m.append(music21.meter.TimeSignature("4/4"))
        measures.append(m)

    # Place notes into measures, splitting at bar lines with ties
    for onset_q, dur_q, pitch, vel in deduped:
        _place_note(measures, onset_q, dur_q, pitch, vel, beats_per_measure)

    # Fill gaps with rests and append to part
    for m in measures:
        m.makeRests(fillGaps=True, inPlace=True)
        part.append(m)

    score.append(part)

    written = score.write("musicxml", fp=str(path))
    logger.info(
        "Saved MusicXML: %s (%d notes, bpm=%.0f)",
        path.name,
        len(deduped),
        bpm,
    )
    return Path(written)


def _place_note(
    measures: list,
    onset_q: float,
    dur_q: float,
    pitch: int,
    vel: int,
    beats_per_measure: float,
) -> None:
    """Place a note into measures, splitting with ties at bar lines.

    If a note crosses a measure boundary, it is split into segments
    connected by ties (start/continue/stop).
    """
    m_idx = int(onset_q / beats_per_measure)
    offset = round(onset_q - m_idx * beats_per_measure, 4)
    remaining = dur_q

    # Collect segments: (measure_index, offset_in_measure, segment_duration)
    segments = []
    while remaining > 0.01 and m_idx < len(measures):
        space = round(beats_per_measure - offset, 4)
        seg_dur = min(remaining, space)
        segments.append((m_idx, offset, seg_dur))
        remaining = round(remaining - seg_dur, 4)
        m_idx += 1
        offset = 0.0

    # Insert notes with tie markings
    for i, (mi, off, dur) in enumerate(segments):
        n = music21.note.Note(pitch, quarterLength=dur)
        n.volume.velocity = vel

        if len(segments) > 1:
            if i == 0:
                n.tie = music21.tie.Tie("start")
            elif i == len(segments) - 1:
                n.tie = music21.tie.Tie("stop")
            else:
                n.tie = music21.tie.Tie("continue")

        measures[mi].insert(off, n)


def load_musicxml_notes(path: Path) -> List[Note]:
    """Load notes from a MusicXML file for round-trip evaluation.

    Parses the MusicXML file and reconstructs Note objects with timing
    converted back to seconds using the score's tempo marking.

    Tied notes (split at bar lines during save) are merged back into
    single notes for round-trip consistency.

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

    # Collect raw notes with tie info
    raw = []
    for el in part.flatten().notesAndRests:
        if isinstance(el, music21.note.Rest):
            continue
        if isinstance(el, music21.harmony.ChordSymbol):
            continue

        if isinstance(el, music21.note.Note):
            onset = float(el.offset) * spq
            duration = float(el.quarterLength) * spq
            velocity = el.volume.velocity if el.volume and el.volume.velocity else 80
            is_continuation = (
                el.tie is not None and el.tie.type in ("stop", "continue")
            )
            raw.append(
                {
                    "pitch": el.pitch.midi,
                    "onset": round(onset, 4),
                    "duration": round(duration, 4),
                    "velocity": velocity,
                    "is_continuation": is_continuation,
                }
            )

    # Merge tied notes back into single notes
    merged = []
    for rn in raw:
        if rn["is_continuation"] and merged:
            merged[-1]["duration"] = round(
                merged[-1]["duration"] + rn["duration"], 4
            )
        else:
            merged.append(rn)

    notes = [
        Note(
            pitch=m["pitch"],
            onset=m["onset"],
            duration=m["duration"],
            velocity=m["velocity"],
        )
        for m in merged
    ]
    notes.sort(key=lambda n: n.onset)

    logger.info(
        "Loaded MusicXML: %s (%d notes, bpm=%.0f)",
        path.name,
        len(notes),
        bpm,
    )
    return notes
