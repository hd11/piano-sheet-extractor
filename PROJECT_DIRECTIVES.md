# Project Directives (필수 지침)

이 파일은 환경이 바뀌어도 반드시 따라야 할 프로젝트 규칙을 정의합니다.

## 핵심 목표

- MP3에서 **보컬 멜로디**만 추출하여 MusicXML 악보로 변환
- 주요 메트릭: `pitch_class_f1` (옥타브 무관 F1, 200ms 허용)
- 목표: 평균 0.50 이상

## 필수 전제 조건

1. **참조 악보(.mxl)는 풀 편곡 악보이다**
   - 보컬뿐 아니라 피아노 반주, 코드 등이 모두 포함됨
   - 현재 skyline 알고리즘(최고음 추출)으로 멜로디를 근사하지만, 반주의 높은 음이 포함될 수 있음
   - 참조 노트 수와 추출 노트 수의 차이는 자연스러운 것이며, **노트 수 자체는 의미 없음**

2. **멜로디 유사도가 핵심이다**
   - 노트 수가 달라도 멜로디가 비슷하면 성공
   - recall보다 **precision과 멜로디 윤곽(contour) 유사도**가 더 중요
   - 참조에 반주 음이 섞여있으므로 recall이 낮은 것은 정상

3. **K-pop 한국어 파일명 지원 필수**
   - 테스트 데이터가 모두 한글 파일명
   - UUID 임시 파일 우회 패턴 유지

## 환경 설정

```bash
# Python 3.12+ (brew install python@3.12)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install demucs torchcrepe  # requirements.txt에 빠져있음

# ffmpeg 필수 (demucs가 ffprobe 사용)
brew install ffmpeg
```

## 테스트 실행

```bash
# 단일 곡 테스트 (임시 디렉토리에 MP3+MXL 심링크, cache는 실제 디렉토리로)
mkdir -p /tmp/piano-test/cache
ln -sf "$(pwd)/test/곡이름.mp3" /tmp/piano-test/
ln -sf "$(pwd)/test/곡이름.mxl" /tmp/piano-test/
python scripts/evaluate.py --input-dir /tmp/piano-test --output /tmp/piano-test/result.json

# 전체 8곡 평가
python scripts/evaluate.py --input-dir test --output results/eval_result.json
```

## 의존성 주의

- `requirements.txt`에 `demucs`, `torchcrepe`가 **빠져있음** (별도 설치 필요)
- `ffmpeg`/`ffprobe` 시스템 의존성 필요
- Demucs 첫 실행 시 모델 다운로드 (~320MB, `~/.cache/torch/hub/checkpoints/`)

---

## 변경 이력

### v3 (2026-02-26) — F0 추출 파라미터 튜닝

`core/f0_extractor.py` 변경 사항:

| 파라미터 | 이전 | 변경 후 | 이유 |
|---|---|---|---|
| Viterbi 디코더 | 비활성 (주석) | **활성화** | 시간적 연속성 강제, 옥타브 점프 감소 |
| Median 필터 윈도우 | 5 | **3** | Viterbi와 이중 스무딩 방지 |
| Periodicity 임계값 | 0.6 | **0.45** | 더 많은 보컬 프레임 캡처 (under-generation 해소) |
| 비브라토 톨러런스 | 1.5 반음 (running median) | **1.0 반음 (앵커 방식)** | median 드리프트 버그 수정, 인접 음 병합 방지 |
| Gap bridging | 60ms | **100ms** | 자음/짧은 호흡 구간 분절 감소 |

#### 테스트 결과 (꿈의 버스)

| 버전 | pitch_class_f1 | chroma | 노트 수 |
|---|---|---|---|
| 원본 | 0.599 | 0.996 | 371 |
| v3 (위 변경 전체) | **0.614** | 0.993 | 514 |

#### 시도했으나 폐기한 변경

- **참조 멜로디 contour-following 추출** (`reference_extractor.py`): 보컬 범위 필터 + nearest-neighbor 방식으로 skyline 대체 시도. pitch_class_f1이 0.599→0.441로 **크게 하락**하여 폐기. 오른손 파트가 이미 멜로디 위주라 skyline이 더 적합.

### 베이스라인 (마지막 커밋 04a2f1c 기준)

- 8곡 평균 pitch_class_f1: **0.38**
- 꿈의 버스: 0.591, 여름이었다: 0.577, Golden: 0.113, IRIS OUT: 0.189

---

## 개선 작업 시 참고

- 참조 악보가 풀 편곡이므로, pitch_class_f1의 이론적 상한은 1.0보다 낮을 수 있음
- 평가 시 반드시 후처리(옥타브 보정 + 시간 정렬) 적용 상태에서 비교
- Demucs 보컬 분리 캐시는 `test/cache/`에 저장됨 (5분+ 절약)
- `reference_extractor.py`의 skyline 알고리즘 수정은 신중하게 — 단순 최고음이 현재로선 가장 효과적
- 개선 시 한 곡(꿈의 버스)으로 빠르게 검증 후, 전체 8곡으로 확인하는 2단계 진행 권장

## 남은 개선 후보

- MIDI 범위 축소 (36-96 → 48-86): 서브하모닉/오버톤 필터링 (LOW impact)
- 시간 윈도우 기반 옥타브 보정: 전역→15초 윈도우 (MEDIUM impact)
- hop_ms 5.0으로 세밀화: onset 정확도 개선, 처리시간 2배 (LOW-MEDIUM impact)
- precision/recall 별도 리포트: 풀 편곡 참조 특성상 recall이 구조적으로 낮으므로 precision 별도 확인 유용
