# Task 4: 전체 8곡 스파이크 테스트 - 완료

## 구현 내용

### 1. spike_essentia.py 수정
- `--all` 옵션 추가 (argparse)
- `test_single_song()` 함수: 단일 곡 테스트 및 결과 반환
- `test_all_songs()` 함수: 8곡 순회 및 테이블 출력

### 2. 실행 결과
```bash
.venv/Scripts/python.exe scripts/spike_essentia.py --all
```

### 3. 결과 요약

| Song    | Skyline | Essentia | Improved |
|---------|---------|----------|----------|
| song_01 | 42.98% |  17.98% |          |
| song_02 | 82.35% |  12.09% |          |
| song_03 | 89.63% |  47.86% |          |
| song_04 | 83.20% |  52.18% |          |
| song_05 | 79.37% |  20.43% |          |
| song_06 | 81.34% |  34.37% |          |
| song_07 | 37.64% |  17.57% |          |
| song_08 | 80.28% |  44.77% |          |
|---------|---------|----------|----------|
| SUMMARY | 72.10% |  30.91% | 0/8 improved |

## 핵심 발견

1. **Skyline이 모든 곡에서 우수**
   - 평균 Skyline: 72.10%
   - 평균 Essentia: 30.91%
   - 차이: +41.19%

2. **Essentia가 개선한 곡: 0/8**
   - 모든 곡에서 Skyline이 더 나은 성능

3. **Essentia의 문제점**
   - 너무 적은 노트 추출 (79~276 notes vs reference 296~607 notes)
   - Skyline은 reference와 비슷한 노트 수 (405~693 notes)

## Evidence
- 전체 출력: `.sisyphus/evidence/task-4-all-songs.txt` (16KB)

## 다음 단계
- Task 5: Essentia 파라미터 튜닝 필요
  - `hopSize`, `minFrequency`, `maxFrequency` 조정
  - 더 많은 노트 추출 목표
