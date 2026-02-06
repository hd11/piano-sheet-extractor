#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick script to analyze reference MIDI structure."""

import sys
import io
import pretty_midi
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

midi_path = Path(__file__).parent.parent / "tests/golden/data/song_01/reference.mid"
midi = pretty_midi.PrettyMIDI(str(midi_path))

print(f"MIDI File: {midi_path.name}")
print(f"Duration: {midi.get_end_time():.2f}s")
print(f"Number of instruments: {len(midi.instruments)}")
print()

for i, inst in enumerate(midi.instruments):
    print(f"Instrument {i}: {inst.name or 'Unnamed'}")
    print(f"  Program: {inst.program}")
    print(f"  Is drum: {inst.is_drum}")
    print(f"  Number of notes: {len(inst.notes)}")

    if inst.notes:
        pitches = [n.pitch for n in inst.notes]
        print(f"  Pitch range: {min(pitches)} - {max(pitches)} (MIDI)")
        print(f"  First 5 notes:")
        for note in inst.notes[:5]:
            print(
                f"    Pitch: {note.pitch}, Start: {note.start:.3f}s, End: {note.end:.3f}s, Duration: {(note.end - note.start) * 1000:.1f}ms"
            )
    print()
