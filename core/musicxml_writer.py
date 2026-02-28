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

    Applies several post-processing steps to produce clean monophonic output:
    1. Strip leading silence (shift all onsets so melody starts at beat 0)
    2. Quantize onsets and durations to 16th-note grid
    3. Deduplicate notes at same onset (keep highest pitch for melody)
    4. Truncate overlapping durations (monophonic constraint)
    5. Legato fill: extend notes to cover small gaps

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

    if not notes:
        score.append(part)
        return score

    # --- Step 1: Strip leading silence ---
    first_onset = min(n.onset for n in notes)
    if first_onset > 0.1:  # more than 100ms of leading silence
        notes = [
            Note(pitch=n.pitch, onset=n.onset - first_onset,
                 duration=n.duration, velocity=n.velocity)
            for n in notes
        ]

    # --- Step 2: Remove isolated notes (large jump from both neighbors) ---
    # Vocal melodies rarely have >7 semitone jumps; isolated jumps are errors
    if len(notes) >= 3:
        cleaned = [notes[0]]
        for i in range(1, len(notes) - 1):
            jump_before = abs(notes[i].pitch - notes[i - 1].pitch)
            jump_after = abs(notes[i].pitch - notes[i + 1].pitch)
            if jump_before > 7 and jump_after > 7:
                continue  # skip isolated note
            cleaned.append(notes[i])
        cleaned.append(notes[-1])
        notes = cleaned

    # --- Step 3: Merge consecutive same-pitch notes (pre-quantization) ---
    # BP often splits one sustained note into multiple short notes
    merged_notes: List[Note] = [notes[0]]
    for i in range(1, len(notes)):
        prev = merged_notes[-1]
        curr = notes[i]
        gap = curr.onset - (prev.onset + prev.duration)
        if curr.pitch == prev.pitch and gap < 0.15:  # same pitch, gap < 150ms
            # Merge: extend previous note to cover current
            new_dur = (curr.onset + curr.duration) - prev.onset
            merged_notes[-1] = Note(
                pitch=prev.pitch, onset=prev.onset,
                duration=new_dur, velocity=prev.velocity,
            )
        else:
            merged_notes.append(curr)
    notes = merged_notes

    # --- Step 4: Quantize to 16th-note grid ---
    # Each entry: [onset_q, dur_q, pitch, velocity]
    quantized = []
    for n in notes:
        onset_q = round(n.onset / seconds_per_quarter * 4) / 4
        dur_q = _quantize_to_16th(n.duration / seconds_per_quarter)
        quantized.append([onset_q, dur_q, n.pitch, n.velocity])

    # --- Step 5: Sort by onset, then pitch descending (melody = top note) ---
    quantized.sort(key=lambda x: (x[0], -x[2]))

    # --- Step 6: Deduplicate same-onset notes (monophonic melody) ---
    deduped = []
    for q in quantized:
        if deduped and abs(q[0] - deduped[-1][0]) < 0.01:
            continue  # same onset position: keep earlier (higher pitch)
        deduped.append(q)

    # --- Step 7: Truncate overlapping durations ---
    for i in range(len(deduped) - 1):
        gap = deduped[i + 1][0] - deduped[i][0]
        if gap > 0 and deduped[i][1] > gap:
            deduped[i][1] = gap  # trim to not overlap next note

    # --- Step 8: Legato fill — extend notes to cover small gaps ---
    for i in range(len(deduped) - 1):
        note_end = deduped[i][0] + deduped[i][1]
        next_onset = deduped[i + 1][0]
        gap = next_onset - note_end
        if 0 < gap <= 0.5:  # gap ≤ half a beat: fill it
            deduped[i][1] = next_onset - deduped[i][0]

    # --- Step 9: Merge consecutive same-pitch notes (post-quantization) ---
    # After legato fill, adjacent same-pitch notes should become one
    final = [deduped[0]]
    for i in range(1, len(deduped)):
        prev = final[-1]
        curr = deduped[i]
        prev_end = prev[0] + prev[1]
        if curr[2] == prev[2] and abs(prev_end - curr[0]) < 0.01:
            # Same pitch and adjacent: merge
            final[-1] = [prev[0], curr[0] + curr[1] - prev[0], prev[2], prev[3]]
        else:
            final.append(curr)
    deduped = final

    # --- Insert into part ---
    for onset_q, dur_q, pitch, vel in deduped:
        m21_note = music21.note.Note(pitch, quarterLength=dur_q)
        m21_note.volume.velocity = vel
        part.insert(onset_q, m21_note)

    # Create measures with bar lines
    part.makeMeasures(inPlace=True)

    score.append(part)
    return score
