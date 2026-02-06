# Draft: 멜로디 추출 시스템 전환 + 단기 스프린트

## 최종 진행 순서 (확정)

1. **Phase 0**: Docker 제거 + 로컬 환경 세팅
2. **Phase 1**: 멜로디 모델 스파이크 (CREPE, Audio-to-MIDI, Librosa)
3. **Phase 2**: 선택된 모델 통합 + 12/8 박자 지원
4. **Phase 3**: (선택적) 코드 정리

---

# (이하 기존 내용)

## 사용자 요구사항 (확인됨)

### 리팩토링 목적
- [x] 코드 정리/가독성 (중복 제거, 파일 분리, 네이밍 개선)
- [x] 성능 최적화
- [x] 아키텍처 개선 (모듈 경계 재정의, 의존성 정리)

### 범위
- backend/core만 (핵심 비즈니스 로직)

### 단기 스프린트 우선순위
- 1순위: 멜로디 추출 개선 (9.26% → 15-20% F1)

---

## 코드 분석 결과

### 테스트 커버리지 현황

| 모듈 | 테스트 | 상태 |
|------|--------|------|
| melody_extractor.py | 337줄 unit tests | ✅ 우수 |
| difficulty_adjuster.py | 없음 | ❌ 필요 |
| comparison_utils.py | 없음 | ❌ 필요 |

### 리팩토링 후보

1. **difficulty_adjuster.py**
   - 테스트 없음
   - Beat 기반 베이스 단순화가 싱코페이션 패시지에서 중요 노트 손실
   - Hard 난이도에 voice leading 최적화 없음

2. **comparison_utils.py**
   - 테스트 없음
   - 매직 넘버 (DTW sigmoid 상수 6.0) 문서화 안됨
   - Graceful degradation 로직 복잡

3. **melody_extractor.py**
   - 테스트 우수
   - ONSET_TOLERANCE, MIN_DURATION 파라미터화 가능
   - 옥타브 정규화 edge case 가능

---

## 멜로디 추출 개선 방향

### 레퍼런스 편곡자 피드백 (2026-02-06)
> 1. "뭔가 다 받아적으려고 하는걸 하지말고, 딱 멜로디만 간결하게 들을수있어야하는데 그게 어렵나봐"
> 2. "8분의12박자로 표현해달라고해줘"
> 3. "그냥 정말 멜로디만 적어줬으면 좋겠다. 애매하게 다 적고 있다"

**핵심 문제**:
- **멜로디 순도 부족** → "애매하게 다 적음" = 멜로디 + 반주 + 화음이 혼재
- **간결성 부족** → 필요 이상으로 많은 노트
- 박자 표기 문제 → 12/8 박자 (compound meter) 지원 필요

**해결 방향**:
- Easy 난이도 = 정말 멜로디"만" (single melodic line)
- 현재 Skyline보다 더 공격적인 필터링 필요
- 화성음/반주음 제거 로직 강화

---

## 사용자 결정 (2026-02-06)

### 1. Easy 난이도 제거
> "일단 이지 난이도 제공은 빼도 됨. 정확한 멜로디 악보를 제공하는데 더 집중했음 좋겠어"

**변경사항**:
- 3단계 (Easy/Medium/Hard) → 2단계 (Medium/Hard) 또는 단일 출력
- difficulty_adjuster.py 단순화
- "멜로디 악보" = 별도 출력으로 분리 (난이도와 무관)

### 2. Docker 제거 검토
> "개인적으로 나만 쓰는 프로그램인데 굳이 도커로 실행해야하나 싶네. 안그래도 메모리도 많이 부족한데"

**결정됨**:
- ✅ Docker 완전 제거 → 로컬 Python 직접 실행
- ✅ 메모리 절약 + GPU 직접 접근

### 3. 출력물 단순화
> 멜로디 악보만 출력

**변경사항**:
- Easy/Medium/Hard → **멜로디만**
- Pop2Piano 풀 편곡 출력 제거
- 순수 멜로디 라인 + 12/8 박자

### 4. 멜로디 추출 모델 탐색
> Pop2Piano 대신 멜로디 추출 전용 모델 탐색

**이유**:
- Pop2Piano = 피아노 "편곡" 생성 (멜로디 + 반주 + 화음)
- 원하는 것 = 순수 "멜로디" 추출
- 다른 접근 방식 필요

**탐색 완료 — 스파이크 테스트 예정**:

| 모델 | 출력 | 메모리 | 설치 |
|------|------|--------|------|
| CREPE | Pitch | 낮음 | `pip install crepe` |
| Audio-to-MIDI | MIDI | 중간 | git clone + PyTorch |
| Librosa+PYIN | Pitch | 최소 | `pip install librosa` |

**스파이크 계획**:
- 3개 모델로 동일 곡 테스트
- 레퍼런스 멜로디와 비교
- 가장 적합한 모델 선택

### 현재 구현
- Skyline 알고리즘 (200ms 내 가장 높은 음 선택)
- 5단계 파이프라인: skyline → 짧은 노트 필터링 → 오버랩 해결 → 옥타브 정규화

### 개선 방향 (피드백 기반)
- [x] **노트 수 축소**: 너무 많은 노트 포함 → 더 공격적인 필터링
- [x] **간결성 우선**: "다 받아적기" 대신 핵심 멜로디만
- [ ] Harmonic context 기반 정제 (코드 구성음 제외)
- [ ] 멜로디 연속성 점수 도입 (점프 페널티)
- [ ] MIN_DURATION 튜닝 (50ms → 100ms? 더 긴 노트만)

---

## 코드베이스 분석 결과 (완료)

### 파일 크기 순위 (총 4,215줄)

| 파일 | 줄 수 | 우선순위 |
|------|-------|----------|
| musicxml_comparator.py | 673 | **P1** |
| job_manager.py | 602 | **P2** |
| midi_to_musicxml.py | 517 | P4 |
| audio_analysis.py | 489 | P3 |
| comparison_utils.py | 446 | - |
| difficulty_adjuster.py | 353 | P5 |
| musicxml_melody_extractor.py | 238 | - |

### .bak 백업 파일
- `audio_to_midi_basic_pitch.py.bak` (4KB)
- `audio_to_midi_bytedance.py.bak` (4.6KB)

### 코드 중복 패턴

1. **노트 추출 중복** (HIGH) — 80줄 절감 가능
   - musicxml_comparator._extract_notes()
   - musicxml_melody_extractor._extract_melody_notes()
   - midi_comparator._notes_to_noteevents()

2. **비교 함수 분산** (HIGH) — 100줄 절감 가능
   - musicxml_comparator: 4개 비교 함수
   - midi_comparator: 2개 비교 함수

3. **Async/Sync 패턴 중복** (MEDIUM) — 100줄 절감 가능
   - job_manager: 3쌍의 async/sync 함수

### LSP 타입 에러 (발견됨)

| 파일 | 에러 수 | 주요 문제 |
|------|---------|-----------|
| midi_to_musicxml.py | 15 | music21 타입 export 이슈 |
| comparison_utils.py | 8 | mir_eval/dtw 조건부 import |
| musicxml_melody_extractor.py | 6 | music21 타입 이슈 |
| difficulty_adjuster.py | 2 | music21 Stream export |

### 예상 절감 효과
- **총 절감**: 740줄+ (17.5% 감소)
- **예상 소요**: 20-25시간
