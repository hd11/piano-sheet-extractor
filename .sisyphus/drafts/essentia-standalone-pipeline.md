# Draft: Essentia 단독 멜로디 파이프라인

## Requirements (confirmed)
- **접근법**: Essentia 단독 사용 (Basic Pitch 하이브리드 아님)
- **평가 지표**: Note F1 Score (mir_eval 기반, 시간+피치 고려)
- **목표 성능**: Note F1 >= 70%
- **테스트 전략**: 기존 골든 테스트만 사용 (새 TDD 없음)
- **Essentia 개선**: 현재 상태로 진행 (31% 기준점에서 시작)
- **실패 시 대응**: 결과 보고 (하이브리드 폴백 없음, 목표 하향 없음)

## Technical Decisions
- **Essentia 현재 구현 유지**: F0→Note 변환 로직 수정 없음
- **평가 지표 변경**: pitch_class_similarity → Note F1
- **mir_eval 도입**: Note Precision/Recall/F1 계산

## Research Findings (from Oracle)
- pitch_class_similarity 문제점: 시간/리듬 무시, 옥타브 무시, 노트 수 많으면 과대평가
- Essentia 31% 원인: F0→Note 변환 손실, confidence threshold 문제
- 권장: Essentia를 "가이드"로 사용하되, 사용자는 단독 사용 선택

## Scope Boundaries
- **INCLUDE**: 
  - Note F1 평가 지표 구현
  - 골든 테스트를 Note F1 기준으로 전환
  - Essentia 단독 파이프라인 결과 측정
- **EXCLUDE**:
  - Essentia 파라미터 튜닝
  - F0→Note 변환 알고리즘 개선
  - Basic Pitch 하이브리드 접근법
  - 새로운 TDD 테스트 추가

## Open Questions
- (없음 - 모든 결정 완료)

## Key Files
- `backend/core/melody_extractor.py` - 현재 파이프라인
- `backend/scripts/essentia_melody_extractor.py` - Essentia 스크립트
- `backend/tests/golden/test_golden.py` - 골든 테스트
- `backend/tests/golden/data/song_01~08/` - 테스트 데이터
