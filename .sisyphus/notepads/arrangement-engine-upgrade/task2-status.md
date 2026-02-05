# Task 2 Status: Pop2Piano Integration Testing

## Date: 2026-02-05

### Code Status: ✅ COMPLETE
All Pop2Piano integration code has been written:
- `backend/core/audio_to_midi.py` - Pop2Piano implementation (185 lines)
- `backend/core/audio_to_midi_bytedance.py.bak` - ByteDance backup
- `backend/requirements.txt` - Updated with transformers>=4.35.0, torch>=2.2.0, torchaudio>=2.2.0
- `backend/Dockerfile` - Updated to use pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

### Testing Status: ⏸️ BLOCKED
Docker Desktop is experiencing stability issues:
- Multiple crashes during container rebuild
- 500 Internal Server Error when connecting to Docker daemon
- Attempted restarts not resolving the issue

### Changes Made to Fix PyTorch Compatibility

#### 1. requirements.txt
```diff
- torch==2.0.1
- torchaudio==2.0.2
+ torch>=2.2.0
+ torchaudio>=2.2.0
+ transformers>=4.35.0
```

#### 2. Dockerfile
```diff
- FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
+ FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

- # Install Python 3.11 and required tools
- RUN apt-get update && apt-get install -y \
-     python3.11 \
-     python3.11-venv \
-     python3.11-dev \
-     python3-pip \
+ # Install system dependencies
+ RUN apt-get update && apt-get install -y \
```

**Rationale**: Pop2Piano requires PyTorch >= 2.2, which requires CUDA 12.x. Using pre-built PyTorch image simplifies setup.

### Next Steps (When Docker is Stable)

1. **Rebuild container**:
   ```bash
   docker compose build backend
   ```

2. **Test Pop2Piano import**:
   ```bash
   docker compose run --rm backend python -c "
   from transformers import Pop2PianoForConditionalGeneration, Pop2PianoProcessor
   print('Pop2Piano Import OK')
   "
   ```

3. **Test MIDI generation**:
   ```bash
   docker compose run --rm backend python -c "
   from pathlib import Path
   from core.audio_to_midi import convert_audio_to_midi
   result = convert_audio_to_midi(
       Path('tests/golden/data/song_01/input.mp3'),
       Path('/tmp/test.mid')
   )
   print(f'Notes: {result[\"note_count\"]}')
   assert result['note_count'] > 0
   "
   ```

4. **Commit if tests pass**:
   ```bash
   git add backend/core/audio_to_midi.py backend/core/audio_to_midi_bytedance.py.bak backend/requirements.txt backend/Dockerfile
   git commit -m "feat(core): replace ByteDance with Pop2Piano for piano arrangement generation"
   git push
   ```

### Docker Troubleshooting Attempted
- ✗ Restart Docker Desktop (multiple times)
- ✗ Force kill and restart
- ✗ Wait for daemon to stabilize (>5 minutes)
- ⏸️ System reboot may be required

### Recommendation
1. Reboot system to fully reset Docker Desktop
2. OR: Test on a different machine/environment
3. OR: Use GitHub Actions CI to test in clean environment

