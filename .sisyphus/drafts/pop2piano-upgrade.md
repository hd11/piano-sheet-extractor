# Draft: Pop2Piano 기반 피아노 편곡 시스템 업그레이드

## Requirements (confirmed)

### 핵심 목표
- 전체 팝송 오디오 → 피아노 편곡 악보 자동 생성
- 사람이 만든 피아노 편곡(reference)과 높은 유사도 달성
- "편곡(Arrangement)" 문제이지, "인식(Transcription)" 문제가 아님

### 사용자 요구사항
- 공격적 접근 (전략 3): 모든 가능한 방법을 시도
- Pop2Piano 통합 + 비교 알고리즘 개선 + 메트릭 재설계 + 파이프라인 개편
- 기존 MXL + 새로 추가된 MIDI 레퍼런스를 모두 활용한 복합 테스트

## Technical Decisions

### 모델 교체
- ByteDance Piano Transcription → Pop2Piano (HuggingFace transformers)
- 이유: ByteDance는 "피아노 인식" 모델, Pop2Piano는 "피아노 편곡 생성" 모델
- Pop2Piano는 K-pop 데이터로 학습되어 도메인 일치

### 비교 알고리즘
- 기존 greedy matching → mir_eval + DTW + 다중 메트릭
- 복합 점수 체계 도입 (멜로디 + 코드 + 리듬 + 구조)

## Research Findings

### Pop2Piano
- HuggingFace `transformers`에 공식 통합
- 팝 오디오 → 피아노 커버 MIDI end-to-end
- 16+ arranger 스타일 선택 가능
- K-pop + Western Pop + Hip Hop 학습
- GitHub: 484 stars

### 현실적 목표 (Oracle 분석)
- 특정 편곡과 노트 단위 85% 일치는 비현실적 (편곡은 정답이 하나가 아님)
- 복합 메트릭(코드+멜로디+리듬+구조) 기준 85%는 도전적이지만 시도 가치 있음

## Test Data Inventory

### 8곡 레퍼런스 파일
| # | 곡명 | MP3 | MXL | MIDI 원본 | MIDI 쉬운 | MIDI 다장조 |
|---|------|-----|-----|-----------|----------|------------|
| 1 | Golden | ✓ | ✓ | ✓ | ✓ | - |
| 2 | IRIS OUT | ✓ | ✓ | ✓ | ✓ | - |
| 3 | 꿈의 버스 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4 | 너에게100퍼센트 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 5 | 달리 표현할 수 없어요 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 6 | 등불을 지키다 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 7 | 비비드라라러브 | ✓ | ✓ | ✓ | ✓ | - |
| 8 | 여름이었다 | ✓ | ✓ | ✓ | ✓ | ✓ |

### MIDI 레퍼런스 활용 방안
- **원본 MIDI**: MXL과 동일한 편곡의 정확한 노트 데이터 → 기본 비교 대상
- **쉬운 MIDI**: 간소화된 편곡 → "Easy" 난이도 출력 검증
- **다장조 MIDI**: C major 조옮김 버전 → 조옮김 기능 검증 및 pitch class 비교 보조

### 골든 테스트 구조 (기존)
- backend/tests/golden/data/song_01~08/ (input.mp3 + reference.mxl + metadata.json)
- MIDI 레퍼런스는 아직 골든 테스트에 미통합

### 골든 테스트 구조 (목표) — 사용자 확인: MIDI도 골든테스트에 포함 필수
- backend/tests/golden/data/song_XX/
  - input.mp3 (기존)
  - reference.mxl (기존)
  - reference.mid (추가: 원본 MIDI)
  - reference_easy.mid (추가: 쉬운 변형)
  - reference_cmajor.mid (추가: 다장조 변형, 해당곡만)
  - metadata.json (기존, 변형 정보 추가)

## Scope Boundaries

### INCLUDE
- Pop2Piano 통합
- 비교 알고리즘 전면 교체
- MIDI 레퍼런스 골든 테스트 통합
- MusicXML 폴리포닉 지원
- 난이도 시스템 재설계
- 복합 메트릭 설계

### EXCLUDE
- Frontend UI 변경 (별도 작업)
- 멀티스텝 보조 파이프라인 (Pop2Piano 결과 보고 후 판단)
- Fine-tuning (데이터 충분하지 않음)

## Open Questions
- (없음 - 모두 확인됨)
