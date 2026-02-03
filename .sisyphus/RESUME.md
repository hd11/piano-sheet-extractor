# Piano Sheet Extractor - 작업 재개 가이드

## 프로젝트 상태: 계획 단계 (Momus 리뷰 진행 중)

- **계획서 위치**: `.sisyphus/plans/piano-sheet-extractor.md` (~4200줄)
- **Momus 리뷰**: 13라운드 완료, 아직 REJECT 상태
- **마지막 작업일**: 2026-02-03

---

## 남은 수정 사항 (Momus 지적 5개)

### 1. 테스트/스크립트 디렉토리 구조 수정
- **현재 문제**: 루트 `tests/golden/`, `scripts/`와 `backend/tests/`, `backend/scripts/` 혼재
- **왜 문제인가**: Docker 빌드 컨텍스트가 `./backend`이면 루트 테스트가 컨테이너에 없음
- **해결 방법**: 모든 테스트/스크립트를 `backend/` 하위로 이동
  - `tests/golden/` → `backend/tests/golden/`
  - `tests/e2e/` → `backend/tests/e2e/`
  - `scripts/` → `backend/scripts/`
  - 모든 커맨드도 그에 맞게 수정

### 2. SSOT 함수명 통일
- `parse_midi()` ✅ vs `parse_midi_to_notes()` ❌
- `update_job_status()` ✅ vs `update_job()` ❌
- 계획서 전체에서 검색/치환 필요

### 3. JOB_STORAGE_PATH 환경변수 전 구간 적용
- TTL cleanup 루프에서 `/tmp/piano-sheet-jobs` 하드코딩됨
- `Path(os.environ.get("JOB_STORAGE_PATH", "/tmp/piano-sheet-jobs"))` 형태로 수정

### 4. Chord 표기 정책 확정
- **현재 충돌**: Task 6은 "major/minor만 지원", 예시에는 "G7" 등장
- **권장 해결**: 
  - 자동 감지: major/minor 24개만
  - 수동 입력: 자유 문자열 허용 (검증 없음)
  - 렌더링: 입력된 그대로 표시

### 5. 업로드 에러 시 job 생성 시점 명확화
- **권장 해결**: 
  - 검증 실패(크기/길이 초과) 시: job.json 생성 안 함, 디렉토리도 없음
  - 처리 중 실패 시: job.json 남김 (status=failed)

---

## 다른 컴퓨터에서 이어서 작업하기

```bash
# 1. 저장소 클론
git clone https://github.com/hd11/piano-sheet-extractor.git
cd piano-sheet-extractor

# 2. AI에게 아래 프롬프트 전달
```

---

## AI 이어서 작업 프롬프트 (복사해서 사용)

```
피아노 악보 추출 웹앱 계획서 Momus 리뷰를 이어서 진행해줘.

**현재 상태:**
- 계획서: `.sisyphus/plans/piano-sheet-extractor.md` (~4200줄)
- Momus 리뷰 13라운드 완료, REJECT 상태
- 상태 파일: `.sisyphus/RESUME.md` 참조

**남은 수정 사항 (5개):**
1. 테스트/스크립트 디렉토리를 backend/ 하위로 이동 (Docker 정책 일치)
2. SSOT 함수명 통일: parse_midi (O), parse_midi_to_notes (X) / update_job_status (O), update_job (X)
3. JOB_STORAGE_PATH 환경변수를 TTL cleanup 등 전 구간에 적용
4. Chord 표기 정책: 감지는 major/minor만, 수동 입력은 자유 허용
5. 업로드 에러 시: 검증 실패면 job.json 생성 안 함, 처리 중 실패면 job.json 남김

위 5개 수정 후 Momus에게 다시 제출해줘.
```

---

## 프로젝트 개요 (참고)

### 기능
- MP3 업로드 (최대 50MB, 20분)
- YouTube URL 입력
- 멜로디 추출 및 MIDI 변환
- MIDI → MusicXML 변환
- 브라우저 악보 렌더링
- 난이도 조절 (초급/중급/고급)
- BPM/Key/Chord 자동 감지 및 수동 수정

### 기술 스택
- **Backend**: FastAPI (Python 3.11)
- **Frontend**: Next.js 14 (React 18)
- **Audio→MIDI**: Spotify Basic Pitch
- **MIDI→MusicXML**: music21
- **Sheet Rendering**: OpenSheetMusicDisplay
- **Deployment**: Docker Compose

### 주요 설계 결정
- Docker-only 개발 정책 (호스트에서 직접 실행 미지원)
- Next.js API Route Proxy (CORS 회피)
- `asyncio.create_task()` 기반 Job 시스템 (workers=1 필수)
- Golden Test: 핵심 멜로디 recall 85% 기준
