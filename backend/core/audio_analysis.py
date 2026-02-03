"""
Audio Analysis Module - BPM, Key, and Chord Detection

This module provides automatic detection of musical features from audio files
using librosa for signal processing.

Functions:
    detect_bpm: Detect tempo (BPM) from audio file
    detect_key: Detect musical key using Krumhansl-Schmuckler algorithm
    detect_chords: Detect chord progression using chroma template matching

Dependencies:
    - librosa>=0.10.0
    - numpy
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import librosa
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Key Detection Constants (Krumhansl-Schmuckler)
# =============================================================================

# Krumhansl-Schmuckler profiles (SSOT)
# Source: Krumhansl, C. L. (1990). Cognitive Foundations of Musical Pitch
KS_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
KS_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

# 12 root notes (C=0, C#=1, ..., B=11)
ROOT_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# =============================================================================
# Chord Detection Constants
# =============================================================================

# Chord templates (major, minor) - 12 roots x 2 = 24 chords
# Index: C=0, C#=1, D=2, D#=3, E=4, F=5, F#=6, G=7, G#=8, A=9, A#=10, B=11
CHORD_TEMPLATES: Dict[str, List[int]] = {
    # Major: root + major 3rd (4 semitones) + perfect 5th (7 semitones)
    "C": [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
    "C#": [0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
    "D": [0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0],
    "D#": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],
    "E": [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1],
    "F": [1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0],
    "F#": [0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
    "G": [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1],
    "G#": [1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0],
    "A": [0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
    "A#": [0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0],
    "B": [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1],
    # Minor: root + minor 3rd (3 semitones) + perfect 5th (7 semitones)
    "Cm": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
    "C#m": [0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
    "Dm": [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0],
    "D#m": [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0],
    "Em": [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],
    "Fm": [1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
    "F#m": [0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
    "Gm": [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0],
    "G#m": [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1],
    "Am": [1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
    "A#m": [0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
    "Bm": [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1],
}


# =============================================================================
# BPM Detection
# =============================================================================


def detect_bpm(audio_path: Path) -> Tuple[float, float]:
    """
    Detect BPM (tempo) from an audio file using librosa.

    Args:
        audio_path: Path to the audio file (MP3, WAV, FLAC, etc.)

    Returns:
        Tuple of (bpm, confidence):
            - bpm: Detected tempo in beats per minute
            - confidence: Confidence score (0.0 - 1.0)

    Algorithm:
        1. Load audio file with librosa
        2. Use librosa.beat.beat_track() for tempo estimation
        3. Calculate confidence based on beat strength consistency

    Raises:
        FileNotFoundError: If audio file does not exist
        ValueError: If audio file cannot be processed

    Example:
        >>> bpm, conf = detect_bpm(Path("song.mp3"))
        >>> print(f"BPM: {bpm:.1f} (confidence: {conf:.2f})")
        BPM: 120.0 (confidence: 0.85)
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info(f"Detecting BPM from: {audio_path}")

    try:
        # Load audio file
        y, sr = librosa.load(str(audio_path))

        # Handle empty or silent audio
        if len(y) == 0 or np.max(np.abs(y)) < 1e-6:
            logger.warning("Audio is empty or silent")
            return 0.0, 0.0

        # Detect tempo and beats
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

        # Handle case where no beats detected
        if len(beat_frames) == 0:
            logger.warning("No beats detected in audio")
            return float(tempo) if np.isscalar(tempo) else float(tempo[0]), 0.0

        # Calculate confidence based on beat strength
        # Get onset strength envelope
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        # Calculate beat strength at detected beat positions
        beat_strengths = onset_env[beat_frames[beat_frames < len(onset_env)]]

        if len(beat_strengths) > 0:
            # Confidence based on:
            # 1. Mean beat strength (normalized)
            # 2. Consistency of beat intervals
            mean_strength = np.mean(beat_strengths)
            max_strength = np.max(onset_env) if np.max(onset_env) > 0 else 1.0
            strength_confidence = mean_strength / max_strength

            # Beat interval consistency
            if len(beat_frames) > 1:
                beat_intervals = np.diff(beat_frames)
                interval_std = np.std(beat_intervals)
                interval_mean = np.mean(beat_intervals)
                interval_cv = interval_std / interval_mean if interval_mean > 0 else 1.0
                # Lower coefficient of variation = more consistent = higher confidence
                interval_confidence = max(0.0, 1.0 - interval_cv)
            else:
                interval_confidence = 0.5

            # Combined confidence
            confidence = (strength_confidence + interval_confidence) / 2
            confidence = min(1.0, max(0.0, confidence))
        else:
            confidence = 0.5

        # Handle numpy array return from newer librosa versions
        tempo_value = float(tempo) if np.isscalar(tempo) else float(tempo[0])

        logger.info(f"Detected BPM: {tempo_value:.1f} (confidence: {confidence:.2f})")

        return tempo_value, confidence

    except Exception as e:
        logger.error(f"Error detecting BPM: {e}")
        raise ValueError(f"Failed to process audio file: {e}")


# =============================================================================
# Key Detection (Krumhansl-Schmuckler Algorithm)
# =============================================================================


def detect_key(y: np.ndarray, sr: int) -> Tuple[str, float]:
    """
    Detect musical key using the Krumhansl-Schmuckler algorithm.

    Args:
        y: Audio time series (numpy array)
        sr: Sample rate of the audio

    Returns:
        Tuple of (key_name, confidence):
            - key_name: Detected key (e.g., "C major", "A minor")
            - confidence: Confidence score (0.0 - 1.0)

    Algorithm:
        1. Extract chroma features (12 pitch classes) using CQT
        2. Average chroma across all frames
        3. Calculate Pearson correlation with 24 key profiles
           (12 roots x 2 modes = 24 candidates)
        4. Select key with highest correlation
        5. Normalize confidence: (correlation + 1) / 2

    Note:
        The Krumhansl-Schmuckler profiles are based on:
        Krumhansl, C. L. (1990). Cognitive Foundations of Musical Pitch

    Example:
        >>> y, sr = librosa.load("song.mp3")
        >>> key, conf = detect_key(y, sr)
        >>> print(f"Key: {key} (confidence: {conf:.2f})")
        Key: C major (confidence: 0.85)
    """
    # Handle empty or silent audio
    if len(y) == 0 or np.max(np.abs(y)) < 1e-6:
        logger.warning("Audio is empty or silent, cannot detect key")
        return "C major", 0.0

    logger.info("Detecting musical key...")

    # 1. Extract chroma features (CQT-based, more accurate)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # 2. Average chroma across all frames
    chroma_mean = np.mean(chroma, axis=1)

    # Handle case where chroma is all zeros
    if np.max(chroma_mean) < 1e-6:
        logger.warning("Chroma features are all zeros")
        return "C major", 0.0

    # 3. Calculate correlation with 24 key profiles
    best_key = None
    best_corr = -1.0

    for root in range(12):
        # Rotate profiles by root position
        major_profile = np.roll(KS_MAJOR_PROFILE, root)
        minor_profile = np.roll(KS_MINOR_PROFILE, root)

        # Pearson correlation coefficient
        major_corr = np.corrcoef(chroma_mean, major_profile)[0, 1]
        minor_corr = np.corrcoef(chroma_mean, minor_profile)[0, 1]

        # Handle NaN correlations
        if np.isnan(major_corr):
            major_corr = -1.0
        if np.isnan(minor_corr):
            minor_corr = -1.0

        if major_corr > best_corr:
            best_corr = major_corr
            best_key = f"{ROOT_NAMES[root]} major"

        if minor_corr > best_corr:
            best_corr = minor_corr
            best_key = f"{ROOT_NAMES[root]} minor"

    # 4. Normalize confidence (correlation range: -1 to 1 -> 0 to 1)
    confidence = (best_corr + 1) / 2
    confidence = min(1.0, max(0.0, confidence))

    logger.info(f"Detected key: {best_key} (confidence: {confidence:.2f})")

    return best_key, confidence


# =============================================================================
# Chord Detection (Chroma Template Matching)
# =============================================================================


def match_chord(
    frame: np.ndarray, templates: Dict[str, List[int]]
) -> Tuple[str, float]:
    """
    Match a single chroma frame to chord templates using cosine similarity.

    Args:
        frame: 12-dimensional chroma vector (unnormalized)
        templates: Dictionary of chord_name -> template_vector

    Returns:
        Tuple of (best_chord, confidence):
            - best_chord: Name of the best matching chord
            - confidence: Cosine similarity score (0.0 - 1.0)

    Algorithm:
        1. Normalize input frame by L2 norm
        2. For each template, calculate cosine similarity
        3. Return chord with highest similarity

    Note:
        Returns "N" (No chord) for silent frames (norm < 1e-6)
    """
    frame_norm = np.linalg.norm(frame)

    # Handle silent frame
    if frame_norm < 1e-6:
        return "N", 0.0

    frame_normalized = frame / frame_norm

    best_chord = "N"
    best_score = 0.0

    for chord_name, template in templates.items():
        template_arr = np.array(template, dtype=float)
        template_norm = np.linalg.norm(template_arr)
        template_normalized = template_arr / template_norm

        # Cosine similarity
        similarity = np.dot(frame_normalized, template_normalized)

        if similarity > best_score:
            best_score = similarity
            best_chord = chord_name

    return best_chord, float(best_score)


def merge_consecutive_chords(
    chords: List[Dict], sr: int, hop_length: int
) -> List[Dict]:
    """
    Merge consecutive identical chords and calculate duration.

    Args:
        chords: List of chord dicts with {time, chord, confidence}
        sr: Sample rate
        hop_length: Hop length used for chroma extraction

    Returns:
        List of merged chord dicts with {time, chord, confidence, duration}

    Duration calculation rules (SSOT):
        1. Merge consecutive frames with the same chord
        2. duration = next_chord_time - current_chord_time
        3. Last chord duration = remaining_frames * hop_length / sr
        4. confidence = average of merged frames' confidence
    """
    if not chords:
        return []

    merged = []
    current = chords[0].copy()
    confidence_sum = current["confidence"]
    frame_count = 1

    for next_chord in chords[1:]:
        if next_chord["chord"] == current["chord"]:
            # Same chord: merge
            confidence_sum += next_chord["confidence"]
            frame_count += 1
        else:
            # Different chord: save current and start new
            current["duration"] = next_chord["time"] - current["time"]
            current["confidence"] = confidence_sum / frame_count
            merged.append(current)

            # Start new chord
            current = next_chord.copy()
            confidence_sum = current["confidence"]
            frame_count = 1

    # Handle last chord
    frame_duration = hop_length / sr
    current["duration"] = frame_count * frame_duration
    current["confidence"] = confidence_sum / frame_count
    merged.append(current)

    return merged


def detect_chords(y: np.ndarray, sr: int, hop_length: int = 512) -> List[Dict]:
    """
    Detect chord progression using librosa chroma and template matching.

    Args:
        y: Audio time series (numpy array)
        sr: Sample rate of the audio
        hop_length: Hop length for chroma extraction (default: 512)

    Returns:
        List of chord dicts, each containing:
            - time: Start time in seconds (float)
            - chord: Chord name (str, e.g., "C", "Am", "F#m")
            - confidence: Confidence score (0.0 - 1.0)
            - duration: Duration in seconds (float)

    Algorithm:
        1. Extract chroma features using CQT
        2. For each frame, match to 24 chord templates (12 major + 12 minor)
        3. Use cosine similarity for matching
        4. Merge consecutive identical chords
        5. Calculate duration for each merged chord

    Limitations:
        - Only detects major and minor triads (24 chords total)
        - Complex chords (7th, 9th, sus) are not detected
        - Expected accuracy: ~60% (manual correction assumed)

    Example:
        >>> y, sr = librosa.load("song.mp3")
        >>> chords = detect_chords(y, sr)
        >>> for c in chords[:5]:
        ...     print(f"{c['time']:.2f}s: {c['chord']} ({c['confidence']:.2f})")
        0.00s: C (0.85)
        2.10s: Am (0.72)
        4.20s: F (0.68)
    """
    # Handle empty or silent audio
    if len(y) == 0 or np.max(np.abs(y)) < 1e-6:
        logger.warning("Audio is empty or silent, cannot detect chords")
        return []

    logger.info("Detecting chord progression...")

    # Extract chroma features
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)

    # Match each frame to chord templates
    chords = []
    for i, frame in enumerate(chroma.T):
        best_chord, best_score = match_chord(frame, CHORD_TEMPLATES)
        time = librosa.frames_to_time(i, sr=sr, hop_length=hop_length)
        chords.append(
            {"time": float(time), "chord": best_chord, "confidence": best_score}
        )

    # Merge consecutive identical chords
    merged = merge_consecutive_chords(chords, sr, hop_length)

    # Filter out "N" (no chord) segments if desired
    # Keep them for now as they indicate silence/unclear sections

    logger.info(f"Detected {len(merged)} chord segments")

    return merged


# =============================================================================
# Convenience Functions
# =============================================================================


def analyze_audio(audio_path: Path) -> Dict:
    """
    Perform complete audio analysis: BPM, key, and chord detection.

    Args:
        audio_path: Path to the audio file

    Returns:
        Dictionary with analysis results:
            - bpm: float (tempo in BPM)
            - bpm_confidence: float (0.0 - 1.0)
            - key: str (e.g., "C major")
            - key_confidence: float (0.0 - 1.0)
            - chords: list of chord dicts

    Example:
        >>> result = analyze_audio(Path("song.mp3"))
        >>> print(f"BPM: {result['bpm']}, Key: {result['key']}")
    """
    logger.info(f"Starting complete audio analysis: {audio_path}")

    # Detect BPM (loads audio internally)
    bpm, bpm_confidence = detect_bpm(audio_path)

    # Load audio once for key and chord detection
    y, sr = librosa.load(str(audio_path))

    # Detect key
    key, key_confidence = detect_key(y, sr)

    # Detect chords
    chords = detect_chords(y, sr)

    result = {
        "bpm": bpm,
        "bpm_confidence": bpm_confidence,
        "key": key,
        "key_confidence": key_confidence,
        "chords": chords,
    }

    logger.info(f"Analysis complete: BPM={bpm:.1f}, Key={key}")

    return result
