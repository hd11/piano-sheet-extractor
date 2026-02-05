# Music2MIDI Spike Validation Result

**Date**: 2026-02-05  
**Decision**: **NO-GO**

## Summary

Music2MIDI integration is **NOT VIABLE** for our current environment due to severe dependency conflicts and compatibility issues.

## Environment

- **Our Stack**: CUDA 11.8, Python 3.11, torch 2.0.1, Ubuntu 22.04
- **Music2MIDI Requirements**: Python 3.9, torch 2.1.0, CUDA 12.1
- **Docker Image**: nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

## Test Results

### ✓ PASS: Repository Access
- Successfully cloned Music2MIDI repository
- Successfully downloaded model checkpoint (119MB, `epoch.799-step.119200.ckpt`)

### ✗ FAIL: Dependency Hell

#### Issue 1: Torch Version Conflict
- Installing pytorch-lightning automatically upgraded torch from 2.0.1 → 2.10.0
- This broke torchaudio 2.0.2 (incompatible with torch 2.10.0)
- Error: `OSError: Could not load this library: libtorchaudio.so`

#### Issue 2: Missing Dependencies
Music2MIDI requires numerous dependencies not in our environment:
- `mir_eval` (music information retrieval evaluation)
- `pytorch-lightning` (training framework)
- `omegaconf` (configuration management)
- `transformers` (HuggingFace models)
- Compatible `torchaudio` version

#### Issue 3: Installation Time
- Dependency installation took >10 minutes and timed out
- Installing all dependencies would significantly bloat our Docker image
- Each container run requires re-installation (no persistence)

### ✗ FAIL: Import Test
Could not successfully import `music2midi.model.Music2MIDI` due to dependency conflicts.

### ✗ FAIL: MIDI Generation Test
Not reached due to import failure.

### ✗ FAIL: Difficulty Conditioning Test
Not reached due to import failure.

## Root Causes

1. **Python Version Mismatch**: Music2MIDI targets Python 3.9, we use 3.11
2. **CUDA Version Mismatch**: Music2MIDI targets CUDA 12.1, we have 11.8
3. **Torch Ecosystem Fragility**: Upgrading one component (torch) breaks others (torchaudio)
4. **Heavy Dependency Tree**: Music2MIDI pulls in ~50+ packages, many conflicting with our stack

## Attempted Solutions

1. ✗ Install dependencies via pip → version conflicts
2. ✗ Upgrade torch to 2.10.0 → broke torchaudio
3. ✗ Upgrade torchaudio → installation timeout

## Impact Assessment

### If We Force Integration (NOT RECOMMENDED):

**Pros:**
- Potentially better MIDI quality than ByteDance model
- Built-in difficulty conditioning

**Cons:**
- Requires major environment overhaul (Python 3.9, CUDA 12.1, torch 2.1.0)
- Risk of breaking existing ByteDance piano transcription
- Significantly larger Docker image (+500MB+ dependencies)
- Longer build times (10+ minutes for dependencies)
- Maintenance burden (managing two conflicting dependency trees)
- Unknown runtime performance (no GPU available in test)

## Recommendation

**DO NOT PROCEED** with Music2MIDI integration.

### Alternative Approaches:

1. **Stick with ByteDance Model**
   - Already integrated and working
   - Optimize post-processing instead of replacing model
   - Implement custom difficulty adjustment layer

2. **Explore Pop2Piano**
   - Lighter weight than Music2MIDI
   - May have better compatibility
   - Worth a separate spike

3. **Custom Arrangement Engine**
   - Use ByteDance for note detection
   - Build custom arrangement logic on top
   - Full control over difficulty levels

4. **Separate Service Architecture**
   - Run Music2MIDI in isolated container with Python 3.9 + CUDA 12.1
   - Communicate via API
   - Avoids dependency conflicts but adds complexity

## Conclusion

Music2MIDI is a **research-grade tool** designed for conda environments with specific versions. Integrating it into our production stack would require:
- Complete environment rebuild
- Risk of breaking existing functionality
- Significant maintenance overhead

**The juice is not worth the squeeze.**

Recommend focusing on **optimizing our current ByteDance-based pipeline** rather than replacing it.

---

## Technical Details

### Dependency Conflicts Encountered

```
torchaudio 2.0.2 requires torch==2.0.1, but you have torch 2.10.0
```

### Import Error Stack Trace

```
OSError: /usr/local/lib/python3.11/dist-packages/torchaudio/lib/libtorchaudio.so: 
undefined symbol: _ZNK5torch8autograd4Node4nameEv
```

### Files Created During Spike

- `/tmp/music2midi/` - Cloned repository
- `/tmp/music2midi/checkpoints/epoch.799-step.119200.ckpt` - Model checkpoint (119MB)
- `test/spike_music2midi.py` - Validation script

### Time Spent

- Investigation: ~30 minutes
- Dependency troubleshooting: ~20 minutes
- Total: ~50 minutes

---

**Spike Completed By**: Sisyphus (AI Agent)  
**Next Steps**: Discuss alternative approaches with team
