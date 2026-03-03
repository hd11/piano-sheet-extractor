"""End-to-end melody extraction pipeline.

Single entry point: extract_melody(mp3_path) -> List[Note]
No reference data enters this module. MP3 is the only input.

Pipeline:
  MP3 -> vocal_separator (Demucs) -> pitch_extractor (CREPE)
      -> note_segmenter -> postprocess -> musicxml_writer -> output.musicxml
"""

import logging
from pathlib import Path
from typing import List, Optional

import librosa
import numpy as np

from .musicxml_writer import save_musicxml
from .note_segmenter import segment_notes
from .pitch_extractor import extract_f0
from .postprocess import postprocess_notes
from .types import Note
from .vocal_separator import separate_vocals

logger = logging.getLogger(__name__)


def extract_melody(
    mp3_path: Path,
    cache_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> List[Note]:
    """Extract vocal melody from an MP3 file.

    Runs the full pipeline: vocal separation -> pitch extraction ->
    note segmentation -> postprocessing. Optionally saves MusicXML output.

    Args:
        mp3_path: Path to input MP3 file.
        cache_dir: Directory for caching vocals. Defaults to mp3_path.parent/cache.
        output_path: If provided, saves MusicXML to this path.

    Returns:
        List of Note objects representing the extracted melody.
    """
    mp3_path = Path(mp3_path)
    if cache_dir is None:
        cache_dir = mp3_path.parent / "cache"

    logger.info("=== Pipeline start: %s ===", mp3_path.name)

    # Step 0: Estimate BPM early (used by postprocess and musicxml_writer)
    bpm = _estimate_bpm(mp3_path)

    # Step 1: Vocal separation
    logger.info("Step 1: Vocal separation (Demucs)")
    vocals, sr = separate_vocals(mp3_path, cache_dir)

    # Step 2: Pitch extraction (CREPE)
    logger.info("Step 2: Pitch extraction (CREPE)")
    contour = extract_f0(vocals, sr)

    # Step 3: Note segmentation
    logger.info("Step 3: Note segmentation")
    notes = segment_notes(contour)

    # Step 4: Postprocessing (self-contained, no reference)
    # Pass original MP3 audio for beat-aligned onset snapping
    logger.info("Step 4: Postprocessing")
    mp3_audio, mp3_sr = librosa.load(str(mp3_path), sr=22050)
    notes = postprocess_notes(notes, audio=mp3_audio, sr=mp3_sr)

    logger.info("Pipeline complete: %d notes extracted", len(notes))

    # Step 5: Save MusicXML if output path given
    if output_path is not None and notes:
        title = mp3_path.stem
        save_musicxml(notes, output_path, title=title, bpm=bpm)
        logger.info("Saved: %s (bpm=%.0f)", output_path, bpm)

    return notes


def _estimate_bpm(mp3_path: Path) -> float:
    """Estimate tempo from audio using librosa beat tracker.

    Includes tempo octave disambiguation: if librosa returns a tempo
    below 100 BPM, checks whether double tempo has comparable beat
    strength via onset autocorrelation. This corrects the common
    half-tempo detection issue in fast songs.
    """
    try:
        y, sr = librosa.load(str(mp3_path), sr=22050, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])
        logger.info("Raw librosa BPM: %.1f", bpm)

        # Tempo octave disambiguation
        if bpm < 100:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            ac = librosa.autocorrelate(onset_env, max_size=len(onset_env))

            # hop_length=512 is librosa default for onset_strength
            hop_length = 512
            bpm_lag = int(round(sr / (bpm / 60.0 * hop_length)))
            double_lag = bpm_lag // 2

            if double_lag > 0 and double_lag < len(ac) and bpm_lag < len(ac):
                ratio = ac[double_lag] / ac[bpm_lag] if ac[bpm_lag] > 0 else 0
                logger.info(
                    "Tempo octave check: ac[%d]=%.2f (2x) vs ac[%d]=%.2f (1x), ratio=%.2f",
                    double_lag, ac[double_lag], bpm_lag, ac[bpm_lag], ratio,
                )
                if ratio > 0.8:  # 2x tempo at least 80% as strong
                    logger.info("Doubling tempo: %.0f -> %.0f", bpm, bpm * 2)
                    bpm *= 2

        bpm = max(60.0, min(200.0, round(bpm)))
        logger.info("Final BPM: %.0f", bpm)
        return bpm
    except Exception as e:
        logger.warning("BPM estimation failed: %s, using 120", e)
        return 120.0
