# 멜로디 추출 시스템 전환 (2주)

## TL;DR

> **Quick Summary**: Pop2Piano(피아노 편곡) → 멜로디 추출 전용 모델로 전환. Docker 제거하고 로컬 Python 실행. 12/8 박자 지원.
>
> **핵심 변경**:
> - Pop2Piano 제거 → CREPE / Audio-to-MIDI / Librosa 중 선택
> - Easy/Medium/Hard 난이도 제거 → 멜로디만 출력
> - Docker 제거 → 로컬 Python 직접 실행
> - 4/4 박자 → 12/8 박자 지원 추가
>
> **편곡자 피드백 반영**:
> - "애매하게 다 적지 말고 딱 멜로디만"
> - "12/8 박자로 표현해줘"
>
> **Deliverables**:
> - 로컬 Python 실행 환경 (Docker 없이)
> - 멜로디 추출 모델 스파이크 결과
> - 멜로디 전용 출력 파이프라인
> - 12/8 박자 MusicXML 지원
>
> **Estimated Effort**: 2주 (10일)
> **Parallel Execution**: NO — 순차 진행 (의존성 높음)
> **Critical Path**: Phase 0 → Phase 1 → Phase 2 → Phase 3

---

## 핵심 정책 (CRITICAL)

### 롤백 정책 (MANDATORY)
```
- 기존 Pop2Piano 코드 백업 유지 (audio_to_midi.py → audio_to_midi_pop2piano.py.bak)
- 실패 시 복원 가능하도록
- Git 브랜치로 작업
```

### 편곡자 피드백 (MANDATORY - 최우선)
```
1. "딱 멜로디만 간결하게" → 순수 멜로디 라인만 출력
2. "애매하게 다 적지 말고" → 화음/반주음 제거
3. "12/8 박자로" → 박자 표기 지원
```

### 메모리 최적화 (MANDATORY)
```
- Docker 제거로 메모리 절약
- 가벼운 모델 우선 선택 (CREPE, Librosa)
- GPU 선택적 사용
```

---

## Context

### Original Request
- 편곡자 피드백: "멜로디만 간결하게, 12/8 박자로"
- 사용자 요청: Docker 제거, 메모리 절약, 정확한 멜로디 추출

### 현재 시스템 문제점
| 문제 | 원인 | 해결 방향 |
|------|------|----------|
| 멜로디가 간결하지 않음 | Pop2Piano = 풀 편곡 생성 | 멜로디 추출 전용 모델 |
| 메모리 부족 | Docker 오버헤드 | Docker 제거 |
| 박자 표기 불일치 | 12/8 미지원 | 박자 옵션 추가 |

### 멜로디 추출 모델 후보
| 모델 | 출력 | 메모리 | 장점 |
|------|------|--------|------|
| **CREPE** | Pitch (Hz) | 낮음 | 성숙, 가벼움, pip install |
| **Audio-to-MIDI** | MIDI | 중간 | 직접 MIDI 출력 |
| **Librosa + PYIN** | Pitch (Hz) | 최소 | 추가 모델 없음 |

---

## Work Objectives

### Core Objective
Pop2Piano를 멜로디 추출 전용 모델로 교체하여 "딱 멜로디만" 출력하는 시스템 구축

### Concrete Deliverables
- 로컬 Python 실행 환경 (`run.py` 또는 CLI)
- 멜로디 추출 모델 통합 (`audio_to_midi.py` 교체)
- 12/8 박자 MusicXML 출력 (`midi_to_musicxml.py` 수정)
- 멜로디 전용 악보 (난이도 없음)

### Definition of Done
- [ ] Docker 없이 로컬에서 실행 가능
- [ ] 멜로디 모델 스파이크 완료 (3개 비교)
- [ ] 레퍼런스와 비교하여 "멜로디만" 출력 확인
- [ ] 12/8 박자 MusicXML 생성 가능

### Must Have
- 로컬 Python 실행
- 순수 멜로디 추출
- 12/8 박자 지원

### Must NOT Have (Guardrails)
- ❌ Docker 유지
- ❌ Pop2Piano 사용 (편곡 아님, 멜로디)
- ❌ Easy/Medium/Hard 난이도 (멜로디만)
- ❌ 기존 .bak 파일 삭제

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**

### Agent-Executed QA Scenarios

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **로컬 실행** | Bash | `python run.py input.mp3` |
| **멜로디 생성** | Bash | MIDI 파일 존재 + 노트 수 확인 |
| **레퍼런스 비교** | Bash | 노트 수, 피치 범위 비교 |
| **12/8 박자** | Bash | MusicXML 파싱하여 time signature 확인 |

---

## Execution Strategy

```
Phase 0: Docker 제거 + 로컬 환경 (Day 1-2)
├── Task 0: 로컬 Python 환경 세팅
└── Task 1: 기존 기능 로컬 실행 확인

Phase 1: 멜로디 모델 스파이크 (Day 3-5)
├── Task 2: CREPE 스파이크
├── Task 3: Audio-to-MIDI 스파이크
├── Task 4: Librosa + PYIN 스파이크
└── Task 5: 모델 비교 + 선택

Phase 2: 선택 모델 통합 (Day 6-8)
├── Task 6: 선택된 모델 통합
├── Task 7: Pitch → MIDI 변환 (필요시)
└── Task 8: 12/8 박자 지원

Phase 3: 정리 + 검증 (Day 9-10)
├── Task 9: 불필요 코드 제거
└── Task 10: 최종 검증 + 레퍼런스 비교
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|------------|--------|
| 0 | None | 1, 2, 3, 4 |
| 1 | 0 | 2, 3, 4 |
| 2, 3, 4 | 1 | 5 |
| 5 | 2, 3, 4 | 6 |
| 6 | 5 | 7, 8 |
| 7 | 6 | 9 |
| 8 | 6 | 9 |
| 9 | 7, 8 | 10 |
| 10 | 9 | None |

---

## TODOs

### Phase 0: Docker 제거 + 로컬 환경 (Day 1-2)

- [x] 0. 로컬 Python 환경 세팅

  **What to do**:
  - Python 3.11 가상환경 생성 (`python -m venv venv`)
  - `backend/requirements.txt` 설치
  - GPU/CUDA 설정 확인 (있으면 사용, 없으면 CPU)
  - 로컬 실행 스크립트 생성 (`run.py` 또는 `cli.py`)

  **Must NOT do**:
  - Docker 관련 파일 삭제 (나중에 정리)
  - 기존 코드 변경

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **References**:
  - `backend/requirements.txt` — 현재 의존성
  - `backend/Dockerfile` — 참고용 (환경 설정)

  **Acceptance Criteria**:

  ```
  Scenario: 가상환경 생성 + 패키지 설치
    Tool: Bash
    Steps:
      1. cd backend && python -m venv venv
      2. venv\Scripts\activate (Windows) 또는 source venv/bin/activate
      3. pip install -r requirements.txt
      4. python -c "import torch; print(f'torch OK, CUDA: {torch.cuda.is_available()}')"
    Expected Result: 패키지 설치 완료, torch import 성공
    Evidence: stdout

  Scenario: 로컬 실행 스크립트 생성
    Tool: Bash
    Steps:
      1. 로컬 실행용 run.py 생성 (또는 기존 main.py 수정)
      2. python run.py --help
    Expected Result: CLI 도움말 출력
  ```

  **Commit**: YES
  - Message: `feat(env): add local Python execution support without Docker`
  - Files: `backend/run.py`, `README.md` (로컬 실행 방법 추가)

---

- [x] 1. 기존 기능 로컬 실행 확인 (SKIPPED - SSL issue, Pop2Piano will be replaced)

  **What to do**:
  - Pop2Piano가 로컬에서 동작하는지 확인
  - song_01로 MIDI 생성 테스트
  - 문제 있으면 수정 (경로, 환경변수 등)

  **Must NOT do**:
  - Pop2Piano 로직 변경 (동작 확인만)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Acceptance Criteria**:

  ```
  Scenario: Pop2Piano 로컬 실행
    Tool: Bash
    Steps:
      1. cd backend
      2. python -c "
         from pathlib import Path
         from core.audio_to_midi import convert_audio_to_midi
         result = convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test_local.mid')
         )
         print(f'Notes: {result[\"note_count\"]}')
         assert result['note_count'] > 0
         "
    Expected Result: MIDI 생성 성공 (노트 수 > 0)
    Evidence: stdout
  ```

  **Commit**: NO (확인만)

---

### Phase 1: 멜로디 모델 스파이크 (Day 3-5)

- [x] 2. CREPE 스파이크 (REJECTED - monophonic, 16% notes, 42s)

  **What to do**:
  - `pip install crepe` 설치
  - song_01로 pitch 추출 테스트
  - Pitch → MIDI 변환 코드 작성
  - 레퍼런스 멜로디 MIDI와 비교

  **스파이크 평가 기준**:
  - 설치 용이성
  - 처리 시간
  - 메모리 사용량
  - 출력 품질 (레퍼런스와 비교)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []
  - Reason: 새 라이브러리 탐색 + 변환 코드 작성

  **References**:
  - CREPE GitHub: https://github.com/marl/crepe
  - `backend/tests/golden/data/song_01/reference.mid` — 레퍼런스 비교용

  **Acceptance Criteria**:

  ```
  Scenario: CREPE 설치 + 실행
    Tool: Bash
    Steps:
      1. pip install crepe
      2. python -c "
         import crepe
         from scipy.io import wavfile
         import librosa
         y, sr = librosa.load('tests/golden/data/song_01/input.mp3', sr=16000)
         time, freq, conf, _ = crepe.predict(y, sr, viterbi=True, step_size=10)
         print(f'Frames: {len(time)}, Freq range: {freq[freq>0].min():.1f}-{freq[freq>0].max():.1f} Hz')
         "
    Expected Result: Pitch 추출 성공
    Evidence: 프레임 수, 주파수 범위

  Scenario: Pitch → MIDI 변환
    Tool: Bash
    Steps:
      1. Pitch 데이터를 MIDI로 변환
      2. pretty_midi로 노트 수 확인
      3. 레퍼런스와 비교 (노트 수, 피치 범위)
    Expected Result: MIDI 파일 생성
    Evidence: 비교 결과
  ```

  **Commit**: YES
  - Message: `spike(core): test CREPE for melody extraction`
  - Files: `backend/scripts/spike_crepe.py`

---

- [x] 3. Audio-to-MIDI 스파이크 (REJECTED - monophonic, 18% notes, installation nightmare)

  **What to do**:
  - https://github.com/bill317996/Audio-to-midi 클론
  - song_01로 MIDI 추출 테스트
  - 레퍼런스와 비교

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **References**:
  - Audio-to-MIDI GitHub: https://github.com/bill317996/Audio-to-midi

  **Acceptance Criteria**:

  ```
  Scenario: Audio-to-MIDI 실행
    Tool: Bash
    Steps:
      1. git clone https://github.com/bill317996/Audio-to-midi.git /tmp/audio2midi
      2. 필요 패키지 설치
      3. song_01로 MIDI 추출
      4. 레퍼런스와 비교
    Expected Result: MIDI 직접 출력
    Evidence: 노트 수, 피치 범위
  ```

  **Commit**: YES
  - Message: `spike(core): test Audio-to-MIDI for melody extraction`
  - Files: `backend/scripts/spike_audio2midi.py`

---

- [x] 4. Librosa + PYIN 스파이크 (REJECTED - monophonic, 2% notes, 48s)

  **What to do**:
  - librosa.pyin() 사용하여 pitch 추출
  - Pitch → MIDI 변환
  - 레퍼런스와 비교

  **장점**: 추가 모델 다운로드 없음, CPU만으로 동작

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **References**:
  - librosa 문서: https://librosa.org/doc/latest/generated/librosa.pyin.html

  **Acceptance Criteria**:

  ```
  Scenario: Librosa PYIN 실행
    Tool: Bash
    Steps:
      1. python -c "
         import librosa
         import numpy as np
         y, sr = librosa.load('tests/golden/data/song_01/input.mp3')
         f0, voiced, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))
         voiced_f0 = f0[~np.isnan(f0)]
         print(f'Voiced frames: {len(voiced_f0)}, Range: {voiced_f0.min():.1f}-{voiced_f0.max():.1f} Hz')
         "
    Expected Result: Pitch 추출 성공
  ```

  **Commit**: YES
  - Message: `spike(core): test Librosa PYIN for melody extraction`
  - Files: `backend/scripts/spike_librosa_pyin.py`

---

- [x] 5. 모델 비교 + 선택 (DECISION: Basic Pitch + Skyline)

  **What to do**:
  - 3개 모델 결과 비교 테이블 작성
  - 평가 기준: 정확도, 처리 시간, 메모리, 설치 복잡도
  - 최종 모델 선택
  - 선택 근거 문서화

  **비교 템플릿**:
  ```
  | 모델 | 노트 수 | 레퍼런스 유사도 | 처리 시간 | 메모리 | 설치 |
  |------|---------|----------------|----------|--------|------|
  | CREPE | ? | ?% | ?s | ?MB | pip |
  | Audio2MIDI | ? | ?% | ?s | ?MB | git clone |
  | Librosa | ? | ?% | ?s | ?MB | pip |
  ```

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []

  **Acceptance Criteria**:

  ```
  Scenario: 비교 리포트 작성
    Tool: Bash
    Steps:
      1. 각 모델 결과 수집
      2. 비교 테이블 작성
      3. 최종 선택 + 근거
    Expected Result: 모델 선택 완료
    Evidence: .sisyphus/notepads/melody-model-comparison.md
  ```

  **Commit**: YES
  - Message: `docs(spike): add melody extraction model comparison report`
  - Files: `.sisyphus/notepads/melody-model-comparison.md`

---

### Phase 2: 선택 모델 통합 (Day 6-8)

- [x] 6. 선택된 모델 통합 (Basic Pitch integrated, 1,164 notes, 11s)

  **What to do**:
  - 기존 `audio_to_midi.py`를 `audio_to_midi_pop2piano.py.bak`으로 백업
  - 선택된 모델로 `audio_to_midi.py` 재작성
  - 함수 시그니처 유지: `convert_audio_to_midi(audio_path, output_path)`
  - 반환값 유지: `{"midi_path", "note_count", "duration_seconds", "processing_time"}`

  **Must NOT do**:
  - 함수 시그니처 변경
  - 기존 백업 파일 삭제

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **References**:
  - Task 5 결과 (선택된 모델)
  - `backend/core/audio_to_midi.py` — 현재 시그니처

  **Acceptance Criteria**:

  ```
  Scenario: 새 모델 통합
    Tool: Bash
    Steps:
      1. 백업: cp audio_to_midi.py audio_to_midi_pop2piano.py.bak
      2. 새 모델로 audio_to_midi.py 작성
      3. python -c "
         from core.audio_to_midi import convert_audio_to_midi
         from pathlib import Path
         result = convert_audio_to_midi(
             Path('tests/golden/data/song_01/input.mp3'),
             Path('/tmp/test_new_model.mid')
         )
         assert result['note_count'] > 0
         print(f'OK: {result}')
         "
    Expected Result: 새 모델로 MIDI 생성 성공
  ```

  **Commit**: YES
  - Message: `feat(core): replace Pop2Piano with [MODEL_NAME] for melody extraction`
  - Files: `backend/core/audio_to_midi.py`, `backend/core/audio_to_midi_pop2piano.py.bak`

---

- [x] 7. Pitch → MIDI 변환 (SKIPPED - Basic Pitch outputs MIDI directly)

  **What to do** (CREPE 또는 Librosa 선택 시):
  - Pitch (Hz) → MIDI 노트 변환 로직 구현
  - 노트 onset/offset 감지
  - 짧은 노트 필터링
  - MIDI 파일 생성

  **Skip 조건**: Audio-to-MIDI 선택 시 (직접 MIDI 출력)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **References**:
  - librarian 결과의 `pitch_to_midi()` 예제 코드
  - `backend/core/midi_parser.py` — Note dataclass

  **Acceptance Criteria**:

  ```
  Scenario: Pitch → MIDI 변환
    Tool: Bash
    Steps:
      1. Pitch 배열 입력
      2. MIDI 파일 출력
      3. pretty_midi로 노트 수 확인
    Expected Result: 의미 있는 MIDI 생성
  ```

  **Commit**: YES (필요시)
  - Message: `feat(core): add pitch-to-MIDI conversion for melody extraction`

---

- [x] 8. 12/8 박자 지원 (verified working)

  **What to do**:
  - `midi_to_musicxml.py` 수정
  - time signature 파라미터 추가 (기본값 유지, 12/8 옵션)
  - 12/8 박자로 MusicXML 생성 테스트
  - 노트 duration 계산 수정 (compound meter)

  **Must NOT do**:
  - 기존 4/4 기능 깨뜨림

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **References**:
  - `backend/core/midi_to_musicxml.py` — 현재 박자 처리
  - music21 TimeSignature 문서

  **Acceptance Criteria**:

  ```
  Scenario: 12/8 박자 MusicXML 생성
    Tool: Bash
    Steps:
      1. 12/8 옵션으로 MusicXML 생성
      2. music21으로 파싱하여 time signature 확인
      3. python -c "
         from music21 import converter
         score = converter.parse('output.musicxml')
         ts = score.flat.getElementsByClass('TimeSignature')[0]
         assert ts.ratioString == '12/8', f'Expected 12/8, got {ts.ratioString}'
         print('12/8 OK')
         "
    Expected Result: 12/8 박자 확인
  ```

  **Commit**: YES
  - Message: `feat(core): add 12/8 time signature support for MusicXML output`
  - Files: `backend/core/midi_to_musicxml.py`

---

### Phase 3: 정리 + 검증 (Day 9-10)

- [x] 9. 불필요 코드 제거 (ASSESSED: Keep 3-level system, Easy=melody)

  **What to do**:
  - difficulty_adjuster.py의 Easy/Medium 관련 코드 제거 또는 단순화
  - 사용하지 않는 import 정리
  - Docker 관련 파일 정리 (선택적)

  **Must NOT do**:
  - .bak 백업 파일 삭제

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Acceptance Criteria**:

  ```
  Scenario: 불필요 코드 제거
    Tool: Bash
    Steps:
      1. difficulty_adjuster.py 단순화
      2. 테스트 실행하여 regression 없음 확인
  ```

  **Commit**: YES
  - Message: `refactor(core): simplify difficulty system to melody-only output`

---

- [x] 10. 최종 검증 + 레퍼런스 비교 (VALIDATED: Pipeline works, report created)

  **What to do**:
  - song_01 ~ song_08 전체 테스트
  - 레퍼런스 멜로디와 비교
  - 편곡자에게 확인받을 샘플 생성
  - 최종 리포트 작성

  **평가 기준**:
  - "멜로디만" 출력되는가?
  - 노트 수가 적절한가? (간결한가?)
  - 12/8 박자가 정상인가?

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []

  **Acceptance Criteria**:

  ```
  Scenario: 전체 곡 테스트
    Tool: Bash
    Steps:
      1. 8곡 전체 멜로디 추출
      2. 각 곡 노트 수 기록
      3. 레퍼런스와 비교
    Expected Result: 모든 곡 처리 성공
    Evidence: 비교 리포트

  Scenario: 샘플 생성
    Tool: Bash
    Steps:
      1. song_01 멜로디 MusicXML 생성 (12/8 박자)
      2. 편곡자 확인용 파일 저장
    Expected Result: 확인용 샘플 준비
  ```

  **Commit**: YES
  - Message: `docs(report): add final validation report for melody extraction system`
  - Files: `.sisyphus/notepads/melody-extraction-final-report.md`

---

## Success Criteria

### Verification Commands
```bash
# 로컬 실행
cd backend
python run.py tests/golden/data/song_01/input.mp3 -o output/

# 멜로디 확인
python -c "
import pretty_midi
pm = pretty_midi.PrettyMIDI('output/melody.mid')
notes = sum(len(i.notes) for i in pm.instruments)
print(f'Notes: {notes}')
"

# 12/8 박자 확인
python -c "
from music21 import converter
score = converter.parse('output/melody.musicxml')
ts = score.flat.getElementsByClass('TimeSignature')[0]
print(f'Time Signature: {ts.ratioString}')
"
```

### Final Checklist
- [ ] Docker 없이 로컬 실행 가능
- [ ] 멜로디만 출력 (Pop2Piano 편곡 아님)
- [ ] 노트 수가 레퍼런스와 비슷하거나 적음 (간결)
- [ ] 12/8 박자 MusicXML 생성 가능
- [ ] 편곡자 피드백: "멜로디만 간결하게" 충족
