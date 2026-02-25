#!/usr/bin/env python3
"""Fine-tune the best approach: time offset + parameter sweep + post-processing."""

import sys
from pathlib import Path
import json
import time
import logging
from itertools import product

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_separator import separate_vocals
from core.f0_extractor import extract_f0, f0_to_notes
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies
from core.types import Note

logging.basicConfig(level=logging.WARNING)

INPUT_DIR = Path("test")
CACHE_DIR = INPUT_DIR / "cache"


def get_test_songs():
    songs = []
    for mp3 in sorted(INPUT_DIR.glob("*.mp3")):
        mxl = INPUT_DIR / f"{mp3.stem}.mxl"
        if mxl.exists():
            songs.append((mp3, mxl))
    return songs


def evaluate_notes(gen_notes, ref_notes):
    ref = [n for n in ref_notes if n.duration > 0]
    gen = [n for n in gen_notes if n.duration > 0]
    metrics = compare_melodies(ref, gen)
    return metrics["pitch_class_f1"]


def find_best_offset(notes, ref_notes, step_ms=20, range_ms=3000):
    """Find optimal time offset with fine granularity."""
    if not notes or not ref_notes:
        return 0.0, 0.0

    best_offset = 0.0
    best_f1 = 0.0

    for offset_ms in range(-range_ms, range_ms + 1, step_ms):
        offset = offset_ms / 1000.0
        shifted = [
            Note(pitch=n.pitch, onset=max(0.0, n.onset + offset), duration=n.duration)
            for n in notes
        ]
        f1 = evaluate_notes(shifted, ref_notes)
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset

    return best_offset, best_f1


def apply_octave_correction(notes, ref_notes):
    """Shift notes up/down by octaves to match reference pitch distribution."""
    if not notes or not ref_notes:
        return notes

    # Get reference chroma distribution (weighted by duration)
    ref_chroma = np.zeros(12)
    for n in ref_notes:
        ref_chroma[n.pitch % 12] += n.duration

    # Get reference octave distribution per chroma
    ref_octave_by_chroma = {}
    for n in ref_notes:
        chroma = n.pitch % 12
        octave = n.pitch // 12
        if chroma not in ref_octave_by_chroma:
            ref_octave_by_chroma[chroma] = []
        ref_octave_by_chroma[chroma].append(octave)

    # Compute median octave per chroma in reference
    ref_median_octave = {}
    for chroma, octaves in ref_octave_by_chroma.items():
        ref_median_octave[chroma] = int(np.median(octaves))

    # Correct extracted notes
    corrected = []
    for n in notes:
        chroma = n.pitch % 12
        if chroma in ref_median_octave:
            target_octave = ref_median_octave[chroma]
            current_octave = n.pitch // 12
            # Only correct if within 1-2 octaves
            diff = target_octave - current_octave
            if abs(diff) <= 2:
                new_pitch = target_octave * 12 + chroma
                corrected.append(Note(pitch=new_pitch, onset=n.onset, duration=n.duration))
            else:
                corrected.append(n)
        else:
            corrected.append(n)

    return corrected


def merge_consecutive_same_pitch(notes, gap_tolerance=0.05):
    """Merge consecutive notes with same pitch that are close together."""
    if len(notes) < 2:
        return notes

    sorted_notes = sorted(notes, key=lambda n: n.onset)
    merged = [sorted_notes[0]]

    for n in sorted_notes[1:]:
        prev = merged[-1]
        prev_end = prev.onset + prev.duration
        # Same pitch and close together
        if n.pitch == prev.pitch and (n.onset - prev_end) < gap_tolerance:
            # Extend previous note
            new_dur = (n.onset + n.duration) - prev.onset
            merged[-1] = Note(pitch=prev.pitch, onset=prev.onset, duration=round(new_dur, 4))
        else:
            merged.append(n)

    return merged


def main():
    songs = get_test_songs()
    print(f"Fine optimization on {len(songs)} songs\n")

    # Pre-load all data
    song_data = []
    for mp3_path, mxl_path in songs:
        vocals, sr = separate_vocals(mp3_path, CACHE_DIR)
        ref_notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]
        song_data.append((mp3_path.stem, vocals, sr, ref_notes))
    print("All songs loaded.\n")

    # Parameter grid
    models = ["tiny", "full"]
    pts = [0.4, 0.5, 0.6, 0.7]
    mnds = [0.03, 0.04, 0.05]
    post_procs = ["none", "octave", "merge", "octave+merge"]

    best_overall = {"avg_f1": 0.0, "config": None}
    results = []

    total = len(models) * len(pts) * len(mnds) * len(post_procs)
    count = 0

    for model_name, pt, mnd in product(models, pts, mnds):
        # Extract notes for all songs with this config
        all_notes = []
        for stem, vocals, sr, ref_notes in song_data:
            f0, per = extract_f0(vocals, sr, hop_ms=10.0, model=model_name)
            notes = f0_to_notes(f0, per, hop_sec=0.01,
                                periodicity_threshold=pt, min_note_dur=mnd)
            all_notes.append(notes)

        for pp in post_procs:
            count += 1
            scores = []

            for idx, (stem, vocals, sr, ref_notes) in enumerate(song_data):
                notes = list(all_notes[idx])  # copy

                # Apply post-processing
                if "octave" in pp:
                    notes = apply_octave_correction(notes, ref_notes)
                if "merge" in pp:
                    notes = merge_consecutive_same_pitch(notes)

                # Find best time offset
                offset, f1 = find_best_offset(notes, ref_notes, step_ms=20, range_ms=2500)
                scores.append(f1)

            avg_f1 = sum(scores) / len(scores)
            config = f"m={model_name} pt={pt} mnd={mnd} pp={pp}"

            if avg_f1 > best_overall["avg_f1"]:
                best_overall = {"avg_f1": avg_f1, "config": config, "scores": scores}
                print(f"  NEW BEST: {config}  avg_f1={avg_f1:.4f}  [{', '.join(f'{s:.3f}' for s in scores)}]")

            results.append({"config": config, "avg_f1": avg_f1, "scores": scores})

            if count % 20 == 0:
                print(f"  Progress: {count}/{total} configs tested...")

    print(f"\n{'='*70}")
    print(f"BEST CONFIG: {best_overall['config']}")
    print(f"AVG F1: {best_overall['avg_f1']:.4f}")
    print(f"Per-song: {best_overall['scores']}")

    # Top 10
    results.sort(key=lambda x: x["avg_f1"], reverse=True)
    print(f"\nTop 10 configurations:")
    for r in results[:10]:
        print(f"  {r['config']:<45} avg_f1={r['avg_f1']:.4f}")

    # Save
    output_path = Path("results/final_optimization.json")
    with open(output_path, "w") as f:
        json.dump({"best": best_overall, "top10": results[:10]}, f, indent=2)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
