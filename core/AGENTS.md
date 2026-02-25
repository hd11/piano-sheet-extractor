<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-25 | Updated: 2026-02-25 -->

# core

## Purpose
멜로디 추출 파이프라인의 핵심 처리 모듈. 보컬 분리, F0 추출, 노트 세그먼테이션, MusicXML 생성, 참조 악보 파싱, 평가 메트릭을 담당한다.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | 패키지 exports — `extract_melody`, `save_musicxml`, `compare_melodies` 등 |
| `types.py` | `Note` dataclass 정의 (pitch, onset, duration, velocity) |
| `vocal_separator.py` | Demucs htdemucs_ft 모델 래퍼. MD5 캐싱, 한국어 파일명 UUID 우회 |
| `f0_extractor.py` | torchcrepe 기반 F0 추출 + `f0_to_notes()` 노트 세그먼테이션 |
| `vocal_melody_extractor.py` | 통합 파이프라인 진입점 — `extract_melody(mp3, cache_dir)` |
| `melody_extractor.py` | 레거시 CQT 파이프라인 (765줄, 롤백용 보존) |
| `musicxml_writer.py` | music21 기반 MusicXML 생성. 16분음표 퀀타이즈, 4/4 박자 |
| `reference_extractor.py` | .mxl 참조 악보에서 멜로디 추출. skyline 알고리즘 적용 |
| `comparator.py` | 5개 평가 메트릭 — pitch_class_f1, chroma, melody_f1, onset_f1 |

## For AI Agents

### Working In This Directory
- `vocal_melody_extractor.py`가 메인 진입점. 내부적으로 `vocal_separator` → `f0_extractor` 순서로 호출
- `melody_extractor.py`는 레거시 코드. 수정하지 말 것 (롤백 대비용)
- 모든 함수에 type hint 적용. `Note` 타입은 `types.py`에서 import
- 캐시 파일은 `{md5}_vocals_v1.npz` 형식으로 `cache_dir`에 저장

### Key Function Signatures
```python
# 통합 파이프라인
extract_melody(mp3_path: Path, cache_dir: Path = None) -> list[Note]

# 개별 단계
separate_vocals(mp3_path: Path, cache_dir: Path) -> tuple[np.ndarray, int]
extract_f0(vocals: np.ndarray, sr: int, hop_ms: int = 10) -> tuple[np.ndarray, np.ndarray]
f0_to_notes(f0: np.ndarray, periodicity: np.ndarray, hop_sec: float) -> list[Note]
save_musicxml(notes: list[Note], output_path: Path, title: str, bpm: int) -> Path
```

### Testing Requirements
- `python test_pipeline.py`로 통합 테스트 (루트에서 실행)
- 개별 모듈 테스트 시 `test/cache/`에 캐시된 보컬 데이터 활용 가능
- Windows에서 `vocal_separator.py` 테스트 불가 (Demucs hang 이슈)

### Common Patterns
- 오디오 데이터: numpy array (float32, -1~1 범위)
- 샘플레이트: Demucs 출력 44.1kHz → torchcrepe 입력 16kHz (내부 리샘플링)
- 피치: Hz (F0) ↔ MIDI number (0-127) 변환
- 시간: 초(seconds) 단위 통일

## Dependencies

### Internal
- `types.py` — 모든 모듈이 `Note` 클래스 import
- `vocal_separator.py` → `f0_extractor.py` → `vocal_melody_extractor.py` (파이프라인 순서)

### External
- **demucs** — 보컬 분리 (htdemucs_ft 모델)
- **torchcrepe** — F0 추출 (tiny 모델)
- **music21** — MusicXML 읽기/쓰기
- **librosa** — 오디오 로딩, 리샘플링
- **mir_eval** — 멜로디 평가 메트릭
- **scipy** — `find_peaks` (레거시 파이프라인)

<!-- MANUAL: -->
