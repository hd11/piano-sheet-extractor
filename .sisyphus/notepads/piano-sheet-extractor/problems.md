
## [2026-02-03 20:50] Docker 설치 대기 중

**문제**: Docker가 시스템에 설치되어 있지 않음
**영향**: 
- Task 2, 3의 pytest 실행 불가
- 실제 MP3 → MIDI 변환 테스트 불가
- YouTube 다운로드 기능 테스트 불가

**해결 방법**:
- Docker Desktop for Windows 설치 필요
- 설치 후 `docker compose build && docker compose up` 실행

**대안**: 
- 코드 작성은 계속 진행 가능 (Task 4~8)
- Docker 설치 후 전체 Golden Test로 일괄 검증

**상태**: ✅ 해결됨 (Docker 설치 완료)

---

## [2026-02-03 20:58] Docker Desktop 시작 지연

**문제**: Docker Desktop이 시작되는 데 60초 이상 소요
**영향**: 
- Backend 빌드 및 테스트 실행 지연
- Task 2, 3, 4 검증 대기 중

**해결 방법**:
- Docker Desktop이 백그라운드에서 시작 중
- 완전히 시작될 때까지 대기 필요 (보통 1-2분)

**대안**: 
- Task 5 (MIDI → MusicXML 변환) 먼저 구현
- Docker 준비 완료 후 전체 테스트 일괄 실행

**상태**: ✅ 해결됨 (Task 5, 6 완료)

---

## [2026-02-03 21:10] Docker Daemon 500 에러

**문제**: Docker daemon이 완전히 시작되지 않음 (500 Internal Server Error)
- `docker ps`: 500 에러
- `docker compose build`: 500 에러
- `docker compose version`: 정상 작동 (v5.0.1)

**영향**: 
- Backend 빌드 불가
- Task 2, 3, 4 pytest 실행 불가

**해결 방법**:
1. Docker Desktop UI에서 "Engine starting..." 상태 확인
2. 완전히 시작될 때까지 대기 (초록색 아이콘 확인)
3. 또는 Docker Desktop 재시작

**대안**:
- 새 CMD 창에서 OpenCode 재시작 (위 재시작 프롬프트 사용)
- Docker 완전 시작 후 계속 진행

**상태**: 차단요소로 기록됨, 대기 중

**사용자 조치**:
- BIOS에서 AMD-V (SVM Mode) 활성화 필요
- Windows에서 Hyper-V 기능 활성화 필요
- 재부팅 후 Docker Desktop 재실행
- 조치 완료 후 Task 2, 3, 4 테스트 실행 예정

**대안 진행**:
- Task 7 완료 (난이도 조절 시스템)
- Task 8 이후 작업 진행 가능 (Docker 독립적)

