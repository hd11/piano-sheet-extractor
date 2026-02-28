#!/usr/bin/env python3
"""Debug: verify MusicXML roundtrip preserves pitch accuracy.

The BPM test showed pc_f1 dropping from 0.735 (raw) to 0.193 (MusicXML).
This tests whether the drop is real or a bug in the extraction code.

Steps:
1. Apply MusicXML writer processing manually (no music21 score) → compare
2. Build music21 score → extract notes back → compare
3. Save MusicXML file → reload → extract notes → compare
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import extract_melody
from core.vocal_separator import separate_vocals
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies
from core.postprocess import apply_sectional_time_offset
from core.musicxml_writer import _build_score, _quantize_to_16th
from core.types import Note

import music21

TEST_MP3 = Path("test/꿈의 버스.mp3")
TEST_MXL = Path("test/꿈의 버스.mxl")
CACHE_DIR = Path("test/cache")


def extract_notes_from_score(score, bpm):
    """Extract Note objects from a music21 Score."""
    sec_per_q = 60.0 / bpm
    notes = []

    # Try both .flat and .flatten()
    try:
        stream = score.flatten()
    except:
        stream = score.flat

    for element in stream.notes:
        if isinstance(element, music21.note.Note):
            onset_sec = float(element.offset) * sec_per_q
            dur_sec = float(element.quarterLength) * sec_per_q
            notes.append(Note(
                pitch=element.pitch.midi,
                onset=round(onset_sec, 4),
                duration=round(dur_sec, 4),
                velocity=element.volume.velocity or 80,
            ))

    return sorted(notes, key=lambda n: n.onset)


def manual_musicxml_processing(notes, bpm):
    """Replicate _build_score processing WITHOUT music21.

    This isolates whether the quality loss is from music21's makeMeasures()
    or from the note processing itself.
    """
    sec_per_q = 60.0 / bpm

    if not notes:
        return []

    # Step 1: Strip leading silence
    first_onset = min(n.onset for n in notes)
    if first_onset > 0.1:
        notes = [
            Note(pitch=n.pitch, onset=n.onset - first_onset,
                 duration=n.duration, velocity=n.velocity)
            for n in notes
        ]

    # Step 2: Remove isolated notes
    if len(notes) >= 3:
        cleaned = [notes[0]]
        for i in range(1, len(notes) - 1):
            jump_before = abs(notes[i].pitch - notes[i - 1].pitch)
            jump_after = abs(notes[i].pitch - notes[i + 1].pitch)
            if jump_before > 7 and jump_after > 7:
                continue
            cleaned.append(notes[i])
        cleaned.append(notes[-1])
        notes = cleaned

    # Step 3: Merge consecutive same-pitch (pre-quantization)
    merged = [notes[0]]
    for i in range(1, len(notes)):
        prev = merged[-1]
        curr = notes[i]
        gap = curr.onset - (prev.onset + prev.duration)
        if curr.pitch == prev.pitch and gap < 0.15:
            new_dur = (curr.onset + curr.duration) - prev.onset
            merged[-1] = Note(pitch=prev.pitch, onset=prev.onset,
                              duration=new_dur, velocity=prev.velocity)
        else:
            merged.append(curr)
    notes = merged

    # Step 4: Quantize to 16th grid
    quantized = []
    for n in notes:
        onset_q = round(n.onset / sec_per_q * 4) / 4
        dur_q = _quantize_to_16th(n.duration / sec_per_q)
        quantized.append([onset_q, dur_q, n.pitch, n.velocity])

    # Step 5: Sort
    quantized.sort(key=lambda x: (x[0], -x[2]))

    # Step 6: Dedup same-onset
    deduped = []
    for q in quantized:
        if deduped and abs(q[0] - deduped[-1][0]) < 0.01:
            continue
        deduped.append(q)

    # Step 7: Truncate overlaps
    for i in range(len(deduped) - 1):
        gap = deduped[i + 1][0] - deduped[i][0]
        if gap > 0 and deduped[i][1] > gap:
            deduped[i][1] = gap

    # Step 8: Legato fill
    for i in range(len(deduped) - 1):
        note_end = deduped[i][0] + deduped[i][1]
        next_onset = deduped[i + 1][0]
        gap = next_onset - note_end
        if 0 < gap <= 0.5:
            deduped[i][1] = next_onset - deduped[i][0]

    # Step 9: Post-quantization same-pitch merge
    final = [deduped[0]]
    for i in range(1, len(deduped)):
        prev = final[-1]
        curr = deduped[i]
        prev_end = prev[0] + prev[1]
        if curr[2] == prev[2] and abs(prev_end - curr[0]) < 0.01:
            final[-1] = [prev[0], curr[0] + curr[1] - prev[0], prev[2], prev[3]]
        else:
            final.append(curr)
    deduped = final

    # Convert back to Note objects with seconds timing
    result = []
    for onset_q, dur_q, pitch, vel in deduped:
        onset_sec = onset_q * sec_per_q
        dur_sec = dur_q * sec_per_q
        result.append(Note(pitch=pitch, onset=round(onset_sec, 4),
                           duration=round(dur_sec, 4), velocity=vel))

    return result


def main():
    print("=" * 70)
    print("MUSICXML ROUNDTRIP QUALITY DEBUG")
    print("=" * 70)

    ref_notes = [n for n in extract_reference_melody(TEST_MXL) if n.duration > 0]
    gen_notes = extract_melody(TEST_MP3, cache_dir=CACHE_DIR)
    gen_notes = [n for n in gen_notes if n.duration > 0]

    bpm = 178.2  # detected BPM

    print(f"\nRaw gen notes: {len(gen_notes)}")
    print(f"Reference notes: {len(ref_notes)}")

    # Test 1: Raw notes (baseline)
    aligned = apply_sectional_time_offset(gen_notes, ref_notes)
    m = compare_melodies(ref_notes, aligned)
    print(f"\n1. RAW notes (baseline):")
    print(f"   pc_f1={m['pitch_class_f1']:.3f}, mel_len={m['melody_f1_lenient']:.3f}, "
          f"contour={m['contour_similarity']:.3f}, notes={len(gen_notes)}")

    # Test 2: Manual MusicXML processing (no music21)
    manual_notes = manual_musicxml_processing(gen_notes, bpm)
    aligned = apply_sectional_time_offset(manual_notes, ref_notes)
    m = compare_melodies(ref_notes, aligned)
    print(f"\n2. MANUAL processing (no music21):")
    print(f"   pc_f1={m['pitch_class_f1']:.3f}, mel_len={m['melody_f1_lenient']:.3f}, "
          f"contour={m['contour_similarity']:.3f}, notes={len(manual_notes)}")

    # Test 3: Through music21 _build_score, extract back
    score = _build_score(gen_notes, "Test", bpm)
    m21_notes = extract_notes_from_score(score, bpm)
    print(f"\n3a. music21 score extraction (pre-alignment):")
    print(f"   Extracted {len(m21_notes)} notes from score")
    if m21_notes:
        print(f"   Onset range: {m21_notes[0].onset:.2f}s - {m21_notes[-1].onset:.2f}s")
        print(f"   Pitch range: {min(n.pitch for n in m21_notes)} - {max(n.pitch for n in m21_notes)}")

        # Compare first 5 notes: manual vs music21
        print(f"\n   First 5 notes comparison:")
        print(f"   {'Source':<10} | {'onset':>8} | {'dur':>8} | {'pitch':>5}")
        print(f"   {'-'*40}")
        for i in range(min(5, len(manual_notes))):
            mn = manual_notes[i]
            print(f"   {'manual':<10} | {mn.onset:>8.3f} | {mn.duration:>8.3f} | {mn.pitch:>5}")
        print()
        for i in range(min(5, len(m21_notes))):
            sn = m21_notes[i]
            print(f"   {'m21':<10} | {sn.onset:>8.3f} | {sn.duration:>8.3f} | {sn.pitch:>5}")

    aligned = apply_sectional_time_offset(m21_notes, ref_notes)
    m = compare_melodies(ref_notes, aligned)
    print(f"\n3b. music21 ALIGNED:")
    print(f"   pc_f1={m['pitch_class_f1']:.3f}, mel_len={m['melody_f1_lenient']:.3f}, "
          f"contour={m['contour_similarity']:.3f}, notes={len(m21_notes)}")

    # Test 4: Save MusicXML, reload, extract
    tmp_xml = Path("/tmp/test_roundtrip.musicxml")
    score.write("musicxml", fp=str(tmp_xml))
    print(f"\n4a. Saved MusicXML to {tmp_xml}")

    reloaded = music21.converter.parse(str(tmp_xml))
    reload_notes = extract_notes_from_score(reloaded, bpm)
    print(f"   Reloaded {len(reload_notes)} notes")
    if reload_notes:
        print(f"   Onset range: {reload_notes[0].onset:.2f}s - {reload_notes[-1].onset:.2f}s")

        aligned = apply_sectional_time_offset(reload_notes, ref_notes)
        m = compare_melodies(ref_notes, aligned)
        print(f"\n4b. RELOADED ALIGNED:")
        print(f"   pc_f1={m['pitch_class_f1']:.3f}, mel_len={m['melody_f1_lenient']:.3f}, "
              f"contour={m['contour_similarity']:.3f}, notes={len(reload_notes)}")

    # Test 5: Check if pitches are preserved through roundtrip
    if manual_notes and m21_notes:
        pitch_match = sum(1 for a, b in zip(
            sorted(manual_notes, key=lambda n: n.onset),
            sorted(m21_notes, key=lambda n: n.onset)
        ) if a.pitch == b.pitch)
        min_len = min(len(manual_notes), len(m21_notes))
        print(f"\n5. Pitch preservation: {pitch_match}/{min_len} "
              f"({100*pitch_match/min_len:.1f}%) match between manual and music21")


if __name__ == "__main__":
    main()
