# Melody Extraction Improvement (Task 7)

**Date:** 2026-02-06

## Baseline (from melody-baseline.md)
- Strict F1 (expected baseline): ~9.26%
- Lenient F1 (expected baseline): ~22.82%

## Approach Tried
**Option A: ONSET_TOLERANCE tuning**

### Change Implemented
- Added `apply_hybrid_scoring_v2()` with `ONSET_TOLERANCE = 0.15` (150ms)
- Kept original `apply_hybrid_scoring()` intact for A/B comparison
- Updated `extract_melody()` to use v2

### Parameters Tested
- ONSET_TOLERANCE: **0.15s** (150ms)

## Measurement Results
**Status:** Not executed (environment blocked)

### Attempted Commands
```bash
cd backend
python measure_melody_baseline.py
pytest tests/unit/test_melody_extractor.py
```

### Blockers
- `python` command unavailable on host (no Python runtime)
- Docker not available (`docker compose` cannot connect to engine)

## Next Steps
1. Run measurement in a working Python or Docker environment.
2. If F1 improvement insufficient, iterate with next single change:
   - ONSET_TOLERANCE = 0.10 / 0.20 / 0.25 / 0.30 (one at a time)
3. Record F1 strict/lenient per change and compare against baseline.
