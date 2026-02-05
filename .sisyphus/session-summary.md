# Pop2Piano 업그레이드 - 세션 요약

**날짜**: 2026-02-05
**플랜**: `.sisyphus/plans/pop2piano-upgrade.md`
**목표**: ByteDance(피아노 인식) → Pop2Piano(피아노 편곡 생성) 전면 교체

---

## 프로젝트 진행 히스토리

### Phase 1: 초기 구축 (완료)
- FastAPI + Next.js 14 + Docker(CUDA 11.8) 기반 웹앱 구축
- Basic Pitch → ByteDance Piano Transcription 교체
- 8곡 골든 테스트 체계 수립

### Phase 2: Reference Matching V2 (완료 - 블로커 발견)
- `.sisyphus/plans/reference-matching-v2.md`
- 5/9 태스크 완료, **Task 6에서 블로커**: 85% 유사도 달성 불가
- 최고 성적: song_08 57.62%, 평균 ~20%
- **근본 원인**: ByteDance는 "피아노 인식" 모델 — 팝 믹스를 넣으면 모든 소리를 피아노 노트로 변환 → 노이즈

### Phase 3: Pop2Piano 업그레이드 (현재 - 플랜 작성 완료, 실행 전)
- `.sisyphus/plans/pop2piano-upgrade.md`
- **Momus 검토: ✅ OKAY (승인)**
- 10개 태스크, 4개 Wave

---

## 핵심 패러다임 (CRITICAL - 반드시 숙지)

```
이 프로젝트는 "피아노 인식(Transcription)"이 아니라
"피아노 편곡 생성(Arrangement)"이다.

- ❌ "음원에서 피아노 소리만 추출" → 틀린 접근
- ✅ "전체 팝송을 피아노로 편곡" → 올바른 접근

Pop2Piano = 편곡 생성 모델 (팝 오디오 → 피아노 커버 MIDI)
ByteDance = 피아노 인식 모델 (피아노 녹음 → 노트 인식)
```

---

## Pop2Piano 업그레이드 플랜 요약

### 10개 태스크 (4 Wave)

| Wave | Task | 내용 | 상태 |
|------|------|------|------|
| 1 | 1 | MIDI 레퍼런스 골든 테스트 데이터 통합 (22개 파일) | ⬜ 대기 |
| 1 | 2 | Pop2Piano 통합 (audio_to_midi.py 교체) | ⬜ 대기 |
| 1→2 | 3 | Pop2Piano composer 스타일 탐색 (21개 중 최적 선택) | ⬜ 대기 |
| 2 | 4 | 비교 알고리즘 전면 교체 (mir_eval + DTW + 복합 메트릭) | ⬜ 대기 |
| 2 | 5 | MusicXML 폴리포닉 양손 악보 지원 | ⬜ 대기 |
| 2 | 6 | 난이도 시스템 재설계 (Easy/Medium/Hard) | ⬜ 대기 |
| 3 | 7 | MIDI 직접 비교 모듈 구현 | ⬜ 대기 |
| 3 | 8 | 복합 골든 테스트 구현 | ⬜ 대기 |
| 3 | 9 | 8곡 전체 유사도 측정 + 리포트 | ⬜ 대기 |
| 4 | 10 | 결과 평가 및 다음 단계 결정 | ⬜ 대기 |

### 핵심 제약사항
- 함수 시그니처 유지: `convert_audio_to_midi(audio_path, output_path) → Dict`
- ByteDance 삭제 금지 → `.bak` 백업 유지
- 소스 분리(Demucs) 접근 금지
- Frontend 변경 없음 (별도 작업)
- 매 task 완료 시 커밋 + 푸시

---

## 기술 조사 결과 (Momus 검토 시 추가 발견)

### Pop2Piano 기술 세부사항
- **Import**: `from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor`
- **모델**: `sweetcocoa/pop2piano` (HuggingFace)
- **샘플레이트**: **44100Hz** (현재 ByteDance는 16kHz → 변경 필요)
- **composer_vocab_size = 21** (플랜에서 "16+"이라 했지만 실제 21개)
- **composer 기본값**: `"composer1"`
- **출력**: `pretty_midi` 객체 (폴리포닉 MIDI)
- **학습 데이터**: K-pop + Western Pop + Hip Hop

### mir_eval 기술 세부사항
- **모듈**: `mir_eval.transcription` (폴리포닉 지원)
- **입력 형식**: intervals `[[onset, offset], ...]` + pitches `[Hz, ...]` (MIDI 번호 아님!)
- **MIDI→Hz 변환 필요**: `mir_eval.util.midi_to_hz()`
- **기본 tolerance**: onset 50ms, pitch 50 cents, offset 20% of duration
- **매칭**: `match_notes()` — 다대다 최대 매칭

### 현재 코드베이스 주요 패턴
- **Singleton 모델 로딩** (`_get_transcriptor()`) → Pop2Piano에서도 유지
- **시간 단위: 초(seconds)** — 모든 내부 처리
- **Note 데이터클래스**: `pitch(int), onset(float), duration(float), velocity(int)`
- **16th-note 양자화** in MusicXML 변환
- **Atomic file writes** (`write_file_atomic()`)

---

## 테스트 데이터 인벤토리

### 골든 테스트 (backend/tests/golden/data/)
- 8곡 × (input.mp3 + reference.mxl + metadata.json) = 24 파일
- **MIDI 레퍼런스 아직 미통합** ← Task 1에서 처리

### 테스트 소스 (test/)
- 8 MP3 + 8 MXL + 18 MIDI (원본 8 + 쉬운 8 + 다장조 5~7) = 34~36 파일
- 다장조 있는 곡: 꿈의 버스, 너에게100퍼센트, 달리 표현할 수 없어요, 등불을 지키다, 여름이었다 (+ 비비드라라러브 확인 필요)

### 골든 테스트 마커
- `@pytest.mark.golden` — 전체
- `@pytest.mark.smoke` — 파이프라인 정상 동작
- `@pytest.mark.compare` — reference 비교
- `@pytest.mark.melody` — 멜로디 유사도

---

## 현재 성적 (기준선)

| 곡 | Melody Similarity | Pitch Class |
|----|-------------------|-------------|
| song_01 (Golden) | 18.49% | — |
| song_02 (IRIS OUT) | 6.63% | — |
| song_03 (꿈의 버스) | 14.10% | — |
| song_04 (너에게100퍼센트) | 4.55% | — |
| song_05 (달리 표현할 수 없어요) | 17.34% | — |
| song_06 (등불을 지키다) | 17.78% | — |
| song_07 (비비드라라러브) | 22.83% | — |
| song_08 (여름이었다) | **57.62%** | — |
| **평균** | **~20%** | — |

---

## .sisyphus 파일 구조

```
.sisyphus/
├── plans/
│   ├── pop2piano-upgrade.md          # ★ 현재 활성 플랜 (Momus OKAY)
│   ├── reference-matching-v2.md      # 이전 플랜 (블로커로 중단)
│   ├── transcription-model-upgrade.md # 모델 교체 조사 플랜
│   ├── golden-test-musicxml.md       # 골든 테스트 구축 플랜
│   └── piano-sheet-extractor.md      # 최초 구축 플랜
├── drafts/
│   └── pop2piano-upgrade.md          # 드래프트 (플랜 완성 후 삭제 가능)
├── notepads/                         # 각 플랜별 학습/이슈/결정 기록
├── evidence/                         # 스크린샷 등 증거 자료
├── boulder.json                      # 현재 활성 boulder 상태
├── session-summary.md                # ★ 이 문서
└── handoff-prompt.md                 # 다음 세션 핸드오프 프롬프트
```

---

## 다음 세션 시작 프롬프트

```
Pop2Piano 기반 피아노 편곡 시스템 업그레이드 플랜을 실행해야 합니다.

플랜: .sisyphus/plans/pop2piano-upgrade.md (Momus 승인 완료)
세션 요약: .sisyphus/session-summary.md

핵심:
- ByteDance(피아노 인식) → Pop2Piano(피아노 편곡 생성) 모델 교체
- "편곡 생성" 문제 — 소스 분리 접근 금지
- 비교 알고리즘: mir_eval + DTW + 복합 메트릭
- MIDI 레퍼런스(원본/쉬운/다장조) 골든 테스트 통합
- Pop2Piano 샘플레이트: 44100Hz (기존 16kHz에서 변경)
- mir_eval pitches는 Hz 단위 (MIDI 번호 → Hz 변환 필요)
- composer_vocab_size = 21 (21개 스타일 탐색)

/start-work 실행하여 플랜 시작
```

---

## 결정 매트릭스 (Task 10에서 사용)

| composite score | 판정 | 다음 단계 |
|-----------------|------|-----------|
| ≥ 70% | GREAT | 최적화 + UI 통합 |
| 50-70% | GOOD | 후처리 파이프라인 추가 |
| 30-50% | MODERATE | 멀티스텝 보조 (Demucs 보컬 → 멜로디 보정) |
| < 30% | POOR | 패러다임 전환 (PiCoGen2, 메트릭 재정의) |
