<!-- Generated: 2026-03-10 | Updated: 2026-03-10 -->

# piano-sheet-extractor

## Purpose
MP3 오디오 파일에서 보컬 멜로디를 추출하여 MusicXML(피아노 악보) 형식으로 저장하는 파이프라인. Demucs 보컬 분리 → FCPE/CREPE F0 추출 → 음표 세그먼테이션 → 자체 후처리 → MusicXML 저장 → 라운드트립 평가의 전체 흐름을 구현한다.

## Key Files

| File | Description |
|------|-------------|
| `requirements.txt` | Python 의존성 목록 (torch, librosa, music21, torchcrepe 등) |
| `PROJECT_DIRECTIVES.md` | **필수 참조** — 절대 명제 5가지 + 모든 실험 이력 (v1~v19) |
| `.gitignore` | Git 무시 파일 목록 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `core/` | 핵심 파이프라인 모듈 (see `core/AGENTS.md`) |
| `scripts/` | CLI 도구 및 평가 스크립트 (see `scripts/AGENTS.md`) |
| `test/` | 테스트 MP3 + MXL 참조 파일 8곡 (see `test/AGENTS.md`) |
| `output/` | 파이프라인 출력 MusicXML 파일 (see `output/AGENTS.md`) |
| `results/` | 실험 결과 JSON 파일 (see `results/AGENTS.md`) |

## For AI Agents

### 작업 시작 전 필수 사항
1. **`PROJECT_DIRECTIVES.md`를 먼저 읽을 것** — 절대 명제 5가지 준수 필수
2. Primary metric: `melody_f1_strict` (정확한 피치 + 50ms 온셋 허용오차)
3. 현재 baseline: mel_strict avg=0.091, mel_strict_oct=0.109, perceptual_score=0.537

### 절대 명제 (5개)
1. **MP3만으로** 멜로디 추출 — 참조 데이터 파이프라인 입력 금지
2. **참조는 분석용** — 과적합 금지
3. **모든 이력 기록** — PROJECT_DIRECTIVES.md에 실험 결과 반드시 문서화
4. **Output = Evaluation Identity** — MusicXML 라운드트립 평가 필수
5. **Tolerance vs Transformation** — 참조 기반 변환 금지

### 아키텍처 가드레일
- `core/pipeline.py`에 `ref_notes` 파라미터 절대 금지
- `core/postprocess.py`에 참조 데이터 입력 불가
- `scripts/evaluate.py`에서 time offset, octave correction 적용 금지
- 평가는 MusicXML 저장 → 로드 → 비교 순서 필수

### Testing Requirements
```bash
# 단일 곡 빠른 평가
python scripts/ablation_test.py --song "꿈의 버스" --mode fcpe

# 전체 8곡 평가
python scripts/evaluate.py --mode fcpe --output results/vNN.json

# 진단 분석
python scripts/diagnose.py
```

### Common Patterns
- 파이프라인 진입: `core/pipeline.py:extract_melody(mp3_path, ...)`
- 캐시 활용: `cache_dir=test/cache/` (보컬 분리 .npz 캐시)
- 평가 결과는 `results/` 하위에 버전 태그 포함 저장 (예: `results/v20.json`)

## Dependencies

### External
- `torch`, `torchaudio` — 딥러닝 백엔드
- `demucs` — 보컬/반주 분리
- `torchcrepe` — CREPE F0 추출
- `torchfcpe` — FCPE F0 추출
- `librosa` — 오디오 분석, 온셋 감지
- `music21` — MusicXML 파싱/생성
- `mir_eval` — 멜로디 평가 메트릭

<!-- MANUAL: 추가 메모는 이 줄 아래에 작성 -->
