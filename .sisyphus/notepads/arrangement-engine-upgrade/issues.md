
## Issue: Music2MIDI Token Generation Incompatibility (2026-02-05)

### Problem
Music2MIDI model generates tokens outside meaningful vocabulary range (334-399) when run on torch 2.2.0.
The meaningful vocab range is 0-332. Tokenizer decodes out-of-range tokens to 0 notes.

### Root Cause
Likely numerical differences between torch 2.1 (training environment) and torch 2.2 (our environment).
Model was trained with transformers 4.34.0; we have a newer version.

### Impact
Music2MIDI cannot be used as arrangement engine. NO-GO verdict.

### Resolution
Proceeding with Pop2Piano which is confirmed working.

---

## Issue: Pop2Piano PyTorch Version Incompatibility (2026-02-05)

### Problem
Pop2Piano requires PyTorch >= 2.2, but current Docker setup uses:
- Base image: `nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04`
- PyTorch: 2.0.1 (locked in requirements.txt)
- Transformers library disables PyTorch models when PyTorch < 2.2

### Root Cause
PyTorch 2.2+ requires CUDA 12.x, but we're using CUDA 11.8 base image.

### Attempted Solutions
1. ✗ Runtime pip install of PyTorch 2.2+ → Takes too long (>10 minutes)
2. ✗ Upgrade to CUDA 12.1 base image → Docker Desktop crashes during build
3. ✗ Use CPU-only PyTorch → No matching distribution found

### Alternative Approaches

#### Option A: Use CPU-only Pop2Piano (Recommended for testing)
- Install PyTorch 2.2+ CPU version
- Slower but works without GPU
- Command: `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu`

#### Option B: Upgrade Docker base image properly
- Use `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04`
- Update requirements.txt: `torch>=2.2.0`, `torchaudio>=2.2.0`
- Rebuild container (may take 15-30 minutes)

#### Option C: Use pre-built PyTorch Docker image
- Base: `pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime`
- Simpler, faster build
- Already has PyTorch 2.2+ installed

### Recommendation
For Task 2 completion, use **Option C** (pre-built PyTorch image) to avoid build complexity.

### Files Modified (pending test success)
- `backend/requirements.txt`: torch==2.0.1 → torch>=2.2.0, torchaudio==2.0.2 → torchaudio>=2.2.0
- `backend/Dockerfile`: CUDA 11.8 → CUDA 12.1 (attempted)

