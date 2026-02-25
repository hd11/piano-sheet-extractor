#!/usr/bin/env python3
"""Grid search over periodicity_threshold and min_note_dur."""

import sys
from pathlib import Path
import json
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import extract_melody
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies

INPUT_DIR = Path("test")
CACHE_DIR = INPUT_DIR / "cache"

# Grid search parameters
PERIODICITY_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]
MIN_NOTE_DURS = [0.04, 0.06, 0.08, 0.10]


def evaluate_params(periodicity_threshold: float, min_note_dur: float) -> dict:
    """Evaluate a parameter combination on all songs."""
    mp3_files = sorted(INPUT_DIR.glob("*.mp3"))
    scores = []

    for mp3_path in mp3_files:
        mxl_path = INPUT_DIR / f"{mp3_path.stem}.mxl"
        if not mxl_path.exists():
            continue

        try:
            gen_notes = extract_melody(
                mp3_path,
                cache_dir=CACHE_DIR,
                periodicity_threshold=periodicity_threshold,
                min_note_dur=min_note_dur,
            )
            ref_notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]
            gen_notes = [n for n in gen_notes if n.duration > 0]

            metrics = compare_melodies(ref_notes, gen_notes)
            scores.append(metrics["pitch_class_f1"])
        except Exception as e:
            print(f"  ERROR on {mp3_path.stem}: {e}")
            scores.append(0.0)

    avg = sum(scores) / len(scores) if scores else 0.0
    return {"avg_f1": avg, "scores": scores}


def main():
    print("Parameter Grid Search")
    print("=" * 70)

    results = {}
    best_avg = 0.0
    best_params = None

    for pt in PERIODICITY_THRESHOLDS:
        for mnd in MIN_NOTE_DURS:
            key = f"pt={pt:.1f}_mnd={mnd:.2f}"
            start = time.time()
            result = evaluate_params(pt, mnd)
            elapsed = time.time() - start

            results[key] = result
            avg = result["avg_f1"]

            marker = ""
            if avg > best_avg:
                best_avg = avg
                best_params = (pt, mnd)
                marker = " <-- BEST"

            print(f"  pt={pt:.1f}  mnd={mnd:.2f}  avg_f1={avg:.4f}  ({elapsed:.1f}s){marker}")

    print(f"\n{'=' * 70}")
    print(f"BEST: periodicity_threshold={best_params[0]:.1f}, min_note_dur={best_params[1]:.2f}")
    print(f"      avg_pitch_class_f1 = {best_avg:.4f}")

    # Save results
    output_path = Path("results/tuning_grid.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"best_params": {"periodicity_threshold": best_params[0], "min_note_dur": best_params[1]},
                    "best_avg_f1": best_avg, "grid": results}, f, indent=2)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
