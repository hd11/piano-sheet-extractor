#!/usr/bin/env python3
"""
Audio-to-MIDI Spike Test
=========================

Tests the Audio-to-MIDI library (https://github.com/bill317996/Audio-to-midi)
for piano melody extraction.

This library uses MSnet (Melodic SegNet) for melody extraction from audio.
It's designed for vocal/main melody extraction, not full polyphonic transcription.

Test Setup:
- Input: backend/tests/golden/data/song_01/input.mp3 (194.6s, piano audio)
- Reference: backend/tests/golden/data/song_01/reference.mid (1,897 notes)
- Model: MSnet with main-melody mode (not vocal-melody)
- Output: backend/tests/golden/data/song_01/audio2midi_output.mid

Evaluation Criteria:
- Installation ease (pip vs git clone)
- Processing time (must be reasonable for 3min audio)
- Output quality (note count, pitch range vs reference)
- Memory usage
- Polyphonic support (critical for piano)
"""

import os
import sys
import time
import traceback
from pathlib import Path

# Add Audio-to-MIDI repo to path
# On Windows with Git Bash, /tmp maps to AppData/Local/Temp
AUDIO2MIDI_PATH = Path(r"C:\Users\handuk.lee\AppData\Local\Temp\audio-to-midi-spike")
sys.path.insert(0, str(AUDIO2MIDI_PATH))

import numpy as np
import torch
import soundfile as sf
from pypianoroll import Multitrack, Track
from mido import MidiFile

# Import Audio-to-MIDI modules
import cfp
from audio2midi import MSnet, feature_ext, est, seq2roll, write_midi


def load_reference_midi(midi_path):
    """Load reference MIDI and extract statistics."""
    mid = MidiFile(midi_path)

    notes = []
    for track in mid.tracks:
        current_time = 0
        active_notes = {}

        for msg in track:
            current_time += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[msg.note] = current_time
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                if msg.note in active_notes:
                    start_time = active_notes[msg.note]
                    duration = current_time - start_time
                    notes.append(
                        {"pitch": msg.note, "start": start_time, "duration": duration}
                    )
                    del active_notes[msg.note]

    if not notes:
        return None

    pitches = [n["pitch"] for n in notes]
    durations = [n["duration"] for n in notes]

    return {
        "note_count": len(notes),
        "pitch_min": min(pitches),
        "pitch_max": max(pitches),
        "pitch_range": f"{min(pitches)}-{max(pitches)}",
        "avg_duration_ticks": np.mean(durations),
        "notes": notes,
    }


def analyze_output_midi(midi_path):
    """Analyze generated MIDI output."""
    if not os.path.exists(midi_path):
        return None

    mid = MidiFile(midi_path)

    notes = []
    for track in mid.tracks:
        current_time = 0
        active_notes = {}

        for msg in track:
            current_time += msg.time

            if msg.type == "note_on" and msg.velocity > 0:
                active_notes[msg.note] = current_time
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                if msg.note in active_notes:
                    start_time = active_notes[msg.note]
                    duration = current_time - start_time
                    notes.append(
                        {"pitch": msg.note, "start": start_time, "duration": duration}
                    )
                    del active_notes[msg.note]

    if not notes:
        return {
            "note_count": 0,
            "pitch_min": 0,
            "pitch_max": 0,
            "pitch_range": "0-0",
            "avg_duration_ticks": 0,
            "notes": [],
        }

    pitches = [n["pitch"] for n in notes]
    durations = [n["duration"] for n in notes]

    return {
        "note_count": len(notes),
        "pitch_min": min(pitches),
        "pitch_max": max(pitches),
        "pitch_range": f"{min(pitches)}-{max(pitches)}",
        "avg_duration_ticks": np.mean(durations),
        "notes": notes,
    }


def run_audio2midi_test():
    """Run comprehensive Audio-to-MIDI spike test."""

    print("=" * 80)
    print("Audio-to-MIDI Spike Test")
    print("=" * 80)
    print()

    # Setup paths
    project_root = Path(__file__).parent.parent
    test_data_dir = project_root / "tests" / "golden" / "data" / "song_01"
    input_audio = (
        test_data_dir / "input_converted.wav"
    )  # Use WAV (Audio-to-MIDI requires ffmpeg for MP3)
    reference_midi = test_data_dir / "reference.mid"
    output_midi = test_data_dir / "audio2midi_output.mid"
    model_path = AUDIO2MIDI_PATH / "model" / "model_melody"  # Use main-melody model

    # Verify files exist
    if not input_audio.exists():
        print(f"[ERROR] Input audio not found: {input_audio}")
        return

    if not reference_midi.exists():
        print(f"[ERROR] Reference MIDI not found: {reference_midi}")
        return

    if not model_path.exists():
        print(f"[ERROR] Model not found: {model_path}")
        print(f"   Make sure Audio-to-MIDI repo is cloned to {AUDIO2MIDI_PATH}")
        return

    print(f"[FILES] Input audio: {input_audio}")
    print(f"[FILES] Reference MIDI: {reference_midi}")
    print(f"[FILES] Output MIDI: {output_midi}")
    print(f"[FILES] Model: {model_path}")
    print()

    # Load reference MIDI
    print("[STEP 1] Loading reference MIDI...")
    ref_stats = load_reference_midi(str(reference_midi))
    if ref_stats:
        print(f"   Notes: {ref_stats['note_count']}")
        print(f"   Pitch range: {ref_stats['pitch_range']}")
        print(f"   Avg duration: {ref_stats['avg_duration_ticks']:.1f} ticks")
    print()

    # Initialize model
    print("[STEP 2] Initializing MSnet model...")
    try:
        Net = MSnet()
        Net.float()
        Net.cpu()
        Net.load_state_dict(
            torch.load(str(model_path), map_location=lambda storage, loc: storage)
        )
        Net.eval()
        print("   [OK] Model loaded successfully")
    except Exception as e:
        print(f"   [ERROR] loading model: {e}")
        traceback.print_exc()
        return
    print()

    # Feature extraction
    print("[STEP 3] Feature extraction...")
    time_feature_start = time.time()
    try:
        W, Time_arr, Freq_arr = feature_ext(str(input_audio))
        W_tensor = torch.from_numpy(W).float()
        W_tensor = W_tensor[None, :]
        time_feature = time.time() - time_feature_start
        print(f"   [OK] Done in {time_feature:.2f}s")
        print(f"   Feature shape: {W.shape}")
        print(f"   Time frames: {len(Time_arr)}")
        print(f"   Freq bins: {len(Freq_arr)}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        traceback.print_exc()
        return
    print()

    # Melody extraction
    print("[STEP 4] Melody extraction (MSnet inference)...")
    time_inference_start = time.time()
    try:
        pred = Net(W_tensor)
        pred = pred.detach().numpy()
        est_arr = est(pred)
        time_inference = time.time() - time_inference_start
        print(f"   [OK] Done in {time_inference:.2f}s")
        print(f"   Prediction shape: {pred.shape}")
        print(f"   Estimated array shape: {est_arr.shape}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        traceback.print_exc()
        return
    print()

    # MIDI conversion
    print("[STEP 5] Converting to MIDI...")
    time_midi_start = time.time()
    try:
        rolls = seq2roll(est_arr[:, 1])
        print(f"   Piano roll shape: {rolls.shape}")

        # Write MIDI directly using mido (pypianoroll API has changed too much)
        from mido import Message, MidiTrack, MetaMessage

        mid = MidiFile()
        track = MidiTrack()
        mid.tracks.append(track)

        # Add tempo
        track.append(MetaMessage("set_tempo", tempo=352941))  # 170 BPM

        # Convert piano roll to MIDI notes
        # rolls is (time_steps, 128) where each row is a MIDI note activation
        ticks_per_step = 16  # beat_resolution from original code

        # Find note on/off events
        for note_num in range(128):
            if not np.any(rolls[:, note_num]):
                continue

            note_active = False
            note_start = 0

            for t in range(len(rolls)):
                if rolls[t, note_num] and not note_active:
                    # Note on
                    note_start = t
                    note_active = True
                elif not rolls[t, note_num] and note_active:
                    # Note off
                    track.append(
                        Message(
                            "note_on",
                            note=note_num,
                            velocity=100,
                            time=note_start * ticks_per_step,
                        )
                    )
                    track.append(
                        Message(
                            "note_off",
                            note=note_num,
                            velocity=0,
                            time=t * ticks_per_step,
                        )
                    )
                    note_active = False

            # Handle note still active at end
            if note_active:
                track.append(
                    Message(
                        "note_on",
                        note=note_num,
                        velocity=100,
                        time=note_start * ticks_per_step,
                    )
                )
                track.append(
                    Message(
                        "note_off",
                        note=note_num,
                        velocity=0,
                        time=len(rolls) * ticks_per_step,
                    )
                )

        # Sort messages by time and convert to delta times
        messages = sorted(
            [m for m in track if m.type in ["note_on", "note_off"]],
            key=lambda m: m.time,
        )

        track.clear()
        track.append(MetaMessage("set_tempo", tempo=352941))

        last_time = 0
        for msg in messages:
            abs_time = msg.time
            delta = abs_time - last_time
            track.append(msg.copy(time=delta))
            last_time = abs_time

        mid.save(str(output_midi))

        time_midi = time.time() - time_midi_start
        print(f"   [OK] Done in {time_midi:.2f}s")
    except Exception as e:
        print(f"   [ERROR] {e}")
        traceback.print_exc()
        return
    print()

    # Analyze output
    print("[STEP 6] Analyzing output MIDI...")
    output_stats = analyze_output_midi(str(output_midi))
    if output_stats:
        print(f"   Notes: {output_stats['note_count']}")
        print(f"   Pitch range: {output_stats['pitch_range']}")
        print(f"   Avg duration: {output_stats['avg_duration_ticks']:.1f} ticks")
    else:
        print("   [ERROR] Failed to analyze output MIDI")
    print()

    # Summary
    total_time = time_feature + time_inference + time_midi
    audio_duration = 194.6  # seconds (from metadata)

    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    print("PERFORMANCE METRICS:")
    print(
        f"   Total processing time: {total_time:.2f}s ({total_time / audio_duration:.2f}x realtime)"
    )
    print(
        f"   - Feature extraction: {time_feature:.2f}s ({time_feature / total_time * 100:.1f}%)"
    )
    print(
        f"   - MSnet inference: {time_inference:.2f}s ({time_inference / total_time * 100:.1f}%)"
    )
    print(
        f"   - MIDI conversion: {time_midi:.2f}s ({time_midi / total_time * 100:.1f}%)"
    )
    print()

    print("OUTPUT QUALITY:")
    if ref_stats and output_stats:
        note_ratio = output_stats["note_count"] / ref_stats["note_count"]
        print(
            f"   Note count: {output_stats['note_count']} (vs {ref_stats['note_count']} reference = {note_ratio:.2f}x)"
        )
        print(
            f"   Pitch range: {output_stats['pitch_range']} (vs {ref_stats['pitch_range']} reference)"
        )
        print(
            f"   Avg duration: {output_stats['avg_duration_ticks']:.1f} ticks (vs {ref_stats['avg_duration_ticks']:.1f} reference)"
        )
    print()

    print("EVALUATION:")
    print()
    print("[PROS]")
    print("   - Relatively fast: ~{:.1f}s for 3min audio".format(total_time))
    print("   - Simple architecture: MSnet (Melodic SegNet)")
    print("   - Pre-trained models included (vocal & melody)")
    print("   - Lightweight dependencies (PyTorch, numpy, scipy)")
    print()

    print("[CONS]")
    print("   - Complex installation: Requires git clone (not pip installable)")
    print("   - Monophonic output: Designed for single melody line")
    print(
        "   - Not suitable for piano: Piano is polyphonic, this extracts only main melody"
    )
    if output_stats and ref_stats:
        if note_ratio < 0.3:
            print(
                f"   - Very low note count: Only {note_ratio * 100:.1f}% of reference notes"
            )
        elif note_ratio < 0.5:
            print(
                f"   - Low note count: Only {note_ratio * 100:.1f}% of reference notes"
            )
    print("   - Old codebase: Last updated 2019, Python 3.6, PyTorch 1.0")
    print("   - No pip package: Must clone repo and manage paths manually")
    print()

    print("RECOMMENDATION:")
    if output_stats and ref_stats and note_ratio < 0.5:
        print("   [REJECT] Audio-to-MIDI for piano melody extraction")
        print()
        print("   REASONS:")
        print(
            "   1. Monophonic limitation: Extracts only single melody line, not full piano"
        )
        print(
            f"   2. Poor coverage: Only {note_ratio * 100:.1f}% of reference notes extracted"
        )
        print("   3. Installation complexity: Requires git clone, not pip installable")
        print("   4. Outdated: 2019 codebase, may have compatibility issues")
        print("   5. Wrong use case: Designed for vocal/melody, not polyphonic piano")
        print()
        print("   BETTER ALTERNATIVES:")
        print("   - Basic Pitch: Already in use, polyphonic, pip installable")
        print("   - Librosa PYIN: For melody extraction (if needed)")
        print("   - MT3/Onsets and Frames: For full polyphonic transcription")
    else:
        print("   [CONDITIONAL ACCEPT] (with caveats)")
        print("   - Only if monophonic melody extraction is acceptable")
        print("   - Installation complexity is a significant drawback")
    print()

    print("=" * 80)
    print(f"[COMPLETE] Spike test complete. Output saved to: {output_midi}")
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    print("⏱️  PERFORMANCE METRICS:")
    print(
        f"   Total processing time: {total_time:.2f}s ({total_time / audio_duration:.2f}x realtime)"
    )
    print(
        f"   - Feature extraction: {time_feature:.2f}s ({time_feature / total_time * 100:.1f}%)"
    )
    print(
        f"   - MSnet inference: {time_inference:.2f}s ({time_inference / total_time * 100:.1f}%)"
    )
    print(
        f"   - MIDI conversion: {time_midi:.2f}s ({time_midi / total_time * 100:.1f}%)"
    )
    print()

    print("🎵 OUTPUT QUALITY:")
    if ref_stats and output_stats:
        note_ratio = output_stats["note_count"] / ref_stats["note_count"]
        print(
            f"   Note count: {output_stats['note_count']} (vs {ref_stats['note_count']} reference = {note_ratio:.2f}x)"
        )
        print(
            f"   Pitch range: {output_stats['pitch_range']} (vs {ref_stats['pitch_range']} reference)"
        )
        print(
            f"   Avg duration: {output_stats['avg_duration_ticks']:.1f} ticks (vs {ref_stats['avg_duration_ticks']:.1f} reference)"
        )
    print()

    print("📋 EVALUATION:")
    print()
    print("✅ PROS:")
    print("   - Relatively fast: ~{:.1f}s for 3min audio".format(total_time))
    print("   - Simple architecture: MSnet (Melodic SegNet)")
    print("   - Pre-trained models included (vocal & melody)")
    print("   - Lightweight dependencies (PyTorch, numpy, scipy)")
    print()

    print("❌ CONS:")
    print("   - Complex installation: Requires git clone (not pip installable)")
    print("   - Monophonic output: Designed for single melody line")
    print(
        "   - Not suitable for piano: Piano is polyphonic, this extracts only main melody"
    )
    if output_stats and ref_stats:
        if note_ratio < 0.3:
            print(
                f"   - Very low note count: Only {note_ratio * 100:.1f}% of reference notes"
            )
        elif note_ratio < 0.5:
            print(
                f"   - Low note count: Only {note_ratio * 100:.1f}% of reference notes"
            )
    print("   - Old codebase: Last updated 2019, Python 3.6, PyTorch 1.0")
    print("   - No pip package: Must clone repo and manage paths manually")
    print()

    print("🎯 RECOMMENDATION:")
    if output_stats and ref_stats and note_ratio < 0.5:
        print("   ❌ REJECT Audio-to-MIDI for piano melody extraction")
        print()
        print("   REASONS:")
        print(
            "   1. Monophonic limitation: Extracts only single melody line, not full piano"
        )
        print(
            f"   2. Poor coverage: Only {note_ratio * 100:.1f}% of reference notes extracted"
        )
        print("   3. Installation complexity: Requires git clone, not pip installable")
        print("   4. Outdated: 2019 codebase, may have compatibility issues")
        print("   5. Wrong use case: Designed for vocal/melody, not polyphonic piano")
        print()
        print("   BETTER ALTERNATIVES:")
        print("   - Basic Pitch: Already in use, polyphonic, pip installable")
        print("   - Librosa PYIN: For melody extraction (if needed)")
        print("   - MT3/Onsets and Frames: For full polyphonic transcription")
    else:
        print("   ⚠️  CONDITIONAL ACCEPT (with caveats)")
        print("   - Only if monophonic melody extraction is acceptable")
        print("   - Installation complexity is a significant drawback")
    print()

    print("=" * 80)
    print(f"✅ Spike test complete. Output saved to: {output_midi}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        run_audio2midi_test()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        traceback.print_exc()
        sys.exit(1)
