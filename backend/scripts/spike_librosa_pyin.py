#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Librosa PYIN spike test for melody extraction.

This script tests librosa.pyin()'s ability to extract melody from audio and convert to MIDI.
Evaluates: installation ease, processing time, memory usage, output quality.

PYIN is a probabilistic YIN algorithm for monophonic pitch tracking.
Unlike CREPE (neural network), PYIN is a traditional signal processing algorithm.
"""

import sys
import io
import time
import numpy as np
import librosa
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


def merge_consecutive_notes(times, midi_notes, voiced_probs, min_duration=0.05):
    """Merge consecutive identical MIDI notes and filter short notes.

    Args:
        times: Array of time stamps (seconds)
        midi_notes: Array of MIDI note numbers
        voiced_probs: Array of voicing probability values
        min_duration: Minimum note duration in seconds

    Returns:
        List of (start_time, end_time, midi_note, avg_prob) tuples
    """
    if len(times) == 0:
        return []

    merged = []
    current_note = None
    start_time = None
    start_idx = None

    for i, (t, note, prob) in enumerate(zip(times, midi_notes, voiced_probs)):
        if note is None:
            # Silence - end current note if any
            if current_note is not None:
                duration = times[i - 1] - start_time
                if duration >= min_duration:
                    avg_prob = np.mean(voiced_probs[start_idx:i])
                    merged.append((start_time, times[i - 1], current_note, avg_prob))
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
                    avg_prob = np.mean(voiced_probs[start_idx:i])
                    merged.append((start_time, times[i - 1], current_note, avg_prob))
                current_note = rounded_note
                start_time = t
                start_idx = i

    # Handle last note
    if current_note is not None:
        duration = times[-1] - start_time
        if duration >= min_duration:
            avg_prob = np.mean(voiced_probs[start_idx:])
            merged.append((start_time, times[-1], current_note, avg_prob))

    return merged


def pitch_to_midi(
    times,
    freqs,
    voiced_flags,
    voiced_probs,
    output_path,
    min_duration=0.05,
    min_prob=0.5,
):
    """Convert pitch contour to MIDI file.

    Args:
        times: Array of time stamps (seconds)
        freqs: Array of frequencies (Hz)
        voiced_flags: Array of voiced/unvoiced flags
        voiced_probs: Array of voicing probability values (0-1)
        output_path: Path to save MIDI file
        min_duration: Minimum note duration in seconds
        min_prob: Minimum voicing probability threshold

    Returns:
        Number of notes created
    """
    # Convert Hz to MIDI, filtering by voicing probability
    midi_notes = []
    for freq, voiced, prob in zip(freqs, voiced_flags, voiced_probs):
        if not voiced or prob < min_prob or np.isnan(freq):
            midi_notes.append(None)
        else:
            midi_notes.append(hz_to_midi(freq))

    # Merge consecutive notes
    merged_notes = merge_consecutive_notes(
        times, midi_notes, voiced_probs, min_duration
    )

    # Create MIDI file
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0, name="PYIN Melody")

    for start, end, pitch, prob in merged_notes:
        note = pretty_midi.Note(
            velocity=int(prob * 100 + 27),  # Map probability to velocity (27-127)
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
    """Run PYIN spike test."""
    print("=" * 80)
    print("Librosa PYIN Melody Extraction Spike Test")
    print("=" * 80)
    print()

    # Paths
    base_dir = Path(__file__).parent.parent
    audio_path = base_dir / "tests/golden/data/song_01/input.mp3"
    reference_path = base_dir / "tests/golden/data/song_01/reference.mid"
    output_path = base_dir / "tests/golden/data/song_01/pyin_output.mid"

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
    y, sr = librosa.load(str(audio_path), sr=22050)  # PYIN works well with 22050 Hz
    load_time = time.time() - load_start
    print(f"  ✓ Loaded in {load_time:.2f}s")
    print(f"  Sample rate: {sr} Hz")
    print(f"  Duration: {len(y) / sr:.2f}s")
    print(f"  Samples: {len(y):,}")
    print()

    # Step 2: Run PYIN
    print("Step 2: Running PYIN pitch detection...")
    print("  Parameters:")
    print("    - fmin: C2 (~65 Hz)")
    print("    - fmax: C7 (~2093 Hz)")
    print("    - frame_length: 2048 samples")
    print("    - hop_length: 1024 samples (~46ms) - optimized for speed")
    pyin_start = time.time()

    # PYIN pitch tracking
    # Use larger hop_length for faster processing (trade-off: less temporal resolution)
    hop_length = 1024  # ~46ms at 22050 Hz (vs 512 = ~23ms)
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),  # ~65 Hz (piano low range)
        fmax=librosa.note_to_hz("C7"),  # ~2093 Hz (piano high range)
        sr=sr,
        frame_length=2048,
        hop_length=hop_length,
    )

    pyin_time = time.time() - pyin_start

    # Create time stamps for each frame
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)

    # Calculate statistics
    voiced_frames = np.sum(voiced_flag)
    total_frames = len(voiced_flag)
    avg_prob = np.nanmean(voiced_probs[voiced_flag])

    print(f"  ✓ Completed in {pyin_time:.2f}s")
    print(f"  Frames analyzed: {total_frames:,}")
    print(
        f"  Voiced frames: {voiced_frames:,} ({voiced_frames / total_frames * 100:.1f}%)"
    )
    print(f"  Average voicing probability: {avg_prob:.3f}")
    print(f"  Prob > 0.5: {np.sum(voiced_probs > 0.5) / total_frames * 100:.1f}%")
    print()

    # Step 3: Convert to MIDI
    print("Step 3: Converting pitch to MIDI...")
    print("  Parameters:")
    print("    - min_duration: 50ms")
    print("    - min_prob: 0.5")
    convert_start = time.time()
    num_notes = pitch_to_midi(
        times,
        f0,
        voiced_flag,
        voiced_probs,
        output_path,
        min_duration=0.05,
        min_prob=0.5,
    )
    convert_time = time.time() - convert_start
    print(f"  ✓ Created {num_notes} notes in {convert_time:.2f}s")
    print(f"  Output: {output_path.name}")
    print()

    # Step 4: Compare with reference
    print("Step 4: Comparing with reference...")
    ref_analysis = analyze_reference_midi(reference_path)
    pyin_analysis = analyze_reference_midi(output_path)

    print("  Reference MIDI:")
    print(f"    Notes: {ref_analysis['num_notes']}")
    print(f"    Duration: {ref_analysis['duration']:.2f}s")
    print(
        f"    Pitch range: {ref_analysis['pitch_range'][0]} - {ref_analysis['pitch_range'][1]}"
    )
    print(f"    Avg note duration: {ref_analysis['avg_note_duration'] * 1000:.1f}ms")
    print()

    print("  PYIN Output:")
    print(f"    Notes: {pyin_analysis['num_notes']}")
    print(f"    Duration: {pyin_analysis['duration']:.2f}s")
    print(
        f"    Pitch range: {pyin_analysis['pitch_range'][0]} - {pyin_analysis['pitch_range'][1]}"
    )
    print(f"    Avg note duration: {pyin_analysis['avg_note_duration'] * 1000:.1f}ms")
    print()

    # Step 5: Summary
    print("=" * 80)
    print("SPIKE EVALUATION SUMMARY")
    print("=" * 80)
    print()

    total_time = load_time + pyin_time + convert_time
    print(f"⏱️  Total Processing Time: {total_time:.2f}s")
    print(f"   - Audio loading: {load_time:.2f}s ({load_time / total_time * 100:.1f}%)")
    print(
        f"   - PYIN inference: {pyin_time:.2f}s ({pyin_time / total_time * 100:.1f}%)"
    )
    print(
        f"   - MIDI conversion: {convert_time:.2f}s ({convert_time / total_time * 100:.1f}%)"
    )
    print()

    print(f"📊 Output Quality:")
    note_ratio = (
        pyin_analysis["num_notes"] / ref_analysis["num_notes"]
        if ref_analysis["num_notes"] > 0
        else 0
    )
    print(
        f"   - Note count: {pyin_analysis['num_notes']} vs {ref_analysis['num_notes']} reference ({note_ratio:.2f}x)"
    )
    print(f"   - Voiced frames: {voiced_frames / total_frames * 100:.1f}%")
    print(f"   - Average voicing probability: {avg_prob:.3f}")
    print()

    print(f"✅ Installation: Already included (librosa)")
    print(f"✅ Dependencies: None (part of librosa)")
    print(f"✅ API: Simple librosa.pyin() call")
    print(f"⚠️  Limitation: Monophonic (like CREPE)")
    print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()

    # Decision criteria
    is_fast = total_time < 10  # Should be much faster than CREPE (42s)
    has_reasonable_notes = note_ratio > 0.2  # Better than CREPE (0.16x)

    if is_fast and has_reasonable_notes:
        print("✅ ACCEPT PYIN for further consideration")
        print()
        print("Reasons:")
        print(f"  - Fast processing: {total_time:.1f}s (vs CREPE 42s)")
        print(f"  - Reasonable output: {note_ratio:.2f}x reference notes")
        print(f"  - No extra dependencies (already in librosa)")
        print(f"  - Simple API")
        print()
        print("Caveats:")
        print("  - Still monophonic (like CREPE)")
        print("  - May miss polyphonic piano content")
        print("  - Best for melody extraction, not full transcription")
    elif is_fast:
        print("⚠️  CONDITIONAL: Fast but poor quality")
        print()
        print(f"  - Processing time: {total_time:.1f}s ✅")
        print(f"  - Note ratio: {note_ratio:.2f}x ❌")
        print()
        print("Consider if melody-only extraction is acceptable.")
    else:
        print("❌ REJECT PYIN")
        print()
        print("Reasons:")
        if not is_fast:
            print(f"  - Too slow: {total_time:.1f}s")
        if not has_reasonable_notes:
            print(f"  - Poor quality: {note_ratio:.2f}x reference notes")

    print()
    print(f"📁 Output saved to: {output_path}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
