"""Basic Pitch + CQT octave correction melody extractor.

Replaces CREPE F0 + note_segmenter with Basic Pitch end-to-end note detection.
BP handles both pitch detection and note segmentation in one step,
avoiding the CREPE subharmonic + custom segmentation bottleneck.

Pipeline: vocals (WAV) -> Basic Pitch (raw ∩ harmonic) -> CQT octave shift -> notes
"""

import logging
import tempfile
from pathlib import Path
from typing import List

import librosa
import numpy as np
import soundfile as sf
from basic_pitch.inference import predict

# Use ONNX model directly (TF saved model has compatibility issues)
import basic_pitch
_BP_MODEL_PATH = str(Path(basic_pitch.__file__).parent / "saved_models" / "icassp_2022" / "nmp.onnx")

from .types import Note

logger = logging.getLogger(__name__)

# Basic Pitch parameters
_BP_ONSET_THRESHOLD = 0.5
_BP_FRAME_THRESHOLD = 0.3
_BP_MIN_NOTE_LENGTH_MS = 127

# CQT parameters
_SR = 22050
_HOP_LENGTH = 512
_N_BINS = 84
_BINS_PER_OCTAVE = 12
_FMIN = float(librosa.note_to_hz("C1"))

# Harmonic salience
_HARMONICS = [1, 2, 3, 4]
_WEIGHTS = [1.0, 0.4, 0.25, 0.15]
_SUBHARMONIC_SUPPRESSION = 1.2
_SUBHARMONIC_OCTAVES = (1, 2)

# Vocal range
_VOCAL_MIDI_LOW = 62   # D4
_VOCAL_MIDI_HIGH = 86  # D6


def extract_notes_bp(
    vocals: np.ndarray,
    sr: int,
) -> List[Note]:
    """Extract melody notes from vocal audio using Basic Pitch + CQT.

    Args:
        vocals: Separated vocal audio (mono, float32).
        sr: Sample rate of vocals.

    Returns:
        List of Note objects representing the extracted melody.
    """
    vocals_f32 = vocals.astype(np.float32)

    # Step 1: Run BP on raw + harmonic vocals, intersect
    bp_notes = _run_bp_pipeline(vocals_f32, sr)

    if not bp_notes:
        logger.warning("BP: no notes extracted")
        return []

    # Step 2: CQT salience for octave determination
    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)

    # Step 3: Determine and apply octave shift
    shift = _determine_octave_shift(bp_notes, sal_w, midi_bins, times_cqt)

    notes = [
        Note(
            pitch=n.pitch + shift,
            onset=round(n.onset, 4),
            duration=round(n.duration, 4),
        )
        for n in bp_notes
        if _VOCAL_MIDI_LOW - 3 <= n.pitch + shift <= _VOCAL_MIDI_HIGH + 5
    ]

    logger.info(
        "BP+CQT: %d notes (shift=%+d, range MIDI %d-%d)",
        len(notes), shift,
        min(n.pitch for n in notes) if notes else 0,
        max(n.pitch for n in notes) if notes else 0,
    )
    return notes


def _run_bp_pipeline(vocals_f32: np.ndarray, sr: int) -> List[Note]:
    """Run BP on raw + harmonic vocals, return intersection."""
    # Write raw vocals to temp WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        raw_wav = tmp.name
    sf.write(raw_wav, vocals_f32, sr)

    # Write harmonic-enhanced vocals to temp WAV
    vocals_harm = librosa.effects.harmonic(vocals_f32, margin=8.0).astype(np.float32)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        harm_wav = tmp.name
    sf.write(harm_wav, vocals_harm, sr)

    try:
        raw_notes = _bp_extract_weighted_melody(raw_wav)
        harm_notes = _bp_extract_weighted_melody(harm_wav)

        if raw_notes and harm_notes:
            intersected = _intersect_melodies(raw_notes, harm_notes)
            if len(intersected) >= len(raw_notes) * 0.5:
                logger.info(
                    "BP intersection: raw=%d, harm=%d -> intersected=%d",
                    len(raw_notes), len(harm_notes), len(intersected),
                )
                return intersected
            logger.info(
                "BP intersection too small (%d/%d), using raw notes",
                len(intersected), len(raw_notes),
            )

        return raw_notes
    finally:
        Path(raw_wav).unlink(missing_ok=True)
        Path(harm_wav).unlink(missing_ok=True)


def _bp_extract_weighted_melody(wav_path: str) -> List[Note]:
    """Run Basic Pitch and extract monophonic melody via weighted selection."""
    _, midi_data, _ = predict(
        wav_path,
        _BP_MODEL_PATH,
        onset_threshold=_BP_ONSET_THRESHOLD,
        frame_threshold=_BP_FRAME_THRESHOLD,
        minimum_note_length=_BP_MIN_NOTE_LENGTH_MS,
    )

    if not midi_data.instruments or not midi_data.instruments[0].notes:
        logger.warning("Basic Pitch: no notes detected")
        return []

    all_notes = midi_data.instruments[0].notes
    bp_sorted = sorted(all_notes, key=lambda n: n.start)

    melody: list = []
    for n in bp_sorted:
        dur = n.end - n.start
        if dur < 0.04 or n.pitch < 40 or n.pitch > 100:
            continue
        if not melody:
            melody.append(n)
        else:
            prev = melody[-1]
            if abs(n.start - prev.start) < 0.05:
                # Simultaneous: keep the one with better continuity
                pp = melody[-2].pitch if len(melody) >= 2 else prev.pitch
                score_new = n.velocity - abs(n.pitch - pp) * 2
                score_old = prev.velocity - abs(prev.pitch - pp) * 2
                if score_new > score_old:
                    melody[-1] = n
            else:
                melody.append(n)

    notes = [
        Note(pitch=n.pitch, onset=round(n.start, 4), duration=round(n.end - n.start, 4))
        for n in melody if 40 <= n.pitch <= 100
    ]
    logger.info("BP weighted melody: %d total -> %d melody notes", len(all_notes), len(notes))
    return notes


def _intersect_melodies(raw_notes: List[Note], harm_notes: List[Note]) -> List[Note]:
    """Intersect raw and harmonic BP runs: keep notes found in both."""
    result = []
    for rn in raw_notes:
        for hn in harm_notes:
            if abs(rn.onset - hn.onset) < 0.15 and rn.pitch % 12 == hn.pitch % 12:
                result.append(rn)
                break
    return result


def _suppress_subharmonics(salience: np.ndarray) -> np.ndarray:
    """Suppress lower-octave bins when higher octave energy dominates."""
    n_bins = salience.shape[0]
    suppression = np.zeros_like(salience)
    for octave in _SUBHARMONIC_OCTAVES:
        shift = int(octave * _BINS_PER_OCTAVE)
        if shift <= 0 or shift >= n_bins:
            continue
        suppression[:-shift, :] = np.maximum(
            suppression[:-shift, :], salience[shift:, :]
        )
    ratio = suppression / (salience + 1e-8)
    attenuation = 1.0 / (1.0 + _SUBHARMONIC_SUPPRESSION * ratio)
    return salience * attenuation


def _compute_cqt_salience(vocals: np.ndarray, sr: int):
    """Compute weighted CQT salience map from vocal audio."""
    vocals_22k = librosa.resample(vocals, orig_sr=sr, target_sr=_SR)
    S = librosa.stft(vocals_22k, hop_length=_HOP_LENGTH)
    S_harm, _ = librosa.decompose.hpss(S, margin=1.5)
    y_harm = librosa.istft(S_harm, hop_length=_HOP_LENGTH)

    C = np.abs(librosa.cqt(
        y_harm, sr=_SR, hop_length=_HOP_LENGTH,
        n_bins=_N_BINS, bins_per_octave=_BINS_PER_OCTAVE, fmin=_FMIN,
    ))
    freqs = librosa.cqt_frequencies(n_bins=_N_BINS, fmin=_FMIN, bins_per_octave=_BINS_PER_OCTAVE)
    times = librosa.times_like(C, sr=_SR, hop_length=_HOP_LENGTH)
    midi_bins = 12.0 * np.log2(freqs / 440.0) + 69.0

    sal = librosa.salience(
        C, freqs=freqs, harmonics=_HARMONICS, weights=_WEIGHTS,
        filter_peaks=False, fill_value=0.0,
    )
    sal = np.nan_to_num(sal, nan=0.0)
    sal = _suppress_subharmonics(sal)

    # Vocal range weighting with height bias
    range_mask = (midi_bins >= _VOCAL_MIDI_LOW) & (midi_bins <= _VOCAL_MIDI_HIGH)
    rw = np.where(range_mask, 1.0, 0.05)
    for i, midi in enumerate(midi_bins):
        if range_mask[i]:
            rw[i] *= 0.4 + 1.2 * (midi - _VOCAL_MIDI_LOW) / (_VOCAL_MIDI_HIGH - _VOCAL_MIDI_LOW)
    sal_w = sal * rw[:, np.newaxis]

    return sal_w, midi_bins, times


def _determine_octave_shift(
    bp_notes: List[Note],
    sal_w: np.ndarray,
    midi_bins: np.ndarray,
    times_cqt: np.ndarray,
) -> int:
    """Determine global octave shift using CQT salience."""
    range_mask = (midi_bins >= _VOCAL_MIDI_LOW) & (midi_bins <= _VOCAL_MIDI_HIGH)
    vocal_bins = np.where(range_mask)[0]

    if len(vocal_bins) == 0 or not bp_notes:
        return 12

    cqt_pitches = []
    for n in bp_notes:
        t = n.onset + n.duration / 2
        frame = np.searchsorted(times_cqt, t)
        lo = max(0, frame - 2)
        hi = min(sal_w.shape[1], frame + 3)
        if lo >= hi:
            continue
        avg = np.mean(sal_w[:, lo:hi], axis=1)
        vs = avg[vocal_bins]
        if np.max(vs) > 0:
            best_idx = np.argmax(vs)
            cqt_pitches.append(int(round(midi_bins[vocal_bins[best_idx]])))

    if not cqt_pitches:
        return 12

    cqt_med = float(np.median(cqt_pitches))
    bp_med = float(np.median([n.pitch for n in bp_notes]))
    shift = round((cqt_med - bp_med) / 12) * 12

    logger.info(
        "CQT octave shift: CQT median=%.1f, BP median=%.1f, shift=%d",
        cqt_med, bp_med, shift,
    )
    return shift
