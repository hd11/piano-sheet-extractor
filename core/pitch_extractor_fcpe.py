"""FCPE-based F0 pitch extraction.

Uses torchfcpe (Conformer-based) for vocal pitch tracking.
FCPE is context-aware unlike CREPE's single-frame CNN,
making it inherently more resistant to subharmonic locking.
"""

import logging

import librosa
import numpy as np
import torch

from .types import F0Contour

logger = logging.getLogger(__name__)


def extract_f0_fcpe(
    audio: np.ndarray,
    sr: int,
    step_size_ms: int = 10,
    confidence_threshold: float = 0.006,
) -> F0Contour:
    """Extract fundamental frequency contour using FCPE.

    Args:
        audio: 1-D mono audio array (float32).
        sr: Sample rate of audio.
        step_size_ms: Hop size in milliseconds (default 10ms = 100 fps).
        confidence_threshold: Frames below this threshold are zeroed.

    Returns:
        F0Contour with times, frequencies (Hz), and confidence arrays.
    """
    import torchfcpe

    device = "cuda" if torch.cuda.is_available() else "cpu"

    # FCPE requires 16kHz input
    target_sr = 16000
    if sr != target_sr:
        audio_16k = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
    else:
        audio_16k = audio

    logger.info(
        "Running FCPE: sr=%d->%d, hop=%dms, device=%s, %.1fs audio",
        sr,
        target_sr,
        step_size_ms,
        device,
        len(audio) / sr,
    )

    model = torchfcpe.spawn_bundled_infer_model(device)

    audio_tensor = torch.from_numpy(audio_16k).unsqueeze(0).unsqueeze(-1).float().to(device)

    # Run FCPE inference
    f0_tensor = model.infer(
        audio_tensor,
        sr=target_sr,
        decoder_mode="local_argmax",
        threshold=confidence_threshold,
        f0_min=50.0,
        f0_max=1100.0,
        interp_uv=False,
    )

    pitch = f0_tensor.squeeze().cpu().numpy()

    # Generate confidence: FCPE doesn't return confidence directly,
    # use voiced/unvoiced as binary confidence (1.0 if voiced, 0.0 if not)
    confidence = (pitch > 0).astype(np.float32)

    logger.info(
        "FCPE raw: %d frames, voiced=%.1f%%",
        len(pitch),
        100.0 * np.mean(pitch > 0),
    )

    # Generate time array matching FCPE's hop size (10ms at 16kHz)
    times = np.arange(len(pitch)) * step_size_ms / 1000.0

    voiced_count = int(np.sum(pitch > 0))
    logger.info(
        "F0 extracted: %d frames, %d voiced (%.1f%%)",
        len(pitch),
        voiced_count,
        100.0 * voiced_count / max(len(pitch), 1),
    )

    return F0Contour(times=times, frequencies=pitch, confidence=confidence)
