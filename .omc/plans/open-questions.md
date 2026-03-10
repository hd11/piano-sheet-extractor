# Open Questions

## mel-strict-0.15-plan - 2026-03-10

- [ ] Is the vocal-to-sheet pitch mismatch dominated by octave errors (+/-12st) or smaller intervals (+/-1-5st)? — Step 1 diagnostics will answer this; determines whether Step 2 (octave) or Step 3 (density) has higher ROI
- [ ] Should the note density MAX_DENSITY constant be calibrated per-genre or use a single global threshold (4.0 notes/sec)? — Per-genre is more accurate but adds complexity; single constant is simpler and Rule 5 compliant
- [ ] For Step 3 F0 variance confidence: what is the right variance->confidence mapping? — Current plan uses `1/(1+var)` but may need tuning. Step 1 diagnostics should reveal the variance distribution across notes.
- [ ] Is the piano arrangement register consistently 1 octave above extracted vocal register, or does it vary per song? — Step 8 mel_strict_oct metric will quantify this gap; determines whether further register work is worthwhile
- [ ] When combining Steps 2-5, what is the interaction effect? — Octave correction + density filter may conflict (correcting octave increases valid notes, then density filter removes some). Requires careful integration testing
- [ ] Is mel_strict the right primary metric for "listenable melody" goal? — Phase 2 Step 7 will produce perceptual_score as alternative; user may want to switch primary metric after seeing both
- [ ] For diatonic gate (Step 5): are any of the 8 test songs in minor keys? — If yes, current major-only template is actively harmful for those songs
- [ ] Should failed note matches be weighted by duration? — A missed whole note is worse than a missed 16th note for listenability, but mel_strict treats them equally

## v20-note-precision-plan - 2026-03-10

- [ ] Is the pipeline actually using CREPE or FCPE for the v19 baseline results? — Step 2 (CREPE confidence threshold) only applies if CREPE is in use. If FCPE, Step 2 should be skipped. The evaluate.py default is "crepe" but FCPE was shown to be +10% better.
- [ ] At what min_note_duration value does IRIS OUT start regressing? — IRIS OUT already has ratio 0.55 (very few notes), further reduction may drop below critical mass. The ablation (80/100/120/150ms) must monitor IRIS OUT specifically.
- [ ] Does tightening vocal range (Step 4) remove real vocal notes in any of the 8 test songs? — Need to check ref note pitch ranges to ensure E3-E6 (52-88) covers all reference melodies.
- [ ] What is the interaction between min_note_duration increase (Step 1) and dedup threshold increase (Step 3)? — Both reduce note count; combined effect could be too aggressive for songs already at low note ratios (Lighthouse 0.70, IRIS OUT 0.55).

## improvement-analysis - 2026-03-10

- [ ] 노트 레벨 다중 모델 선택에서 "신뢰도 점수" 정의가 필요 — F0 confidence 평균, 피치 안정성(분산), 두 모델 일치도 중 어떤 가중치가 최적인지 실험 필요
- [ ] Vocal-to-Sheet Gap이 평가의 한계인지 파이프라인의 한계인지 판별 필요 — 인간 annotation 참조를 만들어 비교해야 확정 가능. 이것이 확인되면 목표 메트릭 자체를 재정의해야 할 수 있음
- [ ] ROSVOT/T3MS 모델의 가용성(코드 공개, 사전훈련 모델, 라이선스) 확인 필요 — 네트워크 제한 환경에서 다운로드 가능 여부가 Phase C 진행의 전제 조건
- [ ] 2-pass pipeline에서 1차 추출 통계를 2차에 어떻게 반영할지 설계 필요 — 과적합(곡별 파라미터) vs 범용성(고정 파라미터) 트레이드오프 결정
- [ ] Demucs 모델 교체(htdemucs_ft vs htdemucs vs mdx_extra) 시 캐시 무효화 전략 필요 — 기존 test/cache/ 파일이 htdemucs_ft 기준이므로 모델 변경 시 재분리 필요
- [ ] mel_strict 0.15 목표가 현실적인지 재평가 필요 — Phase A+B 예상 0.10-0.13, Phase C 없이는 0.15 미달 가능. perceptual_score를 보조/대안 목표로 격상할지 사용자 판단 필요
