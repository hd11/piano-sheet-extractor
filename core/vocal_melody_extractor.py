"""Integrated vocal melody extraction pipeline.

Chains vocal separation, Basic Pitch note detection, and CQT-based octave
correction into a single end-to-end function that extracts melody from MP3.

Pipeline:
    separate_vocals() -> Basic Pitch -> weighted melody -> CQT octave shift
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional

import librosa
import numpy as np
import soundfile as sf
from basic_pitch.inference import predict

from core.types import Note
from core.vocal_separator import separate_vocals

logger = logging.getLogger(__name__)

_DEFAULT_BPM = 120.0

# ── Basic Pitch defaults ────────────────────────────────────────────────────
_BP_ONSET_THRESHOLD = 0.5
_BP_FRAME_THRESHOLD = 0.3
_BP_MIN_NOTE_LENGTH_MS = 127  # milliseconds

# ── CQT parameters (shared with melody_extractor.py) ────────────────────────
_SR = 22050
_HOP_LENGTH = 512
_N_BINS = 84
_BINS_PER_OCTAVE = 12
_FMIN = float(librosa.note_to_hz("C1"))

# ── Harmonic salience ───────────────────────────────────────────────────────
_HARMONICS = [1, 2, 3, 4]
_WEIGHTS = [1.0, 0.4, 0.25, 0.15]
_SUBHARMONIC_SUPPRESSION = 1.2
_SUBHARMONIC_OCTAVES = (1, 2)

# ── Vocal range ─────────────────────────────────────────────────────────────
_VOCAL_MIDI_LOW = 62   # D4
_VOCAL_MIDI_HIGH = 86  # D6


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


def _compute_cqt_salience(vocals: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute weighted CQT salience map from vocal audio.

    Returns:
        (salience_weighted, midi_bins, times_cqt)
    """
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
    bp_notes: list[Note],
    sal_w: np.ndarray,
    midi_bins: np.ndarray,
    times_cqt: np.ndarray,
) -> int:
    """Determine global octave shift using CQT salience.

    Compares BP median pitch to CQT-detected median pitch in vocal range
    and returns the nearest multiple of 12 semitones.
    """
    range_mask = (midi_bins >= _VOCAL_MIDI_LOW) & (midi_bins <= _VOCAL_MIDI_HIGH)
    vocal_bins = np.where(range_mask)[0]

    if len(vocal_bins) == 0 or not bp_notes:
        return 12  # safe default for vocal audio

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
        "Octave shift: CQT median=%.1f, BP median=%.1f, shift=%d",
        cqt_med, bp_med, shift,
    )
    return shift


def _bp_extract_weighted_melody(wav_path: str) -> list[Note]:
    """Run Basic Pitch and extract a monophonic melody via weighted selection.

    For simultaneous notes, keeps the one with best velocity + pitch
    continuity score.
    """
    _, midi_data, _ = predict(
        wav_path,
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
        Note(pitch=n.pitch, onset=n.start, duration=n.end - n.start)
        for n in melody if 40 <= n.pitch <= 100
    ]
    logger.info("BP weighted melody: %d total -> %d melody notes", len(all_notes), len(notes))
    return notes


def detect_bpm(audio: np.ndarray, sr: int) -> float:
    """Detect BPM from an audio signal using librosa.

    Args:
        audio: Mono audio waveform (float32).
        sr: Sample rate.

    Returns:
        Detected BPM as float. Falls back to 120.0 on failure.
    """
    try:
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])
        if bpm <= 0:
            logger.warning("detect_bpm: invalid tempo %.1f, falling back to %.1f", bpm, _DEFAULT_BPM)
            return _DEFAULT_BPM
        logger.info("detect_bpm: detected %.1f BPM", bpm)
        return bpm
    except Exception as e:
        logger.warning("detect_bpm: failed (%s), falling back to %.1f", e, _DEFAULT_BPM)
        return _DEFAULT_BPM


def _intersect_melodies(raw_notes: list[Note], harm_notes: list[Note]) -> list[Note]:
    """Intersect raw and harmonic BP runs: keep notes found in both.

    Two notes match if onsets are within 150ms and pitch class is the same.
    Returns notes from the raw run that have a match in the harmonic run.
    """
    result = []
    for rn in raw_notes:
        for hn in harm_notes:
            if abs(rn.onset - hn.onset) < 0.15 and rn.pitch % 12 == hn.pitch % 12:
                result.append(rn)
                break
    return result


def _run_bp_pipeline(vocals_f32: np.ndarray, sr: int) -> list[Note]:
    """Run BP on raw + harmonic vocals, return intersection.

    Falls back to raw-only if harmonic extraction fails or produces no notes.
    """
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


def extract_melody(
    mp3_path: Path,
    cache_dir: Optional[Path] = None,
    periodicity_threshold: Optional[float] = None,
    min_note_dur: Optional[float] = None,
    model: str = "full",
) -> list[Note]:
    """End-to-end melody extraction from an MP3 file.

    Pipeline:
        separate_vocals -> BP (raw + harmonic intersection) -> CQT octave shift

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for cached .npz files. Defaults to None (no caching).
        periodicity_threshold: Unused (kept for backward compatibility).
        min_note_dur: Unused (kept for backward compatibility).
        model: Unused (kept for backward compatibility).

    Returns:
        List of Note objects representing the extracted melody.
        Returns empty list if no voiced frames are detected.
    """
    logger.info("extract_melody: starting BP+CQT pipeline for %s", mp3_path)

    # Step 1: Separate vocals from the MP3
    vocals, sr = separate_vocals(mp3_path, cache_dir)

    if vocals is None or len(vocals) == 0:
        logger.warning("extract_melody: no vocals extracted")
        return []

    vocals_f32 = vocals.astype(np.float32)

    # Step 2: Run BP on raw + harmonic vocals, intersect
    bp_notes = _run_bp_pipeline(vocals_f32, sr)

    if not bp_notes:
        logger.warning("extract_melody: no BP notes extracted")
        return []

    # Step 3: CQT salience for octave determination
    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)

    # Step 4: Determine and apply octave shift
    shift = _determine_octave_shift(bp_notes, sal_w, midi_bins, times_cqt)

    notes = [
        Note(
            pitch=n.pitch + shift,
            onset=n.onset,
            duration=n.duration,
        )
        for n in bp_notes
        if _VOCAL_MIDI_LOW - 3 <= n.pitch + shift <= _VOCAL_MIDI_HIGH + 5
    ]

    logger.info(
        "extract_melody: pipeline complete, %d notes (shift=%+d)",
        len(notes), shift,
    )
    return notes


def extract_melody_with_bpm(
    mp3_path: Path,
    cache_dir: Optional[Path] = None,
    periodicity_threshold: Optional[float] = None,
    min_note_dur: Optional[float] = None,
    model: str = "full",
) -> tuple[list[Note], float]:
    """Extract melody and auto-detect BPM from an MP3 file.

    Same as extract_melody but also runs BPM detection on the separated vocals.

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for cached .npz files. Defaults to None (no caching).
        periodicity_threshold: Unused (kept for backward compatibility).
        min_note_dur: Unused (kept for backward compatibility).
        model: Unused (kept for backward compatibility).

    Returns:
        Tuple of (notes, bpm).
    """
    logger.info("extract_melody_with_bpm: starting pipeline for %s", mp3_path)

    # Step 1: Separate vocals
    vocals, sr = separate_vocals(mp3_path, cache_dir)

    if vocals is None or len(vocals) == 0:
        logger.warning("extract_melody_with_bpm: no vocals extracted")
        return [], _DEFAULT_BPM

    vocals_f32 = vocals.astype(np.float32)

    # Step 2: Detect BPM from vocals
    bpm = detect_bpm(vocals_f32, sr)

    # Step 3: BP on raw + harmonic vocals, intersect
    bp_notes = _run_bp_pipeline(vocals_f32, sr)

    if not bp_notes:
        logger.warning("extract_melody_with_bpm: no BP notes extracted")
        return [], bpm

    # Step 4: CQT octave correction
    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)
    shift = _determine_octave_shift(bp_notes, sal_w, midi_bins, times_cqt)

    notes = [
        Note(
            pitch=n.pitch + shift,
            onset=n.onset,
            duration=n.duration,
        )
        for n in bp_notes
        if _VOCAL_MIDI_LOW - 3 <= n.pitch + shift <= _VOCAL_MIDI_HIGH + 5
    ]

    logger.info(
        "extract_melody_with_bpm: pipeline complete, %d notes, %.1f BPM (shift=%+d)",
        len(notes), bpm, shift,
    )
    return notes, bpm
