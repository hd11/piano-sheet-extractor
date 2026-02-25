<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-02-25 | Updated: 2026-02-25 -->

# scripts

## Purpose
CLI 진입점 스크립트. 단일/배치 멜로디 추출과 테스트셋 평가 기능을 제공한다.

## Key Files

| File | Description |
|------|-------------|
| `extract_melody.py` | 멜로디 추출 CLI. 단일 MP3 또는 디렉토리 배치 처리 지원 |
| `evaluate.py` | 테스트셋 평가 스크립트. 참조 악보 대비 메트릭 계산 후 JSON 출력 |

## For AI Agents

### Working In This Directory
- 두 스크립트 모두 `core/` 패키지를 import하여 사용
- argparse 기반 CLI. `--input-dir`, `--output-dir`, `--output` 등 인자 사용
- 로깅과 타이밍 정보 출력 포함

### Usage Examples
```bash
# 단일 파일 추출
python scripts/extract_melody.py test/Golden.mp3 --output output/Golden.musicxml

# 배치 추출
python scripts/extract_melody.py --input-dir test --output-dir output

# 평가 실행
python scripts/evaluate.py --input-dir test --output results/eval_v1.json
```

### Testing Requirements
- `extract_melody.py` — 출력 .musicxml 파일이 유효한지 확인
- `evaluate.py` — JSON 출력에 5개 메트릭이 모두 포함되는지 확인
- 한국어 파일명 MP3가 정상 처리되는지 검증

### Common Patterns
- `core.extract_melody()` → `core.save_musicxml()` 순서로 호출
- 평가 시 `core.extract_reference_melody()` + `core.compare_melodies()` 조합
- 결과 JSON: 곡별 메트릭 + summary (평균값)

## Dependencies

### Internal
- `core/vocal_melody_extractor.py` — `extract_melody()`
- `core/musicxml_writer.py` — `save_musicxml()`
- `core/reference_extractor.py` — `extract_reference_melody()`
- `core/comparator.py` — `compare_melodies()`

### External
- **argparse** — CLI 인자 파싱 (stdlib)
- **json** — 결과 출력 (stdlib)
- **pathlib** — 경로 처리 (stdlib)

<!-- MANUAL: -->
