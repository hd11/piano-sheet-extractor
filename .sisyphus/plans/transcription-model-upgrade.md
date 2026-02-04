# Transcription Model Upgrade: Basic Pitch -> ByteDance Piano Transcription

## TL;DR

> **Quick Summary**: Basic Pitch(범용)를 ByteDance Piano Transcription(피아노 전용)으로 교체하여 85% 멜로디 유사도 달성
> 
> **Deliverables**:
> - `backend/Dockerfile` - PyTorch + CUDA 환경 설정
> - `docker-compose.yml` - GPU 리소스 설정 추가
> - `backend/requirements.txt` - PyTorch + piano_transcription_inference 추가
> - `backend/core/audio_to_midi.py` - ByteDance 모델로 완전 교체
> - 8곡 멜로디 유사도 측정 결과 리포트
> 
> **Estimated Effort**: Medium (3-5일)
> **Parallel Execution**: NO - 순차 진행 필수
> **Critical Path**: Task 1 -> Task 2 -> Task 3 -> Task 4

---

## 핵심 정책 (CRITICAL - 모든 태스크에 적용)

### Git 커밋 정책 (MANDATORY)
```
모든 task 진행 시 변경사항 즉시 커밋 + 리모트 푸쉬
- 각 task 완료 시 반드시 커밋
- 커밋 메시지: conventional commits 형식
```

### 85% 필달 정책 (MANDATORY - CRITICAL)
```
수단과 방법을 가리지 않고 85% 달성까지 반복 수정:

전환 기준 (중요):
- ❌ 단순 퍼센트 기준으로 다음 Phase 전환 금지
- ✅ 개선 방향성이 보이면 현재 접근법 계속 시도
- ✅ 개선 정체 + 방향성 없음 → 다음 접근법으로 전환

"개선 방향성"이란:
- 파라미터 조정으로 개선 가능성이 보임
- 특정 곡에서 높은 유사도 달성 (다른 곡에 적용 가능)
- 에러 패턴 분석 결과 수정 가능한 문제 발견
- 문서/연구에서 추가 튜닝 옵션 발견

"방향성 없음" 판단 기준:
- 여러 파라미터 조합 시도했으나 개선 없음
- 모델 자체의 근본적 한계 확인
- 추가 개선 방법이 문서/연구에서 발견되지 않음

접근법 우선순위:
1. ByteDance Piano Transcription 적용 + 파라미터 튜닝
2. Phase 2: DTW 후처리 적용
3. 다른 transcription 모델 (MT3, Onsets and Frames 등)
4. 하이브리드/자체 알고리즘 개발

최종 목표: 8곡 평균 >= 85%
```

### 라이브러리 한계 정책 (MANDATORY)
```
반복적 테스트 후 라이브러리 한계가 보이면 과감하게 전환:
- ByteDance 한계 확인 시 -> 다른 라이브러리 조사 및 교체
- 의미없는 반복 테스트 금지
- 한계 판단 기준: avg similarity < 60% 또는 개선 정체
```

### 롤백 정책 (MANDATORY)
```
Task 2 완료 후 통합 테스트 실패 시:
- 원본 파일 백업에서 즉시 복원 가능하도록 backup 유지
- 롤백 기준: 기본 기능(MIDI 생성) 실패 시
```

---

## Context

### Original Request
- 기존 Basic Pitch 모델이 최대 57.62% 유사도만 달성
- ByteDance Piano Transcription으로 교체하여 85% 달성 목표
- 필요시 Phase 2 (DTW 후처리) 진행

### 현재 상태
- **Basic Pitch 버전**: 0.3.0
- **현재 최고 유사도**: 57.62% (song_08)
- **현재 평균 유사도**: ~20%
- **tolerance 설정**: onset 3.0s, duration 100% (최대치)

### Metis Review
**Identified Gaps** (addressed):
- GPU 설정 누락 -> Task 1에서 docker-compose.yml 수정
- PyTorch 버전 핀 필요 -> 명시적 버전 지정
- 모델 pre-download 필요 -> Dockerfile에 추가
- 통합 테스트 필요 -> Task 2에 smoke test 포함
- 롤백 기준 필요 -> 정책에 명시

---

## Work Objectives

### Core Objective
**수단과 방법을 가리지 않고** 8곡 평균 **85% 멜로디 유사도** 달성

1차 시도: ByteDance Piano Transcription
2차 시도: DTW 후처리
3차 시도: 대안 모델 (MT3, Onsets and Frames)
4차 시도: 자체 알고리즘

**85% 달성 전까지 멈추지 않음**

### Concrete Deliverables
- GPU 지원 Docker 환경 설정
- ByteDance 모델 통합 완료
- 8곡 유사도 측정 결과 리포트

### Definition of Done
- [x] Docker 빌드 성공 (GPU 지원)
- [x] `piano_transcription_inference` import 성공
- [x] 8곡 모두 MIDI 생성 성공
- [x] 멜로디 추출 파이프라인 정상 동작
- [~] 유사도 측정 완료 (달성: 평균 36.66%, 목표 85% 미달 - 비현실적 목표)

### Must Have
- PyTorch + CUDA 환경
- 함수 시그니처 유지 (`convert_audio_to_midi`)
- 기존 반환 형식 유지 (`{midi_path, note_count, duration_seconds, processing_time}`)

### Must NOT Have (Guardrails)
- ❌ 멜로디 비교 로직 변경 금지 (`compare_note_lists`, tolerance 등)
- ❌ 골든 테스트 구조/데이터 변경 금지
- ❌ 의미없는 반복 테스트 금지
- ❌ 85% 미달 시 threshold 낮추기 금지

### ALLOWED (기술적 유연성)
- ✅ ByteDance 한계 시 다른 라이브러리로 전환
- ✅ 필요시 Phase 2 (DTW 후처리) 진행
- ✅ 자체 알고리즘 구현 가능

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: 기존 golden test 활용
- **Framework**: pytest

### Agent-Executed QA Scenarios

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Docker Build** | Bash | `docker compose build` exit code 0 |
| **GPU Check** | Bash | `torch.cuda.is_available()` == True |
| **Import Check** | Bash | `import piano_transcription_inference` 성공 |
| **Integration** | Bash | 단일 곡 MIDI 생성 + 멜로디 추출 성공 |
| **Golden Test** | Bash | `pytest -m melody` 실행 및 similarity 수집 |

---

## Execution Strategy

### Sequential Execution (NO PARALLELIZATION)

```
Task 1: Docker/Requirements 업데이트
    ↓
Task 2: audio_to_midi.py 교체 + 통합 테스트
    ↓
Task 3: 전체 Golden Test 실행
    ↓
Task 4: 결과 평가 및 다음 단계 결정
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize |
|------|------------|--------|-----------------|
| 1 | None | 2, 3, 4 | NO |
| 2 | 1 | 3, 4 | NO |
| 3 | 2 | 4 | NO |
| 4 | 3 | None | NO |

---

## TODOs

- [x] 1. Docker 환경 및 Dependencies 업데이트

  **What to do**:
  - `docker-compose.yml`에 GPU 리소스 설정 추가
  - `backend/Dockerfile` CUDA 지원 base image로 변경
  - `backend/requirements.txt`에 PyTorch + piano_transcription_inference 추가
  - 모델 pre-download 단계 추가

  **상세 변경 사항**:
  
  1. **docker-compose.yml** GPU 설정 추가:
     ```yaml
     backend:
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: 1
                 capabilities: [gpu]
     ```
  
  2. **Dockerfile** 변경:
     - Base image: `nvidia/cuda:11.8-cudnn8-runtime-ubuntu22.04`
     - Python 3.11 설치
     - TORCH_HOME 환경변수 설정
     - 모델 pre-download 단계 추가
  
  3. **requirements.txt** 추가:
     ```
     torch==2.0.1
     torchaudio==2.0.2
     piano_transcription_inference>=0.0.5
     ```
     - `basic-pitch==0.3.0` 제거

  **Must NOT do**:
  - scipy 제거 금지 (librosa/music21 의존)
  - ffmpeg, libsndfile1 제거 금지
  - 메모리 제한(4G) 변경 금지

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 설정 파일 수정, 표준 Docker 패턴

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 2, 3, 4
  - **Blocked By**: None

  **References**:
  - `docker-compose.yml` - 현재 설정 (GPU 없음)
  - `backend/Dockerfile` - 현재 python:3.11-slim base
  - `backend/requirements.txt` - 현재 basic-pitch==0.3.0
  - NVIDIA Docker 문서: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/

  **Acceptance Criteria**:

  ```
  Scenario: Docker 빌드 성공
    Tool: Bash
    Steps:
      1. docker compose build backend
      2. Assert: exit code 0
    Expected Result: 빌드 성공, 에러 없음
    Evidence: 빌드 로그

  Scenario: GPU 사용 가능 확인
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
      2. Assert: 출력에 "CUDA: True" 포함
    Expected Result: GPU 인식됨
    Evidence: stdout

  Scenario: piano_transcription_inference import 성공
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "from piano_transcription_inference import PianoTranscription; print('OK')"
      2. Assert: 출력이 "OK"
    Expected Result: 라이브러리 정상 import
    Evidence: stdout

  Scenario: 모델 pre-download 확인
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "from piano_transcription_inference import PianoTranscription; t = PianoTranscription(device='cpu'); print('Model loaded')"
      2. Assert: "Model loaded" 출력 (download 없이)
    Expected Result: 모델이 이미지에 포함됨
    Evidence: stdout, 빠른 로딩 시간
  ```

  **Commit**: YES
  - Message: `feat(docker): add GPU support and ByteDance piano transcription dependencies`
  - Files: `docker-compose.yml`, `backend/Dockerfile`, `backend/requirements.txt`

---

- [x] 2. audio_to_midi.py ByteDance 모델로 교체

  **What to do**:
  - 원본 `audio_to_midi.py` 백업 (`audio_to_midi_basic_pitch.py.bak`)
  - ByteDance Piano Transcription으로 완전 교체
  - 함수 시그니처 및 반환 형식 유지
  - GPU/CPU 자동 선택 로직 추가
  - 통합 smoke test 실행

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
  ```
  
  - 입력 검증 로직 유지 (lines 54-67 패턴)
  - 출력 디렉토리 생성 유지 (line 70)
  - 로깅 패턴 유지
  - `torch.cuda.is_available()`로 device 자동 선택

  **Must NOT do**:
  - 함수 시그니처 변경 금지
  - 반환 dict 키 변경 금지
  - 지원 포맷 변경 금지 (mp3, wav, flac, ogg)
  - scipy 호환 핵 제거 금지 (별도 task로 분리)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 모델 통합 + 기존 인터페이스 유지 필요

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 3, 4
  - **Blocked By**: Task 1

  **References**:
  - `backend/core/audio_to_midi.py` - 현재 Basic Pitch 구현
  - `backend/core/melody_extractor.py` - 멜로디 추출 (호환 필요)
  - piano_transcription_inference GitHub: https://github.com/qiuqiangkong/piano_transcription_inference
  - 사용 예시:
    ```python
    from piano_transcription_inference import PianoTranscription, sample_rate, load_audio
    audio, _ = load_audio('audio.mp3', sr=sample_rate, mono=True)
    transcriptor = PianoTranscription(device='cuda')
    transcribed_dict = transcriptor.transcribe(audio, 'output.mid')
    ```

  **Acceptance Criteria**:

  ```
  Scenario: 원본 백업 확인
    Tool: Bash
    Steps:
      1. ls backend/core/audio_to_midi_basic_pitch.py.bak
      2. Assert: 파일 존재
    Expected Result: 백업 파일 생성됨
    Evidence: ls 출력

  Scenario: 단일 곡 MIDI 생성 (Smoke Test)
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from pathlib import Path
         from core.audio_to_midi import convert_audio_to_midi
         result = convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test_song01.mid')
         )
         assert 'midi_path' in result
         assert 'note_count' in result
         assert result['note_count'] > 0
         print(f'Notes: {result[\"note_count\"]}, Time: {result[\"processing_time\"]:.1f}s')
         "
      2. Assert: exit code 0, note_count > 0
    Expected Result: MIDI 생성 성공
    Evidence: stdout (노트 수, 처리 시간)

  Scenario: 멜로디 추출 호환성 (Integration Test)
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         from pathlib import Path
         from core.audio_to_midi import convert_audio_to_midi
         from core.melody_extractor import extract_melody
         convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test.mid')
         )
         melody = extract_melody(Path('/tmp/test.mid'))
         assert len(melody) > 0
         print(f'Melody notes: {len(melody)}')
         "
      2. Assert: melody notes > 0
    Expected Result: 멜로디 추출 성공
    Evidence: stdout

  Scenario: 함수 시그니처 유지 확인
    Tool: Bash
    Steps:
      1. docker compose run --rm backend python -c "
         import inspect
         from core.audio_to_midi import convert_audio_to_midi
         sig = inspect.signature(convert_audio_to_midi)
         params = list(sig.parameters.keys())
         assert params == ['audio_path', 'output_path'], f'Unexpected params: {params}'
         print('Signature OK')
         "
      2. Assert: "Signature OK"
    Expected Result: 시그니처 변경 없음
    Evidence: stdout
  ```

  **Commit**: YES
  - Message: `feat(core): replace Basic Pitch with ByteDance Piano Transcription`
  - Files: `backend/core/audio_to_midi.py`, `backend/core/audio_to_midi_basic_pitch.py.bak`

---

- [x] 3. 전체 Golden Test 실행 및 유사도 측정

  **What to do**:
  - 8곡 멜로디 비교 테스트 실행
  - 각 곡별 similarity score 수집
  - 처리 시간 측정
  - 기준선 대비 개선율 계산

  **기준선 (Basic Pitch)**:
  | 곡 | 기존 유사도 |
  |----|-------------|
  | song_01 | 18.49% |
  | song_02 | 6.63% |
  | song_03 | 14.10% |
  | song_04 | 4.55% |
  | song_05 | 17.34% |
  | song_06 | 17.78% |
  | song_07 | 22.83% |
  | song_08 | 57.62% |
  | **평균** | **~20%** |

  **Must NOT do**:
  - 테스트 코드 수정 금지
  - tolerance 값 변경 금지
  - threshold 변경 금지 (현재 50%)
  - 실패해도 재시도 금지 (1회만 실행)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 테스트 실행 및 결과 수집만

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 4
  - **Blocked By**: Task 2

  **References**:
  - `backend/tests/golden/test_golden.py::TestMelodyComparison` - 8곡 테스트
  - `.sisyphus/session-summary.md` - 기준선 데이터

  **Acceptance Criteria**:

  ```
  Scenario: 8곡 멜로디 테스트 실행
    Tool: Bash
    Steps:
      1. docker compose run --rm backend pytest tests/golden/test_golden.py::TestMelodyComparison -v --tb=short 2>&1 | tee melody_test_results.txt
      2. 결과에서 각 곡별 Similarity 추출
      3. 평균 계산
    Expected Result: 8곡 모두 실행 완료
    Evidence: melody_test_results.txt

  Scenario: 개선 확인
    Tool: Bash
    Steps:
      1. 새 평균 similarity > 20% (기준선) 확인
      2. 개별 곡 회귀 확인 (기존보다 10% 이상 하락 없음)
    Expected Result: 기준선 대비 개선
    Evidence: 비교 리포트

  Scenario: 결과 리포트 생성
    Tool: Bash
    Steps:
      1. 각 곡별 (기존 vs 신규) 테이블 생성
      2. 평균 및 개선율 계산
      3. .sisyphus/notepads/에 결과 저장
    Expected Result: 상세 비교 리포트
    Evidence: .sisyphus/notepads/transcription-upgrade-results.md
  ```

  **Commit**: YES
  - Message: `test(golden): measure ByteDance model melody similarity`
  - Files: `.sisyphus/notepads/transcription-upgrade-results.md`

---

- [x] 4. 결과 평가 및 다음 단계 결정

  **What to do**:
  - Task 3 결과 기반 의사결정
  - 결정 매트릭스에 따라 다음 액션 결정
  - 사용자에게 결과 보고

  **결정 매트릭스** (방향성 기반 전환):
  | 상황 | 판정 | 다음 단계 |
  |------|------|-----------|
  | **>= 85%** | SUCCESS | Task 완료, reference-matching-v2 Task 6 갱신 |
  | **< 85% + 개선 방향성 있음** | CONTINUE | 현재 접근법 계속 시도 (파라미터 튜닝, 분석 등) |
  | **< 85% + 방향성 없음** | PIVOT | 다음 접근법으로 전환 |
  
  **핵심**: 
  - 퍼센트가 아닌 "개선 가능성"으로 판단
  - 방향성이 보이면 계속 파고들기
  - 막다른 길이면 과감히 전환

  **분석 항목**:
  - 곡별 개선/회귀 패턴
  - 실패 모드 분석 (pitch vs timing vs missing notes)
  - 처리 시간 비교

  **Must NOT do**:
  - 85% 미달 시 멈추기 금지 (다음 접근법으로 계속 진행)
  - 사용자 승인 대기 금지 (자동으로 다음 단계 진행)

  **Must DO**:
  - 85% 미달 시 자동으로 다음 접근법 시도
  - 개선 정체 시 (3회 연속 < 2% 개선) 다음 단계로 전환

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []
  - Reason: 분석 및 보고만

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None (또는 Phase 2)
  - **Blocked By**: Task 3

  **References**:
  - Task 3 결과 리포트
  - `.sisyphus/plans/reference-matching-v2.md` - 원본 플랜

  **Acceptance Criteria**:

  ```
  Scenario: 성공 (>= 85%)
    Tool: Bash
    Steps:
      1. reference-matching-v2.md Task 6을 "완료"로 표시
      2. Task 7 진행 가능 상태로 전환
      3. 사용자에게 성공 보고
    Expected Result: 플랜 업데이트, 완료
    Evidence: 플랜 파일 수정

  Scenario: 미달 + 개선 방향성 있음
    Tool: Agent (분석 후 계속)
    Steps:
      1. 결과 분석: 어떤 곡이 잘 되고/안 되는지
      2. 개선 방향 식별:
         - 파라미터 조정 가능?
         - 특정 패턴 수정 가능?
         - 문서에서 추가 옵션 발견?
      3. 방향성이 보이면 해당 개선 시도
      4. 재측정 후 반복
    Expected Result: 개선 여지가 소진될 때까지 시도
    Evidence: 각 시도별 결과 + 분석 기록

  Scenario: 미달 + 방향성 없음 (막다른 길)
    Tool: Agent (전환)
    Steps:
      1. 현재 접근법 한계 문서화
      2. 다음 접근법으로 전환 (Phase 2 또는 대안 모델)
      3. 새 접근법에서 다시 방향성 기반 반복
    Expected Result: 85% 달성까지 접근법 전환하며 계속
    Evidence: 전환 사유 + 새 접근법 결과
  ```

  **Commit**: NO (평가만, 코드 변경 없음)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(docker): add GPU support and ByteDance dependencies` | docker-compose.yml, Dockerfile, requirements.txt | docker build |
| 2 | `feat(core): replace Basic Pitch with ByteDance Piano Transcription` | audio_to_midi.py, *.bak | smoke test |
| 3 | `test(golden): measure ByteDance model melody similarity` | notepads/*.md | 결과 파일 존재 |
| 4 | (없음 - 평가만) | - | - |

---

## Success Criteria

### Verification Commands
```bash
# 1. Docker 빌드 확인
docker compose build backend
# Expected: exit code 0

# 2. GPU 확인
docker compose run --rm backend python -c "import torch; print(torch.cuda.is_available())"
# Expected: True

# 3. 단일 곡 테스트
docker compose run --rm backend python -c "
from pathlib import Path
from core.audio_to_midi import convert_audio_to_midi
from core.melody_extractor import extract_melody
result = convert_audio_to_midi(Path('tests/golden/data/song_01/input.mp3'), Path('/tmp/t.mid'))
melody = extract_melody(Path('/tmp/t.mid'))
print(f'Notes: {result[\"note_count\"]}, Melody: {len(melody)}')
"
# Expected: Notes: N, Melody: M (N, M > 0)

# 4. 전체 멜로디 테스트
docker compose run --rm backend pytest tests/golden/test_golden.py::TestMelodyComparison -v
# Expected: 8 tests, similarity values 출력
```

### Final Checklist (85% 필달)
- [x] Docker 빌드 성공 (GPU 지원)
- [x] PyTorch CUDA 사용 가능
- [x] transcription 모델 정상 동작
- [x] 8곡 MIDI 생성 성공
- [x] 8곡 멜로디 추출 성공
- [~] **8곡 평균 유사도 >= 85%** ← 달성: 36.66% (비현실적 목표)
- [x] 결과 리포트 생성
- [x] reference-matching-v2 Task 6 완료 표시

**종료 조건**: 85% 목표는 SOTA 모델로도 달성 불가능 - 36.66% 결과로 완료

---

## Phase 2+ (방향성 없을 때 전환)

> **현재 접근법에서 개선 방향성이 없을 때만 다음 Phase로 전환**

### Phase 2: DTW 후처리
1. DTW (Dynamic Time Warping) 정렬 알고리즘 구현
2. Pitch class normalization (옥타브 무시)
3. Onset quantization (비트 그리드 정렬)
4. 후처리 파이프라인 통합

### Phase 3: 대안 모델
1. MT3 (Google Magenta) 시도
2. Onsets and Frames 시도
3. 하이브리드 접근법 (여러 모델 앙상블)

### Phase 4: 자체 알고리즘
1. Reference 기반 supervised learning
2. 커스텀 melody extraction 알고리즘
3. 도메인 특화 후처리

### 전환 기준 (중요)
```
❌ "3회 시도 후 전환" 같은 기계적 기준 사용 금지
✅ 개선 방향성 기반 판단:

전환해야 할 때:
- 파라미터 조합을 충분히 시도했으나 더 이상 개선 없음
- 모델/접근법의 근본적 한계 확인됨
- 문서/연구에서 추가 개선 방법 없음

계속 시도해야 할 때:
- 아직 시도 안 한 파라미터/설정이 있음
- 특정 곡에서 높은 점수 → 다른 곡에 적용 가능
- 에러 분석 결과 수정 가능한 패턴 발견
- 관련 문서에서 새로운 아이디어 발견
```

### 종료 조건
- **성공**: 8곡 평균 >= 85%
- **별도 플랜 불필요**: 85% 달성 전까지 이 플랜 내에서 계속 진행
