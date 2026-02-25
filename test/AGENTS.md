<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-25 | Updated: 2026-02-25 -->

# test

## Purpose
평가용 테스트 데이터셋. 8곡의 K-pop MP3 파일과 대응하는 MXL(MusicXML) 참조 악보, MIDI 파일을 포함한다. 한국어 파일명 처리 검증도 겸한다.

## Key Files

| File | Description |
|------|-------------|
| `Golden.mp3` / `Golden.mxl` | 영문 파일명 참조 트랙 |
| `IRIS OUT.mp3` / `IRIS OUT.mxl` | 공백 포함 영문 파일명 트랙 |
| `꿈의 버스.mp3` / `꿈의 버스.mxl` | 한국어 파일명 참조 트랙 |
| `너에게100퍼센트.mp3` / `.mxl` | 한국어+숫자 혼합 파일명 |
| `달리 표현할 수 없어요.mp3` / `.mxl` | 한국어 공백 포함 파일명 |
| `등불을 지키다.mp3` / `.mxl` | 한국어 파일명 |
| `비비드라라러브.mp3` / `.mxl` | 한국어 파일명 |
| `여름이었다.mp3` / `.mxl` | 한국어 파일명 |
| `*.mid` | 각 곡의 MIDI 버전 |
| `*쉬운*.mxl` | 쉬운 편곡 버전 (simplified) |
| `*다장조*.mxl` | C장조 이조 버전 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `cache/` | MD5 기반 캐시 (~327MB). Demucs 보컬 분리 결과 등 저장. gitignore 대상 |

## For AI Agents

### Working In This Directory
- MP3 파일은 저작권 보호 음원. 외부 유출 금지
- .mxl 파일은 ground truth — 수동 채보된 참조 악보
- `cache/` 디렉토리는 자동 생성됨. 삭제해도 재생성 가능 (시간 소요)
- 새 테스트곡 추가 시 MP3 + MXL 쌍으로 추가해야 평가 가능

### Testing Requirements
- `test_pipeline.py`가 `Golden.mp3`와 `꿈의 버스.mp3` 2곡으로 빠른 검증
- `scripts/evaluate.py`가 전체 8곡 평가 수행
- 파일명에 한국어/공백/특수문자가 포함된 경우 정상 동작 확인 필수

### Baseline Metrics (Legacy CQT Pipeline)
| Song | pitch_class_f1 |
|------|---------------|
| Golden | 0.0249 |
| 꿈의 버스 | 0.0588 |
| 8곡 평균 | 0.0598 |

## Dependencies

### Internal
- `core/reference_extractor.py`가 .mxl 파일 파싱
- `core/vocal_separator.py`가 MP3 → 보컬 분리 후 cache/ 저장

### External
- 없음 (데이터 디렉토리)

<!-- MANUAL: -->
