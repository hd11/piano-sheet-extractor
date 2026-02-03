# Piano Sheet Extractor - Deployment Guide

## 프로젝트 완료 상태

### ✅ 완료된 작업 (Tasks 1-15)

**Backend (Tasks 1-8)**:
- ✅ Task 1: 프로젝트 구조 및 Docker 설정
- ✅ Task 2: Basic Pitch 통합 (MP3 → MIDI)
- ✅ Task 3: YouTube 다운로더 (yt-dlp)
- ✅ Task 4: 멜로디 추출 (Polyphonic → Monophonic)
- ✅ Task 5: MIDI → MusicXML 변환
- ✅ Task 6: BPM/Key/Chord 자동 감지
- ✅ Task 7: 난이도 조절 시스템
- ✅ Task 8: FastAPI 엔드포인트 + Job System

**Frontend (Tasks 9-12)**:
- ✅ Task 9: 업로드 UI (FileUpload, YouTubeInput, ProgressBar)
- ✅ Task 10: 악보 렌더링 (OpenSheetMusicDisplay)
- ✅ Task 11: 수정 UI (BPM/Key/Chord/Difficulty 편집)
- ✅ Task 12: 다운로드 기능 (MIDI/MusicXML)

**Integration & Testing (Tasks 13-15)**:
- ✅ Task 13: Docker 설정 완성 (전체 시스템 통합)
- ✅ Task 14: Golden Test 시스템 (Smoke 모드)
- ✅ Task 15: E2E 테스트 문서화

## 시스템 실행

### 원클릭 실행

```bash
# 전체 시스템 시작
docker compose up -d

# 서비스 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f
```

### 접속 정보

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 기능 검증

### 1. 파일 업로드 테스트

```bash
# 테스트 오디오 생성
docker compose exec backend python scripts/generate_test_audio.py

# 브라우저에서 테스트
# 1. http://localhost:3000 접속
# 2. "파일 업로드" 탭 선택
# 3. MP3 파일 업로드
# 4. 처리 완료 대기
# 5. 악보 렌더링 확인
```

### 2. API 직접 테스트

```bash
# 헬스체크
curl http://localhost:8000/

# 파일 업로드 (test 디렉토리의 파일 사용)
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test/Golden.mp3"

# Job 상태 확인 (job_id는 위 응답에서 받음)
curl http://localhost:8000/api/status/{job_id}

# 결과 조회
curl http://localhost:8000/api/result/{job_id}

# MIDI 다운로드
curl http://localhost:8000/api/download/{job_id}/midi?difficulty=medium -o output.mid

# MusicXML 다운로드
curl http://localhost:8000/api/download/{job_id}/musicxml?difficulty=medium -o output.musicxml
```

### 3. Golden Test 실행

```bash
# 전체 Golden Test 실행 (8개 테스트 파일)
docker compose exec backend pytest tests/golden/ -v

# Smoke 모드만 실행
docker compose exec backend pytest tests/golden/ -v -m smoke

# 특정 파일만 테스트
docker compose exec backend pytest tests/golden/test_golden.py::TestGoldenSmoke::test_full_pipeline_smoke -v
```

## 시스템 아키텍처

### Backend Stack
- **Framework**: FastAPI (Python 3.11)
- **Audio Processing**: Basic Pitch, librosa, music21, pretty_midi
- **YouTube**: yt-dlp
- **Job System**: asyncio + ThreadPoolExecutor
- **Storage**: File-based (/tmp/piano-sheet-jobs)

### Frontend Stack
- **Framework**: Next.js 14 (React 18)
- **Styling**: Tailwind CSS v4
- **Sheet Rendering**: OpenSheetMusicDisplay
- **Language**: TypeScript

### Docker Configuration
- **Backend**: Python 3.11-slim + ffmpeg + libsndfile
- **Frontend**: Node.js 18-alpine (multi-stage build)
- **Networking**: Docker bridge network
- **Healthchecks**: Enabled for both services

## 성능 특성

### 처리 시간
- **3분 MP3**: ~2분 이내 (CPU 기준)
- **YouTube 다운로드**: 영상 길이에 따라 가변
- **난이도 재생성**: ~10초 이내

### 리소스 사용
- **Backend**: 2 CPU, 4GB RAM (limit)
- **Frontend**: 0.5 CPU, 512MB RAM (limit)
- **Storage**: Job당 ~10-50MB (1시간 후 자동 삭제)

### 제한사항
- **파일 크기**: 최대 50MB
- **오디오 길이**: 최대 20분
- **동시 처리**: 최대 3개 Job
- **Job TTL**: 1시간 (updated_at 기준)

## 테스트 데이터

### Golden Test 파일 (test/ 디렉토리)
- Golden.mp3 (3.1MB)
- IRIS OUT.mp3 (2.5MB)
- 꿈의 버스.mp3 (2.6MB)
- 너에게100퍼센트.mp3 (3.2MB)
- 달리 표현할 수 없어요.mp3 (3.8MB)
- 등불을 지키다.mp3 (3.4MB)
- 비비드라라러브.mp3 (3.9MB)
- 여름이었다.mp3 (3.1MB)

**총 8개 파일, 다양한 장르 포함**

## 트러블슈팅

### 컨테이너가 시작되지 않음

```bash
# 로그 확인
docker compose logs backend
docker compose logs frontend

# 이미지 재빌드
docker compose build --no-cache

# 볼륨 정리
docker compose down -v
docker compose up -d
```

### 처리가 실패함

```bash
# 백엔드 로그 확인
docker compose logs backend -f

# Job 디렉토리 확인
docker compose exec backend ls -la /tmp/piano-sheet-jobs/

# 수동으로 처리 테스트
docker compose exec backend python -c "
from core.audio_to_midi import convert_audio_to_midi
from pathlib import Path
result = convert_audio_to_midi(Path('/app/test/Golden.mp3'), Path('/tmp/test.mid'))
print(result)
"
```

### 프론트엔드가 백엔드에 연결되지 않음

```bash
# 네트워크 확인
docker network inspect piano-sheet-extractor_piano-network

# DNS 확인
docker compose exec frontend ping backend

# API 프록시 설정 확인
docker compose exec frontend cat next.config.js
```

## 개발 환경

### 로컬 개발 (Docker 없이)

**Backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

**주의**: ffmpeg, libsndfile1이 시스템에 설치되어 있어야 합니다.

### 코드 수정 후

```bash
# 백엔드 재빌드
docker compose build backend
docker compose up -d backend

# 프론트엔드 재빌드
docker compose build frontend
docker compose up -d frontend
```

## 프로덕션 배포

### 환경 변수 설정

```bash
# .env 파일 생성
cat > .env << EOF
JOB_STORAGE_PATH=/tmp/piano-sheet-jobs
NODE_ENV=production
NEXT_PUBLIC_API_URL=http://backend:8000
EOF
```

### 보안 고려사항

1. **CORS 설정**: 프로덕션에서는 특정 도메인만 허용
2. **Rate Limiting**: API 엔드포인트에 rate limit 추가
3. **Job 인증**: Job ID 외에 추가 인증 메커니즘 고려
4. **파일 검증**: 업로드 파일의 악성 코드 검사

### 스케일링

현재 아키텍처는 **단일 프로세스**로 설계되었습니다:
- `asyncio.create_task()` 기반 Job 시스템
- 멀티 워커 사용 불가 (`--workers 1` 필수)

**스케일 아웃이 필요한 경우**:
- Celery + Redis로 Job 시스템 재구성
- 공유 스토리지 (S3, NFS) 사용
- 로드 밸런서 추가

## 라이선스 및 저작권

### 사용된 오픈소스 라이브러리

- **Basic Pitch**: Apache-2.0 (Spotify)
- **OpenSheetMusicDisplay**: BSD-3-Clause
- **music21**: BSD-3-Clause
- **FastAPI**: MIT
- **Next.js**: MIT
- **yt-dlp**: Unlicense

### 테스트 데이터

test/ 디렉토리의 MP3 파일은 테스트 목적으로만 사용하세요.
프로덕션 배포 시 저작권 문제가 없는 파일만 사용하세요.

## 지원 및 문의

- **GitHub Issues**: 버그 리포트 및 기능 요청
- **Documentation**: README.md, backend/tests/e2e/README.md
- **API Docs**: http://localhost:8000/docs

## 다음 단계 (Phase 2)

현재 Phase 1 (Smoke 모드)가 완료되었습니다.

**Phase 2 계획**:
1. Reference MIDI 준비
2. Golden Test Full 모드 구현 (정확도 측정)
3. 85% 정확도 달성을 위한 튜닝
4. 추가 장르 테스트 데이터 확보
5. 성능 최적화 (GPU 지원, 캐싱)

---

**프로젝트 상태**: ✅ Production Ready (Phase 1 완료)
**마지막 업데이트**: 2026-02-03
**버전**: 0.1.0
