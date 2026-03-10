# piano-sheet-extractor 개선 방향 분석

**작성일**: 2026-03-10
**현재 버전**: v20 (FCPE 기반 파이프라인)
**Primary Metric**: melody_f1_strict (exact MIDI pitch + 50ms onset)
**현재 수치**: avg 0.091 (목표 0.90, 현실적 단기 목표 0.15)

---

## 1. 현재 상황 요약

### 파이프라인 구조
```
MP3 -> Demucs htdemucs_ft (보컬분리) -> FCPE F0 (피치추출)
    -> note_segmenter (MIDI 변환+그룹핑) -> postprocess (자체보정)
    -> musicxml_writer (악보저장) -> round-trip 평가
```

### 핵심 수치 (v20_final.json, 8곡 평균)
| 메트릭 | 값 | 의미 |
|--------|-----|------|
| mel_strict | 0.091 | exact pitch + 50ms onset F1 |
| mel_strict_oct | 0.110 | 옥타브 허용 시 +20% |
| mel_lenient | 0.162 | exact pitch + 200ms onset |
| onset_f1 | 0.528 | 피치 무관 onset만 |
| chroma | 0.976 | 12-bin 코사인 유사도 |
| contour | 0.766 | 멜로디 방향 일치율 |
| perceptual | 0.536 | 인지적 종합 점수 |

### 핵심 진단 (v19 Phase 1 진단 스크립트 결과)
- 총 gen=4125, ref=4788
- **exact_match=434 (10.5%)** -- 10개 중 1개만 정확
- **pitch_miss=1274 (31%)** -- onset은 맞지만 피치 틀림 (최대 오류원)
- onset_miss=293 (7%) -- 피치는 맞지만 onset 틀림
- both_miss=1397 (34%) -- 둘 다 틀림
- FP=727 (18%) -- 참조에 없는 불필요 노트
- 옥타브 오류=111 (피치 오류의 4.1%만)
- 하모닉 혼동: +/-2st=560(최다), +/-5st=350, +/-7st=292, +/-3st=337

### 곡별 성능 편차
| 곡 | mel_strict | 특이사항 |
|----|-----------|---------|
| IRIS OUT | **0.323** | 유일한 고성능곡, ratio=0.568(적은 생성=높은 정밀도) |
| 너에게100퍼센트 | 0.090 | 높은 음역대, 이전 0.000에서 크게 개선 |
| 여름이었다 | 0.075 | 안정적 |
| 비비드라라러브 | 0.072 | 서브하모닉 심각, 구조적 불일치 |
| 꿈의 버스 | 0.052 | BPM=180 빠른 곡 |
| 등불을 지키다 | 0.050 | onset_f1=0.580(높음) but 피치 레지스터 불일치 |
| 달리 표현할 수 없어요 | 0.036 | ratio=1.224(과다 생성) |
| Golden | 0.028 | 최저 성능, BPM 3:2 보정 필요했던 곡 |

---

## 2. 소진된 방향 (반복 금지)

### 2.1 후처리 기반 피치 보정 (v7, v7b, v9 -- 3회 실패)

| 시도 | 결과 | 실패 이유 |
|------|------|----------|
| Harmonic correction (+/-5/7st) | 0.067->0.047 | 정상적 melodic leap까지 보정 |
| Dynamic vocal_center | 0.067->부분 0.000 | CREPE/FCPE 서브하모닉 값 자체를 center로 사용 |
| CQT spectral octave verify | 0.067->0.021 | CQT에서도 배음/서브하모닉 구분 불가 |

**교훈**: FCPE/CREPE 출력이 이미 왜곡되어 있으므로 왜곡 데이터 기반 자기참조 보정은 오류 증폭. 고정 파라미터(center=75, threshold=7)가 더 안정적.

### 2.2 대안 F0 추출기 단독 교체 (v8, v10, v16 -- 3회 실패)

| 시도 | mel_strict | 실패 이유 |
|------|-----------|----------|
| FCPE 단독 (v8, CREPE 대체) | 0.055 | 달리 대폭 하락, voiced rate 과다 |
| SOME end-to-end (v10) | 0.033 | 중국어 훈련 -> 한국 팝 일반화 부족 |
| RMVPE 단독 (v16) | 0.061 | IRIS OUT, 비비드에서 대폭 하락 |

**교훈**: 단일 F0 모델 교체로는 해결 불가. 각 모델은 다른 곡에서 보완적이나 단독으로 전체 개선 못 함.

### 2.3 F0 레벨 앙상블 (v16 -- 실패)

- FCPE+RMVPE 프레임별 앙상블: 0.090->0.062 (-31%)
- RMVPE 잘못된 피치가 averaging으로 FCPE 정확 피치 오염
- **교훈**: 프레임 레벨 F0 앙상블은 유해. 노트 레벨 선택이 필요할 수 있으나 미시도.

### 2.4 세그멘테이션 직접 재구현 (v14, v17, v18 -- 다수 실패)

| 시도 | mel_strict | 실패 이유 |
|------|-----------|----------|
| Quantized segmentation | 0.057 | 기존보다 하락 |
| Spectral onset detection | 23% match | F0 기반 39%보다 악화 |
| Onset-based segmentation (v17) | 0.060 | IRIS OUT 붕괴(-76.6%) |
| Pitch stability segmenter (v18c) | 청음 실패 | running center drift |
| Consolidate short notes (v14) | 0.035 | 악화 |

**교훈**: FCPE의 기본 segment_notes()가 현재로서는 최적. 직접 재구현하면 검증된 로직을 잃음.

### 2.5 후처리 파라미터 미세 조정 (v19-v20 -- 포화)

- min_note_duration 50->80ms: -9.9% (진짜 짧은 음표 제거)
- Onset strength weighting: -27%
- Diatonic gate 강화/완화: 변화 없음
- Mode-based vocal_center: 서브하모닉 값을 center로 쓰면 shift 차단 (v7b 반복)
- Confidence filter: FCPE confidence가 binary(0/1)이라 무효
- 자연단음계 템플릿: 구조적 no-op (장음계 관계단조와 동일 피치클래스)

**교훈**: postprocess 체인은 이미 최적화됨. outlier(t=14), global_octave(center=75), self_octave(t=7), clip(52-96), diatonic(0.12s), beat_snap(adaptive), dedup(50ms) 현재 구성이 최선.

### 2.6 Basic Pitch (v12 -- 실패)

- mel_strict 0.049->0.020 (-59%)
- isolated vocals에서 노트 감지 부족 (69% 커버리지)
- 이전 0.425 수치는 time alignment 부정 메트릭이었음 확인

---

## 3. 미시도 방향 (우선순위순)

### 3.1 [HIGH PRIORITY] 노트 레벨 다중 모델 선택 (Note-level Model Selection)

**근거**:
- FCPE vs RMVPE 곡별 보완성 확인 (v16): FCPE 약점곡에서 RMVPE +36%
- 프레임 레벨 앙상블은 실패했으나, **노트 레벨 선택**은 미시도
- IRIS OUT: FCPE 0.317 >> RMVPE 0.098 / 너에게100퍼센트: RMVPE 0.099 > FCPE 0.073

**구현 방식**:
- 두 모델(FCPE+RMVPE)로 각각 F0 추출 -> 각각 세그멘테이션 -> 노트 리스트 2개 생성
- 노트별 신뢰도 점수: (a) F0 confidence 평균, (b) 피치 안정성(분산), (c) 두 모델 일치도
- 두 모델이 일치하는 노트: 높은 신뢰도로 채택
- 불일치 노트: 신뢰도 높은 쪽 선택 또는 FCPE 우선 (baseline 성능 우위)

**리스크**: MED -- 프레임 레벨 앙상블 실패 전례 있으나 노트 레벨은 다른 접근
**기대 효과**: mel_strict +0.010~0.020 (곡별 최선 모델 선택 효과)
**이전 시도**: 프레임 레벨 앙상블만 시도 (실패). 노트 레벨 선택은 미시도.

---

### 3.2 [HIGH PRIORITY] Demucs 보컬 분리 품질 개선

**근거**:
- v6 심층 분석: "Phrase-level Gaps -- FN의 71-82%가 구간 통째로 누락" (4/8곡)
- 비비드라라러브: Boundary Overflow -- 곡 종료 후 83초간 122개 잡음 노트 (Demucs 악기 오인)
- Demucs 분리 실패 구간에서 confidence 전체 하락 -> 노트 누락
- 현재 htdemucs_ft 단일 모델 사용. 다른 Demucs 모델/설정 미탐색

**구현 방식**:
- (a) Demucs 모델 비교: htdemucs_ft vs htdemucs vs mdx_extra (분리 품질 비교)
- (b) Demucs 출력 후처리: 무음 구간 감지 + 곡 끝 트리밍 (Boundary Overflow 해결)
- (c) 2-pass 분리: Demucs -> 보컬에서 잔여 악기 제거 (harmonic/percussive 분리)

**리스크**: LOW-MED -- 모델 교체는 비파괴적, 기존 파이프라인과 독립
**기대 효과**: phrase gap 해소 시 mel_strict +0.005~0.015
**이전 시도**: 없음. htdemucs_ft만 사용해옴.

---

### 3.3 [HIGH PRIORITY] 학술 SOTA 모델 적용 (ROSVOT, T3MS)

**근거**:
- v12 조사: 학술 SOTA ROSVOT COnPOff F1=77.4%, T3MS (2025 최신)
- 현재 파이프라인은 "F0 추출 -> 세그멘테이션 -> 후처리" 3단계 수작업
- End-to-end 모델은 이 3단계를 단일 신경망으로 처리
- SOME(v10)은 실패했으나 중국어 특화 모델이었음. ROSVOT/T3MS는 더 범용적

**구현 방식**:
- (a) ROSVOT (ISMIR 2023): singing voice transcription 전용, COnPOff 메트릭
  - GitHub 코드 확인 + 사전훈련 모델 다운로드 + 파이프라인 통합
- (b) T3MS (2025): 최신 singing transcription 모델
  - 논문/코드 공개 여부 확인 필요
- (c) 기존 후처리 체인은 유지하되 F0+segmenter를 ROSVOT 출력으로 대체

**리스크**: HIGH -- 모델 가용성, 의존성, 환경 호환성 불확실
**기대 효과**: 성공 시 mel_strict 0.15-0.30 가능 (구조적 도약)
**이전 시도**: SOME만 시도 (중국어 특화 -> 실패). ROSVOT/T3MS는 미시도.

---

### 3.4 [MED PRIORITY] 참조 멜로디 추출 개선 (평가 정확도)

**근거**:
- v15 핵심 발견: "Vocal-to-sheet gap: onset 매칭 노트 중 exact pitch match 10-27%"
- 참조 악보는 **피아노 편곡**: 보컬 멜로디를 피아노로 편곡한 것이므로 구조적 차이 존재
- 현재 skyline 추출: 오른손 파트에서 최고음 선택
- 피아노 편곡에서 멜로디가 항상 최고음이 아닐 수 있음 (내성부에 멜로디)
- v19에서 contour-following 시도했으나 skyline 대비 열위로 기각

**구현 방식**:
- (a) 인간 청취 기반 참조 annotation: 8곡에 대해 실제 보컬 멜로디를 직접 MIDI로 입력
  - 골든 스탠다드이나 노동 집약적
- (b) 보컬 F0 contour와 참조 노트 간 alignment -> 매칭되는 참조 노트만 선별
  - 단, Rule 5 위반 가능성 (참조 기반 변환이 아닌 참조 자체의 필터링이므로 허용 범위)
- (c) 다중 skyline 전략: 최고음 + 최저음 + 중앙음 중 보컬과 가장 유사한 것 선택

**리스크**: MED -- 평가 체계 변경은 과거 결과와 비교 불가 위험
**기대 효과**: 평가 정확도 향상 -> 진짜 개선/악화 식별 가능. mel_strict 자체는 변할 수 있으나 방향성이 정확해짐
**이전 시도**: skyline(채택), contour-following(기각). 인간 annotation/보컬 기반 필터링은 미시도.

---

### 3.5 [MED PRIORITY] F0 추출 전 보컬 신호 전처리

**근거**:
- FCPE 하모닉 혼동(+/-2-7st)이 31%의 피치 오류 원인
- 하모닉 혼동은 배음(overtone)이 기음(fundamental)보다 강할 때 발생
- 보컬 분리 후 잔여 반주 악기의 배음이 FCPE를 혼동시킬 수 있음
- 100Hz highpass는 v9에서 시도했으나 CQT와 결합해서 실패 (highpass 단독 효과 미분리)

**구현 방식**:
- (a) Adaptive bandpass filter: 보컬 음역대(200-1200Hz fundamental) 외 제거
- (b) Harmonic enhancement: librosa.effects.harmonic()으로 배음 강조 후 F0 추출
- (c) De-reverb: 잔향 제거로 F0 안정성 향상 (librosa 또는 별도 모델)
- (d) 멀티밴드 분석: 저/중/고 대역별 F0 추출 후 일치도 기반 선택

**리스크**: MED -- 전처리가 오히려 유용 정보 제거 가능
**기대 효과**: 하모닉 혼동 10-20% 감소 시 mel_strict +0.005~0.010
**이전 시도**: 100Hz highpass 단독은 미평가 (v9에서 CQT와 결합하여 CQT 실패에 묻힘).

---

### 3.6 [MED PRIORITY] 곡별 적응형 파라미터 (Per-Song Adaptive)

**근거**:
- IRIS OUT(0.323) vs Golden(0.028) -- 11.5배 편차
- IRIS OUT: ratio=0.568 (적은 생성=높은 정밀도). 다른 곡: ratio=0.85-1.22
- 곡 특성(BPM, 음역대, 밀도)에 따라 최적 파라미터가 다를 수 있음
- BPM 적응형 그리드는 이미 구현 (v4). 다른 파라미터로 확장 가능

**구현 방식**:
- (a) BPM 기반 min_note_duration 조정 (빠른 곡=짧게, 느린 곡=길게)
- (b) 노트 밀도 기반 confidence threshold 조정 (과밀=threshold 높임)
- (c) 음역대 기반 vocal_center 조정 (중앙값 기반은 실패했으나, 히스토그램 bimodal 감지 가능)
- (d) 1차 추출 후 통계 분석 -> 2차 추출 (2-pass pipeline)

**리스크**: MED -- 과적합 위험, 범용성 감소
**기대 효과**: 하위 곡 개선 시 mel_strict +0.005~0.015
**이전 시도**: BPM 적응형 grid(v4, 채택), dynamic vocal_center(v7b, 실패). 2-pass는 미시도.

---

### 3.7 [LOW PRIORITY] MusicXML 양자화 최적화

**근거**:
- v14 발견: BPM<140에서 8분음표 그리드 사용 시 max error 110-134ms (>50ms!)
- v15에서 동적 양자화 grid_mult 도입 (모든 곡 max error < 50ms 보장)
- 현재 양자화 오차가 50ms 미만이므로 mel_strict 50ms tolerance 내
- 그러나 양자화 자체가 onset을 이동시키므로 일부 경계 사례에서 손실 가능

**구현 방식**:
- (a) 양자화 없이 자유 onset 저장 (MusicXML에서 가능한 최소 단위 사용)
- (b) Round-trip 시 양자화 오차를 tolerance에 포함 (평가 보정)

**리스크**: LOW -- MusicXML 호환성 문제 가능
**기대 효과**: mel_strict +0.002~0.005 (경계 사례만)
**이전 시도**: 동적 grid_mult(v15, 채택). 자유 onset은 미시도.

---

### 3.8 [LOW PRIORITY] 평가 메트릭 다각화

**근거**:
- mel_strict 50ms+exact pitch는 매우 엄격 (학술 SOTA와 직접 비교 어려움)
- perceptual_score(0.537)는 인지적 품질의 54% 포착
- 청음 평가("0.5점")와 수치가 대략 일치하나 정교화 필요

**구현 방식**:
- (a) MIREX-style 메트릭 추가: raw pitch accuracy, voicing recall 등
- (b) 청음 평가 프레임워크: 블라인드 A/B 비교 체계화
- (c) mel_strict tolerance 변형: 100ms, 150ms 버전 추가로 개선 방향 식별

**리스크**: LOW -- 평가만 변경, 파이프라인 비변경
**기대 효과**: 개선 방향 식별 정확도 향상
**이전 시도**: mel_strict_oct(v20, 구현), perceptual_score(v20, 구현).

---

## 4. 구조적 한계 vs 개선 가능 영역

### 구조적 한계 (파이프라인 변경으로 해결 불가)

1. **Vocal-to-Sheet Gap**: 보컬 멜로디 != 피아노 편곡
   - onset 매칭 노트 중 exact pitch match 10-27% (IRIS OUT만 52%)
   - 피아노 편곡자가 보컬을 해석/변형한 결과이므로 1:1 대응 불가
   - 이것은 **평가의 한계**이지 파이프라인의 한계가 아닐 수 있음
   - 해결: 보컬 직접 annotation 또는 메트릭 재정의

2. **FCPE 하모닉 혼동**: +/-2-7st 피치 오류가 31%
   - FCPE/CREPE/RMVPE 모두 다른 패턴의 하모닉 혼동 발생
   - F0 추출의 근본적 한계 (배음 구조에서 기음 식별)
   - 해결: 더 나은 F0 모델(ROSVOT 등) 또는 노트 레벨 앙상블

3. **Demucs 보컬 분리 한계**: 일부 구간 보컬 누락/악기 혼입
   - FN의 71-82%가 phrase-level gap (보컬 분리 실패 구간)
   - 해결: Demucs 모델 교체 또는 2-pass 분리

### 개선 가능 영역 (현실적 접근)

1. **노트 레벨 모델 선택** (3.1): 기존 모델 조합으로 가능, 새 의존성 없음
2. **보컬 분리 개선** (3.2): Demucs 모델 교체/후처리, 비교적 단순
3. **보컬 전처리** (3.5): bandpass/harmonic enhancement, 단순 DSP
4. **곡별 적응형** (3.6): 기존 파라미터 조건부 변경, 위험 낮음
5. **SOTA 모델** (3.3): 구조적 도약 가능하나 불확실성 높음

### mel_strict 이론 상한 추정

- chroma=0.976 -> 피치 클래스 정보는 ~98% 정확
- onset_f1=0.528 -> onset 위치는 ~53% 정확
- mel_strict = pitch_correct AND onset_correct
- 이론 상한: ~0.976 * 0.528 = ~0.515 (독립 가정)
- 현실 상한: 하모닉 혼동 해결 시 mel_strict 0.20-0.30 추정
- **IRIS OUT 0.323이 현 아키텍처의 실증적 상한 근거**

---

## 5. 추천 실행 순서

### Phase A: 저비용 고확률 개선 (예상 1-2일)

**A1. Demucs 보컬 후처리** (3.2b)
- 곡 끝 트리밍 (energy envelope 기반)
- 비비드라라러브 Boundary Overflow(122개 잡음 노트) 해결
- 예상: mel_strict +0.003~0.005
- 난이도: LOW

**A2. 보컬 전처리 단독 실험** (3.5a,b)
- Adaptive bandpass + harmonic enhancement
- v9 highpass를 CQT 없이 단독 평가 (미분리 실험)
- 예상: mel_strict +0.003~0.008
- 난이도: LOW

### Phase B: 중간 노력 개선 (예상 3-5일)

**B1. 노트 레벨 다중 모델 선택** (3.1)
- FCPE + RMVPE 각각 추출 -> 노트 레벨 신뢰도 기반 선택
- 핵심: 프레임 앙상블이 아닌 노트 단위 선택/투표
- 예상: mel_strict +0.010~0.020
- 난이도: MED

**B2. 곡별 적응형 파라미터** (3.6)
- 1차 추출 통계 -> 2차 추출 (2-pass)
- BPM, 노트 밀도, 음역대 기반 파라미터 조정
- 예상: mel_strict +0.005~0.010
- 난이도: MED

### Phase C: 구조적 도약 시도 (예상 1-2주)

**C1. ROSVOT/T3MS 모델 탐색** (3.3)
- 코드/모델 가용성 확인 -> 파이프라인 통합 시도
- 실패 시: 다른 end-to-end singing transcription 모델 탐색
- 예상: 성공 시 mel_strict 0.15-0.30 (실패 시 0)
- 난이도: HIGH

**C2. 참조 멜로디 재정의** (3.4)
- 인간 annotation 또는 보컬 F0 기반 참조 필터링
- 평가 정확도 향상 -> 개선 방향 식별 정밀화
- 난이도: MED-HIGH

### 누적 기대치

| Phase | 예상 mel_strict | 현실적 범위 |
|-------|----------------|------------|
| 현재 (v20) | 0.091 | - |
| Phase A 완료 | 0.097~0.104 | 낙관 0.105, 비관 0.093 |
| Phase B 완료 | 0.112~0.130 | 낙관 0.135, 비관 0.100 |
| Phase C 완료 | 0.150~0.300 | 성공 시 도약, 실패 시 Phase B 수준 유지 |

**핵심 판단**: Phase A+B만으로는 목표(0.15)에 미달할 가능성 높음. Phase C(SOTA 모델 또는 평가 재정의)가 0.15 달성의 열쇠. 단, Phase A+B는 Phase C의 기반이 되므로 순서대로 진행 권장.

---

## 부록: 실험 이력 요약표

| 버전 | mel_strict | 주요 변경 | 결과 |
|------|-----------|----------|------|
| v1 reset | 0.058 (1곡) | 프로젝트 초기화, CREPE+round-trip | 진정한 baseline |
| v2 | 0.040 | BPM 반템포 보정, beat snap | onset 소폭 개선 |
| v3 | 0.066 | 5단계 개선 (BPM, 옥타브, MusicXML) | +65% |
| v4 | 0.049 (1곡) | BPM 적응형 그리드 | 빠른 곡 개선 |
| v5 | 0.065 | 구멍 해소 (confidence, gap, range) | 구멍 해소, strict 동일 |
| v6 | 0.067 | 잡음 제거, diatonic gate | +3% |
| v7 | 0.047 | harmonic correction | **폐기** |
| v8 | 0.055 | FCPE 단독 | **폐기** |
| v9 | 0.021 | HP+CQT octave | **폐기** |
| v10 | 0.033 | SOME end-to-end | **폐기** |
| v11 | 0.032 (1곡) | re-attack detection | 효과 미미 |
| v12 | 0.020 (1곡) | Basic Pitch+CQT | **폐기** |
| v13 | 0.060 | FCPE 통합 | FCPE 채택 (속도 750x) |
| v14 | - | 세그멘테이션 실험들 | **전부 폐기** |
| v15 | **0.090** | FCPE + 전체 최적화 | **현재 기준선** |
| v16 | 0.061 | RMVPE, 앙상블 | **폐기** (보완성 확인) |
| v17 | 0.060 | onset segmentation | **폐기** |
| v18 | - | hybrid segmentation | **폐기** |
| v19 | 0.091 | Phase 1(실패)+Phase 2(평가 개선) | Phase 1 전체 revert |
| v20 | **0.091** | 정밀도 향상 시도 | 변화 없음, **현재 최종** |
