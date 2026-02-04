## 2026-02-04: Reference Structure Analysis

### Key Discoveries

1. **Reference files are full piano arrangements, not melody-only**
   - All 8 songs have single part "피아노" with 2 staves
   - Staff 1 (right hand) = melody + harmony
   - Staff 2 (left hand) = bass + accompaniment
   - This explains why current similarity is so low (0.05-0.33%)

2. **Voice structure is consistent across all songs**
   - Voice 1 = Primary melody (staff 1)
   - Voice 5 = Bass/accompaniment (staff 2)
   - Voice 2 = Rare, only in songs 01 and 03 for polyphonic passages

3. **Chord representation**
   - Chords use `<chord/>` marker for subsequent notes
   - 21-41% of notes are chord members
   - Song 03 and 07 have highest chord density (~40%)

4. **MXL file format**
   - MXL = ZIP archive containing score.xml
   - Can extract with `unzip reference.mxl`
   - Easy to parse with grep/sed for quick analysis

### Patterns Observed

- **Note density varies widely**: 11.83 to 21.74 notes/measure
- **Octave range**: Most songs span 5-6 octaves (1-6 or 1-5)
- **Staff balance**: Staff 1 and Staff 2 have similar note counts (roughly 50/50 split)

### Melody Extraction Strategy

**Recommended**: Filter by `voice == 1`
- Most reliable indicator of melody
- Works across all 8 songs
- Handles polyphony correctly

**Alternative**: Filter by `staff == 1`
- Simpler but includes harmony
- May need additional filtering for chords

**Chord handling**: Take highest note from chords in melody voice
- Preserves melodic contour
- Matches Basic Pitch behavior (single-line melody)

### Technical Notes

- Voice numbering is not sequential (1, 2, 5) - MuseScore convention
- `<chord/>` element has no closing tag (self-closing)
- Duration is in quarterLength units (not seconds)

### Next Steps

This analysis enables Task 3 (melody extraction implementation).

---

## 2026-02-04: Note Loss Measurement Tool Implementation

### Key Findings from measure_note_loss.py

1. **Unexpected Note Gain Instead of Loss**
   - Initial assumption: MusicXML conversion would lose notes
   - Actual result: Notes are being ADDED during conversion (negative loss rate)
   - Average loss rate across 8 songs: **-8.5%** (8.5% gain)
   - Range: -2.0% (song_02) to -14.0% (song_05)

2. **Measurement Results by Song**
   ```
   song_01: 1164 → 1296 notes (loss: -11.3%)
   song_02: 356 → 363 notes (loss: -2.0%)
   song_03: 1229 → 1323 notes (loss: -7.6%)
   song_04: 1539 → 1637 notes (loss: -6.4%)
   song_05: 2062 → 2350 notes (loss: -14.0%)
   song_06: 2486 → 2713 notes (loss: -9.1%)
   song_07: 1869 → 2003 notes (loss: -7.2%)
   song_08: 1700 → 1873 notes (loss: -10.2%)
   Total: 12405 → 13558 notes
   ```

3. **Possible Explanations for Note Gain**
   - Chord expansion: Chords in MIDI may be expanded to individual notes in MusicXML
   - Quantization artifacts: The 16th-note quantization grid may create additional notes
   - music21 parsing: When parsing MusicXML back, chords are counted as multiple notes
   - Duration rounding: Quantized durations might create additional note events

4. **Tool Architecture**
   - Round-trip pipeline: Audio → MIDI → MusicXML → Parse → Count
   - Uses Basic Pitch for audio-to-MIDI conversion (slow but accurate)
   - Counts both Note and Chord elements (chords counted as multiple notes)
   - JSON output format: `{song, input_notes, output_notes, loss_rate}`
   - Supports both single song and batch processing

5. **Performance Characteristics**
   - Basic Pitch model loading: ~10 seconds per run
   - Audio processing: ~30-60 seconds per song (depends on length)
   - MusicXML conversion: ~5-10 seconds per song
   - Total time for 8 songs: ~5-10 minutes

6. **Code Patterns Used**
   - Temporary directories for intermediate files
   - Logging suppression for verbose dependencies
   - Progress output to stderr, results to stdout
   - Graceful error handling with traceback in verbose mode
   - Support for both human-readable and JSON output formats

### Technical Insights

#### music21 Note Counting
- `music21.note.Note`: Single note element
- `music21.chord.Chord`: Multiple pitches at same time
- When counting, chords are expanded to individual note counts
- This explains why output count > input count

#### Quantization Effects
- 16th-note grid (0.25 quarterLength) is used for quantization
- Rounding can create small duration artifacts
- These artifacts may be preserved in MusicXML export

#### BPM Extraction
- BPM is extracted from Basic Pitch metadata
- Defaults to 120 BPM if not available
- Used for time conversion (seconds ↔ quarterLength)

---

## 2026-02-04: MusicXML Melody Extractor Implementation

### Key Implementation Details

1. **Voice-based filtering does NOT work with music21**
   - Original plan: Filter by `voice == 1` based on MusicXML structure
   - Reality: music21 flattens voice information when parsing
   - `element.voice` returns `None` for all notes after `score.flatten()`
   - Voice containers (`music21.stream.Voice`) are empty in parsed measures

2. **Part-based filtering is the solution**
   - music21 parses piano scores into 2 separate Part objects:
     - Part 0: Right hand (Staff 1) - contains melody
     - Part 1: Left hand (Staff 2) - contains bass
   - Use `score.parts[0]` to get melody part
   - Much simpler than voice filtering

3. **Extraction Pipeline**
   ```python
   1. Parse MusicXML/MXL with music21.converter.parse()
   2. Get first part (right hand): score.parts[0]
   3. Iterate part.flatten().notes
   4. For chords: take highest pitch (pitches[-1])
   5. Apply skyline algorithm (20ms tolerance)
   6. Filter short notes (<50ms)
   7. Resolve overlaps
   8. Normalize octave (C3-C6)
   ```

4. **Time Conversion**
   - music21 uses quarterLength (beat-based) for offsets
   - Our Note dataclass uses seconds
   - Conversion: `seconds = quarterLength * (60 / BPM)`
   - Tempo extracted from MetronomeMark or defaults to 120 BPM

### Extraction Results

- **Song 01**: 588 melody notes from 2040 total (28.8%)
- Within expected 10-30% range
- Skyline algorithm effectively reduces chord members

### Lessons Learned

1. **music21 parsing differs from raw MusicXML structure**
   - Don't assume music21 preserves all MusicXML attributes
   - Test actual parsed structure before implementing filters

2. **Note counting methods matter**
   - `score.flatten().notes` counts Chord objects as single elements
   - Must expand chords to get true note count: `len(chord.pitches)`
   - Total from reference-structure.md (2082) vs flatten() (1501)

3. **Debug scripts are essential**
   - Created `debug_voices.py` and `debug_voices2.py` to understand structure
   - Discovered Part-based structure through debugging

### Edge Cases Handled

- ChordSymbol (harmony annotations) - skipped
- Empty parts - raise error
- Missing tempo marking - default to 120 BPM
- Missing velocity - default to 80
