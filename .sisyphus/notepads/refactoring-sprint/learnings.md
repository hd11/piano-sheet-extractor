# Refactoring Sprint - Learnings

## [2026-02-06] Task 0: midi_parser Unit Tests

### Tests Created
- `test_note_creation` — Note dataclass creation and attribute verification
- `test_note_with_different_values` — Note with various pitch/onset/duration/velocity values
- `test_note_boundary_values` — MIDI range boundary values (0-127 for pitch/velocity)
- `test_parse_midi_returns_list` — parse_midi() returns List[Note]
- `test_parse_midi_note_properties` — Parsed notes have correct pitch, onset, duration, velocity
- `test_parse_midi_sorts_by_onset` — Notes sorted by onset time
- `test_parse_midi_multiple_notes` — Multiple notes parsed correctly
- `test_parse_midi_excludes_drum_track` — Drum tracks excluded from results
- `test_parse_midi_only_drums` — MIDI with only drums returns empty list
- `test_parse_midi_mixed_instruments` — Mixed drum and non-drum instruments handled correctly
- `test_parse_midi_empty_file` — Empty MIDI file returns empty list
- `test_parse_midi_no_instruments` — MIDI with no instruments returns empty list
- `test_parse_midi_zero_duration_note` — Zero-length notes handled
- `test_parse_midi_very_small_duration` — Very short notes (1ms) handled
- `test_parse_midi_simultaneous_notes` — Multiple notes at same onset
- `test_parse_midi_velocity_preservation` — Velocity values preserved (0-127)
- `test_parse_midi_reference_file` — Real test data file (reference.mid) parsing

### Test Results
- **Total tests**: 17
- **Test classes**: 5 (TestNoteDataclass, TestParseMidiNormal, TestParseMidiDrumExclusion, TestParseMidiEdgeCases, TestParseMidiWithRealFile)
- **Coverage**: 
  - Note dataclass: creation, properties, boundary values
  - parse_midi function: normal operation, drum exclusion, edge cases
  - Real file parsing with golden test data

### Key Findings
- Note dataclass is simple: 4 attributes (pitch, onset, duration, velocity)
- parse_midi() uses pretty_midi library for MIDI parsing
- Drum track exclusion via `instrument.is_drum` flag
- Notes automatically sorted by onset in parse_midi()
- Duration calculated as `note.end - note.start` (already in seconds)
- Test data available at `backend/tests/golden/data/song_01/reference.mid`

### Test Data Used
- Dynamically created MIDI files using pretty_midi.PrettyMIDI
- Real test file: `backend/tests/golden/data/song_01/reference.mid`
- Fixtures: tmp_path (pytest built-in)

### Implementation Notes
- Tests follow pytest conventions (test_*.py, Test* classes, test_* functions)
- Uses pytest fixtures for temporary directories (tmp_path)
- Tests create MIDI files on-the-fly for isolation
- Comprehensive edge case coverage: empty files, zero duration, simultaneous notes, velocity ranges
- Drum exclusion tested with is_drum=True flag
