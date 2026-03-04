"""SOME (Singing-Oriented MIDI Extractor) note extraction.

Replaces CREPE F0 + note_segmenter with end-to-end singing-to-MIDI.
SOME is trained specifically for singing voice, handling subharmonics
and note boundaries natively.

Self-contained: takes audio array, returns List[Note]. No reference data.
"""

import logging
import sys
import types
from collections import OrderedDict
from pathlib import Path
from typing import List

import librosa
import numpy as np
import torch

from .types import Note

logger = logging.getLogger(__name__)

# Paths
_PROJECT_ROOT = Path(__file__).parent.parent
_SOME_ROOT = _PROJECT_ROOT / "pretrained_models" / "SOME"
_SOME_WEIGHTS_DIR = (
    _PROJECT_ROOT / "pretrained_models" / "SOME_weights" / "0119_continuous256_5spk"
)
_SOME_CKPT = _SOME_WEIGHTS_DIR / "model_ckpt_steps_100000_simplified.ckpt"
_SOME_CONFIG = _SOME_WEIGHTS_DIR / "config.yaml"

# Singleton model cache
_model_cache = {}


def _install_shims():
    """Install minimal shims to bypass lightning/fairseq dependencies.

    Must be called BEFORE any SOME module is imported. Provides fake
    modules for training_utils (lightning), config_utils, binarizer_utils
    (parselmouth), and contentvec (fairseq).
    """
    some_path = str(_SOME_ROOT)
    if some_path not in sys.path:
        sys.path.insert(0, some_path)

    # training_utils needs get_latest_checkpoint_path
    training_shim = types.ModuleType("utils.training_utils")
    training_shim.__file__ = str(_SOME_ROOT / "utils" / "training_utils.py")
    training_shim.get_latest_checkpoint_path = lambda *a, **kw: None
    sys.modules["utils.training_utils"] = training_shim

    # config_utils needs print_config
    config_shim = types.ModuleType("utils.config_utils")
    config_shim.__file__ = str(_SOME_ROOT / "utils" / "config_utils.py")
    config_shim.print_config = lambda *a, **kw: None
    sys.modules["utils.config_utils"] = config_shim

    # binarizer_utils needs get_pitch_parselmouth
    binarizer_shim = types.ModuleType("utils.binarizer_utils")
    binarizer_shim.__file__ = str(_SOME_ROOT / "utils" / "binarizer_utils.py")
    binarizer_shim.get_pitch_parselmouth = lambda *a, **kw: (None, None)
    sys.modules["utils.binarizer_utils"] = binarizer_shim

    # contentvec needs fairseq
    contentvec_shim = types.ModuleType("modules.contentvec")
    contentvec_shim.__file__ = str(_SOME_ROOT / "modules" / "contentvec" / "__init__.py")
    sys.modules["modules.contentvec"] = contentvec_shim


def _get_model():
    """Load SOME model (cached singleton)."""
    if "model" in _model_cache:
        return _model_cache["model"], _model_cache["config"]

    import yaml

    _install_shims()

    with open(_SOME_CONFIG, "r", encoding="utf8") as f:
        config = yaml.safe_load(f)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Loading SOME model on %s...", device)

    from modules.model.Gmidi_conform import midi_conforms

    model = midi_conforms(config=config).eval().to(device)

    state_dict = torch.load(_SOME_CKPT, map_location=device, weights_only=False)[
        "state_dict"
    ]
    state_dict = OrderedDict(
        {k[len("model."):]: v for k, v in state_dict.items() if k.startswith("model.")}
    )
    model.load_state_dict(state_dict, strict=True)

    from modules.rmvpe.spec import MelSpectrogram

    mel_spec = MelSpectrogram(
        n_mel_channels=config["units_dim"],
        sampling_rate=config["audio_sample_rate"],
        win_length=config["win_size"],
        hop_length=config["hop_size"],
        mel_fmin=config["fmin"],
        mel_fmax=config["fmax"],
    ).to(device)

    _model_cache["model"] = model
    _model_cache["mel_spec"] = mel_spec
    _model_cache["config"] = config
    _model_cache["device"] = device

    n_params = sum(p.numel() for p in model.parameters())
    logger.info("SOME model loaded: %.1fM params", n_params / 1e6)

    return model, config


def extract_notes_some(
    audio: np.ndarray,
    sr: int,
) -> List[Note]:
    """Extract notes from audio using SOME end-to-end model.

    Args:
        audio: Mono audio array (float32).
        sr: Sample rate (will be resampled to 44100 if needed).

    Returns:
        List of Note objects with pitch, onset, duration.
    """
    model, config = _get_model()
    mel_spec = _model_cache["mel_spec"]
    device = _model_cache["device"]

    target_sr = config["audio_sample_rate"]  # 44100
    if sr != target_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)

    # Slice audio by silence boundaries
    from utils.slicer2 import Slicer
    slicer = Slicer(sr=target_sr, max_sil_kept=1000)
    chunks = slicer.slice(audio)
    logger.info("SOME: %d audio chunks", len(chunks))

    from utils.infer_utils import (
        decode_bounds_to_alignment,
        decode_gaussian_blurred_probs,
        decode_note_sequence,
    )

    timestep = config["hop_size"] / target_sr
    midi_min = config["midi_min"]
    midi_max = config["midi_max"]
    midi_deviation = config["midi_prob_deviation"]
    rest_threshold = config["rest_threshold"]

    notes = []

    for chunk in chunks:
        chunk_wave = chunk["waveform"]
        offset = chunk["offset"]

        wav_tensor = torch.from_numpy(chunk_wave).unsqueeze(0).to(device)
        units = mel_spec(wav_tensor).transpose(1, 2)
        pitch = torch.zeros(units.shape[:2], dtype=torch.float32, device=device)
        masks = torch.ones_like(pitch, dtype=torch.bool)

        with torch.no_grad():
            probs, bounds = model(x=units, f0=pitch, mask=masks, sig=True)

        probs_masked = probs * masks[..., None]
        bounds_masked = bounds * masks

        unit2note = decode_bounds_to_alignment(bounds_masked) * masks
        midi_pred, rest_pred = decode_gaussian_blurred_probs(
            probs_masked,
            vmin=midi_min,
            vmax=midi_max,
            deviation=midi_deviation,
            threshold=rest_threshold,
        )
        note_midi, note_dur, note_mask = decode_note_sequence(
            unit2note, midi_pred, ~rest_pred & masks
        )
        note_rest = ~note_mask

        note_midi_np = note_midi.squeeze(0).cpu().numpy()
        note_dur_np = note_dur.squeeze(0).cpu().numpy() * timestep
        note_rest_np = note_rest.squeeze(0).cpu().numpy()

        current_time = offset
        for i in range(len(note_midi_np)):
            if not note_rest_np[i]:
                p = int(round(note_midi_np[i]))
                p = max(0, min(127, p))
                dur = float(note_dur_np[i])
                if dur > 0.03 and 36 <= p <= 96:
                    notes.append(Note(
                        pitch=p,
                        onset=round(current_time, 4),
                        duration=round(dur, 4),
                        velocity=80,
                    ))
            current_time += note_dur_np[i]

    notes.sort(key=lambda n: n.onset)

    if notes:
        pitches = [n.pitch for n in notes]
        logger.info(
            "SOME extracted %d notes: pitch %d-%d (mean=%.1f)",
            len(notes), min(pitches), max(pitches), np.mean(pitches),
        )
    else:
        logger.warning("SOME extracted 0 notes")

    return notes
