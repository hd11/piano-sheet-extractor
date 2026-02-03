# E2E 테스트 가이드

## 개요

본 프로젝트의 E2E 테스트는 **Playwright MCP (Model Context Protocol)**를 사용합니다.

- 전통적인 `*.spec.ts` 파일 대신, AI 에이전트가 MCP 도구를 직접 호출
- 테스트 시나리오는 문서로 정의하고, 실행은 대화형으로 수행
- 스크린샷과 스냅샷으로 결과 검증

## 사전 준비

### 1. 시스템 실행

```bash
# Docker Compose로 전체 시스템 시작
docker compose up -d

# 서비스 상태 확인
docker compose ps

# 백엔드 헬스체크
curl http://localhost:8000/

# 프론트엔드 접속
curl http://localhost:3000/
```

### 2. 테스트 오디오 생성

```bash
# Docker 컨테이너 내부에서 실행
docker compose exec backend python scripts/generate_test_audio.py

# 생성된 파일 확인
docker compose exec backend ls -lh tests/fixtures/test_audio.mp3
```

## 테스트 시나리오

### 시나리오 1: MP3 업로드 → 처리 → 결과 확인

**목적**: 파일 업로드부터 악보 렌더링까지 전체 플로우 검증

**단계**:
1. `browser_navigate`: http://localhost:3000
2. `browser_snapshot`: 초기 화면 확인
3. `browser_file_upload`: tests/fixtures/test_audio.mp3 업로드
4. `browser_snapshot`: 업로드 후 상태 확인
5. `browser_wait_for`: 처리 완료 대기 (progress 100% 또는 완료 메시지)
6. `browser_snapshot`: 결과 화면 확인
7. `browser_click`: 악보 렌더링 영역 확인
8. `browser_take_screenshot`: 최종 결과 스크린샷 저장

**검증 포인트**:
- [ ] 파일 업로드 UI가 정상 표시되는가
- [ ] 업로드 후 진행률이 표시되는가
- [ ] 처리 완료 후 악보가 렌더링되는가
- [ ] 다운로드 버튼이 활성화되는가

### 시나리오 2: 난이도 변경

**목적**: 난이도 선택 기능 검증

**단계**:
1. (시나리오 1 완료 후)
2. `browser_snapshot`: 현재 상태 확인
3. `browser_click`: 난이도 선택 UI
4. `browser_click`: "초급" 선택
5. `browser_wait_for`: 악보 변경 대기
6. `browser_snapshot`: 초급 악보 확인
7. `browser_click`: "고급" 선택
8. `browser_wait_for`: 악보 변경 대기
9. `browser_snapshot`: 고급 악보 확인

**검증 포인트**:
- [ ] 난이도 선택 UI가 동작하는가
- [ ] 난이도 변경 시 악보가 업데이트되는가
- [ ] 초급 악보가 고급보다 단순한가

### 시나리오 3: BPM/Key 수정

**목적**: 분석 결과 수정 및 재생성 기능 검증

**단계**:
1. (시나리오 1 완료 후)
2. `browser_snapshot`: 현재 분석 결과 확인
3. `browser_click`: BPM 입력 필드
4. `browser_type`: 새 BPM 값 입력 (예: 140)
5. `browser_click`: 저장/적용 버튼
6. `browser_wait_for`: 재생성 완료 대기
7. `browser_snapshot`: 변경된 결과 확인

**검증 포인트**:
- [ ] BPM/Key 수정 UI가 동작하는가
- [ ] 수정 후 재생성이 트리거되는가
- [ ] 재생성 완료 후 악보가 업데이트되는가

### 시나리오 4: MIDI/MusicXML 다운로드

**목적**: 파일 다운로드 기능 검증

**단계**:
1. (시나리오 1 완료 후)
2. `browser_click`: "MIDI 다운로드" 버튼
3. `browser_wait_for`: 다운로드 완료 대기
4. `browser_click`: "MusicXML 다운로드" 버튼
5. `browser_wait_for`: 다운로드 완료 대기

**검증 포인트**:
- [ ] 다운로드 버튼이 클릭 가능한가
- [ ] 파일이 다운로드되는가 (브라우저 다운로드 폴더 확인)
- [ ] 파일명이 올바른 형식인가 (`{name}_{difficulty}.{ext}`)

### 시나리오 5: YouTube URL 입력

**목적**: YouTube URL 입력 및 처리 검증

**단계**:
1. `browser_navigate`: http://localhost:3000
2. `browser_click`: "YouTube URL" 탭
3. `browser_type`: YouTube URL 입력 (짧은 영상 권장)
4. `browser_click`: 제출 버튼
5. `browser_wait_for`: 다운로드 및 처리 완료 대기
6. `browser_snapshot`: 결과 확인

**검증 포인트**:
- [ ] YouTube URL 입력 UI가 동작하는가
- [ ] 유효하지 않은 URL에 대한 에러 메시지가 표시되는가
- [ ] 처리 완료 후 악보가 렌더링되는가

## 실행 방법

### Playwright MCP 도구 사용

AI 에이전트에게 다음과 같이 요청:

```
"Piano Sheet Extractor의 E2E 테스트를 실행해주세요.
시나리오 1부터 5까지 순차적으로 실행하고,
각 단계마다 스크린샷을 저장해주세요."
```

에이전트는 자동으로:
1. 브라우저를 열고 (Playwright MCP)
2. 각 시나리오의 단계를 실행하며
3. 스크린샷과 스냅샷을 저장하고
4. 검증 포인트를 확인합니다

### 수동 테스트

브라우저에서 직접 테스트:

1. http://localhost:3000 접속
2. 위 시나리오를 수동으로 실행
3. 각 검증 포인트 확인

## 트러블슈팅

### 서비스가 시작되지 않음

```bash
# 로그 확인
docker compose logs backend
docker compose logs frontend

# 컨테이너 재시작
docker compose restart
```

### 테스트 오디오가 생성되지 않음

```bash
# ffmpeg 설치 확인
docker compose exec backend which ffmpeg

# scipy 설치 확인
docker compose exec backend python -c "import scipy; print(scipy.__version__)"
```

### 업로드가 실패함

- 파일 크기 확인 (50MB 이하)
- 파일 형식 확인 (MP3, WAV)
- 백엔드 로그 확인

## 참고 자료

- [Playwright MCP Documentation](https://github.com/microsoft/playwright)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
