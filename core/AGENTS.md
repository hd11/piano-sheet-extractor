<!-- Parent: ../AGENTS.md -->

# core/

## Purpose

Core melody extraction pipeline modules. Implements the complete audio→melody workflow:

```
MP3 → vocal_separator (Demucs) → pitch_extractor (CREPE/FCPE/RMVPE)
    → note_segmenter (F0→Notes) → postprocess (self-contained fixes)
    → musicxml_writer (save/load round-trip)
```

Single entry point: `extract_melody(mp3_path)` in `pipeline.py`. No reference data enters the pipeline. All postprocessing corrections are self-contained using only extracted notes and source audio.

## Key Files

| File | Description | Key Functions/Classes |
|------|-------------|----------------------|
| `pipeline.py` | Single entry point for end-to-end extraction. Orchestrates Demucs → F0 → segmentation → postprocess → MusicXML. Supports 7 modes: crepe, fcpe, rmvpe, ensemble, onset, hybrid, bp. | `extract_melody(mp3_path, cache_dir, output_path, mode)` |
| `types.py` | Common data types used throughout pipeline. | `Note` (pitch, onset, duration, velocity), `F0Contour` (times, frequencies, confidence) |
| `vocal_separator.py` | Demucs-based vocal/instrumental separation with .npz caching. | `separate_vocals(mp3_path, cache_dir)` |
| `pitch_extractor.py` | CREPE F0 extraction via torchcrepe with Viterbi decoding. | `extract_f0(audio, sr)` returns `F0Contour` |
| `pitch_extractor_fcpe.py` | FCPE F0 extraction via torchfcpe. Binary confidence (0/1). Faster than CREPE. | `extract_f0(audio, sr)` returns `F0Contour` |
| `pitch_extractor_rmvpe.py` | RMVPE F0 extraction. Alternative pitch method. | `extract_f0(audio, sr)` returns `F0Contour` |
| `pitch_extractor_ensemble.py` | Ensemble voting across FCPE and RMVPE with confidence weighting. | `extract_f0_ensemble(audio, sr)` returns `F0Contour` |
| `note_segmenter.py` | F0 contour → Note list conversion. 4 segmentation strategies: standard, onset-based, hybrid, quantized. | `segment_notes(contour)`, `segment_notes_onset(contour, audio, sr)`, `segment_notes_hybrid(contour, audio, sr)`, `segment_notes_quantized(contour, bpm)` |
| `postprocess.py` | **Self-contained** note cleanup: outlier removal, global/self octave correction, vocal range clipping, diatonic gating, beat snapping, deduplication. **ARCHITECTURE GUARD: No ref_notes parameter.** | `postprocess_notes(notes, audio, sr, bpm, beat_times)` |
| `comparator.py` | Tolerance-based melody evaluation metrics. **NO transformations.** Primary: `melody_f1_strict` (exact pitch, 50ms onset). | `compare_melodies(ref_notes, gen_notes)` returns dict with 12+ metrics |
| `musicxml_writer.py` | MusicXML save/load (round-trip). Implements Rule 4 requirement. | `save_musicxml(notes, output_path, bpm, time_sig)`, `load_musicxml_notes(mxl_path)` |
| `reference_extractor.py` | Extract melody from reference MXL files. **For evaluation only — never called in pipeline.** | `extract_melody_from_mxl(mxl_path, method="skyline")`, `extract_melody_contour(mxl_path, method="contour")` |
| `note_extractor_bp.py` | Basic Pitch + CQT-based note extraction (alternative to F0-based pipeline). | `extract_notes_bp(audio, sr)` |
| `note_extractor_some.py` | Experimental note extraction methods. | Various alternative approaches |
| `rmvpe_model.py` | RMVPE model implementation and utilities. | Model loading and inference helpers |

## For AI Agents

### Before Starting Any Task

1. **Read `../PROJECT_DIRECTIVES.md` first** — This documents absolute constraints and all v1–v25 experiments. Never skip.
2. **Primary metric**: `melody_f1_strict` (exact pitch + 50ms onset tolerance, via `comparator.py`)
3. **Current baseline**: TBD during v1 reset 8-song evaluation
4. **Know Rule 4**: MusicXML round-trip is the evaluation identity. Outputs must round-trip faithfully.

### Absolute Constraints (5 Rules)

1. **MP3 only** — `extract_melody()` takes no `ref_notes` parameter. No reference data enters pipeline.
2. **Reference is analysis only** — Never fit to reference data. Use for pattern understanding only.
3. **Log all work** — Update `../PROJECT_DIRECTIVES.md` with version tag, summary, metrics.
4. **Output = Evaluation Identity** — Test via: MusicXML save → load → compare against reference.
5. **Tolerance, not transformation** — Comparator only measures tolerance windows. No octave/time offset corrections in evaluation.

### Architecture Guard Rails

```python
# FORBIDDEN: ref_notes parameter in pipeline.py
extract_melody(mp3_path, ...)  # ✓ NO ref_notes
postprocess_notes(notes, audio, sr, ...)  # ✓ NO ref_notes

# FORBIDDEN: reference data in postprocess.py
def postprocess_notes(notes, ...):  # Takes only notes, audio, sr, bpm
    # All corrections are self-contained

# FORBIDDEN: transformation in comparator.py
compare_melodies(ref, gen)  # ✓ Measures tolerance only, NO offset/octave correction
```

### Common Workflows

#### Extract Melody from MP3
```python
from core.pipeline import extract_melody
from pathlib import Path

notes = extract_melody(
    mp3_path=Path("test/song.mp3"),
    cache_dir=Path("test/cache"),
    output_path=Path("output/song.mxl"),
    mode="fcpe"  # or "crepe", "rmvpe", "ensemble", "onset", "hybrid", "bp"
)
# Returns: List[Note], also writes MusicXML
```

#### Evaluate Against Reference (Round-Trip)
```python
from core.pipeline import extract_melody
from core.musicxml_writer import load_musicxml_notes
from core.comparator import compare_melodies
from core.reference_extractor import extract_melody_from_mxl

# Extract and save
gen_notes = extract_melody("test/song.mp3", output_path="output/song.mxl")

# Reload from MusicXML (round-trip test)
loaded_notes = load_musicxml_notes("output/song.mxl")

# Compare
ref_notes = extract_melody_from_mxl("test/song.mxl")
metrics = compare_melodies(ref_notes, loaded_notes)
print(f"melody_f1_strict: {metrics['melody_f1_strict']:.3f}")
```

#### Add Custom Postprocessing
If adding a new postprocess step:
- Add it to `postprocess_notes()` in `postprocess.py`
- Never introduce a `ref_notes` parameter
- Test via round-trip: save → load → compare
- Document the step in the docstring
- Update metrics in `../PROJECT_DIRECTIVES.md`

#### Test a Single Mode
```bash
cd /Users/lee/projects/piano-sheet-extractor
python scripts/ablation_test.py --song "꿈의 버스" --mode fcpe
```

#### Evaluate All 8 Test Songs
```bash
python scripts/evaluate.py --mode fcpe --output results/vNN.json
```

### Testing Requirements

**Before committing changes:**

1. **Syntax check** — All Python files must parse without import errors
2. **Type consistency** — `extract_melody()` returns `List[Note]`, never transforms
3. **Round-trip test** — At least one song: extract → save → load → compare
4. **Metrics reported** — Log melody_f1_strict in results

Example test:
```bash
# Quick validation
python -c "from core.pipeline import extract_melody; extract_melody('test/꿈의_버스.mp3')"

# Full evaluation
python scripts/evaluate.py --mode fcpe --output results/test.json
```

### Known Issues & Limitations

#### CREPE on CPU
- Single 161s audio: ~25 minutes (no GPU acceleration)
- Use FCPE for faster iteration (3–5x faster)
- GPU required for large-scale experiments

#### CREPE Subharmonic Bias
- CREPE sometimes locks to subharmonic (1 octave below true pitch)
- Detected and corrected by `_global_octave_adjust()` in `postprocess.py`
- Heuristic: if median MIDI < 66, add 12 semitones
- Known songs: "IRIS OUT" (difficult), "비비드라라러브" (structural mismatch with reference)

#### BPM Estimation Variance
- `librosa.beat.beat_track()` on vocals-only audio can be unreliable
- Solution: estimate BPM from mix (drums + bass visible), as `pipeline.py` does
- Some songs may require manual BPM tuning

#### Beat Snap Collisions
- Fast songs (BPM ≥ 140) snap to 16th-note grid
- Collision detection (`_dedup_close_onsets()`) removes notes within 30ms
- If excessive note removal, check BPM estimation

#### Reference Mismatch
- Some test songs have structural differences (e.g., backing vocals, arrangement)
- Never apply reference-based correction; only use for pattern analysis
- Example: "여름이었다" has alternative runs in reference that don't match vocal F0

### Dependencies (Internal)

**Imports within core/**
- `types.Note`, `types.F0Contour` — Used by all modules
- `vocal_separator.separate_vocals()` — Called by `pipeline.py`
- `pitch_extractor*.extract_f0()` — Multiple pitch methods
- `note_segmenter.segment_notes*()` — F0 → Notes conversion
- `postprocess.postprocess_notes()` — Self-contained cleanup
- `musicxml_writer.save_musicxml()` — Write output
- `reference_extractor.extract_melody_from_mxl()` — Evaluation only (not in pipeline)
- `comparator.compare_melodies()` — Evaluation only (not in pipeline)

**External Dependencies**
- `torch`, `torchaudio` — Deep learning (Demucs, CREPE, FCPE, RMVPE)
- `demucs` — Vocal/instrumental separation
- `torchcrepe` — CREPE F0 extraction
- `torchfcpe` — FCPE F0 extraction
- `librosa` — Onset detection, beat tracking, resampling
- `music21` — MusicXML parse/generate
- `mir_eval` — Melody evaluation metrics (onset, transcription, chroma)
- `numpy` — Numerical computation
- `scipy` — Signal processing (filters, interpolation)

### Code Style & Conventions

- **Type hints**: All functions should have full type annotations (input and return)
- **Docstrings**: Module and function docstrings required. Include Args, Returns, Raises
- **No ref_notes**: Architecture guard — any function accepting reference data must be isolated (e.g., in `reference_extractor.py` or `comparator.py`, never in pipeline/postprocess)
- **Logging**: Use `logger.info()` for major steps, `logger.debug()` for details
- **Note**: MIDI pitch (0–127), time in seconds, duration in seconds
- **F0**: Frequency in Hz, 0.0 = unvoiced, confidence 0.0–1.0

### Debugging Checklist

**Melody is too high/low (octave off)**
- Check `_global_octave_adjust()` heuristic in `postprocess.py`
- Review CREPE subharmonic bias detection
- Examine F0 contour before segmentation (`extract_f0_*.py`)

**Too many/few notes**
- Check `segment_notes()` parameters: `min_note_duration` (default 60ms), gap bridging threshold
- Review postprocess deduplication: `_dedup_close_onsets()` (30ms window)
- Inspect beat snap grid resolution (8th vs 16th notes based on BPM)

**Onsets are inaccurate**
- Verify beat track: `librosa.beat.beat_track()` may fail on vocals-only
- Try `segment_notes_onset()` (syllable-based) or `segment_notes_hybrid()` (blend)
- Check BPM estimation: should match mix, not vocals

**MusicXML round-trip lost notes**
- Verify `save_musicxml()` writes all notes without filtering
- Verify `load_musicxml_notes()` reads back all saved notes
- Check for time signature/BPM mismatch causing quantization loss

## Testing Utilities (in scripts/)

- `scripts/ablation_test.py` — Single-song quick evaluation
- `scripts/evaluate.py` — Full 8-song evaluation with results JSON
- `scripts/diagnose.py` — Detailed pipeline tracing
- `scripts/extract.py` — CLI extraction with mode selection
- `scripts/analyze_reference.py` — Reference pattern analysis (not for pipeline)

---

*Last updated: 2026-03-10*
