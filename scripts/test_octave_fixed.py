#!/usr/bin/env python3
"""Test CREPE/pYIN pitch with octave-corrected comparison.

Previous test had a bug: CREPE detects at octave 4, BP at octave 5.
The ±6 constraint filtered everything. Fix: snap CREPE to BP's octave first.
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


def snap_to_bp_octave(crepe_midi_frames: np.ndarray, bp_pitch: int) -> np.ndarray:
    """Snap continuous CREPE MIDI values to BP's octave.

    Keeps CREPE's pitch class but uses BP's octave.
    For each frame, finds the nearest octave of bp_pitch.
    """
    bp_octave = bp_pitch // 12
    crepe_pc = crepe_midi_frames % 12  # fractional pitch class

    # Candidate snapped values at bp_octave and bp_octave±1
    candidates = np.stack([
        (bp_octave - 1) * 12 + crepe_pc,
        bp_octave * 12 + crepe_pc,
        (bp_octave + 1) * 12 + crepe_pc,
    ])  # shape (3, N)

    # Pick the candidate closest to bp_pitch
    dists = np.abs(candidates - bp_pitch)
    best = np.argmin(dists, axis=0)
    snapped = candidates[best, np.arange(len(crepe_midi_frames))]
    return snapped


def build_notes_with_strategy(bp_notes, f0_midi, voiced, times, agg_fn, max_delta=3):
    """Build notes using CREPE F0 with octave-snapping to BP."""
    result = []
    n_changed = 0

    for n in bp_notes:
        mask = (times >= n.onset) & (times < n.onset + n.duration) & voiced
        frames = f0_midi[mask]

        if len(frames) < 3:
            result.append(n)
            continue

        # Snap CREPE frames to BP's octave
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
    ref_notes = [n for n in extract_reference_melody(TEST_MXL) if n.duration > 0]
    vocals, sr = separate_vocals(TEST_MP3, CACHE_DIR)
    vocals_f32 = vocals.astype(np.float32)

    # BP pipeline
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

    # CREPE on harmonic vocals
    vocals_harm = librosa.effects.harmonic(vocals_f32, margin=8.0)
    y_16k = librosa.resample(vocals_harm, orig_sr=sr, target_sr=CREPE_SR)
    audio = torch.from_numpy(y_16k).unsqueeze(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    pitch, periodicity = torchcrepe.predict(
        audio, CREPE_SR, CREPE_HOP,
        fmin=50, fmax=1000, model="full", device=device,
        return_periodicity=True, batch_size=512,
        decoder=torchcrepe.decode.viterbi,
    )
    f0_hz = pitch.squeeze(0).cpu().numpy()
    conf = periodicity.squeeze(0).cpu().numpy()
    f0_hz = torchcrepe.filter.median(torch.tensor(f0_hz).unsqueeze(0), 3).squeeze(0).numpy()
    hop_sec = CREPE_HOP / CREPE_SR
    cr_times = np.arange(len(f0_hz)) * hop_sec

    cr_voiced = (conf >= 0.4) & (f0_hz > 0)
    cr_midi = np.full_like(f0_hz, np.nan)
    cr_midi[cr_voiced] = 12.0 * np.log2(f0_hz[cr_voiced] / 440.0) + 69.0

    # pYIN
    pyin_f0, pyin_voiced_flag, _ = librosa.pyin(
        vocals_harm, fmin=librosa.midi_to_hz(55), fmax=librosa.midi_to_hz(95),
        sr=sr, frame_length=2048,
    )
    py_times = librosa.times_like(pyin_f0, sr=sr, hop_length=512)
    py_midi = np.full_like(pyin_f0, np.nan)
    py_v = pyin_voiced_flag & (~np.isnan(pyin_f0)) & (pyin_f0 > 0)
    py_midi[py_v] = 12.0 * np.log2(pyin_f0[py_v] / 440.0) + 69.0

    # Baseline
    bp_al = apply_sectional_time_offset(bp_shifted, ref_notes)
    bp_m = compare_melodies(ref_notes, bp_al)
    print(f"\nBP baseline: pc_f1={bp_m['pitch_class_f1']:.3f}, mel_len={bp_m['melody_f1_lenient']:.3f}")

    # Strategies to test
    strategies = [
        ("CREPE median", lambda x: int(round(float(np.median(x))))),
        ("CREPE mode", lambda x: Counter(np.round(x).astype(int)).most_common(1)[0][0]),
        ("CREPE Q60", lambda x: int(round(float(np.percentile(x, 60))))),
        ("CREPE Q75", lambda x: int(round(float(np.percentile(x, 75))))),
        ("CREPE Q40", lambda x: int(round(float(np.percentile(x, 40))))),
        ("CREPE mean", lambda x: int(round(float(np.mean(x))))),
    ]

    print(f"\n{'Strategy':<25} | {'Δ notes':<8} | {'pc_f1':<8} | {'Δ pc_f1':<8} | {'mel_len':<8} | {'Δ mel':<8}")
    print("-" * 80)

    for name, agg_fn in strategies:
        for max_d in [2, 3]:
            notes, n_changed = build_notes_with_strategy(
                bp_shifted, cr_midi, cr_voiced, cr_times, agg_fn, max_delta=max_d
            )
            aligned = apply_sectional_time_offset(notes, ref_notes)
            m = compare_melodies(ref_notes, aligned)
            d_pc = m['pitch_class_f1'] - bp_m['pitch_class_f1']
            d_mel = m['melody_f1_lenient'] - bp_m['melody_f1_lenient']
            label = f"{name} (±{max_d})"
            print(f"  {label:<25} | {n_changed:<8} | {m['pitch_class_f1']:<8.3f} | {d_pc:+8.3f} | {m['melody_f1_lenient']:<8.3f} | {d_mel:+8.3f}")

    print(f"\n--- pYIN strategies ---")
    pyin_strategies = [
        ("pYIN median", lambda x: int(round(float(np.median(x))))),
        ("pYIN mode", lambda x: Counter(np.round(x).astype(int)).most_common(1)[0][0]),
        ("pYIN Q75", lambda x: int(round(float(np.percentile(x, 75))))),
    ]

    for name, agg_fn in pyin_strategies:
        for max_d in [2, 3]:
            notes, n_changed = build_notes_with_strategy(
                bp_shifted, py_midi, py_v, py_times, agg_fn, max_delta=max_d
            )
            aligned = apply_sectional_time_offset(notes, ref_notes)
            m = compare_melodies(ref_notes, aligned)
            d_pc = m['pitch_class_f1'] - bp_m['pitch_class_f1']
            d_mel = m['melody_f1_lenient'] - bp_m['melody_f1_lenient']
            label = f"{name} (±{max_d})"
            print(f"  {label:<25} | {n_changed:<8} | {m['pitch_class_f1']:<8.3f} | {d_pc:+8.3f} | {m['melody_f1_lenient']:<8.3f} | {d_mel:+8.3f}")

    # Also test: CREPE for ALL pitches (not just corrections)
    print(f"\n--- Full CREPE pitch replacement ---")
    for name, agg_fn in [
        ("CREPE median (full)", lambda x: int(round(float(np.median(x))))),
        ("CREPE Q75 (full)", lambda x: int(round(float(np.percentile(x, 75))))),
    ]:
        result = []
        for n in bp_shifted:
            mask = (cr_times >= n.onset) & (cr_times < n.onset + n.duration) & cr_voiced
            frames = cr_midi[mask]
            if len(frames) >= 3:
                snapped = snap_to_bp_octave(frames, n.pitch)
                p = agg_fn(snapped)
                result.append(Note(pitch=p, onset=n.onset, duration=n.duration, velocity=n.velocity))
            else:
                result.append(n)

        aligned = apply_sectional_time_offset(result, ref_notes)
        m = compare_melodies(ref_notes, aligned)
        d_pc = m['pitch_class_f1'] - bp_m['pitch_class_f1']
        d_mel = m['melody_f1_lenient'] - bp_m['melody_f1_lenient']
        n_diff = sum(1 for a, b in zip(result, bp_shifted) if a.pitch != b.pitch)
        print(f"  {name:<25} | {n_diff:<8} | {m['pitch_class_f1']:<8.3f} | {d_pc:+8.3f} | {m['melody_f1_lenient']:<8.3f} | {d_mel:+8.3f}")

    # Test: pYIN full replacement
    for name, agg_fn in [
        ("pYIN median (full)", lambda x: int(round(float(np.median(x))))),
        ("pYIN Q75 (full)", lambda x: int(round(float(np.percentile(x, 75))))),
    ]:
        result = []
        for n in bp_shifted:
            mask = (py_times >= n.onset) & (py_times < n.onset + n.duration) & py_v
            frames = py_midi[mask]
            if len(frames) >= 3:
                snapped = snap_to_bp_octave(frames, n.pitch)
                p = agg_fn(snapped)
                result.append(Note(pitch=p, onset=n.onset, duration=n.duration, velocity=n.velocity))
            else:
                result.append(n)

        aligned = apply_sectional_time_offset(result, ref_notes)
        m = compare_melodies(ref_notes, aligned)
        d_pc = m['pitch_class_f1'] - bp_m['pitch_class_f1']
        d_mel = m['melody_f1_lenient'] - bp_m['melody_f1_lenient']
        n_diff = sum(1 for a, b in zip(result, bp_shifted) if a.pitch != b.pitch)
        print(f"  {name:<25} | {n_diff:<8} | {m['pitch_class_f1']:<8.3f} | {d_pc:+8.3f} | {m['melody_f1_lenient']:<8.3f} | {d_mel:+8.3f}")


if __name__ == "__main__":
    main()
