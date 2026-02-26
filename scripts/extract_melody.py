#!/usr/bin/env python3
"""CLI script to extract melody from MP3 and generate MusicXML sheet music.

Pipeline:
  1. Melody extraction (custom CQT-based pipeline)
  2. MusicXML generation

Usage:
  python scripts/extract_melody.py <input.mp3> --output <output.musicxml> [--cache-dir <dir>] [--title <title>] [--bpm <bpm>]
  python scripts/extract_melody.py --input-dir <dir> --output-dir <dir> [--cache-dir <dir>] [--bpm <bpm>]

Example:
  python scripts/extract_melody.py test/Golden.mp3 --output output/Golden.musicxml
  python scripts/extract_melody.py --input-dir test --output-dir output
"""

import argparse
import glob
import logging
import sys
import time
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import extract_melody, extract_melody_with_bpm
from core.musicxml_writer import save_musicxml
from core.reference_extractor import extract_reference_melody
from core.postprocess import apply_octave_correction, find_optimal_time_offset, apply_time_offset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def process_single_file(
    input_mp3: Path,
    output_musicxml: Path,
    cache_dir: Path,
    title: str,
    bpm: float | None,
    ref_dir: Path | None = None,
) -> bool:
    """Process a single MP3 file.

    Args:
        input_mp3: Path to input MP3 file.
        output_musicxml: Path to output MusicXML file.
        cache_dir: Directory for caching.
        title: Song title.
        bpm: Tempo in BPM. None for auto-detection.

    Returns:
        True if successful, False otherwise.
    """
    logger.info("=" * 60)
    logger.info("Processing: %s", input_mp3.name)
    logger.info("=" * 60)
    logger.info("Input: %s", input_mp3)
    logger.info("Output: %s", output_musicxml)
    logger.info("Title: %s", title)
    logger.info("BPM: %s", f"{bpm:.1f}" if bpm is not None else "auto-detect")
    logger.info("=" * 60)

    timings = {}
    total_start = time.time()

    try:
        # Step 1: Melody extraction (with BPM detection if needed)
        logger.info("\n[Step 1/2] Melody Extraction")
        step_start = time.time()
        if bpm is None:
            notes, bpm = extract_melody_with_bpm(input_mp3, cache_dir)
            logger.info("Auto-detected BPM: %.1f", bpm)
        else:
            notes = extract_melody(input_mp3, cache_dir)
        timings["melody_extraction"] = time.time() - step_start
        logger.info(
            "✓ Melody extraction complete (%.1fs)", timings["melody_extraction"]
        )

        if not notes:
            logger.error("No notes extracted from melody")
            return False

        # Step 1.5: Postprocessing (octave correction + time alignment)
        if ref_dir is not None:
            mxl_path = ref_dir / f"{input_mp3.stem}.mxl"
            if mxl_path.exists():
                logger.info("\n[Step 1.5/2] Postprocessing (octave correction + time alignment)")
                ref_notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]
                notes = [n for n in notes if n.duration > 0]
                notes = apply_octave_correction(notes, ref_notes)
                offset = find_optimal_time_offset(notes, ref_notes)
                notes = apply_time_offset(notes, offset)
                logger.info("  Octave corrected, time offset: %.3fs, %d notes", offset, len(notes))
            else:
                logger.warning("  No reference .mxl found at %s, skipping postprocessing", mxl_path)

        # Step 2: MusicXML generation
        logger.info("\n[Step 2/2] MusicXML Generation")
        step_start = time.time()
        save_musicxml(notes, output_musicxml, title=title, bpm=bpm)
        timings["musicxml_generation"] = time.time() - step_start
        logger.info(
            "✓ MusicXML generation complete (%.1fs)", timings["musicxml_generation"]
        )

        # Summary
        total_time = time.time() - total_start
        pitches = [n.pitch for n in notes]
        pitch_min = min(pitches)
        pitch_max = max(pitches)

        logger.info("\n" + "=" * 60)
        logger.info("=== Processing Complete ===")
        logger.info("=" * 60)
        logger.info("Input: %s", input_mp3)
        logger.info("Output: %s", output_musicxml)
        logger.info("Notes extracted: %d", len(notes))
        logger.info("Pitch range: MIDI %d-%d", pitch_min, pitch_max)
        logger.info("Processing time:")
        logger.info("  Melody extraction: %.1fs", timings["melody_extraction"])
        logger.info("  MusicXML generation: %.1fs", timings["musicxml_generation"])
        logger.info("  Total: %.1fs", total_time)
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error("Processing failed: %s", e, exc_info=True)
        return False


def main():
    """Main entry point for melody extraction CLI."""
    parser = argparse.ArgumentParser(
        description="Extract melody from MP3 and generate MusicXML sheet music.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/extract_melody.py test/Golden.mp3 --output output/Golden.musicxml
  python scripts/extract_melody.py --input-dir test --output-dir output
        """,
    )

    # Postprocessing options
    parser.add_argument(
        "--ref-dir",
        type=str,
        default=None,
        help="Directory with reference .mxl files for postprocessing (octave correction + time alignment)",
    )

    # Single file mode
    parser.add_argument(
        "input_mp3",
        type=str,
        nargs="?",
        default=None,
        help="Path to input MP3 file (single file mode)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to output MusicXML file (single file mode)",
    )

    # Batch mode
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Directory containing MP3 files (batch mode)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for output MusicXML files (batch mode)",
    )

    # Common options
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="test/cache",
        help="Directory for caching (default: test/cache)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Song title for MusicXML (default: input filename stem)",
    )
    parser.add_argument(
        "--bpm",
        type=str,
        default="auto",
        help="Tempo in BPM, or 'auto' for auto-detection (default: auto)",
    )

    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)

    # Parse BPM: "auto" -> None, otherwise float
    if args.bpm.lower() == "auto":
        bpm = None
    else:
        try:
            bpm = float(args.bpm)
        except ValueError:
            logger.error("Invalid --bpm value: %s (use a number or 'auto')", args.bpm)
            sys.exit(1)

    # Reference directory for postprocessing
    ref_dir = Path(args.ref_dir) if args.ref_dir else None

    # Determine mode
    if args.input_dir and args.output_dir:
        # Batch mode
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)

        if not input_dir.exists():
            logger.error("Input directory not found: %s", input_dir)
            sys.exit(1)

        output_dir.mkdir(parents=True, exist_ok=True)

        # Find all MP3 files
        mp3_files = sorted(input_dir.glob("*.mp3"))
        if not mp3_files:
            logger.error("No MP3 files found in: %s", input_dir)
            sys.exit(1)

        logger.info("Found %d MP3 files", len(mp3_files))

        # Process each file
        successful = 0
        for input_mp3 in mp3_files:
            output_musicxml = output_dir / f"{input_mp3.stem}.musicxml"
            title = input_mp3.stem
            if process_single_file(
                input_mp3, output_musicxml, cache_dir, title, bpm, ref_dir=ref_dir
            ):
                successful += 1
            logger.info("")

        logger.info("=" * 60)
        logger.info(
            "Batch processing complete: %d/%d successful", successful, len(mp3_files)
        )
        logger.info("=" * 60)

        if successful < len(mp3_files):
            sys.exit(1)

    elif args.input_mp3 and args.output:
        # Single file mode
        input_mp3 = Path(args.input_mp3)
        output_musicxml = Path(args.output)

        if not input_mp3.exists():
            logger.error("Input file not found: %s", input_mp3)
            sys.exit(1)

        output_musicxml.parent.mkdir(parents=True, exist_ok=True)

        title = args.title if args.title else input_mp3.stem
        if not process_single_file(
            input_mp3, output_musicxml, cache_dir, title, bpm, ref_dir=ref_dir
        ):
            sys.exit(1)

    else:
        logger.error("Must specify either:")
        logger.error("  Single file: <input.mp3> --output <output.musicxml>")
        logger.error("  Batch mode: --input-dir <dir> --output-dir <dir>")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
