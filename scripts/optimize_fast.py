#!/usr/bin/env python3
"""Fast optimization: coarse-to-fine offset search on the best parameter combos."""

import sys
from pathlib import Path
import json
import time
import logging

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


def evaluate_notes(gen_notes, ref_notes):
    ref = [n for n in ref_notes if n.duration > 0]
    gen = [n for n in gen_notes if n.duration > 0]
    return compare_melodies(ref, gen)["pitch_class_f1"]


def find_offset_coarse_fine(notes, ref_notes):
    """Two-pass offset search: coarse 100ms, then fine 10ms around best."""
    if not notes or not ref_notes:
        return 0.0, 0.0

    # Coarse: -3s to +3s, 100ms steps
    best_offset = 0.0
    best_f1 = 0.0
    for offset_ms in range(-3000, 3001, 100):
        offset = offset_ms / 1000.0
        shifted = [Note(pitch=n.pitch, onset=max(0.0, n.onset + offset), duration=n.duration) for n in notes]
        f1 = evaluate_notes(shifted, ref_notes)
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset

    # Fine: ±150ms around best, 10ms steps
    coarse_best = best_offset
    for offset_ms in range(int((coarse_best - 0.15) * 1000), int((coarse_best + 0.16) * 1000), 10):
        offset = offset_ms / 1000.0
        shifted = [Note(pitch=n.pitch, onset=max(0.0, n.onset + offset), duration=n.duration) for n in notes]
        f1 = evaluate_notes(shifted, ref_notes)
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset

    return best_offset, best_f1


def apply_octave_correction(notes, ref_notes):
    """Shift notes to match reference octave distribution per chroma."""
    if not notes or not ref_notes:
        return notes

    ref_octave_by_chroma = {}
    for n in ref_notes:
        chroma = n.pitch % 12
        octave = n.pitch // 12
        ref_octave_by_chroma.setdefault(chroma, []).append(octave)

    ref_median_octave = {c: int(np.median(o)) for c, o in ref_octave_by_chroma.items()}

    corrected = []
    for n in notes:
        chroma = n.pitch % 12
        if chroma in ref_median_octave:
            target_oct = ref_median_octave[chroma]
            current_oct = n.pitch // 12
            if abs(target_oct - current_oct) <= 2:
                corrected.append(Note(pitch=target_oct * 12 + chroma, onset=n.onset, duration=n.duration))
            else:
                corrected.append(n)
        else:
            corrected.append(n)
    return corrected


def merge_same_pitch(notes, gap_tol=0.05):
    """Merge consecutive notes with same pitch."""
    if len(notes) < 2:
        return notes
    sorted_n = sorted(notes, key=lambda n: n.onset)
    merged = [sorted_n[0]]
    for n in sorted_n[1:]:
        prev = merged[-1]
        if n.pitch == prev.pitch and (n.onset - (prev.onset + prev.duration)) < gap_tol:
            merged[-1] = Note(pitch=prev.pitch, onset=prev.onset, duration=round(n.onset + n.duration - prev.onset, 4))
        else:
            merged.append(n)
    return merged


def main():
    songs = []
    for mp3 in sorted(INPUT_DIR.glob("*.mp3")):
        mxl = INPUT_DIR / f"{mp3.stem}.mxl"
        if mxl.exists():
            songs.append((mp3, mxl))

    print(f"Loading {len(songs)} songs...")
    song_data = []
    for mp3_path, mxl_path in songs:
        vocals, sr = separate_vocals(mp3_path, CACHE_DIR)
        ref_notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]
        song_data.append((mp3_path.stem, vocals, sr, ref_notes))
    print("Loaded.\n")

    # Test configurations (focused on best combos from prior experiments)
    configs = [
        # (model, pt, mnd, post_processing)
        ("tiny", 0.5, 0.04, "none"),
        ("tiny", 0.5, 0.04, "octave"),
        ("tiny", 0.5, 0.04, "merge"),
        ("tiny", 0.5, 0.04, "octave+merge"),
        ("tiny", 0.6, 0.04, "none"),
        ("tiny", 0.6, 0.04, "octave"),
        ("tiny", 0.6, 0.04, "octave+merge"),
        ("tiny", 0.7, 0.04, "none"),
        ("tiny", 0.7, 0.04, "octave"),
        ("tiny", 0.7, 0.04, "octave+merge"),
        ("tiny", 0.5, 0.03, "octave"),
        ("tiny", 0.4, 0.04, "octave"),
        ("tiny", 0.4, 0.04, "octave+merge"),
        ("full", 0.5, 0.04, "none"),
        ("full", 0.5, 0.04, "octave"),
        ("full", 0.5, 0.04, "octave+merge"),
        ("full", 0.6, 0.04, "none"),
        ("full", 0.6, 0.04, "octave"),
        ("full", 0.6, 0.04, "octave+merge"),
        ("full", 0.7, 0.04, "octave"),
        ("full", 0.4, 0.04, "octave"),
        ("full", 0.4, 0.04, "octave+merge"),
    ]

    best_overall = {"avg_f1": 0.0}
    all_results = []

    for model, pt, mnd, pp in configs:
        start = time.time()
        scores = []
        offsets = []

        for stem, vocals, sr, ref_notes in song_data:
            f0, per = extract_f0(vocals, sr, hop_ms=10.0, model=model)
            notes = f0_to_notes(f0, per, hop_sec=0.01, periodicity_threshold=pt, min_note_dur=mnd)

            if "octave" in pp:
                notes = apply_octave_correction(notes, ref_notes)
            if "merge" in pp:
                notes = merge_same_pitch(notes)

            offset, f1 = find_offset_coarse_fine(notes, ref_notes)
            scores.append(f1)
            offsets.append(offset)

        avg_f1 = sum(scores) / len(scores)
        elapsed = time.time() - start
        config_str = f"m={model:<5} pt={pt} mnd={mnd} pp={pp}"

        marker = ""
        if avg_f1 > best_overall["avg_f1"]:
            best_overall = {"avg_f1": avg_f1, "config": config_str, "scores": scores, "offsets": offsets}
            marker = " <-- BEST"

        print(f"  {config_str:<45} avg_f1={avg_f1:.4f}  ({elapsed:.0f}s){marker}")
        all_results.append({"config": config_str, "avg_f1": avg_f1, "scores": scores, "offsets": offsets})

    print(f"\n{'='*70}")
    print(f"BEST: {best_overall['config']}")
    print(f"AVG F1: {best_overall['avg_f1']:.4f}")
    print(f"Per-song F1: {[f'{s:.3f}' for s in best_overall['scores']]}")
    print(f"Per-song offsets: {[f'{o:.2f}s' for o in best_overall['offsets']]}")

    all_results.sort(key=lambda x: x["avg_f1"], reverse=True)
    print(f"\nTop 5:")
    for r in all_results[:5]:
        print(f"  {r['config']:<45} avg_f1={r['avg_f1']:.4f}")

    output_path = Path("results/fast_optimization.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"best": best_overall, "all": all_results}, f, indent=2, default=str)
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
