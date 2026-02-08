"""F0 (fundamental frequency) extraction using torchcrepe and note segmentation."""

from __future__ import annotations

import logging

import librosa
import numpy as np
import torch
import torchcrepe

from core.types import Note

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_TARGET_SR = 16000  # torchcrepe expects 16 kHz
_MIDI_MIN = 21  # A0
_MIDI_MAX = 108  # C8
_DEFAULT_PERIODICITY_THRESHOLD = 0.5
_DEFAULT_MIN_NOTE_DUR = 0.02  # seconds


def extract_f0(
    vocals: np.ndarray,
    sr: int,
    hop_ms: float = 10.0,
    model: str = "tiny",
) -> tuple[np.ndarray, np.ndarray]:
    """Extract F0 and periodicity from a vocal signal using torchcrepe.

    Parameters
    ----------
    vocals : np.ndarray
        Mono audio waveform (float32).
    sr : int
        Sample rate of *vocals*.
    hop_ms : float
        Hop size in milliseconds (default 10 ms).
    model : str
        torchcrepe model size (default ``'tiny'``).

    Returns
    -------
    f0 : np.ndarray
        Fundamental frequency in Hz per frame.  Unvoiced frames may contain
        arbitrary values (use *periodicity* to gate them).
    periodicity : np.ndarray
        Periodicity confidence in [0, 1] per frame, same length as *f0*.
    """
    # Resample to 16 kHz if needed
    if sr != _TARGET_SR:
        logger.debug("Resampling %d -> %d Hz", sr, _TARGET_SR)
        vocals = librosa.resample(vocals, orig_sr=sr, target_sr=_TARGET_SR)

    hop_length = int(_TARGET_SR * hop_ms / 1000.0)

    # torchcrepe expects a batched tensor of shape (batch, samples)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    audio_t = torch.tensor(vocals, dtype=torch.float32).unsqueeze(0).to(device)

    logger.info(
        "Running torchcrepe (model=%s, hop=%d, device=%s, samples=%d)",
        model,
        hop_length,
        device,
        len(vocals),
    )

    pitch, periodicity = torchcrepe.predict(
        audio_t,
        _TARGET_SR,
        hop_length,
        fmin=50,
        fmax=800,
        model=model,
        device=device,
        return_periodicity=True,
        batch_size=512,
    )

    # Squeeze batch dimension -> 1-D numpy
    pitch = pitch.squeeze(0).cpu().numpy()
    periodicity = periodicity.squeeze(0).cpu().numpy()

    # Median filter to smooth pitch
    pitch = (
        torchcrepe.filter.median(torch.tensor(pitch).unsqueeze(0), 3).squeeze(0).numpy()
    )

    logger.info("F0 extracted: %d frames", len(pitch))
    return pitch, periodicity


def f0_to_notes(
    f0: np.ndarray,
    periodicity: np.ndarray,
    hop_sec: float,
    periodicity_threshold: float = _DEFAULT_PERIODICITY_THRESHOLD,
    min_note_dur: float = _DEFAULT_MIN_NOTE_DUR,
) -> list[Note]:
    """Convert an F0 contour into a list of MIDI-style :class:`Note` objects.

    Parameters
    ----------
    f0 : np.ndarray
        Fundamental frequency per frame (Hz).  Unvoiced / silence should be
        indicated by *periodicity* < *periodicity_threshold* (or f0 <= 0).
    periodicity : np.ndarray
        Confidence per frame in [0, 1].
    hop_sec : float
        Time between successive frames in seconds.
    periodicity_threshold : float
        Frames below this are treated as unvoiced.
    min_note_dur : float
        Notes shorter than this (seconds) are discarded.

    Returns
    -------
    list[Note]
        Detected notes sorted by onset time.
    """
    n_frames = len(f0)
    if n_frames != len(periodicity):
        raise ValueError(
            f"f0 length ({n_frames}) != periodicity length ({len(periodicity)})"
        )

    # Build a voiced-MIDI array; unvoiced frames get midi = -1
    midi = np.full(n_frames, -1, dtype=np.int32)
    for i in range(n_frames):
        if periodicity[i] >= periodicity_threshold and f0[i] > 0:
            raw_midi = 12.0 * np.log2(f0[i] / 440.0) + 69.0
            rounded = int(np.round(raw_midi))
            if _MIDI_MIN <= rounded <= _MIDI_MAX:
                midi[i] = rounded

    # Group consecutive frames with the same MIDI pitch into notes
    notes: list[Note] = []
    i = 0
    while i < n_frames:
        if midi[i] < 0:
            i += 1
            continue

        current_pitch = midi[i]
        start = i
        j = i + 1
        while j < n_frames and midi[j] == current_pitch:
            j += 1

        onset_sec = start * hop_sec
        duration_sec = (j - start) * hop_sec

        if duration_sec >= min_note_dur:
            notes.append(
                Note(
                    pitch=int(current_pitch),
                    onset=round(onset_sec, 4),
                    duration=round(duration_sec, 4),
                )
            )

        i = j

    logger.info("f0_to_notes: %d notes from %d frames", len(notes), n_frames)
    return notes
