"""Vocal separation from MP3 using Demucs htdemucs_ft model.

Separates vocals from an MP3 file, returning mono audio at 44100 Hz.
Uses MD5-based caching to avoid reprocessing identical files.
Handles Korean filenames via UUID-based temp file workaround.
"""

import hashlib
import logging
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple

import librosa
import numpy as np
import torch

logger = logging.getLogger(__name__)

_model = None

VOCALS_CACHE_VERSION = "v1"
SAMPLE_RATE = 44100


def _trim_trailing_silence(
    vocals: np.ndarray,
    sr: int,
    frame_length: int = 2048,
    hop_length: int = 512,
    relative_threshold: float = 1e-4,
    buffer_seconds: float = 1.0,
    min_duration_seconds: float = 10.0,
) -> np.ndarray:
    """Trim trailing silence from a vocals array using energy envelope.

    Computes short-time RMS energy, finds the last frame above a threshold
    relative to the peak energy, adds a buffer, and trims the array.

    Args:
        vocals: 1-D mono float32 array at sample rate sr.
        sr: Sample rate in Hz.
        frame_length: RMS frame length in samples.
        hop_length: Hop length in samples.
        relative_threshold: Energy threshold as fraction of peak energy (-40 dB).
        buffer_seconds: Seconds to keep after the last active frame.
        min_duration_seconds: Skip trimming if result would be shorter than this.

    Returns:
        Trimmed (or original) vocals array.
    """
    original_dur = len(vocals) / sr

    rms = librosa.feature.rms(
        y=vocals, frame_length=frame_length, hop_length=hop_length
    )[0]

    peak_energy = float(rms.max())
    if peak_energy == 0.0:
        return vocals

    threshold = peak_energy * relative_threshold
    active_frames = np.where(rms > threshold)[0]

    if len(active_frames) == 0:
        return vocals

    last_active_frame = int(active_frames[-1])
    # Convert frame index to sample index, add buffer
    last_active_sample = last_active_frame * hop_length + frame_length
    buffer_samples = int(buffer_seconds * sr)
    trim_sample = last_active_sample + buffer_samples

    if trim_sample >= len(vocals):
        return vocals

    trimmed_dur = trim_sample / sr
    if trimmed_dur < min_duration_seconds:
        logger.warning(
            "Trailing silence trim skipped: result would be %.1fs (< %.1fs min)",
            trimmed_dur,
            min_duration_seconds,
        )
        return vocals

    logger.info(
        "Trimmed trailing silence: %.1fs -> %.1fs (removed %.1fs)",
        original_dur,
        trimmed_dur,
        original_dur - trimmed_dur,
    )
    return vocals[:trim_sample]


def _get_model():
    """Load htdemucs_ft model (singleton)."""
    global _model
    if _model is None:
        from demucs.pretrained import get_model

        logger.info("Loading htdemucs_ft model...")
        _model = get_model("htdemucs_ft")
        _model.eval()
        logger.info(
            "Model loaded. sources=%s, samplerate=%d",
            _model.sources,
            _model.samplerate,
        )
    return _model


def _is_ascii_safe(path: Path) -> bool:
    """Check if path contains only ASCII characters."""
    try:
        str(path).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def separate_vocals(
    mp3_path: Path,
    cache_dir: Optional[Path] = None,
) -> Tuple[np.ndarray, int]:
    """Separate vocals from an MP3 file using Demucs htdemucs_ft.

    Args:
        mp3_path: Path to the input MP3 file.
        cache_dir: Optional directory for caching results as .npz files.

    Returns:
        Tuple of (vocals, sample_rate) where vocals is a 1-D mono
        numpy array (float32) at 44100 Hz.
    """
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        raise FileNotFoundError(f"MP3 file not found: {mp3_path}")

    md5_hash = hashlib.md5(mp3_path.read_bytes()).hexdigest()
    cached_path: Optional[Path] = None

    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_path = cache_dir / f"{md5_hash}_vocals_{VOCALS_CACHE_VERSION}.npz"

        if cached_path.exists() and cached_path.stat().st_size > 0:
            logger.info("Cache HIT: %s -> %s", mp3_path.name, cached_path.name)
            data = np.load(cached_path)
            vocals_cached = _trim_trailing_silence(data["vocals"], int(data["sr"]))
            return vocals_cached, int(data["sr"])

        logger.info("Cache MISS: %s (hash=%s)", mp3_path.name, md5_hash)

    from demucs.audio import AudioFile

    if _is_ascii_safe(mp3_path):
        load_path = mp3_path
        tmp_dir = None
    else:
        tmp_dir = tempfile.mkdtemp(prefix="demucs_")
        safe_name = f"{uuid.uuid4().hex}.mp3"
        load_path = Path(tmp_dir) / safe_name
        shutil.copy2(mp3_path, load_path)
        logger.info("Korean filename workaround: %s -> %s", mp3_path.name, safe_name)

    try:
        wav = AudioFile(load_path).read(streams=0, samplerate=SAMPLE_RATE, channels=2)
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info(
        "Audio loaded: %s — %.1fs, shape=%s",
        mp3_path.name,
        wav.shape[-1] / SAMPLE_RATE,
        list(wav.shape),
    )

    model = _get_model()

    with torch.no_grad():
        from demucs.apply import apply_model

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Running Demucs on device=%s", device)
        sources = apply_model(model, wav[None], device=device, progress=False)

    vocals_idx = model.sources.index("vocals")
    vocals_stereo = sources[0, vocals_idx]
    vocals_mono = vocals_stereo.mean(dim=0)
    vocals_np = vocals_mono.numpy().astype(np.float32)

    logger.info(
        "Vocals extracted: %s — %.1fs, shape=%s",
        mp3_path.name,
        len(vocals_np) / SAMPLE_RATE,
        vocals_np.shape,
    )

    if cached_path is not None:
        np.savez_compressed(cached_path, vocals=vocals_np, sr=SAMPLE_RATE)
        logger.info(
            "Cached: %s (%.1f MB)",
            cached_path.name,
            cached_path.stat().st_size / 1e6,
        )

    vocals_np = _trim_trailing_silence(vocals_np, SAMPLE_RATE)
    return vocals_np, SAMPLE_RATE
