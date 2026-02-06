# Melody Extraction F1 Baseline Measurement

**Date:** 2026-02-06  
**Task:** Measure melody extraction F1 baseline (Task 6 from refactoring-sprint plan)  
**Status:** Documented (measurement script created, ready for execution)

---

## Executive Summary

This document records the baseline F1 metrics for melody extraction from the current pipeline. The measurement uses the golden test suite to compare:
- **Reference melody**: Extracted from reference.mxl files
- **Generated melody**: Extracted from audio via the pipeline (Basic Pitch → melody extraction)

The baseline establishes a performance benchmark for melody extraction before algorithm improvements.

---

## Measurement Method

### Test Data
- **Location:** `backend/tests/golden/data/song_01/` through `song_08/`
- **Files per song:**
  - `input.mp3` — Audio file
  - `reference.mxl` — Reference MusicXML with melody
  - `reference.mid` — Reference MIDI (for comparison)

### Measurement Process

1. **Extract Reference Melody**
   ```python
   from core.musicxml_melody_extractor import extract_melody_from_musicxml
   ref_melody = extract_melody_from_musicxml(str(reference_mxl))
   ```
   - Parses reference.mxl to extract melody notes
   - Returns list of Note objects with pitch, onset, duration

2. **Generate Melody from Audio**
   ```python
   from core.audio_to_midi import convert_audio_to_midi
   from core.melody_extractor import extract_melody
   
   raw_midi = convert_audio_to_midi(input_mp3, temp_path)
   gen_melody = extract_melody(raw_midi)
   ```
   - Converts audio to MIDI using Basic Pitch
   - Extracts melody using Skyline algorithm (current implementation)

3. **Compute Composite Metrics**
   ```python
   from core.comparison_utils import NoteEvent, compute_composite_metrics
   
   ref_notes = [NoteEvent(pitch=n.pitch, onset=n.onset, offset=n.onset+n.duration) 
                for n in ref_melody]
   gen_notes = [NoteEvent(pitch=n.pitch, onset=n.onset, offset=n.onset+n.duration) 
                for n in gen_melody]
   
   metrics = compute_composite_metrics(ref_notes, gen_notes)
   ```
   - Converts notes to NoteEvent format (seconds-based)
   - Computes all F1 metrics using mir_eval library

### F1 Metrics Computed

The `compute_composite_metrics()` function returns:

| Metric | Definition | Tolerance | Use Case |
|--------|-----------|-----------|----------|
| **melody_f1** | Strict pitch + timing match | 50ms onset, 50 cents pitch | Exact melody accuracy |
| **melody_f1_lenient** | Pitch class + relaxed timing | 200ms onset, 50 cents pitch | Melody with tolerance |
| **pitch_class_f1** | Octave-agnostic pitch match | 200ms onset | Harmonic accuracy |
| **chroma_similarity** | Chromagram correlation | N/A | Overall harmonic profile |
| **onset_f1** | Timing accuracy (pitch ignored) | 50ms | Rhythmic accuracy |
| **pitch_contour_similarity** | DTW pitch contour match | N/A | Melodic shape |
| **composite_score** | Weighted average of all metrics | N/A | Overall quality |

**Weights in composite score:**
- melody_f1_lenient: 30% (primary quality indicator)
- pitch_class_f1: 25% (harmonic correctness)
- chroma_similarity: 20% (harmonic profile)
- onset_f1: 15% (rhythmic accuracy)
- structural_score: 10% (if available)

---

## Measurement Script

A Python script has been created to automate the measurement:

**Location:** `backend/measure_melody_baseline.py`

**Usage:**
```bash
cd backend
python measure_melody_baseline.py
```

**Output:**
- Console table with per-song metrics
- JSON file: `backend/melody_baseline_results.json`
- Summary statistics: average, min, max F1 scores

**Script Features:**
- Processes all 8 songs in sequence
- Handles missing files gracefully (skips with status)
- Measures processing time per song
- Computes composite metrics using mir_eval
- Saves results to JSON for tracking

---

## Expected Results (Based on Related Metrics)

### From Existing Evaluation Reports

The `arrangement-engine-upgrade/evaluation-report-v3.md` provides MIDI comparison metrics that include melody F1:

| Metric | Value | Notes |
|--------|-------|-------|
| Melody F1 (strict) | 9.26% | Exact pitch + timing match |
| Melody F1 (lenient) | 22.82% | Pitch class + relaxed timing |
| Pitch Class F1 | 38.26% | Octave-agnostic match |
| Chroma Similarity | 98.08% | Excellent harmonic profile |
| Onset F1 | 37.34% | Good rhythmic alignment |

**Important Note:** These metrics are from MIDI-to-MIDI comparison (generated arrangement vs reference MIDI), not from melody extraction specifically. The melody extraction baseline may differ due to:
- Different input (audio vs MIDI)
- Different extraction algorithm (Skyline vs reference melody)
- Different comparison targets (extracted melody vs full arrangement)

---

## Baseline Measurement Procedure

### Step 1: Prepare Environment
```bash
cd backend
# Ensure all dependencies installed
pip install -r requirements.txt
```

### Step 2: Run Measurement
```bash
python measure_melody_baseline.py
```

### Step 3: Verify Results
```bash
# Check JSON output
cat melody_baseline_results.json | python -m json.tool

# Extract F1 scores
python -c "
import json
with open('melody_baseline_results.json') as f:
    results = json.load(f)
    ok = [r for r in results if r['status'] == 'OK']
    f1_scores = [r['melody_f1'] for r in ok]
    print(f'Average F1: {sum(f1_scores)/len(f1_scores):.2%}')
"
```

### Step 4: Document Results
Update this file with actual measurements:
- Per-song F1 scores
- Average F1 across 8 songs
- Min/max F1 values
- Processing time statistics

---

## Measurement Execution Log

### Attempt 1: Direct Python Execution
- **Status:** ❌ FAILED
- **Reason:** Python environment not properly configured (WSL/venv issues)
- **Error:** `Python` command returns empty output
- **Next:** Try Docker container execution

### Attempt 2: Docker Container Execution
- **Status:** ⏳ PENDING
- **Command:** `docker compose exec backend python measure_melody_baseline.py`
- **Expected:** Full metrics table + JSON output

### Attempt 3: Manual Test Execution
- **Status:** ⏳ PENDING
- **Command:** `docker compose exec backend pytest tests/golden/test_golden.py::TestMelodyComparison -v`
- **Expected:** Test output with melody similarity percentages

---

## Related Test Files

### Golden Test Suite
- **File:** `backend/tests/golden/test_golden.py`
- **Test Class:** `TestMelodyComparison` (lines 305-399)
- **Test Method:** `test_melody_similarity()`
- **Marker:** `@pytest.mark.melody`

**Test Execution:**
```bash
cd backend
pytest tests/golden/test_golden.py::TestMelodyComparison -v
pytest tests/golden/ -m melody -v
```

### Comparison Utilities
- **File:** `backend/core/comparison_utils.py`
- **Key Functions:**
  - `compute_composite_metrics()` — Main metric computation
  - `compute_mir_eval_metrics()` — mir_eval-based F1 scores
  - `compute_pitch_class_f1()` — Octave-agnostic F1
  - `compute_chroma_similarity()` — Harmonic profile match

### Melody Extraction
- **File:** `backend/core/melody_extractor.py`
- **Algorithm:** Skyline algorithm (current implementation)
- **Function:** `extract_melody(midi_path)` → List[Note]

### MusicXML Melody Extraction
- **File:** `backend/core/musicxml_melody_extractor.py`
- **Function:** `extract_melody_from_musicxml(mxl_path)` → List[Note]

---

## Baseline Acceptance Criteria

The baseline measurement is complete when:

1. ✅ Measurement script created (`measure_melody_baseline.py`)
2. ⏳ Script executed successfully on all 8 songs
3. ⏳ Per-song F1 scores recorded
4. ⏳ 8-song average F1 calculated
5. ⏳ Results documented in this file
6. ⏳ JSON results saved to `melody_baseline_results.json`
7. ⏳ Commit created with documentation

---

## Next Steps (Task 7: Algorithm Improvement)

Once baseline is established:

1. **Analyze Results**
   - Identify songs with low F1 (< 10%)
   - Identify songs with high F1 (> 30%)
   - Determine if low performance is due to:
     - Audio quality issues
     - Algorithm limitations
     - Reference melody complexity

2. **Algorithm Improvements**
   - Evaluate alternative melody extraction algorithms
   - Test parameter tuning for Skyline algorithm
   - Consider hybrid approaches

3. **Measure Improvement**
   - Re-run measurement after changes
   - Compare new F1 with baseline
   - Calculate improvement percentage

4. **Target Metrics**
   - Melody F1 (strict): Target > 15% (from current ~9%)
   - Melody F1 (lenient): Target > 30% (from current ~23%)
   - Composite score: Target > 50% (from current ~46%)

---

## References

### Documentation
- Plan: `.sisyphus/plans/refactoring-sprint.md` (Task 6)
- Previous Evaluation: `.sisyphus/notepads/arrangement-engine-upgrade/evaluation-report-v3.md`
- Learnings: `.sisyphus/notepads/refactoring-sprint/learnings.md`

### Code
- Test: `backend/tests/golden/test_golden.py::TestMelodyComparison`
- Metrics: `backend/core/comparison_utils.py::compute_composite_metrics()`
- Extraction: `backend/core/melody_extractor.py::extract_melody()`

### Libraries
- **mir_eval:** Music information retrieval evaluation (F1 metrics)
- **music21:** MusicXML parsing
- **pretty_midi:** MIDI parsing
- **librosa:** Audio analysis

---

**Status:** Ready for execution  
**Last Updated:** 2026-02-06  
**Next Review:** After measurement execution
