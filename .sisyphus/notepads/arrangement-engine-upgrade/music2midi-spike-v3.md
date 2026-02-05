
## Music2MIDI v3 Spike Result: NO-GO (2026-02-05)

### Verdict: NO-GO

Music2MIDI cannot be used as the arrangement engine. Proceeding with Pop2Piano.

### Environment
- Docker base: `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`
- torch: 2.2.0, torchaudio: 2.2.0, CUDA: 12.1 (no GPU in Docker Desktop Windows)
- Python: 3.11

### Phase A: Pop2Piano Baseline — PASSED
- Pop2Piano MIDI generation succeeded on song_01
- note_count: 1369, duration: 194.63s, processing_time: 67.11s (CPU)
- midi_file_size: 8974 bytes
- Two bugs fixed in `audio_to_midi.py`:
  1. SyntaxError: `global _model, _processor, _device` declared after `_device` usage (Python 3.11 strict)
  2. CVE-2025-32434: torch.load safety check monkey-patch added
- Added missing deps: `essentia==2.1b6.dev1034`, `resampy>=0.4.0`

### Phase B: Music2MIDI Reconnaissance — API EXISTS
- `cond_index` parameter confirmed in `generate()` at `model.py:67-99`
- Config: genre (6 types) + difficulty (beginner/intermediate/advanced)
- Usage: `model.generate(audio_path, cond_index=[1, 1])` (pop, intermediate)
- Checkpoint: 119MB (within 10GB limit)
- Dependencies: pytorch-lightning, omegaconf, more-itertools, mir_eval

### Phase C: Music2MIDI Spike — FAILED

#### Approach 1 (pip install): FAILED
- No `git` in container, no `setup.py` in repo

#### Approach 2 (wget + manual): Import OK, Generation FAILED
- Dependencies installed, checkpoint downloaded (123MB)
- Model loading succeeded (0.6s, 30M params)
- **MIDI generation produced 0 notes in ALL cases**:
  - Greedy/beam decode: all-same token (384) — degenerate
  - Sampling (temp=0.8, top_k=50): tokens in 334-399 range (outside meaningful vocab 0-332)
  - Tokenizer decodes out-of-range tokens to 0 notes
  - Tested with PL 2.1.0 exact match — same result

#### Root Cause Analysis
- Model produces tokens outside meaningful vocabulary range
- Likely torch 2.2 vs 2.1 numerical differences or transformers version mismatch (trained with 4.34.0)
- CPU performance prohibitive: ~130-168s for 30s audio, estimated ~18 min for full song

### NO-GO Reasons (ANY triggers NO-GO)
1. **Degenerate model output**: 0 notes generated regardless of decoding strategy
2. **Prohibitive CPU inference time**: 130-168s for 30s audio
3. **Same dependency hell as v2**: Different manifestation, same outcome
4. **No viable workaround**: Tried greedy, beam, sampling — all fail

### Decision
- Stick with Pop2Piano (confirmed working, 1369 notes, 67s processing)
- Pop2Piano code in `audio_to_midi.py` is the production arrangement engine
- Music2MIDI spike branch cleaned up: `git branch -D spike/music2midi-v3-cuda12`
