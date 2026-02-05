#!/usr/bin/env python3
"""
Batch MXL generation and accuracy measurement.

Processes all 8 test MP3 files through the full pipeline:
  MP3 → MIDI → Melody → Analysis → MusicXML (3 difficulties)
Then compares generated MXL with reference MXL and reports accuracy.

Output: generated MXL files in /app/test/generated_mxl/
        accuracy report printed to stdout

Usage (inside Docker):
    python scripts/batch_generate_mxl.py
"""

import json
import logging
import sys
import time
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.audio_to_midi import convert_audio_to_midi
from core.melody_extractor import extract_melody
from core.midi_parser import parse_midi
from core.audio_analysis import analyze_audio
from core.difficulty_adjuster import generate_all_sheets
from core.musicxml_comparator import compare_musicxml, compare_note_lists
from core.musicxml_melody_extractor import extract_melody_from_musicxml

# Suppress verbose logging
logging.getLogger("basic_pitch").setLevel(logging.WARNING)
logging.getLogger("librosa").setLevel(logging.WARNING)
logging.getLogger("tensorflow").setLevel(logging.WARNING)
logging.getLogger("music21").setLevel(logging.WARNING)
logging.getLogger("piano_transcription_inference").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format="%(message)s")

logger = logging.getLogger(__name__)

# Song mapping: test/ filename <-> golden data song_id
SONG_MAP = [
    ("Golden", "song_01"),
    ("IRIS OUT", "song_02"),
    ("꿈의 버스", "song_03"),
    ("너에게100퍼센트", "song_04"),
    ("달리 표현할 수 없어요", "song_05"),
    ("등불을 지키다", "song_06"),
    ("비비드라라러브", "song_07"),
    ("여름이었다", "song_08"),
]


def process_song(mp3_path: Path, output_dir: Path, reference_mxl: Path):
    """Process a single song through the full pipeline and measure accuracy."""
    import pretty_midi
    import tempfile

    song_name = mp3_path.stem
    song_output_dir = output_dir / song_name
    song_output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "song": song_name,
        "mp3_path": str(mp3_path),
        "status": "pending",
    }

    try:
        # Step 1: Audio → MIDI
        print(f"  [1/5] Audio → MIDI ...", end=" ", flush=True)
        raw_midi_path = song_output_dir / "raw.mid"
        midi_result = convert_audio_to_midi(mp3_path, raw_midi_path)
        print(
            f"OK ({midi_result['note_count']} notes, {midi_result['processing_time']:.1f}s)"
        )
        result["raw_note_count"] = midi_result["note_count"]

        # Step 2: Melody extraction
        print(f"  [2/5] Melody extraction ...", end=" ", flush=True)
        melody_notes = extract_melody(raw_midi_path)
        print(f"OK ({len(melody_notes)} melody notes)")
        result["melody_note_count"] = len(melody_notes)

        # Save melody MIDI
        melody_midi_path = song_output_dir / "melody.mid"
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        for note in melody_notes:
            midi_note = pretty_midi.Note(
                velocity=note.velocity,
                pitch=note.pitch,
                start=note.onset,
                end=note.onset + note.duration,
            )
            instrument.notes.append(midi_note)
        pm.instruments.append(instrument)
        pm.write(str(melody_midi_path))

        # Step 3: Audio analysis
        print(f"  [3/5] Audio analysis ...", end=" ", flush=True)
        analysis = analyze_audio(mp3_path)
        print(f"OK (BPM={analysis['bpm']:.1f}, Key={analysis['key']})")
        result["bpm"] = analysis["bpm"]
        result["key"] = analysis["key"]

        # Save analysis
        with open(song_output_dir / "analysis.json", "w") as f:
            json.dump(analysis, f, indent=2)

        # Step 4: Generate difficulty sheets
        print(f"  [4/5] Generating sheets ...", end=" ", flush=True)
        sheets = generate_all_sheets(song_output_dir, melody_midi_path, analysis)
        print(f"OK (easy/medium/hard)")

        # Copy medium sheet as the main output MXL
        medium_sheet = song_output_dir / "sheet_medium.musicxml"

        # Step 5: Compare with reference
        print(f"  [5/5] Comparing with reference ...", end=" ", flush=True)

        # 5a. MusicXML-level comparison (note-by-note)
        comparison = compare_musicxml(str(reference_mxl), str(medium_sheet))
        result["musicxml_similarity"] = comparison["similarity"]
        result["ref_note_count"] = comparison["details"]["ref_note_count"]
        result["gen_note_count"] = comparison["details"]["gen_note_count"]
        result["matched_notes"] = comparison["details"]["matched_notes"]

        # 5b. Melody-level comparison (note list comparison)
        try:
            ref_melody = extract_melody_from_musicxml(str(reference_mxl))
            melody_similarity = compare_note_lists(ref_melody, melody_notes)
            result["melody_similarity"] = melody_similarity
            result["ref_melody_count"] = len(ref_melody)
        except Exception as e:
            result["melody_similarity"] = None
            result["melody_error"] = str(e)

        print(f"OK")
        result["status"] = "success"

    except Exception as e:
        print(f"FAILED: {e}")
        result["status"] = "failed"
        result["error"] = str(e)

    return result


def main():
    test_dir = Path("/app/test")
    golden_dir = Path("/app/tests/golden/data")
    output_dir = Path("/app/test/generated_mxl")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  Piano Sheet Extractor - Batch MXL Generation & Accuracy Report")
    print("=" * 70)
    print(f"  Input:  {test_dir}")
    print(f"  Output: {output_dir}")
    print(f"  Songs:  {len(SONG_MAP)}")
    print("=" * 70)

    results = []
    total_start = time.time()

    for song_name, song_id in SONG_MAP:
        mp3_path = test_dir / f"{song_name}.mp3"
        # Reference MXL: prefer test/ directory, fallback to golden data
        reference_mxl = test_dir / f"{song_name}.mxl"
        if not reference_mxl.exists():
            reference_mxl = golden_dir / song_id / "reference.mxl"

        if not mp3_path.exists():
            print(f"\n[SKIP] {song_name}: MP3 not found at {mp3_path}")
            continue

        if not reference_mxl.exists():
            print(f"\n[SKIP] {song_name}: Reference MXL not found")
            continue

        print(f"\n{'─' * 70}")
        print(f"  Processing: {song_name}")
        print(f"{'─' * 70}")

        start = time.time()
        result = process_song(mp3_path, output_dir, reference_mxl)
        result["processing_time_sec"] = round(time.time() - start, 1)
        results.append(result)

    total_time = time.time() - total_start

    # Print summary report
    print(f"\n{'=' * 70}")
    print(f"  ACCURACY REPORT")
    print(f"{'=' * 70}")
    print(
        f"{'Song':<28} {'Status':<8} {'MusicXML':<12} {'Melody':<12} {'Ref/Gen/Match':<20} {'Time':<8}"
    )
    print(f"{'─' * 28} {'─' * 8} {'─' * 12} {'─' * 12} {'─' * 20} {'─' * 8}")

    success_count = 0
    total_mxml_sim = 0
    total_melody_sim = 0
    melody_count = 0

    for r in results:
        song = r["song"][:27]
        status = r["status"]

        if status == "success":
            success_count += 1
            mxml_sim = f"{r['musicxml_similarity']:.2%}"
            total_mxml_sim += r["musicxml_similarity"]

            if r.get("melody_similarity") is not None:
                mel_sim = f"{r['melody_similarity']:.2%}"
                total_melody_sim += r["melody_similarity"]
                melody_count += 1
            else:
                mel_sim = "N/A"

            ref_gen_match = (
                f"{r['ref_note_count']}/{r['gen_note_count']}/{r['matched_notes']}"
            )
            t = f"{r['processing_time_sec']}s"
        else:
            mxml_sim = "FAIL"
            mel_sim = "FAIL"
            ref_gen_match = "-"
            t = f"{r.get('processing_time_sec', '?')}s"

        print(
            f"{song:<28} {status:<8} {mxml_sim:<12} {mel_sim:<12} {ref_gen_match:<20} {t:<8}"
        )

    print(f"{'─' * 70}")

    if success_count > 0:
        avg_mxml = total_mxml_sim / success_count
        avg_melody = total_melody_sim / melody_count if melody_count > 0 else 0
        print(f"  Processed: {success_count}/{len(results)} songs")
        print(f"  Avg MusicXML similarity: {avg_mxml:.2%}")
        print(f"  Avg Melody similarity:   {avg_melody:.2%}")

    print(f"  Total time: {total_time:.1f}s")
    print(f"  Output dir: {output_dir}")
    print(f"{'=' * 70}")

    # Save results JSON
    results_path = output_dir / "accuracy_report.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Results saved: {results_path}")

    # List generated MXL files
    print(f"\n  Generated MXL files:")
    for r in results:
        if r["status"] == "success":
            for diff in ["easy", "medium", "hard"]:
                p = output_dir / r["song"] / f"sheet_{diff}.musicxml"
                if p.exists():
                    size_kb = p.stat().st_size / 1024
                    print(f"    {p.relative_to(output_dir)}: {size_kb:.1f}KB")

    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
