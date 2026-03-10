<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-10 | Updated: 2026-03-10 -->

# results/diagnostics/

## Purpose
`scripts/diagnose.py` 실행 결과 저장 디렉토리. 곡별 음표 오류 분류 및 피치/온셋 오류 분포를 담은 JSON 파일들이 위치한다.

## Key Files

| File | Description |
|------|-------------|
| `summary.json` | 8곡 집계 — 오류 카운트, 피치 히스토그램, 옥타브 오류 수, 온셋 통계 |
| `{곡명}.json` | 곡별 진단 — exact_match/pitch_miss/onset_miss/both_miss/FP/FN 분류 |

## For AI Agents

### 진단 JSON 구조 (summary.json)
```json
{
  "total_songs": 8,
  "aggregate_error_counts": {
    "exact_match": 434, "pitch_miss": 1274, "onset_miss": 293,
    "both_miss": 1397, "false_positive": 727, "false_negative": 2020
  },
  "aggregate_pitch_histogram": { "-12": 46, "-2": 266, "2": 294, ... },
  "aggregate_onset_stats": { "avg_mean_ms": -1.64, "avg_std_ms": 79.83 },
  "total_octave_errors": 111
}
```

### v19 진단 핵심 수치 (현재 baseline)
- pitch_miss=1274(31%) — 주요 오류원, 하모닉 혼동(±2-7st) 지배
- 옥타브 오류=111(4.1%) — 예상보다 적음, 옥타브 보정 효과 제한적
- ±2st 오류=560 (최다), ±5st=350, ±7st=292
- 온셋 편향: mean=-1.6ms (무편향), std=79.8ms

### 이 디렉토리 파일은 직접 편집하지 말 것 — diagnose.py 재실행으로 갱신

<!-- MANUAL: -->
