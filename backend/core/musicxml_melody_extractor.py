"""
MusicXML 멜로디 추출 모듈

MusicXML/MXL 파일에서 멜로디를 추출합니다.
첫 번째 파트(오른손/Staff 1) 필터링과 Skyline 알고리즘을 사용하여
폴리포닉 악보에서 모노포닉 멜로디를 추출합니다.

Reference 파일 구조:
- music21이 파싱하면 2개의 Part로 분리됨
  - Part 0 = 오른손 (Staff 1, 멜로디)
  - Part 1 = 왼손 (Staff 2, 베이스)
- 코드: 여러 음표가 동시에 발음됨 → 최고음 선택
"""

from pathlib import Path
from typing import List, Optional

import music21

from core.midi_parser import Note
from core.melody_extractor import (
    apply_skyline,
    filter_short_notes,
    resolve_overlaps,
    normalize_octave,
)


# ============================================================================
# Constants
# ============================================================================

DEFAULT_TEMPO = 120.0  # BPM (if no tempo marking found)
DEFAULT_VELOCITY = 80  # Default velocity if not specified


# ============================================================================
# Exceptions
# ============================================================================


class MusicXMLExtractionError(Exception):
    """MusicXML 멜로디 추출 중 발생하는 오류"""

    pass


# ============================================================================
# Helper Functions
# ============================================================================


def _get_tempo(score: music21.stream.Score) -> float:
    """
    Score에서 템포(BPM)를 추출합니다.

    Args:
        score: music21 Score 객체

    Returns:
        BPM 값 (찾지 못하면 DEFAULT_TEMPO 반환)
    """
    # MetronomeMark에서 템포 찾기
    metronome_marks = score.flatten().getElementsByClass(music21.tempo.MetronomeMark)
    if metronome_marks:
        return metronome_marks[0].number

    # TempoIndication에서 템포 찾기 (fallback)
    tempo_indications = score.flatten().getElementsByClass(
        music21.tempo.TempoIndication
    )
    if tempo_indications:
        ti = tempo_indications[0]
        if hasattr(ti, "number") and ti.number:
            return ti.number

    return DEFAULT_TEMPO


def _quarter_length_to_seconds(quarter_length: float, bpm: float) -> float:
    """
    quarterLength 단위를 초 단위로 변환합니다.

    Args:
        quarter_length: quarterLength 값
        bpm: 분당 박자 수

    Returns:
        초 단위 시간
    """
    # 1 quarter note = 60/bpm 초
    seconds_per_quarter = 60.0 / bpm
    return quarter_length * seconds_per_quarter


def _get_velocity(element) -> int:
    """
    음표의 velocity를 추출합니다.

    Args:
        element: music21 Note 또는 Chord

    Returns:
        velocity 값 (0-127)
    """
    if hasattr(element, "volume") and element.volume is not None:
        if hasattr(element.volume, "velocity") and element.volume.velocity is not None:
            return int(element.volume.velocity)
    return DEFAULT_VELOCITY


def _extract_melody_notes(score: music21.stream.Score, bpm: float) -> List[Note]:
    """
    Score에서 첫 번째 파트(오른손/멜로디)의 음표를 추출합니다.

    music21이 MusicXML을 파싱하면 피아노 악보가 2개의 Part로 분리됨:
    - Part 0: 오른손 (Staff 1, 멜로디)
    - Part 1: 왼손 (Staff 2, 베이스)

    Args:
        score: music21 Score 객체
        bpm: 템포 (BPM)

    Returns:
        Note 리스트 (초 단위 시간)
    """
    notes = []

    # 첫 번째 파트(오른손/멜로디)만 사용
    if not score.parts:
        return notes

    melody_part = score.parts[0]

    for element in melody_part.flatten().notes:
        # ChordSymbol(화성 기호)은 건너뜀
        if isinstance(element, music21.harmony.ChordSymbol):
            continue

        # 시간 변환
        onset_ql = float(element.offset)
        duration_ql = float(element.duration.quarterLength)

        onset_sec = _quarter_length_to_seconds(onset_ql, bpm)
        duration_sec = _quarter_length_to_seconds(duration_ql, bpm)

        velocity = _get_velocity(element)

        if isinstance(element, music21.note.Note):
            # 단일 음표
            notes.append(
                Note(
                    pitch=element.pitch.midi,
                    onset=onset_sec,
                    duration=duration_sec,
                    velocity=velocity,
                )
            )
        elif isinstance(element, music21.chord.Chord):
            # 코드: 최고음만 추출 (멜로디 특성 유지)
            # music21 chord.pitches는 낮은음→높은음 순서로 정렬됨
            highest_pitch = element.pitches[-1]
            notes.append(
                Note(
                    pitch=highest_pitch.midi,
                    onset=onset_sec,
                    duration=duration_sec,
                    velocity=velocity,
                )
            )

    # onset 기준 정렬
    notes.sort(key=lambda n: n.onset)
    return notes


# ============================================================================
# Main API
# ============================================================================


def extract_melody_from_musicxml(filepath: str) -> List[Note]:
    """
    MusicXML/MXL 파일에서 멜로디를 추출합니다.

    추출 파이프라인:
    1. MusicXML/MXL 파싱
    2. 첫 번째 파트(오른손/Staff 1) 추출
    3. 코드 처리 (최고음 선택)
    4. Skyline 알고리즘 적용 (동시 발음 → 최고음)
    5. 짧은 음표 제거 (< 50ms)
    6. Overlap 해결
    7. 옥타브 정규화 (C3-C6)

    Args:
        filepath: MusicXML (.musicxml) 또는 MXL (.mxl) 파일 경로

    Returns:
        추출된 멜로디 Note 리스트

    Raises:
        MusicXMLExtractionError: 파일이 없거나 파싱 실패 시
    """
    path = Path(filepath)

    if not path.exists():
        raise MusicXMLExtractionError(f"File not found: {filepath}")

    # 1. MusicXML/MXL 파싱
    try:
        score = music21.converter.parse(str(path))
    except Exception as e:
        raise MusicXMLExtractionError(f"Failed to parse {filepath}: {e}")

    # 템포 추출
    bpm = _get_tempo(score)

    # 2-3. Voice 1 필터링 + 코드 처리
    notes = _extract_melody_notes(score, bpm)

    if not notes:
        raise MusicXMLExtractionError(
            f"No melody notes found in first part (right hand): {filepath}"
        )

    # 4. Skyline 알고리즘 (동시 발음 → 최고음)
    notes = apply_skyline(notes)

    # 5. 짧은 음표 제거 (< 50ms)
    notes = filter_short_notes(notes)

    # 6. Overlap 해결
    notes = resolve_overlaps(notes)

    # 7. 옥타브 정규화 (C3-C6)
    notes = normalize_octave(notes, min_pitch=48, max_pitch=84)

    return notes
