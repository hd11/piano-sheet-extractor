"""FCPE-based F0 pitch extraction.

Uses torchfcpe (Conformer-based) for robust vocal pitch tracking.
FCPE is context-aware unlike CREPE's single-frame CNN,
making it inherently more resistant to subharmonic locking.

pip install torchfcpe  (bundled 40MB model, no extra download needed)
"""

import logging

import numpy as np
import torch
from scipy.ndimage import median_filter

from .types import F0Contour

logger = logging.getLogger(__name__)

# Lazy singleton to avoid reloading model on every call
_model = None
_model_device = None


def _get_model(device: str):
    """Get or create the FCPE inference model (singleton)."""
    global _model, _model_device
    if _model is None or _model_device != device:
        from torchfcpe import spawn_bundled_infer_model

        _model = spawn_bundled_infer_model(device=device)
        _model_device = device
        logger.info("FCPE model loaded on %s", device)
    return _model


def extract_f0(
    audio: np.ndarray,
    sr: int,
    step_size_ms: int = 10,
    threshold: float = 0.006,
) -> F0Contour:
    """Extract fundamental frequency contour using FCPE.

    Args:
        audio: 1-D mono audio array (float32).
        sr: Sample rate of audio.
        step_size_ms: Ignored (FCPE fixed at 10ms), kept for API compat.
        threshold: Voiced/unvoiced threshold (default 0.006).

    Returns:
        F0Contour with times, frequencies (Hz), and confidence arrays.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info(
        "Running FCPE: sr=%d, device=%s, %.1fs audio",
        sr, device, len(audio) / sr,
    )

    model = _get_model(device)

    # FCPE accepts any SR; resamples internally to 16kHz
    # Input shape: (batch, n_samples) per official unit test
    wav_tensor = torch.from_numpy(audio).float().unsqueeze(0)

    with torch.no_grad():
        f0_tensor = model.infer(
            wav_tensor,
            sr=sr,
            decoder_mode="local_argmax",
            threshold=threshold,
            interp_uv=False,  # 0.0 for unvoiced frames
        )

    # f0_tensor shape: (1, n_frames, 1) -> (n_frames,)
    pitch = f0_tensor.squeeze().cpu().numpy()

    # Median filter for pitch stabilization (same as CREPE pipeline)
    # Only filter voiced frames to avoid spreading zeros
    voiced_mask = pitch > 0
    if np.sum(voiced_mask) > 3:
        pitch_filtered = median_filter(pitch, size=3)
        # Preserve unvoiced regions
        pitch = np.where(voiced_mask, pitch_filtered, 0.0)

    # FCPE hop = 160 samples at 16kHz = 10ms
    times = np.arange(len(pitch)) * 10.0 / 1000.0

    # Binary confidence from voiced/unvoiced
    confidence = np.where(pitch > 0, 1.0, 0.0).astype(np.float32)

    voiced_count = int(np.sum(pitch > 0))
    logger.info(
        "FCPE extracted: %d frames, %d voiced (%.1f%%)",
        len(pitch), voiced_count,
        100.0 * voiced_count / max(len(pitch), 1),
    )

    return F0Contour(times=times, frequencies=pitch, confidence=confidence)
