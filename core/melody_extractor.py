"""Melodia-style melody extraction pipeline.

Custom pipeline that bypasses vocal separation and F0 estimation:
  MP3 -> CQT -> Harmonic Salience -> Peak Detection -> Contour Formation -> Melody Selection

Parameters tuned for polyphonic pop music with prominent vocal melody:
- CQT: 7 octaves (C1-B7) at 12 bins/octave, hop=512 (~23ms)
- Salience: first 4 harmonics with stronger fundamental bias
- Peaks: prominence-based filtering per frame via scipy.signal.find_peaks
- Contours: greedy nearest-neighbor linking within one semitone
- Melody: contour scoring with vocal range prior (G3-G#5)
"""

import hashlib
import logging
import math
from pathlib import Path

import librosa
import numpy as np
from scipy.signal import find_peaks

from core.types import Note

logger = logging.getLogger(__name__)

# ── CQT parameters ──────────────────────────────────────────────────────────
SR = 22050  # Standard sample rate
HOP_LENGTH = 512  # ~23.2ms per frame
N_BINS = 84  # 7 octaves (C1-B7)
BINS_PER_OCTAVE = 12  # Chromatic resolution
FMIN = float(librosa.note_to_hz("C1"))  # ~32.7 Hz, lowest CQT bin

# ── Harmonic Salience parameters ─────────────────────────────────────────────
HARMONICS = [1, 2, 3, 4]  # Fundamental + 3 overtones
WEIGHTS = [1.0, 0.4, 0.25, 0.15]  # Stronger bias toward fundamentals

# ── Peak Detection parameters ────────────────────────────────────────────────
PEAK_PROMINENCE = 0.05  # Absolute floor for prominence
PEAK_RELATIVE_PROMINENCE = 0.2  # Relative to frame max (0-1)
PEAK_DISTANCE = 2  # Minimum bin distance between peaks (~quarter tone)
HARD_VOCAL_RANGE = False  # Drop peaks outside vocal MIDI range
VOCAL_DOMINANCE_THRESHOLD = 0.6  # Require out-of-range suppression when vocal dominates
SALIENCE_EPS = 1e-8  # Numerical stability for normalization

# ── Contour Formation parameters ─────────────────────────────────────────────
SEMITONE_RATIO = 2.0 ** (1.0 / 12.0)  # ~1.0595
MAX_FREQ_RATIO = SEMITONE_RATIO  # max frequency jump between adjacent frames
MIN_CONTOUR_FRAMES = 8  # minimum contour length (~185ms)

# ── Melody Selection parameters ──────────────────────────────────────────────
VOCAL_MIDI_LOW = 55  # G3
VOCAL_MIDI_HIGH = 80  # G#5
VOCAL_RANGE_BONUS = 3.0  # score multiplier for vocal range
VOCAL_RANGE_PENALTY = 0.5  # penalty for out-of-range contours

# ── Viterbi Smoothing parameters ─────────────────────────────────────────────
VITERBI_SELF_TRANSITION = 0.92  # Self-transition probability for Viterbi
MIDI_RANGE = (21, 108)  # A0 to C8

# ── Note Segmentation parameters ─────────────────────────────────────────────
GAP_BRIDGE_SEC = 0.04  # 40ms breathing tolerance
MIN_DURATION_SEC = 0.04  # 40ms minimum note

# ── Cache ────────────────────────────────────────────────────────────────────
DEFAULT_CACHE_DIR = Path("test/cache")
SALIENCE_CACHE_VERSION = "v4"


def compute_salience_map(
    mp3_path: Path,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute Harmonic Salience map from an MP3 file via CQT.

    Loads the MP3, computes a CQT magnitude spectrogram, then builds a
    Harmonic Salience map that emphasizes frequencies whose overtones
    are also present. Results are cached by MD5 hash of the MP3 content.

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for cached .npz files. Defaults to test/cache.

    Returns:
        Tuple of (salience_map, frequencies, times) where:
            - salience_map: np.ndarray [shape=(n_bins, n_frames)] harmonic salience
            - frequencies: np.ndarray [shape=(n_bins,)] Hz per CQT bin
            - times: np.ndarray [shape=(n_frames,)] seconds per frame

    Raises:
        FileNotFoundError: If mp3_path does not exist.
    """
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        raise FileNotFoundError(f"MP3 file not found: {mp3_path}")

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # MD5-based cache key (same pattern as vocal_separator.py)
    file_bytes = mp3_path.read_bytes()
    md5_hash = hashlib.md5(file_bytes).hexdigest()
    cached_path = cache_dir / f"{md5_hash}_salience_{SALIENCE_CACHE_VERSION}.npz"

    # Check cache
    if cached_path.exists() and cached_path.stat().st_size > 0:
        logger.info("Cache HIT: %s -> %s", mp3_path.name, cached_path.name)
        data = np.load(cached_path)
        return data["salience"], data["freqs"], data["times"]

    logger.info(
        "Cache MISS: %s (hash=%s), computing salience...", mp3_path.name, md5_hash
    )

    # 1. Load audio
    logger.info("Loading audio: %s (sr=%d)", mp3_path.name, SR)
    y, sr = librosa.load(str(mp3_path), sr=SR)
    duration = len(y) / sr
    logger.info("Audio loaded: %.1fs, %d samples", duration, len(y))

    # 2. CQT spectrogram
    logger.info(
        "Computing CQT: n_bins=%d, bins_per_octave=%d, hop=%d, fmin=%.1f",
        N_BINS,
        BINS_PER_OCTAVE,
        HOP_LENGTH,
        FMIN,
    )
    C = np.abs(
        librosa.cqt(
            y,
            sr=sr,
            hop_length=HOP_LENGTH,
            n_bins=N_BINS,
            bins_per_octave=BINS_PER_OCTAVE,
            fmin=FMIN,
        )
    )
    logger.info("CQT shape: %s", C.shape)

    # Frequency and time arrays
    freqs = librosa.cqt_frequencies(
        n_bins=N_BINS, fmin=FMIN, bins_per_octave=BINS_PER_OCTAVE
    )
    times = librosa.times_like(C, sr=sr, hop_length=HOP_LENGTH)

    # 3. Harmonic Salience map
    logger.info("Computing salience: harmonics=%s, weights=%s", HARMONICS, WEIGHTS)
    salience = librosa.salience(
        C,
        freqs=freqs,
        harmonics=HARMONICS,
        weights=WEIGHTS,
        filter_peaks=False,
        fill_value=0.0,
    )
    # Replace NaN with 0 (safety)
    salience = np.nan_to_num(salience, nan=0.0)

    # Emphasize vocal range to reduce accompaniment dominance
    midi_bins = 12.0 * np.log2(freqs / 440.0) + 69.0
    range_mask = (midi_bins >= VOCAL_MIDI_LOW) & (midi_bins <= VOCAL_MIDI_HIGH)
    range_weights = np.where(range_mask, 1.0, VOCAL_RANGE_PENALTY)
    salience = salience * range_weights[:, np.newaxis]
    logger.info(
        "Salience shape: %s, max=%.4f (vocal bins=%d, penalty=%.2f)",
        salience.shape,
        salience.max(),
        int(np.sum(range_mask)),
        VOCAL_RANGE_PENALTY,
    )

    # 4. Cache result
    np.savez_compressed(cached_path, salience=salience, freqs=freqs, times=times)
    logger.info("Cached salience to: %s", cached_path.name)

    return salience, freqs, times


def detect_peaks(
    salience: np.ndarray,
    freqs: np.ndarray,
) -> list[list[tuple[float, float]]]:
    """Detect pitch peaks per frame from a Harmonic Salience map.

    For each time frame, runs scipy.signal.find_peaks with a prominence
    threshold to extract salient frequency peaks.

    Args:
        salience: Harmonic salience map [shape=(n_bins, n_frames)].
        freqs: Frequency array [shape=(n_bins,)] in Hz.

    Returns:
        List of length n_frames, where each element is a list of
        (frequency_hz, normalized_strength) tuples for detected peaks,
        sorted by strength descending.
    """
    n_bins, n_frames = salience.shape
    all_peaks: list[list[tuple[float, float]]] = []
    midi_bins = 12.0 * np.log2(freqs / 440.0) + 69.0
    vocal_mask = (midi_bins >= VOCAL_MIDI_LOW) & (midi_bins <= VOCAL_MIDI_HIGH)

    for frame_idx in range(n_frames):
        frame = salience[:, frame_idx]

        # Skip silent frames
        if frame.max() <= 0:
            all_peaks.append([])
            continue

        frame_max = frame.max()
        frame_max_vocal = frame[vocal_mask].max() if np.any(vocal_mask) else 0.0
        enforce_vocal_only = HARD_VOCAL_RANGE or (
            frame_max_vocal > 0
            and frame_max_vocal >= frame_max * VOCAL_DOMINANCE_THRESHOLD
        )
        prominence = max(PEAK_PROMINENCE, frame_max * PEAK_RELATIVE_PROMINENCE)
        peak_indices, _ = find_peaks(
            frame,
            prominence=prominence,
            distance=PEAK_DISTANCE,
        )

        if len(peak_indices) == 0:
            all_peaks.append([])
            continue

        # Build (frequency_hz, normalized_strength) tuples, sorted by strength desc
        frame_peaks: list[tuple[float, float]] = []
        for idx in peak_indices:
            freq_hz = float(freqs[idx])
            if enforce_vocal_only:
                midi = 12.0 * math.log2(freq_hz / 440.0) + 69.0
                if midi < VOCAL_MIDI_LOW or midi > VOCAL_MIDI_HIGH:
                    continue
            strength = float(frame[idx]) / (frame_max + SALIENCE_EPS)
            frame_peaks.append((freq_hz, strength))
        frame_peaks.sort(key=lambda x: x[1], reverse=True)
        all_peaks.append(frame_peaks)

    frames_with = sum(1 for p in all_peaks if p)
    logger.info(
        "Peak detection: %d/%d frames have peaks (%.1f%%)",
        frames_with,
        n_frames,
        100.0 * frames_with / n_frames if n_frames > 0 else 0,
    )

    return all_peaks


def form_contours(
    peaks: list[list[tuple[float, float]]],
    freqs: np.ndarray,
) -> list[list[tuple[int, float, float]]]:
    """Group temporally adjacent peaks into pitch contours.

    Uses greedy nearest-neighbor linking: for each peak in the current frame,
    find the closest-frequency active contour tail in the previous frame.
    If the frequency ratio is within one semitone (MAX_FREQ_RATIO), extend
    the contour; otherwise start a new one.

    Args:
        peaks: Per-frame peak list from detect_peaks().
            Each element is a list of (frequency_hz, normalized_strength) tuples.
        freqs: Frequency array [shape=(n_bins,)] in Hz (unused but kept
            for API consistency with detect_peaks output).

    Returns:
        List of contours, each contour being a list of
        (frame_index, frequency_hz, normalized_strength) tuples sorted by frame.
        Only contours with >= MIN_CONTOUR_FRAMES points are returned.
    """
    n_frames = len(peaks)
    # Active contours: list of contours still being extended
    # Each entry: list of (frame_idx, freq_hz, salience)
    active: list[list[tuple[int, float, float]]] = []
    # Track which active contours were extended this frame
    finished: list[list[tuple[int, float, float]]] = []

    for frame_idx in range(n_frames):
        frame_peaks = peaks[frame_idx]
        if not frame_peaks:
            # No peaks: all active contours end
            finished.extend(active)
            active = []
            continue

        # Track which active contours got extended
        extended = [False] * len(active)
        # Track which peaks started a new contour
        used_peaks = [False] * len(frame_peaks)

        # For each peak, find the closest active contour tail
        for p_idx, (p_freq, p_sal) in enumerate(frame_peaks):
            best_contour_idx = -1
            best_ratio = float("inf")

            for c_idx, contour in enumerate(active):
                if extended[c_idx]:
                    continue  # already extended by another peak
                tail_frame, tail_freq, _ = contour[-1]
                # Only consider contours whose tail is the previous frame
                if tail_frame != frame_idx - 1:
                    continue
                # Frequency ratio (always >= 1)
                ratio = max(p_freq / tail_freq, tail_freq / p_freq)
                if ratio < best_ratio:
                    best_ratio = ratio
                    best_contour_idx = c_idx

            if best_contour_idx >= 0 and best_ratio <= MAX_FREQ_RATIO:
                active[best_contour_idx].append((frame_idx, p_freq, p_sal))
                extended[best_contour_idx] = True
                used_peaks[p_idx] = True

        # Move non-extended active contours to finished
        new_active: list[list[tuple[int, float, float]]] = []
        for c_idx, contour in enumerate(active):
            if extended[c_idx]:
                new_active.append(contour)
            else:
                finished.append(contour)

        # Start new contours for unmatched peaks
        for p_idx, (p_freq, p_sal) in enumerate(frame_peaks):
            if not used_peaks[p_idx]:
                new_active.append([(frame_idx, p_freq, p_sal)])

        active = new_active

    # Flush remaining active contours
    finished.extend(active)

    # Filter by minimum length
    contours = [c for c in finished if len(c) >= MIN_CONTOUR_FRAMES]

    logger.info(
        "Contour formation: %d raw -> %d contours (min %d frames)",
        len(finished),
        len(contours),
        MIN_CONTOUR_FRAMES,
    )
    if contours:
        lengths = [len(c) for c in contours]
        logger.info(
            "Contour lengths: min=%d, max=%d, median=%d",
            min(lengths),
            max(lengths),
            int(np.median(lengths)),
        )

    return contours


def select_melody(
    contours: list[list[tuple[int, float, float]]],
) -> np.ndarray:
    """Select the most prominent melody contour and build a per-frame F0 array.

    Scores each contour by ``mean_strength * sqrt(duration_frames)``, with a
    bonus multiplier for contours whose mean frequency falls in the vocal
    range (MIDI 55-80, G3-G#5) and a penalty for erratic pitch movement.
    Overlapping contours are resolved by keeping the higher-scoring one per frame.

    Args:
        contours: List of contours from form_contours(). Each contour is a
            list of (frame_index, frequency_hz, normalized_strength) tuples.

    Returns:
        np.ndarray of shape (n_frames,) with F0 in Hz per frame.
        Unvoiced frames are 0.0.
    """
    if not contours:
        logger.warning("select_melody: no contours provided, returning empty array")
        return np.array([], dtype=np.float64)

    # Determine total number of frames from contour data
    max_frame = max(pt[0] for c in contours for pt in c)
    n_frames = max_frame + 1

    scored: list[tuple[float, int]] = []  # (score, contour_index)
    for c_idx, contour in enumerate(contours):
        strengths = [pt[2] for pt in contour]
        mean_strength = sum(strengths) / len(strengths)
        duration = len(contour)
        score = mean_strength * math.sqrt(duration)

        freqs_hz = [pt[1] for pt in contour]
        mean_freq = sum(freqs_hz) / len(freqs_hz)
        if mean_freq > 0:
            midi = 12.0 * math.log2(mean_freq / 440.0) + 69.0
            if VOCAL_MIDI_LOW <= midi <= VOCAL_MIDI_HIGH:
                score *= VOCAL_RANGE_BONUS
            else:
                score *= VOCAL_RANGE_PENALTY

        if len(freqs_hz) > 1:
            deltas = [
                abs(12.0 * math.log2(freqs_hz[i] / freqs_hz[i - 1]))
                for i in range(1, len(freqs_hz))
            ]
            mean_delta = sum(deltas) / len(deltas)
            score /= 1.0 + mean_delta

        scored.append((score, c_idx))

    scored.sort(key=lambda x: x[0], reverse=True)

    melody = np.zeros(n_frames, dtype=np.float64)
    assigned = np.zeros(n_frames, dtype=bool)

    for score, c_idx in scored:
        contour = contours[c_idx]
        contour_frames = [pt[0] for pt in contour]
        overlap_count = sum(1 for f in contour_frames if assigned[f])

        if overlap_count > len(contour) / 2:
            continue

        for frame_idx, freq_hz, _ in contour:
            if not assigned[frame_idx]:
                melody[frame_idx] = freq_hz
                assigned[frame_idx] = True

    voiced = int(np.sum(melody > 0))
    logger.info(
        "Melody selection: %d contours scored, %d/%d frames voiced (%.1f%%)",
        len(contours),
        voiced,
        n_frames,
        100.0 * voiced / n_frames if n_frames > 0 else 0,
    )

    return melody


def smooth_melody(melody_f0: np.ndarray) -> np.ndarray:
    """Apply Viterbi smoothing to fix octave errors in the melody F0 array.

    Quantizes the continuous F0 to MIDI bins, applies Viterbi decoding with
    a self-transition-favouring transition matrix, then converts back to Hz.
    Unvoiced frames (F0 == 0) are preserved as-is.

    Args:
        melody_f0: Per-frame F0 in Hz. Unvoiced frames are 0.0.

    Returns:
        Smoothed F0 array (same shape), with octave jumps corrected.
    """
    if len(melody_f0) == 0:
        return melody_f0.copy()

    voiced_mask = melody_f0 > 0
    if not np.any(voiced_mask):
        return melody_f0.copy()

    midi_low, midi_high = MIDI_RANGE
    n_states = midi_high - midi_low + 1  # 88 piano keys

    # Quantize voiced frames to MIDI bins
    midi_raw = np.zeros_like(melody_f0)
    midi_raw[voiced_mask] = np.round(
        12.0 * np.log2(melody_f0[voiced_mask] / 440.0) + 69.0
    )

    # Build observation likelihood matrix [n_states, n_frames]
    n_frames = len(melody_f0)
    obs_prob = np.full((n_states, n_frames), 1.0 / n_states)  # uniform prior

    sigma = 1.0  # Gaussian spread in semitones
    midi_bins = np.arange(midi_low, midi_high + 1)  # shape (n_states,)

    for t in range(n_frames):
        if not voiced_mask[t]:
            continue  # keep uniform for unvoiced
        detected_midi = midi_raw[t]
        # Gaussian centred on detected MIDI note
        dist = (midi_bins - detected_midi) ** 2
        likelihood = np.exp(-0.5 * dist / (sigma**2))
        likelihood /= likelihood.sum() + 1e-12
        obs_prob[:, t] = likelihood

    # Transition matrix: favour self-transitions
    transition = librosa.sequence.transition_loop(
        n_states, prob=VITERBI_SELF_TRANSITION
    )

    # Viterbi decoding
    smoothed_states = librosa.sequence.viterbi_discriminative(obs_prob, transition)

    # Convert states back to Hz
    smoothed_f0 = melody_f0.copy()
    for t in range(n_frames):
        if voiced_mask[t]:
            midi_note = smoothed_states[t] + midi_low
            smoothed_f0[t] = 440.0 * (2.0 ** ((midi_note - 69.0) / 12.0))

    corrections = int(
        np.sum(voiced_mask & (np.round(midi_raw) != (smoothed_states + midi_low)))
    )
    logger.info(
        "Viterbi smoothing: %d/%d voiced frames corrected (%.1f%%)",
        corrections,
        int(np.sum(voiced_mask)),
        100.0 * corrections / max(int(np.sum(voiced_mask)), 1),
    )

    return smoothed_f0


def segment_notes(melody_f0: np.ndarray) -> list[Note]:
    """Convert a continuous F0 array into discrete Note objects.

    Groups consecutive frames with the same MIDI pitch, bridges short gaps,
    and filters out very short notes. Follows the same pattern as
    ``core.pitch_extractor._segment_notes``.

    Args:
        melody_f0: Per-frame F0 in Hz. Unvoiced frames are 0.0.

    Returns:
        List of Note objects sorted by onset time.
    """
    if len(melody_f0) == 0:
        return []

    # 1. Convert Hz to MIDI (0 stays 0 for unvoiced)
    midi_frames = np.zeros(len(melody_f0), dtype=int)
    voiced_mask = melody_f0 > 0
    if np.any(voiced_mask):
        midi_frames[voiced_mask] = np.round(
            12.0 * np.log2(melody_f0[voiced_mask] / 440.0) + 69.0
        ).astype(int)

    # 2. Find contiguous voiced groups
    padded = np.concatenate(([0], voiced_mask.astype(int), [0]))
    boundaries = np.where(np.diff(padded))[0]
    starts = boundaries[0::2]
    ends = boundaries[1::2]

    if len(starts) == 0:
        logger.warning("segment_notes: no voiced frames found")
        return []

    # 3. Gap bridging: merge groups if gap <= GAP_BRIDGE_SEC
    gap_frames = int(GAP_BRIDGE_SEC * SR / HOP_LENGTH)
    merged: list[list[int]] = []

    for start, end in zip(starts, ends):
        if not merged:
            merged.append([int(start), int(end)])
        else:
            gap = start - merged[-1][1]
            if gap <= gap_frames:
                merged[-1][1] = int(end)
            else:
                merged.append([int(start), int(end)])

    logger.info(
        "segment_notes: %d raw groups -> %d after gap bridging (%d frame tolerance)",
        len(starts),
        len(merged),
        gap_frames,
    )

    # 4. Within each merged group, split into sub-notes by MIDI pitch changes
    notes: list[Note] = []
    for g_start, g_end in merged:
        segment_midi = midi_frames[g_start:g_end]
        segment_voiced = voiced_mask[g_start:g_end]

        # Walk through and group consecutive frames with the same pitch
        i = 0
        while i < len(segment_midi):
            if not segment_voiced[i]:
                i += 1
                continue
            current_pitch = segment_midi[i]
            j = i + 1
            while j < len(segment_midi):
                if not segment_voiced[j]:
                    # Allow skipping unvoiced frames inside a group
                    j += 1
                    continue
                if segment_midi[j] != current_pitch:
                    break
                j += 1

            # Compute onset and duration
            onset_sec = (g_start + i) * HOP_LENGTH / SR
            duration_sec = (j - i) * HOP_LENGTH / SR

            if duration_sec >= MIN_DURATION_SEC:
                midi_low, midi_high = MIDI_RANGE
                if midi_low <= current_pitch <= midi_high:
                    notes.append(
                        Note(
                            pitch=int(current_pitch),
                            onset=round(onset_sec, 4),
                            duration=round(duration_sec, 4),
                        )
                    )
            i = j

    logger.info("segment_notes: %d notes extracted", len(notes))
    return notes


def extract_melody(mp3_path: Path, cache_dir: Path = DEFAULT_CACHE_DIR) -> list[Note]:
    """End-to-end melody extraction from an MP3 file.

    Chains the full custom pipeline:
    compute_salience_map -> detect_peaks -> form_contours ->
    select_melody -> smooth_melody -> segment_notes

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for cached .npz files. Defaults to test/cache.

    Returns:
        List of Note objects representing the extracted melody.
    """
    logger.info("extract_melody: starting pipeline for %s", mp3_path)

    salience, freqs, times = compute_salience_map(mp3_path, cache_dir)
    peaks = detect_peaks(salience, freqs)
    contours = form_contours(peaks, freqs)
    melody_f0 = select_melody(contours)
    melody_f0 = smooth_melody(melody_f0)
    notes = segment_notes(melody_f0)

    logger.info("extract_melody: pipeline complete, %d notes", len(notes))
    return notes
