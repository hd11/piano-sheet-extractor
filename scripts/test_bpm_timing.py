#!/usr/bin/env python3
"""Diagnose BPM and timing accuracy — the likely cause of "unknown song" feeling.

If detected BPM differs from the actual musical tempo, EVERY note in the
MusicXML gets quantized to the wrong position. This could make a correctly-
pitched melody sound completely wrong.

Tests:
1. Compare detected BPM vs reference MXL BPM
2. Analyze note onset quantization errors
3. Test MusicXML output with different BPMs
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vocal_melody_extractor import extract_melody, detect_bpm
from core.vocal_separator import separate_vocals
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies
from core.postprocess import apply_sectional_time_offset
from core.musicxml_writer import _build_score
from core.types import Note

import librosa
import music21

TEST_MP3 = Path("test/꿈의 버스.mp3")
TEST_MXL = Path("test/꿈의 버스.mxl")
CACHE_DIR = Path("test/cache")


def get_ref_bpm(mxl_path: Path) -> float:
    """Extract BPM from reference MXL file."""
    score = music21.converter.parse(str(mxl_path))
    tempos = list(score.flat.getElementsByClass(music21.tempo.MetronomeMark))
    if tempos:
        return tempos[0].number
    return 120.0


def analyze_onset_quantization(notes: list[Note], bpm: float):
    """Analyze how well note onsets align with the beat grid."""
    sec_per_beat = 60.0 / bpm
    sec_per_16th = sec_per_beat / 4

    errors = []
    for n in notes:
        # Distance to nearest 16th note grid position
        grid_pos = round(n.onset / sec_per_16th) * sec_per_16th
        error_ms = abs(n.onset - grid_pos) * 1000
        errors.append(error_ms)

    errors = np.array(errors)
    return errors


def main():
    print("=" * 70)
    print("BPM AND TIMING DIAGNOSTIC")
    print("=" * 70)

    # Step 1: Get reference BPM
    ref_bpm = get_ref_bpm(TEST_MXL)
    print(f"\nReference MXL BPM: {ref_bpm}")

    # Step 2: Detect BPM from audio
    vocals, sr = separate_vocals(TEST_MP3, CACHE_DIR)
    vocals_f32 = vocals.astype(np.float32)
    detected_bpm = detect_bpm(vocals_f32, sr)
    print(f"Detected BPM:      {detected_bpm:.1f}")
    print(f"BPM ratio:         {detected_bpm / ref_bpm:.3f}")
    print(f"BPM error:         {abs(detected_bpm - ref_bpm):.1f} ({abs(detected_bpm - ref_bpm) / ref_bpm * 100:.1f}%)")

    # Also try librosa beat tracking on the original mix
    original, orig_sr = librosa.load(str(TEST_MP3), sr=22050)
    tempo_mix, _ = librosa.beat.beat_track(y=original, sr=22050)
    mix_bpm = float(np.atleast_1d(tempo_mix)[0])
    print(f"Mix BPM (librosa): {mix_bpm:.1f}")

    # Step 3: Extract melody
    gen_notes = extract_melody(TEST_MP3, cache_dir=CACHE_DIR)
    gen_notes = [n for n in gen_notes if n.duration > 0]
    ref_notes = [n for n in extract_reference_melody(TEST_MXL) if n.duration > 0]

    print(f"\nGenerated notes: {len(gen_notes)}")
    print(f"Reference notes: {len(ref_notes)}")

    # Step 4: Analyze onset quantization with different BPMs
    print(f"\n--- Onset quantization error (ms) ---")
    for bpm_label, bpm in [("Detected", detected_bpm), ("Reference", ref_bpm), ("Mix", mix_bpm)]:
        errors = analyze_onset_quantization(gen_notes, bpm)
        print(f"  {bpm_label:<10} (BPM={bpm:>6.1f}): mean={np.mean(errors):5.1f}ms, "
              f"median={np.median(errors):5.1f}ms, max={np.max(errors):5.1f}ms, "
              f"<25ms: {np.sum(errors < 25)/len(errors)*100:.0f}%, "
              f"<50ms: {np.sum(errors < 50)/len(errors)*100:.0f}%")

    # Step 5: Compare metrics with different BPMs (via MusicXML quantization)
    print(f"\n--- MusicXML output quality at different BPMs ---")
    print(f"(Simulating quantization effect on pitch alignment)")

    # The key question: does BPM affect how notes align after quantization?
    # When BPM is wrong, the quantized onset times are different,
    # which affects which reference notes they match with.
    for bpm_label, bpm in [
        ("Detected", detected_bpm),
        ("Reference", ref_bpm),
        ("Mix", mix_bpm),
        ("Detected/2", detected_bpm / 2),
        ("Detected*2", detected_bpm * 2),
    ]:
        # Build score at this BPM, extract the quantized notes
        try:
            score = _build_score(gen_notes, "test", bpm)
            # Extract notes from the score
            quantized_notes = []
            sec_per_q = 60.0 / bpm
            for element in score.flat.notes:
                if isinstance(element, music21.note.Note):
                    onset_sec = float(element.offset) * sec_per_q
                    dur_sec = float(element.quarterLength) * sec_per_q
                    quantized_notes.append(Note(
                        pitch=element.pitch.midi,
                        onset=onset_sec,
                        duration=dur_sec,
                        velocity=element.volume.velocity or 80,
                    ))

            if not quantized_notes:
                print(f"  {bpm_label:<12} (BPM={bpm:>6.1f}): No notes after quantization")
                continue

            # Compare with reference
            aligned = apply_sectional_time_offset(quantized_notes, ref_notes)
            m = compare_melodies(ref_notes, aligned)

            print(f"  {bpm_label:<12} (BPM={bpm:>6.1f}): notes={len(quantized_notes):>3}, "
                  f"pc_f1={m['pitch_class_f1']:.3f}, mel_len={m['melody_f1_lenient']:.3f}, "
                  f"contour={m['contour_similarity']:.3f}")
        except Exception as e:
            print(f"  {bpm_label:<12} (BPM={bpm:>6.1f}): ERROR: {e}")

    # Step 6: Analyze the MUSICXML note timing
    print(f"\n--- Timing analysis of MusicXML output ---")
    sec_per_q = 60.0 / detected_bpm
    first_onset_sec = min(n.onset for n in gen_notes) if gen_notes else 0

    # Check time coverage
    gen_end = max(n.onset + n.duration for n in gen_notes)
    ref_end = max(n.onset + n.duration for n in ref_notes)
    print(f"Gen time range: {min(n.onset for n in gen_notes):.1f}s - {gen_end:.1f}s")
    print(f"Ref time range: {min(n.onset for n in ref_notes):.1f}s - {ref_end:.1f}s")
    print(f"Duration ratio: {gen_end / ref_end:.3f}")

    # Step 7: Note density comparison (notes per second)
    print(f"\n--- Note density ---")
    for label, notes in [("Gen", gen_notes), ("Ref", ref_notes)]:
        durations = [n.duration for n in notes]
        ioi = [notes[i+1].onset - notes[i].onset for i in range(len(notes)-1) if notes[i+1].onset > notes[i].onset]
        print(f"  {label}: {len(notes)} notes, "
              f"avg_dur={np.mean(durations)*1000:.0f}ms, "
              f"avg_IOI={np.mean(ioi)*1000:.0f}ms, "
              f"density={len(notes)/(max(n.onset for n in notes) - min(n.onset for n in notes)):.2f} notes/s")


if __name__ == "__main__":
    main()
