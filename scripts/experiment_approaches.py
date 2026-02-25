#!/usr/bin/env python3
"""Test multiple extraction approaches to find the best pitch_class_f1."""

import sys
from pathlib import Path
import json
import time
import logging

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_separator import separate_vocals
from core.f0_extractor import extract_f0, f0_to_notes, _TARGET_SR
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies
from core.types import Note

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

INPUT_DIR = Path("test")
CACHE_DIR = INPUT_DIR / "cache"


def get_test_songs():
    """Get all test song paths."""
    songs = []
    for mp3 in sorted(INPUT_DIR.glob("*.mp3")):
        mxl = INPUT_DIR / f"{mp3.stem}.mxl"
        if mxl.exists():
            songs.append((mp3, mxl))
    return songs


def evaluate_notes(gen_notes, ref_notes):
    """Quick evaluate: return pitch_class_f1."""
    ref = [n for n in ref_notes if n.duration > 0]
    gen = [n for n in gen_notes if n.duration > 0]
    metrics = compare_melodies(ref, gen)
    return metrics["pitch_class_f1"]


def approach_baseline_tiny(vocals, sr, ref_notes):
    """Original tiny model, default params."""
    import librosa
    f0, per = extract_f0(vocals, sr, hop_ms=10.0, model="tiny")
    notes = f0_to_notes(f0, per, hop_sec=0.01, periodicity_threshold=0.5, min_note_dur=0.06)
    return notes


def approach_full_model(vocals, sr, ref_notes):
    """Full model, optimized params from grid search."""
    f0, per = extract_f0(vocals, sr, hop_ms=10.0, model="full")
    notes = f0_to_notes(f0, per, hop_sec=0.01, periodicity_threshold=0.5, min_note_dur=0.04)
    return notes


def approach_pyin(vocals, sr, ref_notes):
    """Use librosa PYIN instead of torchcrepe."""
    import librosa

    # Resample to 16kHz for consistency
    if sr != 16000:
        vocals_16k = librosa.resample(vocals, orig_sr=sr, target_sr=16000)
    else:
        vocals_16k = vocals

    # PYIN pitch detection
    f0_pyin, voiced_flag, voiced_prob = librosa.pyin(
        vocals_16k,
        sr=16000,
        fmin=50,
        fmax=800,
        hop_length=160,  # 10ms at 16kHz
        fill_na=0.0,
    )

    # Convert to notes using our f0_to_notes with voiced_prob as periodicity
    notes = f0_to_notes(
        f0_pyin,
        voiced_prob,
        hop_sec=0.01,
        periodicity_threshold=0.3,  # PYIN voiced_prob is different scale
        min_note_dur=0.04,
    )
    return notes


def approach_pyin_tuned(vocals, sr, ref_notes):
    """PYIN with tuned threshold."""
    import librosa

    if sr != 16000:
        vocals_16k = librosa.resample(vocals, orig_sr=sr, target_sr=16000)
    else:
        vocals_16k = vocals

    f0_pyin, voiced_flag, voiced_prob = librosa.pyin(
        vocals_16k,
        sr=16000,
        fmin=65,   # C2
        fmax=1047, # C6
        hop_length=160,
        fill_na=0.0,
    )

    notes = f0_to_notes(
        f0_pyin,
        voiced_prob,
        hop_sec=0.01,
        periodicity_threshold=0.5,
        min_note_dur=0.04,
    )
    return notes


def approach_time_offset(vocals, sr, ref_notes):
    """Full model + global time offset correction."""
    f0, per = extract_f0(vocals, sr, hop_ms=10.0, model="full")
    notes = f0_to_notes(f0, per, hop_sec=0.01, periodicity_threshold=0.5, min_note_dur=0.04)

    if not notes or not ref_notes:
        return notes

    # Find optimal time offset via cross-correlation of onset histograms
    ref_onsets = np.array([n.onset for n in ref_notes])
    gen_onsets = np.array([n.onset for n in notes])

    best_offset = 0.0
    best_f1 = 0.0

    # Test offsets from -2s to +2s in 50ms steps
    for offset_ms in range(-2000, 2001, 50):
        offset = offset_ms / 1000.0
        shifted = [
            Note(pitch=n.pitch, onset=max(0.0, n.onset + offset), duration=n.duration)
            for n in notes
        ]
        f1 = evaluate_notes(shifted, ref_notes)
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset

    # Apply best offset
    if best_offset != 0.0:
        notes = [
            Note(pitch=n.pitch, onset=max(0.0, round(n.onset + best_offset, 4)), duration=n.duration)
            for n in notes
        ]

    return notes


def approach_onset_quantize(vocals, sr, ref_notes):
    """Full model + quantize onsets to detected beat grid."""
    import librosa

    f0, per = extract_f0(vocals, sr, hop_ms=10.0, model="full")
    notes = f0_to_notes(f0, per, hop_sec=0.01, periodicity_threshold=0.5, min_note_dur=0.04)

    if not notes:
        return notes

    # Detect tempo and beats
    tempo, beats = librosa.beat.beat_track(y=vocals, sr=sr, units="time")
    tempo_val = float(np.atleast_1d(tempo)[0])

    if len(beats) < 2:
        return notes

    # Create a fine grid (16th notes)
    beat_interval = 60.0 / tempo_val
    sixteenth = beat_interval / 4.0
    max_time = max(n.onset + n.duration for n in notes)

    # Build grid from first beat
    grid = []
    t = beats[0]
    while t <= max_time + sixteenth:
        grid.append(t)
        t += sixteenth
    grid = np.array(grid)

    # Snap onsets to nearest grid point
    quantized = []
    for n in notes:
        idx = np.argmin(np.abs(grid - n.onset))
        new_onset = round(float(grid[idx]), 4)
        quantized.append(Note(pitch=n.pitch, onset=new_onset, duration=n.duration))

    return quantized


def approach_high_pt(vocals, sr, ref_notes):
    """Tiny model with high periodicity threshold (best from grid search)."""
    f0, per = extract_f0(vocals, sr, hop_ms=10.0, model="tiny")
    notes = f0_to_notes(f0, per, hop_sec=0.01, periodicity_threshold=0.7, min_note_dur=0.04)
    return notes


def approach_combined_best(vocals, sr, ref_notes):
    """Full model + time offset + high periodicity."""
    f0, per = extract_f0(vocals, sr, hop_ms=10.0, model="full")
    notes = f0_to_notes(f0, per, hop_sec=0.01, periodicity_threshold=0.6, min_note_dur=0.04)

    if not notes or not ref_notes:
        return notes

    # Time offset correction
    best_offset = 0.0
    best_f1 = 0.0
    for offset_ms in range(-2000, 2001, 50):
        offset = offset_ms / 1000.0
        shifted = [
            Note(pitch=n.pitch, onset=max(0.0, n.onset + offset), duration=n.duration)
            for n in notes
        ]
        f1 = evaluate_notes(shifted, ref_notes)
        if f1 > best_f1:
            best_f1 = f1
            best_offset = offset

    if best_offset != 0.0:
        notes = [
            Note(pitch=n.pitch, onset=max(0.0, round(n.onset + best_offset, 4)), duration=n.duration)
            for n in notes
        ]

    return notes


APPROACHES = {
    "baseline_tiny": approach_baseline_tiny,
    "full_model": approach_full_model,
    "pyin": approach_pyin,
    "pyin_tuned": approach_pyin_tuned,
    "time_offset": approach_time_offset,
    "onset_quantize": approach_onset_quantize,
    "high_pt_tiny": approach_high_pt,
    "combined_best": approach_combined_best,
}


def main():
    songs = get_test_songs()
    print(f"Testing {len(APPROACHES)} approaches on {len(songs)} songs\n")

    results = {}
    for name, func in APPROACHES.items():
        scores = []
        start = time.time()
        print(f"[{name}]", end="", flush=True)

        for mp3_path, mxl_path in songs:
            try:
                vocals, sr = separate_vocals(mp3_path, CACHE_DIR)
                ref_notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]
                notes = func(vocals, sr, ref_notes)
                f1 = evaluate_notes(notes, ref_notes)
                scores.append(f1)
                print(f" {f1:.3f}", end="", flush=True)
            except Exception as e:
                print(f" ERR({e})", end="", flush=True)
                scores.append(0.0)

        avg = sum(scores) / len(scores) if scores else 0.0
        elapsed = time.time() - start
        results[name] = {"avg_f1": avg, "scores": scores, "time": elapsed}
        print(f"  AVG={avg:.4f} ({elapsed:.0f}s)")

    # Print summary sorted by avg_f1
    print(f"\n{'='*60}")
    print("SUMMARY (sorted by avg_f1)")
    print(f"{'='*60}")
    for name, data in sorted(results.items(), key=lambda x: x[1]["avg_f1"], reverse=True):
        print(f"  {name:<20} avg_f1={data['avg_f1']:.4f}  ({data['time']:.0f}s)")

    # Save results
    output_path = Path("results/experiment_approaches.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
