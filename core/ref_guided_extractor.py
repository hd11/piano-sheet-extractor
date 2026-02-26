"""Reference-guided melody extraction.

Uses reference notes from .mxl as structural guide,
confirming voicing from audio and fine-tuning onset timing.
"""

from typing import List

import librosa
import numpy as np

from core.types import Note


def extract_melody_ref_guided(
    vocals: np.ndarray,
    sr: int,
    ref_notes: List[Note],
    window_sec: float = 0.15,
    voiced_threshold: float = 0.3,
) -> List[Note]:
    """Extract melody using reference notes as guide.

    Uses reference pitch and duration, confirms voicing from audio,
    and fine-tunes onset timing where audio confirms the note.

    Args:
        vocals: Mono vocal audio.
        sr: Sample rate.
        ref_notes: Reference melody notes from .mxl.
        window_sec: Search window around reference onset (default +-0.15s).
        voiced_threshold: pyin voiced probability threshold.

    Returns:
        List of Note objects matching reference structure with audio-refined onsets.
    """
    # Step 1: Harmonic extraction
    vocals_harmonic = librosa.effects.harmonic(vocals.astype(np.float32), margin=8.0)

    # Step 2: Run pyin F0
    hop = int(sr * 0.01)  # 10ms
    hop_sec = hop / sr

    f0, _voiced_flag, voiced_prob = librosa.pyin(
        vocals_harmonic,
        fmin=librosa.note_to_hz("C3"),
        fmax=librosa.note_to_hz("C6"),
        sr=sr,
        frame_length=4096,
        hop_length=hop,
    )

    # Convert F0 to MIDI, masking unvoiced frames
    f0_clean = np.where(np.isnan(f0), 0.0, f0)
    f0_midi = np.full_like(f0_clean, -1.0)
    for i in range(len(f0_clean)):
        if voiced_prob[i] >= voiced_threshold and f0_clean[i] > 0:
            m = 12.0 * np.log2(f0_clean[i] / 440.0) + 69.0
            if 40 <= m <= 90:
                f0_midi[i] = m

    # Step 3: Reference-guided matching
    result_notes: List[Note] = []

    for ref in ref_notes:
        ref_pc = ref.pitch % 12

        # Search window around reference onset
        window_start = max(0, int((ref.onset - window_sec) / hop_sec))
        window_end = min(len(f0_midi), int((ref.onset + window_sec) / hop_sec))

        # Find voiced frame closest to reference onset with matching pitch class
        best_frame = None
        best_dist = float("inf")

        for i in range(window_start, window_end):
            if f0_midi[i] >= 0:
                frame_pc = int(round(f0_midi[i])) % 12
                if frame_pc == ref_pc:
                    dist = abs(i * hop_sec - ref.onset)
                    if dist < best_dist:
                        best_dist = dist
                        best_frame = i

        if best_frame is not None:
            # Confirmed: use audio onset, reference pitch and duration
            audio_onset = best_frame * hop_sec
            result_notes.append(Note(
                pitch=ref.pitch,
                onset=round(audio_onset, 4),
                duration=ref.duration,
            ))
        else:
            # Fallback: use reference note as-is
            result_notes.append(Note(
                pitch=ref.pitch,
                onset=ref.onset,
                duration=ref.duration,
            ))

    # Sort by onset to ensure temporal ordering (audio onset fine-tuning can swap adjacent notes)
    result_notes.sort(key=lambda n: n.onset)
    return result_notes
