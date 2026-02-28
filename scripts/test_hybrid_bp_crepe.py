#!/usr/bin/env python3
"""Test hybrid BP onset + CREPE pitch approach.

Hypothesis: BP is good at note onset/offset detection but has 43% flat bias.
CREPE is better at pitch accuracy. Use BP for timing, CREPE for pitch.

Test plan:
1. Load cached vocals for 꿈의 버스
2. Run BP pipeline (existing) to get onsets/durations
3. Run CREPE on full vocals to get frame-level F0
4. For each BP note, use CREPE's median F0 in that time window as pitch
5. Compare: BP-only pitch vs CREPE-refined pitch vs reference
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import (
    _run_bp_pipeline, _compute_cqt_salience, _determine_octave_shift,
    _per_note_octave_correction, _VOCAL_MIDI_LOW, _VOCAL_MIDI_HIGH,
)
from core.vocal_separator import separate_vocals
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies
from core.postprocess import apply_sectional_time_offset
from core.types import Note

import librosa
import torch
import torchcrepe

# ── Config ──────────────────────────────────────────────────────────────────
TEST_MP3 = Path("test/꿈의 버스.mp3")
TEST_MXL = Path("test/꿈의 버스.mxl")
CACHE_DIR = Path("test/cache")

CREPE_SR = 16000
CREPE_HOP = 160  # 10ms frames
CREPE_CONF_THRESH = 0.4  # voiced confidence threshold


def run_crepe_f0(vocals: np.ndarray, sr: int):
    """Run CREPE on full vocals, return (f0_hz, confidence, times)."""
    y_16k = librosa.resample(vocals, orig_sr=sr, target_sr=CREPE_SR)
    audio = torch.from_numpy(y_16k).unsqueeze(0)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    pitch, periodicity = torchcrepe.predict(
        audio, CREPE_SR, CREPE_HOP,
        fmin=50, fmax=1000,
        model="full", device=device,
        return_periodicity=True,
        batch_size=512,
        decoder=torchcrepe.decode.viterbi,
    )

    f0 = pitch.squeeze(0).cpu().numpy()
    conf = periodicity.squeeze(0).cpu().numpy()
    # Median filter for smoothing
    f0 = torchcrepe.filter.median(torch.tensor(f0).unsqueeze(0), 3).squeeze(0).numpy()

    hop_sec = CREPE_HOP / CREPE_SR
    times = np.arange(len(f0)) * hop_sec

    print(f"CREPE: {len(f0)} frames, hop={hop_sec*1000:.1f}ms")
    return f0, conf, times


def hybrid_bp_crepe(bp_notes: list[Note], f0_hz: np.ndarray, conf: np.ndarray,
                     times: np.ndarray, constrain_range: int = 6) -> list[Note]:
    """Replace BP pitch with CREPE's median pitch for each note.

    Args:
        bp_notes: Notes from BP pipeline (with correct octave shift applied)
        f0_hz: CREPE F0 in Hz, frame-level
        conf: CREPE confidence, frame-level
        times: Time stamps for each frame
        constrain_range: Max semitone deviation from BP pitch to accept CREPE

    Returns:
        Notes with CREPE-refined pitch
    """
    voiced = (conf >= CREPE_CONF_THRESH) & (f0_hz > 0)
    f0_midi = np.full_like(f0_hz, np.nan)
    f0_midi[voiced] = 12.0 * np.log2(f0_hz[voiced] / 440.0) + 69.0

    result = []
    n_replaced = 0
    n_kept = 0
    n_nodata = 0
    deltas = []

    for n in bp_notes:
        # Find CREPE frames within this note's time window
        mask = (times >= n.onset) & (times < n.onset + n.duration) & voiced

        if np.sum(mask) < 3:
            result.append(n)
            n_nodata += 1
            continue

        crepe_pitches = f0_midi[mask]
        crepe_median = float(np.median(crepe_pitches))
        crepe_pitch = int(round(crepe_median))

        # Handle octave mismatch: snap CREPE to nearest octave of BP
        bp_pc = n.pitch % 12
        crepe_pc = crepe_pitch % 12

        # If pitch class is similar but octave is different, use BP's octave
        if abs(crepe_pitch - n.pitch) > constrain_range:
            # Try snapping to BP's octave
            bp_octave = n.pitch // 12
            snapped = bp_octave * 12 + crepe_pc
            if abs(snapped - n.pitch) <= constrain_range:
                crepe_pitch = snapped
            elif abs(snapped + 12 - n.pitch) <= constrain_range:
                crepe_pitch = snapped + 12
            elif abs(snapped - 12 - n.pitch) <= constrain_range:
                crepe_pitch = snapped - 12
            else:
                # CREPE too far from BP, keep BP
                result.append(n)
                n_kept += 1
                continue

        delta = crepe_pitch - n.pitch
        deltas.append(delta)

        if delta != 0:
            result.append(Note(
                pitch=crepe_pitch, onset=n.onset,
                duration=n.duration, velocity=n.velocity,
            ))
            n_replaced += 1
        else:
            result.append(n)
            n_kept += 1

    print(f"\nHybrid results:")
    print(f"  Replaced: {n_replaced}/{len(bp_notes)} ({100*n_replaced/len(bp_notes):.1f}%)")
    print(f"  Kept BP:  {n_kept}/{len(bp_notes)} ({100*n_kept/len(bp_notes):.1f}%)")
    print(f"  No data:  {n_nodata}/{len(bp_notes)} ({100*n_nodata/len(bp_notes):.1f}%)")

    if deltas:
        deltas = np.array(deltas)
        print(f"  Delta distribution:")
        for d in range(-6, 7):
            count = np.sum(deltas == d)
            if count > 0:
                print(f"    {d:+d}: {count} ({100*count/len(deltas):.1f}%)")

    return result


def main():
    print("=" * 70)
    print("HYBRID BP+CREPE DIAGNOSTIC")
    print("=" * 70)

    # Load reference
    ref_notes = [n for n in extract_reference_melody(TEST_MXL) if n.duration > 0]
    print(f"\nReference: {len(ref_notes)} notes")

    # Load vocals
    vocals, sr = separate_vocals(TEST_MP3, CACHE_DIR)
    vocals_f32 = vocals.astype(np.float32)
    print(f"Vocals: {len(vocals)/sr:.1f}s, sr={sr}")

    # Step 1: Run BP pipeline
    print("\n--- Step 1: BP Pipeline ---")
    bp_notes = _run_bp_pipeline(vocals_f32, sr)
    print(f"BP raw: {len(bp_notes)} notes")

    # Step 2: CQT octave shift (same as extract_melody)
    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)
    shift = _determine_octave_shift(bp_notes, sal_w, midi_bins, times_cqt)

    bp_shifted = [
        Note(pitch=n.pitch + shift, onset=n.onset, duration=n.duration, velocity=n.velocity)
        for n in bp_notes
        if _VOCAL_MIDI_LOW - 3 <= n.pitch + shift <= _VOCAL_MIDI_HIGH + 5
    ]
    bp_shifted = _per_note_octave_correction(bp_shifted, sal_w, midi_bins, times_cqt)
    print(f"BP after octave correction: {len(bp_shifted)} notes, shift={shift:+d}")

    # Step 3: Run CREPE on full vocals
    print("\n--- Step 2: CREPE F0 ---")
    # Use harmonic-enhanced vocals for cleaner pitch
    vocals_harm = librosa.effects.harmonic(vocals_f32, margin=8.0)
    f0_hz, conf, times = run_crepe_f0(vocals_harm, sr)

    # Step 4: Hybrid — replace BP pitch with CREPE pitch
    print("\n--- Step 3: Hybrid BP+CREPE ---")
    hybrid_notes = hybrid_bp_crepe(bp_shifted, f0_hz, conf, times)

    # Step 5: Evaluate all three approaches
    print("\n" + "=" * 70)
    print("EVALUATION")
    print("=" * 70)

    # BP-only (current pipeline)
    bp_aligned = apply_sectional_time_offset(bp_shifted, ref_notes)
    bp_metrics = compare_melodies(ref_notes, bp_aligned)

    # Hybrid
    hybrid_aligned = apply_sectional_time_offset(hybrid_notes, ref_notes)
    hybrid_metrics = compare_melodies(ref_notes, hybrid_aligned)

    # Also test CREPE-only pitch (no constraint to BP range)
    # More aggressive: use CREPE pitch even if far from BP
    hybrid_aggressive = hybrid_bp_crepe(bp_shifted, f0_hz, conf, times, constrain_range=12)
    aggressive_aligned = apply_sectional_time_offset(hybrid_aggressive, ref_notes)
    aggressive_metrics = compare_melodies(ref_notes, aggressive_aligned)

    print(f"\n{'Metric':<25} | {'BP-only':<10} | {'Hybrid(±6)':<10} | {'Hybrid(±12)':<10}")
    print("-" * 65)
    for key in ['pitch_class_f1', 'pitch_class_precision', 'pitch_class_recall',
                'melody_f1_lenient', 'contour_similarity', 'interval_similarity',
                'chroma_similarity']:
        bp_v = bp_metrics.get(key, 0)
        hy_v = hybrid_metrics.get(key, 0)
        ag_v = aggressive_metrics.get(key, 0)
        delta1 = hy_v - bp_v
        delta2 = ag_v - bp_v
        print(f"  {key:<23} | {bp_v:<10.3f} | {hy_v:<10.3f} ({delta1:+.3f}) | {ag_v:<10.3f} ({delta2:+.3f})")

    # Per-note accuracy comparison (first 30 notes)
    print(f"\n--- Per-note comparison (first 30 matched notes) ---")
    print(f"{'#':<3} | {'REF':<5} | {'BP':<5} | {'CREPE':<5} | {'BP err':<6} | {'CR err':<6} | {'Winner':<7}")
    print("-" * 55)

    # Simple onset matching for diagnostic
    bp_al = sorted(bp_aligned, key=lambda n: n.onset)
    hy_al = sorted(hybrid_aligned, key=lambda n: n.onset)
    ref_sorted = sorted(ref_notes, key=lambda n: n.onset)

    count = 0
    bp_wins = 0
    crepe_wins = 0
    ties = 0

    for rn in ref_sorted:
        if count >= 30:
            break
        # Find nearest BP note
        bp_match = min(bp_al, key=lambda n: abs(n.onset - rn.onset), default=None)
        hy_match = min(hy_al, key=lambda n: abs(n.onset - rn.onset), default=None)

        if bp_match and abs(bp_match.onset - rn.onset) < 0.2:
            if hy_match and abs(hy_match.onset - rn.onset) < 0.2:
                bp_err = abs(bp_match.pitch - rn.pitch)
                cr_err = abs(hy_match.pitch - rn.pitch)

                if bp_err < cr_err:
                    winner = "BP"
                    bp_wins += 1
                elif cr_err < bp_err:
                    winner = "CREPE"
                    crepe_wins += 1
                else:
                    winner = "TIE"
                    ties += 1

                print(f"{count+1:<3} | {rn.pitch:<5} | {bp_match.pitch:<5} | {hy_match.pitch:<5} | {bp_err:<6} | {cr_err:<6} | {winner:<7}")
                count += 1

    print(f"\nWinner tally (first {count}): BP={bp_wins}, CREPE={crepe_wins}, TIE={ties}")


if __name__ == "__main__":
    main()
