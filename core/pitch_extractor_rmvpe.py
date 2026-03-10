"""RMVPE-based F0 pitch extraction.

Uses RMVPE (Robust Model for Vocal Pitch Estimation) from InterSpeech2023.
UNet + BiGRU architecture trained on vocal pitch, resistant to subharmonics.

Requires: pretrained_models/rmvpe.pt (172MB)
"""

import logging
from pathlib import Path

import librosa
import numpy as np
from scipy.ndimage import median_filter

from .types import F0Contour

logger = logging.getLogger(__name__)

# Lazy singleton to avoid reloading model on every call
_model = None
_model_device = None

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent / "models" / "rmvpe.pt"


def _get_model(device: str):
    """Get or create the RMVPE inference model (singleton)."""
    global _model, _model_device
    if _model is None or _model_device != device:
        from .rmvpe_model import RMVPE

        model_path = _DEFAULT_MODEL_PATH
        if not model_path.exists():
            raise FileNotFoundError(
                f"RMVPE model not found at {model_path}. "
                "Download rmvpe.pt to pretrained_models/"
            )
        _model = RMVPE(str(model_path), is_half=False, device=device)
        _model_device = device
    return _model


def extract_f0(
    audio: np.ndarray,
    sr: int,
    step_size_ms: int = 10,
    threshold: float = 0.03,
) -> F0Contour:
    """Extract fundamental frequency contour using RMVPE.

    Args:
        audio: 1-D mono audio array (float32).
        sr: Sample rate of audio.
        step_size_ms: Ignored (RMVPE fixed at 10ms), kept for API compat.
        threshold: Voiced/unvoiced threshold (default 0.03).

    Returns:
        F0Contour with times, frequencies (Hz), and confidence arrays.
    """
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info(
        "Running RMVPE: sr=%d, device=%s, %.1fs audio",
        sr, device, len(audio) / sr,
    )

    model = _get_model(device)

    # RMVPE requires 16kHz input
    if sr != 16000:
        audio_16k = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    else:
        audio_16k = audio

    # Run inference
    f0 = model.infer_from_audio(audio_16k, thred=threshold)

    # Median filter for pitch stabilization (voiced frames only)
    voiced_mask = f0 > 0
    if np.sum(voiced_mask) > 3:
        f0_filtered = median_filter(f0, size=3)
        f0 = np.where(voiced_mask, f0_filtered, 0.0)

    # RMVPE hop = 160 samples at 16kHz = 10ms
    times = np.arange(len(f0)) * 10.0 / 1000.0

    # Binary confidence from voiced/unvoiced
    confidence = np.where(f0 > 0, 1.0, 0.0).astype(np.float32)

    voiced_count = int(np.sum(f0 > 0))
    logger.info(
        "RMVPE extracted: %d frames, %d voiced (%.1f%%)",
        len(f0), voiced_count,
        100.0 * voiced_count / max(len(f0), 1),
    )

    return F0Contour(times=times, frequencies=f0.astype(np.float32), confidence=confidence)
