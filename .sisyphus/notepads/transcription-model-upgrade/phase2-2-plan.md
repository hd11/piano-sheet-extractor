# Phase 2.2: Onset Quantization 구현 계획

## 목표
- 타이밍 오차를 비트 그리드에 정렬하여 개선
- 예상 개선: 2-3%p (36.66% → 38-40%)

## 구현 방법

### Onset Quantization이란?
- 각 음표의 onset(시작 시간)을 가장 가까운 비트 그리드에 정렬
- 예: 16분음표 단위 그리드 사용
- 미세한 타이밍 차이 무시

### 구현 단계

1. **비트 그리드 계산**
   - BPM 기반 그리드 생성
   - 16분음표 단위 (quarter note / 4)
   - 예: BPM 120 → 16분음표 = 0.125초

2. **Onset 정렬**
   - 각 onset을 가장 가까운 그리드에 스냅
   - `quantized_onset = round(onset / grid_size) * grid_size`

3. **비교 함수 수정**
   - Quantized onset으로 비교
   - Pitch class normalization 유지

## 구현 위치
- `backend/core/musicxml_comparator.py`
- 새 함수: `compare_note_lists_with_quantization()`

## 예상 효과
- 타이밍이 약간 어긋난 음표 매칭 개선
- 특히 템포가 불안정한 곡에서 효과적

