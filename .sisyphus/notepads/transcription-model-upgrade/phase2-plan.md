# Phase 2: DTW 후처리 구현 계획

## 목표
- 현재 ByteDance 출력 (20.31%)을 DTW 후처리로 개선
- 목표: 25-30% 수준 (5-10%p 개선)

## 구현 항목

### 1. DTW (Dynamic Time Warping) 정렬
**목적:** Reference와 Generated 멜로디의 시간 정렬

**방법:**
- `dtaidistance` 또는 `fastdtw` 라이브러리 사용
- Reference와 Generated 멜로디 간 최적 정렬 경로 찾기
- 템포 차이 보정

**예상 개선:** 2-3%p

### 2. Pitch Class Normalization (옥타브 무시)
**목적:** 옥타브 차이로 인한 불일치 제거

**방법:**
- MIDI note number를 pitch class (0-11)로 변환
- C4(60) → 0, C#4(61) → 1, ..., B4(71) → 11
- C5(72) → 0 (같은 pitch class)

**예상 개선:** 3-5%p

### 3. Onset Quantization (비트 그리드 정렬)
**목적:** 타이밍 오차 보정

**방법:**
- 비트 그리드 설정 (예: 16분음표 단위)
- 각 노트의 onset을 가장 가까운 그리드에 정렬
- 미세한 타이밍 차이 무시

**예상 개선:** 1-2%p

### 4. 후처리 파이프라인 통합
**목적:** 기존 코드에 통합

**방법:**
- `backend/core/melody_postprocessor.py` 생성
- `compare_note_lists` 함수 수정 또는 래핑
- Golden test에서 자동 적용

## 구현 순서

1. **Phase 2.1:** Pitch Class Normalization (가장 간단, 효과 큼)
2. **Phase 2.2:** Onset Quantization
3. **Phase 2.3:** DTW 정렬 (가장 복잡)
4. **Phase 2.4:** 통합 테스트 및 측정

## 예상 일정
- Phase 2.1: 0.5일
- Phase 2.2: 0.5일
- Phase 2.3: 1일
- Phase 2.4: 0.5일
- **총:** 2.5일

## 리스크
- 낮음: 기존 코드 변경 최소화
- 롤백 가능: 후처리만 제거하면 원상복구

## 성공 기준
- 8곡 평균 >= 25% (현재 20.31% 대비 +5%p)
- 개별 곡 회귀 없음 (모든 곡 >= 기존 성능)

