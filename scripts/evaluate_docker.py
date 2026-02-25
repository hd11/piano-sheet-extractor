#!/usr/bin/env python3
"""Evaluate Demucs+torchcrepe pipeline (designed for Docker/Linux).

Uses the new vocal_melody_extractor pipeline which chains:
    Demucs vocal separation → torchcrepe F0 → note segmentation

Results are saved as JSON with per-song and summary metrics.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import extract_melody
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies


def main():
    input_dir = Path("/data/test")
    output_path = Path("/data/results/docker_demucs_v1.json")
    cache_dir = input_dir / "cache"

    mp3_files = sorted(input_dir.glob("*.mp3"))
    print(f"Found {len(mp3_files)} songs\n")

    results = {"summary": {}, "songs": {}}

    for mp3 in mp3_files:
        mxl = input_dir / f"{mp3.stem}.mxl"
        if not mxl.exists():
            print(f"  Skip {mp3.stem}: no .mxl")
            continue

        print(f"Processing: {mp3.stem}...", flush=True)
        t0 = time.time()
        try:
            gen_notes = extract_melody(mp3, cache_dir=cache_dir)
            ref_notes = [n for n in extract_reference_melody(mxl) if n.duration > 0]
            gen_notes = [n for n in gen_notes if n.duration > 0]
            metrics = compare_melodies(ref_notes, gen_notes)
            dt = time.time() - t0

            results["songs"][mp3.stem] = {**metrics, "processing_time": round(dt, 1)}
            print(
                f"  pc_f1={metrics['pitch_class_f1']:.3f}  "
                f"chroma={metrics['chroma_similarity']:.3f}  "
                f"notes={metrics['note_counts']['gen']}/{metrics['note_counts']['ref']}  "
                f"{dt:.1f}s\n"
            )
        except Exception as e:
            print(f"  ERROR: {e}\n")
            import traceback
            traceback.print_exc()

    if results["songs"]:
        n = len(results["songs"])
        keys = ["pitch_class_f1", "chroma_similarity", "melody_f1_lenient", "onset_f1"]
        results["summary"]["total_songs"] = n
        for k in keys:
            results["summary"][f"avg_{k}"] = (
                sum(s.get(k, 0) for s in results["songs"].values()) / n
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("=" * 80)
    print("RESULTS SUMMARY (Demucs + torchcrepe pipeline)")
    print("=" * 80)
    for k, v in results["summary"].items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
