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

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Singleton model instance — loaded lazily on first call
_model = None

VOCALS_CACHE_VERSION = "v1"
SAMPLE_RATE = 44100


def _get_model():
    """Load htdemucs_ft model (singleton — cached after first call)."""
    global _model
    if _model is None:
        from demucs.pretrained import get_model

        logger.info("Loading htdemucs_ft model (first call, ~300MB)...")
        _model = get_model("htdemucs_ft")
        _model.eval()
        logger.info(
            "Model loaded. sources=%s, samplerate=%d", _model.sources, _model.samplerate
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
            If None, no caching is performed.

    Returns:
        Tuple of (vocals, sample_rate) where vocals is a 1-D mono
        numpy array (float32) at 44100 Hz.

    Raises:
        FileNotFoundError: If the MP3 file does not exist.
    """
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        raise FileNotFoundError(f"MP3 file not found: {mp3_path}")

    # --- MD5-based cache lookup ---
    md5_hash = hashlib.md5(mp3_path.read_bytes()).hexdigest()
    cached_path: Optional[Path] = None

    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_path = cache_dir / f"{md5_hash}_vocals_{VOCALS_CACHE_VERSION}.npz"

        if cached_path.exists() and cached_path.stat().st_size > 0:
            logger.info("Cache HIT: %s -> %s", mp3_path.name, cached_path.name)
            data = np.load(cached_path)
            return data["vocals"], int(data["sr"])

        logger.info("Cache MISS: %s (hash=%s)", mp3_path.name, md5_hash)

    # --- Load audio (Korean filename workaround) ---
    from demucs.audio import AudioFile

    if _is_ascii_safe(mp3_path):
        load_path = mp3_path
        tmp_dir = None
    else:
        # Non-ASCII path: copy to a UUID-named temp file
        tmp_dir = tempfile.mkdtemp(prefix="demucs_")
        safe_name = f"{uuid.uuid4().hex}.mp3"
        load_path = Path(tmp_dir) / safe_name
        shutil.copy2(mp3_path, load_path)
        logger.info("Korean filename workaround: %s -> %s", mp3_path.name, safe_name)

    try:
        wav = AudioFile(load_path).read(streams=0, samplerate=SAMPLE_RATE, channels=2)
    finally:
        # Clean up temp file
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info(
        "Audio loaded: %s — %.1fs, shape=%s",
        mp3_path.name,
        wav.shape[-1] / SAMPLE_RATE,
        list(wav.shape),
    )

    # --- Run Demucs separation ---
    model = _get_model()

    with torch.no_grad():
        from demucs.apply import apply_model

        # apply_model expects [batch, channels, samples], returns [batch, sources, channels, samples]
        sources = apply_model(model, wav[None], device="cpu", progress=False)

    # Extract vocals (index 3: ['drums', 'bass', 'other', 'vocals'])
    vocals_idx = model.sources.index("vocals")
    vocals_stereo = sources[0, vocals_idx]  # [channels, samples]

    # Stereo -> mono
    vocals_mono = vocals_stereo.mean(dim=0)  # [samples]

    # Convert to numpy float32
    vocals_np = vocals_mono.numpy().astype(np.float32)

    logger.info(
        "Vocals extracted: %s — %.1fs, shape=%s",
        mp3_path.name,
        len(vocals_np) / SAMPLE_RATE,
        vocals_np.shape,
    )

    # --- Save to cache ---
    if cached_path is not None:
        np.savez_compressed(cached_path, vocals=vocals_np, sr=SAMPLE_RATE)
        logger.info(
            "Cached: %s (%.1f MB)", cached_path.name, cached_path.stat().st_size / 1e6
        )

    return vocals_np, SAMPLE_RATE
