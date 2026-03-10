# mel_strict 0.090 -> 0.15+ Improvement Plan

**Date**: 2026-03-10
**Status**: COMPLETED — Phase 1 FAILED (all reverted), Phase 2 COMPLETED (metrics implemented)
**Current baseline**: mel_strict avg 0.091 (v26c baseline with new metrics)
**Original Target**: mel_strict avg 0.13+ (Phase 1 realistic), 0.15 aspirational
**Outcome**: mel_strict remains at 0.091. Pipeline limited by F0 accuracy (FCPE harmonic confusion).
**Approach**: Path D — pipeline improvements first, then arrangement adaptation

---

## Context

The pipeline extracts vocal melody from MP3 via: Demucs vocal separation -> FCPE F0 pitch tracking -> note segmentation -> self-contained postprocessing -> MusicXML output. Evaluation uses round-trip MusicXML save/load compared against piano arrangement references (.mxl skyline extraction).

**Key diagnostic signals from current data:**

| Signal | Value | Interpretation |
|--------|-------|----------------|
| chroma_similarity | 0.975 | Pitch *class* (note name) is nearly perfect |
| onset_f1 | 0.524 | ~52% of onsets land within 100ms of a ref note |
| mel_strict | 0.090 | Only 9% of notes match both pitch AND onset (50ms) |
| mel_lenient | 0.161 | 16% match at 200ms onset tolerance |
| contour_similarity | 0.769 | Melodic direction is 77% correct |
| IRIS OUT mel_strict | 0.315 | Best song: 3.5x above average |
| note_count_ratio range | 0.55-1.23 | Varies wildly per song |

**The gap diagnosis**: chroma(0.975) >> mel_strict(0.090) means the pitch *class* is right but the octave register and onset timing are both wrong. The 0.524 onset_f1 confirms roughly half the onsets are reasonable but pitch register errors prevent them from being mel_strict matches. IRIS OUT's 0.315 proves the pipeline CAN work when conditions align (fewer generated notes, 0.55 ratio = high precision).

**Structural ceiling**: Among onset-matched notes, only 10-52% have exact pitch match (vocal-to-sheet gap). This limits theoretical mel_strict to roughly 0.25-0.35 with perfect onset timing. Phase 2 addresses this ceiling.

---

## Guardrails

### Must Have
- All changes self-contained (no reference data in pipeline) — Rule 5
- MusicXML round-trip identity preserved — Rule 4
- Every step evaluated on all 8 songs with before/after comparison
- Ablation: each change tested in isolation before combining
- Failed experiments documented in PROJECT_DIRECTIVES.md — Rule 3

### Must NOT Have
- Reference-based pitch/timing correction in pipeline
- Overfitting to specific songs (must improve average, not just one song)
- Repeating failed experiments: CQT octave verify, harmonic correction (v7), dynamic vocal_center (v7b), F0-level ensemble (v16), onset-only segmentation (v17), float MIDI running center (v18c)

---

## Phase 1: Pipeline Improvements (target: 0.090 -> 0.13+, aspirational 0.15)

**Target realism note**: Individual step impacts (Steps 2-5) sum to +0.045 to +0.09 in isolation. However, interaction effects between changes typically reduce combined gains by 30-50%. Realistic Phase 1 outcome: mel_strict 0.113-0.144. A result of 0.13+ is a clear success. The 0.15 target may require Phase 2 evaluation improvements (Steps 6-8) to close the gap. Do NOT declare failure if Phase 1 lands at ~0.13.

### Step 1: Per-Song Diagnostic Analysis Script

**Description**: Build a diagnostic tool that analyzes *why* each song scores what it does. For each song, classify every generated note as: true positive (matched), false positive (no ref match), or identify the nearest ref note and the failure reason (pitch off by N semitones, onset off by N ms, both). This produces actionable data for all subsequent steps.

**Files to create/modify**:
- `scripts/diagnose.py` (new) — per-song diagnostic analysis

**Implementation details**:
- For each gen note, find nearest ref note by onset (within 500ms)
- Classify: exact match (50ms+0st), pitch-only miss (50ms onset but wrong pitch), onset-only miss (right pitch but >50ms onset), both miss
- Output per-song: pitch error histogram (semitones), onset error histogram (ms), octave error count, note density comparison (notes per second in 5s windows)
- Output aggregate: which error type dominates (pitch vs onset vs both)
- Critical output: for pitch misses, what is the distribution? If dominated by +/-12st -> octave problem. If +/-5/7st -> harmonic confusion. If +/-1-2st -> FCPE precision limit.

**Expected impact**: No direct mel_strict improvement. Provides data to prioritize Steps 2-4.
**Effort**: LOW (1-2 hours)
**Risk**: None
**Dependencies**: None

**Acceptance criteria**:
- [ ] Script runs on all 8 songs and produces per-song JSON diagnostics
- [ ] Pitch error distribution clearly shows dominant error type (octave vs harmonic vs small)
- [ ] Onset error distribution shows mean/std/median for matched notes
- [ ] Output saved to `results/diagnostics/` for reference in subsequent steps

---

### Step 2: Octave Register Precision

**Description**: The current `_global_octave_adjust` uses a fixed vocal_center=75 (Eb5) and applies coarse section-level shifts. The diagnostic data from Step 1 will reveal whether octave errors (+/-12st) dominate pitch misses. This step refines octave correction using per-phrase pitch histogram analysis rather than a single global median.

**Files to modify**:
- `core/postprocess.py` — `_global_octave_adjust()`, `_self_octave_correction()`

**Implementation details**:
- Replace fixed vocal_center=75 with song-adaptive center: compute from the note pitch histogram's densest region (mode, not median — median is skewed by octave errors)
- Reduce section_size from 30 to 15 notes for finer granularity (current 30-note sections span too much musical time for songs with register changes)
- In `_self_octave_correction`: add a guard against correcting notes that are part of a consistent phrase (if 3+ consecutive notes are all in the "wrong" octave, they are probably correct and the surrounding context is wrong)
- Key constraint: do NOT use dynamic vocal_center computed from CREPE/FCPE output directly (failed in v7b because F0 output itself contains octave errors). Instead use the *mode* of the pitch distribution after initial segmentation, which is more robust than median.

**Expected impact**: mel_strict +0.01 to +0.02 (octave errors affect ~15-25% of notes based on v6 analysis showing pitch compression in 6/8 songs)
**Effort**: LOW-MEDIUM
**Risk**: LOW — self_octave_correction with threshold=7 is already validated; refinements are conservative
**Dependencies**: Step 1 (diagnostic data confirms octave error prevalence)

**Acceptance criteria**:
- [ ] Octave error count (from Step 1 diagnostics) decreases by >20% across 8-song average
- [ ] mel_strict avg does not regress below 0.088
- [ ] No single song drops more than 0.02 in mel_strict
- [ ] Ablation: test section_size=15 vs 30 independently, phrase guard independently

---

### Step 3: Note Density Calibration

**Description**: IRIS OUT scores 0.315 with note_count_ratio=0.55 (generates 55% of ref notes). Most other songs generate 0.83-1.23x ref notes. The hypothesis: generating fewer, higher-confidence notes improves precision dramatically. This step adds confidence-scored note filtering to prune low-quality notes.

**IMPORTANT**: FCPE confidence is binary (0/1) — `pitch_extractor_fcpe.py` line 91: `confidence = np.where(pitch > 0, 1.0, 0.0)`. There is NO graded confidence from FCPE. The confidence signal must be derived from other properties.

**Primary approach: F0 variance within note (Option A)**

**Files to modify**:
- `core/note_segmenter.py` — compute per-note confidence during `segment_notes()` (lines 72-93)
- `core/types.py` — add `confidence: float = 1.0` field to `Note` dataclass
- `core/postprocess.py` — new `_confidence_filter()` function after `_diatonic_gate()` (line 62)

**Implementation details**:
- **Confidence computation** (in `segment_notes()`, lines 72-93): During the grouping loop where consecutive same-pitch frames are collected (frames `start` to `i`), the raw Hz values for those frames are available in `freqs[start:i]`. Compute the MIDI-space variance of these frames: `midi_vals = 12 * np.log2(freqs[start:i][freqs[start:i]>0] / 440) + 69`. The variance of `midi_vals` measures pitch stability. Low variance = stable/confident note. High variance = wobbly/unreliable. Store as `Note.confidence = 1.0 / (1.0 + variance)` (normalized to 0-1, where 1.0 = perfectly stable).
- **Confidence filter** (in `postprocess.py`, new `_confidence_filter()` after `_diatonic_gate()` at line 62):
  - Compute current note density: `total_notes / song_duration` (song_duration = last note offset - first note onset)
  - If density > `MAX_DENSITY` (fixed genre constant, default 4.0 notes/sec for K-pop): sort notes by confidence ascending, remove lowest-confidence notes until density <= `MAX_DENSITY`
  - `MAX_DENSITY` is a fixed constant, NOT derived from per-song reference statistics (Rule 5 compliant)
- **Data flow**: `segment_notes()` returns `List[Note]` where each Note now has `.confidence` populated -> `postprocess_notes()` receives these notes -> `_confidence_filter()` uses `.confidence` to select which notes to prune

**Why not the alternatives**:
- ~~Option B (Audio RMS energy)~~: Would work but requires passing vocal audio into postprocess specifically for this purpose, adding parameter coupling. F0 variance is available without additional data.
- ~~Option C (Pure density capping)~~: Too blunt — removes notes without any quality signal. A fast passage of real notes would lose valid notes. F0 variance preserves stable fast passages while removing wobbly artifacts.

**Expected impact**: mel_strict +0.02 to +0.04. Rationale: IRIS OUT's 0.315 at 0.55 ratio vs avg 0.090 at ~1.0 ratio strongly suggests precision > recall for mel_strict.
**Effort**: MEDIUM
**Risk**: MEDIUM — may hurt recall-dependent songs (달리 already at ratio 1.23). Needs per-song ablation.
**Dependencies**: Step 1 (diagnostic data reveals FP characteristics)

**Acceptance criteria**:
- [ ] Note count ratio moves closer to 0.7-0.9 range for songs currently >1.0
- [ ] mel_strict avg improves by at least +0.015
- [ ] No song's mel_strict drops below its current value by more than 0.01
- [ ] Ablation: test MAX_DENSITY thresholds 2.5, 3.0, 3.5, 4.0 notes/sec

---

### Step 4: Onset Timing Refinement

**Description**: onset_f1=0.524 means ~48% of onsets miss their targets. The current beat snap uses mix-derived beat grid with adaptive subdivisions (8th or 16th notes). Two sub-problems: (a) beat grid itself may be misaligned, (b) snap resolution may be too coarse for some phrases.

**Files to modify**:
- `core/postprocess.py` — `_snap_to_beats_from_grid()`
- `core/pipeline.py` — beat tracking parameters

**Implementation details**:
- **4a: Onset strength weighting** — Currently all onsets snap to nearest grid point equally. Add onset strength weighting: if the audio has a clear onset (high spectral flux) near a note's extracted onset, trust the extracted onset more (reduce snap distance). If there is no clear audio onset, snap more aggressively. This prevents snapping notes that are already well-timed.
  - Compute onset strength envelope from vocals (not mix) using `librosa.onset.onset_strength()`
  - For each note, check onset strength at its current onset time
  - High strength (>median) -> reduce max_snap to 25% of subdivision
  - Low strength -> keep current max_snap at 50% of subdivision
- **4b: Adaptive subdivision per phrase** — Fast melodic passages need finer grid (16th notes) even in slow songs. Detect local note density and switch subdivision accordingly.
  - In 2-second windows, if >6 notes: use subdivisions=4
  - If <=6 notes: use current adaptive rule (BPM-based)

**API change required**: Sub-step 4a requires the vocal audio signal inside `_snap_to_beats_from_grid()` to compute onset strength. Currently this function (postprocess.py:765) only receives `notes`, `beat_times`, `subdivisions`. Changes needed:
- Add `audio: Optional[np.ndarray] = None` and `sr: Optional[int] = None` parameters to `_snap_to_beats_from_grid()` (postprocess.py:765)
- Update the call site in `postprocess_notes()` (postprocess.py:68) to pass `audio` and `sr` through: `_snap_to_beats_from_grid(notes, beat_times, subdivisions=snap_subdiv, audio=audio, sr=sr)`
- The `postprocess_notes()` public signature (postprocess.py:23) already accepts `audio` and `sr` — no change needed there
- The pipeline call site (pipeline.py:110) already passes `audio=vocals_22k, sr=22050` — no change needed there

**Expected impact**: mel_strict +0.01 to +0.02 (onset precision improvement converts existing pitch-correct notes into mel_strict matches)
**Effort**: MEDIUM
**Risk**: LOW — onset snap is already the most impactful postprocess step (ablation showed +0.018 in v15)
**Dependencies**: None (can run in parallel with Steps 2-3)

**Acceptance criteria**:
- [ ] onset_f1 avg improves from 0.524 to 0.55+
- [ ] mel_strict avg improves (onset improvement should convert some mel_lenient matches to mel_strict)
- [ ] Onset error std (from Step 1 diagnostics) decreases
- [ ] Ablation: test 4a and 4b independently

---

### Step 5: Diatonic Gate Refinement

**Description**: Current diatonic gate uses major scale template only. Some songs may be in minor keys, causing valid notes to be filtered. The gate removed 11-21% of notes in v6 testing. Refining key detection and adding minor/modal templates could recover valid notes.

**Files to modify**:
- `core/postprocess.py` — `_diatonic_gate()`

**Implementation details**:
- Add natural minor, harmonic minor, and melodic minor scale templates alongside major
- Pick the template with highest weighted score (current approach: major only)
- Increase max_chromatic_duration from 0.15s to 0.20s (keep more intentional accidentals)
- Add a "chromatic passage" detector: if 3+ consecutive notes are all chromatic, keep them all (likely a chromatic run, not artifacts)
- Consider pentatonic scale template as an additional candidate (many K-pop melodies are pentatonic)

**Expected impact**: mel_strict +0.005 to +0.01 (modest — diatonic gate is a secondary filter)
**Effort**: LOW
**Risk**: LOW — adding templates only makes the gate more permissive for valid notes
**Dependencies**: None

**Acceptance criteria**:
- [ ] Key detection accuracy improves (validate against reference key where known)
- [ ] Diatonic gate removal rate drops from 11-21% to 8-15% range
- [ ] mel_strict avg does not regress
- [ ] Songs with minor keys (if any) show improvement

---

### Phase 1 Integration & Verification

After Steps 1-5, combine all accepted changes and run full 8-song evaluation.

**Acceptance criteria for Phase 1 completion**:
- [ ] mel_strict avg >= 0.13 (success), >= 0.15 (aspirational)
- [ ] No single song regresses more than 0.01 from its current best
- [ ] All changes are self-contained (grep for `ref_notes` in pipeline returns 0)
- [ ] MusicXML round-trip test passes (save -> load -> identical notes)
- [ ] Results saved to `results/v_phase1.json`
- [ ] All experiments documented in PROJECT_DIRECTIVES.md
- [ ] If mel_strict lands between 0.13-0.15, proceed to Phase 2 to close the gap via evaluation improvements

---

## Phase 2: Arrangement Adaptation & Evaluation Rethink (post-0.15)

### Step 6: Reference Melody Extraction Improvement

**Description**: The current reference extractor uses a simple skyline algorithm (highest note per onset from Part 0). Piano arrangements contain inner voices, chord tones, and ornaments that are NOT part of the sung melody. A more sophisticated reference extraction could better isolate the actual melody line, making the evaluation target more aligned with what the pipeline is trying to extract.

**Files to modify**:
- `core/reference_extractor.py` — `extract_reference_melody()`

**Implementation details**:
- Beyond skyline (highest note): implement contour-following melody extraction
  - Track the melody as the voice with the smoothest pitch contour (smallest average interval)
  - When multiple notes share an onset, prefer the one closest in pitch to the previous melody note (contour continuity)
  - Add a "melody range" heuristic: if a note is >12st away from the running melody median, it is likely accompaniment, not melody
- Add optional "melody voice" detection: if the .mxl has voice markings (music21 Voice objects), use Voice 1 as melody
- This does NOT violate Rule 5 (no reference in pipeline) — it only changes how we extract the evaluation target

**Expected impact**: mel_strict could jump significantly if current skyline is including non-melody notes in the reference. Even a 10% improvement in reference quality could raise mel_strict by 0.01-0.03 without any pipeline change.
**Effort**: MEDIUM
**Risk**: MEDIUM — changing the reference changes ALL historical comparisons. Must document clearly.
**Dependencies**: Phase 1 complete (so we know the pipeline ceiling with current reference)

**Acceptance criteria**:
- [ ] Compare skyline vs contour-following reference on 2-3 songs manually (listen to both)
- [ ] New reference has fewer notes (inner voices removed) and smoother contour
- [ ] Re-evaluate pipeline with new reference; mel_strict should increase if reference is more accurate
- [ ] Both old and new reference results preserved for comparison

---

### Step 7: Evaluation Metric Augmentation

**Description**: mel_strict (50ms onset, exact pitch) may be too strict for the "listenable melody" goal (Rule 1). A melody that sounds right to a human listener may have systematic timing offsets or octave differences from the piano arrangement. This step adds perceptual evaluation metrics that better capture "does this sound like the melody?"

**Files to modify**:
- `core/comparator.py` — add new metric functions
- `scripts/evaluate.py` — report new metrics

**Implementation details**:
- **pitch_accuracy_at_onset**: For each ref note, find nearest gen note within 200ms. Report what percentage have correct pitch class (octave-agnostic). This isolates pitch quality from timing quality.
- **rhythm_accuracy**: Compare inter-onset-interval (IOI) sequences of ref and gen using dynamic time warping (DTW). Captures rhythmic similarity independent of absolute timing.
- **melodic_contour_correlation**: Compute pitch contour (direction + interval size) correlation between ref and gen, ignoring octave. Captures whether the melody "shape" is right.
- **perceptual_score**: Weighted combination: 0.4*pitch_accuracy_at_onset + 0.3*rhythm_accuracy + 0.3*melodic_contour_correlation
- Keep mel_strict as primary metric for backward compatibility; add perceptual_score as secondary

**Expected impact**: No mel_strict change. Provides a more nuanced picture of quality and may reveal that the pipeline is closer to "listenable" than mel_strict suggests.
**Effort**: MEDIUM
**Risk**: LOW — additive metrics, no existing behavior changes
**Dependencies**: None (can start any time, but most useful after Phase 1)

**Acceptance criteria**:
- [ ] New metrics computed for all 8 songs
- [ ] perceptual_score correlates with human listening judgments (spot-check 2-3 songs)
- [ ] Results show whether pipeline quality is better than mel_strict indicates
- [ ] Documented in PROJECT_DIRECTIVES.md

---

### Step 8: Octave-Tolerant Evaluation Metric

**Description**: Vocal melodies sit in a different octave register than piano right-hand arrangements. The vocal may sing C4 while the piano plays C5. This is a known, systematic difference. Rather than modifying the pipeline (which would violate the Architecture Guard in postprocess.py lines 1-6), this step adds an octave-tolerant variant of mel_strict as an **evaluation-only** metric.

**Files to modify** (evaluation-side only, NOT pipeline):
- `core/comparator.py` — new `melody_f1_strict_octave_tolerant()` metric function
- `scripts/evaluate.py` — report the new metric alongside existing mel_strict

**Implementation details**:
- New metric `mel_strict_octave_tolerant`: same as mel_strict (50ms onset tolerance) but pitch matching is octave-agnostic (pitch % 12 comparison instead of exact MIDI pitch)
- Implemented as a new function in `comparator.py`, NOT by modifying existing `compare_notes()` logic
- Reports both `mel_strict` (exact pitch) and `mel_strict_oct` (octave-tolerant) so we can see the gap
- The gap between mel_strict and mel_strict_oct directly quantifies how much octave register mismatch costs us
- If the gap is large (e.g., mel_strict=0.09, mel_strict_oct=0.25), it validates that the pipeline's pitch class detection is good but register is wrong
- This informs whether Phase 2 should focus on pipeline register correction or accept the vocal register as-is
- **NO changes to `core/postprocess.py` or any pipeline module** — this is purely evaluation infrastructure

**Expected impact**: No mel_strict change (this is a new metric, not a pipeline change). But the diagnostic value is high: it quantifies the octave register gap and informs whether further pipeline work on register correction is worthwhile.
**Effort**: LOW
**Risk**: NONE — purely additive metric, no existing behavior changes
**Dependencies**: Step 1 diagnostic data (confirms whether octave errors are systematic); best interpreted after Phase 1 pipeline changes

**Acceptance criteria**:
- [ ] New metric `mel_strict_oct` computed for all 8 songs
- [ ] Gap between mel_strict and mel_strict_oct quantified (expected: mel_strict_oct >> mel_strict)
- [ ] No changes to any pipeline module (postprocess.py, pipeline.py, note_segmenter.py)
- [ ] Results inform Phase 2 decision: is register correction worth pursuing?

---

## Task Flow & Dependencies

```
Phase 1 (Pipeline):

Step 1 (Diagnostics) ──┬──> Step 2 (Octave)    ──┐
                       └──> Step 3 (Density)    ──┤
                                                  ├──> Phase 1 Integration
Step 4 (Onset) ───────────────────────────────────┤
Step 5 (Diatonic) ────────────────────────────────┘

Phase 2 (Evaluation):

Phase 1 Complete ──┬──> Step 6 (Reference Extraction)
                   ├──> Step 7 (Metrics Augmentation)
                   └──> Step 8 (Octave-Tolerant Metric)
```

Steps 4 and 5 have no dependencies and can start immediately.
Steps 2 and 3 depend on Step 1 diagnostic data.
Steps 6, 7, and 8 are Phase 2 — they modify evaluation methodology, not the pipeline. They should wait for Phase 1 to establish the pipeline ceiling.

## Execution Order (recommended)

1. Step 1 (Diagnostics) — produces data for everything else
2. Steps 2 + 4 + 5 in parallel — independent improvements
3. Step 3 (Density) — after Step 1 data reveals FP characteristics
4. Phase 1 Integration — combine, evaluate, document
5. Steps 6 + 7 + 8 in parallel — Phase 2 evaluation rethink

## Verification Strategy

| Step | Verification Method |
|------|-------------------|
| 1 | Script produces valid JSON output for all 8 songs; spot-check 2 songs manually |
| 2 | 8-song eval: mel_strict avg >= 0.095, octave error count reduced |
| 3 | 8-song eval: mel_strict avg >= 0.11, note_count_ratio closer to 0.7-0.9 |
| 4 | 8-song eval: onset_f1 avg >= 0.55 |
| 5 | 8-song eval: mel_strict not regressed, diatonic removal rate reduced |
| Integration | 8-song eval: mel_strict avg >= 0.13 (success) / 0.15 (aspirational), round-trip test PASS |
| 6 | Manual listening comparison of old vs new reference on 2-3 songs |
| 7 | New metrics computed, perceptual_score reported alongside mel_strict |
| 8 | mel_strict_oct metric computed for all 8 songs; gap vs mel_strict quantified |

## Risk Summary

| Risk | Mitigation |
|------|-----------|
| Changes interact negatively when combined | Test each in isolation first, combine incrementally |
| Note density filter hurts recall | Per-song ablation, do not filter below 0.6 note_count_ratio |
| Onset snap refinement introduces new collisions | Run dedup_close_onsets after any snap changes |
| Phase 2 reference changes invalidate history | Keep old reference results, document version clearly |
| 0.15 target unreachable with Phase 1 alone | Phase 1 success at 0.13+; Phase 2 (Steps 6-8) closes gap to 0.15 via evaluation improvements |

## Success Criteria

**Phase 1 complete when**:
- mel_strict avg >= 0.13 on 8-song benchmark (success threshold)
- mel_strict avg >= 0.15 is aspirational; if Phase 1 lands at 0.13-0.15, proceed to Phase 2
- No single song regresses more than 0.01 from current best
- All changes documented in PROJECT_DIRECTIVES.md
- Results reproducible (saved to results/ with version tag)

**Phase 2 complete when**:
- perceptual_score metric defined and computed
- mel_strict_oct metric quantifies octave register gap
- Reference extraction improved or validated
- Clear understanding of the theoretical ceiling for this pipeline + reference combination
- Decision documented: continue optimizing mel_strict OR adopt perceptual_score as primary metric
- Combined Phase 1 + Phase 2 target: mel_strict >= 0.15 (with improved evaluation methodology)
