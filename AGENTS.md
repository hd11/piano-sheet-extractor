<!-- Generated: 2026-02-25 | Updated: 2026-02-25 -->

# piano-sheet-extractor

## Purpose
MP3 음악 파일에서 보컬 멜로디를 추출하여 MusicXML 악보로 변환하는 Python 오디오 처리 파이프라인. Demucs 신경망 보컬 분리와 torchcrepe F0 추출을 사용하며, K-pop 등 한국어 파일명을 지원한다.

## Key Files

| File | Description |
|------|-------------|
| `requirements.txt` | 핵심 의존성 (audio-separator, librosa, music21, mir_eval 등) |
| `requirements_backup.txt` | 전체 의존성 목록 (torch, demucs, torchcrepe 포함, 77개) |
| `test_pipeline.py` | 2곡(영문+한글 파일명) 빠른 검증 스크립트 |
| `HANDOFF_SUMMARY.md` | 프로젝트 상태 및 다음 단계 문서 |
| `.gitignore` | 캐시, 로그, 빌드 결과물 제외 규칙 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `core/` | 핵심 처리 모듈 - 보컬 분리, F0 추출, 노트 변환, MusicXML 생성 (see `core/AGENTS.md`) |
| `scripts/` | CLI 진입점 - 멜로디 추출 및 평가 스크립트 (see `scripts/AGENTS.md`) |
| `test/` | 테스트 데이터 - 8곡의 K-pop MP3 + MXL 참조 악보 (see `test/AGENTS.md`) |
| `results/` | 평가 결과 JSON 파일 (자동 생성, 39개 버전) |
| `output/` | 생성된 MusicXML 파일 출력 디렉토리 |

## For AI Agents

### Working In This Directory
- Python 3.11+ 환경 필요. `pip install -r requirements.txt`로 의존성 설치
- **Windows Demucs hang 이슈**: `import demucs`가 Windows에서 무한 대기. GPU/Linux/Mac에서 테스트 필요
- 한국어 파일명 처리 시 UUID 임시 파일 우회 패턴 사용 중 (vocal_separator.py 참고)
- MD5 기반 캐싱으로 5분+ 걸리는 Demucs 재처리 방지 (`test/cache/`)

### Pipeline Architecture
```
MP3 → Demucs 보컬 분리 (44.1kHz mono)
    → torchcrepe F0 추출 (16kHz, 10ms hop)
    → F0→MIDI 변환 + 노트 세그먼테이션 (20ms 최소 길이)
    → music21 MusicXML 생성 (16분음표 퀀타이즈)
    → .musicxml 파일 출력
```

### Testing Requirements
- `python test_pipeline.py` — 2곡 빠른 검증
- `python scripts/evaluate.py --input-dir test` — 8곡 전체 평가
- 주요 메트릭: `pitch_class_f1` (옥타브 무관 F1, 200ms 허용)

### Common Patterns
- `@dataclass`로 `Note(pitch, onset, duration, velocity)` 타입 정의
- 모든 모듈에 type hint와 docstring 적용
- 캐시 키로 MD5 해시 사용 (파일 내용 기반)
- 레거시 CQT 파이프라인(`melody_extractor.py`)은 롤백용으로 보존

## Dependencies

### External
- **torch** 2.10.0 — 딥러닝 프레임워크
- **demucs** 4.0.1 — 신경망 보컬 분리 (htdemucs_ft 모델)
- **torchcrepe** 0.0.24 — 신경망 F0 추출 (tiny 모델, 95% 정확도)
- **librosa** >= 0.10.0 — 오디오 신호 처리
- **music21** >= 9.1 — MusicXML 파싱/생성
- **mir_eval** >= 0.7 — 멜로디 평가 메트릭
- **numpy** >= 1.24 — 수치 연산

<!-- MANUAL: -->
