# Project Directives (필수 지침)

이 파일은 환경이 바뀌어도 반드시 따라야 할 프로젝트 규칙을 정의합니다.

## 핵심 목표

- MP3에서 **오른손 멜로디**(보컬 멜로디에 해당)를 추출하여 MusicXML 악보로 변환

## 절대 명제 (Absolute Rules)

**아래 규칙은 환경, 세션, 에이전트가 바뀌어도 반드시 따라야 하는 불변 규칙이다.**

1. **MP3만으로 '들을 수 있는 멜로디'를 추출하는 것이 최종 목표**
   - '정확한 추출'이 아닌 **'들을 수 있는 멜로디'** — 사람이 들었을 때 원곡 멜로디를 인식할 수 있어야 한다
   - .mxl 참조 파일 없이 MP3 → MusicXML 변환이 반드시 달성되어야 함
   - 참조 파일 의존 방식으로 목표 달성했다고 간주하지 말 것

2. **참조 데이터 특성과 비교 기준**
   - 참조 악보(.mxl)는 피아노 편곡: Part 0 = 오른손(멜로디+화음/내성), Part 1 = 왼손(반주)
   - 비교 대상은 오른손의 **멜로디 단선율** (화음/내성 제외)
   - 참조는 음원의 편곡 패턴(멜로디/반주 분리, 음역대, 리듬)을 분석하여 추출 파이프라인 개선에 활용
   - 단순히 "추출 후 테스트"용이 아니라 **패턴 분석용**으로 활용
   - 단, 참조에 과적합(overfitting)되지 않도록 주의 — 최종 목표는 모든 음원에 대한 범용 추출

3. **모든 작업·분석·방향성을 이 파일에 기록**
   - 변경 전 베이스라인 → 변경 내용(파일, 파라미터, 로직) → 변경 후 수치
   - 시도했으나 폐기한 변경도 기록 (동일 실수 반복 방지)
   - 분석/진단 결과는 나오는 즉시 기록 (컨텍스트에만 두지 않는다)
   - 다음 방향성과 그 이유를 함께 기록 (예: "다음: X 시도 — 이유: Y 분석 결과 Z가 원인")
   - 방향이 바뀔 때 이전 방향을 버린 이유도 기록
   - 버전 번호 순차 부여, 각 버전에 날짜와 한줄 요약
   - **모든 세션에서 작업 시작 전 이 파일을 먼저 읽고 최신 이력 확인 후 진행**

4. **Output = Evaluation Identity (출력 = 평가 동일성)**
   - 평가하는 노트 시퀀스는 최종 MusicXML 출력 노트와 **완전히 동일**해야 한다
   - 추출 결과 → 그대로 악보 저장 → 그대로 평가 (중간에 참조 기반 보정 삽입 금지)
   - 메트릭이 높아도 실제 출력물과 다른 노트를 평가했다면 그 메트릭은 무의미

5. **허용 범위(Tolerance) vs 변환(Transformation) 구분**
   - **Tolerance (허용)**: 비교 시 매칭 허용 범위 (예: ±50ms onset, ±1 semitone) → OK
   - **Transformation (변환)**: 참조를 이용해 추출 노트 자체를 변경 (예: 옥타브 보정, 타임 오프셋) → **금지**
   - Tolerance는 "얼마나 비슷한가"를 측정하는 자(ruler)
   - Transformation은 "참조에 맞춰 답을 고치는" 부정행위
   - 파이프라인 내부에서 참조 없이 자체적으로 수행하는 보정은 Transformation이 아님

## 변경 이력

### v1 Reset (2026-03-03) — 프로젝트 초기화, 올바른 평가 체계 구축

**이유**: v9~v21(47+ 실험)에서 evaluate.py가 참조 기반 보정(time offset, octave correction)을 적용한 후 평가하여 메트릭이 부풀려짐. 실제 MusicXML 출력물과 평가 노트가 달랐기 때문에 모든 메트릭이 무의미했음.

**변경 사항**:
- 전체 코드베이스 초기화 및 재설계
- 파이프라인: MP3 → Demucs 보컬분리 → CREPE F0 → Note 세그먼테이션 → 자체 후처리 → MusicXML
- 평가: pipeline → MusicXML 저장 → **다시 로드(round-trip)** → 참조와 비교 (Rule 4 보장)
- Primary metric: `melody_f1_strict` (exact pitch, 50ms onset) — pc_f1 폐기
- postprocess.py에서 `ref_notes` 파라미터 완전 제거 (아키텍처 가드레일)
- 모든 보정은 자체적(self-contained): outlier 제거, same-pitch merge, self-octave correction, vocal range clip

**모듈 구조**:
- `core/types.py` — Note, F0Contour dataclass
- `core/vocal_separator.py` — Demucs htdemucs_ft + MD5 캐싱
- `core/pitch_extractor.py` — CREPE F0 추출 (Viterbi decoding)
- `core/note_segmenter.py` — F0 contour → Note list
- `core/postprocess.py` — 자체 보정만 (ref 입력 금지)
- `core/musicxml_writer.py` — save + load round-trip
- `core/pipeline.py` — extract_melody(mp3) 단일 진입점
- `core/reference_extractor.py` — 평가 전용 skyline
- `core/comparator.py` — tolerance 기반 메트릭
- `scripts/evaluate.py` — round-trip 평가 (Rule 4)
- `scripts/extract.py` — CLI 추출
- `scripts/analyze_reference.py` — 참조 패턴 분석

**검증 완료**:
- Round-trip identity test: PASS (save → load → 노트 동일)
- 참조 불침투: pipeline 모듈에 ref 파라미터 0건
- 모듈 import: 전체 PASS
- Segmenter + Postprocess 단위 테스트: PASS

**단일곡 예비 결과 (꿈의 버스)**:
- melody_f1_strict: 0.058, melody_f1_lenient: 0.157, pc_f1: 0.166
- onset_f1: 0.501, chroma_similarity: 0.996
- Gen: 389 notes (MIDI 68-84), Ref: 477 notes (MIDI 68-90)
- 참고: 이전 v10에서 참조 기반 보정 적용 시 pc_f1=0.728이었으나, 그것은 부정 메트릭
- 진정한 baseline은 낮지만 이것이 실제 출력물의 정확도

**참조 분석 결과 (8곡)**:
- 꿈의 버스: BPM=180, 477노트, pitch 68-90 (med=76), 82% stepwise
- Golden: BPM=183, 588노트, pitch 62-93 (med=79), 71% stepwise
- IRIS OUT: BPM=135, 734노트, pitch 55-95 (med=71), 64% stepwise
- 너에게100퍼센트: BPM=159, 649노트, pitch 72-87 (med=80), 62% stepwise
- 달리: BPM=68, 607노트, pitch 60-80 (med=73), 77% stepwise
- 등불을 지키다: BPM=112, 653노트, pitch 63-82 (med=72), 85% stepwise
- 비비드라라러브: BPM=170, 455노트, pitch 53-86 (med=65), 76% stepwise
- 여름이었다: BPM=180, 625노트, pitch 57-83 (med=71), 69% stepwise

**8곡 full baseline**: 평가 실행 중 (CREPE CPU 처리로 수 시간 소요)

### v2 Timing (2026-03-03) — BPM 반템포 보정 + beat-aligned onset snapping

**이유**: 꿈의 버스에서 mel_strict=0.058, onset_f1=0.501. 피치는 맞지만(chroma=0.996) onset 타이밍이 안 맞음.
원인 분석: librosa가 BPM을 89로 추정 (실제 ~180), MusicXML 양자화 그리드가 왜곡됨.

**변경 사항**:
1. `core/pipeline.py` — `_estimate_bpm()` 템포 옥타브 보정
   - BPM < 100일 때 onset autocorrelation으로 2배 템포 후보 검증
   - ac[double_lag]/ac[bpm_lag] > 0.8이면 BPM 2배 적용
   - 꿈의 버스: 89 → 178 BPM 보정 확인
2. `core/postprocess.py` — `_snap_to_beats()` 추가
   - librosa beat tracking → subdivision grid (16th note) 생성
   - 각 onset을 가장 가까운 grid point에 snap (max_snap = half subdivision)
   - **원본 MP3** audio 사용 (drums/bass 있어서 beat 감지 양호)
   - 참조 데이터 불침투: audio만 사용, ref 파라미터 없음
3. `core/pipeline.py` — BPM을 Step 0에서 미리 추정, mp3_audio를 postprocess에 전달

**검증**:
- Import: PASS
- BPM 보정: 89 → 178 (expected ~180) PASS
- 참조 불침투: postprocess/pipeline 모두 ref 파라미터 0건 PASS
- 꿈의 버스 전체 평가: 미완 (CREPE CPU ~25분 소요)

### v3 Analysis (2026-03-03) — v2 baseline 8곡 평가 완료 + 분석

**데이터**: results/v2_baseline.json (8곡 full round-trip 평가)

**주요 발견**:
1. **Chroma vs Melody 메트릭 역전**
   - chroma_similarity=0.972 (매우 높음) but melody_f1_strict=0.040 (극히 낮음)
   - 해석: 음정 contour는 정확하나 pitch register와 onset timing이 모두 문제

2. **너에게100퍼센트 mel_strict=0.000 (유일)**
   - ref pitch range: 72-87 (좁은 범위, 높은 음역)
   - pc_f1=0.187 (평균과 유사)
   - chroma=0.992 (높음)
   - 원인: CREPE의 subharmonic lock이 높은 음역대에서 심함 (global +12 보정 불충분)
   - 또는 높은 음역대 onset snap이 과도함 (beat grid snapping이 음정까지 왜곡)

3. **MusicXML 라운드트립 노트 수 증가**
   - Golden: 368 저장 → (load 시 몇 개?)
   - IRIS OUT: 311 저장 → (load 시 몇 개?)
   - 꿈의 버스: 457 저장 (ref 477과 유사)
   - 패턴: 많은 곡에서 음역대별 note_count_ratio < 1 → 음지가 손실됨
   - 의심: musicxml_writer.py의 note 병합/타이 로직이 save 시점에 작동, load 시 분할

4. **Onset_f1 평균 0.417**
   - 반대의 연호 평가로 보면: ~42% 정도만 정확한 타이밍
   - beat snap이 onset을 "정확히" 만들지는 못함 (아마도 off-beat phrase, dotted rhythm 문제)

5. **곡별 성능 편차**
   - 좋음: IRIS OUT (mel_strict=0.122), 여름이었다 (mel_strict=0.060)
   - 나쁨: Golden (mel_strict=0.013), 너에게100퍼센트 (mel_strict=0.000)
   - 상관관계: BPM/stepwise%/음역대와의 직접 상관 약함 → 다른 요소 (harmony complexity, vocal articulation 등)

**3개 에이전트 분석 종합 — 핵심 병목 3가지**:

1. **BPM 추정 오류** (음악-이론, DSP 에이전트 지적)
   - 현재: 풀믹스 기반 librosa.tempo() → 하프 템포 감지 (예: 180→89)
   - 원인: percussion/bass가 주파수 대역을 지배, BPM 감지 이중화
   - 해결책: 보컬 기반 beat_track() 사용 (v21에서 이미 검증됨)

2. **CREPE 서브하모닉 + global +12 고정 보정** (DSP, 음악-이론 지적)
   - 현재: CREPE median 58-71 MIDI → global +12 → 70-83 MIDI (모든 곡 동일)
   - 문제: 곡별 음역대 편차 미대응. 너에게100퍼센트(ref 72-87)에서 mel_strict=0.000
   - 원인: 높은 음역대에서 subharmonic lock 심함, +12 보정이 과도할 수 있음
   - 해결책: 구간별 적응형 옥타브 보정 또는 CREPE confidence threshold 하향 (0.5→0.35)

3. **MusicXML 라운드트립 노트 손실** (DSP, 메트릭 에이전트 지적)
   - 현재: musicxml_writer.py에서 makeMeasures() 사용 + 16분음표 고정 양자화
   - 문제: save 시 노트 병합/타이 처리 → load 시 파괴 또는 이중화 (Golden 368→?, IRIS OUT 311→?)
   - 원인: music21 makeMeasures()가 aggressive note consolidation 수행
   - 해결책: v21의 musicxml_writer_v2.py 방식 (명시적 measure 구성, makeMeasures 제거)

**다음 방향 (우선순위 순)**:
1. [LOW effort] BPM 추정을 보컬 기반으로 변경 + beat snap에 vocals 신호 전달
2. [LOW effort] CREPE confidence 0.5→0.35, min_note_duration 0.08→0.05 (false positive 제거)
3. [MED effort] 적응형 구간별 옥타브 보정 (pitch histogram 기반)
4. [MED effort] MusicXML writer v2 방식 교체 (makeMeasures 제거, 명시적 measure)
5. [LOW effort] Viterbi 후 median filter 제거 (이중 스무딩 방지)

**근거**:
- v2 파이프라인은 chroma(0.972), contour(0.767)에서는 우수
- 그러나 mel_strict(0.040) 극히 낮음 → onset/pitch register 문제 복합
- 위 3가지 병목 해결 시 mel_strict 0.040→0.150+ 예상 (chroma 높으므로)

### v3 Implementation (2026-03-03) — 5단계 파이프라인 개선

**목표**: v2 baseline mel_strict 0.040 → 0.15+ (v3 Analysis에서 식별된 3대 병목 해결)

**Step #1: BPM 보컬 기반 변경**
- `core/pipeline.py`: BPM 추정을 풀믹스→보컬로 이동 (Step 1 보컬분리 이후)
- `_estimate_bpm(mp3_path)` → `_estimate_bpm_from_audio(vocals_22k, 22050)`
- postprocess beat snap도 보컬 오디오 전달: `postprocess_notes(notes, audio=vocals_22k, sr=22050)`

**Step #2: CREPE 파라미터 튜닝**
- `core/pitch_extractor.py`: median filter size 5→3 (Viterbi와 이중 스무딩 완화)
- `core/note_segmenter.py`: min_note_duration 0.08→0.06 (60ms), max_gap_frames 3→5 (50ms 브리징)
- confidence_threshold: 0.3, 0.4 시도 → 과도한 노트 생성으로 폐기, 0.5 유지
- median filter 완전 제거 시도 → 일부 곡 하락으로 size=3으로 절충

**Step #3: 적응형 구간별 옥타브 보정**
- `core/postprocess.py`: `_global_octave_adjust()` 재작성
- vocal_center 72→75 (Eb5, CREPE 서브하모닉 상향 편향)
- 글로벌 최적 시프트 [-24,-12,+12,+24] 탐색 후 적용
- 글로벌 시프트=0일 때 구간별(30노트) 보정 폴백
- 효과: 너에게100퍼센트 mel_strict 0.000→0.091

**Step #4: MusicXML writer 개선**
- `core/musicxml_writer.py`: 전면 재작성
- `makeMeasures(inPlace=True)` 제거 → 명시적 `Measure` 객체 생성
- 양자화 그리드: 16분음표(0.25)→8분음표(0.5)
- 마디 경계 노트 분할 + tie(start/continue/stop) 명시 처리
- `load_musicxml_notes()`: 타이드 노트 병합으로 라운드트립 일관성 보장
- 라운드트립 검증: save 5노트 → load 5노트 일치 확인
- 효과: IRIS OUT 0.085→0.181, 달리 0.039→0.158 대폭 개선

**Step #5: beat snap 그리드 통일**
- `core/postprocess.py`: `_snap_to_beats()` subdivisions 4(16분음표)→2(8분음표)
- MusicXML 8분음표 그리드와 일관성 확보

**결과 (v3 step4 기준, 8곡 평균)**:

| 지표 | v2 baseline | v3 step4 | 변화 |
|------|-------------|----------|------|
| mel_strict | 0.040 | **0.066** | +65% |
| mel_lenient | 0.106 | **0.173** | +63% |
| pc_f1 | 0.149 | **0.189** | +27% |
| onset_f1 | 0.417 | **0.481** | +15% |
| contour | 0.767 | **0.786** | +2% |
| chroma | 0.972 | **0.969** | -0.3% |

**곡별 주요 변화**:
- IRIS OUT: mel_strict 0.122→0.181 (+48%)
- 달리 표현할 수 없어요: mel_strict 0.020→0.158 (+690%)
- 너에게100퍼센트: mel_strict 0.000→0.039 (개선, step3b에서 0.091이었으나 8분음표 그리드로 소폭 하락)

**폐기한 시도**:
- CREPE confidence 0.3: 노트 과잉 생성 (달리 668→990노트), mel_strict 하락
- CREPE confidence 0.4: IRIS OUT mel_strict 0.122→0.048 하락
- median filter 완전 제거: 일부 곡 피치 안정성 저하

**다음 방향**:
- 전곡 최종 평가 (step5 포함) 실행 필요
- 8분음표 그리드가 일부 빠른 곡에서 과도할 수 있음 → 적응형 그리드 검토
- 여전히 mel_strict 0.066으로 목표(0.15) 미달 → pitch register 정확도 추가 개선 필요

### v4 Adaptive Grid (2026-03-04) — BPM 적응형 양자화 그리드

**이유**: 꿈의 버스(BPM=180) 청음 시 v3보다 v2가 멜로디 구분이 더 잘 됨.
music-melody-expert 에이전트 분석 결과, v3에서 8분음표 그리드(subdivisions=2, quantize=0.5)가
BPM=180 곡의 리듬 해상도를 절반으로 낮춘 것이 원인.

**근거**:
- BPM=180에서 8분음표 = 0.169초 → 전체 duration의 61.2%가 동일 값으로 균일화
- IOI(음표 간 시간)가 4종류로만 집중, 리듬 변화 소멸
- 노트 수 22% 감소 (v2: 457 → v3: 356) — 동일 grid에 겹쳐 deduplicate
- 82% stepwise 원곡에서 리듬 구분 소실 → "같은 음 나열"로 들림

**변경 사항**:
1. `core/postprocess.py` — `_snap_to_beats()`: BPM 적응형 subdivisions
   - BPM >= 140: subdivisions=4 (16분음표)
   - BPM < 140: subdivisions=2 (8분음표)
   - BPM 파라미터 추가 (pipeline에서 전달)
2. `core/musicxml_writer.py` — `save_musicxml()`: BPM 적응형 양자화
   - BPM >= 140: 16분음표 그리드 (round * 4 / 4)
   - BPM < 140: 8분음표 그리드 (round * 2 / 2)
3. `core/pipeline.py` — BPM을 postprocess에 전달

**꿈의 버스 단일곡 결과**:

| 메트릭 | v2 | v3 | v4 |
|--------|-----|-----|-----|
| mel_strict | 0.058 | ~0.04 | 0.049 |
| onset_f1 | 0.501 | ~0.42 | 0.488 |
| chroma | 0.996 | ~0.97 | 0.993 |
| notes | 457 | 356 | 429/477 |

- 노트 수 v3(356) → v4(429) 회복 (+20%), grid points 1645개 (16분음표)
- max_snap=44ms로 BPM=172 16분음표 해상도 유지
- mel_strict v2(0.058)보다 소폭 하락 → BPM 보컬 기반(172 vs 178), 적응형 옥타브 보정(center=75) 영향
- 청음 검증 필요: v2 대비 멜로디 구분 개선 여부 확인

**남은 이슈**:
- BPM 보컬 기반 172 vs 풀믹스 178: 어느 쪽이 나은지 A/B 비교 필요
- mel_strict 0.049로 목표(0.15) 미달 → pitch register 정확도가 주요 병목

### v5 Hole Fix (2026-03-04) — 구멍난 악보 해결

**이유**: 청음 피드백 "멜로디가 중간중간 구멍난 악보 느낌". music-melody-expert 분석 결과
161개 구멍(45.2초, 곡의 28%)이 프레이즈 내부에 존재. 출력 커버리지 67.3% vs 참조 92.0%.

**근본 원인 3가지**:
1. gap bridging이 same-pitch일 때만 동작 → 비브라토(72→0→73)에서 bridge 거부
2. CREPE confidence 0.5가 너무 높아 브레시/비브라토 구간 삭제
3. VOCAL_RANGE_HIGH=84가 참조 상한(MIDI 90)보다 낮아 고음 노트 차단

**변경 사항**:
1. `core/note_segmenter.py` — gap bridging pitch tolerance ±2 semitone, max_gap 5→10 frames
2. `core/pitch_extractor.py` — confidence_threshold 0.5→0.35
3. `core/postprocess.py` — VOCAL_RANGE_HIGH 84→96

**꿈의 버스 결과**:

| 메트릭 | v4 | v5 | 변화 |
|--------|-----|-----|------|
| mel_strict | 0.049 | 0.032 | -35% (strict 하락) |
| mel_lenient | 0.137 | 0.265 | +93% (대폭 상승) |
| pc_f1 | 0.141 | 0.267 | +89% (대폭 상승) |
| onset_f1 | 0.488 | 0.474 | -3% |
| notes | 429/477 | 473/477 | 구멍 해소 |

**해석**:
- 노트 수 473/477 → 구멍 거의 다 메워짐 (목표 달성)
- mel_lenient +93% → 대략적 멜로디는 훨씬 개선 (청음 체감 개선 예상)
- mel_strict -35% → confidence 0.35로 내린 노트의 피치 정확도가 낮아 exact match 하락
- 트레이드오프: 구멍 해소 vs 피치 정확도. 청음 체감은 구멍 해소가 우선

**v5 8곡 전체 평가 결과 (2026-03-05, results/v5_full.json)**:

| 곡 | mel_strict | mel_lenient | pc_f1 | onset_f1 | chroma | contour | notes |
|----|-----------|-------------|-------|----------|--------|---------|-------|
| Golden | 0.041 | 0.141 | 0.165 | 0.378 | 0.986 | 0.798 | 348/588 |
| IRIS OUT | **0.171** | **0.329** | **0.349** | 0.556 | 0.871 | 0.704 | 389/734 |
| 꿈의 버스 | 0.046 | 0.131 | 0.136 | 0.492 | 0.993 | 0.738 | 482/477 |
| 너에게100퍼센트 | 0.041 | 0.155 | 0.158 | 0.490 | 0.988 | 0.723 | 526/649 |
| 달리 표현할 수 없어요 | **0.122** | **0.411** | **0.421** | **0.591** | 0.983 | 0.803 | 686/607 |
| 등불을 지키다 | 0.057 | 0.061 | 0.076 | 0.579 | 0.966 | 0.875 | 394/653 |
| 비비드라라러브 | 0.004 | 0.051 | 0.096 | 0.373 | 0.936 | 0.792 | 483/455 |
| 여름이었다 | 0.034 | 0.157 | 0.189 | 0.495 | 0.996 | 0.720 | 506/625 |
| **평균** | **0.065** | **0.180** | **0.199** | **0.494** | **0.965** | **0.769** | - |

**v3 → v5 비교 (8곡 평균)**:

| 지표 | v3 | v5 | 변화 |
|------|-----|-----|------|
| mel_strict | 0.066 | 0.065 | -2% (거의 동일) |
| mel_lenient | 0.173 | 0.180 | +4% |
| pc_f1 | 0.189 | 0.199 | +5% |
| onset_f1 | 0.481 | 0.494 | +3% |
| chroma | 0.969 | 0.965 | -0.4% |
| contour | 0.786 | 0.769 | -2% |

**분석**:
- mel_strict 평균 0.065로 v3(0.066)과 거의 동일 — 구멍 해소는 되었으나 추가 노트의 피치 정확도가 낮음
- mel_lenient +4% → 대략적 멜로디 품질은 소폭 개선
- 최고: IRIS OUT(0.171), 달리(0.122) — 다른 곡 대비 월등
- 최저: 비비드라라러브(0.004) — 서브하모닉 심각, 구조적 불일치
- 등불을 지키다: onset_f1=0.579(높음) but mel_lenient=0.061(극히 낮음) → 피치 레지스터 완전 불일치
- 비비드라라러브 CREPE 8시간+ 소요 (CPU bottleneck 심각)

**다음 방향**:
- mel_strict 0.065 → 0.15 목표 달성을 위해 pitch register 정확도가 핵심
- 등불을 지키다/비비드라라러브의 피치 레지스터 문제 해결 필요
- confidence 0.35 노트에 대한 피치 보정 강화 검토
- MusicXML round-trip 노트 손실 문제 (Golden 431→348, 등불을 551→394) 해결 필요

### v6 Quality Fix (2026-03-04) — 잡음 제거 + gap bridge 정밀화 + confidence 조정

**이유**: v5 청음 피드백 "매꿔야 할 데는 안 매꿔지고, 필요 없는 곳에 노트 추가됨".
music-melody-expert 분석 결과:
- 추출 578노트 vs 참조 486노트 (92개 초과 — FP 과다)
- FP 186개 중 60.8%가 16분음표 이하의 극히 짧은 잡음 노트
- 비조성 노트 67개 (A major에서 C/F/G 등 — CREPE 저신뢰 피치 오차)
- gap bridging ±2st가 서로 다른 노트 경계를 합쳐 8분음표 프레이즈 파괴
- flat bias: exact pitch 41.6%, -2st 22.2%, -1st 13.5%

**근본 원인**: v5의 3가지 변경(confidence 0.5→0.35, gap bridge ±2st/10frames, range 84→96)이
모두 과도하게 공격적 → 구멍은 일부만 메꿔지고 잡음 대량 유입

**변경 사항**:
1. `core/pitch_extractor.py` — confidence 0.35→0.40 (FP/FN 절충)
2. `core/note_segmenter.py` — gap bridging 조건 강화:
   - 같은 피치: 기존대로 bridge (max_gap_frames=10)
   - 다른 피치(±2st): gap≤3 frames(30ms)일 때만 bridge (짧은 비브라토만 허용)
   - 이외: bridge 안 함 (노트 경계 보존)
3. `core/postprocess.py` — diatonic gate 추가:
   - key 감지 후 비조성+짧은(0.15s 미만) 노트 제거
   - 자체 key 추정 (노트 chroma histogram 기반)
   - ARCHITECTURE GUARD 준수 (참조 데이터 미사용)

**8곡 전체 평가 결과 (v6 vs v3 step4)**:

| 지표 | v2 baseline | v3 step4 | **v6** | v2→v6 |
|------|-------------|----------|--------|-------|
| mel_strict | 0.040 | 0.066 | **0.067** | +68% |
| mel_lenient | 0.106 | 0.173 | **0.191** | +80% |
| pc_f1 | 0.158 | 0.189 | **0.209** | +32% |
| onset_f1 | 0.417 | 0.481 | **0.470** | +13% |
| chroma | 0.972 | 0.969 | **0.972** | 0% |
| contour | 0.767 | 0.786 | **0.788** | +3% |

**곡별 변화 (v3→v6)**:
- 개선 6곡: Golden, 너에게100퍼센트, 등불을 지키다, 비비드라라러브, 여름이었다, 꿈의 버스(lenient)
- 유사 1곡: IRIS OUT
- 하락 1곡: 달리 (mel_strict 0.158→0.117, diatonic gate가 17% 노트 과다 제거)

**범용성 판정**: 과적합 아님 — 8곡 중 6곡 개선, mel_lenient 평균 +10%

**Diatonic gate 관찰**:
- 꿈의 버스: A major 정확, 52/469 제거 (11%) — 적절
- IRIS OUT: A major 추정, 95/447 제거 (21%) — 과다 가능성
- 달리: C# major 추정, 162/953 제거 (17%) — 과다, strict 하락 원인
- 등불을 지키다: G# major 추정, 83/508 제거 (16%)

### v6 심층 분석 (2026-03-04) — 참조 멜로디 vs 추출 비교 (3곡)

**분석 방법**: music-melody-expert 에이전트가 꿈의 버스, Golden, 너에게100퍼센트의 참조 멜로디와 v6 추출 결과를 비교 (패턴 분석용, Rule 2 준수)

**3곡 공통 문제 패턴 5가지**:

1. **Pitch Compression** — 고음/저음이 중앙으로 끌림
   - self_octave_correction(threshold=7)이 정상적 7-10st 도약을 오판하여 -12st 보정
   - 너에게100퍼센트: ref MIDI 85,87 노트 전부 손실 (ext max 84)
   - global_octave_adjust vocal_center=75 고정 (실제 곡 median 76-80)

2. **CREPE Harmonic Confusion** — 4th/5th 간격(5st, 7st) 오추정
   - Golden: matched notes 37%가 quartal error, 너에게100퍼센트: 28%
   - 옥타브 오류와 전혀 다른 유형 (2nd/3rd harmonic partial lock)
   - Viterbi decoding으로도 해결 안 됨

3. **Micro-artifacts** — 34-36% 노트가 최소 grid 길이 (참조에는 0개)
   - min_note_duration 0.06s가 너무 낮아 jitter artifact 통과
   - 참조 최단: 0.082-0.189s (BPM에 따라)

4. **Phrase-level Gaps** — FN의 71-82%가 구간 통째로 누락
   - Demucs 보컬 분리 실패 구간에서 confidence 전체 하락

5. **BPM 오추정** — Golden: 123 vs 실제 183 (3:2 비율, 치명적)
   - 현재 disambiguation이 BPM<100일 때만 2:1 검증
   - 3:2 ratio 미대응, BPM>=100 구간 미검증

**폐기한 시도 (v7)**:
- P2 Harmonic correction (±5/7st context 기반 보정): 정상적 melodic leap까지 보정 → 꿈의 버스 0.032→0.002, 너에게100퍼센트 0.050→0.000. 평균 mel_strict 0.067→0.047
- P4 threshold 7→10: octave correction이 느슨해져 오히려 하락
- P5 dynamic vocal_center: CREPE 서브하모닉 피치의 weighted avg를 center로 쓰면 octave shift 방향 오판 → 꿈의 버스 0.032→0.005, 너에게100퍼센트 0.050→0.000
- **교훈**: CREPE 출력 자체가 이미 왜곡되어 있으므로, 왜곡된 데이터 기반의 자기참조 보정은 오류를 증폭함. 외부 기준(고정 center, 고정 threshold)이 더 안정적

**폐기한 시도 (v8 FCPE)**:
- FCPE(torchfcpe) 단독으로 CREPE 대체: mel_strict 0.067→0.055, mel_lenient 0.191→0.138
- 너에게100퍼센트, 비비드라라러브에서 개선이나 달리 대폭 하락(0.117→0.033)
- 속도는 5-15배 빠름(곡당 1-5초). 일부 곡에서 CREPE와 보완적이나 단독으로는 부족

**폐기한 시도 (v9 Highpass+CQT)**:
- 100Hz highpass filter + CQT spectral energy 기반 octave verification
- mel_strict 0.067→0.021 (-69%), mel_lenient 0.191→0.075 (-61%)
- CQT octave verify가 41% 노트를 보정하며 올바른 옥타브를 잘못된 쪽으로 이동
- CQT 에너지에서 서브하모닉/배음 구분이 안 됨 — 원래 기대한 "CQT gives correct register"가 isolated vocal에서도 안정적이지 않음
- **교훈**: 피치 보정 방향의 접근은 전반적으로 한계. 보정할수록 악화됨

**8곡 전체 추가 분석 (나머지 5곡)**:

추가 패턴 3가지 발견:
- [F] Boundary Overflow: 비비드에서 곡 종료 후 83초간 122개 잡음 노트 (Demucs 악기 오인)
- [G] Same-pitch Repetition Loss: **전체 8곡** 평균 22pp 손실 (merge_same_pitch가 re-attack 무시)
- [H] Grid Threshold Edge: IRIS OUT (BPM=136) 140 임계값 바로 아래 → 89.5% 동일 duration

8곡 패턴 분포: Pitch Compression 6/8, Quartal>15% 5/8, Grid Lock 4/8, Phrase Gaps 4/8, BPM err 2/8, Same-pitch Loss **8/8**

**폐기한 시도 (v10 SOME end-to-end)**:
- SOME (Singing-Oriented MIDI Extractor) — 중국어 노래 5명 데이터로 훈련된 end-to-end 모델
- CREPE+segmenter를 SOME으로 완전 대체 (F0 추출 + 노트 분할 모두 SOME이 수행)
- mel_strict 0.067→0.033 (-51%), mel_lenient 0.191→0.091 (-52%)
- contour만 0.767→0.801 (+4%) 개선 — 멜로디 윤곽은 더 정확하나 pitch/timing 매칭 저조
- 원인: (1) 중국어 노래 훈련 → 한국 팝 일반화 부족, (2) 후처리가 CREPE 오류 패턴에 맞춰져 있어 SOME 출력과 충돌
- 파일: core/note_extractor_some.py (파이프라인에서 미사용, 참고용)

**다음 방향 (우선순위순, 8곡 데이터 기반, 모두 범용/참조 미사용)**:
1. **RMVPE F0 추출기** — subharmonic에 강한 별도 F0 모델 (pip 미지원, 설치 복잡)
2. ~~[G] Same-pitch re-attack — amplitude envelope로 re-attack 감지 (8/8곡)~~ → v11에서 구현
3. [P3+H] Grid 개선 — BPM-adaptive min_note_duration (4/8곡)
4. [P1] BPM disambiguation — 다중 ratio 후보 검증 (2/8곡)
5. [F] Boundary overflow — energy envelope 기반 곡 끝 감지 (1/8곡)

### v11 Re-attack Detection (2026-03-05) — Same-pitch re-attack 감지

**이유**: v6 심층 분석에서 Same-pitch Repetition Loss가 **8/8곡** 공통 문제로 식별 (~22pp 손실).
`_merge_same_pitch()`이 gap < 0.15s인 연속 동일 피치 노트를 맹목적으로 병합, 가수의 re-attack(같은 음 반복) 리듬 정보 소실.

**변경 사항**:
1. `core/postprocess.py` — `_merge_same_pitch()` 개선
   - 기존: gap < 0.15s이면 무조건 병합
   - 변경: 보컬 amplitude envelope 분석으로 re-attack 감지
   - gap >= 20ms일 때 gap 구간 RMS vs 전후 노트 RMS 비교
   - dip_ratio < 0.4 (gap RMS가 주변의 40% 미만) → re-attack으로 판정, 병합 안 함
   - gap < 20ms → CREPE 프레임 아티팩트, 기존대로 병합
2. `_detect_reattack()` 함수 추가
   - 30ms context window로 전후 노트 amplitude 측정
   - self-contained: 보컬 오디오만 사용, 참조 데이터 미사용

**검증**:
- Unit test: 4가지 시나리오 PASS (no audio, no dip, dip, short gap)
- 참조 불침투: audio만 사용, ref 파라미터 없음
- 8곡 전체 평가: 실행 중 (results/v11_reattack.json)

**8곡 전체 평가 결과**: (평가 완료 후 기록)

**아키텍처 변경 필요성 확인 (v7~v10 6회 실패)**:
- CREPE 파라미터 튜닝 한계 도달 (v6 mel_strict=0.067이 ceiling)
- 후처리 기반 pitch 보정 전부 실패 (v7 harmonic, v7b dynamic center, v9 CQT)
- 대안 F0 추출기 단독 사용도 부족 (v8 FCPE, v10 SOME)
- 남은 유망 경로: RMVPE (subharmonic 전용 설계), CREPE+FCPE 앙상블

(이전 v9~v21 이력은 git history 참조)
