#!/usr/bin/env python3
"""
Measure melody extraction F1 baseline.

This script measures the F1 score for melody extraction by:
1. Extracting reference melody from reference.mxl
2. Extracting generated melody from audio via pipeline
3. Computing composite metrics (melody_f1, melody_f1_lenient, etc.)
4. Reporting per-song and average F1 scores
"""

import sys
from pathlib import Path
import json
import time

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from core.audio_to_midi import convert_audio_to_midi
from core.melody_extractor import extract_melody
from core.musicxml_melody_extractor import extract_melody_from_musicxml
from core.comparison_utils import NoteEvent, compute_composite_metrics


def run_melody_baseline_measurement():
    """Measure melody F1 baseline for all 8 songs."""

    golden_data_dir = Path(__file__).parent / "tests" / "golden" / "data"

    if not golden_data_dir.exists():
        print(f"ERROR: Golden data directory not found: {golden_data_dir}")
        return None

    song_ids = [f"song_{i:02d}" for i in range(1, 9)]
    results = []

    print("\n" + "=" * 90)
    print("MELODY EXTRACTION F1 BASELINE MEASUREMENT")
    print("=" * 90)
    print(
        f"{'Song':<10} {'Status':<12} {'Melody F1':>12} {'F1 Lenient':>12} "
        f"{'PC F1':>10} {'Chroma':>10} {'Onset F1':>10}"
    )
    print("-" * 90)

    for song_id in song_ids:
        song_path = golden_data_dir / song_id
        input_mp3 = song_path / "input.mp3"
        reference_mxl = song_path / "reference.mxl"

        if not input_mp3.exists() or not reference_mxl.exists():
            print(f"{song_id:<10} {'SKIPPED':<12} (missing files)")
            results.append({"song_id": song_id, "status": "SKIPPED"})
            continue

        try:
            start_time = time.time()

            # Step 1: Extract reference melody from reference.mxl
            ref_melody = extract_melody_from_musicxml(str(reference_mxl))
            if not ref_melody:
                print(f"{song_id:<10} {'ERROR':<12} (no ref melody)")
                results.append(
                    {"song_id": song_id, "status": "ERROR", "error": "no ref melody"}
                )
                continue

            # Step 2: Generate MIDI from audio
            temp_midi = Path(f"/tmp/{song_id}_raw.mid")
            temp_midi.parent.mkdir(exist_ok=True)
            convert_audio_to_midi(input_mp3, temp_midi)

            # Step 3: Extract generated melody
            gen_melody = extract_melody(temp_midi)
            if not gen_melody:
                print(f"{song_id:<10} {'ERROR':<12} (no gen melody)")
                results.append(
                    {"song_id": song_id, "status": "ERROR", "error": "no gen melody"}
                )
                continue

            # Step 4: Convert to NoteEvent format for comparison
            ref_notes = [
                NoteEvent(pitch=n.pitch, onset=n.onset, offset=n.onset + n.duration)
                for n in ref_melody
            ]
            gen_notes = [
                NoteEvent(pitch=n.pitch, onset=n.onset, offset=n.onset + n.duration)
                for n in gen_melody
            ]

            # Step 5: Compute composite metrics
            metrics = compute_composite_metrics(ref_notes, gen_notes)

            elapsed = time.time() - start_time

            # Store result
            result = {
                "song_id": song_id,
                "status": "OK",
                "melody_f1": metrics["melody_f1"],
                "melody_f1_lenient": metrics["melody_f1_lenient"],
                "pitch_class_f1": metrics["pitch_class_f1"],
                "chroma_similarity": metrics["chroma_similarity"],
                "onset_f1": metrics["onset_f1"],
                "composite_score": metrics["composite_score"],
                "ref_notes": metrics["note_counts"]["ref"],
                "gen_notes": metrics["note_counts"]["gen"],
                "elapsed": elapsed,
            }
            results.append(result)

            # Print result
            print(
                f"{song_id:<10} {'OK':<12} "
                f"{metrics['melody_f1']:>11.2%} "
                f"{metrics['melody_f1_lenient']:>11.2%} "
                f"{metrics['pitch_class_f1']:>9.2%} "
                f"{metrics['chroma_similarity']:>9.2%} "
                f"{metrics['onset_f1']:>9.2%}"
            )

            # Clean up temp file
            if temp_midi.exists():
                temp_midi.unlink()

        except Exception as e:
            print(f"{song_id:<10} {'ERROR':<12} {str(e)[:40]}")
            results.append({"song_id": song_id, "status": "ERROR", "error": str(e)})

    # Print summary
    print("-" * 90)

    ok_results = [r for r in results if r.get("status") == "OK"]
    if ok_results:
        melody_f1_scores = [r["melody_f1"] for r in ok_results]
        melody_f1_lenient_scores = [r["melody_f1_lenient"] for r in ok_results]

        avg_f1 = sum(melody_f1_scores) / len(melody_f1_scores)
        avg_f1_lenient = sum(melody_f1_lenient_scores) / len(melody_f1_lenient_scores)

        print(f"{'AVERAGE':<10} {'':12} {avg_f1:>11.2%} {avg_f1_lenient:>11.2%}")
        print(
            f"{'MIN':<10} {'':12} "
            f"{min(melody_f1_scores):>11.2%} "
            f"{min(melody_f1_lenient_scores):>11.2%}"
        )
        print(
            f"{'MAX':<10} {'':12} "
            f"{max(melody_f1_scores):>11.2%} "
            f"{max(melody_f1_lenient_scores):>11.2%}"
        )

    print("=" * 90)

    return results


if __name__ == "__main__":
    results = run_melody_baseline_measurement()

    if results:
        # Save results to JSON
        output_file = Path(__file__).parent / "melody_baseline_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {output_file}")
