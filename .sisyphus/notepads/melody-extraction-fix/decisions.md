- [Decision] Hybrid Scoring 알고리즘 설계 완료. Velocity(0.5), Contour(0.3), Register(0.2) 가중치 적용. 상세 내용은 .sisyphus/drafts/hybrid-scoring-design.md 참조.

## Task 3: Essentia Confidence Threshold Decision

### Problem
Initial confidence threshold of 0.8 filtered out ALL notes (max confidence was 0.565).

### Decision
Set `CONFIDENCE_THRESHOLD = 0.3`

### Rationale
1. **Empirical Data**: Essentia's PredominantPitchMelodia produces confidence < 0.6
2. **Trade-off**: Lower threshold = more notes but potentially more false positives
3. **Validation**: 185 notes extracted with reasonable pitch range (54-83)
4. **Comparison**: Still underperforms Skyline, but provides viable baseline

### Alternative Considered
- Adaptive threshold based on confidence distribution
- Rejected: Adds complexity without proven benefit for spike test

