# Draft: 보컬 분리 기반 멜로디 추출 파이프라인

## 요구사항 (확인됨)
- `test/` 폴더의 .mp3 = **보컬이 포함된 원곡** (AI가 만든 게 아님)
- `test/` 폴더의 .mxl = **피아노 편곡 악보** (멜로디 + 화음 포함)
- `test/` 폴더의 .mid = 피아노 편곡 MIDI
- `backend/tests/golden/data/` = **AI가 만든 가공물** (진짜 데이터 아님)
- 목표: **멜로디만 정확하게 추출**
- 환경: Windows, CPU only (내장 GPU), Python 3.11, Docker/WSL 불필요

## 기술 결정사항

### 파이프라인 (Oracle 확인)
```
input.mp3 (보컬 원곡)
  → audio-separator (보컬 분리, UVR 모델)
  → vocal.wav
  → librosa.pyin (monophonic pitch 추출)
  → pitch contour
  → note segmentation (voiced mask + smoothing + quantize)
  → MIDI melody
  → MusicXML 악보
```

### 라이브러리 선택
| 역할 | 선택 | 이유 |
|------|------|------|
| 보컬 분리 | audio-separator[cpu] | Windows 네이티브, 활발 유지보수, UVR 모델 |
| Pitch 추출 | librosa.pyin | 이미 의존성에 있음, monophonic에 적합, voiced/unvoiced 판별 |
| MIDI 생성 | pretty_midi | 이미 프로젝트에서 사용 중 |
| MusicXML | music21 | 이미 프로젝트에서 사용 중 |

### 레퍼런스 멜로디 추출 방식 (Oracle 확인)
- .mxl에서 treble clef part 가져오기
- onset별로 동시 발음 음표 그룹핑
- 그룹 내 최고 음 선택 (skyline)
- 짧은 스파이크 제거 (smoothing)

### 비교 지표
- Note-level F1 (pitch tolerance ±2 semitone, time tolerance)
- DTW (pitch contour similarity)
- Chroma similarity (pitch class 분포)

## 폴백 전략
- 보컬 분리 품질 저하 시: HPSS + pyin 또는 Basic Pitch + skyline
- pyin 정확도 부족 시: torchcrepe 추가 테스트

## 캐싱
- 분리된 보컬은 캐시 (곡당 2-5분 소요)
- 모델 + input hash로 키 관리

## 열린 질문
- (없음 - 모든 핵심 결정 완료)

## 범위
- INCLUDE: 보컬 분리, 멜로디 추출, 레퍼런스 비교, 8곡 테스트
- EXCLUDE: 난이도 조절, 화음/반주 생성, 유닛 테스트, Docker
