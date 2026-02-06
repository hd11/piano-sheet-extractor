"""
MIDI 파서 모듈 단위 테스트
"""

import pytest
from pathlib import Path
from core.midi_parser import Note, parse_midi
import pretty_midi


class TestNoteDataclass:
    """Note 데이터클래스 테스트"""

    def test_note_creation(self):
        """Note 객체 생성 및 속성 검증"""
        note = Note(pitch=60, onset=0.0, duration=0.5, velocity=80)

        assert note.pitch == 60
        assert note.onset == 0.0
        assert note.duration == 0.5
        assert note.velocity == 80

    def test_note_with_different_values(self):
        """다양한 값으로 Note 생성"""
        note = Note(pitch=72, onset=1.5, duration=0.25, velocity=100)

        assert note.pitch == 72
        assert note.onset == 1.5
        assert note.duration == 0.25
        assert note.velocity == 100

    def test_note_boundary_values(self):
        """MIDI 범위 경계값 테스트"""
        # 최소값
        note_min = Note(pitch=0, onset=0.0, duration=0.01, velocity=0)
        assert note_min.pitch == 0
        assert note_min.velocity == 0

        # 최대값
        note_max = Note(pitch=127, onset=100.0, duration=10.0, velocity=127)
        assert note_max.pitch == 127
        assert note_max.velocity == 127


class TestParseMidiNormal:
    """parse_midi() 정상 동작 테스트"""

    def test_parse_midi_returns_list(self, tmp_path):
        """parse_midi()가 Note 리스트 반환"""
        # 간단한 MIDI 파일 생성
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5)
        )
        pm.instruments.append(instrument)

        midi_path = tmp_path / "test.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Note)

    def test_parse_midi_note_properties(self, tmp_path):
        """파싱된 Note의 속성 검증"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=64, start=0.5, end=1.0)
        )
        pm.instruments.append(instrument)

        midi_path = tmp_path / "test.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert result[0].pitch == 64
        assert result[0].onset == 0.5
        assert result[0].duration == 0.5  # 1.0 - 0.5
        assert result[0].velocity == 80

    def test_parse_midi_sorts_by_onset(self, tmp_path):
        """Note들이 onset 기준으로 정렬됨"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)

        # 역순으로 추가
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=67, start=2.0, end=2.5)
        )
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5)
        )
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=64, start=1.0, end=1.5)
        )

        pm.instruments.append(instrument)

        midi_path = tmp_path / "test.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        # onset 순서 검증
        assert result[0].onset == 0.0
        assert result[1].onset == 1.0
        assert result[2].onset == 2.0

    def test_parse_midi_multiple_notes(self, tmp_path):
        """여러 음표 파싱"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)

        # 5개의 음표 추가
        for i in range(5):
            instrument.notes.append(
                pretty_midi.Note(
                    velocity=80, pitch=60 + i, start=float(i), end=float(i) + 0.5
                )
            )

        pm.instruments.append(instrument)

        midi_path = tmp_path / "test.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert len(result) == 5
        for i, note in enumerate(result):
            assert note.pitch == 60 + i
            assert note.onset == float(i)


class TestParseMidiDrumExclusion:
    """parse_midi() 드럼 트랙 제외 테스트"""

    def test_parse_midi_excludes_drum_track(self, tmp_path):
        """드럼 트랙이 제외됨"""
        pm = pretty_midi.PrettyMIDI()

        # 드럼 트랙
        drum = pretty_midi.Instrument(program=0, is_drum=True)
        drum.notes.append(pretty_midi.Note(velocity=80, pitch=36, start=0.0, end=0.1))
        pm.instruments.append(drum)

        # 일반 악기
        instrument = pretty_midi.Instrument(program=0)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5)
        )
        pm.instruments.append(instrument)

        midi_path = tmp_path / "drums.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        # 드럼 음표는 제외, 일반 악기 음표만 포함
        assert len(result) == 1
        assert result[0].pitch == 60

    def test_parse_midi_only_drums(self, tmp_path):
        """드럼 트랙만 있는 경우"""
        pm = pretty_midi.PrettyMIDI()

        drum = pretty_midi.Instrument(program=0, is_drum=True)
        drum.notes.append(pretty_midi.Note(velocity=80, pitch=36, start=0.0, end=0.1))
        drum.notes.append(pretty_midi.Note(velocity=80, pitch=38, start=0.5, end=0.6))
        pm.instruments.append(drum)

        midi_path = tmp_path / "only_drums.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        # 모든 드럼 음표가 제외됨
        assert len(result) == 0

    def test_parse_midi_mixed_instruments(self, tmp_path):
        """드럼과 일반 악기 혼합"""
        pm = pretty_midi.PrettyMIDI()

        # 드럼 트랙
        drum = pretty_midi.Instrument(program=0, is_drum=True)
        drum.notes.append(pretty_midi.Note(velocity=80, pitch=36, start=0.0, end=0.1))
        drum.notes.append(pretty_midi.Note(velocity=80, pitch=38, start=0.5, end=0.6))
        pm.instruments.append(drum)

        # 첫 번째 일반 악기
        instrument1 = pretty_midi.Instrument(program=0)
        instrument1.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5)
        )
        pm.instruments.append(instrument1)

        # 두 번째 일반 악기
        instrument2 = pretty_midi.Instrument(program=1)
        instrument2.notes.append(
            pretty_midi.Note(velocity=80, pitch=72, start=1.0, end=1.5)
        )
        pm.instruments.append(instrument2)

        midi_path = tmp_path / "mixed.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        # 드럼 제외, 일반 악기 음표만 포함
        assert len(result) == 2
        assert result[0].pitch == 60
        assert result[1].pitch == 72


class TestParseMidiEdgeCases:
    """parse_midi() 엣지 케이스 테스트"""

    def test_parse_midi_empty_file(self, tmp_path):
        """빈 MIDI 파일"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        pm.instruments.append(instrument)

        midi_path = tmp_path / "empty.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_midi_no_instruments(self, tmp_path):
        """악기가 없는 MIDI 파일"""
        pm = pretty_midi.PrettyMIDI()
        # 악기 추가 안 함

        midi_path = tmp_path / "no_instruments.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_midi_zero_duration_note(self, tmp_path):
        """0 길이 음표"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.5, end=0.5)
        )
        pm.instruments.append(instrument)

        midi_path = tmp_path / "zero_duration.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert len(result) == 1
        assert result[0].duration == 0.0

    def test_parse_midi_very_small_duration(self, tmp_path):
        """매우 짧은 음표"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.001)
        )
        pm.instruments.append(instrument)

        midi_path = tmp_path / "tiny.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert len(result) == 1
        assert result[0].duration == pytest.approx(0.001, abs=1e-6)

    def test_parse_midi_simultaneous_notes(self, tmp_path):
        """동시 발음 음표들"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)

        # 같은 시간에 시작하는 3개 음표
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5)
        )
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=64, start=0.0, end=0.5)
        )
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=67, start=0.0, end=0.5)
        )

        pm.instruments.append(instrument)

        midi_path = tmp_path / "simultaneous.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert len(result) == 3
        # 모두 같은 onset
        assert all(note.onset == 0.0 for note in result)

    def test_parse_midi_velocity_preservation(self, tmp_path):
        """음표의 velocity 보존"""
        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)

        velocities = [30, 60, 90, 127]
        for i, vel in enumerate(velocities):
            instrument.notes.append(
                pretty_midi.Note(
                    velocity=vel, pitch=60, start=float(i), end=float(i) + 0.5
                )
            )

        pm.instruments.append(instrument)

        midi_path = tmp_path / "velocities.mid"
        pm.write(str(midi_path))

        result = parse_midi(midi_path)

        assert len(result) == 4
        for i, note in enumerate(result):
            assert note.velocity == velocities[i]


class TestParseMidiWithRealFile:
    """실제 테스트 데이터 파일을 사용한 테스트"""

    def test_parse_midi_reference_file(self):
        """reference.mid 파일 파싱"""
        midi_path = (
            Path(__file__).parent.parent
            / "golden"
            / "data"
            / "song_01"
            / "reference.mid"
        )

        if not midi_path.exists():
            pytest.skip(f"Test data not found: {midi_path}")

        result = parse_midi(midi_path)

        # 기본 검증
        assert isinstance(result, list)
        assert len(result) > 0

        # 모든 Note가 유효한 속성을 가짐
        for note in result:
            assert isinstance(note, Note)
            assert 0 <= note.pitch <= 127
            assert note.onset >= 0
            assert note.duration >= 0
            assert 0 <= note.velocity <= 127

        # onset 정렬 검증
        for i in range(len(result) - 1):
            assert result[i].onset <= result[i + 1].onset
