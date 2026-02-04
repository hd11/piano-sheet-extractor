
## [2026-02-04 20:10] Task 1: GPU 설정 이슈

### WSL GPU 미지원
- **문제**: WSL 환경에서 NVIDIA GPU 어댑터 없음
- **에러**: `nvidia-container-cli: initialization error: WSL environment detected but no adapters were found`
- **해결**: docker-compose.yml에서 GPU devices 설정 제거
- **영향**: 개발 환경에서는 CPU 모드로만 동작
- **프로덕션**: GPU 있는 환경에서는 코드 레벨에서 자동 선택 (`torch.cuda.is_available()`)

### NumPy 2.x 호환성 문제
- **문제**: piano_transcription_inference가 NumPy 1.x로 컴파일됨
- **해결**: `numpy<2` 제약 추가
- **상태**: 해결됨

