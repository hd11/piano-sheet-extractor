#!/usr/bin/env python3
"""Note loss measurement tool - MIDI → MusicXML → reimport round-trip.

Measures how many notes are lost during the conversion pipeline:
1. Parse input MIDI file
2. Convert to MusicXML
3. Parse MusicXML back
4. Compare note counts

Output: JSON with {input_notes, output_notes, loss_rate}

Usage:
    python scripts/measure_note_loss.py tests/golden/data/song_01/
    python scripts/measure_note_loss.py tests/golden/data/  # All songs
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import music21

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from core.audio_to_midi import convert_audio_to_midi
from core.midi_parser import parse_midi
from core.midi_to_musicxml import notes_to_musicxml

# Suppress verbose logging from dependencies
logging.getLogger("basic_pitch").setLevel(logging.WARNING)
logging.getLogger("librosa").setLevel(logging.WARNING)
logging.getLogger("tensorflow").setLevel(logging.WARNING)
logging.getLogger("music21").setLevel(logging.WARNING)


@dataclass(frozen=True)
class MeasurementResult:
    """Result of note loss measurement for a single song."""

    song_name: str
    input_notes: int
    output_notes: int
    loss_rate: float  # 0.0 to 1.0


def count_notes_in_musicxml(musicxml_str: str) -> int:
    """Parse MusicXML string and count all notes (including chords)."""
    # Write to temp file (music21 requires file path)
    with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False, mode="w") as f:
        f.write(musicxml_str)
        temp_path = f.name

    try:
        score = music21.converter.parse(temp_path)
        count = 0
        for element in score.flatten().notes:
            if isinstance(element, music21.note.Note):
                count += 1
            elif isinstance(element, music21.chord.Chord):
                count += len(element.pitches)
        return count
    finally:
        Path(temp_path).unlink(missing_ok=True)


def measure_song(song_dir: Path, verbose: bool = False) -> Optional[MeasurementResult]:
    """Measure note loss for a single song directory.

    Args:
        song_dir: Path to song directory (must contain input.mp3)
        verbose: Print progress messages

    Returns:
        MeasurementResult if successful, None if song_dir is invalid
    """
    mp3_path = song_dir / "input.mp3"
    if not mp3_path.exists():
        return None

    song_name = song_dir.name

    # Step 1: Convert audio to MIDI
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_midi_path = Path(tmpdir) / "raw.mid"

        if verbose:
            print(f"  [{song_name}] Converting audio to MIDI...", file=sys.stderr)
        midi_meta = convert_audio_to_midi(mp3_path, raw_midi_path)

        # Step 2: Parse MIDI to get input note count
        if verbose:
            print(f"  [{song_name}] Parsing MIDI...", file=sys.stderr)
        input_notes = parse_midi(raw_midi_path)
        input_count = len(input_notes)

        # Step 3: Convert to MusicXML
        if verbose:
            print(f"  [{song_name}] Converting to MusicXML...", file=sys.stderr)
        # Extract BPM from metadata (default to 120 if not available)
        bpm = float(midi_meta.get("bpm") or 120.0)
        key = "C major"  # Default key
        musicxml_str = notes_to_musicxml(input_notes, bpm, key)

        # Step 4: Count notes in MusicXML
        if verbose:
            print(f"  [{song_name}] Counting notes in MusicXML...", file=sys.stderr)
        output_count = count_notes_in_musicxml(musicxml_str)

        # Step 5: Calculate loss rate
        loss_rate = (
            0.0 if input_count == 0 else (input_count - output_count) / input_count
        )

        return MeasurementResult(
            song_name=song_name,
            input_notes=input_count,
            output_notes=output_count,
            loss_rate=loss_rate,
        )


def main() -> int:
    """Main entry point."""
    ap = argparse.ArgumentParser(
        description="Measure note loss in MIDI → MusicXML → reimport round-trip"
    )
    ap.add_argument(
        "path",
        type=Path,
        help="Path to song directory or parent directory containing song_XX folders",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (one result per line)",
    )
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print progress messages",
    )
    args = ap.parse_args()

    path = args.path.resolve()

    # Determine if path is a single song or parent directory
    if (path / "input.mp3").exists():
        # Single song directory
        song_dirs = [path]
    else:
        # Parent directory - find all song_XX subdirectories
        song_dirs = sorted(
            [d for d in path.iterdir() if d.is_dir() and d.name.startswith("song_")]
        )

    if not song_dirs:
        print(f"Error: No song directories found in {path}", file=sys.stderr)
        return 1

    results: list[MeasurementResult] = []

    for i, song_dir in enumerate(song_dirs, 1):
        try:
            if args.verbose:
                print(
                    f"[{i}/{len(song_dirs)}] Processing {song_dir.name}...",
                    file=sys.stderr,
                )

            result = measure_song(song_dir, verbose=args.verbose)
            if result is None:
                print(f"Skipping {song_dir.name}: no input.mp3 found", file=sys.stderr)
                continue

            results.append(result)

            if args.json:
                # Output JSON for each song
                print(
                    json.dumps(
                        {
                            "song": result.song_name,
                            "input_notes": result.input_notes,
                            "output_notes": result.output_notes,
                            "loss_rate": round(result.loss_rate, 4),
                        }
                    )
                )
            else:
                # Human-readable output
                print(
                    f"{result.song_name}: {result.input_notes} → {result.output_notes} "
                    f"(loss: {result.loss_rate * 100:.1f}%)"
                )

        except Exception as e:
            print(f"Error processing {song_dir.name}: {e}", file=sys.stderr)
            import traceback

            if args.verbose:
                traceback.print_exc(file=sys.stderr)
            return 1

    # Summary
    if not args.json and results:
        print("\n" + "=" * 60)
        total_input = sum(r.input_notes for r in results)
        total_output = sum(r.output_notes for r in results)
        avg_loss = sum(r.loss_rate for r in results) / len(results) if results else 0.0
        print(f"Total: {total_input} → {total_output} notes")
        print(f"Average loss rate: {avg_loss * 100:.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
