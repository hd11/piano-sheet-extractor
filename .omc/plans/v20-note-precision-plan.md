# v20 Note Precision Improvement Plan

**Created**: 2026-03-10
**Baseline**: mel_strict avg = 0.091 (v19/v26c)
**Target**: mel_strict avg >= 0.12
**Strategy**: Reduce false positive notes to improve precision, leveraging the IRIS OUT insight (0.55 ratio = 3.5x better mel_strict)

## Context

The IRIS OUT pattern is the strongest signal in the entire experimental history:
- IRIS OUT generates only 404 notes for 734 ref notes (ratio 0.55)
- mel_strict = 0.320, which is 3.5x the average (0.091)
- Precision = 53.4% vs ~10% for other songs

This means: **fewer, higher-confidence notes = dramatically better mel_strict**. The current pipeline over-generates notes, creating many false positives that tank precision. Three songs have gen/ref > 1.0 (Dream Bus 1.10, Dali 1.22, Vivid 1.06).

The problem is NOT pitch class (chroma=0.975) -- it is:
1. Too many spurious short notes from F0 jitter (precision killer)
2. Harmonic confusion at +/-2-7 semitones (31% of errors)
3. Onset timing variance (std=79.8ms >> 50ms tolerance)

## Guardrails

**Must Have:**
- Each step independently evaluated with full 8-song benchmark
- Preserve v26c postprocess chain order
- No reference data in pipeline (Rule 1)
- MusicXML round-trip evaluation (Rule 4)
- IRIS OUT mel_strict must not regress below 0.300

**Must NOT Have:**
- Any technique from the failed lists (mode vocal_center, onset strength weighting, harmonic correction, CQT octave verify, F0 ensemble, float MIDI running center)
- Reference-based transformations in evaluation
- Architecture changes to pipeline flow

## Consensus Review Result (Architect + Critic — 2026-03-10)

**Verdict: APPROVE WITH MODIFICATIONS**

**Accepted changes to original plan:**
1. ~~Step 2 (CREPE confidence threshold)~~ — **DROPPED.** Baseline uses FCPE mode (3.2s/song processing confirms it). CREPE threshold is a no-op on the FCPE pipeline. FCPE confidence is binary (0/1) — cannot be thresholded.
2. Step 4 — **HIGH stays at 96 (not 88).** IRIS OUT ref notes reach MIDI 95, Golden reach 93. Clipping at 88 would prevent octave correction from shifting into the correct high register. Only tighten LOW: 48 → 52 (safe, lowest ref note is MIDI 53).
3. Steps 1+3 — **Measure combined effect explicitly** after individual runs. If combined ≠ sum±0.005, investigate interaction.
4. Step 5 — **Run 5b (minor template) before 5a (threshold change)** — independent axes, minor template is lower risk.

## Task Flow (Revised)

```
Step 1 (min_note_duration 50→80ms) --> evaluate
    |
Step 3 (dedup 30→50ms) --> evaluate
    |
Steps 1+3 combined check --> evaluate
    |
Step 4 (VOCAL_RANGE_LOW 48→52 ONLY, HIGH stays 96) --> evaluate
    |
Step 5b (minor scale template) --> evaluate
    |
Step 5a (diatonic threshold 0.15→0.12s) --> evaluate
    |
    v
Cumulative integration --> final evaluation (results/v20_*.json)
```

Each step is additive. If a step regresses, revert it before proceeding.

---

## Step 1: Increase min_note_duration (Highest Priority)

**Rationale**: The strongest available lever. Current 50ms allows many F0 jitter artifacts through as notes. The IRIS OUT pattern proves that reducing note count dramatically improves precision. Increasing min_note_duration is the safest way to reduce spurious short notes without touching pitch logic.

**Files to modify**: `core/note_segmenter.py`

**Implementation**:
- Change `min_note_duration` default from `0.05` to `0.08` (80ms) in `segment_notes()` function signature (line 20)
- Also update the docstring on line 33 to match
- Do NOT change `segment_notes_onset`, `segment_notes_hybrid`, or `segment_notes_quantized` (unused in main pipeline)

**Why 80ms**:
- 50ms (current) was previously increased from 60ms for +0.005 gain
- But the IRIS OUT pattern suggests we need FEWER notes, not more
- 80ms is one step back from the "more notes" direction
- 80ms is still well below typical vocal note duration (~200ms+)
- If 80ms improves, try 100ms and 120ms as follow-up ablation

**Ablation plan**: Test 80ms, 100ms, 120ms, 150ms. Pick the value that maximizes average mel_strict without dropping IRIS OUT below 0.300.

**Expected impact**: +0.005 to +0.015 mel_strict avg. Songs with ratio > 1.0 (Dali, Dream Bus, Vivid) should improve most as their shortest jitter notes get filtered.

**Acceptance criteria**:
- [ ] mel_strict avg > 0.091 (improvement over baseline)
- [ ] IRIS OUT mel_strict >= 0.300 (no regression on best song)
- [ ] Ablation results for 80/100/120/150ms documented in PROJECT_DIRECTIVES.md

---

## Step 2: CREPE Confidence Threshold Increase

**Rationale**: CREPE (unlike FCPE) has real-valued periodicity confidence per frame. Current threshold is 0.40 -- frames below this are zeroed. Increasing this filters out low-confidence F0 frames BEFORE segmentation, removing uncertain pitch estimates that cause both spurious notes and harmonic confusion. This is different from the failed FCPE confidence filter (Step 3 of v19) because CREPE periodicity is a continuous gradient, not binary.

**CRITICAL**: The pipeline currently defaults to `mode="crepe"` in evaluate.py. Check whether the current best results use CREPE or FCPE mode. If FCPE is being used, this step applies to CREPE mode only and requires switching the default mode.

**Files to modify**: `core/pitch_extractor.py`

**Implementation**:
- Change `confidence_threshold` default from `0.40` to `0.50` in `extract_f0()` (line 23)
- Ablation: test 0.45, 0.50, 0.55, 0.60

**Why this works differently from failed v19 Step 3**: v19 Step 3 tried to use F0 variance as a proxy confidence for FCPE (which has binary confidence). That never activated because note density was below threshold. Here we use CREPE's native periodicity score, which is a proven quality signal already used at 0.40.

**Expected impact**: +0.005 to +0.010 mel_strict. Higher threshold = fewer voiced frames = fewer spurious notes, especially in non-vocal regions where CREPE tracks instrumental harmonics.

**Acceptance criteria**:
- [ ] mel_strict avg > result from Step 1
- [ ] Ablation of 0.45/0.50/0.55/0.60 documented
- [ ] No song regresses more than -0.015 from Step 1 result

**NOTE**: If the pipeline is actually running FCPE (not CREPE) for best results, skip this step and document why. FCPE confidence is binary and cannot be thresholded meaningfully.

---

## Step 3: Increase Dedup Close Onset Threshold

**Rationale**: After beat snapping, notes with onsets within 30ms are deduplicated. Since onset_f1 tolerance is 100ms and mel_strict onset tolerance is 50ms, two notes within 50ms of each other cannot both match the same reference note. Increasing dedup threshold from 30ms to 50ms removes more near-simultaneous collisions that can only hurt precision.

**Files to modify**: `core/postprocess.py`

**Implementation**:
- Change `min_gap` default in `_dedup_close_onsets()` from `0.030` to `0.050` (line 720)

**Expected impact**: +0.002 to +0.005 mel_strict. Small but essentially risk-free -- any two notes within 50ms can match at most one reference note, so removing the weaker one can only help or be neutral.

**Acceptance criteria**:
- [ ] mel_strict avg >= previous step result (no regression)
- [ ] Note count reduction documented per song
- [ ] If neutral (< 0.001 change), keep the change anyway as it is logically correct

---

## Step 4: Tighten Vocal Range Clipping

**Rationale**: Current vocal range is MIDI 48-96 (C3-C7). This is extremely wide. Most pop/ballad vocals sit in MIDI 55-84 (G3-C6). Notes outside this range are almost certainly F0 artifacts (instrumental bleed, subharmonic locks, or harmonic overtones). The global_octave_adjust targets center=75 and range 60-84, but the clip step still allows 48-96.

**Files to modify**: `core/postprocess.py`

**Implementation**:
- Change `VOCAL_RANGE_LOW` from `48` to `52` (E3) -- line 19
- Change `VOCAL_RANGE_HIGH` from `96` to `88` (E6) -- line 20
- Also update `_global_octave_adjust` and `_self_octave_correction` to use the same constants (they already reference `VOCAL_RANGE_LOW`/`VOCAL_RANGE_HIGH`)

**Why E3-E6 (52-88)**: Conservative tightening. E3 is below typical female/male pop range low. E6 covers high soprano notes and whistle register. This removes clearly instrumental frequencies without cutting real vocal notes.

**Ablation**: Test current (48-96) vs moderate (52-88) vs tight (55-84). Check which songs lose real notes at each threshold.

**Expected impact**: +0.002 to +0.008 mel_strict. Songs with F0 artifacts outside vocal range will improve. Risk is low because notes below E3 or above E6 in pop vocals are extremely rare.

**Acceptance criteria**:
- [ ] mel_strict avg >= previous step result
- [ ] Count of notes removed per song by tighter range
- [ ] Verify no real vocal notes are cut (check against reference pitch range)

---

## Step 5: Diatonic Gate Threshold Tuning + Minor Scale

**Rationale**: Current diatonic gate removes chromatic (out-of-key) notes shorter than 0.15s using major scale only. The v19 experiment tried lowering to 0.10s and adding multi-scale templates, with neutral/negative results. However, the v19 test combined multiple changes. An isolated test of just the threshold (not the template) at 0.12s could still help, and adding natural minor to the template matching (without changing threshold logic) is a separate axis.

**Files to modify**: `core/postprocess.py`

**Implementation (two independent sub-experiments)**:

**5a: Threshold 0.15 -> 0.12s**:
- Change `max_chromatic_duration` default in `_diatonic_gate()` from `0.15` to `0.12` (line 664)
- This removes chromatic notes in the 0.12-0.15s range that were previously kept

**5b: Add natural minor scale template** (independent from 5a):
- In `_diatonic_gate()`, after the major scale matching (line 691-697), add natural minor template `[0, 2, 3, 5, 7, 8, 10]`
- Pick whichever scale (major or minor) scores higher
- This ensures minor-key songs don't lose valid notes

**Expected impact**: +0.002 to +0.005 mel_strict per sub-experiment. Low risk since only short chromatic notes are affected.

**Acceptance criteria**:
- [ ] 5a and 5b tested independently and in combination
- [ ] mel_strict avg >= previous step result
- [ ] IRIS OUT mel_strict >= 0.300
- [ ] Document which songs are in minor keys and whether 5b helps them

---

## Cumulative Integration

After all steps are individually validated:

1. Combine all accepted changes into a single evaluation run
2. Run full 8-song benchmark
3. Document cumulative result in PROJECT_DIRECTIVES.md as v20
4. If cumulative result is worse than best individual step (interaction effects), do binary search to find the conflicting pair

**Final acceptance criteria**:
- [ ] mel_strict avg >= 0.10 (minimum viable improvement, +10% relative)
- [ ] IRIS OUT mel_strict >= 0.300
- [ ] No individual song regresses more than -0.020 from v19 baseline
- [ ] All results saved to `results/v20_*.json`
- [ ] PROJECT_DIRECTIVES.md updated with v20 section

---

## Risk Assessment

| Step | Risk | Reversibility | Expected Impact |
|------|------|---------------|-----------------|
| 1. min_note_duration | LOW | Trivial (1 param) | HIGH (+0.005-0.015) |
| 2. CREPE confidence | LOW-MED | Trivial (1 param) | MED (+0.005-0.010) |
| 3. dedup threshold | VERY LOW | Trivial (1 param) | LOW (+0.002-0.005) |
| 4. vocal range clip | LOW | Trivial (2 constants) | LOW-MED (+0.002-0.008) |
| 5. diatonic gate | LOW | Trivial (1 param + template) | LOW (+0.002-0.005) |

Total expected range: +0.016 to +0.043, realistic midpoint: +0.025
Realistic target: mel_strict avg ~0.115 (v19 0.091 + 0.025)

## What This Plan Does NOT Address

These are known limitations that require fundamentally different approaches:
- **Harmonic confusion (31% of errors)**: Requires better F0 model or post-hoc harmonic disambiguation. All postprocess-level harmonic correction has failed.
- **Vocal-to-sheet gap**: Vocal melody != piano arrangement notes. Structural mismatch, not a pipeline bug.
- **Onset timing variance (std=79.8ms)**: Beat snap helps but cannot solve fundamental F0 frame timing imprecision.
