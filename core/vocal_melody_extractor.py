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

import basic_pitch
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


def _bp_extract_viterbi_melody(wav_path: str) -> list[Note]:
    """Run Basic Pitch and extract monophonic melody via Viterbi DP.

    Keeps all BP note candidates, groups them into 50ms time slots, then
    uses DP to find the globally smoothest melody path (minimising pitch
    jumps, maximising note velocity).
    """
    _model_path = basic_pitch.build_icassp_2022_model_path(basic_pitch.FilenameSuffix.onnx)
    _, midi_data, _ = predict(
        wav_path,
        _model_path,
        onset_threshold=_BP_ONSET_THRESHOLD,
        frame_threshold=_BP_FRAME_THRESHOLD,
        minimum_note_length=_BP_MIN_NOTE_LENGTH_MS,
    )

    if not midi_data.instruments or not midi_data.instruments[0].notes:
        logger.warning("Basic Pitch: no notes detected")
        return []

    all_notes = midi_data.instruments[0].notes
    candidates = sorted(
        [n for n in all_notes if n.end - n.start >= 0.04 and 40 <= n.pitch <= 100],
        key=lambda n: n.start,
    )

    if not candidates:
        return []

    # Group notes into 50ms time slots
    slots: list[list] = []
    current: list = [candidates[0]]
    for n in candidates[1:]:
        if abs(n.start - current[0].start) < 0.05:
            current.append(n)
        else:
            slots.append(current)
            current = [n]
    slots.append(current)

    # Viterbi DP: score[j] = best cumulative score ending at note j
    prev_scores = [float(n.velocity) for n in slots[0]]
    prev_notes = list(slots[0])
    back: list[list[int]] = [[0] * len(s) for s in slots]

    for i in range(1, len(slots)):
        curr_slot = slots[i]
        curr_scores: list[float] = []
        for j, curr in enumerate(curr_slot):
            best_score = float("-inf")
            best_k = 0
            for k, (prev_note, ps) in enumerate(zip(prev_notes, prev_scores)):
                score = ps + curr.velocity - abs(curr.pitch - prev_note.pitch) * 2.0
                if score > best_score:
                    best_score = score
                    best_k = k
            curr_scores.append(best_score)
            back[i][j] = best_k
        prev_scores = curr_scores
        prev_notes = curr_slot

    # Backtrack from best final state
    path: list[int] = [int(np.argmax(prev_scores))]
    for i in range(len(slots) - 1, 0, -1):
        path.append(back[i][path[-1]])
    path.reverse()

    notes = [
        Note(
            pitch=slots[i][j].pitch,
            onset=slots[i][j].start,
            duration=slots[i][j].end - slots[i][j].start,
            velocity=slots[i][j].velocity,
        )
        for i, j in enumerate(path)
        if 40 <= slots[i][j].pitch <= 100
    ]
    logger.info(
        "BP Viterbi melody: %d total -> %d slots -> %d notes",
        len(all_notes), len(slots), len(notes),
    )
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


# ── Krumhansl-Schmuckler key profiles ───────────────────────────────────────
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_SCALE_INTERVALS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _detect_key(vocals: np.ndarray, sr: int) -> tuple[int, str]:
    """Detect musical key using Krumhansl-Schmuckler chroma correlation.

    Returns:
        (root_pitch_class, mode) where root is 0-11 (C=0) and mode is 'major'/'minor'.
    """
    chroma = librosa.feature.chroma_cqt(y=vocals, sr=sr)
    chroma_sum = np.sum(chroma, axis=1)

    best_corr = -np.inf
    best_root, best_mode = 0, "major"

    for root in range(12):
        for profile, mode in [(_KS_MAJOR, "major"), (_KS_MINOR, "minor")]:
            rotated = np.roll(profile, root)
            corr = float(np.corrcoef(chroma_sum, rotated)[0, 1])
            if corr > best_corr:
                best_corr = corr
                best_root, best_mode = root, mode

    logger.info(
        "Key detection: %s %s (corr=%.3f)",
        _NOTE_NAMES[best_root], best_mode, best_corr,
    )
    return best_root, best_mode


def _diatonic_snap(notes: list[Note], root: int, mode: str) -> list[Note]:
    """Snap each note to the nearest diatonic pitch in the detected key.

    Notes already on a scale degree are unchanged. Off-scale notes (typically
    from BP flat bias) are moved to the nearest diatonic semitone.
    """
    scale_pcs = set((root + i) % 12 for i in _SCALE_INTERVALS[mode])
    snapped = []
    n_changed = 0

    for n in notes:
        pc = n.pitch % 12
        if pc in scale_pcs:
            snapped.append(n)
            continue

        # Find smallest semitone delta that lands on a scale note
        best_delta = 12  # sentinel
        for s_pc in scale_pcs:
            for delta in [(s_pc - pc) % 12, -((pc - s_pc) % 12)]:
                if abs(delta) < abs(best_delta):
                    best_delta = delta

        new_pitch = n.pitch + best_delta
        snapped.append(Note(pitch=new_pitch, onset=n.onset, duration=n.duration))
        n_changed += 1

    logger.info(
        "Diatonic snap (%s %s): %d/%d notes adjusted",
        _NOTE_NAMES[root], mode, n_changed, len(notes),
    )
    return snapped


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


def _harmonic_only_bp(vocals_f32: np.ndarray, sr: int) -> list[Note]:
    """Run BP only on harmonic-enhanced vocals (skip raw-harmonic intersection)."""
    vocals_harm = librosa.effects.harmonic(vocals_f32, margin=8.0).astype(np.float32)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        harm_wav = tmp.name
    sf.write(harm_wav, vocals_harm, sr)
    try:
        notes = _bp_extract_viterbi_melody(harm_wav)
        logger.info("Harmonic-only BP: %d notes", len(notes))
        return notes
    finally:
        Path(harm_wav).unlink(missing_ok=True)


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
        raw_notes = _bp_extract_viterbi_melody(raw_wav)
        harm_notes = _bp_extract_viterbi_melody(harm_wav)

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


# ── High-resolution CQT pitch correction ─────────────────────────────────────
_HIRES_BINS_PER_OCTAVE = 36          # 1 bin = 1/3 semitone
_HIRES_N_BINS = 7 * 36               # C1–B7
_HIRES_SEARCH_SEMITONES = 3          # search window ±3 semitones around BP pitch


def _highres_cqt_pitch_correction(
    notes: list[Note],
    vocals: np.ndarray,
    sr: int,
) -> list[Note]:
    """Correct per-note pitch via high-resolution CQT + parabolic interpolation.

    Computes a 36-bin/octave CQT on the harmonic-enhanced signal, then for each
    note searches a ±3-semitone window around the BP pitch. A parabolic fit gives
    sub-bin precision. Only upward corrections of +1 or +2 semitones are applied
    (targeting the known BP flat bias).
    """
    search_bins = _HIRES_SEARCH_SEMITONES * _HIRES_BINS_PER_OCTAVE // 12  # 9 bins

    # Build harmonic-enhanced high-res CQT
    vocals_22k = librosa.resample(vocals, orig_sr=sr, target_sr=_SR)
    S = librosa.stft(vocals_22k, hop_length=_HOP_LENGTH)
    S_harm, _ = librosa.decompose.hpss(S, margin=4.0)
    y_harm = librosa.istft(S_harm, hop_length=_HOP_LENGTH)

    C = np.abs(librosa.cqt(
        y_harm, sr=_SR, hop_length=_HOP_LENGTH,
        n_bins=_HIRES_N_BINS, bins_per_octave=_HIRES_BINS_PER_OCTAVE, fmin=_FMIN,
    ))
    freqs_hires = librosa.cqt_frequencies(
        n_bins=_HIRES_N_BINS, fmin=_FMIN, bins_per_octave=_HIRES_BINS_PER_OCTAVE,
    )
    times_cqt = librosa.times_like(C, sr=_SR, hop_length=_HOP_LENGTH)
    midi_bins_hires = 12.0 * np.log2(freqs_hires / 440.0) + 69.0

    corrected: list[Note] = []
    n_changed = 0

    for n in notes:
        frame_lo = max(0, int(np.searchsorted(times_cqt, n.onset)) - 1)
        frame_hi = min(C.shape[1], int(np.searchsorted(times_cqt, n.onset + n.duration)) + 1)

        if frame_lo >= frame_hi:
            corrected.append(n)
            continue

        avg_cqt = np.mean(C[:, frame_lo:frame_hi], axis=1)

        # Bin index nearest to BP pitch
        bp_bin = int(np.argmin(np.abs(midi_bins_hires - n.pitch)))
        lo = max(0, bp_bin - search_bins)
        hi = min(len(avg_cqt), bp_bin + search_bins + 1)
        window = avg_cqt[lo:hi]

        if len(window) < 3:
            corrected.append(n)
            continue

        peak_local = int(np.argmax(window))
        peak_bin = lo + peak_local

        # Parabolic interpolation
        if 0 < peak_local < len(window) - 1:
            a = window[peak_local - 1]
            b = window[peak_local]
            c = window[peak_local + 1]
            delta = 0.5 * (a - c) / (a - 2 * b + c + 1e-10)
            precise_bin = peak_bin + delta
        else:
            precise_bin = float(peak_bin)

        precise_midi = float(np.interp(
            precise_bin, np.arange(len(midi_bins_hires)), midi_bins_hires,
        ))
        corrected_pitch = int(round(precise_midi))
        delta_pitch = corrected_pitch - n.pitch

        # Only apply upward corrections of +1 or +2 (flat bias fix)
        if 1 <= delta_pitch <= 2:
            corrected.append(Note(pitch=corrected_pitch, onset=n.onset, duration=n.duration))
            n_changed += 1
        else:
            corrected.append(n)

    logger.info(
        "High-res CQT correction: %d/%d notes adjusted (+1 or +2)",
        n_changed, len(notes),
    )
    return corrected


def _pyin_flat_bias_correction(
    notes: list[Note],
    vocals: np.ndarray,
    sr: int,
) -> list[Note]:
    """Correct BP flat bias using pyin per-note pitch re-estimation.

    For each note, extracts the audio segment and runs pyin to get a precise
    F0 estimate. If pyin says the note should be +1 or +2 semitones higher
    (matching the known BP flat bias pattern), applies the correction.
    """
    if not notes:
        return notes

    # Use harmonic-enhanced audio for cleaner pitch estimation
    vocals_harm = librosa.effects.harmonic(vocals, margin=8.0)

    corrected: list[Note] = []
    n_changed = 0

    for n in notes:
        # Extract audio segment for this note (with small margin)
        margin = 0.05  # 50ms margin on each side
        start_sample = max(0, int((n.onset - margin) * sr))
        end_sample = min(len(vocals_harm), int((n.onset + n.duration + margin) * sr))
        segment = vocals_harm[start_sample:end_sample]

        if len(segment) < sr * 0.05:  # too short
            corrected.append(n)
            continue

        # Run pyin on the segment
        f0, voiced_flag, _ = librosa.pyin(
            segment,
            fmin=librosa.midi_to_hz(max(40, n.pitch - 5)),
            fmax=librosa.midi_to_hz(min(100, n.pitch + 5)),
            sr=sr,
            frame_length=2048,
        )

        # Get median pitch from voiced frames
        voiced_f0 = f0[voiced_flag] if voiced_flag is not None else f0[~np.isnan(f0)]
        if len(voiced_f0) == 0:
            corrected.append(n)
            continue

        median_f0 = float(np.median(voiced_f0))
        pyin_midi = 12.0 * np.log2(median_f0 / 440.0) + 69.0
        pyin_pitch = int(round(pyin_midi))
        delta = pyin_pitch - n.pitch

        # Only apply upward corrections of +1 or +2 (flat bias fix)
        if 1 <= delta <= 2:
            corrected.append(Note(pitch=pyin_pitch, onset=n.onset, duration=n.duration, velocity=n.velocity))
            n_changed += 1
        else:
            corrected.append(n)

    logger.info(
        "pyin flat bias correction: %d/%d notes adjusted (+1 or +2)",
        n_changed, len(notes),
    )
    return corrected


_HIRES_ENERGY_RATIO = 1.3  # CQT peak must be ≥1.3× original to justify correction


def _hires_cqt_pitch_refinement(
    notes: list[Note],
    vocals: np.ndarray,
    sr: int,
) -> list[Note]:
    """Bidirectional per-note pitch refinement via high-res CQT.

    Like _highres_cqt_pitch_correction but allows corrections of -2 to +2
    semitones (not just upward), and only applies when the CQT energy at
    the corrected pitch is significantly stronger than at the original pitch.
    """
    search_bins = _HIRES_SEARCH_SEMITONES * _HIRES_BINS_PER_OCTAVE // 12  # 9 bins

    vocals_22k = librosa.resample(vocals, orig_sr=sr, target_sr=_SR)
    S = librosa.stft(vocals_22k, hop_length=_HOP_LENGTH)
    S_harm, _ = librosa.decompose.hpss(S, margin=4.0)
    y_harm = librosa.istft(S_harm, hop_length=_HOP_LENGTH)

    C = np.abs(librosa.cqt(
        y_harm, sr=_SR, hop_length=_HOP_LENGTH,
        n_bins=_HIRES_N_BINS, bins_per_octave=_HIRES_BINS_PER_OCTAVE, fmin=_FMIN,
    ))
    freqs_hires = librosa.cqt_frequencies(
        n_bins=_HIRES_N_BINS, fmin=_FMIN, bins_per_octave=_HIRES_BINS_PER_OCTAVE,
    )
    times_cqt = librosa.times_like(C, sr=_SR, hop_length=_HOP_LENGTH)
    midi_bins_hires = 12.0 * np.log2(freqs_hires / 440.0) + 69.0

    corrected: list[Note] = []
    n_changed = 0

    for n in notes:
        frame_lo = max(0, int(np.searchsorted(times_cqt, n.onset)) - 1)
        frame_hi = min(C.shape[1], int(np.searchsorted(times_cqt, n.onset + n.duration)) + 1)

        if frame_lo >= frame_hi:
            corrected.append(n)
            continue

        avg_cqt = np.mean(C[:, frame_lo:frame_hi], axis=1)

        # Energy at current BP pitch
        bp_bin = int(np.argmin(np.abs(midi_bins_hires - n.pitch)))
        bp_energy = float(avg_cqt[bp_bin])

        # Search window around BP pitch
        lo = max(0, bp_bin - search_bins)
        hi = min(len(avg_cqt), bp_bin + search_bins + 1)
        window = avg_cqt[lo:hi]

        if len(window) < 3:
            corrected.append(n)
            continue

        peak_local = int(np.argmax(window))
        peak_bin = lo + peak_local
        peak_energy = float(window[peak_local])

        # Parabolic interpolation for sub-bin precision
        if 0 < peak_local < len(window) - 1:
            a = window[peak_local - 1]
            b = window[peak_local]
            c = window[peak_local + 1]
            delta = 0.5 * (a - c) / (a - 2 * b + c + 1e-10)
            precise_bin = peak_bin + delta
        else:
            precise_bin = float(peak_bin)

        precise_midi = float(np.interp(
            precise_bin, np.arange(len(midi_bins_hires)), midi_bins_hires,
        ))
        corrected_pitch = int(round(precise_midi))
        delta_pitch = corrected_pitch - n.pitch

        # Apply correction if:
        # 1. Within ±2 semitones (and not 0)
        # 2. CQT peak energy is significantly stronger than at original pitch
        if (
            -2 <= delta_pitch <= 2
            and delta_pitch != 0
            and peak_energy >= bp_energy * _HIRES_ENERGY_RATIO
        ):
            corrected.append(Note(pitch=corrected_pitch, onset=n.onset, duration=n.duration))
            n_changed += 1
        else:
            corrected.append(n)

    logger.info(
        "High-res CQT refinement (±2): %d/%d notes adjusted",
        n_changed, len(notes),
    )
    return corrected


# ── CREPE F0 tracking ─────────────────────────────────────────────────────────
def _crepe_pitch_correction(
    notes: list[Note],
    vocals: np.ndarray,
    sr: int,
) -> list[Note]:
    """Correct BP pitch using CREPE monophonic F0 estimation.

    Runs CREPE once on the full vocal audio, then for each BP note checks
    the CREPE median pitch in the note's time window. If CREPE suggests
    a pitch +1 or +2 semitones higher with good confidence, applies the
    correction (targeting the known BP flat bias).
    """
    if not notes:
        return notes

    # Run CREPE on harmonic-enhanced vocals for cleaner pitch tracking
    vocals_harm = librosa.effects.harmonic(vocals, margin=8.0)
    f0_hz, conf, times = _crepe_f0_extract(vocals_harm, sr)

    # Convert F0 to MIDI
    f0_midi = np.full_like(f0_hz, np.nan)
    voiced = (conf >= _CREPE_CONF_THRESH) & (f0_hz > 0)
    f0_midi[voiced] = 12.0 * np.log2(f0_hz[voiced] / 440.0) + 69.0

    corrected: list[Note] = []
    n_changed = 0

    for n in notes:
        # Find CREPE frames within this note's time window
        mask = (times >= n.onset) & (times < n.onset + n.duration) & voiced
        if np.sum(mask) < 3:  # too few voiced frames
            corrected.append(n)
            continue

        crepe_pitches = f0_midi[mask]
        crepe_median = float(np.median(crepe_pitches))
        crepe_pitch = int(round(crepe_median))
        delta = crepe_pitch - n.pitch

        # Only apply upward corrections of +1 or +2 (flat bias fix)
        if 1 <= delta <= 2:
            corrected.append(Note(
                pitch=crepe_pitch, onset=n.onset,
                duration=n.duration, velocity=n.velocity,
            ))
            n_changed += 1
        else:
            corrected.append(n)

    logger.info(
        "CREPE pitch correction: %d/%d notes adjusted (+1 or +2)",
        n_changed, len(notes),
    )
    return corrected


_CREPE_SR = 16000
_CREPE_HOP = 160          # 10 ms per frame at 16 kHz
_CREPE_CONF_THRESH = 0.5  # voiced/unvoiced confidence threshold
_CREPE_MIN_NOTE_MS = 80   # minimum note duration to keep (ms)
_CREPE_JUMP_SEMITONES = 1.5  # pitch jump > this semitones → note boundary
_CREPE_WINDOW_SEC = 15.0  # per-window CQT octave correction window size


def _crepe_f0_extract(
    vocals_f32: np.ndarray,
    sr: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract F0 using CREPE with Viterbi decoder.

    Returns:
        (f0_hz, periodicity, times) — frame-level arrays of length T.
    """
    import torch
    import torchcrepe

    y_16k = librosa.resample(vocals_f32, orig_sr=sr, target_sr=_CREPE_SR)
    audio = torch.from_numpy(y_16k).unsqueeze(0)  # (1, T)

    pitch, periodicity = torchcrepe.predict(
        audio,
        _CREPE_SR,
        hop_length=_CREPE_HOP,
        fmin=55.0,    # A1 — below any singing voice
        fmax=1760.0,  # A6 — above any singing voice
        model="full",
        batch_size=512,
        device="cpu",
        return_periodicity=True,
        decoder=torchcrepe.decode.viterbi,
    )

    f0_hz = pitch.squeeze(0).cpu().numpy()
    conf = periodicity.squeeze(0).cpu().numpy()
    times = np.arange(len(f0_hz)) * (_CREPE_HOP / _CREPE_SR)

    voiced_count = int(np.sum(conf >= _CREPE_CONF_THRESH))
    logger.info(
        "CREPE F0: %d frames, %d voiced (%.0f%%)",
        len(f0_hz), voiced_count, 100.0 * voiced_count / max(len(f0_hz), 1),
    )
    return f0_hz, conf, times


def _f0_to_notes(
    f0_hz: np.ndarray,
    conf: np.ndarray,
    times: np.ndarray,
    conf_thresh: float = _CREPE_CONF_THRESH,
    min_note_ms: float = _CREPE_MIN_NOTE_MS,
    jump_semitones: float = _CREPE_JUMP_SEMITONES,
) -> list[Note]:
    """Convert frame-level F0 to Note objects (F0-tracker agnostic).

    Splits on silence or pitch jumps > jump_semitones from the
    running segment median. Notes shorter than min_note_ms are discarded.
    """
    hop_sec = float(times[1] - times[0]) if len(times) > 1 else 0.01
    min_dur = min_note_ms / 1000.0

    voiced = (conf >= conf_thresh) & (f0_hz > 30.0)
    midi_raw = np.where(
        voiced,
        12.0 * np.log2(np.maximum(f0_hz, 1e-6) / 440.0) + 69.0,
        np.nan,
    )

    notes: list[Note] = []
    i = 0
    n = len(midi_raw)

    while i < n:
        if np.isnan(midi_raw[i]):
            i += 1
            continue

        start_idx = i
        segment: list[float] = [float(midi_raw[i])]
        i += 1

        while i < n and not np.isnan(midi_raw[i]):
            seg_med = float(np.median(segment))
            if abs(float(midi_raw[i]) - seg_med) > jump_semitones:
                break
            segment.append(float(midi_raw[i]))
            i += 1

        dur = (i - start_idx) * hop_sec
        if dur >= min_dur and segment:
            pitch_val = int(round(float(np.median(segment))))
            if 36 <= pitch_val <= 108:
                notes.append(Note(
                    pitch=pitch_val,
                    onset=float(times[start_idx]),
                    duration=dur,
                ))

    logger.info(
        "F0->notes: %d voiced frames -> %d notes",
        int(np.sum(voiced)), len(notes),
    )
    return notes


def _windowed_cqt_octave_correction(
    notes: list[Note],
    sal_w: np.ndarray,
    midi_bins: np.ndarray,
    times_cqt: np.ndarray,
) -> list[Note]:
    """Apply per-window CQT octave correction.

    Divides the song into _CREPE_WINDOW_SEC-sized windows and computes an
    independent octave shift per window, allowing local octave errors to be
    corrected independently (unlike one global shift).
    """
    if not notes:
        return notes

    range_mask = (midi_bins >= _VOCAL_MIDI_LOW) & (midi_bins <= _VOCAL_MIDI_HIGH)
    vocal_bin_idx = np.where(range_mask)[0]

    song_end = max(n.onset + n.duration for n in notes)
    corrected: list[Note] = []
    t = 0.0

    while t < song_end:
        t_end = min(t + _CREPE_WINDOW_SEC, song_end + 0.001)
        win_notes = [n for n in notes if t <= n.onset < t_end]

        if not win_notes:
            t = t_end
            continue

        # CQT-based pitch estimate for each note in this window
        cqt_pitches: list[int] = []
        for note in win_notes:
            center = note.onset + note.duration / 2
            frame = int(np.searchsorted(times_cqt, center))
            lo = max(0, frame - 2)
            hi = min(sal_w.shape[1], frame + 3)
            if lo >= hi:
                continue
            avg = np.mean(sal_w[:, lo:hi], axis=1)
            vs = avg[vocal_bin_idx]
            if vs.max() > 0:
                best_bin = int(vocal_bin_idx[np.argmax(vs)])
                cqt_pitches.append(int(round(float(midi_bins[best_bin]))))

        if not cqt_pitches:
            corrected.extend(win_notes)
            t = t_end
            continue

        cqt_med = float(np.median(cqt_pitches))
        note_med = float(np.median([n.pitch for n in win_notes]))
        shift = round((cqt_med - note_med) / 12) * 12

        logger.info(
            "Window [%.0f-%.0fs]: note_med=%.1f, cqt_med=%.1f, shift=%+d",
            t, t_end, note_med, cqt_med, shift,
        )

        for note in win_notes:
            new_pitch = note.pitch + shift
            if _VOCAL_MIDI_LOW - 3 <= new_pitch <= _VOCAL_MIDI_HIGH + 5:
                corrected.append(Note(
                    pitch=new_pitch, onset=note.onset, duration=note.duration,
                ))
            else:
                corrected.append(note)

        t = t_end

    return sorted(corrected, key=lambda n: n.onset)


def _crepe_pipeline(vocals_f32: np.ndarray, sr: int) -> list[Note]:
    """Extract monophonic melody via CREPE F0 + windowed CQT octave correction.

    1. CREPE Viterbi F0 track (monophonic — avoids sub-harmonic lock)
    2. F0 segmentation into Note objects
    3. Per-window CQT octave correction (_CREPE_WINDOW_SEC-sized windows)
    """
    f0_hz, conf, times = _crepe_f0_extract(vocals_f32, sr)

    notes = _f0_to_notes(f0_hz, conf, times)
    if not notes:
        logger.warning("CREPE pipeline: no notes from F0 track")
        return []

    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)
    notes = _windowed_cqt_octave_correction(notes, sal_w, midi_bins, times_cqt)

    logger.info("CREPE pipeline: %d final notes", len(notes))
    return notes


def _salience_melody_extract(vocals_f32: np.ndarray, sr: int) -> list[Note]:
    """Extract melody directly from CQT harmonic salience (MELODIA-style).

    Bypasses F0 trackers entirely. Uses the existing CQT salience (with
    harmonic weighting, sub-harmonic suppression, and vocal range bias)
    to find pitch peaks frame-by-frame, then groups into notes.

    No octave correction needed — salience is already in the correct range.
    """
    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)

    range_mask = (midi_bins >= _VOCAL_MIDI_LOW) & (midi_bins <= _VOCAL_MIDI_HIGH)
    vocal_bins = np.where(range_mask)[0]

    if len(vocal_bins) == 0 or sal_w.shape[1] == 0:
        return []

    vocal_sal = sal_w[vocal_bins, :]  # (n_vocal_bins, n_frames)

    # Voiced detection: peak salience must exceed adaptive threshold
    peak_vals = np.max(vocal_sal, axis=0)
    nonzero = peak_vals[peak_vals > 0]
    if len(nonzero) == 0:
        return []
    threshold = float(np.percentile(nonzero, 20))
    voiced = peak_vals > threshold

    # Peak MIDI pitch per frame
    peak_idx = np.argmax(vocal_sal, axis=0)
    f0_midi = np.where(voiced, midi_bins[vocal_bins[peak_idx]], 0.0)

    # Convert to Hz for _f0_to_notes
    f0_hz = np.where(
        f0_midi > 0,
        440.0 * 2.0 ** ((f0_midi - 69.0) / 12.0),
        0.0,
    )
    conf = np.where(voiced, peak_vals / (np.max(peak_vals) + 1e-8), 0.0)

    notes = _f0_to_notes(
        f0_hz, conf, times_cqt,
        conf_thresh=0.05, min_note_ms=100, jump_semitones=1.5,
    )

    logger.info("Salience melody: %d notes from CQT salience", len(notes))
    return notes


def _pyin_f0_extract(
    vocals_f32: np.ndarray,
    sr: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract F0 using librosa PYIN (probabilistic YIN).

    Returns:
        (f0_hz, conf, times) — same format as _crepe_f0_extract.
        Unvoiced frames have f0_hz=0 and conf=0.
    """
    hop_length = 512
    f0, voiced_flag, voiced_probs = librosa.pyin(
        vocals_f32,
        fmin=55.0,    # A1
        fmax=1760.0,  # A6
        sr=sr,
        frame_length=2048,
        hop_length=hop_length,
    )

    f0_hz = np.where(np.isnan(f0), 0.0, f0)
    conf = np.where(voiced_flag, voiced_probs, 0.0)
    times = librosa.times_like(f0, sr=sr, hop_length=hop_length)

    voiced_count = int(np.sum(voiced_flag))
    logger.info(
        "PYIN F0: %d frames, %d voiced (%.0f%%)",
        len(f0_hz), voiced_count, 100.0 * voiced_count / max(len(f0_hz), 1),
    )
    return f0_hz, conf, times


def _pyin_pipeline(vocals_f32: np.ndarray, sr: int) -> list[Note]:
    """Extract monophonic melody via PYIN F0 + windowed CQT octave correction.

    1. PYIN F0 track (fast, no GPU needed)
    2. F0 segmentation into Note objects
    3. Per-window CQT octave correction (_CREPE_WINDOW_SEC-sized windows)
    """
    f0_hz, conf, times = _pyin_f0_extract(vocals_f32, sr)

    notes = _f0_to_notes(f0_hz, conf, times)
    if not notes:
        logger.warning("PYIN pipeline: no notes from F0 track")
        return []

    sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)
    notes = _windowed_cqt_octave_correction(notes, sal_w, midi_bins, times_cqt)

    logger.info("PYIN pipeline: %d final notes", len(notes))
    return notes


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
            velocity=n.velocity,
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
