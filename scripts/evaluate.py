#!/usr/bin/env python3
"""Evaluate melody extraction pipeline on test songs.

KEY DESIGN (Rule 4 — Output = Evaluation Identity):
1. Pipeline runs and saves MusicXML output
2. MusicXML is loaded back (round-trip) -> gen_notes
3. Reference .mxl is loaded -> ref_notes
4. compare_melodies(ref_notes, gen_notes) — tolerance only, NO transformations

This ensures the evaluated notes are exactly what the MusicXML file contains.
"""

import argparse
import glob
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.comparator import compare_melodies
from core.musicxml_writer import load_musicxml_notes
from core.pipeline import extract_melody
from core.reference_extractor import extract_reference_melody


def evaluate_all_songs(input_dir: Path, output_json: Path, output_dir: Path, mode: str = "crepe"):
    """Evaluate pipeline on all songs in input directory."""

    mp3_files = sorted(glob.glob(str(input_dir / "*.mp3")))
    if not mp3_files:
        print(f"No MP3 files found in {input_dir}")
        return

    print(f"Found {len(mp3_files)} songs to evaluate\n")

    results = {"summary": {}, "songs": {}}

    for mp3_path in mp3_files:
        mp3_path = Path(mp3_path)
        stem = mp3_path.stem
        mxl_path = input_dir / f"{stem}.mxl"

        if not mxl_path.exists():
            print(f"  Skipping {stem}: No matching .mxl file")
            continue

        print(f"Processing: {stem}")
        start_time = time.time()

        try:
            cache_dir = input_dir / "cache"
            musicxml_output = output_dir / f"{stem}.musicxml"

            # Step 1: Run pipeline -> save MusicXML
            extract_melody(
                mp3_path,
                cache_dir=cache_dir,
                output_path=musicxml_output,
                mode=mode,
            )

            # Step 2: Load back (round-trip identity)
            gen_notes = load_musicxml_notes(musicxml_output)

            # Step 3: Load reference
            ref_notes = [
                n for n in extract_reference_melody(mxl_path) if n.duration > 0
            ]

            # Step 4: Compare (NO transformations)
            metrics = compare_melodies(ref_notes, gen_notes)

            processing_time = time.time() - start_time
            results["songs"][stem] = {
                **metrics,
                "processing_time": round(processing_time, 1),
            }

            print(
                f"  mel_strict={metrics['melody_f1_strict']:.3f}  "
                f"mel_lenient={metrics['melody_f1_lenient']:.3f}  "
                f"pc_f1={metrics['pitch_class_f1']:.3f}  "
                f"onset={metrics['onset_f1']:.3f}  "
                f"chroma={metrics['chroma_similarity']:.3f}  "
                f"contour={metrics['contour_similarity']:.3f}  "
                f"notes={metrics['note_counts']['gen']}/{metrics['note_counts']['ref']}  "
                f"time={processing_time:.1f}s"
            )

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Summary
    if results["songs"]:
        n = len(results["songs"])
        for key in [
            "melody_f1_strict",
            "melody_f1_lenient",
            "pitch_class_f1",
            "onset_f1",
            "chroma_similarity",
            "contour_similarity",
        ]:
            results["summary"][f"avg_{key}"] = round(
                sum(s[key] for s in results["songs"].values()) / n, 4
            )
        results["summary"]["total_songs"] = n

    # Save
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary table
    print(f"\n{'=' * 100}")
    print("EVALUATION RESULTS (v1 reset baseline)")
    print(f"{'=' * 100}")

    header = (
        f"{'Song':<30} | {'mel_strict':<10} | {'mel_lenient':<11} | "
        f"{'pc_f1':<6} | {'onset':<6} | {'chroma':<6} | "
        f"{'contour':<7} | {'notes':<12} | {'time':<6}"
    )
    print(header)
    print("-" * 100)

    for stem, m in results["songs"].items():
        nc = m["note_counts"]
        print(
            f"{stem:<30} | {m['melody_f1_strict']:<10.3f} | "
            f"{m['melody_f1_lenient']:<11.3f} | {m['pitch_class_f1']:<6.3f} | "
            f"{m['onset_f1']:<6.3f} | {m['chroma_similarity']:<6.3f} | "
            f"{m['contour_similarity']:<7.3f} | "
            f"{nc['gen']:>4}/{nc['ref']:<6} | {m['processing_time']:<6.1f}s"
        )

    print("-" * 100)
    s = results["summary"]
    print(
        f"{'AVERAGE':<30} | {s.get('avg_melody_f1_strict', 0):<10.3f} | "
        f"{s.get('avg_melody_f1_lenient', 0):<11.3f} | "
        f"{s.get('avg_pitch_class_f1', 0):<6.3f} | "
        f"{s.get('avg_onset_f1', 0):<6.3f} | "
        f"{s.get('avg_chroma_similarity', 0):<6.3f} | "
        f"{s.get('avg_contour_similarity', 0):<7.3f} |"
    )

    print(f"\nResults saved to: {output_json}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate melody extraction pipeline (Rule 4: round-trip evaluation)"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("test"),
        help="Directory with .mp3 and .mxl files (default: test)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/v1_reset.json"),
        help="Output JSON file (default: results/v1_reset.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for MusicXML outputs (default: output/)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="crepe",
        choices=["crepe", "fcpe", "rmvpe", "ensemble", "bp"],
        help="F0 extraction mode (default: crepe)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    evaluate_all_songs(args.input_dir, args.output, args.output_dir, mode=args.mode)


if __name__ == "__main__":
    main()
