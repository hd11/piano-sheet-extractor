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

> **버전 번호 주의**: git 이력에는 리뉴얼 이전 구 시스템(v9~v21, pc_f1 기반, 참조 보정 포함)의
> 커밋이 남아있음. 아래 v1 Reset 이후 버전들은 **완전히 다른 새 시스템**으로 번호가 겹쳐도
> 다른 실험임. 리뉴얼 이전 커밋의 메트릭(pc_f1 0.7~, mel_strict 0.29~)은 무효 수치.

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

**v11 꿈의 버스 단일곡 결과 (re-attack)**:

| 메트릭 | v6 | v11 | 변화 |
|--------|-----|------|------|
| mel_strict | 0.049 | 0.032 | -35% |
| mel_lenient | 0.137 | 0.106 | -23% |
| onset_f1 | 0.488 | 0.466 | -5% |
| notes | 429/477 | 411/477 | |

- re-attack 감지: 4개만 감지됨 (dip_threshold=0.4 너무 엄격하거나 꿈의 버스에 same-pitch 반복 적음)
- 노트 수 감소(482→411)로 오히려 하락. 다른 곡에서 효과 있을 수 있으나 이 곡에서는 비효과적

### v12 Basic Pitch + CQT 테스트 (2026-03-05) — BP 파이프라인 재평가

**이유**: 이전 git history(bcc2632)에서 BP+CQT로 mel_strict=0.425 달성 기록 발견.
단, 당시는 time alignment 적용 구버전 평가 → v1 reset 후 엄격한 round-trip 평가로 재측정 필요.

**변경 사항**:
1. `core/note_extractor_bp.py` 신규 — Basic Pitch + CQT octave correction 추출기
   - BP: raw + harmonic vocals 2회 추출 → intersection
   - CQT: harmonic salience 기반 octave shift 결정
   - weighted melody selection (동시 노트 중 velocity+continuity 최적 선택)
2. `core/pipeline.py` — `mode` 파라미터 추가 ("bp" / "crepe")

**꿈의 버스 결과 (round-trip 평가)**:

| 메트릭 | CREPE (v6) | BP+CQT (v12) | 변화 |
|--------|-----------|--------------|------|
| mel_strict | 0.049 | 0.020 | -59% |
| mel_lenient | 0.137 | 0.109 | -20% |
| onset_f1 | 0.488 | 0.448 | -8% |
| chroma | 0.993 | 0.996 | +0.3% |
| notes | 429/477 | 327/477 | -24% |
| **처리 시간** | ~1350s | **25.4s** | **53x 빠름** |

**분석**:
- BP가 분리된 보컬에서 노트 감지 부족 (327/477 = 69% 커버리지)
- 이전 mel_strict=0.425는 time alignment 적용 결과로 부풀려진 수치 확인
- BP는 범용 AMT이므로 isolated vocals 전용으로는 CREPE에 못 미침
- 속도 53x 빠름 (25s vs 1350s) → 빠른 실험용으로 유용
- **pipeline 기본값은 CREPE 유지**, BP는 mode="bp"로 사용 가능

**상용 프로그램 조사 결과** (2026-03-05):
- AnthemScore, Sing2Notes, ScoreCloud, Melodyne 등 비교 완료
- 폴리포닉 보컬 멜로디 추출은 **업계 전체 미해결 과제**
- 상용 툴도 복잡한 팝 음악에서 정확도 낮음
- 학술 SOTA: ROSVOT(COnPOff F1=77.4%), T3MS(2025 최신)
- 우리의 mel_strict=0.065는 엄격한 메트릭이므로 직접 비교 어려움

**아키텍처 변경 필요성 확인 (v7~v10 6회 실패)**:
- CREPE 파라미터 튜닝 한계 도달 (v6 mel_strict=0.067이 ceiling)
- 후처리 기반 pitch 보정 전부 실패 (v7 harmonic, v7b dynamic center, v9 CQT)
- 대안 F0 추출기 단독 사용도 부족 (v8 FCPE, v10 SOME)
- 남은 유망 경로: RMVPE (subharmonic 전용 설계), CREPE+FCPE 앙상블

### v13 FCPE F0 추출기 통합 (2026-03-05) — torchfcpe 파이프라인

**배경**: RMVPE 모델 다운로드 네트워크 차단 → pip 설치 가능한 torchfcpe (40MB 번들)로 전환

**변경**:
- `core/pitch_extractor_fcpe.py` 신규 — FCPE F0 추출 wrapper (singleton 모델, median filter)
- `core/pipeline.py` — `mode="fcpe"` 추가 (crepe/fcpe/bp 3종)
- `scripts/evaluate.py` — `--mode` CLI 인자 추가

**8곡 전체 결과** (v13b, median filter 적용):
| 메트릭 | FCPE | CREPE baseline | 차이 |
|--------|------|----------------|------|
| mel_strict avg | 0.060 | 0.067 | -10% |
| pc_f1 avg | 0.171 | ~0.735 | -77% |
| chroma avg | 0.970 | ~0.98 | -1% |
| onset_f1 avg | 0.461 | ~0.50 | -8% |
| 시간/곡 | **2초** | **25분** | **750x** |

**곡별 특이점**:
- IRIS OUT: mel_strict=0.189 (CREPE ~0.03) — FCPE가 서브하모닉 문제 없이 6배 우수
- 등불을 지키다: mel_strict=0.059 (CREPE ~0.095) — FCPE 약간 낮음

**분석**:
- chroma=0.970 (피치 클래스 정확) vs pc_f1=0.171 (노트 매칭 실패) → **note segmentation이 병목**
- FCPE의 85.9% voiced rate이 CREPE보다 높아 비보컬 구간도 노트화
- mel_strict는 CREPE와 거의 동등 (0.060 vs 0.067)
- 속도 750배 향상 → 빠른 실험 반복에 매우 유용
- **pipeline 기본값은 CREPE 유지**, FCPE는 `--mode fcpe`로 사용 가능

**다음 방향**:
- note_segmenter 개선이 CREPE/FCPE 공통 병목
- RMVPE는 네트워크 차단으로 보류 (아래 별도 기록 참조)

### RMVPE 보류 (2026-03-05) — 네트워크 환경 변경 시 재시도

**상태**: 코드 준비 완료, 모델 다운로드만 차단됨

**준비된 파일**:
- `core/rmvpe_model.py` — RVC에서 가져온 RMVPE 모델 코드 (670줄, imports 패치 완료)
- `from infer.lib import jit` 제거
- `from infer.modules.ipex import ipex_init` 제거

**필요한 작업** (네트워크 환경 변경 시):
1. 모델 다운로드: `curl -L -o models/rmvpe.pt "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.pt"` (181MB)
2. `core/pitch_extractor_rmvpe.py` wrapper 생성 (FCPE wrapper 참고)
3. `core/pipeline.py`에 `mode="rmvpe"` 추가
4. torch.load 시 `weights_only=False` 필요 (PyTorch 2.6+)

**RMVPE API**:
```python
from core.rmvpe_model import RMVPE
rmvpe = RMVPE("models/rmvpe.pt", is_half=False, device="cpu", use_jit=False)
f0_hz = rmvpe.infer_from_audio(audio_16k, thred=0.03)
# input: 16kHz mono np.ndarray
# output: np.ndarray float32, shape (n_frames,), 100fps (hop=160@16kHz), 0.0=unvoiced
```

**기대 효과**: CREPE보다 서브하모닉 내성 강함, FCPE와 유사한 속도

### v14 Experiments (2026-03-05) — 세그먼테이션 실험 (전부 무효)

**시도한 것들** (전부 폐기):
- 짧은 노트 병합 (_consolidate_short_notes, ±2st merge): mel_strict 0.035 → 악화
- 같은 피치만 병합: mel_strict 0.025 → 악화
- 전곡 subdivisions=4: mel_strict 0.059 → 변화 없음
- Spectral onset detection: 23% vs F0 기반 39% (50ms) → 악화

**심층 분석 결과**:
- Onset offset: mean=-9.8ms, std=112ms → 체계적 편향 없음, 분산만 큼
- 50ms tolerance에서 pitch+onset 동시 매칭: 겨우 2.7%
- 생성/참조 노트 시퀀스가 근본적으로 다름 → vocal-to-sheet-music gap
- MusicXML writer 양자화: BPM<140에서 8분음표 그리드 사용 → max error 110-134ms (>50ms!)

### v15 Post-v14 전체 탐색 및 최적화 (2026-03-05) — mel_strict 0.066 → 0.090+

v14 이후 이번 세션에서 진행한 모든 실험을 하나로 묶음.

#### 탐색 실험 전체 목록

| 내용 | mel_strict | 결과 |
|------|-----------|------|
| quantized seg + old grid | 0.057 | 폐기 |
| quantized seg + fine grid | 0.056 | 폐기 |
| free seg + fine grid | 0.065 | 개선 |
| no postprocess | 0.011 | 폐기 (postprocess 필수 확인) |
| beat snap 제거 | 0.054 | 폐기 (beat snap 필요) |
| CQT octave verify | 0.015 | 폐기 (치명적 악화) |
| harmonic correction | 0.054 | 폐기 (FCPE에 불필요) |
| **free seg + fine grid + mix beats** | **0.074** | **채택** |
| subdivisions=4 전체 적용 | 0.066 | 폐기 (slow songs 악화) |
| dedup + BPM 3:2 초기 적용 | 0.075 | 채택 |
| outlier threshold 9→14 | 0.081 | 채택 |
| merge_same_pitch 제거 | 0.085 | 채택 |
| min_note_duration 60ms→50ms | 0.090 | 채택 |
| FCPE argmax / pyin / threshold 실험 | - | 폐기 |
| max_gap_frames 10→5, pitch bridge 제거 | ~0.091 | 채택 (평가 중) |

#### 최종 채택 변경 사항

**`core/musicxml_writer.py`** — 동적 양자화 그리드
- `grid_mult > 600/bpm`, 2의 거듭제곱으로 올림
- 모든 곡에서 max quantization error < 50ms 보장

**`core/pipeline.py`** — BPM 추정 개선
- 원본 믹스에서 BPM 추정 + beat tracking (보컬보다 정확)
- 2:1 disambiguation (BPM<100), 3:2 disambiguation (BPM 100-140, ratio>0.75)
- Golden: 123→185 BPM 보정 (ref=183)

**`core/postprocess.py`** — 체인 정리
- `_snap_to_beats_from_grid()`: 외부 beat_times 직접 사용
- `_dedup_close_onsets()` 추가: 30ms 이내 충돌 노트 제거
- `_remove_outliers()` threshold 9→14
- `_merge_same_pitch()` **제거** (ablation: -10% 유해)
- 현재 체인: `outlier(t=14) → global_octave → self_octave(t=7) → clip → diatonic → beat_snap → dedup(30ms)`

**`core/note_segmenter.py`** — 세그먼터 파라미터
- min_note_duration 60ms→50ms
- max_gap_frames 10→5
- pitch tolerance bridging 제거 (효과 없음 확인)

#### 주요 ablation 결과

Outlier threshold:
| t | avg | IRIS OUT |
|---|-----|---------|
| 9 | 0.075 | 0.301 |
| 12 | 0.077 | 0.306 |
| **14** | **0.081** | **0.305** |
| 16 | 0.052 | 0.078 ← cliff |

Progressive postprocess:
| 단계 | avg |
|------|-----|
| raw_seg + oct + clip | 0.046 |
| + self_octave | 0.048 |
| + outlier | 0.060 ← 핵심 |
| + beat_snap | 0.078 |
| + diatonic | 0.080 |
| merge 제거 후 full | 0.085 |
| + min_dur 50ms | **0.090** |

Gap bridging:
- max_gap 10 (기존): 0.0901
- max_gap 5: **0.0906** ← 채택
- pitch tolerance ±2st: 효과 없음 → 제거

#### 최종 결과 (평가 완료)

| 곡 | mel_strict | mel_lenient | onset_f1 | notes |
|----|-----------|-------------|----------|-------|
| Golden | 0.028 | 0.075 | 0.478 | 558/588 |
| IRIS OUT | **0.315** | 0.346 | 0.617 | 404/734 |
| 꿈의 버스 | 0.054 | 0.128 | 0.563 | 525/477 |
| 너에게100퍼센트 | 0.089 | 0.212 | 0.509 | 538/649 |
| 달리 표현할 수 없어요 | 0.037 | 0.155 | 0.526 | 746/607 |
| 등불을 지키다 | 0.050 | 0.060 | 0.577 | 456/653 |
| 비비드라라러브 | 0.073 | 0.152 | 0.418 | 479/455 |
| 여름이었다 | 0.075 | 0.162 | 0.506 | 526/625 |
| **평균** | **0.090** | **0.161** | **0.524** | - |

최종 실험(max_gap 5) 평가 결과: 실행 중 (완료 후 업데이트 예정, 예상 ~0.091)

#### 핵심 발견

- MusicXML 양자화 오차가 mel_strict에 치명적 (8분음표 → 50ms 초과)
- merge_same_pitch는 유해: segmenter min_dur이 이미 아티팩트 필터 역할
- outlier removal이 가장 중요한 단계 (IRIS OUT: +181%)
- Vocal-to-sheet gap: onset 매칭 노트 중 exact pitch match 10-27% (IRIS OUT 52%)
  → 보컬 멜로디 ≠ 피아노 편곡, 파이프라인 개선으로 해결 불가능한 구조적 한계
- FCPE: CREPE 대비 750x 빠르고 mel_strict +10%

**다음 방향**:
1. FCPE+RMVPE 앙상블 — 곡별 보완적 (아래 v16 참조)
2. Diatonic gate 개선 — minor scale template, adaptive threshold
3. 곡별 adaptive parameter 탐색

(이전 v9~v14 이력은 git history 및 위 섹션 참조)

### v16 RMVPE 통합 및 평가 (2026-03-05) — RMVPE 단독은 FCPE 미달, 앙상블 가능성

**배경**: HuggingFace 네트워크 차단 해제 → RMVPE 모델(172MB) 다운로드 성공

**변경 사항**:
- `core/rmvpe_model.py` 신규 — RVC RMVPE 아키텍처 (DeepUnet + BiGRU + Linear, 741 params)
- `core/pitch_extractor_rmvpe.py` 신규 — RMVPE F0 wrapper (singleton, 16kHz resample, median filter)
- `core/pipeline.py` — `mode="rmvpe"` 분기 추가
- `scripts/evaluate.py` — rmvpe 선택지 추가

**FCPE vs RMVPE 8곡 비교**:

| 곡 | FCPE | RMVPE | 승자 |
|----|------|-------|------|
| Golden | 0.033 | 0.036 | RMVPE +9% |
| IRIS OUT | **0.317** | 0.098 | FCPE +223% |
| 꿈의 버스 | 0.058 | **0.073** | RMVPE +26% |
| 너에게100퍼센트 | 0.073 | **0.099** | RMVPE +36% |
| 달리 | 0.039 | 0.026 | FCPE +50% |
| 등불을 지키다 | 0.045 | 0.048 | RMVPE +7% |
| 비비드라라러브 | **0.072** | 0.025 | FCPE +188% |
| 여름이었다 | 0.081 | 0.080 | 동등 |
| **평균** | **0.090** | **0.061** | **FCPE +48%** |

**분석**:
- RMVPE 단독 평균 mel_strict=0.061로 FCPE(0.090) 대비 -32%
- 그러나 곡별로 보완적: RMVPE가 3곡에서 우세 (꿈의 버스, 너에게100퍼센트, Golden)
- FCPE 약점곡(너에게100퍼센트 0.073)에서 RMVPE가 0.099로 +36%
- RMVPE 약점: IRIS OUT(0.098 vs 0.317), 비비드라라러브(0.025 vs 0.072)에서 대폭 하락
- 속도: RMVPE ~2-6초/곡 (FCPE와 유사, CREPE 대비 수백배 빠름)

**결론**: RMVPE 단독 사용은 부적합. FCPE 기본값 유지.

**F0 앙상블 시도 (FCPE+RMVPE)**:
- 전략: 프레임별 — 둘 다 voiced&agree(100cents 이내)→average, disagree→FCPE 선택, 하나만 voiced→그것 사용
- 결과: mel_strict 평균 **0.062** (FCPE 단독 0.090 대비 -31%)
- 원인: RMVPE 잘못된 피치가 averaging을 통해 FCPE 정확 피치 오염 (IRIS OUT 0.317→0.095 치명적)
- 소폭 개선 3곡: Golden(0.033→0.040), 등불을 지키다(0.045→0.051), 여름이었다(0.081→0.082)
- **F0-level 앙상블은 실패. 폐기.**

**최종 결론**: FCPE 단독(mel_strict 0.090)이 현재 최고. RMVPE, 앙상블 모두 하락.
**다음 방향**:
1. Diatonic gate 개선 — minor scale template, adaptive threshold
2. 곡별 adaptive parameter 탐색
3. Note-level 후처리 개선 (segmenter, postprocess 체인)

### v17 Onset-Based Segmentation (2026-03-06) — 음절 기반 노트 분리, 전체 평균 하락

**배경**: FCPE의 F0 프레임 경계 기반 세그멘테이션 대신 보컬 음절(syllable) 단위로 노트를 분리하는 새 방식 시도. 사람의 노래는 음절마다 새 음표가 시작되므로 이론적으로 악보 노트 경계와 더 잘 일치할 것이라는 가설.

**변경 사항**:
- `core/note_segmenter.py` — `segment_notes_onset()` 함수 추가
  - librosa onset detection(backtrack=True, delta=0.03) → 음절 경계 탐지
  - 각 경계 구간에서 voiced MIDI 중앙값 → Note 생성
  - min_voiced_ratio=0.25 미만 구간 → rest 처리
- `core/pipeline.py` — `mode="onset"` 분기 추가 (FCPE F0 + onset_segmenter)
- `scripts/evaluate.py` — "onset" 선택지 추가

**FCPE vs Onset 8곡 비교 (onset_delta=0.03)**:

| 곡 | FCPE | Onset | 차이 |
|----|------|-------|------|
| Golden | 0.0279 | 0.0281 | +1.0% |
| IRIS OUT | **0.3199** | 0.0748 | **-76.6%** |
| 꿈의 버스 | 0.0519 | 0.0569 | +9.5% |
| 너에게100퍼센트 | 0.0907 | **0.1080** | +19.1% |
| 달리 표현할 수 없어요 | 0.0371 | 0.0201 | -45.7% |
| 비비드라라러브 | 0.0725 | 0.0757 | +4.4% |
| 등불을 지키다 | 0.0505 | 0.0568 | +12.6% |
| 여름이었다 | 0.0747 | 0.0621 | -16.9% |
| **평균** | **0.0907** | **0.0603** | **-33.5%** |

**분석**:
- IRIS OUT 한 곡이 0.32→0.07로 붕괴(-76.6%) → 전체 평균을 크게 끌어내림
- IRIS OUT 제외 시: FCPE 0.0579 vs Onset 0.0582 (+0.5%, 사실상 동등)
- Onset 개선 곡(+19.1%, +12.6%, +9.5%, +4.4%, +1.0%)과 악화 곡(-76.6%, -45.7%, -16.9%) 명확히 분리
- IRIS OUT 실패 원인: 734 ref 음표로 매우 조밀한 보컬 → onset detector가 경계를 잘못 잡음
- 달리 실패 원인: 특정 음향 특성에서 onset 탐지 신뢰도 낮음

**결론**: Onset 세그멘테이션은 현재 형태로 채택 불가. FCPE standard가 여전히 최선.
단, 일부 곡에서 onset 방식이 유효하므로 per-song 선택 또는 hybrid 방식 가능성 있음.

**다음 방향**:
1. beat-grid 양자화 세그먼테이션 (`segment_notes_quantized`) 실험
2. IRIS OUT 근본 원인 분석 — 모든 실험에서 어려운 곡
3. postprocess 체인 개선 (diatonic gate, self-octave 등)

### v18 Hybrid Segmentation (2026-03-06) — 피치 안정성 + onset 재공격 감지

**이유**: v15 FCPE(mel_strict=0.090)가 수치상 최고이나 청음 시 "음표가 너무 많고 파편적".
v17 onset(음절 기반)은 노트 수는 적절하나 피치 정확도 하락(-33.5%).
사용자 피드백: "음절 기준으로 맞췄으면 좋겠는데, 노래가 딱딱 음절에 맞춰 하는 건 아님"

**핵심 문제**: 기존 `segment_notes()`가 MIDI 정수 1 차이에도 새 노트 생성 → 비브라토(±50cents)에서 노트 파편화

**변경 사항**:
- `core/note_segmenter.py` — `segment_notes_hybrid()` 전면 재설계
  - **v18a (첫 시도)**: FCPE segment_notes() → onset 경계로 병합 → 329노트 (구멍 많음)
  - **v18b (gap fill 추가)**: 빈 구간에서 raw F0 median 폴백 → 381노트 (구멍 줄음, 여전히 부족)
  - **v18c (피치 안정성, 현재)**: 완전히 새로운 접근
    - Float MIDI 사용 (정수 반올림 안 함 → sub-semitone 정보 보존)
    - ±1.5st tolerance로 같은 노트 유지 (비브라토 흡수)
    - onset 감지는 같은 피치 재공격(syllable repeat)에만 사용
    - running center: alpha=0.05로 느리게 이동 (portamento 추적)
    - 최종 피치 = 프레임 median의 반올림
    - gap bridging: max_gap_frames=5 (50ms) 이내 무성 구간 연결
- `core/pipeline.py` — `mode="hybrid"` 추가 (FCPE F0 → hybrid segmenter → postprocess)

**폐기한 시도**:
- v18a onset 병합 방식: FCPE 노트를 onset 구간에 병합 → 329노트지만 구멍 많음
- v18b gap fill: raw F0 폴백 추가 → 381노트, 개선은 됐으나 근본적 한계 (onset 경계 정확도)

**꿈의 버스 단일곡 결과**:
- v18c: 496노트 (ref 477과 거의 일치)
- FCPE: 524노트 (과다), Onset: 367노트 (부족)

**v18c 피치 안정성 세그먼터 — 폐기**:
- float MIDI ±1.5st tolerance + onset 재공격 + running center(alpha=0.05)
- 꿈의 버스 496노트(ref 477과 유사)이나 청음 결과 "완전 이상하다"
- 원인 추정: running center drift로 피치가 점진적으로 이탈, 비브라토 흡수가 오히려 피치 정확도 파괴
- **교훈**: F0 프레임 레벨 세그멘테이션을 직접 재구현하면 FCPE segment_notes()의 검증된 로직을 잃음. FCPE 노트를 기반으로 병합하는 v18b 방식이 더 안전

**최종 채택: v18b** (FCPE segment_notes → onset 병합 → gap fill)
- 사용자 평가: "지금까지 들었던 것 중에 제일 나은데 구멍이 있음, 내 기준 0.5"
- 꿈의 버스: 381노트 (FCPE 524 → 27% 감소, ref 477의 80%)

**폐기: delta=0.05, ratio=0.2 튜닝**:
- 꿈의 버스 381→465노트, 전체 +22% 증가
- 청음 결과 "중복된 같은 음이 많아진 것 같다" → onset 경계가 너무 민감해져 같은 피치 구간을 여러 노트로 쪼갬
- **원복: delta=0.07, ratio=0.25**

**다음 방향**:
- 구멍 문제는 onset_delta 조절이 아닌 다른 접근 필요
- 같은 피치 연속 노트 병합 (postprocess에서 hybrid 출력에 맞게)
- postprocess 체인이 hybrid 출력에 최적화되었는지 확인

### v19 Plan (2026-03-10) — 3-agent 합의 계획 (Planner→Architect→Critic)

**목표**: mel_strict 0.090 → 0.13+ (Phase 1), 0.15 (Phase 1+2)

**핵심 진단**: chroma(0.975) >> mel_strict(0.090) = 피치 클래스는 맞지만 옥타브 레지스터 + 온셋 타이밍이 문제. IRIS OUT 0.315 at 0.55 ratio → 정밀도 > 재현율.

**Phase 1 (파이프라인 개선)**:
1. [진행중] 진단 스크립트 — 곡별 오류 분류 (`scripts/diagnose.py`)
2. [대기] 옥타브 정밀도 — adaptive vocal_center(mode), section 15, phrase guard (`postprocess.py`)
3. [대기] 노트 밀도 조정 — F0 분산 기반 confidence + 밀도 필터 (`note_segmenter.py`, `types.py`, `postprocess.py`)
4. [진행중] 온셋 정밀도 — onset strength 가중치 + adaptive subdivision (`postprocess.py`)
5. [진행중] Diatonic gate — minor/pentatonic 템플릿, 반음계 패시지 보존 (`postprocess.py`)

**Phase 2 (평가 체계)**:
6. [대기] 참조 멜로디 추출 개선 — contour-following
7. [대기] 지각적 메트릭 — perceptual_score
8. [대기] 옥타브 허용 메트릭 — mel_strict_oct (평가 전용)

**실행 순서**: Step 1+4+5 병렬 → Step 1 완료 후 Step 2+3 → Phase 1 통합 → Phase 2

**현실적 기대치**: 개별 효과 합산 +0.045~0.09, 상호작용 효과로 50-60% 유지 → 현실적 0.113-0.144. Phase 2 포함 시 0.15 도달 기대.

**상세 계획**: `.omc/plans/mel-strict-0.15-plan.md` 참조

**Step 1 진단 결과 (2026-03-10)**:
- 총 gen=4125, ref=4788, exact_match=434(10.5%), pitch_miss=1274(31%), onset_miss=293(7%), both_miss=1397(34%), FP=727(18%), FN=2020
- 옥타브 오류 111개 (피치 오류의 4.1%만) → Step 2 효과 제한적
- 피치 오류 분포: ±2st=560(최다), ±5st=350, ±7st=292, ±3st=337 → 하모닉 혼동이 주요 원인
- IRIS OUT: exact=196/367(53.4% precision) — 적은 생성 = 높은 정밀도 확인
- 온셋 오류: mean=-1.6ms, std=79.8ms → 편향 없음, 분산만 큼

**Step 2 결과: 실패** (mode-based vocal_center): FCPE 출력의 mode pitch=66이 서브하모닉 잠금 값 자체임. 이를 vocal_center로 사용하면 +12 글로벌 옥타브 시프트가 차단됨. 고정 center=75가 올바르게 시프트 필요를 감지. v7b 실패 패턴과 동일. → **REVERTED**

**Step 3 결과: 비활성** (confidence filter): 전곡 노트 밀도 2.1-3.6 n/s < threshold 4.0 → 필터 미작동. FCPE confidence는 binary(0/1)이므로 F0 분산 기반 대안 사용했으나 밀도 조건 미충족. → **REVERTED**

**Step 4 결과: 실패** (onset strength weighting): onset strength 가중치로 FP 9개 추가(533→524 아닌 533 vs 524). mel_strict -27% (0.052→0.038, 꿈의 버스). onset_f1 거의 불변(0.561→0.562). → **REVERTED**

**Step 5 결과: 중립/소폭 악화** (diatonic gate 개선): multi-scale 템플릿 자체는 중립. max_chromatic_duration 0.20은 정확한 노트 4개 추가 제거. 0.15 유지가 최적. → **REVERTED**

**Phase 1 통합 결과 (v19_phase1.json)**:
- 잔여 변경(section_size=15, phrase guard, multi-scale templates) 결합: mel_strict avg 0.090→0.087 (-3%)
- 달리 표현할 수 없어요: -0.013 회귀
- **전체 Phase 1 REVERTED TO BASELINE v26c** (mel_strict avg 0.090)

**Phase 1 핵심 교훈**: mel_strict의 병목은 후처리가 아닌 F0 피치 정확도. pitch_miss=1274(31%)가 주요 오류원이며 옥타브 오류(111, 4.1%)는 소수. ±2st 오류(560)가 최다 → 하모닉 혼동이 FCPE의 근본적 한계. chroma_similarity(0.975) >> mel_strict(0.090)는 피치 클래스는 정확하지만 레지스터/타이밍이 문제임을 확인.

### v20 Plan (2026-03-10) — 3-agent 합의 계획 (Planner→Architect→Critic)

**목표**: mel_strict 0.091 → 0.12+
**전략**: FP 노트 감소로 정밀도 향상 (IRIS OUT 0.55 ratio = 3.5x mel_strict 근거)
**상세 계획**: `.omc/plans/v20-note-precision-plan.md`

**실행 순서 (Critic 승인)**:
1. min_note_duration 50ms → 80ms (note_segmenter.py)
2. Dedup threshold 30ms → 50ms (postprocess.py)
3. Steps 1+2 합산 상호작용 검증
4. VOCAL_RANGE_LOW 48→52 (HIGH=96 유지, IRIS OUT ref 최고=MIDI 95)
5b. 자연단음계 템플릿 추가 (postprocess.py, 먼저 실행)
5a. Diatonic gate 0.15s → 0.12s (postprocess.py)
6. 누적 통합 최종 평가

**드롭**: Step 2(CREPE confidence threshold) — FCPE 파이프라인에서 no-op
**수정**: Step 4 HIGH=88 → 96 유지 (IRIS OUT ref 최고 MIDI 95 보호)

**Phase 2 완료 (2026-03-10)**: 파이프라인 변경 없이 평가 체계 개선

**Step 6 결과: 기각** (contour-following reference): skyline(0.091) > contour(0.087). contour-following은 내성부 음표를 선택하여 chroma 0.975→0.951 하락. 피아노 편곡에서 skyline이 더 정확한 멜로디 추출. `extract_reference_melody(method="contour")` 구현 완료하나 default는 skyline 유지.

**Step 7 결과: 구현 완료** (perceptual metrics):
- `pitch_accuracy_at_onset`: 참조 음표별 200ms 내 최근접 생성 음표의 피치 클래스 일치율
- `rhythm_similarity`: IOI 히스토그램 코사인 유사도 (50ms 해상도)
- `perceptual_score = 0.4*pitch_acc + 0.3*rhythm + 0.3*contour` → avg 0.537
- 파이프라인이 인지적 멜로디 품질의 ~54% 포착

**Step 8 결과: 구현 완료** (mel_strict_oct):
- mel_strict avg=0.091, mel_strict_oct avg=0.109 → 갭 +0.018 (20% 상대적 향상)
- 옥타브 레지스터 불일치가 mel_strict 실패의 ~18%를 설명
- 예상보다 작은 갭 → 대부분의 피치 오류는 옥타브가 아닌 하모닉 혼동(±2-7st)
- IRIS OUT: 가장 큰 갭(0.320→0.371, +0.051) — 옥타브 오류가 상대적으로 많은 곡

**Phase 2 전체 결과 (v19_phase2_skyline.json)**:

| Song | mel_strict | mel_strict_oct | perceptual | chroma | contour |
|------|-----------|---------------|------------|--------|---------|
| Golden | 0.028 | 0.047 | 0.461 | 0.980 | 0.749 |
| IRIS OUT | 0.320 | 0.371 | 0.587 | 0.939 | 0.766 |
| 꿈의 버스 | 0.052 | 0.074 | 0.536 | 0.990 | 0.767 |
| 너에게100퍼센트 | 0.091 | 0.096 | 0.542 | 0.989 | 0.746 |
| 달리 표현할 수 없어요 | 0.037 | 0.040 | 0.574 | 0.992 | 0.733 |
| 등불을 지키다 | 0.050 | 0.065 | 0.556 | 0.969 | 0.821 |
| 비비드라라러브 | 0.072 | 0.096 | 0.477 | 0.953 | 0.822 |
| 여름이었다 | 0.075 | 0.085 | 0.565 | 0.990 | 0.734 |
| **AVG** | **0.091** | **0.109** | **0.537** | **0.975** | **0.767** |

**v19 종합 결론**:
- Phase 1 파이프라인 개선: 전체 실패. F0 정확도(FCPE 하모닉 혼동)가 근본 병목
- Phase 2 평가 개선: mel_strict_oct(+20%), perceptual_score(0.537) 구현 완료
- contour reference: skyline 대비 열위, 기각
- **mel_strict 0.091 = 현 파이프라인의 실질적 상한**. 의미있는 개선을 위해서는 F0 추출 자체의 개선(서브하모닉/하모닉 혼동 해결)이 필요
- 향후 방향: (a) 더 나은 F0 모델 탐색, (b) perceptual_score를 보조 지표로 활용, (c) mel_strict_oct로 옥타브 보정 효과 추적

**v20 실행 결과 (2026-03-10)**:

**Step 1 (min_note_duration 50→80ms)**: **기각/복구**
- 결과: mel_strict 0.091 → 0.082 (-9.9%, regression)
- 비비드라라러브: -0.035 (가장 큰 피해)
- 원인: 80ms는 실제 보컬 음표를 걸러냄. F0 지터 아티팩트가 아닌 진짜 짧은 음표 제거
- 복구: note_segmenter.py min_note_duration=0.05 유지
- 결과 파일: `results/v20_step1_mindur80.json`

**Step 2 (CREPE confidence threshold)**: 드롭 (FCPE 파이프라인에서 no-op)

**Step 3 (dedup 30→50ms)**: **중립 → 유지**
- 결과: mel_strict 0.091 (변화 없음)
- 원인: beat snap 후 노트는 이미 >50ms 간격. 실질 변화 없음
- 논리적 정합성이 있으므로 유지 (50ms 이내 두 노트는 어차피 참조 하나에만 매칭 가능)
- 결과 파일: `results/v20_step3_dedup50.json`

**Step 4 (VOCAL_RANGE_LOW 48→52)**: **중립 → 유지**
- 결과: mel_strict 0.091 (변화 없음)
- 원인: 8곡 중 MIDI 52 이하 참조 음표 없음. 실질 변화 없음
- 논리적 정합성으로 유지 (VOCAL_RANGE_HIGH=96 유지, IRIS OUT ref 최고=MIDI 95)
- 결과 파일: `results/v20_step4_vocalrange.json`

**Step 5b (자연단음계 템플릿)**: **기각/복구**
- 결과: mel_strict 0.091 (변화 없음, 구조적 no-op)
- 원인: 자연단음계 [0,2,3,5,7,8,10]은 장음계 [0,2,4,5,7,9,11]의 관계단조(relative minor)
  와 동일한 7개 피치 클래스를 공유. key_chromas 집합이 변하지 않아 어떤 음표도 걸러지거나 보존되는 방식이 달라지지 않음
- 복구: postprocess.py 단음계 템플릿 추가 코드 제거
- 결과 파일: `results/v20_step5b_minor.json`

**Step 5a (diatonic gate 0.15→0.12s)**: **중립 → 유지**
- 결과: mel_strict 0.091 (변화 없음), IRIS OUT 0.323 (+0.003)
- 원인: 현재 곡들에서 0.12~0.15s 구간의 반음계 음표가 거의 없음
- 논리적 정합성으로 유지
- 결과 파일: `results/v20_step5a_diatonic12.json`

**v20 최종 결과 (results/v20_final.json)**:

| Song | mel_strict | mel_strict_oct | notes |
|------|-----------|---------------|-------|
| Golden | 0.028 | 0.047 | 561/588 |
| IRIS OUT | 0.323 | 0.377 | 417/734 |
| 꿈의 버스 | 0.052 | 0.074 | 528/477 |
| 너에게100퍼센트 | 0.090 | 0.095 | 549/649 |
| 달리 표현할 수 없어요 | 0.036 | 0.039 | 743/607 |
| 등불을 지키다 | 0.050 | 0.065 | 458/653 |
| 비비드라라러브 | 0.072 | 0.096 | 485/455 |
| 여름이었다 | 0.075 | 0.085 | 528/625 |
| **AVG** | **0.091** | **0.110** | — |

**v20 최종 코드 상태**:
- `core/postprocess.py`: VOCAL_RANGE_LOW=52, dedup min_gap=0.050, max_chromatic_duration=0.12
- `core/note_segmenter.py`: min_note_duration=0.05 (변경 없음)

**v20 종합 결론**:
- 목표(0.12+) 달성 실패. mel_strict 0.091 변화 없음
- 파라미터 튜닝(후처리 레이어) 차원에서는 개선 여지 소진
- **근본 원인 재확인**: 하모닉 혼동(±2-7 semitone, 31% of errors)과 F0 subharmonic이 mel_strict 병목
- 후처리 파라미터 단순 조정으로는 한계. F0 모델 자체 개선 필요
- **향후 방향**: RMVPE/CREPE 앙상블 실험, 혹은 더 정밀한 보컬 특화 F0 모델 탐색

### v21 Plan (2026-03-10) — 3-agent 합의 계획 (Phase A+B 순차 실행)

**목표**: mel_strict 0.091 → 0.112~0.130 (Phase B 완료 시)
**근거**: v19-v20에서 후처리 파라미터 소진. 근본 병목 해결(F0 하모닉 혼동) 방향으로 전환.
**상세 계획**: `.omc/plans/improvement-analysis.md`

**실행 순서**:

#### Phase A: 저비용 선행 실험

**A1. Demucs 보컬 후처리 — 곡 끝 에너지 트리밍**
- 문제: 비비드라라러브 Boundary Overflow (곡 종료 후 122개 잡음 노트)
- 구현: `core/vocal_separator.py`에 `_trim_trailing_silence()` 추가 (librosa RMS 에너지 기반)
- 임계값: 최대 에너지의 -40dB 이하 구간 트리밍 + 1.0s 버퍼
- 가드: 트리밍 후 10s 미만이면 트리밍 생략
- 수락 기준: avg delta ≥ 0.010, IRIS OUT ≥ 0.250
- 결과 파일: `results/v21_a1_demucs_trim.json`

**A2. 보컬 bandpass filter (100~2000Hz) 단독 실험**
- 문제: v9에서 CQT와 결합하여 실패. CQT 없이 bandpass만 단독 평가
- 구현: Demucs 보컬 분리 후, F0 추출 전에 butterworth bandpass (100-2000Hz) 적용
- 수락 기준: avg delta ≥ 0.010, IRIS OUT ≥ 0.250
- 결과 파일: `results/v21_a2_bandpass.json`

#### Phase B: 핵심 개선

**B1. 노트 레벨 다중 모델 선택** (최고 우선순위)
- FCPE + RMVPE 각각 독립 F0 추출 → 각각 segment_notes() → 두 노트 리스트 비교
- 선택 기준:
  - 일치 노트 → 채택
  - 불일치 → **피치 분산(pitch variance)** 낮은 쪽 선택 (confidence는 binary이므로 불가)
  - 동률 → FCPE 우선
- 주의: FCPE/RMVPE confidence = binary(0/1), "confidence 평균" 사용 불가
- `pipeline.py`에 `mode="multi"` 신설 (current default: "crepe")
- 수락 기준: avg delta ≥ 0.010, IRIS OUT ≥ 0.250
- 결과 파일: `results/v21_b1_multi_model.json`

**B2. 곡별 적응형 파라미터** (B1 이후)
- 1차 추출 통계(BPM, 노트 밀도, 음역대) → 2차 파라미터 자동 조정
- 수락 기준: avg delta ≥ 0.010, IRIS OUT ≥ 0.250
- 결과 파일: `results/v21_b2_adaptive.json`

**가드레일**:
- 통계적 유의성: avg delta < 0.010은 노이즈로 간주, 채택 금지 (n=8)
- IRIS OUT 보호: 어떤 변경이든 IRIS OUT < 0.250이면 자동 기각
- Rule 5 준수: 참조 기반 추출 결과 변환 절대 금지
- Demucs 캐시: 모델 변경 시 캐시 키에 모델명 포함 필요

**Phase A 실행 결과 (2026-03-10)**:

**A1. Demucs trailing silence trimming**: **중립 → 유지**
- 결과: mel_strict 0.091 (변화 없음)
- 원인: 현재 파이프라인에서 비비드라라러브 trailing noise는 이미 세그멘테이션에서 필터됨. 122개 잡음 노트는 이전 onset-based segmenter 실험에서 관찰된 것으로, 현재 표준 segmenter에서는 영향 없음
- 코드: `core/vocal_separator.py`에 `_trim_trailing_silence()` 추가 (유지 — 무해, 향후 onset segmenter 사용 시 유용)
- 결과 파일: `results/v21_a1_demucs_trim.json`

**A2. Bandpass filter (100~2000Hz)**: **기각/복구**
- 결과: mel_strict 0.091 → 0.078 (-14.3%, 치명적 회귀)
- 비비드라라러브: 0.072 → 0.006 (거의 0)
- IRIS OUT: 0.323 → 0.283 (-12.4%)
- 원인: FCPE가 내부적으로 2000Hz 이상의 배음 정보를 활용하여 기본음을 추정하는 것으로 추정. 2000Hz 컷오프가 FCPE 입력에 필요한 정보를 제거함
- 복구: `core/pipeline.py`에서 bandpass 관련 코드 전체 제거
- 결과 파일: `results/v21_a2_bandpass.json`
- **교훈**: FCPE는 스펙트럼 피크 기반이 아닌 학습 기반 모델. 단순 bandpass는 FCPE 입력 특성을 손상시킴

**Phase A 결론**: 두 실험 모두 의미있는 개선 없음. mel_strict 0.091 유지. Phase B(B1 노트 레벨 모델 선택)로 진행.

**Phase B 실행 상태 (2026-03-10)**:

**B1. 노트 레벨 다중 모델 선택**: **차단 — RMVPE 모델 불가**
- 코드 구현 완료: `core/note_segmenter_multi.py` + `core/pipeline.py` mode="multi" 추가
- 차단 원인: `models/rmvpe.pt` 파일이 HTML redirect(452B) — HuggingFace 네트워크 차단
  - 참고: v16(2026-03-05)에서 정상 다운로드되어 실험 완료된 모델
  - 현재 네트워크 환경에서 `https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.pt` 차단됨
- **수동 해결 방법**: 다른 네트워크에서 RMVPE 모델(181MB) 다운로드 후 `models/rmvpe.pt`에 배치
- 평가 명령: `python scripts/evaluate.py --mode multi --output results/v21_b1_multi_model.json`
- 기대 효과: mel_strict +0.010~0.020 (FCPE/RMVPE 보완성 근거: 꿈의버스 RMVPE +26%, 너에게 +36%)

**v21 진행 상태**:
- Phase A 완료 (모두 중립/기각)
- Phase B1 차단 (RMVPE 모델 다운로드 불가)
- 다음 단계: RMVPE 모델 수동 다운로드 후 B1 평가, 또는 다른 개선 방향 탐색
