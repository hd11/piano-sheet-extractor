
## Arrangement Engine v3 Evaluation Report (2026-02-05)

### Model: Pop2Piano (sweetcocoa/pop2piano)
### Environment: pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime, CPU inference

---

### 8-Song Composite Metrics

| Song | Title | Gen Notes | Ref Notes | Composite | Chroma | Melody F1 (lenient) | PC F1 | Onset F1 | Contour | Time |
|------|-------|-----------|-----------|-----------|--------|---------------------|-------|----------|---------|------|
| song_01 | Golden | 1369 | 1897 | 48.38% | 99.64% | 26.45% | 48.25% | 31.11% | 41.35% | 74.9s |
| song_02 | IRIS OUT | 1018 | 1131 | 38.59% | 86.85% | 8.43% | 20.90% | 53.83% | 31.72% | 34.9s |
| song_03 | 꿈의 버스 | 1223 | 1543 | 42.62% | 95.84% | 25.31% | 41.97% | 2.91% | 42.00% | 26.4s |
| song_04 | 너에게100퍼센트 | 1873 | 2413 | 47.13% | 96.58% | 26.34% | 41.53% | 26.11% | 44.00% | 39.6s |
| song_05 | 달리 표현할 수 없어요 | 1273 | 1746 | 42.08% | 99.09% | 15.16% | 28.48% | 24.71% | 40.00% | 34.3s |
| song_06 | 등불을 지키다 | 1480 | 1665 | **55.23%** | 97.37% | **39.12%** | **52.54%** | 44.26% | 46.00% | 34.0s |
| song_07 | 비비드라라러브 | 1890 | 2024 | 43.94% | 99.36% | 10.14% | 29.05% | 54.64% | 38.00% | 55.5s |
| song_08 | 여름이었다 | 1806 | 2073 | 47.93% | 99.21% | 18.20% | 36.76% | 52.43% | 42.00% | 33.0s |

### Averages

| Metric | Average | Best | Worst |
|--------|---------|------|-------|
| **Composite Score** | **45.74%** | 55.23% (song_06) | 38.59% (song_02) |
| Chroma Similarity | **96.74%** | 99.64% (song_01) | 86.85% (song_02) |
| Melody F1 (lenient) | 21.14% | 39.12% (song_06) | 8.43% (song_02) |
| Pitch Class F1 | 37.44% | 52.54% (song_06) | 20.90% (song_02) |
| Onset F1 | 36.25% | 54.64% (song_07) | 2.91% (song_03) |
| Processing Time | 41.6s avg | 26.4s (song_03) | 74.9s (song_01) |

### Comparison with Previous Baseline

| Metric | ByteDance (v1) | Pop2Piano (v3) | Improvement |
|--------|---------------|----------------|-------------|
| Similarity (old metric) | 20.31% | N/A (different metric) | — |
| Composite Score | N/A | **45.74%** | New metric |
| Chroma Similarity | N/A | **96.74%** | New metric |

**Note**: Direct comparison with ByteDance is not meaningful because:
1. ByteDance was a *transcription* model (extracting piano from audio)
2. Pop2Piano is an *arrangement* model (generating piano arrangement from full mix)
3. The comparison metrics are completely different (old: greedy note matching; new: mir_eval + DTW + chroma)

### Difficulty System

| Song | Easy Notes | Medium Notes | Hard Notes | Ratio (Easy/Hard) |
|------|-----------|-------------|------------|-------------------|
| song_01 | 12 | 874 | 1369 | 0.9% |
| song_02 | 0 | 327 | 1018 | 0.0% |
| song_03 | 20 | 977 | 1223 | 1.6% |
| song_04 | 48 | 1059 | 1873 | 2.6% |
| song_05 | 45 | 875 | 1273 | 3.5% |
| song_06 | 67 | 1211 | 1480 | 4.5% |
| song_07 | 62 | 978 | 1890 | 3.3% |
| song_08 | 50 | 969 | 1806 | 2.8% |

**Issue**: Easy mode produces very few notes (0-67). The skyline algorithm is too aggressive on Pop2Piano's polyphonic output. This needs tuning — the split point or skyline tolerance may need adjustment.

### Key Findings

1. **Chroma similarity is excellent (96.74%)**: Pop2Piano captures the harmonic content of songs almost perfectly. This means the model understands *what notes to play*.

2. **Onset F1 varies widely (2.91% - 54.64%)**: Rhythmic alignment is inconsistent. Some songs (song_07: 54.64%) have good timing, others (song_03: 2.91%) are very different rhythmically.

3. **Melody F1 is moderate (21.14%)**: Note-level matching is limited because Pop2Piano generates a *different arrangement* than the reference. This is expected — two pianists would also differ at note level.

4. **Pitch Class F1 (37.44%) > Melody F1 (21.14%)**: Octave differences account for ~16% of the gap. Pop2Piano sometimes places notes in different octaves than the reference.

5. **song_06 (등불을 지키다) is the best performer**: 55.23% composite, suggesting Pop2Piano works best with certain song structures.

6. **song_02 (IRIS OUT) is the worst performer**: 38.59% composite, 86.85% chroma — the only song below 95% chroma similarity.

### Decision Matrix Result

| Composite Score Range | Verdict | Our Result |
|----------------------|---------|------------|
| ≥ 70% | GREAT | — |
| 50-70% | GOOD | song_06 (55.23%) |
| 30-50% | **MODERATE** | **Average: 45.74%** |
| < 30% | POOR | — |

**Verdict: MODERATE** — Average composite 45.74% falls in the 30-50% range.

### Recommended Next Steps

1. **Pop2Piano composer style optimization (Task 3)**: Test all 21 composer styles to find the best match for each song type. This could improve composite scores by 5-15%.

2. **Easy difficulty tuning**: The skyline algorithm produces too few notes. Consider:
   - Lowering the split point from 60 to 48
   - Using a less aggressive skyline (keep top 2 notes instead of 1)
   - Or using the medium difficulty as the new "easy"

3. **Post-processing pipeline**: Add note quantization and alignment to improve onset F1.

4. **Hybrid approach consideration**: For songs where Pop2Piano's chroma is low (song_02), consider a fallback strategy.

### Total Processing Time
- 8 songs: 337.8s (5.6 minutes) on CPU
- Average per song: 41.6s
- Model loading (first song): ~15s overhead
