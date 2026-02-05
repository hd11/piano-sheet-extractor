# Pop2Piano 기반 피아노 편곡 시스템 전면 업그레이드

## TL;DR

> **Quick Summary**: ByteDance(피아노 인식) → Pop2Piano(피아노 편곡 생성)로 모델 교체 + 비교 알고리즘 전면 개편 + MIDI 레퍼런스 골든 테스트 통합 + MusicXML 폴리포닉 지원
> 
> **Deliverables**:
> - Pop2Piano 통합 (`audio_to_midi.py` 교체)
> - 비교 알고리즘 전면 교체 (`musicxml_comparator.py` → mir_eval + DTW + 다중 메트릭)
> - MIDI 레퍼런스 골든 테스트 데이터 통합 (원본/쉬운/다장조)
> - MusicXML 폴리포닉 지원 (`midi_to_musicxml.py` 양손 악보)
> - 난이도 시스템 재설계 (`difficulty_adjuster.py`)
> - 복합 테스트 체계 (MXL + MIDI 동시 비교)
> - 8곡 전체 유사도 측정 리포트
> 
> **Estimated Effort**: Large (1-2주)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 2 → Task 5 → Task 6 → Task 8 → Task 9 → Task 10

---

## 핵심 정책 (CRITICAL - 모든 태스크에 적용)

### Git 커밋 정책 (MANDATORY)
```
모든 task 진행 시 변경사항 즉시 커밋 + 리모트 푸쉬
- 각 task 완료 시 반드시 커밋
- 커밋 메시지: conventional commits 형식
```

### 패러다임 이해 (MANDATORY - CRITICAL)
```
이 프로젝트는 "피아노 인식(Transcription)"이 아니라
"피아노 편곡 생성(Arrangement)"이다.

- ❌ "음원에서 피아노 소리만 추출" → 틀린 접근
- ✅ "전체 팝송을 피아노로 편곡" → 올바른 접근

Pop2Piano는 "편곡 생성" 모델 — 팝 오디오를 듣고 피아노 커버를 생성
ByteDance는 "피아노 인식" 모델 — 피아노 녹음을 듣고 노트를 인식
```

### 비교 메트릭 정책 (MANDATORY)
```
단일 노트 매칭 유사도만으로 평가하지 않는다.
복합 메트릭(멜로디 + 코드 + 리듬 + 구조)으로 다각도 평가.

편곡은 "정답이 하나"가 아니므로:
- 같은 곡을 두 피아니스트가 편곡하면 노트 단위 50-70% 다를 수 있음
- 하지만 둘 다 "좋은 편곡"일 수 있음
- 따라서 코드 진행, 멜로디 컨투어, 구조적 유사도 등 복합 평가 필수
```

### 롤백 정책 (MANDATORY)
```
Pop2Piano 통합 실패 시:
- 원본 audio_to_midi.py 백업에서 즉시 복원
- 롤백 기준: Pop2Piano가 MIDI 생성 자체를 실패하거나
  기존 대비 모든 메트릭에서 악화 시
```

---

## Context

### Original Request
- 팝송 오디오 → 피아노 편곡 악보 자동 생성 시스템 전면 업그레이드
- 공격적 접근: 모든 가능한 방법 시도
- MIDI 레퍼런스(원본/쉬운/다장조)도 골든 테스트에 포함

### 문제 진단
- 현재 ByteDance Piano Transcription은 "피아노 인식" 모델 → 팝 믹스에서 모든 소리를 피아노 노트로 변환 → 노이즈
- Pop2Piano는 "피아노 편곡 생성" 모델 → 정확히 이 프로젝트의 목적에 맞음
- Pop2Piano는 K-pop 데이터로 학습 → 테스트 곡(K-pop)과 도메인 일치
- 비교 알고리즘(greedy matching)이 정확도를 실제보다 5-15% 낮게 보고

### 현재 상태
- **현재 모델**: ByteDance Piano Transcription (piano_transcription_inference)
- **현재 유사도**: 평균 36.66% (melody similarity with pitch class)
- **현재 비교**: greedy O(n×m) matching, ONSET_TOLERANCE=3.0s
- **테스트 데이터**: 8곡 MP3 + MXL + MIDI(원본/쉬운/다장조)

### Metis Review
**Identified Gaps** (addressed):
- Pop2Piano의 출력 MIDI 구조 확인 필요 → Task 2에서 청감 평가 포함
- MIDI 레퍼런스의 정확한 구조(트랙, 채널) 분석 필요 → Task 1에 포함
- 기존 파이프라인(melody_extractor, difficulty_adjuster)과의 호환성 → Task 5-6에서 처리
- Pop2Piano composer 파라미터 최적화 필요 → Task 3에 포함
- 비교 메트릭에서 "좋은 편곡"의 정의 필요 → Task 4에서 복합 메트릭 설계

---

## Work Objectives

### Core Objective
Pop2Piano를 핵심 편곡 엔진으로 교체하고, MIDI 레퍼런스를 포함한 복합 테스트 체계를 구축하여 피아노 편곡 품질을 최대한 끌어올린다.

### Concrete Deliverables
- `backend/core/audio_to_midi.py` — Pop2Piano 기반으로 완전 교체
- `backend/core/musicxml_comparator.py` — mir_eval + DTW + 다중 메트릭
- `backend/core/midi_comparator.py` — MIDI 직접 비교 모듈 (신규)
- `backend/core/midi_to_musicxml.py` — 폴리포닉 양손 악보 지원
- `backend/core/difficulty_adjuster.py` — 폴리포닉 난이도 시스템
- `backend/tests/golden/data/song_XX/` — MIDI 레퍼런스 추가
- `backend/tests/golden/test_golden.py` — MIDI 비교 테스트 추가

### Definition of Done
- [ ] Pop2Piano가 8곡 모두 MIDI 생성 성공
- [ ] 복합 메트릭으로 8곡 유사도 측정 완료
- [ ] MIDI 레퍼런스(원본/쉬운/다장조) 골든 테스트에 통합
- [ ] 양손 피아노 MusicXML 악보 생성 성공
- [ ] 난이도별(easy/medium/hard) 출력이 레퍼런스 변형과 비교 가능

### Must Have
- Pop2Piano HuggingFace transformers 통합
- 함수 시그니처 유지 (`convert_audio_to_midi(audio_path, output_path)`)
- 기존 API 호환성 유지 (FastAPI 엔드포인트 변경 없음)
- 8곡 전부 MIDI 생성 가능
- MIDI 레퍼런스 골든 테스트 통합

### Must NOT Have (Guardrails)
- ❌ 소스 분리(Demucs)로 피아노만 추출하는 접근 금지 — 편곡 목적에 반함
- ❌ 기존 레퍼런스 MXL/MIDI 파일 수정 금지
- ❌ Frontend UI 변경 (별도 작업)
- ❌ Pop2Piano fine-tuning (데이터 부족)
- ❌ ByteDance 코드 삭제 금지 — .bak으로 백업 유지

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: 기존 golden test 확장
- **Framework**: pytest

### Agent-Executed QA Scenarios

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Pop2Piano MIDI 생성** | Bash | Python import + 단일 곡 MIDI 생성 |
| **MIDI 비교** | Bash | pytest 실행 + 유사도 수치 수집 |
| **MusicXML 생성** | Bash | 파일 존재 + music21 파싱 성공 |
| **골든 테스트** | Bash | `pytest -m golden` 실행 |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: MIDI 레퍼런스 골든 테스트 데이터 통합
├── Task 2: Pop2Piano 통합 (audio_to_midi.py 교체)
└── Task 3: Pop2Piano composer 스타일 탐색

Wave 2 (After Wave 1):
├── Task 4: 비교 알고리즘 전면 교체 (mir_eval + DTW)
├── Task 5: MusicXML 폴리포닉 지원
└── Task 6: 난이도 시스템 재설계

Wave 3 (After Wave 2):
├── Task 7: MIDI 직접 비교 모듈 구현
├── Task 8: 복합 골든 테스트 구현
└── Task 9: 8곡 전체 유사도 측정 + 리포트

Wave 4 (After Wave 3):
└── Task 10: 결과 평가 및 다음 단계 결정
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 7, 8 | 2, 3 |
| 2 | None | 3, 5, 6, 9 | 1 |
| 3 | 2 | 9 | 1 |
| 4 | None | 7, 8, 9 | 5, 6 |
| 5 | 2 | 8, 9 | 4, 6 |
| 6 | 2 | 8, 9 | 4, 5 |
| 7 | 1, 4 | 8 | - |
| 8 | 1, 4, 5, 6, 7 | 9 | - |
| 9 | 2, 3, 8 | 10 | - |
| 10 | 9 | None | - |

---

## TODOs

- [ ] 1. MIDI 레퍼런스 골든 테스트 데이터 통합

  **What to do**:
  - `test/` 폴더의 MIDI 파일들을 `backend/tests/golden/data/song_XX/`로 복사
  - 파일명 규칙: `reference.mid`, `reference_easy.mid`, `reference_cmajor.mid`
  - `metadata.json` 업데이트: MIDI 변형 정보 추가
  - MIDI 파일 구조 분석 (트랙 수, 채널, 노트 수, 키/BPM 등)

  **파일 매핑**:
  ```
  test/Golden.mid → backend/tests/golden/data/song_01/reference.mid
  test/Golden 쉬운.mid → backend/tests/golden/data/song_01/reference_easy.mid
  test/IRIS OUT.mid → backend/tests/golden/data/song_02/reference.mid
  test/IRIS OUT 쉬운.mid → backend/tests/golden/data/song_02/reference_easy.mid
  test/꿈의 버스.mid → backend/tests/golden/data/song_03/reference.mid
  test/꿈의 버스 쉬운.mid → backend/tests/golden/data/song_03/reference_easy.mid
  test/꿈의 버스 다장조.mid → backend/tests/golden/data/song_03/reference_cmajor.mid
  test/너에게100퍼센트.mid → backend/tests/golden/data/song_04/reference.mid
  test/너에게100퍼센트 쉬운.mid → backend/tests/golden/data/song_04/reference_easy.mid
  test/너에게100퍼센트 다장조.mid → backend/tests/golden/data/song_04/reference_cmajor.mid
  test/달리 표현할 수 없어요.mid → backend/tests/golden/data/song_05/reference.mid
  test/달리 표현할 수 없어요 쉬운.mid → backend/tests/golden/data/song_05/reference_easy.mid
  test/달리 표현할 수 없어요 다장조.mid → backend/tests/golden/data/song_05/reference_cmajor.mid
  test/등불을 지키다.mid → backend/tests/golden/data/song_06/reference.mid
  test/등불을 지키다 쉬운.mid → backend/tests/golden/data/song_06/reference_easy.mid
  test/등불을 지키다 다장조.mid → backend/tests/golden/data/song_06/reference_cmajor.mid
  test/비비드라라러브.mid → backend/tests/golden/data/song_07/reference.mid
  test/비비드라라러브 쉬운.mid → backend/tests/golden/data/song_07/reference_easy.mid
  test/여름이었다.mid → backend/tests/golden/data/song_08/reference.mid
  test/여름이었다 쉬운.mid → backend/tests/golden/data/song_08/reference_easy.mid
  test/여름이었다 다장조.mid → backend/tests/golden/data/song_08/reference_cmajor.mid
  ```

  - 각 MIDI 파일 구조 분석 리포트 생성 (pretty_midi로):
    * 트랙 수, 노트 수, 피치 범위, BPM, 총 길이
    * 원본 vs 쉬운 vs 다장조 차이점

  **Must NOT do**:
  - 원본 MIDI/MXL 파일 수정 금지
  - test/ 폴더의 원본 파일 삭제 금지 (복사만)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 파일 복사 + 간단한 분석 스크립트

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: None

  **References**:
  - `test/` 폴더 전체 파일 목록 (이 플랜의 Context 참고)
  - `backend/tests/golden/data/song_01/metadata.json` — 기존 메타데이터 형식
  - `backend/tests/golden/conftest.py` — 골든 테스트 fixture

  **Acceptance Criteria**:

  ```
  Scenario: MIDI 레퍼런스 파일 복사 확인
    Tool: Bash
    Steps:
      1. ls backend/tests/golden/data/song_01/reference.mid
      2. ls backend/tests/golden/data/song_01/reference_easy.mid
      3. ls backend/tests/golden/data/song_03/reference_cmajor.mid
      4. 모든 8곡에 reference.mid, reference_easy.mid 존재 확인
      5. 6곡에 reference_cmajor.mid 존재 확인
    Expected Result: 총 22개 MIDI 파일 존재
    Evidence: ls 출력

  Scenario: MIDI 파일 구조 분석
    Tool: Bash
    Steps:
      1. python -c "
         import pretty_midi
         pm = pretty_midi.PrettyMIDI('backend/tests/golden/data/song_01/reference.mid')
         print(f'Tracks: {len(pm.instruments)}, Notes: {sum(len(i.notes) for i in pm.instruments)}')
         "
      2. Assert: 트랙 수 >= 1, 노트 수 > 0
    Expected Result: 모든 MIDI 파일 정상 파싱
    Evidence: 분석 리포트 출력

  Scenario: metadata.json 업데이트 확인
    Tool: Bash
    Steps:
      1. python -c "import json; d=json.load(open('backend/tests/golden/data/song_03/metadata.json')); assert 'midi_variants' in d"
      2. Assert: midi_variants 키 존재
    Expected Result: 메타데이터에 MIDI 변형 정보 포함
    Evidence: JSON 출력
  ```

  **Commit**: YES
  - Message: `test(golden): add MIDI reference files (original, easy, cmajor variants)`
  - Files: `backend/tests/golden/data/song_*/reference*.mid`, `backend/tests/golden/data/song_*/metadata.json`

---

- [ ] 2. Pop2Piano 통합 (audio_to_midi.py 교체)

  **What to do**:
  - `backend/requirements.txt`에 `transformers`, `pop2piano` 관련 의존성 추가
  - 원본 `audio_to_midi.py` 백업 (`audio_to_midi_bytedance.py.bak`)
  - Pop2Piano HuggingFace 모델로 완전 교체
  - 함수 시그니처 및 반환 형식 유지
  - GPU/CPU 자동 선택 로직
  - 모델 캐시 로직 (singleton 패턴 유지)

  **구현 요구사항**:
  ```python
  # 유지해야 할 함수 시그니처
  def convert_audio_to_midi(audio_path: Path, output_path: Path) -> Dict[str, Any]:
      """
      Returns:
          {
              "midi_path": str,
              "note_count": int,
              "duration_seconds": float,
              "processing_time": float
          }
      """
  
  # Pop2Piano 사용 패턴
  from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor
  
  model = Pop2PianoForConditionalGeneration.from_pretrained("sweetcocoa/pop2piano")
  processor = Pop2PianoProcessor.from_pretrained("sweetcocoa/pop2piano")
  
  # 오디오 로딩 → processor → model.generate → decode → MIDI
  inputs = processor(audio=audio_array, sampling_rate=sr, return_tensors="pt")
  outputs = model.generate(input_features=inputs["input_features"], composer="composer1")
  midi_output = processor.batch_decode(token_ids=outputs, feature_extractor_output=inputs)
  midi_output["pretty_midi_objects"][0].write(str(output_path))
  ```

  - `composer` 파라미터는 기본값 사용, Task 3에서 최적화
  - 입력 검증 로직 유지 (파일 존재, 포맷 확인)
  - 출력 디렉토리 생성 유지

  **Must NOT do**:
  - 함수 시그니처 변경 금지
  - 반환 dict 키 변경 금지
  - ByteDance 코드 삭제 금지 (.bak으로 보관)
  - 기존 melody_extractor.py 수정 금지 (이 task에서는)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 새 모델 통합 + 기존 인터페이스 유지 + HuggingFace API 활용

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3 시작 가능하나 3은 2 완료 필요)
  - **Blocks**: Tasks 3, 5, 6, 9
  - **Blocked By**: None

  **References**:
  - `backend/core/audio_to_midi.py` — 현재 ByteDance 구현 (시그니처 참고)
  - HuggingFace Pop2Piano 문서: https://huggingface.co/docs/transformers/en/model_doc/pop2piano
  - GitHub: https://github.com/sweetcocoa/pop2piano
  - `backend/requirements.txt` — 현재 의존성 목록

  **Acceptance Criteria**:

  ```
  Scenario: Pop2Piano import 성공
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor
         print('Import OK')
         "
      2. Assert: "Import OK" 출력
    Expected Result: 라이브러리 정상 import
    Evidence: stdout

  Scenario: 단일 곡 MIDI 생성 (Smoke Test)
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from pathlib import Path
         from core.audio_to_midi import convert_audio_to_midi
         result = convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test_pop2piano.mid')
         )
         assert 'midi_path' in result
         assert 'note_count' in result
         assert result['note_count'] > 0
         print(f'Notes: {result[\"note_count\"]}, Time: {result[\"processing_time\"]:.1f}s')
         "
      2. Assert: exit code 0, note_count > 0
    Expected Result: Pop2Piano MIDI 생성 성공
    Evidence: stdout (노트 수, 처리 시간)

  Scenario: 함수 시그니처 유지 확인
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         import inspect
         from core.audio_to_midi import convert_audio_to_midi
         sig = inspect.signature(convert_audio_to_midi)
         params = list(sig.parameters.keys())
         assert params == ['audio_path', 'output_path'], f'Unexpected: {params}'
         print('Signature OK')
         "
      2. Assert: "Signature OK"
    Expected Result: 시그니처 변경 없음
    Evidence: stdout

  Scenario: 원본 백업 확인
    Tool: Bash
    Steps:
      1. ls backend/core/audio_to_midi_bytedance.py.bak
      2. Assert: 파일 존재
    Expected Result: ByteDance 백업 생성됨
    Evidence: ls 출력
  ```

  **Commit**: YES
  - Message: `feat(core): replace ByteDance with Pop2Piano for piano arrangement generation`
  - Files: `backend/core/audio_to_midi.py`, `backend/core/audio_to_midi_bytedance.py.bak`, `backend/requirements.txt`

---

- [ ] 3. Pop2Piano composer 스타일 탐색

  **What to do**:
  - Pop2Piano의 16+ composer 스타일을 1곡(song_01)에 대해 전부 생성
  - 각 스타일의 MIDI를 reference.mid와 비교
  - 레퍼런스 편곡 스타일에 가장 가까운 composer 식별
  - 최적 composer를 기본값으로 설정

  **Must NOT do**:
  - 8곡 전체를 모든 스타일로 생성 금지 (시간 과다) — 1-2곡만
  - 스타일 선택을 하드코딩 금지 — 설정 파일이나 파라미터로

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 여러 스타일 생성 + MIDI 비교 + 최적 선택

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Task 2

  **References**:
  - `backend/core/audio_to_midi.py` — Pop2Piano 통합 코드 (Task 2 결과)
  - `backend/tests/golden/data/song_01/reference.mid` — 비교 대상
  - Pop2Piano HuggingFace 문서: composer 파라미터 목록

  **Acceptance Criteria**:

  ```
  Scenario: 다중 스타일 MIDI 생성
    Tool: Bash
    Steps:
      1. 16+ composer 스타일로 song_01의 MIDI 각각 생성
      2. 각 MIDI의 노트 수, 피치 범위, 길이 비교
    Expected Result: 모든 스타일의 MIDI 파일 생성
    Evidence: 스타일별 MIDI 파일 + 비교 테이블

  Scenario: 최적 스타일 식별
    Tool: Bash
    Steps:
      1. 각 스타일 MIDI를 reference.mid와 비교 (노트 매칭)
      2. 가장 높은 유사도의 composer 식별
      3. 상위 3개 composer와 유사도 리포트
    Expected Result: 최적 composer 식별
    Evidence: .sisyphus/notepads/pop2piano-style-comparison.md
  ```

  **Commit**: YES
  - Message: `feat(core): optimize Pop2Piano composer style selection`
  - Files: `backend/core/audio_to_midi.py` (기본 composer 설정), `.sisyphus/notepads/`

---

- [ ] 4. 비교 알고리즘 전면 교체 (mir_eval + DTW + 다중 메트릭)

  **What to do**:
  - `backend/requirements.txt`에 `mir_eval`, `dtw-python` 추가
  - `backend/core/musicxml_comparator.py`를 전면 개편:
    * mir_eval 표준 메트릭 (precision, recall, F1)
    * DTW 기반 시간 정렬
    * Pitch class (옥타브 무시) 비교
    * Chroma 유사도
    * 코드 진행 비교
  - 복합 메트릭 점수 체계 도입
  - 기존 `compare_musicxml()`, `compare_note_lists()` API 유지 + 새 API 추가

  **복합 메트릭 설계**:
  ```python
  {
      "melody_f1": float,          # mir_eval onset+pitch F1
      "melody_f1_lenient": float,  # 넓은 tolerance (200ms)
      "pitch_class_f1": float,     # 옥타브 무시 F1
      "chroma_similarity": float,  # chroma 프로필 상관
      "onset_f1": float,           # onset만 비교 (pitch 무시)
      "structural_similarity": {
          "measure_count_match": bool,
          "key_match": bool,
          "time_sig_match": bool,
      },
      "composite_score": float,    # 가중 평균 종합 점수
  }
  ```

  **Must NOT do**:
  - 기존 `compare_musicxml()` 함수 삭제 금지 — 호환성 유지
  - mir_eval import 실패 시 graceful fallback 필수

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: mir_eval/DTW 통합 + 복합 메트릭 설계 + 기존 API 호환

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: Tasks 7, 8, 9
  - **Blocked By**: None (독립적으로 개발 가능, reference 데이터는 이미 존재)

  **References**:
  - `backend/core/musicxml_comparator.py` — 현재 비교 로직 (561줄)
  - mir_eval 문서: https://mir-evaluation.github.io/mir_eval/
  - `backend/core/midi_parser.py` — Note 데이터 구조

  **Acceptance Criteria**:

  ```
  Scenario: mir_eval import 성공
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "import mir_eval; print('OK')"
      2. Assert: "OK" 출력
    Expected Result: 라이브러리 정상
    Evidence: stdout

  Scenario: 기존 API 호환
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from core.musicxml_comparator import compare_musicxml
         result = compare_musicxml(
             'tests/golden/data/song_01/reference.mxl',
             'tests/golden/data/song_01/reference.mxl'  # self-compare
         )
         assert result['similarity'] > 0.99
         print(f'Self-similarity: {result[\"similarity\"]:.2%}')
         "
      2. Assert: self-similarity > 99%
    Expected Result: 기존 API 정상 동작
    Evidence: stdout

  Scenario: 복합 메트릭 출력 확인
    Tool: Bash
    Steps:
      1. 새 compare 함수로 song_01 reference.mxl 자기비교
      2. Assert: melody_f1, pitch_class_f1, chroma_similarity, composite_score 키 존재
    Expected Result: 복합 메트릭 모두 출력
    Evidence: stdout
  ```

  **Commit**: YES
  - Message: `feat(core): replace comparison algorithm with mir_eval + DTW + composite metrics`
  - Files: `backend/core/musicxml_comparator.py`, `backend/requirements.txt`

---

- [ ] 5. MusicXML 폴리포닉 양손 악보 지원

  **What to do**:
  - `backend/core/midi_to_musicxml.py` 수정:
    * Pop2Piano 출력 MIDI (폴리포닉) → 양손 피아노 악보
    * 높은음자리표 (RH: 보통 MIDI >= 60) + 낮은음자리표 (LH: MIDI < 60)
    * 2스태프 피아노 파트로 구성
  - 기존 모노포닉 모드도 유지 (fallback)

  **Must NOT do**:
  - 기존 단일 스태프 모드 제거 금지
  - RH/LH 분할 기준을 하드코딩하지 말 것 — 설정 가능하게

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: music21 활용 양손 악보 생성

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Task 2

  **References**:
  - `backend/core/midi_to_musicxml.py` — 현재 모노포닉 구현
  - `backend/tests/golden/data/song_01/reference.mxl` — 레퍼런스 구조 (2스태프)
  - music21 문서: Part, Staff, Clef

  **Acceptance Criteria**:

  ```
  Scenario: 양손 악보 생성
    Tool: Bash
    Steps:
      1. Pop2Piano로 song_01 MIDI 생성
      2. midi_to_musicxml로 MusicXML 변환
      3. music21으로 파싱하여 Part 수 확인
      4. Assert: 2개 Staff (높은음/낮은음 자리표)
    Expected Result: 양손 피아노 악보
    Evidence: Part/Staff 구조 출력
  ```

  **Commit**: YES
  - Message: `feat(core): add polyphonic two-hand piano score support in MusicXML`
  - Files: `backend/core/midi_to_musicxml.py`

---

- [ ] 6. 난이도 시스템 재설계

  **What to do**:
  - `backend/core/difficulty_adjuster.py` 수정:
    * **Easy**: 멜로디만 (RH skyline) — 레퍼런스의 "쉬운" MIDI와 비교 가능
    * **Medium**: 멜로디 + 간단한 코드 (RH + 간소화된 LH)
    * **Hard**: Pop2Piano 풀 편곡 그대로
  - Easy 추출 시 기존 `melody_extractor.py`의 skyline 알고리즘 활용 가능
  - 각 난이도의 MusicXML 파일 생성

  **Must NOT do**:
  - melody_extractor.py의 기존 로직 파괴 금지
  - 3단계 외 추가 난이도 금지 (scope 제한)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 편곡 간소화 로직 + 기존 모듈 재활용

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: Tasks 8, 9
  - **Blocked By**: Task 2

  **References**:
  - `backend/core/difficulty_adjuster.py` — 현재 난이도 시스템
  - `backend/core/melody_extractor.py` — Skyline 알고리즘
  - `backend/tests/golden/data/song_01/reference_easy.mid` — Easy 레퍼런스

  **Acceptance Criteria**:

  ```
  Scenario: 3단계 난이도 생성
    Tool: Bash
    Steps:
      1. Pop2Piano로 song_01 MIDI 생성
      2. generate_all_sheets() 호출
      3. sheet_easy.musicxml, sheet_medium.musicxml, sheet_hard.musicxml 존재 확인
      4. Easy의 노트 수 < Medium < Hard 확인
    Expected Result: 3단계 파일 생성, 노트 수 단계적
    Evidence: 각 파일의 노트 수 출력
  ```

  **Commit**: YES
  - Message: `feat(core): redesign difficulty system for polyphonic piano arrangement`
  - Files: `backend/core/difficulty_adjuster.py`

---

- [ ] 7. MIDI 직접 비교 모듈 구현

  **What to do**:
  - `backend/core/midi_comparator.py` 신규 생성:
    * MIDI 파일 간 직접 비교 (MusicXML 변환 없이)
    * pretty_midi 기반 노트 추출
    * mir_eval 메트릭 적용
    * DTW 정렬 적용
    * 복합 메트릭 출력 (Task 4와 동일 구조)
  - MXL 비교와 MIDI 비교 결과를 동시에 사용 가능하게

  **Must NOT do**:
  - MusicXML comparator와 코드 중복 최소화 — 공통 로직 분리

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: MIDI 파싱 + mir_eval 통합

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 1, 4

  **References**:
  - `backend/core/musicxml_comparator.py` — 비교 로직 패턴 (Task 4 결과)
  - `backend/core/midi_parser.py` — 기존 MIDI 파서
  - `backend/tests/golden/data/song_01/reference.mid` — MIDI 레퍼런스

  **Acceptance Criteria**:

  ```
  Scenario: MIDI 자기비교 (self-compare)
    Tool: Bash
    Steps:
      1. reference.mid를 자기 자신과 비교
      2. Assert: composite_score > 0.99
    Expected Result: 자기비교 ≈ 100%
    Evidence: stdout

  Scenario: 원본 vs 쉬운 비교
    Tool: Bash
    Steps:
      1. reference.mid vs reference_easy.mid 비교
      2. Assert: composite_score < 1.0 (다른 편곡이므로)
      3. Assert: melody_f1 > 0.5 (멜로디는 유사)
    Expected Result: 의미 있는 차이 측정
    Evidence: 비교 결과 출력
  ```

  **Commit**: YES
  - Message: `feat(core): add MIDI direct comparison module with mir_eval metrics`
  - Files: `backend/core/midi_comparator.py`

---

- [ ] 8. 복합 골든 테스트 구현

  **What to do**:
  - `backend/tests/golden/test_golden.py` 확장:
    * `TestMIDIComparison` 클래스 추가 — MIDI 레퍼런스와 비교
    * `TestEasyDifficulty` 클래스 추가 — Easy 출력 vs reference_easy.mid
    * `TestCMajorVariant` 클래스 추가 — 다장조 변형 비교 (해당 곡만)
    * `TestCompositeMetrics` 클래스 추가 — 복합 메트릭 리포트
  - Pop2Piano 출력을 모든 레퍼런스 타입(MXL + MIDI 원본/쉬운/다장조)과 비교
  - 각 비교의 복합 메트릭 수집 및 리포트 생성

  **테스트 매트릭스**:
  ```
  각 곡별:
  1. Pop2Piano MIDI 생성 (hard)
  2. Easy/Medium/Hard 난이도 MusicXML 생성
  3. 비교:
     a. generated_hard.musicxml vs reference.mxl (기존)
     b. generated_hard.mid vs reference.mid (MIDI 직접 비교)
     c. generated_easy.mid vs reference_easy.mid (Easy 비교)
     d. generated의 pitch class vs reference_cmajor.mid (해당 곡만)
  4. 복합 메트릭 수집
  ```

  **Must NOT do**:
  - 기존 TestGoldenSmoke, TestGoldenCompare, TestMelodyComparison 삭제 금지
  - 새 테스트가 기존 테스트를 깨뜨리면 안 됨

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 복합 테스트 설계 + 다중 비교 로직

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 1, 4, 5, 6, 7

  **References**:
  - `backend/tests/golden/test_golden.py` — 기존 테스트 (399줄)
  - `backend/tests/golden/conftest.py` — 테스트 fixture
  - `backend/core/midi_comparator.py` — MIDI 비교 (Task 7 결과)
  - `backend/core/musicxml_comparator.py` — MXL 비교 (Task 4 결과)

  **Acceptance Criteria**:

  ```
  Scenario: 전체 골든 테스트 실행
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -v --tb=short
      2. Assert: 기존 테스트 PASS 유지
      3. Assert: 새 MIDI 비교 테스트 실행됨
    Expected Result: 모든 테스트 실행 (일부 신규 테스트는 threshold 미달 가능)
    Evidence: pytest 출력

  Scenario: MIDI 비교 테스트 8곡 실행
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -m midi -v
      2. 각 곡별 composite_score 수집
    Expected Result: 8곡 모두 MIDI 비교 결과 출력
    Evidence: pytest 출력
  ```

  **Commit**: YES
  - Message: `test(golden): add comprehensive MIDI comparison tests with composite metrics`
  - Files: `backend/tests/golden/test_golden.py`

---

- [ ] 9. 8곡 전체 유사도 측정 + 리포트

  **What to do**:
  - Pop2Piano (최적 composer 스타일)로 8곡 전체 처리
  - 모든 비교 수행 (MXL, MIDI 원본, MIDI 쉬운, MIDI 다장조)
  - 상세 리포트 생성:
    * 곡별 복합 메트릭 테이블
    * 기존 ByteDance 대비 개선율
    * 메트릭별 분석 (어떤 부분이 강하고 약한지)
    * 다음 개선 방향 제안

  **Must NOT do**:
  - 결과 조작 금지
  - 실패해도 재시도 금지 (1회만 실행)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []
  - Reason: 테스트 실행 + 결과 수집 + 리포트 작성

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 3, 8

  **References**:
  - Task 3 결과 (최적 composer 스타일)
  - Task 8 결과 (복합 테스트)
  - `.sisyphus/session-summary.md` — 기존 기준선 데이터

  **Acceptance Criteria**:

  ```
  Scenario: 8곡 전체 측정
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/ -v --tb=short 2>&1 | tee results.txt
      2. 각 곡별 모든 메트릭 수집
      3. 평균 계산
    Expected Result: 8곡 모두 측정 완료
    Evidence: .sisyphus/notepads/pop2piano-results.md

  Scenario: 기존 대비 개선 확인
    Tool: Bash
    Steps:
      1. 기존 기준선 (ByteDance 평균 36.66%) 대비 비교
      2. 메트릭별 개선/악화 분석
    Expected Result: 상세 비교 리포트
    Evidence: .sisyphus/notepads/pop2piano-results.md
  ```

  **Commit**: YES
  - Message: `docs: add Pop2Piano comprehensive evaluation report for 8 songs`
  - Files: `.sisyphus/notepads/pop2piano-results.md`

---

- [ ] 10. 결과 평가 및 다음 단계 결정

  **What to do**:
  - Task 9 결과 기반 의사결정
  - 결정 매트릭스에 따라 다음 액션 결정
  - 사용자에게 결과 보고

  **결정 매트릭스**:
  | 상황 | 판정 | 다음 단계 |
  |------|------|-----------|
  | composite >= 70% | GREAT | 최적화 + UI 통합 진행 |
  | 50% <= composite < 70% | GOOD | 후처리 파이프라인 추가 (quantize, DTW 보정) |
  | 30% <= composite < 50% | MODERATE | 멀티스텝 보조 (Demucs 보컬 → 멜로디 보정) |
  | composite < 30% | POOR | 패러다임 전환 (PiCoGen2, 메트릭 재정의) |

  **Must NOT do**:
  - 사용자 승인 없이 다음 플랜 자동 생성 금지 (결과 보고만)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []
  - Reason: 분석 및 보고만

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: Task 9

  **References**:
  - Task 9 결과 리포트
  - `.sisyphus/plans/reference-matching-v2.md` — 원본 플랜

  **Acceptance Criteria**:

  ```
  Scenario: 결과 리포트 및 권장사항
    Tool: Agent
    Steps:
      1. 결과 분석
      2. 결정 매트릭스 적용
      3. 사용자에게 보고
    Expected Result: 명확한 결과 + 다음 단계 권장
    Evidence: 사용자 보고 메시지
  ```

  **Commit**: YES
  - Message: `docs: complete Pop2Piano upgrade evaluation and next steps`
  - Files: `.sisyphus/plans/pop2piano-upgrade.md` (상태 업데이트)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `test(golden): add MIDI reference files` | golden/data/*/reference*.mid | ls + pretty_midi 파싱 |
| 2 | `feat(core): replace ByteDance with Pop2Piano` | audio_to_midi.py, requirements.txt | 단일 곡 MIDI 생성 |
| 3 | `feat(core): optimize Pop2Piano composer style` | audio_to_midi.py, notepads/ | 스타일 비교 리포트 |
| 4 | `feat(core): replace comparison with mir_eval+DTW` | musicxml_comparator.py | self-compare 테스트 |
| 5 | `feat(core): add polyphonic two-hand MusicXML` | midi_to_musicxml.py | 2-staff 확인 |
| 6 | `feat(core): redesign difficulty system` | difficulty_adjuster.py | 3단계 노트 수 |
| 7 | `feat(core): add MIDI direct comparison` | midi_comparator.py | self-compare 테스트 |
| 8 | `test(golden): add comprehensive MIDI tests` | test_golden.py | pytest 실행 |
| 9 | `docs: Pop2Piano evaluation report` | notepads/ | 리포트 파일 |
| 10 | `docs: complete evaluation` | plans/ | 상태 업데이트 |

---

## Success Criteria

### Verification Commands
```bash
# 1. Pop2Piano MIDI 생성 확인
docker compose run --rm backend python -c "
from pathlib import Path
from core.audio_to_midi import convert_audio_to_midi
result = convert_audio_to_midi(Path('tests/golden/data/song_01/input.mp3'), Path('/tmp/t.mid'))
print(f'Notes: {result[\"note_count\"]}')
"
# Expected: Notes: N (N > 0)

# 2. 복합 메트릭 비교
docker compose run --rm backend python -c "
from core.musicxml_comparator import compare_musicxml_comprehensive
result = compare_musicxml_comprehensive('tests/golden/data/song_01/reference.mxl', '/tmp/sheet.musicxml')
print(f'Composite: {result[\"composite_score\"]:.2%}')
"
# Expected: Composite: XX% (수치 확인)

# 3. MIDI 직접 비교
docker compose run --rm backend python -c "
from core.midi_comparator import compare_midi
result = compare_midi('tests/golden/data/song_01/reference.mid', '/tmp/t.mid')
print(f'Composite: {result[\"composite_score\"]:.2%}')
"
# Expected: Composite: XX%

# 4. 전체 골든 테스트
docker compose run --rm backend pytest tests/golden/ -v
# Expected: 기존 + 신규 테스트 실행
```

### Final Checklist
- [ ] Pop2Piano 8곡 MIDI 생성 성공
- [ ] MIDI 레퍼런스 골든 테스트 통합 (22개 파일)
- [ ] 비교 알고리즘 mir_eval + DTW 교체
- [ ] 복합 메트릭 출력 (melody_f1, pitch_class_f1, chroma, composite)
- [ ] 양손 피아노 MusicXML 생성
- [ ] 3단계 난이도 생성 (Easy/Medium/Hard)
- [ ] MIDI 직접 비교 모듈
- [ ] 복합 골든 테스트 (MXL + MIDI 원본/쉬운/다장조)
- [ ] 8곡 전체 유사도 리포트
- [ ] 기존 ByteDance 대비 개선 확인
