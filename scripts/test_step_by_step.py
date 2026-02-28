#!/usr/bin/env python3
"""Isolate which MusicXML processing step destroys pc_f1.

Apply each step one at a time and check pc_f1 after each.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import extract_melody
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies
from core.postprocess import apply_sectional_time_offset
from core.musicxml_writer import _quantize_to_16th
from core.types import Note

TEST_MP3 = Path("test/꿈의 버스.mp3")
TEST_MXL = Path("test/꿈의 버스.mxl")
CACHE_DIR = Path("test/cache")

BPM = 178.2


def eval_notes(gen_notes, ref_notes, label):
    """Evaluate with sectional time offset and print results."""
    aligned = apply_sectional_time_offset(gen_notes, ref_notes)
    m = compare_melodies(ref_notes, aligned)
    print(f"  {label:<45}: notes={len(gen_notes):>3}, pc_f1={m['pitch_class_f1']:.3f}, "
          f"mel_len={m['melody_f1_lenient']:.3f}")
    return m['pitch_class_f1']


def main():
    ref_notes = [n for n in extract_reference_melody(TEST_MXL) if n.duration > 0]
    gen_notes = extract_melody(TEST_MP3, cache_dir=CACHE_DIR)
    gen_notes = [n for n in gen_notes if n.duration > 0]

    print(f"Reference: {len(ref_notes)} notes, onset {min(n.onset for n in ref_notes):.1f}-{max(n.onset for n in ref_notes):.1f}s")
    print(f"Generated: {len(gen_notes)} notes, onset {min(n.onset for n in gen_notes):.1f}-{max(n.onset for n in gen_notes):.1f}s")
    print()

    notes = list(gen_notes)

    # Step 0: Baseline
    eval_notes(notes, ref_notes, "0. Baseline (raw)")

    # Step 1: Strip leading silence
    first_onset = min(n.onset for n in notes)
    if first_onset > 0.1:
        notes1 = [
            Note(pitch=n.pitch, onset=n.onset - first_onset,
                 duration=n.duration, velocity=n.velocity)
            for n in notes
        ]
    else:
        notes1 = list(notes)
    eval_notes(notes1, ref_notes, f"1. Strip silence (-{first_onset:.1f}s)")

    # Step 2: Remove isolated notes
    if len(notes1) >= 3:
        cleaned = [notes1[0]]
        for i in range(1, len(notes1) - 1):
            jb = abs(notes1[i].pitch - notes1[i - 1].pitch)
            ja = abs(notes1[i].pitch - notes1[i + 1].pitch)
            if jb > 7 and ja > 7:
                continue
            cleaned.append(notes1[i])
        cleaned.append(notes1[-1])
        notes2 = cleaned
    else:
        notes2 = list(notes1)
    eval_notes(notes2, ref_notes, f"2. Remove isolated ({len(notes1)-len(notes2)} removed)")

    # Step 3: Merge same-pitch pre-quantization
    merged = [notes2[0]]
    for i in range(1, len(notes2)):
        prev = merged[-1]
        curr = notes2[i]
        gap = curr.onset - (prev.onset + prev.duration)
        if curr.pitch == prev.pitch and gap < 0.15:
            new_dur = (curr.onset + curr.duration) - prev.onset
            merged[-1] = Note(pitch=prev.pitch, onset=prev.onset,
                              duration=new_dur, velocity=prev.velocity)
        else:
            merged.append(curr)
    notes3 = merged
    eval_notes(notes3, ref_notes, f"3. Pre-merge same-pitch ({len(notes2)-len(notes3)} merged)")

    # Step 4: Quantize to 16th grid
    sec_per_q = 60.0 / BPM
    quantized = []
    for n in notes3:
        onset_q = round(n.onset / sec_per_q * 4) / 4
        dur_q = _quantize_to_16th(n.duration / sec_per_q)
        onset_sec = onset_q * sec_per_q
        dur_sec = dur_q * sec_per_q
        quantized.append([onset_sec, dur_sec, n.pitch, n.velocity])

    # Sort by onset, pitch desc
    quantized.sort(key=lambda x: (x[0], -x[2]))

    # Step 5: Dedup same-onset
    deduped = []
    for q in quantized:
        if deduped and abs(q[0] - deduped[-1][0]) < 0.001:
            continue
        deduped.append(q)

    notes4 = [Note(pitch=p, onset=o, duration=d, velocity=v) for o, d, p, v in deduped]
    eval_notes(notes4, ref_notes, f"4+5. Quantize+dedup ({len(notes3)-len(notes4)} removed)")

    # Step 6: Truncate overlaps
    for i in range(len(deduped) - 1):
        gap = deduped[i + 1][0] - deduped[i][0]
        if gap > 0 and deduped[i][1] > gap:
            deduped[i][1] = gap

    # Step 7: Legato fill
    for i in range(len(deduped) - 1):
        note_end = deduped[i][0] + deduped[i][1]
        next_onset = deduped[i + 1][0]
        gap_q = (next_onset - note_end) / sec_per_q  # gap in quarter notes
        if 0 < gap_q <= 0.5:
            deduped[i][1] = next_onset - deduped[i][0]

    # Step 8: Post-merge same-pitch
    final = [deduped[0]]
    for i in range(1, len(deduped)):
        prev = final[-1]
        curr = deduped[i]
        prev_end = prev[0] + prev[1]
        if curr[2] == prev[2] and abs(prev_end - curr[0]) < 0.001:
            final[-1] = [prev[0], curr[0] + curr[1] - prev[0], prev[2], prev[3]]
        else:
            final.append(curr)

    notes5 = [Note(pitch=p, onset=o, duration=d, velocity=v) for o, d, p, v in final]
    eval_notes(notes5, ref_notes, f"6-8. Overlap+legato+merge ({len(notes4)-len(notes5)} changed)")

    # Cross-check: what if we DON'T strip silence but DO merge?
    print()
    print("--- Cross-checks ---")

    # Merge without silence strip
    merged_raw = [gen_notes[0]]
    for i in range(1, len(gen_notes)):
        prev = merged_raw[-1]
        curr = gen_notes[i]
        gap = curr.onset - (prev.onset + prev.duration)
        if curr.pitch == prev.pitch and gap < 0.15:
            new_dur = (curr.onset + curr.duration) - prev.onset
            merged_raw[-1] = Note(pitch=prev.pitch, onset=prev.onset,
                                  duration=new_dur, velocity=prev.velocity)
        else:
            merged_raw.append(curr)
    eval_notes(merged_raw, ref_notes, "Merge only (no silence strip)")

    # Silence strip only (no merge)
    eval_notes(notes1, ref_notes, "Silence strip only (no merge)")


if __name__ == "__main__":
    main()
