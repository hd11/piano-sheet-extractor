#!/usr/bin/env python3
"""Test FCPE (Fast Context-based Pitch Estimator) as vocal pitch source.

FCPE is a singing-voice-specific F0 extractor (torchfcpe). Unlike BP/CREPE/pYIN
which are general-purpose, FCPE was trained on singing data and handles vibrato,
breathiness, and vocal nuances differently.

Test: Use BP for onset/duration + FCPE for pitch determination.
Also test FCPE standalone with same note segmentation as CREPE pipeline.
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


def run_fcpe(vocals: np.ndarray, sr: int, hop_ms: float = 10.0):
    """Run FCPE on vocals, return (f0_hz, confidence, times)."""
    from torchfcpe import spawn_bundled_infer_model

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = spawn_bundled_infer_model(device=device)

    # FCPE expects (batch, samples) at original sr
    audio_t = torch.from_numpy(vocals).unsqueeze(0).float().to(device)

    hop_length = int(sr * hop_ms / 1000.0)

    # Run FCPE
    f0 = model.infer(
        audio_t,
        sr=sr,
        decoder_mode="local_argmax",  # or "argmax"
        threshold=0.006,
    )
    # f0 shape: (batch, frames, 1)
    f0 = f0.squeeze(0).squeeze(-1).cpu().numpy()  # (frames,)

    # FCPE doesn't return confidence directly, use f0 > 0 as voiced
    confidence = (f0 > 0).astype(float)

    # Generate time axis
    # FCPE's hop length depends on internal implementation
    # Typically outputs at ~10ms resolution
    times = np.arange(len(f0)) * hop_ms / 1000.0

    print(f"FCPE: {len(f0)} frames, voiced={np.sum(f0 > 0)}, "
          f"range={np.min(f0[f0>0]):.1f}-{np.max(f0[f0>0]):.1f} Hz")

    return f0, confidence, times


def snap_to_bp_octave(crepe_midi_frames, bp_pitch):
    """Snap F0 MIDI values to BP's octave."""
    bp_octave = bp_pitch // 12
    pc = crepe_midi_frames % 12
    candidates = np.stack([
        (bp_octave - 1) * 12 + pc,
        bp_octave * 12 + pc,
        (bp_octave + 1) * 12 + pc,
    ])
    dists = np.abs(candidates - bp_pitch)
    best = np.argmin(dists, axis=0)
    return candidates[best, np.arange(len(crepe_midi_frames))]


def build_hybrid_notes(bp_notes, f0_hz, voiced, times, strategy="median", max_delta=3):
    """Build notes using BP onset + F0 pitch with octave snap."""
    f0_midi = np.full_like(f0_hz, np.nan)
    v_mask = voiced & (f0_hz > 0)
    f0_midi[v_mask] = 12.0 * np.log2(f0_hz[v_mask] / 440.0) + 69.0

    agg_fns = {
        "median": lambda x: int(round(float(np.median(x)))),
        "mode": lambda x: Counter(np.round(x).astype(int)).most_common(1)[0][0],
        "Q75": lambda x: int(round(float(np.percentile(x, 75)))),
    }
    agg_fn = agg_fns[strategy]

    result = []
    n_changed = 0

    for n in bp_notes:
        mask = (times >= n.onset) & (times < n.onset + n.duration) & v_mask
        frames = f0_midi[mask]

        if len(frames) < 3:
            result.append(n)
            continue

        snapped = snap_to_bp_octave(frames, n.pitch)
        try:
            p = agg_fn(snapped)
        except:
            result.append(n)
            continue

        delta = p - n.pitch
        if abs(delta) <= max_delta and delta != 0:
            result.append(Note(pitch=p, onset=n.onset, duration=n.duration, velocity=n.velocity))
            n_changed += 1
        else:
            result.append(n)

    return result, n_changed


def main():
    print("=" * 70)
    print("FCPE SINGING VOICE PITCH ESTIMATION TEST")
    print("=" * 70)

    ref_notes = [n for n in extract_reference_melody(TEST_MXL) if n.duration > 0]
    vocals, sr = separate_vocals(TEST_MP3, CACHE_DIR)
    vocals_f32 = vocals.astype(np.float32)

    # BP pipeline (baseline)
    bp_notes = _run_bp_pipeline(vocals_f32, sr)
    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)
    shift = _determine_octave_shift(bp_notes, sal_w, midi_bins, times_cqt)
    bp_shifted = [
        Note(pitch=n.pitch + shift, onset=n.onset, duration=n.duration, velocity=n.velocity)
        for n in bp_notes
        if _VOCAL_MIDI_LOW - 3 <= n.pitch + shift <= _VOCAL_MIDI_HIGH + 5
    ]
    bp_shifted = _per_note_octave_correction(bp_shifted, sal_w, midi_bins, times_cqt)

    bp_al = apply_sectional_time_offset(bp_shifted, ref_notes)
    bp_m = compare_melodies(ref_notes, bp_al)
    print(f"\nBP baseline: {len(bp_shifted)} notes, pc_f1={bp_m['pitch_class_f1']:.3f}, "
          f"mel_len={bp_m['melody_f1_lenient']:.3f}")

    # Run FCPE
    print("\n--- Running FCPE ---")
    vocals_harm = librosa.effects.harmonic(vocals_f32, margin=8.0)

    try:
        fcpe_f0, fcpe_conf, fcpe_times = run_fcpe(vocals_harm, sr)
    except Exception as e:
        print(f"FCPE failed: {e}")
        print("Trying with different parameters...")
        try:
            fcpe_f0, fcpe_conf, fcpe_times = run_fcpe(vocals_f32, sr)
        except Exception as e2:
            print(f"FCPE also failed on raw vocals: {e2}")
            return

    # Run CREPE for comparison
    print("\n--- Running CREPE ---")
    y_16k = librosa.resample(vocals_harm, orig_sr=sr, target_sr=16000)
    audio_t = torch.from_numpy(y_16k).unsqueeze(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    pitch, periodicity = torchcrepe.predict(
        audio_t, 16000, 160,
        fmin=50, fmax=1000, model="full", device=device,
        return_periodicity=True, batch_size=512,
        decoder=torchcrepe.decode.viterbi,
    )
    cr_f0 = pitch.squeeze(0).cpu().numpy()
    cr_conf = periodicity.squeeze(0).cpu().numpy()
    cr_f0 = torchcrepe.filter.median(torch.tensor(cr_f0).unsqueeze(0), 3).squeeze(0).numpy()
    cr_times = np.arange(len(cr_f0)) * 0.01

    # Compare FCPE vs CREPE vs BP on per-note basis
    print(f"\n{'='*70}")
    print("COMPARISON: FCPE vs CREPE vs BP")
    print(f"{'='*70}")

    # Test hybrid strategies
    print(f"\n{'Strategy':<35} | {'Δ notes':<8} | {'pc_f1':<8} | {'Δ pc_f1':<8} | {'mel_len':<8}")
    print("-" * 75)

    for estimator, f0, conf, times in [
        ("FCPE", fcpe_f0, fcpe_conf, fcpe_times),
        ("CREPE", cr_f0, cr_conf, cr_times),
    ]:
        voiced = (conf >= 0.4) & (f0 > 0) if estimator == "CREPE" else (f0 > 0)

        for strategy in ["median", "Q75"]:
            for max_d in [2, 3]:
                notes, n_changed = build_hybrid_notes(
                    bp_shifted, f0, voiced, times, strategy=strategy, max_delta=max_d
                )
                aligned = apply_sectional_time_offset(notes, ref_notes)
                m = compare_melodies(ref_notes, aligned)
                d_pc = m['pitch_class_f1'] - bp_m['pitch_class_f1']
                label = f"{estimator} {strategy} (±{max_d})"
                print(f"  {label:<35} | {n_changed:<8} | {m['pitch_class_f1']:<8.3f} | "
                      f"{d_pc:+8.3f} | {m['melody_f1_lenient']:<8.3f}")

    # Also check: does FCPE give DIFFERENT pitches than BP/CREPE?
    print(f"\n--- FCPE vs CREPE pitch agreement ---")
    fcpe_voiced = fcpe_f0 > 0
    fcpe_midi = np.full_like(fcpe_f0, np.nan)
    fcpe_midi[fcpe_voiced] = 12.0 * np.log2(fcpe_f0[fcpe_voiced] / 440.0) + 69.0

    cr_voiced = (cr_conf >= 0.4) & (cr_f0 > 0)
    cr_midi = np.full_like(cr_f0, np.nan)
    cr_midi[cr_voiced] = 12.0 * np.log2(cr_f0[cr_voiced] / 440.0) + 69.0

    agree = 0
    disagree = 0
    disagree_deltas = []

    for n in bp_shifted:
        # FCPE pitch
        f_mask = (fcpe_times >= n.onset) & (fcpe_times < n.onset + n.duration) & fcpe_voiced
        f_frames = fcpe_midi[f_mask]

        # CREPE pitch
        c_mask = (cr_times >= n.onset) & (cr_times < n.onset + n.duration) & cr_voiced
        c_frames = cr_midi[c_mask]

        if len(f_frames) >= 3 and len(c_frames) >= 3:
            f_snapped = snap_to_bp_octave(f_frames, n.pitch)
            c_snapped = snap_to_bp_octave(c_frames, n.pitch)

            f_pitch = int(round(float(np.median(f_snapped))))
            c_pitch = int(round(float(np.median(c_snapped))))

            if f_pitch == c_pitch:
                agree += 1
            else:
                disagree += 1
                disagree_deltas.append(f_pitch - c_pitch)

    total = agree + disagree
    print(f"  Agree: {agree}/{total} ({100*agree/total:.1f}%)")
    print(f"  Disagree: {disagree}/{total} ({100*disagree/total:.1f}%)")
    if disagree_deltas:
        print(f"  Disagreement deltas: {Counter(disagree_deltas).most_common(10)}")


if __name__ == "__main__":
    main()
