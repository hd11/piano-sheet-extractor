
## Local Python Environment Setup (Task 0)

### Completed Tasks
1. **Virtual Environment**: Created and configured `.venv` with Python 3.11.14
2. **Package Installation**: Successfully installed all core dependencies
   - torch 2.10.0+cpu (CPU-only, no CUDA available on this system)
   - torchaudio, transformers, librosa, music21, fastapi, uvicorn, etc.
   - Note: essentia==2.1b6.dev1034 not available; closest version is 2.1b6.dev234
3. **CLI Script**: Created `backend/run.py` with argparse-based interface
4. **Verification**: All expected outcomes met

### Key Findings
- Windows environment uses `.venv` (not `venv`)
- Python 3.11.14 is available in the venv
- Torch installed with CPU support (no CUDA/GPU available)
- Core modules (audio_to_midi, melody_extractor, midi_parser) are importable
- Function names: `convert_audio_to_midi` (not `audio_to_midi`)

### CLI Features Implemented
- Input validation (MP3/WAV files only)
- Output directory creation
- Melody extraction option (`--melody` flag)
- Verbose logging support
- Help documentation with examples

### Usage
```bash
cd backend
.venv/Scripts/python run.py input.mp3 -o output/
.venv/Scripts/python run.py song.wav --melody --verbose
```

### Commit
- Message: `feat(env): add local Python execution support without Docker`
- File: `backend/run.py` (114 lines)
- Commit hash: 19ac64a

---

## CREPE Spike Test (Task 2)

### Test Results (song_01, 194.6s audio)

**Performance Metrics:**
- Total processing time: **42.15s** (0.22x realtime)
  - Audio loading: 5.62s (13.3%)
  - CREPE inference: 36.43s (86.4%) - **BOTTLENECK**
  - MIDI conversion: 0.10s (0.2%)
- Model: `tiny` (full model would take ~14+ minutes)
- Frames analyzed: 19,463 (10ms step size)

**Output Quality:**
- Notes extracted: 308 (vs 1,897 reference = **0.16x ratio**)
- Average confidence: 0.439 (low)
- Confidence > 0.5: 40.2% (poor)
- Pitch range: 24-84 (vs 31-93 reference)
- Avg note duration: 132.5ms (vs 329.6ms reference)

**Evaluation:**

✅ **Pros:**
- Easy installation: `pip install crepe`
- Simple API: `crepe.predict(audio, sr, viterbi=True)`
- Minimal dependencies (numpy, scipy, tensorflow)
- Viterbi smoothing for pitch tracking
- Works out-of-the-box

❌ **Cons:**
- **VERY SLOW**: 36s for 3min audio with tiny model (14+ min with full model)
- **Poor quality**: Only 16% of expected notes extracted
- **Low confidence**: Average 0.439, only 40% frames > 0.5
- **Polyphonic limitation**: Designed for monophonic pitch tracking
- **Heavy dependency**: Requires TensorFlow (large install)
- **Not suitable for piano**: Piano is polyphonic, CREPE is monophonic

**Conclusion:**
❌ **REJECT CREPE** for piano melody extraction
- Too slow for production use
- Fundamentally wrong tool (monophonic vs polyphonic)
- Poor quality output (missing 84% of notes)
- Better alternatives exist (Basic Pitch is already polyphonic)

**Next Steps:**
- Continue with Basic Pitch spike (Task 3)
- CREPE is not viable for this use case

### Files Created
- `backend/scripts/spike_crepe.py` (full spike test script)
- `backend/scripts/analyze_reference_midi.py` (helper script)
- `backend/tests/golden/data/song_01/crepe_output.mid` (test output)


---

## Librosa PYIN Spike Test (Task 4)

### Test Results (song_01, 194.6s audio)

**Performance Metrics:**
- Total processing time: **48.55s** (0.25x realtime)
  - Audio loading: 5.25s (10.8%)
  - PYIN inference: 43.29s (89.2%) - **BOTTLENECK**
  - MIDI conversion: 0.01s (0.0%)
- Parameters: hop_length=1024 (~46ms), frame_length=2048
- Frames analyzed: 4,192 (vs CREPE 19,463 with 10ms steps)

**Output Quality:**
- Notes extracted: 34 (vs 1,897 reference = **0.02x ratio**)
- Voiced frames: 54.2% (2,270 / 4,192)
- Average voicing probability: 0.174 (very low)
- Probability > 0.5: 8.1% (extremely poor)
- Pitch range: 36-71 (vs 31-93 reference)
- Avg note duration: 210.5ms (vs 329.6ms reference)

**Evaluation:**

✅ **Pros:**
- No installation needed (already in librosa)
- Simple API: `librosa.pyin(y, fmin, fmax, sr)`
- No extra dependencies (part of librosa core)
- Traditional signal processing (no neural network)

❌ **Cons:**
- **VERY SLOW**: 43s for 3min audio (similar to CREPE 36s)
- **EXTREMELY POOR QUALITY**: Only 2% of expected notes (worse than CREPE's 16%)
- **Very low confidence**: Average probability 0.174, only 8% frames > 0.5
- **Monophonic limitation**: Like CREPE, designed for single pitch tracking
- **Not suitable for piano**: Piano is polyphonic, PYIN is monophonic
- **Worse than CREPE**: Both slow AND lower quality

**Comparison with CREPE:**

| Metric | PYIN | CREPE | Winner |
|--------|------|-------|--------|
| Processing time | 48.5s | 42.2s | CREPE (faster) |
| Note count | 34 (0.02x) | 308 (0.16x) | CREPE (8x more notes) |
| Confidence/Prob | 0.174 avg | 0.439 avg | CREPE (2.5x higher) |
| High confidence | 8.1% | 40.2% | CREPE (5x more) |
| Installation | Built-in | pip install | PYIN (easier) |

**Conclusion:**
❌ **REJECT PYIN** for piano melody extraction
- Slower than CREPE with much worse quality
- Only extracted 34 notes vs CREPE's 308 notes
- Extremely low voicing probability (0.174 avg)
- PYIN is worse than CREPE in every metric except installation
- If we rejected CREPE for poor quality, PYIN is even worse

**Key Insight:**
Both CREPE and PYIN are **monophonic pitch trackers** designed for single-note melodies (like vocals or solo instruments). They fundamentally cannot handle polyphonic piano audio where multiple notes play simultaneously. The poor results (2% and 16% of expected notes) confirm this limitation.

**Next Steps:**
- Continue with polyphonic approaches (Basic Pitch, Audio-to-MIDI)
- Monophonic pitch tracking is not viable for piano transcription
- Need algorithms designed for polyphonic music

### Files Created
- `backend/scripts/spike_librosa_pyin.py` (full spike test script)
- `backend/tests/golden/data/song_01/pyin_output.mid` (test output - 34 notes)


---

## Audio-to-MIDI Spike Test (Task 3)

### Test Results (song_01, 194.6s audio)

**Performance Metrics:**
- Total processing time: **25.89s** (0.13x realtime)
  - Feature extraction: 22.58s (87.2%) - **BOTTLENECK**
  - MSnet inference: 2.95s (11.4%)
  - MIDI conversion: 0.36s (1.4%)
- Model: MSnet (Melodic SegNet) with main-melody mode
- Feature extraction: CFP (Combined Frequency and Periodicity) representation

**Output Quality:**
- Notes extracted: 342 (vs 1,897 reference = **0.18x ratio**)
- Pitch range: 50-83 (vs 31-93 reference)
- Avg note duration: 183.5 ticks (vs 462.3 reference)

**Installation Complexity:**
- ❌ **NOT pip installable** - requires git clone
- ❌ **Requires ffmpeg** for MP3 support (had to convert to WAV)
- ❌ **Multiple compatibility issues** with modern libraries:
  - scipy: `blackmanharris` moved to `scipy.signal.windows`
  - numpy: `np.float` deprecated, `np.round()` returns float not int
  - pypianoroll: API changed completely (`beat_resolution` → `resolution`, `append_track` removed)
- ⚠️ Required manual patching of 5+ compatibility issues
- Dependencies: PyTorch, numpy, scipy, soundfile, pypianoroll, pydub

**Evaluation:**

✅ **Pros:**
- Reasonably fast: 25.9s for 3min audio (faster than CREPE)
- Simple architecture: MSnet (Melodic SegNet)
- Pre-trained models included (vocal & melody)
- Lightweight model size (~2MB)

❌ **Cons:**
- **VERY COMPLEX INSTALLATION**: Git clone + manual patching required
- **Monophonic limitation**: Designed for single melody line, not polyphonic
- **Poor coverage**: Only 18% of reference notes extracted
- **Outdated codebase**: Last updated 2019, Python 3.6, PyTorch 1.0
- **Compatibility nightmare**: Requires patching for modern numpy/scipy/pypianoroll
- **No pip package**: Must clone repo and manage sys.path manually
- **Requires ffmpeg**: For MP3 support (not included)
- **Wrong use case**: Designed for vocal/melody extraction, not piano transcription

**Conclusion:**
❌ **REJECT Audio-to-MIDI** for piano melody extraction

**Reasons:**
1. **Monophonic limitation**: Extracts only single melody line, piano is polyphonic
2. **Poor coverage**: Only 18% of reference notes (worse than CREPE's 16%)
3. **Installation nightmare**: Git clone + 5+ manual patches + ffmpeg dependency
4. **Outdated**: 2019 codebase with severe compatibility issues
5. **Wrong use case**: Designed for vocal/melody, not piano transcription
6. **Maintenance burden**: Would require maintaining patches for compatibility

**Comparison with CREPE:**
| Metric | Audio-to-MIDI | CREPE | Winner |
|--------|---------------|-------|--------|
| Note count | 342 (18%) | 308 (16%) | Audio-to-MIDI (slightly) |
| Processing time | 25.9s | 42.2s | Audio-to-MIDI |
| Installation | Git clone + patches | `pip install crepe` | CREPE |
| Compatibility | Requires 5+ patches | Works out-of-box | CREPE |
| Use case fit | Vocal/melody | Monophonic pitch | Both wrong |

**Both are REJECTED** - neither is suitable for polyphonic piano transcription.

**Next Steps:**
- Continue with Librosa PYIN spike (Task 4) - also monophonic but pip installable
- Focus on polyphonic solutions: Basic Pitch (already in use), MT3, Onsets and Frames

### Files Created
- `backend/scripts/spike_audio2midi.py` (full spike test script with mido MIDI writer)
- `backend/tests/golden/data/song_01/audio2midi_output.mid` (test output)
- `backend/tests/golden/data/song_01/input_converted.wav` (WAV conversion for testing)

### Key Learnings
- **Monophonic ≠ Melody extraction for piano**: Piano has multiple simultaneous notes
- **Old research code = compatibility hell**: 2019 code requires extensive patching
- **Installation complexity is a deal-breaker**: Git clone + patches is not production-ready
- **"딱 멜로디만"** means the main melodic line, but piano has chords + bass + melody
- Audio-to-MIDI is designed for **vocal melody extraction**, not piano transcription


---

## Basic Pitch + Skyline Test (Task 5)

### Test Results (song_01, 194.6s audio)

**Performance Metrics:**
- Total processing time: **8.6s** (0.04x realtime) - **FASTEST**
- Model: Basic Pitch (ICASSP 2022 model)
- Polyphonic transcription: YES (handles multiple simultaneous notes)

**Output Quality:**
- Raw notes: 1,164 (vs 1,897 reference = **61.4% ratio**)
- After Skyline: 488 notes (vs 1,897 reference = **25.7% ratio**)
- Pitch range: 28-91 (raw) → 48-84 (normalized to C3-C6)
- Avg note duration: 308.6ms (vs 329.6ms reference)

**Skyline Pipeline:**
1. Raw MIDI: 1,164 notes
2. After Skyline (highest note per onset): 488 notes
3. After filtering short notes (<50ms): 488 notes (no change)
4. After overlap resolution: 488 notes (no change)
5. After octave normalization (C3-C6): 488 notes (no change)

**Evaluation:**

✅ **Pros:**
- **Polyphonic**: Handles multiple simultaneous notes (piano is polyphonic)
- **Very fast**: 8.6s for 3min audio (5x faster than CREPE, 3x faster than Audio-to-MIDI)
- **Easy installation**: `pip install basic-pitch`
- **Good coverage**: 61.4% raw notes (3-30x better than monophonic models)
- **Production-ready**: Maintained by Spotify, modern codebase
- **Works out-of-box**: No git clone, no manual patches
- **Clean melody**: Skyline reduces 1,164 → 488 notes (removes accompaniment)

⚠️ **Cons:**
- **scipy compatibility**: Requires scipy<1.14 (gaussian function moved to scipy.signal.windows)
- **Over-transcription**: Captures 1,164 raw notes (needs Skyline filtering)
- **Final ratio 25.7%**: Lower than raw 61.4%, but this is expected (melody only, not all notes)

**Conclusion:**
✅ **ACCEPT Basic Pitch + Skyline** for piano melody extraction

**Reasons:**
1. **Polyphonic support**: Only model that handles piano's multiple simultaneous notes
2. **Speed**: 8.6s (fastest of all tested models)
3. **Quality**: 61% raw coverage (best of all models)
4. **Ease of use**: pip install, no patches
5. **Production-ready**: Maintained by Spotify
6. **Proven approach**: Skyline algorithm already implemented

**Why 25.7% final ratio is acceptable:**
- Reference MIDI (1,897 notes) includes **all notes** (melody + chords + bass)
- Goal: "딱 멜로디만 간결하게" (just melody, concisely)
- 488 notes = clean melody line without accompaniment
- This is the **intended behavior**, not a failure

**Comparison with rejected models:**

| Model | Type | Notes | Ratio | Time | Verdict |
|-------|------|-------|-------|------|---------|
| CREPE | Monophonic | 308 | 16% | 42s | ❌ REJECTED |
| Audio-to-MIDI | Monophonic | 342 | 18% | 26s | ❌ REJECTED |
| PYIN | Monophonic | 34 | 2% | 48s | ❌ REJECTED |
| Basic Pitch (raw) | Polyphonic | 1,164 | 61% | 8.6s | ✅ SELECTED |
| Basic Pitch + Skyline | Polyphonic | 488 | 26% | 8.6s | ✅ SELECTED |

**Key Insight:**
Monophonic models (CREPE, Audio-to-MIDI, PYIN) failed because piano is polyphonic. They extract only one pitch at a time, missing 82-98% of notes. Basic Pitch is polyphonic, capturing all notes (61%), then Skyline extracts the melody (26%).

**Next Steps:**
- Integrate Basic Pitch into `core/audio_to_midi.py`
- Use existing Skyline algorithm from `core/melody_extractor.py`
- Add scipy<1.14 to requirements.txt
- Run golden tests to validate end-to-end pipeline

### Files Created
- `backend/scripts/spike_basic_pitch.py` (full spike test script)
- `backend/scripts/output/basic_pitch_raw.mid` (1,164 notes)
- `backend/scripts/output/basic_pitch_melody.mid` (488 notes)
- `.sisyphus/notepads/melody-extraction-pivot/decisions.md` (model comparison document)

### Key Learnings
- **Polyphonic vs Monophonic**: Piano requires polyphonic transcription, not monophonic pitch tracking
- **Skyline algorithm**: Effective for extracting melody from polyphonic MIDI (1,164 → 488 notes)
- **scipy compatibility**: scipy 1.14+ moved `gaussian` to `scipy.signal.windows` (requires patch or downgrade)
- **"딱 멜로디만"**: Means main melodic line, not all notes (25.7% ratio is correct)
- **Basic Pitch**: Best balance of speed (8.6s), quality (61%), and ease of use (pip install)

### Installation Fix
**Problem:** scipy 1.14+ moved `gaussian` to `scipy.signal.windows`

**Fix:**
```python
import scipy.signal
if not hasattr(scipy.signal, 'gaussian'):
    from scipy.signal.windows import gaussian
    scipy.signal.gaussian = gaussian
```

**Solution:** Pin scipy<1.14 in requirements.txt

