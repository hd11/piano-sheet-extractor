
## Pop2Piano Composer Style Comparison (2026-02-05)

### Test Song: song_01 (Golden)
### Reference: 1897 notes, pitch 31-93, duration 190.8s

---

### Quick Heuristic Ranking (chroma + note_ratio + pitch_overlap + pc_jaccard)

| Rank | Composer | Notes | Chroma | Note Ratio | Pitch Overlap | PC Jaccard | Heuristic Score | Time |
|------|----------|-------|--------|------------|---------------|------------|-----------------|------|
| 1 | composer3 | 1864 | 0.9982 | 0.9826 | 0.9231 | 0.7000 | 0.9487 | 27.5s |
| 2 | composer8 | 1775 | 0.9908 | 0.9357 | 0.9365 | 0.7000 | 0.9343 | 25.9s |
| 3 | composer5 | 1746 | 0.9860 | 0.9204 | 0.9254 | 0.7000 | 0.9256 | 24.0s |
| 4 | composer11 | 1594 | 0.9900 | 0.8403 | 0.9394 | 0.7000 | 0.9060 | 21.9s |
| 5 | composer20 | 1473 | 0.9942 | 0.7765 | 0.9231 | 0.8750 | 0.9028 | 20.2s |
| 6 | composer15 | 1548 | 0.9957 | 0.8160 | 0.8769 | 0.7000 | 0.8885 | 26.7s |
| 7 | composer6 | 1373 | 0.9976 | 0.7238 | 0.9194 | 0.8750 | 0.8876 | 20.7s |
| 8 | composer10 | 1343 | 0.9914 | 0.7080 | 0.9538 | 0.8750 | 0.8872 | 19.7s |
| 9 | composer18 | 1431 | 0.9904 | 0.7543 | 0.9254 | 0.7778 | 0.8853 | 20.4s |
| 10 | composer4 | 1420 | 0.9911 | 0.7486 | 0.9194 | 0.7778 | 0.8827 | 22.5s |
| 11 | composer7 | 2384 | 0.9897 | 0.7957 | 0.8261 | 0.7778 | 0.8776 | 29.2s |
| 12 | composer14 | 1495 | 0.9930 | 0.7881 | 0.8507 | 0.7000 | 0.8738 | 23.2s |
| 13 | **composer1** | **1369** | **0.9964** | **0.7217** | **0.8871** | **0.7778** | **0.8703** | **20.9s** |
| 14 | composer2 | 1278 | 0.9980 | 0.6737 | 0.9516 | 0.7778 | 0.8694 | 21.0s |
| 15 | composer17 | 1315 | 0.9962 | 0.6932 | 0.9048 | 0.7778 | 0.8652 | 22.2s |
| 16 | composer16 | 1391 | 0.9860 | 0.7333 | 0.8732 | 0.7000 | 0.8590 | 22.1s |
| 17 | composer12 | 1205 | 0.9916 | 0.6352 | 0.8986 | 0.8750 | 0.8544 | 18.8s |
| 18 | composer13 | 1260 | 0.9968 | 0.6642 | 0.8065 | 0.8750 | 0.8468 | 24.8s |
| 19 | composer19 | 1214 | 0.9951 | 0.6400 | 0.7258 | 0.8750 | 0.8227 | 16.9s |
| 20 | composer21 | 800 | 0.9930 | 0.4217 | 0.8065 | 1.0000 | 0.7850 | 17.5s |
| 21 | composer9 | 709 | 0.9899 | 0.3737 | 0.8387 | 0.7778 | 0.7536 | 13.5s |

### Full mir_eval Comparison (Top 3 + Baseline)

| Composer | Composite | Chroma | Melody F1 (lenient) | PC F1 | Onset F1 | Contour | Notes |
|----------|-----------|--------|---------------------|-------|----------|---------|-------|
| **composer5** | **51.96%** | 98.60% | **34.53%** | **52.76%** | 30.74% | **44.80%** | 1746 |
| composer8 | 49.25% | 99.08% | 28.59% | 52.78% | 26.74% | 41.93% | 1775 |
| composer1 (old default) | 48.38% | 99.64% | 26.45% | 48.25% | **31.11%** | 41.33% | 1369 |
| composer3 | 47.15% | **99.82%** | 23.24% | 48.92% | 28.82% | 40.70% | 1864 |

### Key Insight

The heuristic ranking (note count similarity, chroma, pitch overlap) does NOT correlate well with the full mir_eval composite score. composer3 has the most similar note count to the reference (1864 vs 1897) but scores lowest on mir_eval because:

1. **More notes ≠ better arrangement**: composer3 generates many notes but they don't align well with the reference's melody and timing
2. **composer5 wins on melody**: 34.53% melody F1 vs composer1's 26.45% (+8.1pp) — it captures the melodic content better
3. **composer5 wins on pitch class**: 52.76% vs 48.25% (+4.5pp) — better harmonic accuracy
4. **Chroma is uniformly high**: All composers score >98.6% chroma, so it's not a differentiator

### Decision

**Changed default from `composer1` to `composer5`**

Improvement on song_01:
- Composite: 48.38% → 51.96% (+3.6pp)
- Melody F1: 26.45% → 34.53% (+8.1pp)
- Pitch Class F1: 48.25% → 52.76% (+4.5pp)
- Onset F1: 31.11% → 30.74% (-0.4pp, negligible)

### Caveat

This was tested on song_01 only (per plan: "1곡만"). The optimal composer may vary per song. A future improvement could be per-song style selection or ensemble of top styles.
