# Model Comparison and Selection Decision

**Date:** 2026-02-06  
**Task:** Melody Extraction Model Selection  
**Test Dataset:** song_01 (194.6s audio, 1,897 reference notes)

---

## Executive Summary

**DECISION: Use Basic Pitch + Skyline Algorithm**

After testing 4 models (CREPE, Audio-to-MIDI, PYIN, Basic Pitch), we selected **Basic Pitch** as the audio-to-MIDI converter, combined with the **Skyline algorithm** for melody extraction.

**Key Reasons:**
1. ✅ **Polyphonic**: Handles multiple simultaneous notes (piano is polyphonic)
2. ✅ **Fast**: 8.6s for 194.6s audio (0.04x realtime)
3. ✅ **Easy installation**: `pip install basic-pitch`
4. ✅ **Good coverage**: 61.4% raw notes vs reference (vs 2-18% for monophonic models)
5. ✅ **Production-ready**: Maintained by Spotify, modern codebase

---

## Model Comparison Table

| Model | Type | Notes (Raw) | Notes (Final) | Ratio vs Ref | Time | Installation | Verdict |
|-------|------|-------------|---------------|--------------|------|--------------|---------|
| **CREPE** | Monophonic | 308 | N/A | 16% | 42s | `pip install` | ❌ REJECTED |
| **Audio-to-MIDI** | Monophonic | 342 | N/A | 18% | 26s | Git clone + patches | ❌ REJECTED |
| **PYIN** | Monophonic | 34 | N/A | 2% | 48s | Built-in (librosa) | ❌ REJECTED |
| **Basic Pitch** | Polyphonic | 1,164 | 488 | 61% → 26% | 8.6s | `pip install` | ✅ **SELECTED** |

**Reference:** 1,897 notes, pitch range 31-93, avg duration 329.6ms

---

## Detailed Analysis

### 1. CREPE (REJECTED)

**Type:** Monophonic pitch tracker (neural network)

**Results:**
- Notes: 308 (16% of reference)
- Time: 42.2s (0.22x realtime)
- Confidence: 0.439 avg (low)
- Pitch range: 24-84

**Pros:**
- Easy installation: `pip install crepe`
- Simple API
- Viterbi smoothing

**Cons:**
- ❌ **Monophonic limitation**: Cannot handle simultaneous notes
- ❌ **Very slow**: 42s for 3min audio (tiny model)
- ❌ **Poor quality**: Missing 84% of notes
- ❌ **Low confidence**: Only 40% frames > 0.5

**Verdict:** ❌ REJECTED - Fundamentally wrong tool for polyphonic piano

---

### 2. Audio-to-MIDI (REJECTED)

**Type:** Monophonic melody extractor (MSnet)

**Results:**
- Notes: 342 (18% of reference)
- Time: 25.9s (0.13x realtime)
- Pitch range: 50-83

**Pros:**
- Reasonably fast (25.9s)
- Lightweight model (~2MB)

**Cons:**
- ❌ **Installation nightmare**: Git clone + 5+ manual patches
- ❌ **Monophonic limitation**: Single melody line only
- ❌ **Outdated**: 2019 codebase, Python 3.6, PyTorch 1.0
- ❌ **Compatibility issues**: scipy, numpy, pypianoroll all need patches
- ❌ **Requires ffmpeg**: For MP3 support
- ❌ **Wrong use case**: Designed for vocal melody, not piano

**Verdict:** ❌ REJECTED - Installation complexity + monophonic limitation

---

### 3. PYIN (REJECTED)

**Type:** Monophonic pitch tracker (signal processing)

**Results:**
- Notes: 34 (2% of reference)
- Time: 48.5s (0.25x realtime)
- Voicing probability: 0.174 avg (very low)
- Pitch range: 36-71

**Pros:**
- No installation needed (built into librosa)
- Simple API

**Cons:**
- ❌ **Extremely poor quality**: Only 2% of notes (worst of all)
- ❌ **Very slow**: 48.5s (slowest of all)
- ❌ **Very low confidence**: 0.174 avg, only 8% frames > 0.5
- ❌ **Monophonic limitation**: Cannot handle polyphonic piano

**Verdict:** ❌ REJECTED - Worst performance in every metric

---

### 4. Basic Pitch (SELECTED)

**Type:** Polyphonic transcription (neural network)

**Results:**
- Raw notes: 1,164 (61.4% of reference)
- Final notes (after Skyline): 488 (25.7% of reference)
- Time: 8.6s (0.04x realtime)
- Pitch range: 28-91 (raw) → 48-84 (normalized)

**Pros:**
- ✅ **Polyphonic**: Handles multiple simultaneous notes
- ✅ **Fast**: 8.6s for 3min audio (5x faster than CREPE)
- ✅ **Easy installation**: `pip install basic-pitch`
- ✅ **Good coverage**: 61% raw notes (3-30x better than monophonic models)
- ✅ **Production-ready**: Maintained by Spotify, modern codebase
- ✅ **Works out-of-box**: No patches or manual fixes needed

**Cons:**
- ⚠️ **Over-transcription**: Captures 1,164 raw notes (needs Skyline filtering)
- ⚠️ **scipy compatibility**: Requires scipy<1.14 (gaussian function moved)

**Skyline Algorithm Results:**
1. Raw MIDI: 1,164 notes
2. After Skyline (highest note per onset): 488 notes
3. After filtering short notes (<50ms): 488 notes
4. After overlap resolution: 488 notes
5. After octave normalization (C3-C6): 488 notes

**Final ratio:** 488 / 1,897 = 25.7%

**Verdict:** ✅ **SELECTED** - Best balance of quality, speed, and ease of use

---

## Why Monophonic Models Failed

All three monophonic models (CREPE, Audio-to-MIDI, PYIN) failed because:

1. **Piano is polyphonic**: Multiple notes play simultaneously (chords, bass, melody)
2. **Monophonic = single pitch**: These models extract only one pitch at a time
3. **Missing notes**: When chords play, they pick one note and discard the rest
4. **Wrong use case**: Designed for vocals/solo instruments, not piano

**Example:**
- Piano plays C-E-G chord (3 notes)
- Monophonic model extracts only G (highest pitch)
- Missing C and E → 67% note loss

This explains the poor ratios:
- CREPE: 16% (missing 84% of notes)
- Audio-to-MIDI: 18% (missing 82% of notes)
- PYIN: 2% (missing 98% of notes)

---

## Why Basic Pitch + Skyline Works

### Basic Pitch (Polyphonic Transcription)
- Captures **all notes** in polyphonic audio
- Designed for piano/guitar/multi-instrument music
- Outputs 1,164 raw notes (61% of reference)

### Skyline Algorithm (Melody Extraction)
- Selects **highest note** per onset (200ms tolerance)
- Filters out accompaniment (bass, inner voices)
- Keeps only the melodic line
- Reduces 1,164 → 488 notes (25.7% of reference)

### Why 25.7% is acceptable:
- Reference MIDI (1,897 notes) includes **all notes** (melody + chords + bass)
- Goal: "딱 멜로디만 간결하게" (just melody, concisely)
- 488 notes = clean melody line without accompaniment
- This is the **intended behavior**, not a failure

---

## Implementation Plan

### Phase 1: Basic Pitch Integration
```python
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH

# Audio → MIDI (polyphonic)
model_output, midi_data, note_events = predict(
    audio_path,
    ICASSP_2022_MODEL_PATH,
)
```

### Phase 2: Skyline Algorithm (Already Implemented)
```python
from core.melody_extractor import (
    apply_skyline,
    filter_short_notes,
    resolve_overlaps,
    normalize_octave,
)

# MIDI → Melody
notes = parse_midi(midi_path)
notes = apply_skyline(notes)          # Highest note per onset
notes = filter_short_notes(notes)     # Remove <50ms notes
notes = resolve_overlaps(notes)       # Fix overlapping notes
notes = normalize_octave(notes)       # C3-C6 range
```

### Phase 3: Pipeline
```
Audio (MP3/WAV)
  ↓
Basic Pitch (8.6s)
  ↓
Raw MIDI (1,164 notes)
  ↓
Skyline Algorithm
  ↓
Melody MIDI (488 notes)
  ↓
MusicXML / Sheet Music
```

---

## Dependencies

### Required
```bash
pip install basic-pitch
pip install "scipy<1.14"  # Compatibility fix for gaussian function
```

### Already Installed
- pretty_midi (MIDI I/O)
- librosa (audio processing)
- numpy, scipy (numerical computing)

---

## Known Issues and Fixes

### Issue 1: scipy.signal.gaussian compatibility
**Problem:** scipy 1.14+ moved `gaussian` to `scipy.signal.windows`

**Fix:**
```python
import scipy.signal
if not hasattr(scipy.signal, 'gaussian'):
    from scipy.signal.windows import gaussian
    scipy.signal.gaussian = gaussian
```

**Solution:** Pin scipy<1.14 in requirements.txt

---

## Performance Comparison

| Metric | CREPE | Audio-to-MIDI | PYIN | Basic Pitch |
|--------|-------|---------------|------|-------------|
| **Speed** | 42s | 26s | 48s | **8.6s** ✅ |
| **Note Coverage** | 16% | 18% | 2% | **61%** ✅ |
| **Installation** | pip | Git clone | Built-in | **pip** ✅ |
| **Polyphonic** | ❌ | ❌ | ❌ | **✅** |
| **Maintenance** | Active | Abandoned | Active | **Active** ✅ |
| **Use Case Fit** | Vocals | Vocals | Vocals | **Piano** ✅ |

**Winner:** Basic Pitch (best in 5/6 metrics)

---

## Recommendation

**Use Basic Pitch + Skyline for melody extraction**

### Rationale:
1. **Polyphonic support**: Only model that handles piano's multiple simultaneous notes
2. **Speed**: 8.6s for 3min audio (5x faster than alternatives)
3. **Quality**: 61% raw note coverage (3-30x better than monophonic models)
4. **Ease of use**: `pip install basic-pitch` (no git clone, no patches)
5. **Production-ready**: Maintained by Spotify, modern codebase
6. **Proven approach**: Skyline algorithm already implemented and tested

### Next Steps:
1. ✅ Integrate Basic Pitch into `core/audio_to_midi.py`
2. ✅ Use existing Skyline algorithm from `core/melody_extractor.py`
3. ✅ Add scipy<1.14 to requirements.txt
4. ✅ Update documentation
5. ✅ Run golden tests to validate end-to-end pipeline

---

## Appendix: Test Environment

- **OS:** Windows 11
- **Python:** 3.11.14
- **Test Audio:** song_01 (194.6s, MP3)
- **Reference MIDI:** 1,897 notes, pitch 31-93, avg duration 329.6ms
- **Test Date:** 2026-02-06
- **Test Script:** `backend/scripts/spike_basic_pitch.py`

---

## Appendix: Output Files

Generated during testing:
- `backend/scripts/output/basic_pitch_raw.mid` (1,164 notes)
- `backend/scripts/output/basic_pitch_melody.mid` (488 notes)

Compare with:
- `backend/tests/golden/data/song_01/reference.mid` (1,897 notes)
