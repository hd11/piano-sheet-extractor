"""
Golden Test - Smoke Mode

Phase 1: 처리 성공 여부만 검증
- 각 테스트 곡이 에러 없이 처리되는지 확인
- 출력 파일(melody.mid, sheet_*.musicxml)이 생성되는지 확인
- 처리 시간 측정

Phase 2 (추후): Reference MIDI와 비교하여 정확도 측정
"""

import pytest
import time
from pathlib import Path
import json

# Import core modules
from core.audio_to_midi import convert_audio_to_midi
from core.melody_extractor import extract_melody
from core.midi_parser import parse_midi
from core.audio_analysis import analyze_audio
from core.difficulty_adjuster import generate_all_sheets


@pytest.mark.golden
@pytest.mark.smoke
class TestGoldenSmoke:
    """Golden Test - Smoke Mode: 처리 성공 여부 검증"""

    def test_audio_files_exist(self, test_audio_files):
        """테스트 데이터 존재 확인"""
        assert len(test_audio_files) >= 5, (
            f"Expected at least 5 test files, found {len(test_audio_files)}"
        )

        for audio_file in test_audio_files:
            assert audio_file.exists(), f"Test file not found: {audio_file}"
            assert audio_file.stat().st_size > 0, f"Test file is empty: {audio_file}"

    @pytest.mark.parametrize("audio_file", pytest.lazy_fixture("test_audio_files"))
    def test_full_pipeline_smoke(self, audio_file, job_storage_path):
        """
        전체 파이프라인 Smoke 테스트

        검증 항목:
        1. Basic Pitch 변환 성공
        2. 멜로디 추출 성공
        3. 분석 성공 (BPM/Key/Chord)
        4. 3단계 난이도 MusicXML 생성 성공
        5. 모든 출력 파일 존재
        """
        print(f"\n{'=' * 60}")
        print(f"Testing: {audio_file.name}")
        print(f"{'=' * 60}")

        start_time = time.time()
        job_dir = job_storage_path / audio_file.stem
        job_dir.mkdir(exist_ok=True)

        try:
            # Step 1: Audio → MIDI (Basic Pitch)
            print("Step 1: Converting audio to MIDI...")
            raw_midi_path = job_dir / "raw.mid"
            result = convert_audio_to_midi(audio_file, raw_midi_path)
            assert raw_midi_path.exists(), "raw.mid not created"
            assert result["note_count"] > 0, "No notes detected in MIDI"
            print(f"  ✓ MIDI created: {result['note_count']} notes")

            # Step 2: Melody extraction
            print("Step 2: Extracting melody...")
            melody_notes = extract_melody(str(raw_midi_path))
            assert len(melody_notes) > 0, "No melody notes extracted"

            # Save melody MIDI
            melody_midi_path = job_dir / "melody.mid"
            import pretty_midi

            pm = pretty_midi.PrettyMIDI()
            instrument = pretty_midi.Instrument(program=0)
            for note in melody_notes:
                midi_note = pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.onset,
                    end=note.onset + note.duration,
                )
                instrument.notes.append(midi_note)
            pm.instruments.append(instrument)
            pm.write(str(melody_midi_path))
            assert melody_midi_path.exists(), "melody.mid not created"
            print(f"  ✓ Melody extracted: {len(melody_notes)} notes")

            # Step 3: Audio analysis
            print("Step 3: Analyzing audio...")
            analysis = analyze_audio(audio_file)
            assert "bpm" in analysis, "BPM not detected"
            assert "key" in analysis, "Key not detected"
            assert "chords" in analysis, "Chords not detected"

            # Save analysis
            analysis_path = job_dir / "analysis.json"
            with open(analysis_path, "w") as f:
                json.dump(analysis, f, indent=2)
            print(
                f"  ✓ Analysis complete: BPM={analysis['bpm']:.1f}, Key={analysis['key']}"
            )

            # Step 4: Generate difficulty sheets
            print("Step 4: Generating difficulty sheets...")
            sheets = generate_all_sheets(job_dir, melody_midi_path, analysis)

            # Verify all sheets created
            for difficulty in ["easy", "medium", "hard"]:
                sheet_path = job_dir / f"sheet_{difficulty}.musicxml"
                assert sheet_path.exists(), f"sheet_{difficulty}.musicxml not created"
                assert sheet_path.stat().st_size > 0, (
                    f"sheet_{difficulty}.musicxml is empty"
                )
            print(f"  ✓ All difficulty sheets generated")

            # Success
            elapsed = time.time() - start_time
            print(f"\n✅ SUCCESS: {audio_file.name}")
            print(f"   Processing time: {elapsed:.2f}s")
            print(f"   Output files: {len(list(job_dir.glob('*')))} files")

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ FAILED: {audio_file.name}")
            print(f"   Error: {str(e)}")
            print(f"   Time before failure: {elapsed:.2f}s")
            raise

    def test_generate_summary_report(self, test_audio_files, job_storage_path):
        """테스트 결과 요약 리포트 생성"""
        report = {
            "total_files": len(test_audio_files),
            "test_files": [f.name for f in test_audio_files],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        report_path = job_storage_path / "golden_test_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n{'=' * 60}")
        print(f"Golden Test Summary")
        print(f"{'=' * 60}")
        print(f"Total test files: {report['total_files']}")
        print(f"Report saved: {report_path}")
