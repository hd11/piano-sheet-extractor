<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-10 | Updated: 2026-03-10 -->

# results/

## Purpose
실험 결과 JSON 파일 저장 디렉토리. 각 실험 버전(v4~v19)의 8곡 평가 결과가 저장된다. PROJECT_DIRECTIVES.md의 이력 기록과 연계된다.

## Key Files

| File | Description |
|------|-------------|
| `v26c_mindur50.json` | **기준 베이스라인** — FCPE, mel_strict avg=0.091 |
| `v19_phase2_skyline.json` | 최신 평가 — Phase 2 새 메트릭 포함 (skyline 참조) |
| `v19_phase2_contour.json` | 컨투어 참조 비교 실험 — skyline보다 열위 확인 |
| `v19_phase1.json` | Phase 1 통합 전 결과 (mel_strict 0.087, 전체 revert됨) |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `diagnostics/` | 곡별 진단 JSON (`diagnose.py` 출력) — 오류 분류 및 히스토그램 |

## For AI Agents

### 파일 명명 규칙
- 새 실험 결과: `results/vNN.json` 또는 `results/vNN_description.json`
- 버전 번호는 PROJECT_DIRECTIVES.md의 이력과 일치해야 함

### JSON 구조
```json
{
  "summary": {
    "avg_melody_f1_strict": 0.091,
    "avg_melody_f1_strict_oct": 0.109,
    "avg_perceptual_score": 0.537,
    ...
  },
  "songs": {
    "곡명": { "melody_f1_strict": ..., "processing_time": ... }
  }
}
```

### 진단 파일 (results/diagnostics/)
- `summary.json` — 8곡 집계 오류 분류
- `{곡명}.json` — 곡별 피치/온셋 오류 히스토그램

<!-- MANUAL: 추가 메모는 이 줄 아래에 작성 -->
