
## [2026-02-04 20:10] Task 1: Docker 환경 업데이트

### 성공 사항
- ✅ CUDA base image로 전환: `nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04`
- ✅ PyTorch 2.0.1 + torchaudio 2.0.2 설치 성공
- ✅ piano-transcription-inference 0.0.6 설치 성공
- ✅ 모델 로딩 확인 (CPU 모드에서 50초)

### 발견된 이슈 및 해결
1. **WSL GPU 문제**
   - 문제: `nvidia-container-cli: initialization error: WSL environment detected but no adapters were found`
   - 해결: docker-compose.yml에서 GPU devices 설정 제거
   - 이유: 개발 환경(WSL)에 GPU가 없지만, 프로덕션에서는 GPU 사용 가능

2. **NumPy 버전 호환성**
   - 문제: NumPy 2.x와 piano_transcription_inference 충돌
   - 해결: requirements.txt에 `numpy<2` 제약 추가
   - 경고 메시지: "A module that was compiled using NumPy 1.x cannot be run in NumPy 2.3.5"

### 파일 변경 내역
- `docker-compose.yml`: GPU 설정 추가 후 제거 (WSL 호환성)
- `backend/Dockerfile`: CUDA base image, Python 3.11 설치, TORCH_HOME 설정
- `backend/requirements.txt`: torch, torchaudio, piano-transcription-inference, numpy<2

### 검증 명령어
```bash
# PyTorch 확인
docker compose run --rm backend python -c "import torch; print('PyTorch:', torch.__version__)"

# piano_transcription_inference 확인
docker compose run --rm backend python -c "from piano_transcription_inference import PianoTranscription; print('OK')"

# 모델 로딩 확인 (CPU)
docker compose run --rm backend python -c "from piano_transcription_inference import PianoTranscription; PianoTranscription(device='cpu')"
```

### GPU vs CPU 모드
- GPU 모드: `device='cuda'` - 프로덕션 환경에서 사용
- CPU 모드: `device='cpu'` - 개발/테스트 환경에서 사용
- 코드에서 자동 선택: `device='cuda' if torch.cuda.is_available() else 'cpu'`


## [2026-02-04 21:32] Task 2: audio_to_midi.py ByteDance 모델로 교체

### 구현 내용
- ✅ ByteDance PianoTranscription으로 완전 교체
- ✅ Device: CPU (WSL 환경) - 자동 선택 로직 구현
- ✅ 처리 시간: ~460초 (CPU 모드, 194초 오디오)
- ✅ MIDI 노트 수: 2242개 (song_01)
- ✅ 멜로디 추출 호환성: 304 노트 추출 성공

### 기술적 선택

1. **librosa 호환성 문제 해결**
   - 문제: `piano_transcription_inference.load_audio()`가 구버전 librosa API 사용
   - 해결: librosa를 직접 사용하여 오디오 로드
   ```python
   audio, sr = librosa.load(str(audio_path), sr=sample_rate, mono=True)
   audio = audio.astype(np.float32)
   ```

2. **싱글톤 패턴 적용**
   - 모델 재로딩 방지를 위한 `_get_transcriptor()` 함수 구현
   - 첫 호출에서만 모델 로드, 이후 재사용

3. **모델 캐시 볼륨 추가**
   - docker-compose.yml에 `piano-model-cache` 볼륨 추가
   - `/root/piano_transcription_inference_data` 경로 마운트
   - 모델 재다운로드 방지 (~164MB)

### 파일 변경 내역
- `backend/core/audio_to_midi.py`: ByteDance 모델로 완전 교체
- `backend/core/audio_to_midi_basic_pitch.py.bak`: 원본 백업
- `docker-compose.yml`: 모델 캐시 볼륨 추가

### 검증 결과
- ✅ 백업 파일 존재
- ✅ MIDI 생성: 2242 notes, 460.4s 처리
- ✅ 멜로디 추출: 304 notes
- ✅ 함수 시그니처: `(audio_path, output_path)` 유지

### 성능 참고
- CPU 모드: ~460초 for 194초 오디오 (2.4배)
- GPU 모드: 예상 ~30-60초 (미확인)

## [2026-02-05 00:20] Phase 2.1: Pitch Class Normalization 완료

### 성과
- ✅ 36.66% 달성 (20.31% → 36.66%, +16.35%p)
- ✅ Phase 2 목표 (25-30%) 초과 달성
- ✅ song_05가 51.40% 달성 (50% threshold 통과)
- ✅ 모든 곡 개선 (회귀 없음)

### 핵심 발견
- ByteDance 모델은 pitch class는 정확하지만 옥타브를 자주 틀림
- Pitch class normalization으로 예상(3-5%p)의 3-5배 개선 (16.35%p)
- song_04, song_05가 가장 큰 개선 (25%p, 28%p)

### 기술적 구현
- `_pitch_to_pitch_class()`: pitch % 12
- `_match_notes_pitch_class()`: 옥타브 무시 매칭
- `compare_note_lists_with_pitch_class()`: 공개 API

### 다음 단계
- Phase 2.2: Onset Quantization (예상 +2-3%p)
- Phase 2.3: DTW 정렬 (예상 +2-3%p)
- Phase 2 완료 후 Phase 3 전환 필요 (85% 목표 달성 위해)

