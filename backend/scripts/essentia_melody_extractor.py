#!/usr/bin/env python3
"""
Essentia Melody Extractor (WSL용)

입력: 오디오 파일 경로 (WSL 형식: /mnt/c/...)
출력: stdout으로 JSON 배열 [{"pitch": 60, "onset": 0.5, "duration": 0.25}, ...]

Essentia의 PredominantPitchMelodia 알고리즘을 사용하여 멜로디를 추출합니다.
- confidence >= 0.8 프레임만 유효
- 연속 유효 프레임 → 하나의 노트 (median pitch)
- 최소 duration: 50ms
- 피아노 범위 (MIDI 21-108) 필터링
"""

import sys
import json
import numpy as np
from pathlib import Path

try:
    import essentia.standard as es
except ImportError:
    print(
        json.dumps(
            {
                "error": "Essentia not installed. Run: pip3 install --break-system-packages essentia"
            }
        ),
        file=sys.stderr,
    )
    sys.exit(1)


# ============================================================================
# Constants
# ============================================================================

FRAME_SIZE = 2048
HOP_SIZE = 128
SAMPLE_RATE = 44100

# Confidence threshold for valid pitch frames
# Note: Essentia's PredominantPitchMelodia typically produces confidence values < 0.6
# Setting threshold too high (e.g., 0.8) will filter out all notes
CONFIDENCE_THRESHOLD = 0.3

# Minimum note duration in seconds
MIN_NOTE_DURATION = 0.05  # 50ms

# Piano MIDI range
PIANO_MIN_PITCH = 21  # A0
PIANO_MAX_PITCH = 108  # C8


# ============================================================================
# Helper Functions
# ============================================================================


def hz_to_midi(frequency: float) -> int:
    """
    Convert frequency (Hz) to MIDI note number.

    Args:
        frequency: Frequency in Hz

    Returns:
        MIDI note number (rounded to nearest integer)
    """
    if frequency <= 0:
        return 0

    # MIDI note = 69 + 12 * log2(f / 440)
    midi = 69 + 12 * np.log2(frequency / 440.0)
    return int(round(midi))


def convert_pitch_to_notes(
    pitch_values: np.ndarray, confidence: np.ndarray, hop_size: int, sample_rate: int
) -> list:
    """
    Convert pitch contour to note list.

    Algorithm:
    1. Filter frames with confidence >= CONFIDENCE_THRESHOLD
    2. Group consecutive valid frames into notes
    3. Use median pitch for each note
    4. Filter notes shorter than MIN_NOTE_DURATION
    5. Filter notes outside piano range

    Args:
        pitch_values: Array of pitch values (Hz) per frame
        confidence: Array of confidence values (0-1) per frame
        hop_size: Hop size in samples
        sample_rate: Sample rate in Hz

    Returns:
        List of notes: [{"pitch": int, "onset": float, "duration": float}, ...]
    """
    notes = []

    # Frame duration in seconds
    frame_duration = hop_size / sample_rate

    # Find valid frames (confidence >= threshold)
    valid_frames = confidence >= CONFIDENCE_THRESHOLD

    # Group consecutive valid frames
    current_note_frames = []
    current_note_start_idx = None

    for i, is_valid in enumerate(valid_frames):
        if is_valid:
            if current_note_start_idx is None:
                # Start new note
                current_note_start_idx = i
                current_note_frames = [pitch_values[i]]
            else:
                # Continue current note
                current_note_frames.append(pitch_values[i])
        else:
            if current_note_start_idx is not None:
                # End current note
                onset = current_note_start_idx * frame_duration
                duration = len(current_note_frames) * frame_duration

                # Filter short notes
                if duration >= MIN_NOTE_DURATION:
                    # Use median pitch
                    median_pitch_hz = np.median(current_note_frames)
                    midi_pitch = hz_to_midi(median_pitch_hz)

                    # Filter piano range
                    if PIANO_MIN_PITCH <= midi_pitch <= PIANO_MAX_PITCH:
                        notes.append(
                            {
                                "pitch": midi_pitch,
                                "onset": round(onset, 3),
                                "duration": round(duration, 3),
                            }
                        )

                # Reset
                current_note_start_idx = None
                current_note_frames = []

    # Handle last note if still active
    if current_note_start_idx is not None:
        onset = current_note_start_idx * frame_duration
        duration = len(current_note_frames) * frame_duration

        if duration >= MIN_NOTE_DURATION:
            median_pitch_hz = np.median(current_note_frames)
            midi_pitch = hz_to_midi(median_pitch_hz)

            if PIANO_MIN_PITCH <= midi_pitch <= PIANO_MAX_PITCH:
                notes.append(
                    {
                        "pitch": midi_pitch,
                        "onset": round(onset, 3),
                        "duration": round(duration, 3),
                    }
                )

    return notes


def extract_melody(audio_path: str) -> list:
    """
    Extract melody from audio file using Essentia.

    Args:
        audio_path: Path to audio file (WSL format: /mnt/c/...)

    Returns:
        List of notes: [{"pitch": int, "onset": float, "duration": float}, ...]

    Raises:
        Exception: If audio loading or melody extraction fails
    """
    # Load audio
    try:
        loader = es.MonoLoader(filename=audio_path, sampleRate=SAMPLE_RATE)
        audio = loader()
    except Exception as e:
        raise Exception(f"Failed to load audio: {e}")

    if len(audio) == 0:
        raise Exception("Audio file is empty")

    # Extract pitch using PredominantPitchMelodia
    pitch_extractor = es.PredominantPitchMelodia(
        frameSize=FRAME_SIZE, hopSize=HOP_SIZE, sampleRate=SAMPLE_RATE
    )

    pitch_values, pitch_confidence = pitch_extractor(audio)

    # Convert pitch contour to notes
    notes = convert_pitch_to_notes(
        pitch_values, pitch_confidence, HOP_SIZE, SAMPLE_RATE
    )

    return notes


# ============================================================================
# Main
# ============================================================================


def main():
    if len(sys.argv) != 2:
        print(
            json.dumps(
                {"error": "Usage: python3 essentia_melody_extractor.py <audio_path>"}
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    audio_path = sys.argv[1]

    # Validate file exists
    if not Path(audio_path).exists():
        print(json.dumps({"error": f"File not found: {audio_path}"}), file=sys.stderr)
        sys.exit(1)

    try:
        notes = extract_melody(audio_path)

        # Output JSON to stdout
        print(json.dumps(notes))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
