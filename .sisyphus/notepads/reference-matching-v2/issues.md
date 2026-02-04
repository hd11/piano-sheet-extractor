# Reference Matching v2 - Issues & Blockers

## Current Issues

### 1. Note Gain Instead of Loss (UNEXPECTED)
- **Status**: Discovered during measurement
- **Impact**: Contradicts initial assumption about note loss
- **Root Cause**: Unknown - likely chord expansion or quantization artifacts
- **Next Action**: Investigate by comparing MIDI vs MusicXML note-by-note

### 2. Character Encoding in Output
- **Status**: Minor cosmetic issue
- **Impact**: Arrow character (→) displays as garbled in some terminals
- **Root Cause**: Terminal encoding mismatch
- **Workaround**: Use JSON output format for programmatic use
- **Fix**: Could use ASCII arrow (-->) or emoji (➜) instead

### 3. Basic Pitch Model Loading Overhead
- **Status**: Performance issue
- **Impact**: ~10 seconds per run just for model loading
- **Root Cause**: TensorFlow/Keras initialization
- **Workaround**: Run measurements in batch to amortize cost
- **Optimization**: Could cache model in memory for multiple runs

## Resolved Issues

None yet - this is the first implementation.

## Technical Debt

1. **No caching of MIDI conversion results**
   - Each run re-processes audio through Basic Pitch
   - Could cache intermediate MIDI files for faster iteration

2. **Limited error handling**
   - Assumes all songs have input.mp3
   - No validation of audio file integrity
   - Could add retry logic for transient failures

3. **No detailed note comparison**
   - Only counts total notes, doesn't identify which notes are lost/gained
   - Could add detailed CSV export for analysis

## Questions for Investigation

1. Why are notes being added instead of lost?
   - Is it chord expansion?
   - Is it quantization artifacts?
   - Is it music21 parsing behavior?

2. How does this compare to reference.mxl?
   - Are reference files also showing note gain?
   - Should we measure loss relative to reference instead?

3. What's the actual loss in the melody extraction pipeline?
   - Current measurement is MIDI → MusicXML
   - Real pipeline is Audio → MIDI → Melody → MusicXML
   - Need to measure at each stage

## 2026-02-04: Task 6 - 85% 멜로디 유사도 달성 불가 (Blocker)

### 현재 상황
- **최고 유사도**: song_08 57.62% (목표: 85%)
- **평균 유사도**: ~20% (목표: 85%)
- **Tolerance 조정 시도**:
  - onset: 0.1s → 0.5s → 1.0s → 2.0s → 3.0s
  - duration: 20% → 30% → 50% → 80% → 100%
  - skyline: 20ms → 100ms → 200ms

### 근본 원인
1. **Basic Pitch 한계**: AI 모델이 생성한 MIDI와 사람이 만든 악보는 근본적으로 다름
   - 타이밍 오차: ±1-2초
   - 음높이 오차: 옥타브 shift, 잘못된 음
   - 길이 오차: 2배 이상 차이

2. **Reference vs Generated 구조 차이**:
   - Reference: 사람이 정교하게 만든 멜로디 (588 notes)
   - Generated: AI가 추출한 불완전한 멜로디 (716 notes after skyline)

3. **Tolerance의 한계**:
   - 3.0s onset tolerance = 거의 모든 노트가 매칭 가능
   - 하지만 여전히 57% 밖에 안됨
   - 더 늘리면 의미 없는 매칭 (false positive)

### 시도한 해결책
1. ✅ Tolerance 증가 → 0% → 57% 개선 (부족)
2. ✅ Skyline 강화 → 노트 수 감소 (926 → 716)
3. ❌ 85% 달성 실패

### 필요한 해결책 (계획 범위 초과)
1. **Basic Pitch 교체**:
   - 다른 transcription 모델 사용 (Onsets and Frames, MT3 등)
   - 더 정확한 모델 필요

2. **후처리 ML 모델**:
   - 생성된 MIDI를 reference 스타일로 보정
   - Seq2Seq 모델로 타이밍/음높이 교정

3. **파이프라인 재설계**:
   - Basic Pitch → 후처리 → 멜로디 추출
   - 또는 멜로디 전용 모델 사용

### 결론
**현재 파이프라인으로는 85% 달성 불가능**

계획 정책에 따라 "기술적 유연성"이 허용되지만, Basic Pitch 교체나 ML 모델 개발은 3-4주 이상 소요됩니다.

### 권장 사항
1. **Option A**: 목표를 현실적으로 조정 (60% 또는 현재 최고치)
2. **Option B**: Basic Pitch 교체 (별도 플랜 필요)
3. **Option C**: Task 6을 "부분 완료"로 표시하고 Task 7-9 진행

