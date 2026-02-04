# MT3 (Multi-Task Multitrack Music Transcription) Research - 2026-02-05

## Executive Summary

MT3 is a **Transformer-based** music transcription model from Google Magenta that treats transcription as a sequence-to-sequence problem. It shows promise for improving over ByteDance (36.66%) but has **significant implementation challenges**.

**Key Finding**: Official MT3 uses JAX/Flax (incompatible with our PyTorch stack). PyTorch ports exist but are unofficial. **YourMT3** appears to be the most promising path forward.

---

## 1. What is MT3?

### Basic Information

- **Full Name**: MT3 - Multi-Task Multitrack Music Transcription
- **Developer**: Google Magenta Research Team
  - Josh Gardner, Ian Simon, Ethan Manilow, Curtis Hawthorne, Jesse Engel
- **Papers**: 
  - ISMIR 2021 (Piano model): https://archives.ismir.net/ismir2021/paper/000030.pdf
  - ICLR 2022 (Multi-instrument): https://openreview.net/pdf?id=iMSjopcOn0p
  - arXiv: 2111.03017

### Architecture

**Type**: Transformer-based (T5 architecture)
- Treats music transcription as sequence-to-sequence translation
- Input: Audio spectrogram frames
- Output: Event tokens representing notes (onset, offset, pitch, velocity, program)

**Framework**: JAX/Flax with T5X (Google's T5 framework)

**Evidence** ([source](https://github.com/magenta/mt3/blob/fa04532779a6078819c3418adcd83747c94329a4/README.md#L3)):
> MT3 is a multi-instrument automatic music transcription model that uses the T5X framework.

### Training Data

- **Piano Model**: MAESTRO v3.0.0 dataset
- **Multi-instrument Model**: MAESTRO + GuitarSet + Slakh2100 + others

---

## 2. Performance

### Strengths

1. **Multi-instrument capability**: Can transcribe piano, guitar, drums, bass simultaneously
2. **Polyphonic handling**: Transformer architecture handles complex polyphony
3. **State-of-the-art claims**: Papers report competitive results on MAESTRO
4. **Robust evaluation**: Uses mir_eval standard metrics

### Evaluation Metrics

**Evidence** ([source](https://github.com/magenta/mt3/blob/fa04532779a6078819c3418adcd83747c94329a4/mt3/metrics.py#L36-L100)):

MT3 uses program-aware note scoring:
- **Precision**: Correct predictions / Total predictions
- **Recall**: Correct predictions / Total ground truth
- **F1 Score**: Harmonic mean of precision and recall
- **Onset-only** for drums, **Onset+offset** for melodic instruments

```python
def _program_aware_note_scores(
    ref_ns: note_seq.NoteSequence,
    est_ns: note_seq.NoteSequence,
    granularity_type: str
) -> Mapping[str, float]:
  """Compute precision/recall/F1 for notes taking program into account."""
```

### Benchmark Results

**Note**: Specific F1 scores not found in repository README. Need to check papers for exact numbers.

**YourMT3 Claims**: State-of-the-art on Papers With Code for:
- Multi-instrument music transcription
- Slakh2100 dataset
- ENST-Drums dataset

---

## 3. Implementation Options

### Option 1: Official MT3 (magenta/mt3)

**Repository**: https://github.com/magenta/mt3
- **Stars**: 1,664
- **Last Updated**: 2026-02-03
- **Commit SHA**: fa04532779a6078819c3418adcd83747c94329a4

**Dependencies** ([source](https://github.com/magenta/mt3/blob/fa04532779a6078819c3418adcd83747c94329a4/setup.py#L39-L56)):
```python
install_requires=[
    'flax @ git+https://github.com/google/flax#egg=flax',
    't5x @ git+https://github.com/google-research/t5x#egg=t5x',
    'tensorflow',
    'tensorflow-datasets',
    'librosa',
    'mir_eval',
    'note-seq',
    'pretty_midi',
    # ... more
]
```

**Pros**:
- ✅ Official Google implementation
- ✅ Well-documented in research papers
- ✅ Pretrained checkpoints available
- ✅ Colab notebook for inference

**Cons**:
- ❌ **Uses JAX/Flax** (NOT PyTorch) - incompatible with our stack
- ❌ **Uses T5X framework** - complex setup
- ❌ **Training not easily supported** (per README)
- ❌ Requires TensorFlow for data processing
- ❌ Google Cloud Storage dependencies

**Verdict**: **NOT COMPATIBLE** with our PyTorch 2.0.1 environment

---

### Option 2: PyTorch Port (kunato/mt3-pytorch)

**Repository**: https://github.com/kunato/mt3-pytorch
- **Stars**: 40
- **Last Updated**: 2026-01-29
- **Status**: Unofficial implementation

**API** ([source](https://github.com/kunato/mt3-pytorch/blob/main/README.md#L7-L12)):
```python
from inference import InferenceHandler

handler = InferenceHandler('./pretrained')
handler.inference('music.mp3')
```

**Dependencies** ([source](https://github.com/kunato/mt3-pytorch/blob/main/requirements.txt)):
```
transformers==4.18.0
torch
librosa==0.9.1
ddsp==3.3.4
t5==0.9.3
note-seq==0.0.3
pretty-midi==0.2.9
einops==0.4.1
```

**Implementation Details** ([source](https://github.com/kunato/mt3-pytorch/blob/main/inference.py#L16-L35)):
```python
class InferenceHandler:
    def __init__(self, weight_path, device=torch.device('cuda')) -> None:
        config = T5Config.from_dict(config_dict)
        model: nn.Module = T5ForConditionalGeneration(config)
        model.load_state_dict(torch.load(weight_path, map_location='cpu'))
        self.SAMPLE_RATE = 16000
        self.spectrogram_config = spectrograms.SpectrogramConfig()
```

**Pros**:
- ✅ **PyTorch-based** (compatible with our stack)
- ✅ Simple inference API
- ✅ Uses HuggingFace Transformers
- ✅ Direct MIDI output

**Cons**:
- ❌ **Unofficial port** (may have accuracy differences from official)
- ❌ **Training "not done yet"** per README
- ❌ Only 40 stars (less community validation)
- ❌ Pretrained weights availability unclear
- ❌ May have bugs or incomplete features

**Verdict**: **TESTABLE** but risky due to unofficial status

---

### Option 3: YourMT3 / YourMT3+ (RECOMMENDED)

**Repository**: https://github.com/mimbres/YourMT3
- **Stars**: 198
- **Last Updated**: 2026-01-28
- **Description**: "multi-task and multi-track music transcription for everyone"

**Latest Version**: YourMT3+ (MLSP 2024)
- **Paper**: https://arxiv.org/abs/2407.04822
- **HuggingFace Demo**: https://huggingface.co/spaces/mimbres/YourMT3
- **Colab Demo**: Available

**Evidence** ([source](https://github.com/mimbres/YourMT3/blob/main/README.md#L1)):
> [![PWC](https://img.shields.io/endpoint.svg?url=https://paperswithcode.com/badge/yourmt3-multi-instrument-music-transcription/multi-instrument-music-transcription-on)](https://paperswithcode.com/sota/multi-instrument-music-transcription-on?p=yourmt3-multi-instrument-music-transcription)

**Pros**:
- ✅ **Improved version of MT3** with better usability
- ✅ **Active development** (updated Jan 2026)
- ✅ **HuggingFace integration** (easy deployment)
- ✅ **State-of-the-art results** on Papers With Code
- ✅ Community-friendly ("for everyone")
- ✅ Free GPU demo available

**Cons**:
- ⚠️ Repository appears minimal (only LICENSE and README in clone)
- ⚠️ Implementation details need investigation
- ⚠️ May require HuggingFace account/API
- ⚠️ Framework (PyTorch vs JAX) unclear

**Verdict**: **MOST PROMISING** - investigate implementation details

---

## 4. Compatibility Analysis

### Python Version
- Official MT3: Python 3.7+ (TensorFlow 2.x)
- PyTorch port: Python 3.8+
- **Our Environment**: Python 3.11 ✅

### Framework
- Official MT3: JAX/Flax ❌
- PyTorch port: PyTorch ✅
- YourMT3: Unknown (needs investigation)
- **Our Stack**: PyTorch 2.0.1

### OS Compatibility
- Linux: Full support ✅
- macOS: Supported ✅
- Windows: Should work but less tested ⚠️
- **Our Environment**: Docker (Linux-based) ✅

### GPU Requirements
- CUDA-capable GPU recommended
- Model size: Large (T5-based, likely 100M-300M parameters)
- Inference: Can run on CPU but slow
- **Our Setup**: GPU available ✅

### Docker Support
- No official Docker image
- Can be containerized with TensorFlow/PyTorch base images
- **Our Environment**: Docker ✅

---

## 5. Known Limitations

### Technical Limitations

1. **Framework Com
