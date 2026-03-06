"""End-to-end melody extraction pipeline.

Single entry point: extract_melody(mp3_path) -> List[Note]
No reference data enters this module. MP3 is the only input.

Pipeline modes:
  crepe:  MP3 -> Demucs -> CREPE F0  -> note_segmenter -> postprocess -> MusicXML
  fcpe:   MP3 -> Demucs -> FCPE F0   -> note_segmenter -> postprocess -> MusicXML
  rmvpe:  MP3 -> Demucs -> RMVPE F0  -> note_segmenter -> postprocess -> MusicXML
  onset:  MP3 -> Demucs -> FCPE F0   -> onset_segmenter (syllable-based) -> postprocess -> MusicXML
  bp:     MP3 -> Demucs -> Basic Pitch + CQT octave correction -> postprocess -> MusicXML
"""

import logging
from pathlib import Path
from typing import List, Optional

import librosa
import numpy as np

from .musicxml_writer import save_musicxml
from .note_extractor_bp import extract_notes_bp
from .note_segmenter import segment_notes, segment_notes_quantized, segment_notes_onset, segment_notes_hybrid
from .pitch_extractor import extract_f0 as extract_f0_crepe
from .pitch_extractor_ensemble import extract_f0_ensemble
from .pitch_extractor_fcpe import extract_f0 as extract_f0_fcpe
from .pitch_extractor_rmvpe import extract_f0 as extract_f0_rmvpe
from .postprocess import postprocess_notes
from .types import Note
from .vocal_separator import separate_vocals

logger = logging.getLogger(__name__)


def extract_melody(
    mp3_path: Path,
    cache_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    mode: str = "crepe",
) -> List[Note]:
    """Extract vocal melody from an MP3 file.

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for caching vocals. Defaults to mp3_path.parent/cache.
        output_path: If provided, saves MusicXML to this path.
        mode: "crepe" (default), "fcpe" for FCPE, "bp" for Basic Pitch + CQT.

    Returns:
        List of Note objects representing the extracted melody.
    """
    mp3_path = Path(mp3_path)
    if cache_dir is None:
        cache_dir = mp3_path.parent / "cache"

    logger.info("=== Pipeline start: %s (mode=%s) ===", mp3_path.name, mode)

    # Step 1: Vocal separation
    logger.info("Step 1: Vocal separation (Demucs)")
    vocals, sr = separate_vocals(mp3_path, cache_dir)

    # Step 2: Estimate BPM and beat positions from original mix
    # (mix has drums/bass for clearer beat tracking than vocals-only)
    mix_22k, _ = librosa.load(str(mp3_path), sr=22050, duration=300)
    bpm = _estimate_bpm_from_audio(mix_22k, 22050)

    # Beat positions from mix for onset snapping
    _, beat_frames = librosa.beat.beat_track(y=mix_22k, sr=22050)
    beat_times = librosa.frames_to_time(beat_frames, sr=22050)

    vocals_22k = librosa.resample(vocals, orig_sr=sr, target_sr=22050)

    # Step 3: Note extraction
    if mode == "bp":
        logger.info("Step 3: Note extraction (Basic Pitch + CQT)")
        notes = extract_notes_bp(vocals, sr)
    elif mode == "fcpe":
        logger.info("Step 3: Pitch extraction (FCPE)")
        contour = extract_f0_fcpe(vocals, sr)
        logger.info("Step 4: Note segmentation")
        notes = segment_notes(contour)
    elif mode == "rmvpe":
        logger.info("Step 3: Pitch extraction (RMVPE)")
        contour = extract_f0_rmvpe(vocals, sr)
        logger.info("Step 4: Note segmentation")
        notes = segment_notes(contour)
    elif mode == "hybrid":
        logger.info("Step 3: Pitch extraction (FCPE) + hybrid segmentation")
        contour = extract_f0_fcpe(vocals, sr)
        logger.info("Step 4: Note segmentation (FCPE pitch + onset boundaries)")
        notes = segment_notes_hybrid(contour, vocals_22k, 22050)
    elif mode == "onset":
        logger.info("Step 3: Pitch extraction (FCPE) + onset-based segmentation")
        contour = extract_f0_fcpe(vocals, sr)
        logger.info("Step 4: Note segmentation (syllable onset)")
        notes = segment_notes_onset(contour, vocals_22k, 22050)
    elif mode == "ensemble":
        logger.info("Step 3: Pitch extraction (FCPE+RMVPE ensemble)")
        contour = extract_f0_ensemble(vocals, sr)
        logger.info("Step 4: Note segmentation")
        notes = segment_notes(contour)
    else:
        logger.info("Step 3: Pitch extraction (CREPE)")
        contour = extract_f0_crepe(vocals, sr)
        logger.info("Step 4: Note segmentation")
        notes = segment_notes(contour)

    # Postprocessing (self-contained, no reference)
    logger.info("Postprocessing")
    notes = postprocess_notes(notes, audio=vocals_22k, sr=22050, bpm=bpm, beat_times=beat_times)

    logger.info("Pipeline complete: %d notes extracted", len(notes))

    # Save MusicXML if output path given
    if output_path is not None and notes:
        title = mp3_path.stem
        save_musicxml(notes, output_path, title=title, bpm=bpm)
        logger.info("Saved: %s (bpm=%.0f)", output_path, bpm)

    return notes


def _estimate_bpm_from_audio(y: np.ndarray, sr: int) -> float:
    """Estimate tempo from audio array using librosa beat tracker.

    Includes tempo octave disambiguation: if librosa returns a tempo
    below 100 BPM, checks whether double tempo has comparable beat
    strength via onset autocorrelation.

    Args:
        y: Audio array (mono, typically vocals at 22050 Hz).
        sr: Sample rate.
    """
    try:
        # Use first 60 seconds
        max_samples = sr * 60
        if len(y) > max_samples:
            y = y[:max_samples]
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])
        logger.info("Raw librosa BPM: %.1f", bpm)

        # Tempo octave disambiguation
        # librosa often returns half-tempo or 2/3-tempo for fast songs
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        ac = librosa.autocorrelate(onset_env, max_size=len(onset_env))
        hop_length = 512

        # Check 2:1 ratio (half-tempo) when BPM < 100
        if bpm < 100:
            bpm_lag = int(round(sr / (bpm / 60.0 * hop_length)))
            double_lag = bpm_lag // 2

            if double_lag > 0 and double_lag < len(ac) and bpm_lag < len(ac):
                ratio = ac[double_lag] / ac[bpm_lag] if ac[bpm_lag] > 0 else 0
                logger.info(
                    "Tempo 2:1 check: ac[%d]=%.2f (2x) vs ac[%d]=%.2f (1x), ratio=%.2f",
                    double_lag, ac[double_lag], bpm_lag, ac[bpm_lag], ratio,
                )
                if ratio > 0.8:
                    logger.info("Doubling tempo: %.0f -> %.0f", bpm, bpm * 2)
                    bpm *= 2

        # Check 3:2 ratio (2/3-tempo) when BPM is 100-140
        # e.g., librosa returns 123 when true tempo is ~184
        if 100 <= bpm <= 140:
            bpm_lag = int(round(sr / (bpm / 60.0 * hop_length)))
            triple_lag = int(round(bpm_lag * 2 / 3))  # lag for 3/2 * bpm

            if triple_lag > 0 and triple_lag < len(ac) and bpm_lag < len(ac):
                ratio = ac[triple_lag] / ac[bpm_lag] if ac[bpm_lag] > 0 else 0
                logger.info(
                    "Tempo 3:2 check: ac[%d]=%.2f (1.5x) vs ac[%d]=%.2f (1x), ratio=%.2f",
                    triple_lag, ac[triple_lag], bpm_lag, ac[bpm_lag], ratio,
                )
                if ratio > 0.75:
                    new_bpm = bpm * 1.5
                    if new_bpm <= 200:
                        logger.info("3:2 tempo correction: %.0f -> %.0f", bpm, new_bpm)
                        bpm = new_bpm

        bpm = max(60.0, min(200.0, round(bpm)))
        logger.info("Final BPM: %.0f", bpm)
        return bpm
    except Exception as e:
        logger.warning("BPM estimation failed: %s, using 120", e)
        return 120.0
