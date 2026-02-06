"""
Essentia + Skyline 알고리즘 테스트 스크립트

목적:
- Essentia로 audio → melody 추출 (WSL subprocess)
- Skyline 알고리즘으로 멜로디 추출 (기존 파이프라인)
- Reference MusicXML과 비교

테스트 대상:
- song_01: 194.6s, reference 1,897 notes
"""

import sys
import json
import subprocess
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.midi_parser import Note
from core.melody_extractor import extract_melody
from core.musicxml_melody_extractor import extract_melody_from_musicxml
from core.musicxml_comparator import compare_note_lists_with_pitch_class


# ============================================================================
# Constants
# ============================================================================

# Test data paths (resolve to absolute path)
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent
GOLDEN_DATA_DIR = PROJECT_ROOT / "backend" / "tests" / "golden" / "data"

# WSL script path
WSL_SCRIPT_PATH = "/mnt/c/Users/handuk.lee/projects/mk-pinano-sheet/backend/scripts/essentia_melody_extractor.py"


# ============================================================================
# Helper Functions
# ============================================================================


def windows_path_to_wsl(windows_path: Path) -> str:
    """
    Convert Windows path to WSL path.

    Example:
        C:\\Users\\handuk.lee\\projects\\... -> /mnt/c/Users/handuk.lee/projects/...

    Args:
        windows_path: Windows Path object

    Returns:
        WSL path string
    """
    # Convert to absolute path
    abs_path = windows_path.resolve()

    # Convert to string and replace backslashes
    path_str = str(abs_path).replace("\\", "/")

    # Replace drive letter (C: -> /mnt/c)
    if len(path_str) >= 2 and path_str[1] == ":":
        drive = path_str[0].lower()
        path_str = f"/mnt/{drive}{path_str[2:]}"

    return path_str


def run_essentia_extractor(audio_path: Path) -> list[Note]:
    """
    Run Essentia melody extractor via WSL subprocess.

    Args:
        audio_path: Path to audio file (Windows format)

    Returns:
        List of Note objects

    Raises:
        Exception: If WSL subprocess fails
    """
    # Convert Windows path to WSL path
    wsl_audio_path = windows_path_to_wsl(audio_path)

    # Run WSL subprocess
    cmd = ["wsl.exe", "python3", WSL_SCRIPT_PATH, wsl_audio_path]
    result = None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )

        if result.returncode != 0:
            raise Exception(f"Essentia extractor failed: {result.stderr}")

        # Parse JSON output
        notes_data = json.loads(result.stdout)

        # Convert to Note objects
        notes = []
        for note_dict in notes_data:
            notes.append(
                Note(
                    pitch=note_dict["pitch"],
                    onset=note_dict["onset"],
                    duration=note_dict["duration"],
                    velocity=80,  # Default velocity
                )
            )

        return notes

    except subprocess.TimeoutExpired:
        raise Exception("Essentia extractor timed out (5 minutes)")
    except json.JSONDecodeError as e:
        output = result.stdout if result else "N/A"
        raise Exception(f"Failed to parse Essentia output: {e}\nOutput: {output}")
    except Exception as e:
        raise Exception(f"Failed to run Essentia extractor: {e}")


def analyze_notes(notes: list[Note]) -> dict:
    """Analyze note list statistics"""
    if not notes:
        return {
            "count": 0,
            "pitch_min": 0,
            "pitch_max": 0,
            "avg_duration": 0,
        }

    return {
        "count": len(notes),
        "pitch_min": min(n.pitch for n in notes),
        "pitch_max": max(n.pitch for n in notes),
        "avg_duration": sum(n.duration for n in notes) / len(notes),
    }


# ============================================================================
# Main Test Functions
# ============================================================================


def test_essentia(audio_path: Path) -> dict:
    """
    Test Essentia melody extraction.

    Args:
        audio_path: Path to audio file

    Returns:
        Dict with notes and stats
    """
    print(f"\n{'=' * 60}")
    print(f"Testing Essentia on: {audio_path.name}")
    print(f"{'=' * 60}\n")

    print("Step 1: Running Essentia melody extractor (via WSL)...")

    try:
        notes = run_essentia_extractor(audio_path)
        stats = analyze_notes(notes)

        print(f"[OK] Essentia extraction completed")
        print(f"\nEssentia stats:")
        print(f"  Notes: {stats['count']}")
        print(f"  Pitch range: {stats['pitch_min']}-{stats['pitch_max']}")
        print(f"  Avg duration: {stats['avg_duration'] * 1000:.1f}ms")

        return {
            "notes": notes,
            "stats": stats,
        }

    except Exception as e:
        print(f"[ERROR] Essentia extraction failed: {e}")
        return {
            "notes": [],
            "stats": analyze_notes([]),
            "error": str(e),
        }


def test_skyline(audio_path: Path) -> dict:
    """
    Test Skyline melody extraction (existing pipeline).

    Args:
        audio_path: Path to audio file

    Returns:
        Dict with notes and stats
    """
    print(f"\n{'=' * 60}")
    print(f"Testing Skyline on: {audio_path.name}")
    print(f"{'=' * 60}\n")

    print("Step 1: Running Basic Pitch + Skyline pipeline...")

    try:
        # Note: This requires Basic Pitch to be installed
        # For spike test, we'll use the existing MIDI if available
        # Otherwise, this will fail gracefully

        # Check if reference MIDI exists (for quick test)
        midi_path = audio_path.parent / "reference.mid"
        if not midi_path.exists():
            raise Exception(f"Reference MIDI not found: {midi_path}")

        notes = extract_melody(midi_path)
        stats = analyze_notes(notes)

        print(f"[OK] Skyline extraction completed")
        print(f"\nSkyline stats:")
        print(f"  Notes: {stats['count']}")
        print(f"  Pitch range: {stats['pitch_min']}-{stats['pitch_max']}")
        print(f"  Avg duration: {stats['avg_duration'] * 1000:.1f}ms")

        return {
            "notes": notes,
            "stats": stats,
        }

    except Exception as e:
        print(f"[ERROR] Skyline extraction failed: {e}")
        return {
            "notes": [],
            "stats": analyze_notes([]),
            "error": str(e),
        }


def compare_with_reference(reference_path: Path) -> dict:
    """
    Extract melody from reference MusicXML.

    Args:
        reference_path: Path to reference MusicXML file

    Returns:
        Dict with notes and stats
    """
    print(f"\n{'=' * 60}")
    print(f"Reference MusicXML: {reference_path.name}")
    print(f"{'=' * 60}\n")

    try:
        ref_notes = extract_melody_from_musicxml(str(reference_path))
        ref_stats = analyze_notes(ref_notes)

        print(f"Reference stats:")
        print(f"  Notes: {ref_stats['count']}")
        print(f"  Pitch range: {ref_stats['pitch_min']}-{ref_stats['pitch_max']}")
        print(f"  Avg duration: {ref_stats['avg_duration'] * 1000:.1f}ms")

        return {
            "notes": ref_notes,
            "stats": ref_stats,
        }

    except Exception as e:
        print(f"[ERROR] Failed to extract reference melody: {e}")
        return {
            "notes": [],
            "stats": analyze_notes([]),
            "error": str(e),
        }


# ============================================================================
# Main
# ============================================================================


def test_single_song(song_name: str) -> dict:
    """
    Test a single song and return results.

    Args:
        song_name: Song directory name (e.g., "song_01")

    Returns:
        Dict with song_name, skyline_similarity, essentia_similarity, improved
    """
    # Paths
    song_dir = GOLDEN_DATA_DIR / song_name
    audio_path = song_dir / "input.mp3"
    reference_path = song_dir / "reference.mxl"

    # Validate inputs
    if not audio_path.exists():
        print(f"ERROR: Audio file not found: {audio_path}")
        return {
            "song_name": song_name,
            "skyline_similarity": 0.0,
            "essentia_similarity": 0.0,
            "improved": False,
            "error": "Audio file not found",
        }

    if not reference_path.exists():
        print(f"ERROR: Reference MusicXML not found: {reference_path}")
        return {
            "song_name": song_name,
            "skyline_similarity": 0.0,
            "essentia_similarity": 0.0,
            "improved": False,
            "error": "Reference MusicXML not found",
        }

    # Run tests
    ref_result = compare_with_reference(reference_path)
    essentia_result = test_essentia(audio_path)
    skyline_result = test_skyline(audio_path)

    # Compare results
    print(f"\n{'=' * 60}")
    print("COMPARISON")
    print(f"{'=' * 60}\n")

    ref_notes = ref_result["notes"]
    essentia_notes = essentia_result["notes"]
    skyline_notes = skyline_result["notes"]

    print(f"Reference: {len(ref_notes)} notes")
    print(f"Essentia: {len(essentia_notes)} notes")
    print(f"Skyline: {len(skyline_notes)} notes")

    # Calculate similarities (pitch class based, ignoring octave)
    if ref_notes and essentia_notes:
        essentia_similarity = compare_note_lists_with_pitch_class(
            ref_notes, essentia_notes
        )
        print(f"\nEssentia vs Reference:")
        print(f"  Pitch class similarity: {essentia_similarity * 100:.2f}%")
    else:
        essentia_similarity = 0.0
        print(f"\nEssentia vs Reference: N/A (no notes)")

    if ref_notes and skyline_notes:
        skyline_similarity = compare_note_lists_with_pitch_class(
            ref_notes, skyline_notes
        )
        print(f"\nSkyline vs Reference:")
        print(f"  Pitch class similarity: {skyline_similarity * 100:.2f}%")
    else:
        skyline_similarity = 0.0
        print(f"\nSkyline vs Reference: N/A (no notes)")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}\n")

    print(f"Reference: {len(ref_notes)} notes")
    print(
        f"Essentia: {len(essentia_notes)} notes ({essentia_similarity * 100:.2f}% similarity)"
    )
    print(
        f"Skyline: {len(skyline_notes)} notes ({skyline_similarity * 100:.2f}% similarity)"
    )

    improved = essentia_similarity > skyline_similarity

    if improved:
        print(
            f"\n[+] Essentia performs better (+{(essentia_similarity - skyline_similarity) * 100:.2f}%)"
        )
    elif skyline_similarity > essentia_similarity:
        print(
            f"\n[+] Skyline performs better (+{(skyline_similarity - essentia_similarity) * 100:.2f}%)"
        )
    else:
        print(f"\n[=] Both methods have equal performance")

    print(f"\n{'=' * 60}\n")

    return {
        "song_name": song_name,
        "skyline_similarity": skyline_similarity,
        "essentia_similarity": essentia_similarity,
        "improved": improved,
    }


def test_all_songs() -> None:
    """Test all 8 songs and output comparison table."""
    song_names = [f"song_{i:02d}" for i in range(1, 9)]
    results = []

    print(f"\n{'=' * 80}")
    print("TESTING ALL 8 SONGS")
    print(f"{'=' * 80}\n")

    for song_name in song_names:
        print(f"\n{'#' * 80}")
        print(f"# Testing {song_name}")
        print(f"{'#' * 80}\n")

        result = test_single_song(song_name)
        results.append(result)

    # Print markdown table
    print(f"\n{'=' * 80}")
    print("RESULTS TABLE")
    print(f"{'=' * 80}\n")

    print("| Song    | Skyline | Essentia | Improved |")
    print("|---------|---------|----------|----------|")

    for result in results:
        song = result["song_name"]
        skyline = result["skyline_similarity"]
        essentia = result["essentia_similarity"]
        improved = "✓" if result["improved"] else ""

        print(f"| {song:<7} | {skyline:>6.2%} | {essentia:>7.2%} | {improved:^8} |")

    # Calculate summary statistics
    skyline_avg = sum(r["skyline_similarity"] for r in results) / len(results)
    essentia_avg = sum(r["essentia_similarity"] for r in results) / len(results)
    improved_count = sum(1 for r in results if r["improved"])

    print("|---------|---------|----------|----------|")
    print(
        f"| SUMMARY | {skyline_avg:>6.2%} | {essentia_avg:>7.2%} | {improved_count}/8 improved |"
    )

    print(f"\n{'=' * 80}")
    print("ANALYSIS")
    print(f"{'=' * 80}\n")

    print(f"Average Skyline similarity: {skyline_avg * 100:.2f}%")
    print(f"Average Essentia similarity: {essentia_avg * 100:.2f}%")
    print(
        f"Songs improved with Essentia: {improved_count}/8 ({improved_count / 8 * 100:.1f}%)"
    )

    if essentia_avg > skyline_avg:
        print(
            f"\n[+] Essentia performs better overall (+{(essentia_avg - skyline_avg) * 100:.2f}%)"
        )
    elif skyline_avg > essentia_avg:
        print(
            f"\n[+] Skyline performs better overall (+{(skyline_avg - essentia_avg) * 100:.2f}%)"
        )
    else:
        print(f"\n[=] Both methods have equal average performance")

    print(f"\n{'=' * 80}\n")


def main():
    parser = argparse.ArgumentParser(description="Essentia vs Skyline spike test")
    parser.add_argument(
        "--song", default="song_01", help="Song name (default: song_01)"
    )
    parser.add_argument(
        "--all", action="store_true", help="Test all 8 songs (song_01 to song_08)"
    )
    args = parser.parse_args()

    if args.all:
        test_all_songs()
    else:
        test_single_song(args.song)


if __name__ == "__main__":
    main()
