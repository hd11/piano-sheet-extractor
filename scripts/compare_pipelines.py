#!/usr/bin/env python3
"""Fair comparison of BP, CREPE, pYIN pipelines with consistent post-processing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_separator import separate_vocals
from core.vocal_melody_extractor import (
    _run_bp_pipeline, _crepe_pipeline, _pyin_pipeline,
    _per_note_octave_correction, _compute_cqt_salience,
    _determine_octave_shift, _crepe_q75_pitch_refinement,
)
from core.reference_extractor import extract_reference_melody
from core.postprocess import apply_sectional_time_offset
from core.comparator import compare_melodies
from core.types import Note
import numpy as np

test_dir = Path("test")
mp3 = test_dir / "꿈의 버스.mp3"
mxl = test_dir / "꿈의 버스.mxl"
cache_dir = test_dir / "cache"

ref_notes = [n for n in extract_reference_melody(mxl) if n.duration > 0]

# Demucs는 한 번만 실행
vocals, sr = separate_vocals(mp3, cache_dir)
vocals_f32 = vocals.astype(np.float32)

# 공통 후처리: CQT salience (BP, CREPE, pYIN 모두 동일하게 적용)
sal_w, midi_bins, times_cqt = _compute_cqt_salience(vocals_f32, sr)

_VOCAL_MIDI_LOW = 62   # D4
_VOCAL_MIDI_HIGH = 86  # D6


def post_process(notes, sal_w, midi_bins, times_cqt):
    """Apply per-note octave correction (self-referencing)."""
    if not notes:
        return notes
    notes = _per_note_octave_correction(notes, sal_w, midi_bins, times_cqt)
    return notes


def evaluate(notes, ref_notes, label):
    aligned = apply_sectional_time_offset(notes, ref_notes)
    m = compare_melodies(ref_notes, aligned)
    print(f"{label:<25} gen={len(notes):3d}  "
          f"pc_f1={m['pitch_class_f1']:.3f}  "
          f"mel_strict={m['melody_f1_strict']:.3f}  "
          f"mel_lenient={m['melody_f1_lenient']:.3f}  "
          f"onset_f1={m['onset_f1']:.3f}  "
          f"prec={m['pitch_class_precision']:.3f}  "
          f"rec={m['pitch_class_recall']:.3f}")


print("=== Pipeline Comparison (꿈의 버스, same Demucs + same post-processing) ===\n")

# BP: 현재 파이프라인과 동일
print("[1] Running BP pipeline...")
bp_raw = _run_bp_pipeline(vocals_f32, sr)
shift = _determine_octave_shift(bp_raw, sal_w, midi_bins, times_cqt)
bp_shifted = [Note(pitch=n.pitch+shift, onset=n.onset, duration=n.duration, velocity=n.velocity)
              for n in bp_raw if _VOCAL_MIDI_LOW-3 <= n.pitch+shift <= _VOCAL_MIDI_HIGH+5]
bp_notes = post_process(bp_shifted, sal_w, midi_bins, times_cqt)
bp_notes_q75 = _crepe_q75_pitch_refinement(bp_notes, vocals_f32, sr)
evaluate(bp_notes, ref_notes, "BP (no CREPE Q75)")
evaluate(bp_notes_q75, ref_notes, "BP + CREPE Q75 (v20)")

# CREPE: 동일한 post-processing 적용
print("\n[2] Running CREPE pipeline...")
crepe_raw = _crepe_pipeline(vocals_f32, sr)  # includes windowed CQT octave correction
crepe_notes = post_process(crepe_raw, sal_w, midi_bins, times_cqt)
evaluate(crepe_raw, ref_notes, "CREPE (pipeline only)")
evaluate(crepe_notes, ref_notes, "CREPE + per-note oct")
crepe_q75 = _crepe_q75_pitch_refinement(crepe_notes, vocals_f32, sr)
evaluate(crepe_q75, ref_notes, "CREPE + per-note + Q75")

# pYIN: 동일한 post-processing 적용
print("\n[3] Running pYIN pipeline...")
pyin_raw = _pyin_pipeline(vocals_f32, sr)  # includes windowed CQT octave correction
pyin_notes = post_process(pyin_raw, sal_w, midi_bins, times_cqt)
evaluate(pyin_raw, ref_notes, "pYIN (pipeline only)")
evaluate(pyin_notes, ref_notes, "pYIN + per-note oct")
pyin_q75 = _crepe_q75_pitch_refinement(pyin_notes, vocals_f32, sr)
evaluate(pyin_q75, ref_notes, "pYIN + per-note + Q75")
