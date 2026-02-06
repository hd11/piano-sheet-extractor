#!/usr/bin/env python3
"""Local CLI for melody extraction from audio files.

This script provides a command-line interface to extract melody from audio files
(MP3 or WAV) without requiring Docker. It uses the core modules to process audio
and generate MIDI output.

Usage:
    python run.py input.mp3 -o output/
    python run.py song.wav --output results/
"""

import argparse
import logging
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.audio_to_midi import convert_audio_to_midi
from core.melody_extractor import extract_melody
from core.midi_parser import parse_midi

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract melody from audio files (MP3/WAV)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py input.mp3 -o output/
  python run.py song.wav --output results/ --melody
  python run.py audio.mp3 -o out/ --verbose
        """,
    )

    parser.add_argument("input", type=Path, help="Input audio file (MP3 or WAV)")

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output"),
        help="Output directory (default: output/)",
    )

    parser.add_argument(
        "--melody", action="store_true", help="Extract melody from generated MIDI"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate input file
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    if args.input.suffix.lower() not in [".mp3", ".wav"]:
        logger.error(f"Unsupported file format: {args.input.suffix}")
        logger.info("Supported formats: MP3, WAV")
        sys.exit(1)

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {args.output}")

    try:
        # Step 1: Convert audio to MIDI
        logger.info(f"Processing audio file: {args.input}")
        midi_path = args.output / f"{args.input.stem}_generated.mid"

        logger.info("Converting audio to MIDI...")
        convert_audio_to_midi(args.input, midi_path)
        logger.info(f"MIDI generated: {midi_path}")

        # Step 2: Extract melody if requested
        if args.melody:
            logger.info("Extracting melody from MIDI...")
            melody_notes = extract_melody(midi_path)
            logger.info(f"Extracted {len(melody_notes)} melody notes")

            # Save melody info
            melody_info_path = args.output / f"{args.input.stem}_melody.txt"
            with open(melody_info_path, "w") as f:
                f.write("Melody Notes (pitch, onset, duration, velocity):\n")
                for note in melody_notes:
                    f.write(
                        f"{note.pitch}, {note.onset:.3f}, {note.duration:.3f}, {note.velocity}\n"
                    )
            logger.info(f"Melody info saved: {melody_info_path}")

        logger.info("✓ Processing complete!")

    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
