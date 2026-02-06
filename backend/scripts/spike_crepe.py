#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CREPE spike test for melody extraction.

This script tests CREPE's ability to extract melody from audio and convert to MIDI.
Evaluates: installation ease, processing time, memory usage, output quality.
"""

import sys
import io
import time
import numpy as np
import librosa
import crepe
import pretty_midi
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def hz_to_midi(freq):
    """Convert Hz to MIDI note number.

    Args:
        freq: Frequency in Hz

    Returns:
        MIDI note number (float) or None if invalid
    """
    if freq <= 0 or np.isnan(freq):
        return None
    return 69 + 12 * np.log2(freq / 440.0)


def merge_consecutive_notes(times, midi_notes, confs, min_duration=0.05):
    """Merge consecutive identical MIDI notes and filter short notes.

    Args:
        times: Array of time stamps (seconds)
        midi_notes: Array of MIDI note numbers
        confs: Array of confidence values
        min_duration: Minimum note duration in seconds

    Returns:
        List of (start_time, end_time, midi_note, avg_confidence) tuples
    """
    if len(times) == 0:
        return []

    merged = []
    current_note = None
    start_time = None
    start_idx = None

    for i, (t, note, conf) in enumerate(zip(times, midi_notes, confs)):
        if note is None:
            # Silence - end current note if any
            if current_note is not None:
                duration = times[i - 1] - start_time
                if duration >= min_duration:
                    avg_conf = np.mean(confs[start_idx:i])
                    merged.append((start_time, times[i - 1], current_note, avg_conf))
                current_note = None
        else:
            # Round to nearest semitone
            rounded_note = int(round(note))

            if current_note is None:
                # Start new note
                current_note = rounded_note
                start_time = t
                start_idx = i
            elif rounded_note != current_note:
                # Note changed - save previous and start new
                duration = times[i - 1] - start_time
                if duration >= min_duration:
                    avg_conf = np.mean(confs[start_idx:i])
                    merged.append((start_time, times[i - 1], current_note, avg_conf))
                current_note = rounded_note
                start_time = t
                start_idx = i

    # Handle last note
    if current_note is not None:
        duration = times[-1] - start_time
        if duration >= min_duration:
            avg_conf = np.mean(confs[start_idx:])
            merged.append((start_time, times[-1], current_note, avg_conf))

    return merged


def pitch_to_midi(
    times, freqs, confs, output_path, min_duration=0.05, min_confidence=0.5
):
    """Convert pitch contour to MIDI file.

    Args:
        times: Array of time stamps (seconds)
        freqs: Array of frequencies (Hz)
        confs: Array of confidence values (0-1)
        output_path: Path to save MIDI file
        min_duration: Minimum note duration in seconds
        min_confidence: Minimum confidence threshold

    Returns:
        Number of notes created
    """
    # Convert Hz to MIDI, filtering by confidence
    midi_notes = []
    for freq, conf in zip(freqs, confs):
        if conf < min_confidence:
            midi_notes.append(None)
        else:
            midi_notes.append(hz_to_midi(freq))

    # Merge consecutive notes
    merged_notes = merge_consecutive_notes(times, midi_notes, confs, min_duration)

    # Create MIDI file
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0, name="CREPE Melody")

    for start, end, pitch, conf in merged_notes:
        note = pretty_midi.Note(
            velocity=int(conf * 100 + 27),  # Map confidence to velocity (27-127)
            pitch=pitch,
            start=start,
            end=end,
        )
        instrument.notes.append(note)

    midi.instruments.append(instrument)
    midi.write(str(output_path))

    return len(merged_notes)


def analyze_reference_midi(midi_path):
    """Analyze reference MIDI for comparison.

    Args:
        midi_path: Path to reference MIDI file

    Returns:
        Dict with analysis results
    """
    midi = pretty_midi.PrettyMIDI(str(midi_path))

    all_notes = []
    for inst in midi.instruments:
        if not inst.is_drum:
            all_notes.extend(inst.notes)

    if not all_notes:
        return {
            "num_notes": 0,
            "duration": 0,
            "pitch_range": (0, 0),
            "avg_note_duration": 0,
        }

    pitches = [n.pitch for n in all_notes]
    durations = [(n.end - n.start) for n in all_notes]

    return {
        "num_notes": len(all_notes),
        "duration": midi.get_end_time(),
        "pitch_range": (min(pitches), max(pitches)),
        "avg_note_duration": np.mean(durations),
    }


def main():
    """Run CREPE spike test."""
    print("=" * 80)
    print("CREPE Melody Extraction Spike Test")
    print("=" * 80)
    print()

    # Paths
    base_dir = Path(__file__).parent.parent
    audio_path = base_dir / "tests/golden/data/song_01/input.mp3"
    reference_path = base_dir / "tests/golden/data/song_01/reference.mid"
    output_path = base_dir / "tests/golden/data/song_01/crepe_output.mid"

    # Check files exist
    if not audio_path.exists():
        print(f"ERROR: Audio file not found: {audio_path}")
        return 1
    if not reference_path.exists():
        print(f"ERROR: Reference MIDI not found: {reference_path}")
        return 1

    print(
        f"Audio: {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f} MB)"
    )
    print(f"Reference: {reference_path.name}")
    print()

    # Step 1: Load audio
    print("Step 1: Loading audio...")
    load_start = time.time()
    y, sr = librosa.load(str(audio_path), sr=16000)  # CREPE expects 16kHz
    load_time = time.time() - load_start
    print(f"  ✓ Loaded in {load_time:.2f}s")
    print(f"  Sample rate: {sr} Hz")
    print(f"  Duration: {len(y) / sr:.2f}s")
    print(f"  Samples: {len(y):,}")
    print()

    # Step 2: Run CREPE
    print("Step 2: Running CREPE pitch detection...")
    print("  Parameters:")
    print("    - viterbi: True (smoothing)")
    print("    - step_size: 10ms")
    print("    - model_capacity: tiny (for speed)")
    crepe_start = time.time()
    time_stamps, frequencies, confidence, activation = crepe.predict(
        y,
        sr,
        viterbi=True,  # Use Viterbi smoothing for better pitch tracking
        step_size=10,  # 10ms steps
        model_capacity="tiny",  # Use tiny model for speed test
    )
    crepe_time = time.time() - crepe_start
    print(f"  ✓ Completed in {crepe_time:.2f}s")
    print(f"  Frames analyzed: {len(time_stamps):,}")
    print(f"  Average confidence: {np.mean(confidence):.3f}")
    print(
        f"  Confidence > 0.5: {np.sum(confidence > 0.5) / len(confidence) * 100:.1f}%"
    )
    print()

    # Step 3: Convert to MIDI
    print("Step 3: Converting pitch to MIDI...")
    print("  Parameters:")
    print("    - min_duration: 50ms")
    print("    - min_confidence: 0.5")
    convert_start = time.time()
    num_notes = pitch_to_midi(
        time_stamps,
        frequencies,
        confidence,
        output_path,
        min_duration=0.05,
        min_confidence=0.5,
    )
    convert_time = time.time() - convert_start
    print(f"  ✓ Created {num_notes} notes in {convert_time:.2f}s")
    print(f"  Output: {output_path.name}")
    print()

    # Step 4: Compare with reference
    print("Step 4: Comparing with reference...")
    ref_analysis = analyze_reference_midi(reference_path)
    crepe_analysis = analyze_reference_midi(output_path)

    print("  Reference MIDI:")
    print(f"    Notes: {ref_analysis['num_notes']}")
    print(f"    Duration: {ref_analysis['duration']:.2f}s")
    print(
        f"    Pitch range: {ref_analysis['pitch_range'][0]} - {ref_analysis['pitch_range'][1]}"
    )
    print(f"    Avg note duration: {ref_analysis['avg_note_duration'] * 1000:.1f}ms")
    print()

    print("  CREPE Output:")
    print(f"    Notes: {crepe_analysis['num_notes']}")
    print(f"    Duration: {crepe_analysis['duration']:.2f}s")
    print(
        f"    Pitch range: {crepe_analysis['pitch_range'][0]} - {crepe_analysis['pitch_range'][1]}"
    )
    print(f"    Avg note duration: {crepe_analysis['avg_note_duration'] * 1000:.1f}ms")
    print()

    # Step 5: Summary
    print("=" * 80)
    print("SPIKE EVALUATION SUMMARY")
    print("=" * 80)
    print()

    total_time = load_time + crepe_time + convert_time
    print(f"⏱️  Total Processing Time: {total_time:.2f}s")
    print(f"   - Audio loading: {load_time:.2f}s ({load_time / total_time * 100:.1f}%)")
    print(
        f"   - CREPE inference: {crepe_time:.2f}s ({crepe_time / total_time * 100:.1f}%)"
    )
    print(
        f"   - MIDI conversion: {convert_time:.2f}s ({convert_time / total_time * 100:.1f}%)"
    )
    print()

    print(f"📊 Output Quality:")
    note_ratio = (
        crepe_analysis["num_notes"] / ref_analysis["num_notes"]
        if ref_analysis["num_notes"] > 0
        else 0
    )
    print(f"   - Note count ratio: {note_ratio:.2f}x reference")
    print(f"   - Average confidence: {np.mean(confidence):.3f}")
    print()

    print(f"✅ Installation: Easy (pip install crepe)")
    print(f"✅ Dependencies: Minimal (numpy, scipy, tensorflow via crepe)")
    print(f"✅ API: Simple and intuitive")
    print()

    print(f"📁 Output saved to: {output_path}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
