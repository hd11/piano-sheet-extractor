#!/usr/bin/env python3
"""CLI: Extract vocal melody from MP3 and save as MusicXML.

Usage:
    python scripts/extract.py test/꿈의\ 버스.mp3 -o output/꿈의_버스.musicxml
    python scripts/extract.py test/*.mp3 -o output/
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pipeline import extract_melody


def main():
    parser = argparse.ArgumentParser(
        description="Extract vocal melody from MP3 -> MusicXML"
    )
    parser.add_argument(
        "mp3_files",
        type=Path,
        nargs="+",
        help="Input MP3 file(s)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("output"),
        help="Output file or directory (default: output/)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Cache directory for vocal separation",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    for mp3_path in args.mp3_files:
        if not mp3_path.exists():
            print(f"File not found: {mp3_path}", file=sys.stderr)
            continue

        # Determine output path
        if args.output.suffix in (".musicxml", ".xml"):
            output_path = args.output
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            output_path = args.output / f"{mp3_path.stem}.musicxml"

        print(f"Processing: {mp3_path.name}")
        try:
            notes = extract_melody(
                mp3_path,
                cache_dir=args.cache_dir,
                output_path=output_path,
            )
            print(f"  -> {len(notes)} notes -> {output_path}")
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
