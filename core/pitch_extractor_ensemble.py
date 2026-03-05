"""Ensemble F0 extraction combining FCPE and RMVPE.

Frame-level fusion: when both extractors agree on pitch, confidence is boosted.
When they disagree, the extractor closer to the local context wins.
"""

import logging

import librosa
import numpy as np
from scipy.ndimage import median_filter

from .pitch_extractor_fcpe import extract_f0 as extract_f0_fcpe
from .pitch_extractor_rmvpe import extract_f0 as extract_f0_rmvpe
from .types import F0Contour

logger = logging.getLogger(__name__)


def extract_f0_ensemble(
    audio: np.ndarray,
    sr: int,
    agreement_tolerance_cents: float = 100.0,
) -> F0Contour:
    """Extract F0 by ensembling FCPE and RMVPE.

    Strategy per frame:
      - Both voiced & agree (within tolerance): average pitch, confidence=1.0
      - Both voiced & disagree: pick FCPE (better overall), confidence=0.7
      - One voiced: use that one, confidence=0.5
      - Neither voiced: unvoiced

    Args:
        audio: Mono audio array.
        sr: Sample rate.
        agreement_tolerance_cents: Max pitch difference (cents) to count as agreement.

    Returns:
        F0Contour with fused frequencies and confidence.
    """
    logger.info("Running ensemble: FCPE + RMVPE")

    contour_fcpe = extract_f0_fcpe(audio, sr)
    contour_rmvpe = extract_f0_rmvpe(audio, sr)

    # Align to same length (both are 10ms hop = 100fps)
    n = min(len(contour_fcpe.frequencies), len(contour_rmvpe.frequencies))
    f_fcpe = contour_fcpe.frequencies[:n]
    f_rmvpe = contour_rmvpe.frequencies[:n]

    fused_freq = np.zeros(n, dtype=np.float32)
    fused_conf = np.zeros(n, dtype=np.float32)

    voiced_fcpe = f_fcpe > 0
    voiced_rmvpe = f_rmvpe > 0
    both_voiced = voiced_fcpe & voiced_rmvpe
    only_fcpe = voiced_fcpe & ~voiced_rmvpe
    only_rmvpe = ~voiced_fcpe & voiced_rmvpe

    # Both voiced: check agreement
    if np.any(both_voiced):
        cents_diff = np.abs(1200.0 * np.log2(
            np.clip(f_fcpe[both_voiced], 1e-6, None) /
            np.clip(f_rmvpe[both_voiced], 1e-6, None)
        ))
        agree = cents_diff <= agreement_tolerance_cents
        disagree = ~agree

        # Agreement: average
        both_idx = np.where(both_voiced)[0]
        agree_idx = both_idx[agree]
        disagree_idx = both_idx[disagree]

        fused_freq[agree_idx] = (f_fcpe[agree_idx] + f_rmvpe[agree_idx]) / 2.0
        fused_conf[agree_idx] = 1.0

        # Disagreement: pick FCPE (better overall average)
        fused_freq[disagree_idx] = f_fcpe[disagree_idx]
        fused_conf[disagree_idx] = 0.7

    # Only one voiced
    fused_freq[only_fcpe] = f_fcpe[only_fcpe]
    fused_conf[only_fcpe] = 0.5

    fused_freq[only_rmvpe] = f_rmvpe[only_rmvpe]
    fused_conf[only_rmvpe] = 0.5

    # Median filter on voiced frames
    voiced_mask = fused_freq > 0
    if np.sum(voiced_mask) > 3:
        filtered = median_filter(fused_freq, size=3)
        fused_freq = np.where(voiced_mask, filtered, 0.0)

    times = np.arange(n) * 10.0 / 1000.0

    n_agree = int(np.sum(fused_conf == 1.0))
    n_disagree = int(np.sum(fused_conf == 0.7))
    n_single = int(np.sum(fused_conf == 0.5))
    n_voiced = int(np.sum(fused_freq > 0))
    logger.info(
        "Ensemble: %d frames, %d voiced (%.1f%%), agree=%d, disagree=%d, single=%d",
        n, n_voiced, 100.0 * n_voiced / max(n, 1),
        n_agree, n_disagree, n_single,
    )

    return F0Contour(times=times, frequencies=fused_freq, confidence=fused_conf)
