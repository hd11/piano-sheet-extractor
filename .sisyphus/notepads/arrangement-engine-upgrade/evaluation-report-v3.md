# Piano Arrangement Engine Evaluation Report v3

**Date:** 2026-02-05  
**Model:** Pop2Piano (sweetcocoa/pop2piano-composer5)  
**Songs Tested:** 8  
**Test Duration:** ~15 minutes (5 min per report type)

---

## Executive Summary

The Pop2Piano (composer5) arrangement engine was evaluated on 8 test songs with comprehensive metrics across three comparison scenarios:

- **Average Composite Score (vs Original):** 46.26%
- **Average Composite Score (vs Easy):** 24.36%
- **Average Composite Score (vs C-Major):** 30.42%

### Key Findings

1. **Strong Harmonic Accuracy:** Chroma similarity averages 98.08% across all songs, indicating excellent harmonic content preservation
2. **Moderate Melodic Capture:** Melody F1 (strict) averages 9.15%, with lenient matching at 22.82%
3. **Good Rhythmic Alignment:** Onset F1 averages 37.34%, showing reasonable timing accuracy
4. **Consistent Performance:** Composite scores range from 39.29% to 57.75%, with song_06 performing best

---

## 1. Original Reference Comparison

### Per-Song Metrics

| Song    | Composite | Melody F1 | Lenient | PC F1  | Chroma | Onset  | Contour | Ref Notes | Gen Notes |
|---------|-----------|-----------|---------|--------|--------|--------|---------|-----------|-----------|
| song_01 | 53.20%    | 11.69%    | 34.53%  | 52.76% | 98.60% | 30.74% | 44.77%  | 1897      | 1746      |
| song_02 | 41.08%    | 11.72%    | 12.14%  | 22.46% | 95.26% | 57.76% | 44.07%  | 1709      | 1158      |
| song_03 | 47.13%    | 1.68%     | 33.51%  | 48.05% | 99.48% | 3.03%  | 49.47%  | 1598      | 1374      |
| song_04 | 43.95%    | 8.01%     | 21.23%  | 35.59% | 98.83% | 30.17% | 44.86%  | 1551      | 2321      |
| song_05 | 39.29%    | 4.77%     | 14.99%  | 29.10% | 98.33% | 26.14% | 51.45%  | 1220      | 1756      |
| song_06 | 57.75%    | 24.96%    | 38.55%  | 54.28% | 98.97% | 46.97% | 47.02%  | 1710      | 1735      |
| song_07 | 42.39%    | 4.94%     | 12.90%  | 28.05% | 96.86% | 52.65% | 47.39%  | 2213      | 2486      |
| song_08 | 45.25%    | 6.33%     | 14.67%  | 35.82% | 98.40% | 51.27% | 44.10%  | 1524      | 2049      |
| **AVG** | **46.26%** | **9.26%** | **22.82%** | **38.26%** | **98.08%** | **37.34%** | **46.64%** | **1678** | **1828** |
| **MIN** | **39.29%** | **1.68%** | **12.14%** | **22.46%** | **95.26%** | **3.03%** | **44.07%** | **1220** | **1158** |
| **MAX** | **57.75%** | **24.96%** | **38.55%** | **54.28%** | **99.48%** | **57.76%** | **51.45%** | **2213** | **2486** |

### Analysis

**Best Performer:** song_06 (57.75% composite)
- Highest melody F1 (24.96%)
- Strong pitch class F1 (54.28%)
- Balanced note count (1710 ref vs 1735 gen)

**Weakest Performer:** song_05 (39.29% composite)
- Low melody F1 (4.77%)
- Lowest pitch class F1 (29.10%)
- Significant note count mismatch (1220 ref vs 1756 gen)

**Outlier:** song_03 (47.13% composite)
- Extremely low onset F1 (3.03%) - possible timing/tempo issue
- Very low melody F1 (1.68%)
- Excellent chroma (99.48%) suggests harmonic content is correct

---

## 2. Easy Difficulty Comparison

### Per-Song Metrics

| Song    | Composite | Melody F1 | Chroma | Ref Notes | Gen Notes |
|---------|-----------|-----------|--------|-----------|-----------|
| song_01 | 47.83%    | 9.09%     | 98.54% | 1177      | 649       |
| song_02 | 38.65%    | 6.47%     | 93.20% | 857       | 566       |
| song_03 | 15.13%    | 0.00%     | 56.99% | 1029      | 409       |
| song_04 | 11.92%    | 0.12%     | 29.12% | 1147      | 501       |
| song_05 | 11.22%    | 0.23%     | 20.21% | 853       | 861       |
| song_06 | 18.14%    | 0.41%     | 39.54% | 1288      | 660       |
| song_07 | 33.53%    | 1.48%     | 95.15% | 1672      | 619       |
| song_08 | 18.46%    | 0.76%     | 43.64% | 1088      | 500       |
| **AVG** | **24.36%** | **2.32%** | **59.55%** | **1139** | **596** |

### Analysis

**Key Observations:**
1. **Difficulty Adjustment Impact:** Easy difficulty shows significantly lower composite scores (24.36% vs 46.26%)
2. **Note Reduction:** Average generated notes reduced from 1828 (full) to 596 (easy) - 67% reduction
3. **Harmonic Degradation:** Chroma similarity drops from 98.08% to 59.55% - difficulty adjustment affects harmonic content
4. **Melody Capture Challenges:** Melody F1 drops to 2.32%, indicating difficulty adjustment may be too aggressive

**Best Easy Match:** song_01 (47.83%)
- Maintains high chroma (98.54%)
- Reasonable melody F1 (9.09%)

**Worst Easy Match:** song_05 (11.22%)
- Very low chroma (20.21%)
- Near-zero melody F1 (0.23%)

---

## 3. C-Major Variant Comparison

### Per-Song Metrics

| Song    | Composite | Chroma | Onset F1 | Contour | Ref Notes | Gen Notes |
|---------|-----------|--------|----------|---------|-----------|-----------|
| song_03 | 34.38%    | 60.37% | 99.84%   | 47.25%  | 1598      | 1593      |
| song_04 | 30.05%    | 37.65% | 100.00%  | 40.70%  | 1551      | 1551      |
| song_05 | 21.52%    | 19.37% | 100.00%  | 75.75%  | 1220      | 1220      |
| song_06 | 31.85%    | 35.46% | 100.00%  | 52.69%  | 1710      | 1710      |
| song_08 | 34.31%    | 48.96% | 100.00%  | 57.97%  | 1524      | 1524      |
| **AVG** | **30.42%** | **40.36%** | **99.97%** | **54.87%** | **1521** | **1520** |

### Analysis

**Key Observations:**
1. **Perfect Timing Preservation:** Onset F1 averages 99.97% - C-major transposition preserves timing perfectly
2. **Exact Note Count Match:** Generated notes match reference exactly (1520 vs 1521 avg)
3. **Harmonic Shift Expected:** Chroma similarity at 40.36% is expected due to key transposition
4. **Contour Preservation:** Pitch contour similarity at 54.87% shows melodic shape is maintained

**Best C-Major Match:** song_03 (34.38%)
- Highest chroma similarity (60.37%)
- Perfect onset alignment (99.84%)

**Weakest C-Major Match:** song_05 (21.52%)
- Lowest chroma (19.37%)
- Highest contour preservation (75.75%) - suggests melodic shape maintained despite harmonic differences

---

## 4. Metric-by-Metric Analysis

### Composite Score (Average: 46.26%)

**Definition:** Weighted average of all metrics  
**Interpretation:** Overall similarity between generated and reference arrangements

**Findings:**
- Consistent performance across songs (39-58% range)
- song_06 significantly outperforms (57.75%)
- No catastrophic failures (all > 39%)

**Recommendation:** Target 50%+ composite score as baseline quality threshold

---

### Melody F1 - Strict (Average: 9.26%)

**Definition:** Exact pitch + timing match for melody notes  
**Interpretation:** How accurately the model captures the reference melody

**Findings:**
- Low overall performance (1.68% - 24.96% range)
- song_06 achieves 24.96% (best)
- song_03 only 1.68% (worst)
- High variance suggests song-dependent performance

**Root Causes:**
1. Pop2Piano generates full arrangements, not isolated melodies
2. Strict matching penalizes octave shifts and timing variations
3. Reference melodies may be simplified/idealized versions

**Recommendation:** 
- Use lenient melody F1 (22.82% avg) as primary melody metric
- Consider melody F1 > 15% (lenient) as acceptable
- Investigate song_03 timing issues (3.03% onset F1)

---

### Melody F1 - Lenient (Average: 22.82%)

**Definition:** Pitch class + relaxed timing match  
**Interpretation:** Melody capture with tolerance for octave/timing shifts

**Findings:**
- 2.5x improvement over strict matching (22.82% vs 9.26%)
- song_01 achieves 34.53% (best lenient)
- song_02 drops to 12.14% (worst lenient)

**Recommendation:** Use lenient F1 as primary melody quality indicator

---

### Pitch Class F1 (Average: 38.26%)

**Definition:** Pitch class distribution match (ignoring octaves)  
**Interpretation:** Harmonic content accuracy

**Findings:**
- Moderate performance (22.46% - 54.28% range)
- Correlates with composite score (r ≈ 0.8)
- song_06 leads at 54.28%

**Recommendation:** Target PC F1 > 40% for acceptable harmonic accuracy

---

### Chroma Similarity (Average: 98.08%)

**Definition:** Chromagram correlation over time  
**Interpretation:** Overall harmonic profile match

**Findings:**
- **Excellent pe
