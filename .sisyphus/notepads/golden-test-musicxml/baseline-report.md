# Baseline Comparison Report

## Test Execution
- **Date**: 2026-02-04 09:33 KST
- **Command**: `docker compose exec backend pytest tests/golden/test_golden.py::TestGoldenCompare -v --tb=short`
- **Threshold**: 85%
- **Environment**: Docker backend container (Python 3.11.14)

## Results Summary

| Song | Similarity | Ref Notes | Gen Notes | Matched | Status | Time |
|------|------------|-----------|-----------|---------|--------|------|
| song_01 | 0.29% | 2040 | 109 | 6 | ❌ FAIL | 87.3s |
| song_02 | 0.12% | 1720 | 34 | 2 | ❌ FAIL | 91.1s |
| song_03 | 0.00% | 1696 | 58 | 0 | ❌ FAIL | 89.0s |
| song_04 | 0.02% | 1560 | 5856 | 1 | ❌ FAIL | 104.4s |
| song_05 | 0.22% | 1387 | 115 | 3 | ❌ FAIL | 82.9s |
| song_06 | 0.27% | 1839 | 72 | 5 | ❌ FAIL | 81.5s |
| song_07 | 0.10% | 1647 | 7105 | 7 | ❌ FAIL | 97.0s |
| song_08 | 0.12% | 1620 | 74 | 2 | ❌ FAIL | 80.8s |

## Pass Rate
- **Passed**: 0/8 (0%)
- **Failed**: 8/8 (100%)
- **Average Similarity**: 0.14%
- **Average Processing Time**: 89.2s

## Critical Issues Identified

### 1. Severe Note Count Mismatch

All 8 songs show **extreme discrepancy** between reference and generated note counts:

- **song_01**: 2040 ref → 109 gen (5.3% of expected)
- **song_02**: 1720 ref → 34 gen (2.0% of expected)
- **song_03**: 1696 ref → 58 gen (3.4% of expected)
- **song_04**: 1560 ref → 5856 gen (375% of expected - OVER-GENERATION)
- **song_05**: 1387 ref → 115 gen (8.3% of expected)
- **song_06**: 1839 ref → 72 gen (3.9% of expected)
- **song_07**: 1647 ref → 7105 gen (431% of expected - OVER-GENERATION)
- **song_08**: 1620 ref → 74 gen (4.6% of expected)

**Pattern Analysis**:
- 6 songs: Severe **under-generation** (2-8% of expected notes)
- 2 songs (song_04, song_07): Severe **over-generation** (375-431% of expected notes)

### 2. MusicXML Export Warnings

All tests show repeated warnings:
```
WARNING  root:midi_to_musicxml.py:196 MusicXML export failed: 
In part (None), measure (1): Cannot convert inexpressible durations to MusicXML.. 
Retrying with simplified stream...
```

This warning appears **3 times per test** (for easy, medium, hard difficulties), indicating:
- Duration quantization issues in MIDI → MusicXML conversion
- Possible loss of note information during "simplified stream" fallback

### 3. Matching Algorithm Ineffectiveness

Even with the few notes generated, matching rate is extremely low:
- song_03: 0/58 notes matched (0%)
- song_04: 1/1560 notes matched (0.06%)
- song_01: 6/109 notes matched (5.5%)

This suggests:
- Timing/onset misalignment between reference and generated
- Pitch differences
- Duration quantization errors

## Root Cause Analysis

### Hypothesis 1: Melody Extraction Over-Filtering
The pipeline shows:
- **song_01**: 1164 MIDI notes → 926 melody notes → **109 MusicXML notes**
- **song_02**: 356 MIDI notes → 320 melody notes → **34 MusicXML notes**

**88-90% note loss** occurs during MusicXML generation, not melody extraction.

### Hypothesis 2: MusicXML Conversion Failure
The "Cannot convert inexpressible durations" warning suggests:
- music21's `stream.write('musicxml')` is rejecting most notes
- "Simplified stream" fallback is discarding notes instead of fixing them
- Duration quantization in `midi_to_musicxml.py` is insufficient

### Hypothesis 3: Wrong Difficulty Level
The test uses `sheet_medium.musicxml`, but:
- Medium difficulty may apply aggressive note filtering
- Reference MXL files may be at a different difficulty level
- Need to verify reference difficulty vs. generated difficulty

## Recommendations

### Immediate Actions (Priority 1)

1. **Investigate MusicXML Export Failure**
   - Check `backend/core/midi_to_musicxml.py` line 196
   - Review "simplified stream" fallback logic
   - Verify duration quantization is working correctly
   - Test with `sheet_easy.musicxml` and `sheet_hard.musicxml` to compare note counts

2. **Verify Reference Difficulty Level**
   - Parse reference.mxl files to check their actual note density
   - Compare reference note count with expected difficulty level
   - Determine if reference is easy/medium/hard difficulty

3. **Debug Note Loss Pipeline**
   - Add logging to track note count at each stage:
     - After MIDI generation
     - After melody extraction
     - After difficulty filtering
     - After MusicXML export
   - Identify exact stage where 88-90% notes are lost

### Medium-Term Actions (Priority 2)

4. **Test with Hard Difficulty**
   - Run comparison using `sheet_hard.musicxml` instead of medium
   - Hard difficulty should have higher note density
   - May improve similarity if reference is also high-density

5. **Review Duration Quantization**
   - Check if duration quantization is too aggressive
   - Verify time signature handling (all songs show 4/4 detection)
   - Test with different quantization tolerances

6. **Improve Matching Algorithm**
   - Current tolerance: onset ±0.1 quarterLength, duration ±20%
   - May need to increase tolerances for initial baseline
   - Consider tempo-aware tolerance (faster songs need wider windows)

### Long-Term Actions (Priority 3)

7. **Baseline Adjustment**
   - 85% threshold is unrealistic with current pipeline
   - Establish realistic baseline after fixing MusicXML export
   - Consider phased thresholds: 30% → 50% → 70% → 85%

8. **Pipeline Validation**
   - Create unit tests for each pipeline stage
   - Validate MIDI → MusicXML conversion independently
   - Test with synthetic MIDI files (known note counts)

## Next Steps

**MUST DO FIRST**:
1. Inspect `backend/core/midi_to_musicxml.py:196` to understand the warning
2. Check generated `sheet_medium.musicxml` files to see what's actually in them
3. Compare with `sheet_easy.musicxml` and `sheet_hard.musicxml` note counts

**DO NOT**:
- Lower the 85% threshold without fixing the root cause
- Modify reference.mxl files
- Skip the MusicXML export investigation

## Conclusion

**All 8 songs failed with <0.3% similarity** due to:
1. **Critical MusicXML export failure** causing 88-90% note loss
2. **Possible difficulty level mismatch** between reference and generated
3. **Ineffective note matching** even for the few notes that survive

The pipeline is **not production-ready**. The MusicXML export issue must be resolved before meaningful comparison can occur.

**Estimated effort to reach 85% threshold**: 
- Fix MusicXML export: 1-2 days
- Verify difficulty alignment: 0.5 days  
- Tune matching algorithm: 1 day
- **Total**: 2.5-3.5 days of focused debugging

---

*Report generated: 2026-02-04 09:45 KST*
