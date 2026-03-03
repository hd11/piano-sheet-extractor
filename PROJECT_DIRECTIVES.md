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

(이전 v9~v21 이력은 git history 참조)
