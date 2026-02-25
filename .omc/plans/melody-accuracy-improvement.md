# 멜로디 추출 정확도 개선 계획

## 현재 상태
- **pitch_class_f1 평균: 0.06** (39차례 파라미터 튜닝 후에도 거의 변화 없음)
- 레거시 CQT 파이프라인으로 평가. Demucs+torchcrepe 신규 파이프라인은 Windows hang으로 미평가
- 문제는 단일 원인이 아닌 **7개 복합 문제**의 곱셈적 결합

## 근본 원인 분석

### 문제 1: 평가 메트릭 버그 — offset_ratio 기본값 (CRITICAL)
- **파일:** `core/comparator.py:119-126`, `:177-184`
- `mir_eval.transcription.precision_recall_f1_overlap` 호출 시 `offset_ratio=None` 미설정
- mir_eval 기본값 `offset_ratio=0.2`가 자동 적용 → 노트 종료 시간도 20% 이내로 일치해야 "정답"
- 파이프라인의 연속 시간 기반 노트 vs 참조의 퀀타이즈된 악보 → 지속시간 불일치로 정확한 노트도 탈락
- **영향: 점수를 2~5배 감소시킴**

### 문제 2: 레거시 파이프라인의 다성 음악 처리 불가
- **파일:** `core/melody_extractor.py` (전체)
- CQT 기반 파이프라인이 전체 믹스에서 동작 → 보컬이 아닌 반주 피치 추출
- chroma_similarity=0.92 (같은 키/스케일) vs pitch_class_f1=0.06 (노트별 매칭 실패)
- → 올바른 조성의 **잘못된 악기** 음을 추출하고 있음

### 문제 3: 체계적 과소 추출 (노트 수 부족)
- 생성 노트 수가 참조의 23~84% (IRIS OUT은 23%로 극단적)
- 레거시 파이프라인의 윤곽 연결이 개별 노트를 장음으로 병합
- recall 상한이 노트 수 비율로 제한됨

### 문제 4: 참조 악보 추출의 skyline 알고리즘 한계
- **파일:** `core/reference_extractor.py:40, :74, :82-83`
- `score.parts[0]` 하드코딩 → 피아노 우손 파트가 항상 멜로디라는 가정
- 코드 반주, 아르페지오, 대선율이 포함될 수 있음
- float 키 사용으로 onset 중복 제거 시 부동소수점 오차 가능
- 높은 피치로 교체 시 duration 미갱신

### 문제 5: F0→노트 변환의 노트 파편화
- **파일:** `core/f0_extractor.py:140-166`
- 정확한 MIDI 값 일치만 허용 (line 151) → 비브라토로 인접 MIDI 값 진동 시 분절
- 갭 브리징 없음 → 자음/호흡으로 한 프레임 탈락 시 노트 분리
- `min_note_dur=0.02` (20ms)로 미세 파편도 생존

### 문제 6: torchcrepe "tiny" 모델 사용
- **파일:** `core/f0_extractor.py:30`
- 가장 저정확도 모델. "full" 대비 ~5배 빠르지만 정확도 열세
- 분리된 보컬에서는 tiny도 충분할 수 있으나, 전체 믹스에서는 부족

### 문제 7: 퀀타이즈 불일치
- **파일:** `core/musicxml_writer.py:11-22`
- 파이프라인: 연속 시간(10ms 해상도) / 참조: 16분음표 그리드(120 BPM)
- offset_ratio와 결합 시 오차 증폭

## 개선 계획 (우선순위순)

### Phase 1: 즉시 적용 (Low Effort, High Impact)

#### 1.1 평가 메트릭 수정 — offset_ratio=None
- **파일:** `core/comparator.py`
- **변경:** line 119, 177의 `precision_recall_f1_overlap` 호출에 `offset_ratio=None` 추가
- **예상 효과:** pitch_class_f1 2~5배 즉시 향상
- **검증:** 기존 결과와 새 결과 비교 출력

#### 1.2 onset-only 메트릭 추가
- **파일:** `core/comparator.py`
- **변경:** `offset_ratio=None`인 별도 메트릭 추가 (기존 메트릭도 유지)
- **목적:** 지속시간 정확도 vs 피치+온셋 정확도 분리 진단

### Phase 2: 노트 세그먼테이션 개선 (Medium Effort, High Impact)

#### 2.1 비브라토 허용 범위 추가
- **파일:** `core/f0_extractor.py:140-166` (`f0_to_notes`)
- **변경:**
  - 정확한 MIDI 일치 대신 ±1 반음 허용
  - 현재 구간의 중앙값(median) MIDI를 최종 피치로 사용
- **검증:** 비브라토가 있는 곡에서 노트 수 비교

#### 2.2 갭 브리징 추가
- **파일:** `core/f0_extractor.py`
- **변경:** 50ms 미만의 무성 구간은 이전 노트 계속
- **검증:** 생성 노트 수가 참조에 근접하는지 확인

#### 2.3 최소 노트 길이 상향
- **파일:** `core/f0_extractor.py:24`
- **변경:** `min_note_dur` 0.02 → 0.06초
- **검증:** 파편 노트 감소 확인

### Phase 3: 참조 추출 개선 (Medium Effort, Medium Impact)

#### 3.1 onset 키 반올림
- **파일:** `core/reference_extractor.py:74`
- **변경:** `round(onset_seconds, 3)` 사용

#### 3.2 duration 갱신 수정
- **파일:** `core/reference_extractor.py:82-83`
- **변경:** 높은 피치로 교체 시 해당 노트의 duration도 함께 갱신

#### 3.3 파트 선택 유연화
- **파일:** `core/reference_extractor.py:40`
- **변경:** 파트 인덱스를 파라미터화하거나 clef/이름 기반 자동 감지

### Phase 4: Demucs 파이프라인 평가 (Medium Effort, Highest Potential)

#### 4.1 비-Windows 환경에서 Demucs 평가 실행
- Docker, Linux, 또는 Mac에서 `scripts/evaluate.py` 실행
- Phase 1-3 수정 적용 후 평가하여 효과 측정
- **예상 효과:** 보컬 분리로 F0 정확도 극적 향상 (0.06 → 0.30~0.50+)

#### 4.2 torchcrepe 모델 업그레이드
- **파일:** `core/f0_extractor.py:30`
- **변경:** `model="tiny"` → `model="full"` (또는 파라미터화)
- **Trade-off:** ~5배 느려지나 피치 정확도 향상

### Phase 5: 고급 개선 (Higher Effort)

#### 5.1 적응적 BPM 감지
- librosa.beat.beat_track으로 실제 BPM 감지 후 퀀타이즈 적용
- 120 BPM 고정값 대체

#### 5.2 보컬 범위 필터링
- Demucs 출력에서도 잔여 반주가 있을 수 있음
- MIDI 36~84 (C2~C6) 범위 외 노트 필터링

## 수용 기준

| 기준 | 목표 | 측정 방법 |
|------|------|-----------|
| pitch_class_f1 (offset_ratio=None) | >= 0.30 | `scripts/evaluate.py` 8곡 평균 |
| 노트 수 비율 (gen/ref) | 0.7~1.3 | 평가 JSON의 note_counts |
| onset_f1 | >= 0.40 | 평가 JSON |
| Phase 1 단독 효과 | 기존 대비 2배+ 향상 | 동일 파이프라인 재평가 |
| 비브라토 파편화 | 50% 이상 감소 | Phase 2 전후 노트 수 비교 |

## 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| Windows Demucs hang 미해결 | Docker/WSL2로 우회; Phase 1-3은 Windows에서 검증 가능 |
| 비브라토 허용이 인접 음 병합 | ±1 반음 허용 + 중앙값 사용으로 최소화 |
| 참조 악보가 보컬 멜로디와 불일치 | 1~2곡 수동 검증 후 skyline 개선 판단 |
| torchcrepe full 모델 속도 | 캐싱으로 반복 실행 비용 제거 |

## 실행 순서

```
Phase 1 (즉시) → 재평가 → Phase 2 → 재평가 → Phase 3 → 재평가 → Phase 4 (Demucs) → 최종 평가
```

각 Phase 후 재평가하여 개선 효과를 누적 측정한다.
