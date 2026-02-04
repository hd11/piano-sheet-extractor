# Reference Matching V2 - 세션 핸드오프 프롬프트

## 다음 세션 시작 시 사용할 프롬프트

```
reference-matching-v2 플랜을 계속 진행해줘.

현재 상태:
- Task 1-5: 완료 (인프라 구축)
- Task 6: 진행 중 (85% 목표 달성 실패 - 현재 최고 57.62%)
- Task 7-9: 미시작

핵심 블로커:
- Basic Pitch 모델의 한계로 85% 유사도 달성 불가
- Tolerance 조정만으로는 한계 (0% → 57% 개선이 최대)

다음 단계 선택지:
1. Basic Pitch 파라미터 튜닝 시도
2. 다른 transcription 모델 조사 (MT3, Onsets and Frames)
3. 후처리 ML 모델 개발
4. 현실적인 목표로 재설정 후 Task 7-9 진행

상세 내용은 아래 파일 참고:
- .sisyphus/plans/reference-matching-v2.md (전체 플랜)
- .sisyphus/notepads/reference-matching-v2/issues.md (블로커 상세)
- .sisyphus/session-summary.md (세션 요약)
```

---

## 빠른 컨텍스트 복원

### 커밋 히스토리 (최근 10개)
```bash
git log --oneline -10
```

### 현재 테스트 상태 확인
```bash
docker compose exec -T backend pytest tests/golden/ -m melody -v 2>&1 | grep "Similarity:"
```

### 주요 파일 위치
- 플랜: `.sisyphus/plans/reference-matching-v2.md`
- 이슈: `.sisyphus/notepads/reference-matching-v2/issues.md`
- 세션 요약: `.sisyphus/session-summary.md`
- 비교 로직: `backend/core/musicxml_comparator.py`
- 멜로디 추출: `backend/core/melody_extractor.py`
- 테스트: `backend/tests/golden/test_golden.py`
