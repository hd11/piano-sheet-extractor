#!/usr/bin/env python3
"""Quick ablation test: run single song with different postprocess configs.

Tests each Step 2-5 change independently to identify regression source.
Uses environment variables to toggle features.
"""
import os
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.comparator import compare_melodies
from core.musicxml_writer import load_musicxml_notes
from core.pipeline import extract_melody
from core.reference_extractor import extract_reference_melody


def run_single_song(song_stem: str, mode: str = "fcpe", tag: str = "test"):
    """Run pipeline + eval on a single song, return metrics."""
    input_dir = Path("test")
    mp3_path = input_dir / f"{song_stem}.mp3"
    mxl_path = input_dir / f"{song_stem}.mxl"
    output_dir = Path("output") / "ablation"
    output_dir.mkdir(parents=True, exist_ok=True)
    musicxml_output = output_dir / f"{song_stem}_{tag}.musicxml"

    start = time.time()
    extract_melody(mp3_path, cache_dir=input_dir / "cache",
                   output_path=musicxml_output, mode=mode)
    gen_notes = load_musicxml_notes(musicxml_output)
    ref_notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]
    metrics = compare_melodies(ref_notes, gen_notes)
    elapsed = time.time() - start

    return {
        "tag": tag,
        "mel_strict": metrics["melody_f1_strict"],
        "mel_lenient": metrics["melody_f1_lenient"],
        "onset_f1": metrics["onset_f1"],
        "notes": f"{metrics['note_counts']['gen']}/{metrics['note_counts']['ref']}",
        "time": f"{elapsed:.1f}s",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--song", default="꿈의 버스")
    parser.add_argument("--mode", default="fcpe")
    parser.add_argument("--tag", default="current")
    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.WARNING)

    result = run_single_song(args.song, args.mode, args.tag)
    print(json.dumps(result, indent=2, ensure_ascii=False))
