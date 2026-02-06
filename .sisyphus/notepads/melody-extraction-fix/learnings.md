# Learnings - Melody Extraction Fix

## Task 1: WSL 환경 설정 및 Essentia 설치

### Key Findings

1. **WSL2 Already Installed**
   - WSL version: 2.6.2.0
   - Kernel version: 6.6.87.2-1
   - No additional WSL2 installation needed

2. **Ubuntu Packages Already Present**
   - python3-pip: Already installed (24.0+dfsg-1ubuntu1.3)
   - python3-dev: Already installed (3.12.3-0ubuntu2.1)
   - ffmpeg: Already installed (7:6.1.1-3ubuntu5)
   - All dependencies were pre-installed in the WSL environment

3. **Essentia Installation**
   - Initial pip3 install failed with "externally-managed-environment" error
   - Solution: Used `--break-system-packages` flag to override PEP 668 restrictions
   - Successfully installed: essentia-2.1b6.dev1389 (cp312 wheel)
   - Dependencies: numpy>=1.25, pyyaml, six (all satisfied)

4. **MP3 Loading Success**
   - Essentia MonoLoader can load MP3 files directly without ffmpeg conversion
   - Test file: song_01/input.mp3 (8.2 MB, ~194.63 seconds)
   - Audio shape: (8583168,) samples at 44100 Hz
   - No ffmpeg fallback needed for this test case

### Technical Details

- **Essentia Version**: 2.1-beta6-dev
- **FFmpeg Version**: 6.1.1-3ubuntu5 (with comprehensive codec support)
- **Python Version**: 3.12
- **Ubuntu Version**: Noble (24.04 LTS)

### Workflow Notes

- WSL path conversion: Windows `C:\Users\...` → WSL `/mnt/c/Users/...`
- Essentia MonoLoader automatically handles MP3 decoding via libavformat
- No additional audio codec installation required

### Blockers Resolved

- ✅ PEP 668 externally-managed-environment restriction
- ✅ MP3 decoding capability verified
- ✅ All dependencies satisfied

### Next Steps

- Task 3 and 4 can now proceed with Essentia installed
- MP3 loading is confirmed working, no ffmpeg conversion needed for basic cases
- Consider ffmpeg conversion for edge cases or specific audio formats

## Task 3: Essentia Spike Test

### Essentia Integration Pattern
- **WSL Subprocess**: Use `wsl.exe` (not `wsl`) to avoid Git Bash path mangling
- **Path Conversion**: Windows `C:\...` → WSL `/mnt/c/...`
- **Communication**: JSON via stdout, errors via stderr
- **Timeout**: 5 minutes for ~3min audio file

### Essentia PredominantPitchMelodia Characteristics
- **Confidence Range**: Typically 0.0 - 0.6 (NOT 0.0 - 1.0)
- **Optimal Threshold**: 0.3 (not 0.8 as initially assumed)
- **Frame Rate**: 128 samples hop size @ 44.1kHz = ~344 fps
- **Output**: Pitch (Hz) + confidence per frame

### Performance Comparison (song_01)
| Method | Notes | Similarity | Pitch Range |
|--------|-------|------------|-------------|
| Reference | 584 | - | 62-84 |
| Essentia | 185 | 17.98% | 54-83 |
| Skyline | 527 | 42.98% | 48-84 |

**Conclusion**: Skyline (Basic Pitch + post-processing) outperforms Essentia by 25%

### Why Essentia Underperforms
1. **Too Conservative**: Confidence threshold filters out valid notes
2. **Fewer Notes**: 185 vs 527 (31% of Skyline)
3. **Monophonic Focus**: Essentia designed for single melody line
4. **Basic Pitch Advantage**: Trained on piano data, better polyphonic handling

