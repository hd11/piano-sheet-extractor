"""
멜로디 추출 모듈 단위 테스트
"""

import pytest
from pathlib import Path
from backend.core.melody_extractor import (
    Note,
    apply_skyline,
    filter_short_notes,
    resolve_overlaps,
    normalize_octave,
    extract_melody,
)


@pytest.fixture
def sample_notes():
    """기본 샘플 Note 리스트"""
    return [
        Note(pitch=60, onset=0.0, duration=0.5, velocity=80),
        Note(pitch=64, onset=0.0, duration=0.5, velocity=80),  # 동시 발음
        Note(pitch=67, onset=1.0, duration=0.3, velocity=80),
        Note(pitch=65, onset=1.5, duration=0.02, velocity=80),  # 짧은 음 (20ms)
    ]


@pytest.fixture
def overlapping_notes():
    """겹치는 음표들"""
    return [
        Note(pitch=60, onset=0.0, duration=1.0, velocity=80),
        Note(pitch=64, onset=0.5, duration=0.5, velocity=80),  # 겹침
        Note(pitch=67, onset=1.5, duration=0.3, velocity=80),
    ]


@pytest.fixture
def out_of_range_notes():
    """범위 밖의 음표들"""
    return [
        Note(pitch=36, onset=0.0, duration=0.5, velocity=80),  # C2 (범위 밖)
        Note(pitch=60, onset=0.5, duration=0.5, velocity=80),  # C4 (범위 내)
        Note(pitch=96, onset=1.0, duration=0.5, velocity=80),  # C7 (범위 밖)
    ]


class TestApplySkyline:
    """Skyline 알고리즘 테스트"""

    def test_skyline_selects_highest_pitch(self):
        """동시 발음 중 최고음 선택"""
        notes = [
            Note(pitch=60, onset=0.0, duration=0.5, velocity=80),
            Note(pitch=64, onset=0.0, duration=0.5, velocity=80),
            Note(pitch=67, onset=0.0, duration=0.5, velocity=80),
        ]
        result = apply_skyline(notes)

        assert len(result) == 1
        assert result[0].pitch == 67  # 최고음

    def test_skyline_respects_onset_tolerance(self):
        """ONSET_TOLERANCE 경계 테스트"""
        notes = [
            Note(pitch=60, onset=0.0, duration=0.5, velocity=80),
            Note(pitch=64, onset=0.015, duration=0.5, velocity=80),  # 15ms 차이 (동시)
            Note(pitch=67, onset=0.025, duration=0.5, velocity=80),  # 25ms 차이 (별개)
        ]
        result = apply_skyline(notes)

        assert len(result) == 2
        assert result[0].pitch == 64  # 60과 64 중 최고음
        assert result[1].pitch == 67

    def test_skyline_empty_list(self):
        """빈 리스트 처리"""
        result = apply_skyline([])
        assert result == []

    def test_skyline_single_note(self):
        """단일 음표"""
        notes = [Note(pitch=60, onset=0.0, duration=0.5, velocity=80)]
        result = apply_skyline(notes)

        assert len(result) == 1
        assert result[0].pitch == 60


class TestFilterShortNotes:
    """짧은 음표 필터링 테스트"""

    def test_filter_removes_short_notes(self):
        """50ms 미만 음표 제거"""
        notes = [
            Note(pitch=60, onset=0.0, duration=0.1, velocity=80),  # 100ms (유지)
            Note(pitch=64, onset=0.5, duration=0.02, velocity=80),  # 20ms (제거)
            Note(pitch=67, onset=1.0, duration=0.05, velocity=80),  # 50ms (유지)
        ]
        result = filter_short_notes(notes)

        assert len(result) == 2
        assert result[0].pitch == 60
        assert result[1].pitch == 67

    def test_filter_boundary_50ms(self):
        """정확히 50ms 경계값"""
        notes = [
            Note(pitch=60, onset=0.0, duration=0.049, velocity=80),  # 49ms (제거)
            Note(pitch=64, onset=0.5, duration=0.05, velocity=80),  # 50ms (유지)
            Note(pitch=67, onset=1.0, duration=0.051, velocity=80),  # 51ms (유지)
        ]
        result = filter_short_notes(notes)

        assert len(result) == 2
        assert result[0].pitch == 64
        assert result[1].pitch == 67

    def test_filter_empty_list(self):
        """빈 리스트"""
        result = filter_short_notes([])
        assert result == []


class TestResolveOverlaps:
    """겹침 해결 테스트"""

    def test_resolve_overlaps_trims_previous(self):
        """이전 음표 duration 자르기"""
        notes = [
            Note(pitch=60, onset=0.0, duration=1.0, velocity=80),
            Note(pitch=64, onset=0.5, duration=0.5, velocity=80),
        ]
        result = resolve_overlaps(notes)

        assert len(result) == 2
        assert result[0].duration == 0.5  # 0.5 - 0.0 = 0.5
        assert result[1].duration == 0.5

    def test_resolve_overlaps_removes_too_short(self):
        """너무 짧아진 음표 제거"""
        notes = [
            Note(pitch=60, onset=0.0, duration=1.0, velocity=80),
            Note(pitch=64, onset=0.005, duration=0.5, velocity=80),  # 5ms 차이
        ]
        result = resolve_overlaps(notes)

        # 첫 번째 음표가 0.005 - 0.0 = 0.005 (< 0.01) 이므로 제거됨
        assert len(result) == 1
        assert result[0].pitch == 64

    def test_resolve_overlaps_no_overlap(self):
        """겹침 없음"""
        notes = [
            Note(pitch=60, onset=0.0, duration=0.5, velocity=80),
            Note(pitch=64, onset=0.5, duration=0.5, velocity=80),
        ]
        result = resolve_overlaps(notes)

        assert len(result) == 2
        assert result[0].duration == 0.5
        assert result[1].duration == 0.5

    def test_resolve_overlaps_empty_list(self):
        """빈 리스트"""
        result = resolve_overlaps([])
        assert result == []

    def test_resolve_overlaps_multiple_overlaps(self):
        """연속 겹침"""
        notes = [
            Note(pitch=60, onset=0.0, duration=1.0, velocity=80),
            Note(pitch=64, onset=0.3, duration=0.8, velocity=80),
            Note(pitch=67, onset=0.8, duration=0.5, velocity=80),
        ]
        result = resolve_overlaps(notes)

        assert len(result) == 3
        assert result[0].duration == 0.3  # 0.3 - 0.0
        assert result[1].duration == 0.5  # 0.8 - 0.3
        assert result[2].duration == 0.5


class TestNormalizeOctave:
    """옥타브 정규화 테스트"""

    def test_normalize_below_range(self):
        """범위 미만 → 옥타브 올림"""
        notes = [
            Note(pitch=36, onset=0.0, duration=0.5, velocity=80),  # C2
        ]
        result = normalize_octave(notes, min_pitch=48, max_pitch=84)

        assert len(result) == 1
        assert result[0].pitch == 60  # C2 + 12 = C3 (범위 내)

    def test_normalize_above_range(self):
        """범위 초과 → 옥타브 내림"""
        notes = [
            Note(pitch=96, onset=0.0, duration=0.5, velocity=80),  # C7
        ]
        result = normalize_octave(notes, min_pitch=48, max_pitch=84)

        assert len(result) == 1
        assert result[0].pitch == 84  # C7 - 12 = C6 (범위 내)

    def test_normalize_within_range(self):
        """범위 내 → 변경 없음"""
        notes = [
            Note(pitch=60, onset=0.0, duration=0.5, velocity=80),  # C4
            Note(pitch=72, onset=0.5, duration=0.5, velocity=80),  # C5
        ]
        result = normalize_octave(notes, min_pitch=48, max_pitch=84)

        assert len(result) == 2
        assert result[0].pitch == 60
        assert result[1].pitch == 72

    def test_normalize_multiple_octaves(self):
        """여러 옥타브 이동"""
        notes = [
            Note(pitch=24, onset=0.0, duration=0.5, velocity=80),  # C1 (범위 미만)
        ]
        result = normalize_octave(notes, min_pitch=48, max_pitch=84)

        assert len(result) == 1
        assert result[0].pitch == 60  # C1 + 12 + 12 = C3

    def test_normalize_empty_list(self):
        """빈 리스트"""
        result = normalize_octave([])
        assert result == []


class TestExtractMelody:
    """전체 파이프라인 통합 테스트"""

    def test_extract_melody_pipeline(self, tmp_path):
        """전체 파이프라인 통합 테스트"""
        # 간단한 MIDI 파일 생성 (pretty_midi 사용)
        import pretty_midi

        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)

        # 동시 발음 (Skyline 테스트)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=60, start=0.0, end=0.5)
        )
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=64, start=0.0, end=0.5)
        )

        # 짧은 음 (필터링 테스트)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=67, start=0.5, end=0.52)
        )

        # 겹치는 음 (Overlap 테스트)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=65, start=1.0, end=1.5)
        )
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=69, start=1.2, end=1.7)
        )

        # 범위 밖 음 (옥타브 정규화 테스트)
        instrument.notes.append(
            pretty_midi.Note(velocity=80, pitch=36, start=2.0, end=2.5)
        )

        pm.instruments.append(instrument)

        midi_path = tmp_path / "test.mid"
        pm.write(str(midi_path))

        # 파이프라인 실행
        result = extract_melody(midi_path)

        # 검증
        assert len(result) > 0

        # 모든 음표가 범위 내
        for note in result:
            assert 48 <= note.pitch <= 84

        # 모든 음표가 50ms 이상
        for note in result:
            assert note.duration >= 0.05

        # 겹침 없음
        for i in range(len(result) - 1):
            curr_end = result[i].onset + result[i].duration
            next_start = result[i + 1].onset
            assert curr_end <= next_start + 0.001  # 부동소수점 오차 허용

    def test_extract_melody_empty_midi(self, tmp_path):
        """빈 MIDI 파일"""
        import pretty_midi

        pm = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)
        pm.instruments.append(instrument)

        midi_path = tmp_path / "empty.mid"
        pm.write(str(midi_path))

        result = extract_melody(midi_path)
        assert result == []

    def test_extract_melody_drum_track_excluded(self, tmp_path):
        """드럼 트랙 제외"""
        import pretty_midi

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

        result = extract_melody(midi_path)

        # 드럼 음표는 제외되고 일반 악기 음표만 포함
        assert len(result) == 1
        assert result[0].pitch == 60
