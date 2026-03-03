#!/usr/bin/env python3
"""Analyze reference .mxl files for development insights.

Extracts patterns from reference piano arrangements:
- Pitch range and distribution
- Note density and tempo
- Key signature detection
- Melody vs accompaniment separation quality
"""

import argparse
import glob
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.reference_extractor import extract_reference_melody, get_reference_bpm
from core.types import Note


def analyze_song(mxl_path: Path) -> dict:
    """Analyze a single reference .mxl file."""
    notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]
    bpm = get_reference_bpm(mxl_path)

    if not notes:
        return {"error": "No notes extracted"}

    pitches = np.array([n.pitch for n in notes])
    durations = np.array([n.duration for n in notes])
    onsets = np.array([n.onset for n in notes])

    total_duration = onsets[-1] + durations[-1] - onsets[0]
    notes_per_second = len(notes) / total_duration if total_duration > 0 else 0

    # Pitch class distribution
    pc_hist = np.zeros(12)
    for n in notes:
        pc_hist[n.pitch % 12] += n.duration
    pc_hist /= pc_hist.sum() + 1e-10

    pc_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    top_pcs = sorted(range(12), key=lambda i: pc_hist[i], reverse=True)[:5]

    # Interval distribution
    intervals = np.diff(pitches)
    abs_intervals = np.abs(intervals)

    return {
        "bpm": bpm,
        "note_count": len(notes),
        "duration_sec": round(total_duration, 1),
        "notes_per_second": round(notes_per_second, 2),
        "pitch_range": {
            "min": int(pitches.min()),
            "max": int(pitches.max()),
            "median": int(np.median(pitches)),
            "std": round(float(np.std(pitches)), 1),
        },
        "duration_stats": {
            "min_ms": round(float(durations.min()) * 1000, 0),
            "max_ms": round(float(durations.max()) * 1000, 0),
            "median_ms": round(float(np.median(durations)) * 1000, 0),
            "mean_ms": round(float(np.mean(durations)) * 1000, 0),
        },
        "top_pitch_classes": [pc_names[i] for i in top_pcs],
        "interval_stats": {
            "mean_semitones": round(float(np.mean(abs_intervals)), 2),
            "max_semitones": int(abs_intervals.max()) if len(abs_intervals) > 0 else 0,
            "pct_stepwise": round(float(np.mean(abs_intervals <= 2)) * 100, 1),
            "pct_octave_jumps": round(float(np.mean(abs_intervals >= 10)) * 100, 1),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze reference .mxl files for development insights"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("test"),
        help="Directory with .mxl files (default: test)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file (optional)",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    mxl_files = sorted(glob.glob(str(args.input_dir / "*.mxl")))
    if not mxl_files:
        print(f"No .mxl files found in {args.input_dir}")
        return

    print(f"Analyzing {len(mxl_files)} reference files\n")

    results = {}
    for mxl_path in mxl_files:
        mxl_path = Path(mxl_path)
        stem = mxl_path.stem
        print(f"Analyzing: {stem}")

        try:
            analysis = analyze_song(mxl_path)
            results[stem] = analysis

            pr = analysis["pitch_range"]
            ds = analysis["duration_stats"]
            iv = analysis["interval_stats"]
            print(
                f"  BPM={analysis['bpm']:.0f}  "
                f"notes={analysis['note_count']}  "
                f"n/s={analysis['notes_per_second']:.1f}  "
                f"pitch={pr['min']}-{pr['max']} (med={pr['median']})  "
                f"dur={ds['median_ms']:.0f}ms  "
                f"step={iv['pct_stepwise']:.0f}%  "
                f"keys={','.join(analysis['top_pitch_classes'][:3])}"
            )
        except Exception as e:
            print(f"  ERROR: {e}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
