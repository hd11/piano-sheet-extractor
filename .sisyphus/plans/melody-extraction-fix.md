# 멜로디 추출 수정 계획

## TL;DR

> **Quick Summary**: 현재 Skyline 알고리즘이 "가장 높은 음 = 멜로디"로 가정해서 완전히 틀린 멜로디를 추출함. Essentia/Melodia (WSL 경유)를 **오디오 단계에서** 적용하여 멜로디 라인을 직접 추출하고, 실패 시 Hybrid Scoring으로 폴백.
> 
> **핵심 설계 결정**:
> - Essentia는 **오디오 → 멜로디 MIDI** 단계로 동작 (Basic Pitch와 병렬)
> - 기존 `extract_melody(midi_path)` 시그니처 유지 (MIDI 기반 파이프라인)
> - 새 진입점: `extract_melody_with_audio(audio_path, midi_path)` 추가
> - 골든 테스트 지표: 기존 `pitch_class_similarity` 유지 (현재 테스트 인프라 활용)
>
> **Deliverables**:
> - WSL용 Essentia 멜로디 추출 스크립트 (`essentia_melody_extractor.py`)
> - 새 함수 `extract_melody_with_audio()` in `melody_extractor.py`
> - 스파이크 테스트 결과 (Essentia vs Skyline)
> - 골든 테스트 통과 (pitch_class_similarity ≥ 0.50)
> 
> **Estimated Effort**: Medium (2-3일)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: WSL 설정 → Essentia 스파이크 → 통합 → 검증

---

## Context

### Original Request
편곡자 피드백: "멜로디라인이 없다" - 추출된 멜로디가 완전히 엉뚱함. 코드 음과 화성음이 나오고 실제 멜로디가 아님.

### Interview Summary
**Key Discussions**:
- **접근 방식**: Essentia/Melodia via WSL (Windows에서 Python 바인딩 미지원)
- **폴백**: Hybrid Scoring (순수 Python) - Essentia 실패 시
- **허용 기준**: pitch_class_similarity ≥ 0.50 (현재 골든 테스트 지표 활용)
- **테스트 전략**: 스파이크 + 골든 테스트만 (단위 테스트 없음)

**Research Findings**:
- Essentia `PredominantPitchMelodia`: 폴리포닉 오디오에서 주요 멜로디 추출 설계됨
- Windows에서 WSL2 필요 (네이티브 Python 바인딩 미지원)
- 현재 구현: 5단계 파이프라인 (Parse → Skyline → Filter → Resolve → Normalize)
- **현재 `extract_melody(midi_path)` 시그니처**: MIDI 경로만 받음 (오디오 접근 불가)
- **현재 골든 테스트**: `compare_note_lists_with_pitch_class()` 사용, `MELODY_SIMILARITY_THRESHOLD = 0.50`
- 기존 비교 도구: `midi_comparator.py`, `comparison_utils.py` (composite metrics)

### 아키텍처 결정 (Momus 리뷰 반영)
**Essentia 통합 위치**:
- Essentia는 **오디오**에서 멜로디를 추출 → 기존 MIDI 파이프라인과 별도 경로
- **새 함수**: `extract_melody_with_audio(audio_path, midi_path)` 추가
- **기존 함수**: `extract_melody(midi_path)` 시그니처 유지 (하위 호환성)
- **호출 흐름**: 골든 테스트에서 오디오 경로 + MIDI 경로 모두 전달

**인터페이스 정의**:
- `essentia_melody_extractor.py` (WSL): 오디오 경로 → stdout으로 JSON 출력 `[{pitch, onset, duration}, ...]`
- `extract_melody_with_audio()`: WSL subprocess 호출 → JSON 파싱 → Note 리스트 반환

### Metis Review
**Identified Gaps** (addressed):
- **메트릭 정의**: `pitch_class_similarity` ≥ 0.50 (현재 골든 테스트 지표 그대로 사용)
- **아키텍처 위치**: Essentia는 **오디오 단계에서 별도 경로**로 동작 (Skyline은 폴백으로 유지)
- **임계값 적용**: 기존 골든 테스트 임계값 `MELODY_SIMILARITY_THRESHOLD = 0.50` 유지
- **Hybrid Scoring 정의**: velocity(0.5) + contour(0.3) + register(0.2) 가중치

### Momus Review (고정밀 검토)
**Identified Issues** (addressed in this revision):
1. **입력 불일치 해결**: Essentia는 오디오 기반이므로 새 함수 `extract_melody_with_audio(audio_path, midi_path)` 추가
2. **테스트 지표 정렬**: 기존 `pitch_class_similarity` 지표 유지 (melody_f1_lenient 대신)
3. **인터페이스 명확화**: WSL 스크립트는 JSON stdout 출력, Python에서 파싱

---

## Work Objectives

### Core Objective
멜로디 추출 품질을 개선하여 레퍼런스 MIDI 대비 70% 이상 매칭률 달성

### Concrete Deliverables
- `backend/scripts/essentia_melody_extractor.py` (WSL용)
- 수정된 `backend/core/melody_extractor.py`
- `backend/scripts/spike_essentia.py` (스파이크 테스트)
- 골든 테스트 통과 증거

### Definition of Done
- [ ] `pytest tests/golden/ -m melody` → 8곡 모두 pitch_class_similarity ≥ 0.50 (현재 임계값)
- [ ] 스파이크 테스트에서 Essentia 결과가 Skyline보다 개선됨 (정성적 확인)
- [ ] 기존 테스트 그대로 통과 (기존 임계값 유지하며 품질 개선)

### Must Have
- Essentia via WSL 통합
- 70%+ 평균 매칭률
- 기존 Skyline 코드 백업 (삭제 금지)

### Must NOT Have (Guardrails)
- Basic Pitch 교체 금지 (audio→MIDI는 유지)
- 기존 파이프라인 구조 변경 금지 (Skyline 위치만 대체)
- 단위 테스트 작성 금지 (스파이크 + 골든만)
- WSL 외 Windows 네이티브 Essentia 시도 금지

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> The executing agent will directly run commands and verify results.

### Test Decision
- **Infrastructure exists**: YES (pytest, golden tests)
- **Automated tests**: Spike + Golden tests only
- **Framework**: pytest

### Agent-Executed QA Scenarios (MANDATORY - ALL tasks)

모든 태스크는 에이전트가 직접 실행하는 QA 시나리오를 포함합니다.
- **스파이크 테스트**: Bash로 스크립트 실행, 출력 파싱
- **골든 테스트**: pytest 실행, 결과 확인
- **통합 테스트**: 전체 파이프라인 실행, MIDI 비교

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: WSL 환경 설정 및 Essentia 설치
└── Task 2: Hybrid Scoring 알고리즘 설계 (문서화만)

Wave 2 (After Wave 1):
├── Task 3: Essentia 스파이크 테스트 (song_01)
└── Task 4: 전체 8곡 스파이크 테스트

Wave 3 (After Wave 2):
└── Task 5: melody_extractor.py 통합

Wave 4 (After Wave 3):
├── Task 6: 골든 테스트 검증
└── Task 7: (조건부) Hybrid Scoring 구현

Critical Path: Task 1 → Task 3 → Task 5 → Task 6
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 3, 4 | 2 |
| 2 | None | 7 | 1 |
| 3 | 1 | 5 | 4 |
| 4 | 1 | 5 | 3 |
| 5 | 3, 4 | 6, 7 | None |
| 6 | 5 | 7 | None |
| 7 | 2, 6 (조건부) | None | None |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2 | quick (WSL 설정), writing (설계 문서) |
| 2 | 3, 4 | unspecified-low (스파이크 테스트) |
| 3 | 5 | unspecified-high (통합 작업) |
| 4 | 6, 7 | quick (검증), unspecified-high (폴백 구현) |

---

## TODOs

### Task 1: WSL 환경 설정 및 Essentia 설치

**What to do**:
1. WSL2 설치 확인 (`wsl --version`)
2. Ubuntu 환경에서 Essentia 및 오디오 디코딩 의존성 설치:
   ```bash
   wsl sudo apt-get update
   wsl sudo apt-get install -y python3-pip python3-dev ffmpeg
   wsl pip3 install essentia
   ```
3. **MP3 디코딩 검증**: Essentia가 MP3를 읽을 수 있는지 확인
   - 실패 시: ffmpeg로 wav 변환 후 사용하는 워크플로우 확인
4. 설치 검증 스크립트 실행

**Must NOT do**:
- Windows 네이티브에 Essentia 설치 시도
- conda 환경 생성 (pip만 사용)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 단순 설치 및 검증 작업
- **Skills**: []
  - No special skills needed

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Task 2)
- **Blocks**: Tasks 3, 4
- **Blocked By**: None

**References**:
- Essentia 설치 가이드: https://essentia.upf.edu/installing.html
- WSL2 설치: https://docs.microsoft.com/en-us/windows/wsl/install

**Acceptance Criteria**:

```
Scenario: Essentia 설치 검증
  Tool: Bash
  Preconditions: WSL2 installed
  Steps:
    1. wsl python3 -c "import essentia; print(essentia.__version__)"
    2. Assert: 출력에 버전 번호 포함 (예: "2.1b6")
    3. Assert: exit code 0
  Expected Result: Essentia import 성공
  Evidence: .sisyphus/evidence/task-1-essentia-version.txt

Scenario: ffmpeg 설치 검증
  Tool: Bash
  Steps:
    1. wsl ffmpeg -version
    2. Assert: "ffmpeg version" 출력됨
    3. Assert: exit code 0
  Expected Result: ffmpeg 사용 가능
  Evidence: .sisyphus/evidence/task-1-ffmpeg-version.txt

Scenario: MP3 로딩 테스트 (Essentia 또는 ffmpeg 변환)
  Tool: Bash
  Steps:
    1. 테스트용 MP3 파일 WSL 경로로 변환: /mnt/c/.../song_01/input.mp3
    2. wsl python3 -c "
       import essentia.standard as es
       try:
           audio = es.MonoLoader(filename='/mnt/c/.../input.mp3')()
           print(f'Loaded {len(audio)} samples')
       except Exception as e:
           print(f'MonoLoader failed: {e}')
           # ffmpeg 폴백
           import subprocess
           subprocess.run(['ffmpeg', '-i', '/mnt/c/.../input.mp3', '/tmp/test.wav', '-y'])
           audio = es.MonoLoader(filename='/tmp/test.wav')()
           print(f'Loaded via ffmpeg: {len(audio)} samples')
       "
    3. Assert: "Loaded" 포함 (samples > 0)
  Expected Result: MP3 로딩 성공 (직접 또는 ffmpeg 변환 후)
  Evidence: .sisyphus/evidence/task-1-mp3-load.txt
```

**Commit**: NO (설정만)

---

### Task 2: Hybrid Scoring 알고리즘 설계 (문서화)

**What to do**:
1. `.sisyphus/drafts/hybrid-scoring-design.md` 작성
2. 알고리즘 수식 정의:
   ```
   score(note) = 0.5 * velocity_score + 0.3 * contour_score + 0.2 * register_score
   
   velocity_score = note.velocity / 127
   contour_score = 1.0 / (1 + |note.pitch - prev_pitch|)
   register_score = gaussian(note.pitch, center=72, sigma=12)
   ```
3. 엣지 케이스 정의 (첫 노트, 동일 onset 등)

**Must NOT do**:
- 코드 구현 (설계만)
- 기존 melody_extractor.py 수정

**Recommended Agent Profile**:
- **Category**: `writing`
  - Reason: 기술 문서 작성
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Task 1)
- **Blocks**: Task 7
- **Blocked By**: None

**References**:
- `backend/core/melody_extractor.py:12-56` - 현재 Skyline 알고리즘 구조
- Oracle 권장: "hybrid scoring: 0.5×velocity + 0.3×contour + 0.2×register"

**Acceptance Criteria**:

```
Scenario: 설계 문서 검증
  Tool: Bash
  Steps:
    1. cat .sisyphus/drafts/hybrid-scoring-design.md
    2. Assert: "velocity_score" 포함
    3. Assert: "contour_score" 포함
    4. Assert: "register_score" 포함
    5. Assert: 가중치 합계 = 1.0 (0.5 + 0.3 + 0.2)
  Expected Result: 완전한 설계 문서
  Evidence: 파일 내용 캡처
```

**Commit**: NO (드래프트만)

---

### Task 3: Essentia 스파이크 테스트 (song_01)

**What to do**:
1. `backend/scripts/essentia_melody_extractor.py` 작성 (WSL용)
   - **입력**: 오디오 파일 경로 (WSL 형식: `/mnt/c/...`)
   - **출력**: stdout으로 JSON 배열 `[{"pitch": 60, "onset": 0.5, "duration": 0.25}, ...]`
   - **MP3 로딩 실패 시**: ffmpeg로 임시 wav 변환 후 로딩
   
   ```python
   #!/usr/bin/env python3
   import essentia.standard as es
   import json
   import sys
   import subprocess
   import tempfile
   import os
   
   def load_audio(audio_path: str, sr: int = 44100):
       """오디오 로딩 (MP3 실패 시 ffmpeg 변환 폴백)"""
       try:
           return es.MonoLoader(filename=audio_path, sampleRate=sr)()
       except Exception:
           # ffmpeg로 wav 변환
           with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
               wav_path = f.name
           subprocess.run(['ffmpeg', '-i', audio_path, '-ar', str(sr), '-ac', '1', wav_path, '-y'],
                          capture_output=True, check=True)
           audio = es.MonoLoader(filename=wav_path, sampleRate=sr)()
           os.unlink(wav_path)
           return audio
   
   def convert_pitch_to_notes(pitches, confidences, hop_size: int, sr: int, 
                               conf_threshold: float = 0.8, min_duration: float = 0.05):
       """
       Pitch contour → Note events 변환
       
       규칙:
       1. confidence < conf_threshold인 프레임은 무음(silence)으로 처리
       2. 연속된 유효 프레임을 하나의 노트로 병합
       3. 노트 pitch는 구간 내 중앙값(median)으로 결정
       4. min_duration 미만 노트는 제거
       
       Args:
           pitches: Hz 단위 pitch 배열
           confidences: 0-1 신뢰도 배열
           hop_size: 프레임 간격 (samples)
           sr: 샘플레이트
           conf_threshold: 유효 프레임 판단 임계값
           min_duration: 최소 노트 길이 (초)
       
       Returns:
           [{"pitch": midi_note, "onset": sec, "duration": sec}, ...]
       """
       import numpy as np
       
       frame_duration = hop_size / sr
       notes = []
       
       # 유효 프레임 마스크
       valid = (confidences >= conf_threshold) & (pitches > 20)  # 20Hz 미만 = silence
       
       # 연속 구간 찾기
       in_note = False
       note_start = 0
       note_pitches = []
       
       for i, (is_valid, pitch) in enumerate(zip(valid, pitches)):
           if is_valid and not in_note:
               # 노트 시작
               in_note = True
               note_start = i
               note_pitches = [pitch]
           elif is_valid and in_note:
               # 노트 계속
               note_pitches.append(pitch)
           elif not is_valid and in_note:
               # 노트 종료
               in_note = False
               duration = (i - note_start) * frame_duration
               if duration >= min_duration and note_pitches:
                   median_hz = np.median(note_pitches)
                   midi_note = int(round(12 * np.log2(median_hz / 440) + 69))
                   if 21 <= midi_note <= 108:  # 피아노 범위
                       notes.append({
                           "pitch": midi_note,
                           "onset": round(note_start * frame_duration, 4),
                           "duration": round(duration, 4)
                       })
               note_pitches = []
       
       # 마지막 노트 처리
       if in_note and note_pitches:
           duration = (len(pitches) - note_start) * frame_duration
           if duration >= min_duration:
               median_hz = np.median(note_pitches)
               midi_note = int(round(12 * np.log2(median_hz / 440) + 69))
               if 21 <= midi_note <= 108:
                   notes.append({
                       "pitch": midi_note,
                       "onset": round(note_start * frame_duration, 4),
                       "duration": round(duration, 4)
                   })
       
       return notes
   
   def extract_melody_to_json(audio_path):
       audio = load_audio(audio_path, sr=44100)
       
       pitch_extractor = es.PredominantPitchMelodia(
           frameSize=2048, hopSize=128, sampleRate=44100
       )
       pitches, confidences = pitch_extractor(audio)
       
       notes = convert_pitch_to_notes(pitches, confidences, hop_size=128, sr=44100)
       
       # Output as JSON to stdout
       print(json.dumps(notes))
   
   if __name__ == "__main__":
       extract_melody_to_json(sys.argv[1])
   ```

2. `backend/scripts/spike_essentia.py` 작성 (Windows 측)
   - WSL subprocess 호출: `wsl python3 /mnt/c/.../essentia_melody_extractor.py <audio_path>`
   - JSON stdout 파싱 → Note 리스트
   - reference.mxl에서 추출한 멜로디와 비교 (`compare_note_lists_with_pitch_class`)
   - 결과 출력: note count, pitch_class_similarity

3. song_01에 대해 실행 및 결과 비교
   - Skyline 결과 vs Essentia 결과 정량 비교

**Must NOT do**:
- Windows 네이티브 실행 시도
- melody_extractor.py 수정 (스파이크만)
- MIDI 파일로 중간 저장 (JSON stdout으로 직접 전달)

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: 스파이크 테스트 스크립트 작성
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Task 4)
- **Blocks**: Task 5
- **Blocked By**: Task 1

**References**:
- `backend/scripts/spike_basic_pitch.py` - 기존 스파이크 테스트 패턴
- `backend/tests/golden/data/song_01/input.mp3` - 테스트 오디오
- `backend/tests/golden/data/song_01/reference.mxl` - 레퍼런스 MusicXML
- `backend/core/musicxml_comparator.py:compare_note_lists_with_pitch_class` - pitch_class_similarity 계산
- **Pitch→Note 변환 규칙** (이 계획 내 정의됨):
  - confidence ≥ 0.8 프레임만 유효
  - 연속 유효 프레임 → 하나의 노트 (median pitch)
  - 최소 duration: 50ms
  - 피아노 범위 (MIDI 21-108) 필터링

**Acceptance Criteria**:

```
Scenario: Essentia 스파이크 테스트 실행
  Tool: Bash
  Preconditions: Task 1 완료 (Essentia 설치됨)
  Steps:
    1. cd backend && python scripts/spike_essentia.py --song song_01
    2. Assert: stdout에 JSON 파싱 성공 로그
    3. Assert: "pitch_class_similarity" 출력됨
    4. Assert: "skyline_similarity" 출력됨 (비교용)
    5. Assert: essentia_similarity > skyline_similarity (개선 확인)
    6. Assert: essentia_note_count > 50
  Expected Result: Essentia가 Skyline보다 나은 결과
  Evidence: 터미널 출력 캡처 (.sisyphus/evidence/task-3-spike-result.txt)

Scenario: Essentia JSON 출력 검증
  Tool: Bash
  Steps:
    1. wsl python3 /mnt/c/.../essentia_melody_extractor.py /mnt/c/.../song_01/input.mp3
    2. Assert: stdout이 JSON 배열 형식
    3. Assert: 각 요소에 "pitch", "onset", "duration" 키 존재
  Expected Result: 유효한 JSON 출력
  Evidence: JSON 출력 캡처

Scenario: 실패 케이스 - Essentia가 Skyline보다 나쁨
  Tool: Bash
  Steps:
    1. cd backend && python scripts/spike_essentia.py --song song_01
    2. If essentia_similarity <= skyline_similarity:
       - 로그: "Essentia 결과가 Skyline과 비슷하거나 나쁨"
       - Task 7 (Hybrid Scoring) 필요 플래그 설정
  Expected Result: 폴백 필요 여부 결정
  Evidence: 결과 파일에 기록 (.sisyphus/evidence/task-3-fallback-needed.txt)
```

**Commit**: YES
- Message: `feat(melody): add Essentia spike test for melody extraction`
- Files: `backend/scripts/essentia_melody_extractor.py`, `backend/scripts/spike_essentia.py`

---

### Task 4: 전체 8곡 스파이크 테스트

**What to do**:
1. spike_essentia.py 수정하여 8곡 모두 테스트
2. 곡별 결과 테이블 출력 (Skyline vs Essentia 비교):
   ```
   | Song    | Skyline | Essentia | Improved |
   |---------|---------|----------|----------|
   | song_01 | 0.23    | 0.45     | ✓        |
   | song_02 | 0.31    | 0.52     | ✓        |
   ...
   | SUMMARY | 0.27    | 0.48     | 6/8 improved |
   ```
   - **지표**: `pitch_class_similarity` (compare_note_lists_with_pitch_class 사용)
3. 평균 및 개선된 곡 수 계산

**Must NOT do**:
- 곡별 커스텀 파라미터 적용
- melody_extractor.py 수정

**Recommended Agent Profile**:
- **Category**: `unspecified-low`
  - Reason: 스파이크 테스트 확장
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Task 3)
- **Blocks**: Task 5
- **Blocked By**: Task 1

**References**:
- `backend/tests/golden/data/song_01/` through `song_08/` - 8곡 테스트 데이터
- Task 3 결과물: `spike_essentia.py`

**Acceptance Criteria**:

```
Scenario: 8곡 전체 스파이크 테스트
  Tool: Bash
  Preconditions: Task 3 완료
  Steps:
    1. cd backend && python scripts/spike_essentia.py --all
    2. Assert: 8곡 모두 결과 출력됨
    3. Assert: 결과 테이블 포함 (Song, Skyline, Essentia 컬럼)
    4. Assert: Essentia가 Skyline보다 높은 곡 > 4개 (과반수 개선)
    5. 결과 저장: .sisyphus/evidence/task-4-all-songs.txt
  Expected Result: 전체 곡에서 Essentia가 Skyline 대비 개선
  Evidence: .sisyphus/evidence/task-4-all-songs.txt

Scenario: 결과 테이블 형식 검증
  Tool: Bash
  Steps:
    1. cd backend && python scripts/spike_essentia.py --all
    2. Assert: stdout에 마크다운 테이블 형식 출력
       예시:
       | Song | Skyline | Essentia | Improved |
       |------|---------|----------|----------|
       | song_01 | 0.23 | 0.45 | ✓ |
    3. Assert: "SUMMARY" 섹션 포함 (개선된 곡 수, 평균 변화)
  Expected Result: 정량 비교 가능한 결과
  Evidence: 테이블 캡처
```

**Commit**: YES (Task 3과 함께)
- Message: `feat(melody): extend Essentia spike to all 8 songs`
- Files: `backend/scripts/spike_essentia.py`

---

### Task 5: melody_extractor.py 통합

**What to do**:
1. **기존 함수 유지**: `extract_melody(midi_path)` 시그니처 그대로 유지 (하위 호환성)
2. **새 함수 추가**: `extract_melody_with_audio(audio_path: Path, midi_path: Path) -> List[Note]`
   ```python
   def _get_wsl_script_path() -> str:
       """현재 repo 기준 WSL 스크립트 경로 계산"""
       # 이 파일 기준으로 scripts/ 폴더 위치 계산
       import os
       this_dir = Path(os.path.dirname(os.path.abspath(__file__)))
       script_path = this_dir.parent / "scripts" / "essentia_melody_extractor.py"
       
       # Windows 경로 → WSL 경로 변환
       # C:\Users\... → /mnt/c/Users/...
       win_path = str(script_path.resolve())
       drive_letter = win_path[0].lower()
       rest_path = win_path[2:].replace("\\", "/")
       return f"/mnt/{drive_letter}{rest_path}"
   
   def _call_essentia_wsl(audio_path: Path) -> List[Note]:
       """WSL에서 Essentia를 호출하여 멜로디 추출"""
       # Windows 경로 → WSL 경로 변환
       win_audio = str(audio_path.resolve())
       drive_letter = win_audio[0].lower()
       rest_path = win_audio[2:].replace("\\", "/")
       wsl_audio_path = f"/mnt/{drive_letter}{rest_path}"
       
       # WSL 스크립트 경로 (repo 기준 계산)
       script_path = _get_wsl_script_path()
       
       result = subprocess.run(
           ["wsl", "python3", script_path, wsl_audio_path],
           capture_output=True, text=True, timeout=120
       )
       
       if result.returncode != 0:
           raise RuntimeError(f"Essentia failed: {result.stderr}")
       
       # JSON stdout 파싱 → Note 리스트
       import json
       data = json.loads(result.stdout)
       return [Note(pitch=n["pitch"], onset=n["onset"], duration=n["duration"], velocity=80) 
               for n in data]
   
   def extract_melody_with_audio(audio_path: Path, midi_path: Path) -> List[Note]:
       """
       오디오 기반 Essentia 멜로디 추출 (폴백: MIDI 기반 Skyline)
       
       Args:
           audio_path: 원본 오디오 파일 경로
           midi_path: Basic Pitch로 생성된 MIDI 파일 경로 (폴백용)
       
       Returns:
           멜로디 Note 리스트
       """
       try:
           notes = _call_essentia_wsl(audio_path)
           logger.info(f"Essentia extracted {len(notes)} melody notes")
       except Exception as e:
           logger.warning(f"Essentia failed: {e}, falling back to Skyline")
           notes = extract_melody(midi_path)  # 기존 MIDI 기반 폴백
       
       # 후처리 (짧은 음표 제거, overlap 해결, 옥타브 정규화)
       notes = filter_short_notes(notes)
       notes = resolve_overlaps(notes)
       notes = normalize_octave(notes)
       return notes
   ```
3. 기존 `extract_melody()` 함수는 **그대로 유지** (Skyline 파이프라인)
4. 골든 테스트에서 `extract_melody_with_audio()` 호출하도록 수정 (별도 Task 아님)

**Must NOT do**:
- `apply_skyline()` 함수 삭제 (폴백으로 사용)
- `extract_melody()` 시그니처 변경 (하위 호환성)
- Basic Pitch 호출 부분 수정

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: 핵심 모듈 수정, 통합 작업
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 3 (sequential)
- **Blocks**: Tasks 6, 7
- **Blocked By**: Tasks 3, 4

**References**:
- `backend/core/melody_extractor.py:12-56` - 현재 apply_skyline() 구현
- `backend/core/melody_extractor.py:158-190` - extract_melody() 메인 함수
- Task 3 결과물: `essentia_melody_extractor.py`

**Acceptance Criteria**:

```
Scenario: 새 함수 import 검증
  Tool: Bash
  Preconditions: Tasks 3, 4 완료
  Steps:
    1. cd backend && python -c "from core.melody_extractor import extract_melody_with_audio; print('import ok')"
    2. Assert: import 성공 (exit code 0)
    3. cd backend && python -c "from core.melody_extractor import extract_melody; print('legacy ok')"
    4. Assert: 기존 함수도 import 성공 (exit code 0)
  Expected Result: 새 함수 + 기존 함수 모두 사용 가능
  Evidence: .sisyphus/evidence/task-5-import.txt

Scenario: Essentia 경로로 멜로디 추출 성공
  Tool: Bash
  Preconditions: WSL Essentia 설치됨, job_dir에 raw.mid 생성됨
  Steps:
    1. cd backend && python -c "
       from core.melody_extractor import extract_melody_with_audio
       from core.audio_to_midi import convert_audio_to_midi
       from pathlib import Path
       import tempfile
       
       audio = Path('tests/golden/data/song_01/input.mp3')
       
       # raw.mid 동적 생성 (골든 테스트와 동일한 방식)
       with tempfile.TemporaryDirectory() as job_dir:
           midi = Path(job_dir) / 'raw.mid'
           convert_audio_to_midi(audio, midi)
           result = extract_melody_with_audio(audio, midi)
           print(f'Essentia Notes: {len(result)}')"
    2. Assert: Notes > 50
    3. Assert: stdout에 "Essentia extracted" 포함 (폴백 아님)
  Expected Result: Essentia 경로로 멜로디 추출 성공
  Evidence: .sisyphus/evidence/task-5-essentia-success.txt

Scenario: Skyline 폴백 검증 (WSL 비활성화 시뮬레이션)
  Tool: Bash
  Steps:
    1. cd backend && SKIP_WSL=1 python -c "
       from core.melody_extractor import extract_melody_with_audio
       from core.audio_to_midi import convert_audio_to_midi
       from pathlib import Path
       import tempfile
       
       audio = Path('tests/golden/data/song_01/input.mp3')
       
       with tempfile.TemporaryDirectory() as job_dir:
           midi = Path(job_dir) / 'raw.mid'
           convert_audio_to_midi(audio, midi)
           result = extract_melody_with_audio(audio, midi)
           print(f'Fallback Notes: {len(result)}')"
    2. Assert: 에러 없이 결과 반환
    3. Assert: stderr에 "falling back to Skyline" 포함
  Expected Result: 폴백 로직 정상 작동
  Evidence: .sisyphus/evidence/task-5-fallback.txt
```

**Commit**: YES
- Message: `feat(melody): add extract_melody_with_audio with Essentia support`
- Files: `backend/core/melody_extractor.py`
- Pre-commit: `cd backend && python -c "from core.melody_extractor import extract_melody_with_audio, extract_melody"`

---

### Task 6: 골든 테스트 검증

**What to do**:
1. 골든 테스트가 `extract_melody_with_audio()`를 호출하도록 수정 (선택적):
   - `test_golden.py`의 `TestMelodyComparison.test_melody_similarity`에서
   - `gen_melody = extract_melody(raw_midi_path)` → 
   - `gen_melody = extract_melody_with_audio(input_mp3, raw_midi_path)`로 변경
2. 전체 골든 테스트 실행: `pytest tests/golden/ -m melody -v`
3. pitch_class_similarity 결과 확인:
   - 모든 곡 ≥ 0.50 → 성공 (현재 임계값 `MELODY_SIMILARITY_THRESHOLD`)
   - 실패하는 곡 있음 → Task 7 진행 필요

**Must NOT do**:
- 테스트 임계값 수정 (0.50 유지)
- 실패한 테스트 건너뛰기
- 지표 변경 (pitch_class_similarity 유지)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: 테스트 실행 및 결과 확인
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 4 (sequential)
- **Blocks**: Task 7 (조건부)
- **Blocked By**: Task 5

**References**:
- `backend/tests/golden/test_golden.py` - 골든 테스트 스위트
- `backend/core/comparison_utils.py` - 메트릭 계산

**Acceptance Criteria**:

```
Scenario: 골든 테스트 통과 (8곡 전체)
  Tool: Bash
  Preconditions: Task 5 완료, test_golden.py가 extract_melody_with_audio 호출
  Steps:
    1. cd backend && pytest tests/golden/ -m melody -v --tb=short
    2. Assert: "8 passed" 출력됨
    3. Assert: 각 곡별 "Similarity:" 값 ≥ 50%
    4. 결과 저장: pytest 전체 출력을 .sisyphus/evidence/task-6-golden-result.txt에 캡처
  Expected Result: 8곡 모두 pitch_class_similarity ≥ 0.50 통과
  Evidence: .sisyphus/evidence/task-6-golden-result.txt

Scenario: 일부 곡 실패 (Hybrid Scoring 필요)
  Tool: Bash
  Steps:
    1. cd backend && pytest tests/golden/ -m melody -v --tb=short
    2. If any test fails:
       - 실패한 곡 목록 기록
       - 로그: "Essentia alone insufficient for: [song_list]"
       - Task 7 진행 필요 플래그 설정
    3. 결과 저장: .sisyphus/evidence/task-6-failed-songs.txt
  Expected Result: 폴백 필요 여부 결정
  Evidence: .sisyphus/evidence/task-6-failed-songs.txt

Scenario: 기존 대비 개선 확인 (정성적)
  Tool: Bash
  Steps:
    1. Essentia 적용 전 결과 vs 적용 후 결과 비교 (수동 기록)
    2. 개선된 곡 수, 평균 similarity 변화 기록
  Expected Result: 정량적 개선 증거
  Evidence: .sisyphus/evidence/task-6-improvement-summary.md
```

**Commit**: YES (테스트 코드 수정 시)
- Message: `refactor(test): use extract_melody_with_audio in golden tests`
- Files: `backend/tests/golden/test_golden.py`
- Pre-commit: `pytest tests/golden/ -m melody -v`

---

### Task 7: (조건부) Hybrid Scoring 구현

> **조건**: Task 6에서 평균 melody_f1_lenient < 0.70인 경우에만 실행

**What to do**:
1. Task 2의 설계 문서 기반으로 `apply_hybrid_scoring()` 구현:
   ```python
   def hybrid_score(note: Note, prev_pitch: int) -> float:
       v = note.velocity / 127  # velocity score
       c = 1.0 / (1 + abs(note.pitch - prev_pitch)) if prev_pitch else 0.5  # contour
       r = math.exp(-((note.pitch - 72) ** 2) / (2 * 12 ** 2))  # register (gaussian)
       return 0.5 * v + 0.3 * c + 0.2 * r
   
   def apply_hybrid_scoring(notes: List[Note]) -> List[Note]:
       # 동일 onset 그룹에서 가장 높은 hybrid_score를 가진 노트 선택
   ```
2. `extract_melody()`에서 Essentia + Hybrid 조합:
   - Essentia 결과에 Hybrid Scoring 적용
   - 또는 Skyline 대신 Hybrid Scoring 단독 사용

**Must NOT do**:
- Essentia 코드 삭제 (조합 사용)
- 기존 함수 시그니처 변경

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: 알고리즘 구현
- **Skills**: []

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Wave 4 (after Task 6)
- **Blocks**: None (최종 태스크)
- **Blocked By**: Tasks 2, 6

**References**:
- `.sisyphus/drafts/hybrid-scoring-design.md` - Task 2 설계 문서
- `backend/core/melody_extractor.py` - 현재 구현
- Oracle 권장 알고리즘

**Acceptance Criteria**:

```
Scenario: Hybrid Scoring 통합 후 골든 테스트
  Tool: Bash
  Preconditions: Task 6에서 일부 곡이 pitch_class_similarity < 0.50
  Steps:
    1. cd backend && pytest tests/golden/ -m melody -v --tb=short
    2. Assert: 8 passed (모든 곡 pitch_class_similarity >= 0.50)
    3. If still fails:
       - 로그: "Further iteration needed - check weights"
       - 가중치 조정 필요 플래그
  Expected Result: 골든 테스트 전체 통과
  Evidence: .sisyphus/evidence/task-7-hybrid-result.txt
```

**Commit**: YES
- Message: `feat(melody): add Hybrid Scoring for improved melody extraction`
- Files: `backend/core/melody_extractor.py`
- Pre-commit: `pytest tests/golden/ -m melody -v`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 3, 4 | `feat(melody): add Essentia spike test` | scripts/*.py | python spike_essentia.py |
| 5 | `feat(melody): integrate Essentia` | core/melody_extractor.py | import test |
| 7 | `feat(melody): add Hybrid Scoring` | core/melody_extractor.py | pytest -m melody |

---

## Success Criteria

### Verification Commands
```bash
# Essentia 설치 확인
wsl python3 -c "import essentia; print('OK')"  # Expected: OK

# 스파이크 테스트 (Essentia vs Skyline 비교)
cd backend && python scripts/spike_essentia.py --all
# Expected: 과반수(5+곡)에서 Essentia가 Skyline보다 높음

# 새 함수 import 검증
cd backend && python -c "from core.melody_extractor import extract_melody_with_audio, extract_melody"
# Expected: 에러 없이 import 성공

# 골든 테스트 (기존 임계값 0.50)
cd backend && pytest tests/golden/ -m melody -v
# Expected: 8 passed
```

### Final Checklist
- [ ] Essentia WSL 설치 완료 (`wsl python3 -c "import essentia"` 성공)
- [ ] 스파이크 테스트 통과 (Essentia가 Skyline 대비 개선)
- [ ] 새 함수 `extract_melody_with_audio()` 추가됨
- [ ] 기존 함수 `extract_melody()` 시그니처 유지됨 (하위 호환성)
- [ ] 골든 테스트 통과 (8곡 모두 pitch_class_similarity ≥ 0.50)
- [ ] 기존 Skyline 코드 유지됨 (폴백으로 사용)
