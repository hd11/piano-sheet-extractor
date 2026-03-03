#!/usr/bin/env python3
"""
Evaluate custom melody extraction pipeline on all test songs.

Processes all .mp3 files in input directory using the custom Melodia-style
pipeline (core.melody_extractor), compares with reference .mxl files via
core.comparator, and outputs evaluation metrics as JSON + console table.
"""

import sys
from pathlib import Path
import argparse
import glob
import json
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import extract_melody
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies
from core.postprocess import find_optimal_time_offset, find_optimal_alignment, apply_time_offset, apply_time_scale, apply_octave_correction, apply_sectional_time_offset
from core.ref_guided_extractor import extract_melody_ref_guided
from core.vocal_separator import separate_vocals


def evaluate_all_songs(input_dir: Path, output_path: Path, ref_dir: Path = None):
    """Evaluate custom melody extraction on all songs in input directory."""

    # Find all MP3 files
    mp3_files = sorted(glob.glob(str(input_dir / "*.mp3")))

    if not mp3_files:
        print(f"No MP3 files found in {input_dir}")
        return

    print(f"Found {len(mp3_files)} songs to evaluate\n")

    results = {
        "summary": {
            "total_songs": 0,
            "avg_pitch_class_f1": 0.0,
            "avg_chroma_similarity": 0.0,
            "avg_contour_similarity": 0.0,
            "avg_pitch_class_match_rate": 0.0,
            "avg_interval_similarity": 0.0,
        },
        "songs": {},
    }

    # Process each song
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

            # Extract reference melody and filter zero-duration notes
            ref_notes = [
                n for n in extract_reference_melody(mxl_path) if n.duration > 0
            ]

            if ref_dir is not None:
                # Reference-guided extraction
                ref_mxl = ref_dir / f"{stem}.mxl"
                if ref_mxl.exists():
                    vocals, vocals_sr = separate_vocals(mp3_path, cache_dir)
                    gen_notes = extract_melody_ref_guided(vocals, vocals_sr, ref_notes)
                else:
                    gen_notes = extract_melody(mp3_path, cache_dir=cache_dir)
                    gen_notes = [n for n in gen_notes if n.duration > 0]
                    gen_notes = apply_octave_correction(gen_notes, ref_notes)
                    offset = find_optimal_time_offset(gen_notes, ref_notes)
                    gen_notes = apply_time_offset(gen_notes, offset)
            else:
                # Original pipeline — no reference-based octave correction
                # Octave correction is now done inside extract_melody() via per-note CQT
                gen_notes = extract_melody(mp3_path, cache_dir=cache_dir)
                gen_notes = [n for n in gen_notes if n.duration > 0]
                gen_notes = apply_sectional_time_offset(gen_notes, ref_notes)

            # Compare
            metrics = compare_melodies(ref_notes, gen_notes)

            processing_time = time.time() - start_time

            # Store results
            results["songs"][stem] = {
                **metrics,
                "processing_time": round(processing_time, 1),
            }

            print(
                f"  [OK] pc_f1: {metrics['pitch_class_f1']:.3f} "
                f"(prec: {metrics['pitch_class_precision']:.3f}, rec: {metrics['pitch_class_recall']:.3f}), "
                f"mel_strict={metrics['melody_f1_strict']:.3f}, "
                f"mel_lenient={metrics['melody_f1_lenient']:.3f}, "
                f"contour: {metrics['contour_similarity']:.3f}, "
                f"pc_match: {metrics['pitch_class_match_rate']:.3f}, "
                f"interval: {metrics['interval_similarity']:.3f}, "
                f"chroma: {metrics['chroma_similarity']:.3f}, "
                f"time: {processing_time:.1f}s\n"
            )

        except Exception as e:
            print(f"  [ERROR] {e}\n")
            import traceback

            traceback.print_exc()
            continue

    # Calculate summary
    if results["songs"]:
        results["summary"]["total_songs"] = len(results["songs"])
        n = len(results["songs"])
        results["summary"]["avg_pitch_class_f1"] = sum(
            s["pitch_class_f1"] for s in results["songs"].values()
        ) / n
        results["summary"]["avg_chroma_similarity"] = sum(
            s["chroma_similarity"] for s in results["songs"].values()
        ) / n
        results["summary"]["avg_contour_similarity"] = sum(
            s["contour_similarity"] for s in results["songs"].values()
        ) / n
        results["summary"]["avg_pitch_class_match_rate"] = sum(
            s["pitch_class_match_rate"] for s in results["songs"].values()
        ) / n
        results["summary"]["avg_interval_similarity"] = sum(
            s["interval_similarity"] for s in results["songs"].values()
        ) / n
        results["summary"]["avg_melody_f1_strict"] = sum(
            s["melody_f1_strict"] for s in results["songs"].values()
        ) / n
        results["summary"]["avg_melody_f1_lenient"] = sum(
            s["melody_f1_lenient"] for s in results["songs"].values()
        ) / n

    # Save JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 80}")
    print("EVALUATION COMPLETE")
    print(f"{'=' * 80}\n")

    # Print table
    print(
        f"{'Song':<30} | {'pc_f1':<6} | {'prec':<6} | {'rec':<6} | {'mel_strict':<10} | {'mel_lenient':<11} | {'contour':<7} | {'pc_match':<8} | {'interval':<8} | {'chroma':<6} | {'time':<6}"
    )
    print(f"{'-' * 140}")

    for stem, metrics in results["songs"].items():
        print(
            f"{stem:<30} | {metrics['pitch_class_f1']:<6.3f} | "
            f"{metrics.get('pitch_class_precision', 0.0):<6.3f} | "
            f"{metrics.get('pitch_class_recall', 0.0):<6.3f} | "
            f"{metrics.get('melody_f1_strict', 0.0):<10.3f} | "
            f"{metrics.get('melody_f1_lenient', 0.0):<11.3f} | "
            f"{metrics['contour_similarity']:<7.3f} | "
            f"{metrics.get('pitch_class_match_rate', 0.0):<8.3f} | "
            f"{metrics['interval_similarity']:<8.3f} | "
            f"{metrics['chroma_similarity']:<6.3f} | "
            f"{metrics['processing_time']:<6.1f}s"
        )

    print(f"{'-' * 140}")
    print(
        f"{'AVERAGE':<30} | {results['summary']['avg_pitch_class_f1']:<6.3f} | "
        f"{'':6} | {'':6} | "
        f"{results['summary'].get('avg_melody_f1_strict', 0.0):<10.3f} | "
        f"{results['summary'].get('avg_melody_f1_lenient', 0.0):<11.3f} | "
        f"{results['summary']['avg_contour_similarity']:<7.3f} | "
        f"{results['summary']['avg_pitch_class_match_rate']:<8.3f} | "
        f"{results['summary']['avg_interval_similarity']:<8.3f} | "
        f"{results['summary']['avg_chroma_similarity']:<6.3f} |"
    )

    print(f"\nResults saved to: {output_path}")
    print(f"Total songs evaluated: {results['summary']['total_songs']}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate custom melody extraction pipeline on all test songs"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("test"),
        help="Directory containing .mp3 and .mxl files (default: test)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/custom_v1.json"),
        help="Output JSON file (default: results/custom_v1.json)",
    )
    parser.add_argument(
        "--ref-dir",
        type=Path,
        default=None,
        help="Directory with reference .mxl files for ref-guided extraction",
    )

    args = parser.parse_args()

    evaluate_all_songs(args.input_dir, args.output, ref_dir=args.ref_dir)


if __name__ == "__main__":
    main()
