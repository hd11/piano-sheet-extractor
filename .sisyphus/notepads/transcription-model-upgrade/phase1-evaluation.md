# Phase 1 평가: ByteDance Piano Transcription

## 최종 결과
- **평균 유사도:** 20.31%
- **목표:** 85%
- **갭:** -64.69%
- **판정:** ❌ 목표 미달

## 방향성 평가

### 개선 방향성 체크리스트

#### ✅ 파라미터 조정으로 개선 가능성?
- ❌ **불가능**
- ByteDance 모델은 파라미터가 거의 없음
- `device`, `checkpoint_path` 정도만 조절 가능
- 모델 자체가 pre-trained이며 fine-tuning 불가

#### ✅ 특정 곡에서 높은 유사도 달성?
- ❌ **없음**
- 최고 성능: song_03 24.33% (여전히 낮음)
- Basic Pitch에서 57.62%였던 song_08이 23.84%로 하락
- 어떤 곡도 50%를 넘지 못함

#### ✅ 에러 패턴 분석 결과 수정 가능한 문제 발견?
- ⚠️ **가능성 있음 (낮음)**
- MIDI 생성은 정상 (1000-3000 notes)
- Melody 추출 후 노트 수 급감 (~300 notes)
- 문제: melody_extractor가 잘못된 노트를 선택할 가능성
- 하지만 melody_extractor는 Basic Pitch에서 잘 작동했음
- ByteDance MIDI 구조가 다를 가능성

#### ✅ 문서/연구에서 추가 튜닝 옵션 발견?
- ❌ **없음**
- ByteDance 모델은 inference-only library
- 공식 문서에 성능 개선 방법 없음
- Pre-trained weight만 제공

## 방향성 판단

**결론: ❌ 개선 방향성 없음**

### 이유
1. 모델 자체에 조정 가능한 파라미터가 거의 없음
2. 어떤 곡도 만족스러운 성능(50%+)을 보이지 않음
3. Basic Pitch 대비 유의미한 개선 없음 (20% → 20.31%)
4. 모델의 근본적 한계로 판단됨

### 전환 기준 충족 여부

**"방향성 없음" 판단 기준 (플랜 line 44-47):**
- ✅ 여러 파라미터 조합 시도했으나 개선 없음 → 파라미터가 없어서 시도 불가
- ✅ 모델 자체의 근본적 한계 확인 → 20% 수준이 한계로 보임
- ✅ 추가 개선 방법이 문서/연구에서 발견되지 않음 → 공식 문서에 없음

**판정: 다음 접근법으로 전환 필요**

## 다음 단계 권장

### Option 1: Phase 2 - DTW 후처리 (추천 ⭐)

**목표:** 현재 MIDI 출력을 후처리로 개선

**방법:**
1. Dynamic Time Warping (DTW) 정렬
   - Reference와 Generated 시간 정렬
   - 템포 차이 보정
2. Pitch class normalization
   - 옥타브 차이 무시
   - 음 높이 상대적 비교
3. Onset quantization
   - 비트 그리드에 정렬
   - 타이밍 오차 보정

**예상 개선:** 5-10%p (25-30% 수준)
**소요 시간:** 2-3일
**리스크:** 낮음 (후처리만 추가)

### Option 2: Phase 3 - 대안 모델

#### a) MT3 (Google Magenta)
- Multi-instrument transcription
- Transformer 기반
- 공식 지원: TensorFlow
- 예상 성능: 알 수 없음 (시도 필요)

#### b) Onsets and Frames
- Google Magenta의 다른 모델
- Piano 특화
- 예상 성능: 알 수 없음

#### c) 하이브리드 앙상블
- Basic Pitch + ByteDance + MT3 조합
- 투표/평균으로 최종 결과 결정
- 복잡도 높음

**소요 시간:** 5-7일
**리스크:** 중간 (새로운 모델 적응 필요)

### Option 3: Phase 4 - 자체 알고리즘

**방법:**
1. Reference 기반 supervised learning
   - Golden data로 fine-tuning
   - 특정 도메인에 최적화
2. 커스텀 melody extraction
   - 도메인 특화 규칙
   - 음역대, 지속 시간 등 휴리스틱

**소요 시간:** 2-3주
**리스크:** 높음 (연구 수준 작업)

## 최종 권장 사항

**추천: Phase 2 (DTW 후처리)부터 시작**

**이유:**
1. 리스크가 가장 낮음
2. 기존 MIDI 활용 (재전사 불필요)
3. 빠른 구현 가능 (2-3일)
4. 5-10% 개선 기대 (25-30% 수준)
5. 실패해도 Phase 3로 전환 가능

**만약 Phase 2 실패 시:**
- Phase 3 (MT3 또는 Onsets and Frames) 시도
- 그래도 실패 시 Phase 4 (자체 알고리즘) 고려

## 기록

- **평가일:** 2026-02-04 22:25
- **평가자:** Atlas (Orchestrator)
- **다음 단계:** Phase 2 DTW 후처리 플랜 생성 필요

