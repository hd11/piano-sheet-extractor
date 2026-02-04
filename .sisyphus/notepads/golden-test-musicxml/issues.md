
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


## [2026-02-04] Alignment diagnosis (song_01) — similarity near-zero is NOT a seconds→quarterLength bug

Ran `backend/scripts/diagnose_alignment.py` (output saved under `backend/scripts/_diagnose_out/song_01/diagnose_alignment.txt`).

### Key evidence
- **Tempo/timebase looks consistent**:
  - `bpm_ref(from MXL)=122.0`
  - `bpm_gen(from XML)=123.046875`
  - `bpm_analysis(used for conversion)=123.05`
  - Both scores start at `first_onset_ql=0.000` (no obvious constant offset bug).
- **Generated file contains chord symbols that get counted as notes**:
  - The first generated “notes” are `p=45,48,52` at `t=0.000` with `dur_ql=0.000`, which matches the default voicing of an **A-minor chord (A2-C3-E3)**.
  - This strongly suggests `music21.harmony.ChordSymbol` entries (inserted via `add_chord_symbols()`) are being returned by `score.flatten().notes` and then treated as `Chord` in `_extract_notes()`.
  - These chord-symbol-derived pitches have **duration 0**, so they will never match reference notes under duration tolerance, but they **inflate gen note count and pollute ordering/pitch statistics**.
- **Pitch/range mismatch indicates we’re not comparing like-for-like**:
  - `ref_pitch_range=35..93` vs `gen_pitch_range=45..79` (generated is constrained/simplified; reference includes much lower + higher notes).
- **Score span mismatch**:
  - `ref_span_ql=564` vs `gen_span_ql=399` (generated roughly matches ~192s at ~123 BPM; reference’s timeline appears substantially longer in quarterLength terms).

### Working conclusion
The extremely low similarity (0.05–0.33%) is better explained by **representation mismatch** (generated includes chord symbols; reference likely doesn’t or encodes harmony differently) and **content mismatch** (reference appears to be a fuller arrangement across a wider range) than by a BPM/seconds→quarterLength conversion bug.


## [2026-02-04] Comparator fix applied: skip music21.harmony.ChordSymbol in _extract_notes

- Patched `backend/core/musicxml_comparator.py` to `continue` when element is `music21.harmony.ChordSymbol` (ChordSymbol is a subclass of `music21.chord.Chord`).
- Verification on `song_01` generated `sheet_medium.musicxml`:
  - Raw `gen_score.flatten().notes` count: **449**; first types include many `ChordSymbol`.
  - Comparator-extracted gen notes: **115** (down from 1117 when chord symbols were miscounted).
  - Zero-duration notes after filtering: **0**.
  - `compare_musicxml(song_01)` now reports: matched=2, ref=2040, gen=115, similarity≈**0.098%**.

Note: the standalone diagnostic script still shows chord-symbol entries because it directly prints `flatten().notes` from the generated MusicXML; comparator extraction is now clean.

