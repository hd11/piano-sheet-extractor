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

## [2026-02-06] Task 1: job_manager Unit Tests

### Tests Created
- test_create_job_generates_unique_id — Verifies UUID generation
- test_create_job_initializes_status_pending — Verifies status=PENDING on creation
- test_create_job_stores_source_and_metadata — Verifies source and kwargs storage
- test_create_job_sets_timestamps — Verifies created_at and updated_at ISO 8601 format
- test_create_job_initializes_optional_fields — Verifies error, analysis, current_stage initialization
- test_create_job_multiple_calls_unique_ids — Verifies multiple calls generate unique IDs
- test_get_job_returns_existing_job — Verifies job retrieval from file
- test_get_job_returns_none_when_not_found — Verifies None return for missing jobs
- test_get_job_parses_json_correctly — Verifies JSON parsing and field access
- test_get_job_handles_empty_metadata — Verifies empty metadata handling
- test_get_job_handles_completed_job_with_analysis — Verifies analysis data retrieval
- test_update_job_status_changes_status — Verifies status/progress/stage updates
- test_update_job_status_updates_timestamp — Verifies updated_at timestamp refresh
- test_update_job_status_handles_nonexistent_job — Verifies graceful handling of missing jobs
- test_update_job_status_preserves_other_fields — Verifies field preservation during updates
- test_update_job_status_progress_transitions — Verifies multiple status transitions
- test_update_job_status_with_empty_stage — Verifies empty stage parameter handling
- test_job_status_constants_exist — Verifies all JobStatus constants defined
- test_job_status_values — Verifies JobStatus constant values

### Mocking Strategy
- File I/O mocked using unittest.mock.patch and mock_open
- No actual file operations during tests
- Mocked: uuid.uuid4, _save_job, _get_job_dir, _get_job_file, Path.exists, file I/O
- Job data structure: {job_id, status, progress, current_stage, source, created_at, updated_at, error, analysis, metadata}

### Key Findings
- create_job() generates UUID, creates job directory, initializes job data with PENDING status
- get_job() reads JSON from file, returns None if file doesn't exist
- update_job_status() modifies status/progress/stage, updates timestamp, preserves other fields
- All functions handle edge cases: missing jobs, empty metadata, None values
- Job lifecycle states: PENDING → PROCESSING → GENERATING → COMPLETED/FAILED
- Timestamps use ISO 8601 format with 'Z' suffix (UTC)

### Test Coverage
- 19 test functions across 4 test classes
- All tests use mocking for file I/O (no actual files created)
- Tests focus on core functions only: create_job, get_job, update_job_status
- Edge cases covered: missing jobs, empty fields, multiple transitions, timestamp updates
