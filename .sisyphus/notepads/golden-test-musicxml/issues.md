
## [2026-02-04] Task 3: Baseline Test Execution - Critical Failures

### Test Results: 0/8 Passed (0% success rate)

All 8 songs failed with similarity <0.3%, far below 85% threshold.

### Critical Issue: Extreme Note Count Mismatch

**Under-generation (6 songs)**:
- song_01: 2040 ref → 109 gen (5.3%)
- song_02: 1720 ref → 34 gen (2.0%)
- song_03: 1696 ref → 58 gen (3.4%)
- song_05: 1387 ref → 115 gen (8.3%)
- song_06: 1839 ref → 72 gen (3.9%)
- song_08: 1620 ref → 74 gen (4.6%)

**Over-generation (2 songs)**:
- song_04: 1560 ref → 5856 gen (375%)
- song_07: 1647 ref → 7105 gen (431%)

### Root Cause: MusicXML Export Failure

**Repeated warning in all tests**:
```
WARNING  root:midi_to_musicxml.py:196 MusicXML export failed: 
In part (None), measure (1): Cannot convert inexpressible durations to MusicXML.. 
Retrying with simplified stream...
```

**Evidence**:
- Melody extraction works: 1164 MIDI → 926 melody notes (song_01)
- MusicXML export fails: 926 melody → **109 MusicXML notes** (88% loss)
- "Simplified stream" fallback is discarding notes instead of fixing them

### Hard Difficulty Analysis

Checked `sheet_hard.musicxml` for songs 06-08:
- song_06: 1756 notes (vs 1839 ref = 95% density)
- song_07: 4772 notes (vs 1647 ref = 290% density)
- song_08: 1340 notes (vs 1620 ref = 83% density)

**Observation**: Hard difficulty has much higher note counts, but:
- Still doesn't match reference note counts
- song_07 shows 290% over-generation (worse than medium's 431%)
- Suggests difficulty filtering is not the primary issue

### Hypothesis: Reference Difficulty Mismatch

Reference MXL files may be at **different difficulty levels** than generated medium sheets:
- Some references may be "easy" (low note density)
- Some references may be "hard" (high note density)
- Generated "medium" doesn't align with reference difficulty

**Need to verify**: Parse reference.mxl to determine actual difficulty level.

### Blocking Issues

1. **MusicXML export failure** (backend/core/midi_to_musicxml.py:196)
   - Cannot convert inexpressible durations
   - Simplified stream fallback loses 88-90% of notes
   - Must fix before meaningful comparison

2. **Difficulty level unknown**
   - Reference MXL difficulty not documented
   - Generated medium may not match reference
   - Need to test with all 3 difficulties (easy/medium/hard)

3. **Matching algorithm ineffective**
   - Even with few notes, matching rate <6%
   - Suggests timing/pitch/duration misalignment
   - May need wider tolerances or different algorithm

### Next Actions Required

**MUST DO**:
1. Investigate `midi_to_musicxml.py:196` - why is duration conversion failing?
2. Parse reference.mxl files to determine their actual note density/difficulty
3. Test comparison with `sheet_hard.musicxml` instead of medium
4. Add debug logging to track note loss at each pipeline stage

**DO NOT**:
- Lower 85% threshold without fixing root cause
- Modify reference.mxl files
- Skip MusicXML export investigation

### Impact

- **Baseline cannot be established** until MusicXML export is fixed
- **85% threshold is unrealistic** with current pipeline
- **Estimated 2.5-3.5 days** of debugging required to reach production-ready state

