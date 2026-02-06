"""
Essentia Baseline Measurement Script (Docker version)

Measures Note F1 scores for Essentia melody extraction on 8 songs.
Uses mir_eval with 50ms onset tolerance, 50 cents pitch tolerance.

Runs INSIDE Docker container where Essentia is available directly.

Usage:
    docker compose exec backend python scripts/measure_essentia_docker.py
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.midi_parser import parse_midi, Note
from core.comparison_utils import NoteEvent, compute_mir_eval_metrics
from scripts.essentia_melody_extractor import extract_melody

# ============================================================================
# Constants
# ============================================================================

GOLDEN_DATA_DIR = Path(__file__).parent.parent / "tests" / "golden" / "data"
EVIDENCE_DIR = Path(__file__).parent.parent.parent / ".sisyphus" / "evidence"

SONG_IDS = [f"song_{i:02d}" for i in range(1, 9)]  # song_01 ~ song_08


# ============================================================================
# Helper Functions
# ============================================================================


def note_to_noteevent(note: Note) -> NoteEvent:
    """Convert Note to NoteEvent."""
    return NoteEvent(
        pitch=note.pitch,
        onset=note.onset,
        offset=note.onset + note.duration,
    )


def dict_to_noteevent(note_dict: dict) -> NoteEvent:
    """Convert Essentia dict to NoteEvent."""
    return NoteEvent(
        pitch=note_dict["pitch"],
        onset=note_dict["onset"],
        offset=note_dict["onset"] + note_dict["duration"],
    )


def measure_song(song_id: str) -> dict:
    """Measure Note F1 for a single song."""
    print(f"\n[{song_id}] Processing...")

    song_dir = GOLDEN_DATA_DIR / song_id
    audio_path = song_dir / "input.mp3"
    reference_path = song_dir / "reference.mid"

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio not found: {audio_path}")
    if not reference_path.exists():
        raise FileNotFoundError(f"Reference not found: {reference_path}")

    # Run Essentia directly (no WSL needed in Docker)
    print(f"  - Running Essentia...")
    try:
        essentia_notes = extract_melody(str(audio_path))
        print(f"  - Essentia extracted {len(essentia_notes)} notes")
    except Exception as e:
        print(f"  - Essentia FAILED: {e}")
        essentia_notes = []

    # Load reference
    print(f"  - Loading reference MIDI...")
    ref_notes = parse_midi(reference_path)
    print(f"  - Reference has {len(ref_notes)} notes")

    # Convert to NoteEvent
    ref_events = [note_to_noteevent(n) for n in ref_notes]
    gen_events = [dict_to_noteevent(n) for n in essentia_notes]

    # Compute mir_eval metrics
    if len(gen_events) == 0:
        print(f"  - No generated notes, F1 = 0.0")
        metrics = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    else:
        print(f"  - Computing mir_eval metrics (onset_tolerance=0.05)...")
        metrics = compute_mir_eval_metrics(
            ref_events,
            gen_events,
            onset_tolerance=0.05,  # 50ms
            pitch_tolerance=50.0,  # 50 cents
        )

    print(
        f"  - F1: {metrics['f1']:.4f}, Precision: {metrics['precision']:.4f}, Recall: {metrics['recall']:.4f}"
    )

    return {
        "song_id": song_id,
        "f1": metrics["f1"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "ref_notes": len(ref_events),
        "gen_notes": len(gen_events),
    }


def main():
    """Main measurement loop."""
    print("=" * 80)
    print("Essentia Baseline Measurement (Docker)")
    print("=" * 80)
    print(f"Songs: {len(SONG_IDS)}")
    print(f"Onset tolerance: 50ms (0.05s)")
    print(f"Pitch tolerance: 50 cents")
    print()

    # Measure all songs
    results = []
    for song_id in SONG_IDS:
        try:
            result = measure_song(song_id)
            results.append(result)
        except Exception as e:
            print(f"\n[{song_id}] ERROR: {e}")
            results.append(
                {
                    "song_id": song_id,
                    "f1": 0.0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "ref_notes": 0,
                    "gen_notes": 0,
                    "error": str(e),
                }
            )

    # Calculate summary
    f1_scores = [r["f1"] for r in results]
    average_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    songs_above_70pct = sum(1 for f1 in f1_scores if f1 >= 0.70)
    min_f1 = min(f1_scores) if f1_scores else 0.0
    max_f1 = max(f1_scores) if f1_scores else 0.0

    summary = {
        "average_f1": average_f1,
        "songs_above_70pct": songs_above_70pct,
        "min_f1": min_f1,
        "max_f1": max_f1,
    }

    # Print summary
    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Average F1: {average_f1:.4f} ({average_f1 * 100:.2f}%)")
    print(f"Songs above 70%: {songs_above_70pct}/8")
    print(f"Min F1: {min_f1:.4f} ({min_f1 * 100:.2f}%)")
    print(f"Max F1: {max_f1:.4f} ({max_f1 * 100:.2f}%)")
    print()

    if average_f1 < 0.30:
        print("WARNING: Average F1 below 30%, 70% target likely unachievable")
    if max_f1 < 0.70:
        print(
            "CRITICAL: No song achieved 70% F1, target impossible without improvements"
        )

    print()

    # Detailed table
    print("DETAILED RESULTS")
    print("-" * 80)
    print(
        f"{'Song':<10} {'F1':>8} {'Precision':>10} {'Recall':>8} {'Ref':>6} {'Gen':>6}"
    )
    print("-" * 80)
    for r in results:
        print(
            f"{r['song_id']:<10} {r['f1']:>8.4f} {r['precision']:>10.4f} {r['recall']:>8.4f} {r['ref_notes']:>6} {r['gen_notes']:>6}"
        )
    print("-" * 80)

    # Save JSON
    output_data = {
        "results": results,
        "summary": summary,
    }

    # Try to save to evidence dir, fall back to local
    try:
        output_path = EVIDENCE_DIR / "essentia-note-f1-baseline.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        output_path = Path(__file__).parent.parent / "essentia-note-f1-baseline.json"

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print()
    print(f"Results saved to: {output_path}")

    # Also print JSON to stdout for easy capture
    print()
    print("JSON_OUTPUT_START")
    print(json.dumps(output_data, indent=2))
    print("JSON_OUTPUT_END")


if __name__ == "__main__":
    main()
