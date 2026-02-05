
## Decision: NO-GO for Music2MIDI, Proceed with Pop2Piano (2026-02-05)

### Context
Task 0 of arrangement-engine-upgrade-v3 plan. Music2MIDI re-spike on CUDA 12.1 / torch 2.2.

### Decision
**NO-GO** for Music2MIDI. Continue with Pop2Piano as the arrangement engine.

### Rationale
1. Music2MIDI generates 0 notes (degenerate output) — all decoding strategies fail
2. CPU inference prohibitively slow (130-168s for 30s audio)
3. Pop2Piano confirmed working: 1369 notes, 67s processing, valid MIDI output
4. Pop2Piano has HuggingFace integration (stable, maintained)

### Consequences
- Follow NO-GO path in plan: Tasks 1, 2-B, 3, 4, 5, 6-B, 7, 8, 9, 10
- Pop2Piano composer style exploration (Task 3) to optimize output quality
- Difficulty system uses heuristic redesign (Task 6-B) instead of native conditioning
