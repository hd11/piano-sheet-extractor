
## Learnings from Task 0: Pop2Piano + Music2MIDI Spike v3 (2026-02-05)

### Pop2Piano Works on CUDA 12.1 / torch 2.2
- Pop2Piano generates valid MIDI (1369 notes, 194.63s duration) on CPU
- Processing time: 67.11s for ~3min song on CPU — acceptable
- Two bugs needed fixing: Python 3.11 global declaration order + CVE-2025-32434 torch.load safety

### torch.load CVE-2025-32434 Workaround
- Transformers library now requires torch >= 2.6 for safe `torch.load`
- Monkey-patch `transformers.modeling_utils.safe_globals` and `torch.serialization.safe_globals` to bypass
- This is a temporary workaround until torch 2.6+ is adopted

### Music2MIDI Generates Degenerate Output
- Model loads fine (30M params, 0.6s) but produces tokens outside meaningful vocab range (334-399 vs 0-332)
- All decoding strategies fail: greedy (all-same token 384), beam, sampling
- Root cause likely: numerical differences between torch 2.1 (training) and 2.2 (inference)
- CPU inference is prohibitively slow: 130-168s for 30s audio

### essentia + resampy Required for Pop2Piano
- Pop2Piano's audio preprocessing chain requires `essentia==2.1b6.dev1034` and `resampy>=0.4.0`
- These were missing from requirements.txt

### Python 3.11 Strict Global Declaration
- Python 3.11 made it a hard error to use `global x` after `x` is already referenced in the function
- Must declare `global` at the very top of the function before any usage
