"""CREPE-based F0 pitch extraction.

Uses torchcrepe with Viterbi decoding for smooth vocal pitch tracking.
"""

import logging

import numpy as np
import torch
import torchcrepe
from scipy.ndimage import median_filter

from .types import F0Contour

logger = logging.getLogger(__name__)


def extract_f0(
    audio: np.ndarray,
    sr: int,
    step_size_ms: int = 10,
    confidence_threshold: float = 0.5,
) -> F0Contour:
    """Extract fundamental frequency contour using CREPE.

    Args:
        audio: 1-D mono audio array (float32).
        sr: Sample rate of audio.
        step_size_ms: Hop size in milliseconds (default 10ms = 100 fps).
        confidence_threshold: Frames below this periodicity are zeroed.

    Returns:
        F0Contour with times, frequencies (Hz), and confidence arrays.
    """
    hop_length = int(sr * step_size_ms / 1000)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    audio_tensor = torch.from_numpy(audio).unsqueeze(0).float()

    logger.info(
        "Running CREPE: sr=%d, hop=%d (%dms), device=%s, %.1fs audio",
        sr,
        hop_length,
        step_size_ms,
        device,
        len(audio) / sr,
    )

    pitch, periodicity = torchcrepe.predict(
        audio_tensor,
        sr,
        hop_length,
        fmin=50.0,
        fmax=1100.0,
        model="full",
        decoder=torchcrepe.decode.viterbi,
        return_periodicity=True,
        batch_size=2048,
        device=device,
    )

    pitch = pitch.squeeze(0).cpu().numpy()
    periodicity = periodicity.squeeze(0).cpu().numpy()

    logger.info(
        "CREPE raw: %d frames, voiced=%.1f%% (conf>%.1f)",
        len(pitch),
        100.0 * np.mean(periodicity > confidence_threshold),
        confidence_threshold,
    )

    # Median filter for pitch smoothing (50ms window at 10ms step)
    pitch = median_filter(pitch, size=5)

    # Zero out low-confidence frames
    pitch[periodicity < confidence_threshold] = 0.0

    times = np.arange(len(pitch)) * step_size_ms / 1000.0

    voiced_count = int(np.sum(pitch > 0))
    logger.info(
        "F0 extracted: %d frames, %d voiced (%.1f%%)",
        len(pitch),
        voiced_count,
        100.0 * voiced_count / max(len(pitch), 1),
    )

    return F0Contour(times=times, frequencies=pitch, confidence=periodicity)
