<!-- Parent: ../AGENTS.md -->

# scripts/ — CLI Tools & Evaluation

Evaluation, extraction, and diagnostic tools for the melody extraction pipeline.

## Purpose

Scripts in this directory support four workflows:
1. **Full evaluation** — assess pipeline on all 8 songs with round-trip MusicXML validation (Rule 4)
2. **Quick ablation** — test single song with different modes or configurations
3. **Diagnostic analysis** — classify errors (pitch, onset, false positives) per-song
4. **CLI extraction** — extract melody from a single MP3 to MusicXML
5. **Reference analysis** — inspect test data patterns (density, key, range)

## Key Files

| File | Purpose | Input | Output |
|------|---------|-------|--------|
| `evaluate.py` | Full 8-song round-trip evaluation (Rule 4 compliant) | `test/*.mp3` + `test/*.mxl` | `results/vNN.json` + `output/*.musicxml` |
| `ablation_test.py` | Single-song quick test with metrics | `test/SONG.mp3` + `test/SONG.mxl` | metrics dict printed to stdout |
| `diagnose.py` | Per-song error classification (exact match, pitch miss, onset miss, FP, FN, octave errors) | `output/*.musicxml` (cached) | `results/diagnostics/*.json` |
| `extract.py` | CLI extraction: MP3 → MusicXML (no evaluation) | MP3 file (any path) | MusicXML file (specified output) |
| `analyze_reference.py` | Reference data pattern analysis (note density, key, pitch range) | `test/*.mxl` | JSON summary printed to stdout |

## For AI Agents

### When to Use Each Script

**`evaluate.py`** — Full evaluation of all 8 songs. Use this:
- After making code changes to the pipeline, to measure impact
- To test a new F0 mode (`--mode crepe/fcpe/rmvpe/bp/onset/hybrid`)
- To test reference extraction methods (`--ref-method skyline/contour`)
- To save version-tagged results (`--output results/vNN.json`)

**`ablation_test.py`** — Quick single-song test. Use this:
- During development to iterate fast (1-2 seconds vs 25 min for full evaluation)
- To debug a specific song
- To test configuration changes before committing to full 8-song run
- Example: `python scripts/ablation_test.py --song "꿈의 버스" --mode fcpe --tag debug_v1`

**`diagnose.py`** — Deep error analysis. Use this:
- To understand why a song scores low (identify pitch_miss vs onset_miss patterns)
- To find octave error rates and pitch error histograms
- To reuse cached outputs from `evaluate.py` with `--reuse-output`
- Outputs `results/diagnostics/SONG_diagnose.json` for each song

**`extract.py`** — Standalone extraction (no evaluation). Use this:
- To extract melody from user-provided MP3 files
- When reference MXL is not available (no evaluation)
- Example: `python scripts/extract.py user_song.mp3 -o output/user_song.musicxml --mode fcpe`

**`analyze_reference.py`** — Reference data statistics. Use this:
- When starting a new project to understand reference distribution
- To guide postprocess heuristics (e.g., BPM thresholds, pitch range)
- Already run on initial 8 songs; results documented in `PROJECT_DIRECTIVES.md`

### Usage Examples

```bash
# Full 8-song evaluation (round-trip, takes ~25-30 min with CREPE)
python scripts/evaluate.py --mode crepe --output results/v20.json

# Fast 8-song evaluation with FCPE (takes ~10 seconds)
python scripts/evaluate.py --mode fcpe --output results/v20_fcpe.json

# Single song quick test (takes ~1-2 seconds)
python scripts/ablation_test.py --song "꿈의 버스" --mode fcpe --tag quick_test

# Diagnostic analysis of existing outputs
python scripts/diagnose.py

# Diagnostic with fresh extraction (no cache)
python scripts/diagnose.py --reuse-output=false

# Extract single MP3 to MusicXML
python scripts/extract.py test/꿈의\ 버스.mp3 -o output/result.musicxml --mode fcpe

# List reference melody patterns
python scripts/analyze_reference.py
```

### Key Design Rules

**Rule 4 (Output = Evaluation Identity)**
- `evaluate.py` **must** use round-trip: pipeline → save MusicXML → load MusicXML → compare
- Never apply transformations (time offset, octave shift) during evaluation
- Generated and reference notes must be compared **exactly as saved**

**Tolerance vs Transformation**
- Evaluation applies **tolerance** (e.g., ±50ms onset, ±0.5 semitone pitch tolerance) to define matching
- Evaluation **never applies transformation** (e.g., no octave correction, no time shift in the evaluation pipeline)
  - Self-contained octave corrections in `postprocess.py` are OK (part of pipeline output)
  - Evaluation-time transformations (e.g., fitting gen to ref via offset) are forbidden

**Version Tagging**
- Experiment results must be saved as `results/vNN.json` (e.g., `v20.json`, `v21_fcpe.json`)
- Always document in `PROJECT_DIRECTIVES.md` if results show significant change
- Results file should include:
  - `mode` (which F0 extractor was used)
  - `ref_method` (which reference extraction method)
  - Per-song metrics: `melody_f1_strict`, `melody_f1_lenient`, `pc_f1`, `onset_f1`, `chroma_similarity`, `contour_similarity`
  - Summary averages

**No Reference Contamination**
- `extract.py` takes MP3 only, no reference MXL
- `pipeline.extract_melody()` must never receive `ref_notes` parameter
- `postprocess.py` must never use reference data for correction

### Available Modes

| Mode | F0 Extractor | Speed | Notes |
|------|--------------|-------|-------|
| `crepe` | CREPE (torchcrepe) | ~1350s/song (CPU) | Default, high-quality pitch, subharmonic issues |
| `fcpe` | FCPE (torchfcpe) | ~2-5s/song | 750x faster, robust to subharmonic, baseline `mel_strict=0.090` |
| `rmvpe` | RMVPE (RVC model) | ~2-6s/song | Subharmonic-resistant, but lower `mel_strict=0.061` vs FCPE |
| `bp` | Basic Pitch (meta-learning) | ~25s/song | Fast, lower accuracy (53x vs CREPE), useful for fast iteration |
| `onset` | FCPE + onset-based segmentation | ~5s/song | Syllable-aware, unstable across songs, **not recommended** |
| `hybrid` | FCPE + hybrid segmenter | ~5s/song | Onset-merged segmentation, experimental, **not recommended** |

### Reference Extraction Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| `skyline` (default) | Top line of Part 0 (right hand) | Standard; works best for piano sheet music |
| `contour` | Contour-following from Part 0 | Experimental; less accurate for standard sheet music |

### Primary Metric

**`melody_f1_strict`** — primary metric for all evaluations:
- Definition: F1 score between reference and generated notes
- Matching criteria: exact pitch (within 0.5 semitone) AND onset within ±50ms
- Baseline (v19, FCPE): `avg=0.090` across 8 songs
- Target (Phase 1): `0.13+`; (Phase 2): `0.15`

### Supplementary Metrics

| Metric | Definition | Notes |
|--------|-----------|-------|
| `melody_f1_lenient` | Pitch ±2 semitones, onset ±100ms | Captures approximate melody shape |
| `pc_f1` | Pitch class (chroma) matching, ±50ms onset | Octave-invariant |
| `onset_f1` | Onset only (pitch-independent) | Rhythmic accuracy |
| `chroma_similarity` | Cosine similarity of chroma vectors | Pitch class sequence accuracy |
| `contour_similarity` | Interval sequence matching | Melodic contour shape |
| `perceptual_score` | Weighted blend: 0.4*pitch_acc + 0.3*rhythm + 0.3*contour | Human perception proxy |
| `mel_strict_oct` | Pitch ±1 octave, onset ±50ms | Measures octave-register forgiveness |

## Dependencies

### Python Runtime
- `python >= 3.10`
- `torch`, `torchaudio` — deep learning backend
- `torchcrepe` — CREPE F0 extraction
- `torchfcpe` — FCPE F0 extraction
- `librosa` — audio analysis, onset detection
- `music21` — MusicXML parsing and generation
- `mir_eval` — melody evaluation metrics (F1, V-measure)
- `scipy` — signal processing

### Data Dependencies
- `test/*.mp3` — 8 test songs (Korean K-pop)
- `test/*.mxl` — corresponding reference piano sheet music
- `test/cache/` — vocal separation cache (generated on first run by `vocal_separator.py`)

### Pipeline Module Dependencies
All scripts import from `core/`:
- `core/pipeline.py` — `extract_melody(mp3_path, ..., mode="fcpe")`
- `core/musicxml_writer.py` — `load_musicxml_notes(path)`
- `core/reference_extractor.py` — `extract_reference_melody(mxl_path)`
- `core/comparator.py` — `compare_melodies(ref_notes, gen_notes)`
- `core/types.py` — `Note` dataclass

### External Model Files
- Models auto-downloaded on first use and cached in `~/.cache/torch/models/`
- RMVPE model (172MB) requires HuggingFace network access
- All models run on CPU (no GPU required, but slow)

## Notes

- **FCPE is the current baseline** (`--mode fcpe`, `mel_strict=0.090`)
- **Evaluation takes time**: CREPE ~25-30 min / 8 songs (CPU bound); FCPE ~10s; consider using FCPE for iteration
- **Cache locality**: keep `test/cache/` in repo for fast vocal separation reuse
- **Results versioning**: always save experiment results with unique version tag (e.g., `v20_fcpe.json`) and document in `PROJECT_DIRECTIVES.md`

