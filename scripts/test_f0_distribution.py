#!/usr/bin/env python3
"""Analyze CREPE F0 distribution within each note to understand flat bias.

Key question: Is the continuous F0 at the semitone boundary? Would different
rounding (e.g., round up from 0.3 instead of 0.5) fix the flat bias?

Also tests pYIN (autocorrelation-based, not neural) as a third opinion.
"""

import sys
from pathlib import Path
import numpy as np
from collections import Counter

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

TEST_MP3 = Path("test/꿈의 버스.mp3")
TEST_MXL = Path("test/꿈의 버스.mxl")
CACHE_DIR = Path("test/cache")

CREPE_SR = 16000
CREPE_HOP = 160


def main():
    # Load reference and vocals
    ref_notes = [n for n in extract_reference_melody(TEST_MXL) if n.duration > 0]
    vocals, sr = separate_vocals(TEST_MP3, CACHE_DIR)
    vocals_f32 = vocals.astype(np.float32)

    # Run BP pipeline
    bp_notes = _run_bp_pipeline(vocals_f32, sr)
    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)
    shift = _determine_octave_shift(bp_notes, sal_w, midi_bins, times_cqt)
    bp_shifted = [
        Note(pitch=n.pitch + shift, onset=n.onset, duration=n.duration, velocity=n.velocity)
        for n in bp_notes
        if _VOCAL_MIDI_LOW - 3 <= n.pitch + shift <= _VOCAL_MIDI_HIGH + 5
    ]
    bp_shifted = _per_note_octave_correction(bp_shifted, sal_w, midi_bins, times_cqt)
    print(f"BP notes: {len(bp_shifted)}")

    # Run CREPE on harmonic vocals
    vocals_harm = librosa.effects.harmonic(vocals_f32, margin=8.0)
    y_16k = librosa.resample(vocals_harm, orig_sr=sr, target_sr=CREPE_SR)
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
    f0_hz = pitch.squeeze(0).cpu().numpy()
    conf = periodicity.squeeze(0).cpu().numpy()
    f0_hz = torchcrepe.filter.median(torch.tensor(f0_hz).unsqueeze(0), 3).squeeze(0).numpy()

    hop_sec = CREPE_HOP / CREPE_SR
    times = np.arange(len(f0_hz)) * hop_sec

    # Convert to continuous MIDI
    voiced = (conf >= 0.4) & (f0_hz > 0)
    f0_midi = np.full_like(f0_hz, np.nan)
    f0_midi[voiced] = 12.0 * np.log2(f0_hz[voiced] / 440.0) + 69.0

    # Also run pYIN on full vocals
    print("\nRunning pYIN...")
    pyin_f0, pyin_voiced, pyin_prob = librosa.pyin(
        vocals_harm, fmin=librosa.midi_to_hz(55), fmax=librosa.midi_to_hz(95),
        sr=sr, frame_length=2048,
    )
    pyin_times = librosa.times_like(pyin_f0, sr=sr, hop_length=512)
    pyin_midi = np.full_like(pyin_f0, np.nan)
    pyin_v = pyin_voiced & (~np.isnan(pyin_f0)) & (pyin_f0 > 0)
    pyin_midi[pyin_v] = 12.0 * np.log2(pyin_f0[pyin_v] / 440.0) + 69.0
    print(f"pYIN: {len(pyin_f0)} frames, {np.sum(pyin_v)} voiced")

    # Match BP notes to ref notes for analysis
    bp_aligned = apply_sectional_time_offset(bp_shifted, ref_notes)
    ref_sorted = sorted(ref_notes, key=lambda n: n.onset)

    # For each matched note pair, analyze F0 distribution
    print("\n" + "=" * 90)
    print("F0 DISTRIBUTION ANALYSIS FOR FLAT NOTES")
    print("=" * 90)
    print(f"{'#':<3} | {'REF':<4} | {'BP':<4} | {'Δ':<3} | {'CREPE_med':<10} | {'CREPE_frac':<10} | {'pYIN_med':<10} | {'pYIN_frac':<10} | {'Q75cr':<6} | {'Q75py':<6}")
    print("-" * 90)

    flat_notes = []
    correct_notes = []
    n_flat_fixable_crepe = 0
    n_flat_fixable_pyin = 0
    all_crepe_fracs = []
    all_pyin_fracs = []

    count = 0
    for rn in ref_sorted:
        bp_match = min(bp_aligned, key=lambda n: abs(n.onset - rn.onset), default=None)
        if not bp_match or abs(bp_match.onset - rn.onset) >= 0.2:
            continue

        delta = bp_match.pitch - rn.pitch
        if abs(delta) > 5 and abs(delta) != 12:
            continue  # skip wild mismatches

        # Find CREPE F0 in this note's window (use bp_match for original timing)
        # Need original note timing (before alignment)
        orig_bp = min(bp_shifted, key=lambda n: abs(n.onset - (bp_match.onset)), default=None)
        if not orig_bp:
            continue

        # Actually, use the original bp_shifted onset for F0 lookup
        # We need the aligned onset for ref matching, but original for audio lookup
        # This is tricky - let's use a different approach
        # Find the bp_shifted note closest to bp_match by pitch and rough timing
        best_orig = None
        best_dist = float('inf')
        for bn in bp_shifted:
            if bn.pitch == bp_match.pitch:
                d = abs(bn.onset - bp_match.onset)
                if d < best_dist and d < 5.0:
                    best_dist = d
                    best_orig = bn
        if not best_orig:
            continue

        # CREPE F0 distribution
        cr_mask = (times >= best_orig.onset) & (times < best_orig.onset + best_orig.duration) & voiced
        cr_frames = f0_midi[cr_mask]

        # pYIN F0 distribution
        py_mask = (pyin_times >= best_orig.onset) & (pyin_times < best_orig.onset + best_orig.duration) & pyin_v
        py_frames = pyin_midi[py_mask]

        if len(cr_frames) < 2 and len(py_frames) < 2:
            continue

        cr_med = float(np.median(cr_frames)) if len(cr_frames) > 0 else float('nan')
        cr_frac = cr_med - int(cr_med) if not np.isnan(cr_med) else float('nan')
        cr_q75 = float(np.percentile(cr_frames, 75)) if len(cr_frames) > 0 else float('nan')
        cr_q75_pitch = int(round(cr_q75)) if not np.isnan(cr_q75) else -1

        py_med = float(np.median(py_frames)) if len(py_frames) > 0 else float('nan')
        py_frac = py_med - int(py_med) if not np.isnan(py_med) else float('nan')
        py_q75 = float(np.percentile(py_frames, 75)) if len(py_frames) > 0 else float('nan')
        py_q75_pitch = int(round(py_q75)) if not np.isnan(py_q75) else -1

        if not np.isnan(cr_frac):
            all_crepe_fracs.append(cr_frac)
        if not np.isnan(py_frac):
            all_pyin_fracs.append(py_frac)

        is_flat = delta in [-1, -2]

        if is_flat:
            flat_notes.append((rn.pitch, bp_match.pitch, cr_med, py_med, cr_q75, py_q75))
            if cr_q75_pitch == rn.pitch:
                n_flat_fixable_crepe += 1
            if py_q75_pitch == rn.pitch:
                n_flat_fixable_pyin += 1

        if delta == 0:
            correct_notes.append((rn.pitch, bp_match.pitch, cr_med, py_med))

        if count < 50 and (is_flat or delta == 0):
            marker = " FLAT" if is_flat else ""
            print(f"{count+1:<3} | {rn.pitch:<4} | {bp_match.pitch:<4} | {delta:+2d} | {cr_med:<10.2f} | {cr_frac:<10.3f} | {py_med:<10.2f} | {py_frac:<10.3f} | {cr_q75_pitch:<6} | {py_q75_pitch:<6}{marker}")
            count += 1

    print(f"\n--- Summary ---")
    print(f"Flat notes analyzed: {len(flat_notes)}")
    print(f"Correct notes analyzed: {len(correct_notes)}")
    print(f"Flat fixable by CREPE Q75: {n_flat_fixable_crepe}/{len(flat_notes)}")
    print(f"Flat fixable by pYIN Q75: {n_flat_fixable_pyin}/{len(flat_notes)}")

    if all_crepe_fracs:
        fracs = np.array(all_crepe_fracs)
        print(f"\nCREPE fractional MIDI (all notes):")
        print(f"  Mean: {np.mean(fracs):.3f}")
        print(f"  Std:  {np.std(fracs):.3f}")
        print(f"  Histogram:")
        for lo in np.arange(0, 1, 0.1):
            hi = lo + 0.1
            cnt = np.sum((fracs >= lo) & (fracs < hi))
            bar = "#" * int(cnt / len(fracs) * 50)
            print(f"    [{lo:.1f}-{hi:.1f}): {cnt:3d} ({100*cnt/len(fracs):5.1f}%) {bar}")

    if all_pyin_fracs:
        fracs = np.array(all_pyin_fracs)
        print(f"\npYIN fractional MIDI (all notes):")
        print(f"  Mean: {np.mean(fracs):.3f}")
        print(f"  Std:  {np.std(fracs):.3f}")

    # Test different rounding thresholds
    print(f"\n--- Testing different rounding strategies ---")
    for strategy_name, agg_fn in [
        ("median (default)", lambda x: int(round(float(np.median(x))))),
        ("mode (most common MIDI)", lambda x: Counter(np.round(x).astype(int)).most_common(1)[0][0]),
        ("Q60 (60th percentile)", lambda x: int(round(float(np.percentile(x, 60))))),
        ("Q75 (75th percentile)", lambda x: int(round(float(np.percentile(x, 75))))),
        ("ceil-biased (round from 0.3)", lambda x: int(np.floor(float(np.median(x)) + 0.2))),
    ]:
        # Build notes with this strategy using CREPE
        crepe_notes = []
        for n in bp_shifted:
            mask = (times >= n.onset) & (times < n.onset + n.duration) & voiced
            frames = f0_midi[mask]
            if len(frames) >= 3:
                try:
                    p = agg_fn(frames)
                    # Constrain to ±6 of BP
                    if abs(p - n.pitch) <= 6:
                        crepe_notes.append(Note(pitch=p, onset=n.onset, duration=n.duration, velocity=n.velocity))
                    else:
                        crepe_notes.append(n)
                except:
                    crepe_notes.append(n)
            else:
                crepe_notes.append(n)

        aligned = apply_sectional_time_offset(crepe_notes, ref_notes)
        metrics = compare_melodies(ref_notes, aligned)
        print(f"  {strategy_name:<30}: pc_f1={metrics['pitch_class_f1']:.3f}, mel_len={metrics['melody_f1_lenient']:.3f}")

        # Same with pYIN
        pyin_notes = []
        for n in bp_shifted:
            mask = (pyin_times >= n.onset) & (pyin_times < n.onset + n.duration) & pyin_v
            frames = pyin_midi[mask]
            if len(frames) >= 3:
                try:
                    p = agg_fn(frames)
                    if abs(p - n.pitch) <= 6:
                        pyin_notes.append(Note(pitch=p, onset=n.onset, duration=n.duration, velocity=n.velocity))
                    else:
                        pyin_notes.append(n)
                except:
                    pyin_notes.append(n)
            else:
                pyin_notes.append(n)

        aligned = apply_sectional_time_offset(pyin_notes, ref_notes)
        metrics = compare_melodies(ref_notes, aligned)
        print(f"  {strategy_name:<30}: pc_f1={metrics['pitch_class_f1']:.3f}, mel_len={metrics['melody_f1_lenient']:.3f}  (pYIN)")

    # Baseline for comparison
    bp_al = apply_sectional_time_offset(bp_shifted, ref_notes)
    bp_m = compare_melodies(ref_notes, bp_al)
    print(f"\n  {'BP baseline':<30}: pc_f1={bp_m['pitch_class_f1']:.3f}, mel_len={bp_m['melody_f1_lenient']:.3f}")


if __name__ == "__main__":
    main()
