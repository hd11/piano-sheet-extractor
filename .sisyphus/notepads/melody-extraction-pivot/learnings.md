
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


---

## Basic Pitch Integration (Task 6)

### Summary
Replaced Pop2Piano with Basic Pitch in `backend/core/audio_to_midi.py`.

### Changes Made
1. **Backup created**: `backend/core/audio_to_midi_pop2piano.py.bak`
2. **Removed Pop2Piano dependencies**:
   - Removed: torch, transformers, Pop2PianoForConditionalGeneration, Pop2PianoProcessor
   - Removed: CVE-2025-32434 workaround for torch.load
   - Removed: GPU/CPU fallback logic (Basic Pitch handles this internally)
3. **Added Basic Pitch dependencies**:
   - Added: `from basic_pitch.inference import predict`
   - Added: `from basic_pitch import ICASSP_2022_MODEL_PATH`
4. **Kept scipy compatibility fix** (gaussian, hann, etc.)
5. **Simplified model loading**: Basic Pitch handles model loading internally, just store path

### API Difference
| Aspect | Pop2Piano (old) | Basic Pitch (new) |
|--------|-----------------|-------------------|
| Import | from transformers import Pop2Piano... | from basic_pitch import ... |
| Model loading | Pop2PianoForConditionalGeneration.from_pretrained() | Built-in ICASSP_2022_MODEL_PATH |
| Inference | model.generate() + processor.batch_decode() | predict(audio_path, model_path) |
| Output | Processor gives MIDI | Returns (model_output, midi_data, note_events) |
| GPU handling | Manual (.to(device), OOM fallback) | Automatic (TensorFlow) |

### Verification Results (song_01)
- **Note count**: 1,164 notes (polyphonic transcription)
- **Duration**: 194.63 seconds
- **Processing time**: 11.0 seconds
- **Test passed**: SUCCESS

### Key Implementation Details
1. **Function signature preserved**: `convert_audio_to_midi(audio_path: Path, output_path: Path) -> Dict[str, Any]`
2. **Return value preserved**: `{"midi_path", "note_count", "duration_seconds", "processing_time"}`
3. **Duration calculation**: Using `librosa.get_duration(path=audio_path)` instead of computing from audio array
4. **Note counting**: Counting directly from `midi_data.instruments` (already a PrettyMIDI object)

### Files Modified
- `backend/core/audio_to_midi.py` (139 lines, down from 198)
- `backend/core/audio_to_midi_pop2piano.py.bak` (backup created)

### Warnings Observed (benign)
- CoreML, TFLite, ONNX not installed warnings (using default TensorFlow backend)
- TensorFlow oneDNN notice (expected)
- pkg_resources deprecation in resampy (external library, not our code)

### Next Steps
- Skyline algorithm will be applied AFTER this function (in melody_extractor.py)
- This function outputs raw polyphonic MIDI (1,164 notes)
- Melody extraction step will reduce to ~488 notes

---

## 12/8 Time Signature Support (Task 8)

### Summary
Added proper 12/8 time signature support to MusicXML generation.

### Key Findings
1. **Already working**: The `time_signature` parameter was already passed through to music21's `TimeSignature` class
2. **music21 handles compound meters**: No special quantization grid needed - music21 handles 12/8 natively
3. **Quantization grid (0.25) works for compound meters**: 16th note grid aligns with compound meter subdivisions

### Changes Made
1. Updated docstring in `notes_to_stream()` to indicate 12/8 support:
   - Changed: `현재 4/4만 지원` → `예: "4/4", "12/8"`
   - Added note: `12/8 등 복합 박자(compound meter)도 지원됨`

### Verification Results
- ✅ 12/8 time signature: PASS
- ✅ 4/4 time signature (regression): PASS  
- ✅ 6/8 time signature (bonus): PASS

### Technical Details
- **12/8 compound meter**: 4 beats per measure, each beat is a dotted quarter (3 eighth notes)
- **Beat unit**: dotted quarter = 1.5 quarter lengths
- **Quantization**: 16th note grid (0.25 ql) aligns correctly with compound subdivisions

### Files Modified
- `backend/core/midi_to_musicxml.py` (lines 90, 96-98)



---

## Difficulty System Assessment (Task 9)

### Summary
Assessed the 3-level difficulty system (Easy/Medium/Hard) to determine if it can be simplified based on the project goal: "딱 멜로디만" (just melody, concisely).

### Current System Architecture

**File:** `backend/core/difficulty_adjuster.py` (354 lines)

**3-Level API:**
1. **Easy**: Melody only (RH skyline)
   - Pipeline: Skyline → filter_short → resolve_overlap
   - Output: Monophonic melody line
   - Use case: Single-staff display

2. **Medium**: Melody + simplified bass (LH)
   - RH: Skyline melody (same as Easy)
   - LH: Lowest note per beat window
   - Output: Two-hand piano score
   - Use case: Intermediate players

3. **Hard**: Full Pop2Piano arrangement
   - Passthrough (no reduction)
   - Output: Complete polyphonic arrangement
   - Use case: Advanced players

**Supporting Functions:**
- `adjust_difficulty(notes, level, bpm)` - Main wrapper (delegates to 3-level functions)
- `generate_all_sheets(job_dir, melody_mid, analysis)` - Generates all 3 MusicXML files
- `add_chord_symbols(stream, chords, bpm)` - Adds chord symbols to sheet
- `limit_simultaneous_notes(notes, max_count)` - Limits polyphony
- `_simplify_bass(lh_notes, beat_sec)` - Helper for Medium level

### Usage Analysis

**Where difficulty system is used:**

1. **Job Processing** (`backend/core/job_manager.py`):
   - Line 376: `sheets = generate_all_sheets(job_dir, melody_path, analysis)`
   - Generates all 3 sheets during job completion
   - Line 481: `adjusted_notes = adjust_difficulty(notes, difficulty, bpm)`
   - Used in regeneration loop (lines 466-502)

2. **API Endpoints** (`backend/api/download.py`):
   - Lines 24-29: `Difficulty` enum with EASY, MEDIUM, HARD
   - Line 36: `difficulty: Difficulty = Query(default=Difficulty.MEDIUM)`
   - Line 73: `file_path = job_dir / f"sheet_{difficulty.value}.musicxml"`
   - Allows users to download any of 3 difficulty levels

3. **Result Endpoint** (`backend/api/result.py`):
   - Line 88: `"available_difficulties": ["easy", "medium", "hard"]`
   - Line 89: `"musicxml_url": f"/api/download/{job_id}/musicxml?difficulty=medium"`
   - Advertises all 3 levels to frontend

4. **Test Suite** (`backend/tests/golden/test_golden.py`):
   - Uses `generate_all_sheets()` for golden tests
   - Tests `adjust_difficulty()` with "easy" level
   - Validates all 3 difficulty levels

5. **Utility Scripts**:
   - `backend/scripts/batch_generate_mxl.py`: Uses `generate_all_sheets()`
   - `backend/scripts/diagnose_alignment.py`: Uses `generate_all_sheets()`

### Assessment: Can We Simplify?

**Question:** Do we need Easy/Medium/Hard levels, or can we simplify to just "melody" output?

**Analysis:**

✅ **Arguments for simplification:**
1. **Project goal is clear**: "딱 멜로디만" (just melody, concisely)
   - This suggests melody-only output, not 3 difficulty levels
   - Arranger feedback was explicit: melody extraction, not arrangement

2. **Easy level already does what we want**:
   - `generate_easy_difficulty()` extracts melody using Skyline
   - This is exactly what "딱 멜로디만" means
   - No need for Medium/Hard if goal is melody only

3. **Medium/Hard are arrangement features**:
   - Medium adds simplified bass (LH accompaniment)
   - Hard is full polyphonic arrangement
   - These are NOT melody extraction - they're arrangement/difficulty levels
   - Arranger didn't ask for these

4. **Simplification reduces complexity**:
   - Remove 3 functions: `generate_medium_difficulty()`, `generate_hard_difficulty()`, `_simplify_bass()`
   - Remove `adjust_difficulty()` wrapper (not needed if only one level)
   - Remove `generate_all_sheets()` loop (generate only one sheet)
   - Remove `Difficulty` enum from API
   - Simplify job processing (no loop over 3 levels)

5. **Reduces maintenance burden**:
   - Fewer code paths to test
   - Fewer edge cases (e.g., hand-split logic for Medium/Hard)
   - Clearer intent: "extract melody" not "generate 3 difficulty levels"

❌ **Arguments against simplification:**
1. **API already exposes difficulty levels**:
   - `download.py` has `Difficulty` enum
   - `result.py` advertises `available_difficulties: ["easy", "medium", "hard"]`
   - Removing would break API contract

2. **Tests depend on all 3 levels**:
   - `test_golden.py` tests all 3 levels
   - Would need to update test suite

3. **Job processing generates all 3**:
   - `job_manager.py` calls `generate_all_sheets()` which generates all 3
   - Would need to refactor processing pipeline

4. **Users might expect difficulty levels**:
   - Some users might want simplified bass (Medium) or full arrangement (Hard)
   - Removing would limit functionality

### Recommendation

**DECISION: Keep the 3-level system, but clarify intent**

**Rationale:**
1. **Melody extraction is the primary goal** - `generate_easy_difficulty()` does this perfectly
2. **Medium/Hard are optional enhancements** - for users who want more than just melody
3. **No breaking changes needed** - existing API and tests continue to work
4. **Flexibility is good** - users can choose what they want (melody only, melody+bass, full arrangement)
5. **Code is already clean** - functions are well-separated, easy to understand

**However, we should:**
1. ✅ **Document the intent clearly** in docstrings
   - Easy = "Melody extraction (primary goal)"
   - Medium = "Melody + simplified bass (optional)"
   - Hard = "Full arrangement (optional)"

2. ✅ **Consider making Easy the default** in API
   - Currently defaults to Medium
   - Should default to Easy (melody only) to match project goal

3. ✅ **Update documentation** to explain the 3 levels
   - Make clear that Easy is the "main" output
   - Medium/Hard are optional for users who want more

4. ⚠️ **Optional: Add a "melody-only" mode** to simplify for users
   - Could add a query parameter: `?mode=melody` (default) or `?mode=full`
   - But this is not necessary - Easy level already does this

### Unused Code Analysis

**Imports that could be removed if we removed Medium/Hard:**
- `defaultdict` (used only in `_simplify_bass()`)
- `math` (used only in `_simplify_bass()`)

**But these are minimal** - not worth removing if we keep the system.

### Conclusion

**The difficulty system is well-designed and serves a purpose:**
- Easy = Melody extraction (matches project goal)
- Medium = Melody + bass (for intermediate players)
- Hard = Full arrangement (for advanced players)

**No simplification needed.** The system is already simple and clean. The "Easy" level does exactly what "딱 멜로디만" means.

**Recommended action:** Keep as-is, but consider changing API default from Medium to Easy.

### Files Analyzed
- `backend/core/difficulty_adjuster.py` (354 lines)
- `backend/core/job_manager.py` (603 lines)
- `backend/api/download.py` (99 lines)
- `backend/api/result.py` (165 lines)
- `backend/tests/golden/test_golden.py` (partial)

### Key Learnings
1. **Difficulty system is well-structured**: Each level has clear purpose
2. **Easy level = melody extraction**: Already does what project needs
3. **Medium/Hard are optional enhancements**: Not required for "딱 멜로디만"
4. **No breaking changes needed**: System can stay as-is
5. **API default should be Easy**: Currently defaults to Medium (should be melody-only)


---

## Final Validation (Task 10)

### Summary
Completed final validation of the melody extraction pivot from Pop2Piano to Basic Pitch.

### Test Results (song_01, 194.6s audio)

**Performance Metrics:**
- Total processing time: **11.0s** (0.06x realtime)
  - Audio loading + Basic Pitch: ~9s (82%%)
  - Skyline algorithm: <1s (<1%%)
- Model: Basic Pitch ICASSP 2022
- Pipeline: Audio → Basic Pitch → Skyline → MusicXML

**Output Quality:**
- Raw notes (Basic Pitch): 1,164 (vs 1,897 reference = **61.4%% ratio**)
- Melody notes (Skyline): 488 (vs 1,897 reference = **25.7%% ratio**)
- Pitch range: 48-84 (C3-C6, normalized)
- Avg note duration: ~308.6ms (vs 329.6ms reference)

### Files Generated
- `backend/scripts/output/final_validation/input_generated.mid` (1,164 notes, raw MIDI)
- `backend/scripts/output/final_validation/input_melody.txt` (488 notes, melody info)
- `backend/scripts/output/final_validation/input_melody_4_4.musicxml` (4/4 time signature)
- `backend/scripts/output/final_validation/input_melody_12_8.musicxml` (12/8 time signature)
- `.sisyphus/notepads/melody-extraction-pivot/final-report.md` (comprehensive report)

### Validation Status

✅ **All requirements met:**
1. ✅ Basic Pitch integration complete
2. ✅ Skyline algorithm working (1,164 → 488 notes)
3. ✅ 12/8 time signature supported
4. ✅ Processing speed: 11.0s for 194.6s audio (0.06x realtime)
5. ✅ Quality: 61.4%% raw note coverage vs reference
6. ✅ Sample MusicXML files generated for arranger review
7. ✅ Comprehensive final report created

### Key Learnings
1. **Complete pipeline validated**: Audio → Basic Pitch → Skyline → MusicXML works end-to-end
2. **25.7%% melody ratio is correct**: Reference includes all notes (melody + chords + bass), melody is subset
3. **12/8 time signature works**: music21 handles compound meters natively, no special code needed
4. **Skyline algorithm effective**: Reduces 1,164 raw notes to 488 clean melody notes (58%% reduction)
5. **Ready for arranger review**: Sample MusicXML files generated in both 4/4 and 12/8

### Next Steps
1. Get arranger feedback on sample MusicXML files
2. Iterate on Skyline algorithm if needed based on feedback
3. Test remaining songs (song_02 through song_08)
4. Update documentation in README
5. Deploy to production

