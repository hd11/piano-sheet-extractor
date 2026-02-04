# Onsets and Frames Piano Transcription Model - Research Report

**Date:** 2026-02-05
**Context:** Evaluating for piano-sheet-extractor project (target: 85% similarity)

---

## EXECUTIVE SUMMARY

**Onsets and Frames** is a state-of-the-art deep learning model for automatic polyphonic piano music transcription developed by Google Magenta (2017-2018). It converts raw piano audio into MIDI using a dual-objective approach that separately predicts note onsets and active frames.

**Key Achievement:** Over 100% relative improvement in note F1 score (50.22 vs 23.14 previous SOTA on MAPS dataset).

**Recommendation:** ⚠️ CONDITIONAL - Strong candidate IF pre-trained model available. Compare with MT3 before final decision.

---

## 1. WHAT IS ONSETS AND FRAMES?

### Identity
- **Full Name:** "Onsets and Frames: Dual-Objective Piano Transcription"
- **Developer:** Google Magenta (TensorFlow team)
- **Authors:** Curtis Hawthorne, Erich Elsen, Jialin Song, Adam Roberts, Ian Simon, Colin Raffel, Jesse Engel, Sageev Oore, Douglas Eck
- **Publication:** arXiv:1710.11153 (October 2017, revised June 2018)
- **Paper:** https://arxiv.org/abs/1710.11153
- **Blog:** https://magenta.tensorflow.org/onsets-frames

### Architecture

**Dual-stack neural network with 5 components:**

1. **Onset Stack:** CNN + BiLSTM → Detects note onset events
2. **Offset Stack:** CNN + BiLSTM → Detects note offset events  
3. **Frame Stack:** CNN → Detects active frames
4. **Combined Stack:** BiLSTM → Combines predictions
5. **Velocity Stack:** CNN → Predicts note velocities

**Model Size:** 26M parameters (default)

**Key Innovation:** Onset predictions condition frame predictions, preventing false positives.

**Evidence:** https://github.com/jongwook/onsets-and-frames/blob/783ca08498bb8ada41516c9ed492868b4e947abf/onsets_and_frames/transcriber.py#L52-L84

### Training Data

- **Primary:** MAESTRO dataset (~200 hours virtuosic piano, ~200 GB storage)
- **Test:** MAPS Database (Disklavier portion)

---

## 2. PERFORMANCE

### Benchmark Results

| Metric | Previous SOTA | Onsets and Frames | Improvement |
|--------|---------------|-------------------|-------------|
| Note F1 Score (with offsets) | 23.14 | 50.22 | +117% |

### Strengths
✅ Excellent onset detection
✅ Offset prediction (knows when notes end)
✅ Velocity estimation
✅ Polyphonic capability (88 keys)
✅ Rhythm preservation
✅ Harmony capture

### Weaknesses
⚠️ Resource intensive (32GB RAM, 8GB GPU for training)
⚠️ No pre-trained models in official repo
⚠️ Piano-specific (not multi-instrument)
⚠️ Older architecture (2017-2018)
⚠️ Training complexity

### Comparison Context
- **Basic Pitch (Spotify):** General-purpose SOTA for multi-instrument
- **Onsets and Frames:** Specialized SOTA for solo piano (as of 2018)
- **MT3:** Newer Google model (2021+) may supersede

**Note:** Direct comparison with ByteDance (36.66%) requires benchmarking on your dataset.

---

## 3. IMPLEMENTATION

### Repositories

**PyTorch Implementation (Recommended):**
- **URL:** https://github.com/jongwook/onsets-and-frames
- **Stars:** 240 | **Forks:** 76
- **Last Updated:** 2026-01-25
- **Status:** Active, well-maintained

**Original (TensorFlow):**
- **URL:** https://github.com/tensorflow/magenta
- **Path:** magenta/models/onsets_frames_transcription/
- **Stars:** 19,775

### Installation

**Not available as pip package** - Must clone and install:

```bash
git clone https://github.com/jongwook/onsets-and-frames.git
cd onsets-and-frames
pip install -r requirements.txt
```

### Dependencies

**Evidence:** https://github.com/jongwook/onsets-and-frames/blob/783ca08498bb8ada41516c9ed492868b4e947abf/requirements.txt

```
scipy>=1.1.0
torch>=1.2.0          # Your project: 2.0.1 ✅
SoundFile>=0.10.2
sacred==0.7.4
librosa>=0.6.2
numpy>=1.15.0
tqdm>=4.28.1
git+https://github.com/craffel/mir_eval.git
mido>=1.2.9
Pillow>=6.2.0
```

---

## 4. USAGE

### Command-Line Interface

**Training:**
```bash
python train.py with logdir=runs/model iterations=1000000
```

**Evaluation:**
```bash
python evaluate.py runs/model/model-100000.pt --save-path output/
```

**Transcription:**
```bash
python transcribe.py model.pt audio.flac --save-path output/
```

### Input/Output

**Input:**
- Format: FLAC (16-bit PCM)
- Sample Rate: 16,000 Hz
- Channels: Mono
- MIDI Range: 21-108 (A0 to C8, full 88-key piano)

**Output:**
- MIDI file (.mid) with onsets, offsets, velocities
- Piano roll image (.png) visualization

**Evidence:** https://github.com/jongwook/onsets-and-frames/blob/783ca08498bb8ada41516c9ed492868b4e947abf/onsets_and_frames/constants.py#L4-L11

### Programmatic Usage

```python
# Load model
model = torch.load(model_file, map_location=device).eval()

# Load audio
audio, sr = soundfile.read(audio_path, dtype='int16')
audio = torch.ShortTensor(audio).float().div_(32768.0)

# Transcribe
predictions = transcribe(model, audio)

# Extract notes
p_est, i_est, v_est = extract_notes(
    predictions['onset'], 
    predictions['frame'], 
    predictions['velocity']
)

# Save MIDI
save_midi(output_path, p_est, i_est, v_est)
```

**Evidence:** https://github.com/jongwook/onsets-and-frames/blob/783ca08498bb8ada41516c9ed492868b4e947abf/transcribe.py#L38-L50

---

## 5. COMPATIBILITY

### Python Version
- **Minimum:** Python 3.6+
- **Recommended:** Python 3.8-3.11
- **Your Project:** Python 3.11 ✅ **COMPATIBLE**

### OS Support
✅ Linux | ✅ macOS | ✅ Windows

### Docker Support
✅ **Docker Compatible**
- All dependencies pip-installable
- GPU support via NVIDIA Docker runtime
- **Your Stack:** Docker + Python 3.11 + PyTorch 2.0.1 ✅

### Hardware Requirements

**Inference (Your Use Case):**
- RAM: 8 GB minimum
- GPU: 4 GB VRAM (CPU fallback available)

**Training:**
- RAM: 32 GB+
- GPU: 8 GB+ VRAM
- Storage: 200 GB for MAESTRO

---

## 6. PROS AND CONS

### Pros ✅

1. **State-of-the-art (2018):** 50.22 F1, 100%+ improvement over previous SOTA
2. **Dual-objective architecture:** Reduces false positives
3. **Velocity prediction:** Natural-sounding transcriptions
4. **Offset detection:** Knows when notes end
5. **Well-documented:** Paper, blog, examples
6. **PyTorch implementation:** Modern codebase (240 stars, 76 forks)
7. **Compatible:** Python 3.11, PyTorch 2.0.1, Docker ✅
8. **Piano-specialized:** Optimized for piano
9. **Active community:** Recent updates (2026-01-25)

### Cons ⚠️

1. **No pre-trained models:** Must train or find community models
2. **Resource intensive:** 32GB RAM + 8GB GPU for training
3. **Large dataset:** MAESTRO is ~200 GB
4. **Older architecture:** 2017-2018, may be surpassed
5. **Piano-only:** Not multi-instrument
6. **Not pip-installable:** Manual setup required
7. **Training complexity:** Sacred configuration, ML expertise needed
8. **No official Docker image:** Custom Dockerfile required
9. **Uncertain performance:** 50.22 F1 on MAPS, but your target is 85% similarity (different metric)

---

## 7. RECOMMENDATION

### Decision Matrix

**Use Onsets and Frames IF:**
- ✅ You can find/train a pre-trained model
- ✅ You have 8GB+ GPU for inference
- ✅ Your audio is solo piano
- ✅ You need velocity information
- ✅ You want proven, documented approach

**Consider Alternatives IF:**
- ❌ You need ready-to-use pip package → Basic Pitch
- ❌ You need multi-instrument → Basic Pitch, MT3
- ❌ You want absolute latest SOTA → MT3
- ❌ You can't find pre-trained weights
- ❌ Limited compute resources

### Comparison with Current Setup

- **Current:** ByteDance (36.66% similarity)
- **Target:** 85% similarity
- **Onsets and Frames:** 50.22 F1 (MAPS dataset)

**Key Questions:**
1. Metric compatibility: Your "similarity" vs. F1 score?
2. Pre-trained model availability?
3. Is MT3 better?

### Next Steps

**Recommended Action Plan:**

1. **Search for pre-trained models:**
   - Hug
