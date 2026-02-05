#!/usr/bin/env python3
"""
Music2MIDI Spike Validation Script
Tests Music2MIDI compatibility and generates GO/NO-GO decision.
"""

import sys
import time
import subprocess
import os


def run_command(cmd, description):
    """Run a shell command and return success status."""
    print(f"\n{'=' * 60}")
    print(f"{description}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode == 0


def write_test_script(filename, code):
    """Write Python code to a file and return the path."""
    path = f"/tmp/{filename}"
    with open(path, "w") as f:
        f.write(code)
    return path


def main():
    results = {}

    # Step 0: Install git and wget
    success = run_command(
        "apt-get update -qq && apt-get install -y -qq git wget",
        "Step 0: Install git and wget",
    )
    if not success:
        print("FAILED: Could not install git/wget")
        return False

    # Step 0b: Install Python dependencies
    # Note: torch 2.10.0 is already installed, need compatible torchaudio
    success = run_command(
        "pip install -q omegaconf pytorch-lightning more-itertools mido transformers mir_eval torchaudio",
        "Step 0b: Install Music2MIDI dependencies",
    )
    if not success:
        print("FAILED: Could not install dependencies")
        return False

    # Step 1: Clone Music2MIDI
    success = run_command(
        "cd /tmp && git clone https://github.com/ytinyui/music2midi.git",
        "Step 1: Clone Music2MIDI repository",
    )
    results["clone"] = success
    if not success:
        print("FAILED: Could not clone repository")
        return False

    # Step 2: Download checkpoint
    success = run_command(
        "mkdir -p /tmp/music2midi/checkpoints && cd /tmp/music2midi/checkpoints && wget -q https://github.com/ytinyui/music2midi/releases/download/0.1.0/epoch.799-step.119200.ckpt && ls -lh epoch.799-step.119200.ckpt",
        "Step 2: Download model checkpoint",
    )
    results["checkpoint"] = success
    if not success:
        print("FAILED: Could not download checkpoint")
        return False

    # Step 3: Test import
    test_import_code = """
import sys
sys.path.insert(0, '/tmp/music2midi')
import torch
from music2midi.model import Music2MIDI
print(f"Import OK - Torch {torch.__version__}, Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
"""
    test_path = write_test_script("test_import.py", test_import_code)
    success = run_command(f"python {test_path}", "Step 3: Test Music2MIDI import")
    results["import"] = success
    if not success:
        print("FAILED: Could not import Music2MIDI")
        return False

    # Step 4: Generate MIDI (Advanced)
    test_generate_code = """
import sys
sys.path.insert(0, '/tmp/music2midi')
import torch
from music2midi.model import Music2MIDI
import time
import pretty_midi

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Loading model on {device}...")

model = Music2MIDI.load_from_checkpoint(
    "/tmp/music2midi/checkpoints/epoch.799-step.119200.ckpt",
    config_path="/tmp/music2midi/config.yaml"
)
model.to(device).eval()
print("Model loaded")

print("Generating MIDI (Advanced)...")
start = time.time()
midi_data = model.generate("/app/tests/golden/data/song_01/input.mp3", cond_index=[1, 2])
elapsed = time.time() - start
midi_data.write("/tmp/spike_advanced.mid")

pm = pretty_midi.PrettyMIDI("/tmp/spike_advanced.mid")
notes = sum(len(i.notes) for i in pm.instruments)
pitches = [n.pitch for i in pm.instruments for n in i.notes]
pitch_min = min(pitches) if pitches else 0
pitch_max = max(pitches) if pitches else 0
duration = pm.get_end_time()

print(f"RESULT: {notes} notes, pitch {pitch_min}-{pitch_max}, {duration:.1f}s duration, {elapsed:.1f}s generation time")
"""
    test_path = write_test_script("test_generate.py", test_generate_code)
    success = run_command(
        f"python {test_path}", "Step 4: Generate MIDI (Advanced difficulty)"
    )
    results["generate_advanced"] = success
    if not success:
        print("FAILED: Could not generate MIDI")
        return False

    # Step 5: Test difficulty conditioning
    test_difficulties_code = """
import sys
sys.path.insert(0, '/tmp/music2midi')
import torch
from music2midi.model import Music2MIDI
import time
import pretty_midi

device = "cuda" if torch.cuda.is_available() else "cpu"
model = Music2MIDI.load_from_checkpoint(
    "/tmp/music2midi/checkpoints/epoch.799-step.119200.ckpt",
    config_path="/tmp/music2midi/config.yaml"
)
model.to(device).eval()

# Beginner
start = time.time()
midi_data = model.generate("/app/tests/golden/data/song_01/input.mp3", cond_index=[1, 0])
time_beg = time.time() - start
midi_data.write("/tmp/spike_beginner.mid")
pm = pretty_midi.PrettyMIDI("/tmp/spike_beginner.mid")
notes_beg = sum(len(i.notes) for i in pm.instruments)

# Intermediate
start = time.time()
midi_data = model.generate("/app/tests/golden/data/song_01/input.mp3", cond_index=[1, 1])
time_int = time.time() - start
midi_data.write("/tmp/spike_intermediate.mid")
pm = pretty_midi.PrettyMIDI("/tmp/spike_intermediate.mid")
notes_int = sum(len(i.notes) for i in pm.instruments)

# Advanced
start = time.time()
midi_data = model.generate("/app/tests/golden/data/song_01/input.mp3", cond_index=[1, 2])
time_adv = time.time() - start
midi_data.write("/tmp/spike_advanced.mid")
pm = pretty_midi.PrettyMIDI("/tmp/spike_advanced.mid")
notes_adv = sum(len(i.notes) for i in pm.instruments)

print(f"Beginner: {notes_beg} notes ({time_beg:.1f}s)")
print(f"Intermediate: {notes_int} notes ({time_int:.1f}s)")
print(f"Advanced: {notes_adv} notes ({time_adv:.1f}s)")
print(f"Conditioning works: {notes_beg < notes_int < notes_adv}")
print(f"Total time: {time_beg + time_int + time_adv:.1f}s")
"""
    test_path = write_test_script("test_difficulties.py", test_difficulties_code)
    success = run_command(f"python {test_path}", "Step 5: Test difficulty conditioning")
    results["difficulty"] = success

    # Summary
    print(f"\n{'=' * 60}")
    print("SPIKE VALIDATION SUMMARY")
    print(f"{'=' * 60}")
    for step, status in results.items():
        print(f"{step:20s}: {'✓ PASS' if status else '✗ FAIL'}")

    all_pass = all(results.values())
    print(f"\n{'=' * 60}")
    print(f"DECISION: {'GO' if all_pass else 'NO-GO'}")
    print(f"{'=' * 60}")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
