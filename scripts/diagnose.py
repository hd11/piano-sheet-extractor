#!/usr/bin/env python3
"""Diagnostic analysis of melody extraction pipeline.

For each song, classifies every generated note against reference and reports:
  - Error type breakdown (exact_match, pitch_miss, onset_miss, both_miss, FP, FN)
  - Pitch error histogram (semitones, -24 to +24)
  - Onset error stats (mean, std, median in ms)
  - Octave error count (pitch errors that are exactly ±12 or ±24)
  - Note density comparison (notes per second in 5s windows)

Uses the same round-trip approach as evaluate.py (Rule 4).
Reuses existing MusicXML outputs if --reuse-output is set.
"""

import argparse
import glob
import json
import logging
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.musicxml_writer import load_musicxml_notes
from core.pipeline import extract_melody
from core.reference_extractor import extract_reference_melody
from core.types import Note

logger = logging.getLogger(__name__)

# Matching thresholds
STRICT_ONSET_TOL = 0.050   # 50ms — mel_strict criterion
SEARCH_ONSET_TOL = 0.200   # 200ms — nearest-neighbour search window
OCTAVE_SEMITONES = {12, 24}

WINDOW_SIZE = 5.0  # seconds for density comparison


# ---------------------------------------------------------------------------
# Per-note classification
# ---------------------------------------------------------------------------

def _classify_notes(
    gen_notes: List[Note],
    ref_notes: List[Note],
) -> Tuple[List[dict], List[dict]]:
    """Classify each gen note and flag unmatched ref notes.

    Args:
        gen_notes: Generated notes (round-trip loaded).
        ref_notes: Reference notes.

    Returns:
        gen_classified: List of dicts with fields:
            pitch, onset, class_, onset_err_ms, pitch_err_semitones,
            matched_ref_idx (or None)
        ref_matched: List of bool indicating whether each ref note was matched.
    """
    ref_matched = [False] * len(ref_notes)

    # For greedy matching: each ref note can only be used once.
    # Sort ref by onset for binary-search-style lookup.
    ref_sorted_idx = sorted(range(len(ref_notes)), key=lambda i: ref_notes[i].onset)

    gen_classified = []

    for gn in gen_notes:
        # Find ref notes within SEARCH_ONSET_TOL
        candidates = []
        for ri in ref_sorted_idx:
            rn = ref_notes[ri]
            onset_diff = abs(gn.onset - rn.onset)
            if onset_diff <= SEARCH_ONSET_TOL:
                candidates.append((onset_diff, ri, rn))

        if not candidates:
            gen_classified.append({
                "pitch": gn.pitch,
                "onset": gn.onset,
                "class_": "false_positive",
                "onset_err_ms": None,
                "pitch_err_semitones": None,
                "matched_ref_idx": None,
            })
            continue

        # Pick closest by onset (ties broken by pitch proximity)
        candidates.sort(key=lambda c: (c[0], abs(gn.pitch - c[2].pitch)))
        onset_diff, best_ri, best_rn = candidates[0]

        onset_err_ms = (gn.onset - best_rn.onset) * 1000.0  # signed
        pitch_err = gn.pitch - best_rn.pitch                 # signed semitones

        onset_ok = abs(onset_err_ms) <= STRICT_ONSET_TOL * 1000
        pitch_ok = pitch_err == 0

        if onset_ok and pitch_ok:
            cls = "exact_match"
        elif onset_ok and not pitch_ok:
            cls = "pitch_miss"
        elif not onset_ok and pitch_ok:
            cls = "onset_miss"
        else:
            cls = "both_miss"

        # Mark ref note as matched (greedy — first gen note wins)
        if not ref_matched[best_ri]:
            ref_matched[best_ri] = True

        gen_classified.append({
            "pitch": gn.pitch,
            "onset": round(gn.onset, 4),
            "class_": cls,
            "onset_err_ms": round(onset_err_ms, 2),
            "pitch_err_semitones": pitch_err,
            "matched_ref_idx": best_ri,
        })

    return gen_classified, ref_matched


# ---------------------------------------------------------------------------
# Pitch histogram
# ---------------------------------------------------------------------------

def _pitch_histogram(classified: List[dict]) -> Dict[int, int]:
    """Build pitch error histogram for pitch_miss and both_miss notes."""
    hist: Dict[int, int] = defaultdict(int)
    for c in classified:
        if c["class_"] in ("pitch_miss", "both_miss") and c["pitch_err_semitones"] is not None:
            err = c["pitch_err_semitones"]
            if -24 <= err <= 24:
                hist[err] += 1
    return dict(sorted(hist.items()))


# ---------------------------------------------------------------------------
# Onset error stats
# ---------------------------------------------------------------------------

def _onset_stats(classified: List[dict]) -> dict:
    """Compute onset error stats (in ms) for notes that had a ref match."""
    errs = [
        c["onset_err_ms"]
        for c in classified
        if c["onset_err_ms"] is not None
    ]
    if not errs:
        return {"mean_ms": None, "std_ms": None, "median_ms": None, "n": 0}
    mean = statistics.mean(errs)
    std = statistics.stdev(errs) if len(errs) > 1 else 0.0
    med = statistics.median(errs)
    return {
        "mean_ms": round(mean, 2),
        "std_ms": round(std, 2),
        "median_ms": round(med, 2),
        "n": len(errs),
    }


# ---------------------------------------------------------------------------
# Octave error count
# ---------------------------------------------------------------------------

def _octave_error_count(classified: List[dict]) -> int:
    """Count pitch errors that are exactly ±12 or ±24 semitones."""
    count = 0
    for c in classified:
        if c["class_"] in ("pitch_miss", "both_miss") and c["pitch_err_semitones"] is not None:
            if abs(c["pitch_err_semitones"]) in OCTAVE_SEMITONES:
                count += 1
    return count


# ---------------------------------------------------------------------------
# Note density comparison
# ---------------------------------------------------------------------------

def _note_density(notes: List[Note], window: float = WINDOW_SIZE) -> Dict[str, float]:
    """Compute notes-per-second in fixed windows.

    Returns dict keyed by window start (str) -> notes_per_second.
    """
    if not notes:
        return {}
    t_end = max(n.onset + n.duration for n in notes)
    result = {}
    t = 0.0
    while t < t_end:
        count = sum(1 for n in notes if t <= n.onset < t + window)
        result[str(round(t, 1))] = round(count / window, 3)
        t += window
    return result


# ---------------------------------------------------------------------------
# Per-song diagnostics
# ---------------------------------------------------------------------------

def diagnose_song(
    gen_notes: List[Note],
    ref_notes: List[Note],
    song_name: str,
) -> dict:
    """Compute full diagnostics for one song."""

    classified, ref_matched = _classify_notes(gen_notes, ref_notes)

    counts = {
        "exact_match": sum(1 for c in classified if c["class_"] == "exact_match"),
        "pitch_miss": sum(1 for c in classified if c["class_"] == "pitch_miss"),
        "onset_miss": sum(1 for c in classified if c["class_"] == "onset_miss"),
        "both_miss": sum(1 for c in classified if c["class_"] == "both_miss"),
        "false_positive": sum(1 for c in classified if c["class_"] == "false_positive"),
        "false_negative": sum(1 for matched in ref_matched if not matched),
        "gen_total": len(gen_notes),
        "ref_total": len(ref_notes),
    }

    pitch_hist = _pitch_histogram(classified)
    onset_stats = _onset_stats(classified)
    octave_errors = _octave_error_count(classified)

    gen_density = _note_density(gen_notes)
    ref_density = _note_density(ref_notes)

    return {
        "song": song_name,
        "error_counts": counts,
        "pitch_error_histogram": pitch_hist,
        "onset_error_stats": onset_stats,
        "octave_error_count": octave_errors,
        "note_density": {
            "gen_notes_per_sec": gen_density,
            "ref_notes_per_sec": ref_density,
        },
    }


# ---------------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------------

def _aggregate(song_results: List[dict]) -> dict:
    """Compute aggregate stats across all songs."""
    if not song_results:
        return {}

    n = len(song_results)

    def avg(key_path):
        vals = []
        for r in song_results:
            obj = r
            for k in key_path:
                obj = obj.get(k, {})
            if isinstance(obj, (int, float)):
                vals.append(obj)
        return round(sum(vals) / len(vals), 3) if vals else None

    total_counts: Dict[str, int] = defaultdict(int)
    for r in song_results:
        for k, v in r["error_counts"].items():
            total_counts[k] += v

    # Pitch histogram aggregated
    combined_hist: Dict[int, int] = defaultdict(int)
    for r in song_results:
        for k, v in r["pitch_error_histogram"].items():
            combined_hist[int(k)] += v

    # Onset stats — pool all individual error values (approximated via per-song stats)
    onset_mean_vals = [
        r["onset_error_stats"]["mean_ms"]
        for r in song_results
        if r["onset_error_stats"]["mean_ms"] is not None
    ]
    onset_std_vals = [
        r["onset_error_stats"]["std_ms"]
        for r in song_results
        if r["onset_error_stats"]["std_ms"] is not None
    ]
    onset_median_vals = [
        r["onset_error_stats"]["median_ms"]
        for r in song_results
        if r["onset_error_stats"]["median_ms"] is not None
    ]

    octave_total = sum(r["octave_error_count"] for r in song_results)

    # Precision/recall/F1 for strict match
    tp = total_counts["exact_match"]
    fp = total_counts["false_positive"] + total_counts["pitch_miss"] + total_counts["onset_miss"] + total_counts["both_miss"]
    fn = total_counts["false_negative"]
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "total_songs": n,
        "aggregate_error_counts": dict(total_counts),
        "aggregate_strict_metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "aggregate_pitch_histogram": dict(sorted(combined_hist.items())),
        "aggregate_onset_stats": {
            "avg_mean_ms": round(sum(onset_mean_vals) / len(onset_mean_vals), 2) if onset_mean_vals else None,
            "avg_std_ms": round(sum(onset_std_vals) / len(onset_std_vals), 2) if onset_std_vals else None,
            "avg_median_ms": round(sum(onset_median_vals) / len(onset_median_vals), 2) if onset_median_vals else None,
        },
        "total_octave_errors": octave_total,
        "per_song": {
            r["song"]: r["error_counts"] for r in song_results
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_diagnostics(
    input_dir: Path,
    output_dir: Path,
    diag_dir: Path,
    mode: str,
    reuse_output: bool,
) -> None:
    mp3_files = sorted(glob.glob(str(input_dir / "*.mp3")))
    if not mp3_files:
        print(f"No MP3 files found in {input_dir}")
        return

    print(f"Found {len(mp3_files)} songs\n")
    diag_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    song_results = []

    for mp3_path_str in mp3_files:
        mp3_path = Path(mp3_path_str)
        stem = mp3_path.stem
        mxl_path = input_dir / f"{stem}.mxl"

        if not mxl_path.exists():
            print(f"  Skipping {stem}: no matching .mxl reference")
            continue

        print(f"Processing: {stem}")
        start = time.time()

        try:
            cache_dir = input_dir / "cache"
            musicxml_output = output_dir / f"{stem}.musicxml"

            if reuse_output and musicxml_output.exists():
                print(f"  Reusing existing MusicXML: {musicxml_output.name}")
            else:
                extract_melody(
                    mp3_path,
                    cache_dir=cache_dir,
                    output_path=musicxml_output,
                    mode=mode,
                )

            gen_notes = load_musicxml_notes(musicxml_output)
            ref_notes = [n for n in extract_reference_melody(mxl_path) if n.duration > 0]

            result = diagnose_song(gen_notes, ref_notes, stem)
            result["processing_time_s"] = round(time.time() - start, 1)

            ec = result["error_counts"]
            print(
                f"  exact={ec['exact_match']}  pitch_miss={ec['pitch_miss']}  "
                f"onset_miss={ec['onset_miss']}  both_miss={ec['both_miss']}  "
                f"FP={ec['false_positive']}  FN={ec['false_negative']}  "
                f"octave_err={result['octave_error_count']}  "
                f"gen/ref={ec['gen_total']}/{ec['ref_total']}  "
                f"time={result['processing_time_s']}s"
            )

            song_json = diag_dir / f"{stem}.json"
            with open(song_json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            song_results.append(result)

        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            continue

    if not song_results:
        print("No songs processed successfully.")
        return

    summary = _aggregate(song_results)
    summary_path = diag_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Print summary table
    sep = "=" * 105
    print(f"\n{sep}")
    print("DIAGNOSTIC SUMMARY")
    print(sep)
    header = (
        f"{'Song':<30} | {'exact':>6} | {'p_miss':>6} | {'o_miss':>6} | "
        f"{'both':>5} | {'FP':>5} | {'FN':>5} | {'oct_err':>7} | "
        f"{'gen/ref':>9}"
    )
    print(header)
    print("-" * 105)

    for r in song_results:
        ec = r["error_counts"]
        print(
            f"{r['song']:<30} | {ec['exact_match']:>6} | {ec['pitch_miss']:>6} | "
            f"{ec['onset_miss']:>6} | {ec['both_miss']:>5} | {ec['false_positive']:>5} | "
            f"{ec['false_negative']:>5} | {r['octave_error_count']:>7} | "
            f"{ec['gen_total']:>4}/{ec['ref_total']:<4}"
        )

    print("-" * 105)
    agg = summary["aggregate_error_counts"]
    sm = summary["aggregate_strict_metrics"]
    print(
        f"{'TOTAL':<30} | {agg.get('exact_match',0):>6} | {agg.get('pitch_miss',0):>6} | "
        f"{agg.get('onset_miss',0):>6} | {agg.get('both_miss',0):>5} | "
        f"{agg.get('false_positive',0):>5} | {agg.get('false_negative',0):>5} | "
        f"{summary['total_octave_errors']:>7} | "
        f"{agg.get('gen_total',0):>4}/{agg.get('ref_total',0):<4}"
    )
    print()
    print(
        f"Aggregate strict P={sm['precision']:.4f}  R={sm['recall']:.4f}  F1={sm['f1']:.4f}"
    )

    onset_s = summary["aggregate_onset_stats"]
    if onset_s["avg_mean_ms"] is not None:
        print(
            f"Onset error (avg across songs): "
            f"mean={onset_s['avg_mean_ms']:+.1f}ms  "
            f"std={onset_s['avg_std_ms']:.1f}ms  "
            f"median={onset_s['avg_median_ms']:+.1f}ms"
        )

    print(f"\nPer-song JSON: {diag_dir}/{{song}}.json")
    print(f"Summary JSON:  {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostic analysis of melody extraction (Rule 4 round-trip)"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("test"),
        help="Directory with .mp3 and .mxl files (default: test)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for MusicXML pipeline outputs (default: output/)",
    )
    parser.add_argument(
        "--diag-dir",
        type=Path,
        default=Path("results/diagnostics"),
        help="Directory for diagnostic JSON outputs (default: results/diagnostics/)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="fcpe",
        choices=["crepe", "fcpe", "rmvpe", "ensemble", "onset", "bp"],
        help="F0 extraction mode (default: fcpe)",
    )
    parser.add_argument(
        "--reuse-output",
        action="store_true",
        help="Skip extraction if MusicXML already exists in --output-dir",
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

    run_diagnostics(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        diag_dir=args.diag_dir,
        mode=args.mode,
        reuse_output=args.reuse_output,
    )


if __name__ == "__main__":
    main()
