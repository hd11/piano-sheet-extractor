"""
MIDI → MusicXML 변환 유틸리티 모듈

이 모듈은 Note 리스트를 music21 Stream 객체로 변환하고,
Stream을 MusicXML 문자열로 변환하는 함수들을 제공합니다.

Task 7 (난이도 조절)에서 이 모듈의 notes_to_stream() 함수를 사용하여
코드 심볼을 추가합니다.
"""

import tempfile
from pathlib import Path
from typing import List

import music21

from backend.core.midi_parser import Note


def seconds_to_quarter_length(seconds: float, bpm: float) -> float:
    """
    초(seconds) 단위 시간을 music21의 quarterLength로 변환합니다.

    music21은 내부적으로 quarterLength(4분음표 기준)를 사용합니다.
    이 함수는 프로젝트 표준인 초 단위를 music21 단위로 변환합니다.

    Args:
        seconds: 초 단위 시간 (float)
        bpm: 템포 (beats per minute)

    Returns:
        quarterLength (float): music21 내부 시간 단위

    Example:
        >>> seconds_to_quarter_length(1.0, 60)  # 1초, 60 BPM
        1.0  # 1초 = 1 quarterLength (4분음표)

        >>> seconds_to_quarter_length(0.5, 120)  # 0.5초, 120 BPM
        1.0  # 0.5초 = 1 quarterLength (4분음표)
    """
    beats_per_second = bpm / 60.0
    return seconds * beats_per_second


def quarter_length_to_seconds(ql: float, bpm: float) -> float:
    """
    music21의 quarterLength를 초(seconds) 단위 시간으로 변환합니다.

    seconds_to_quarter_length()의 역함수입니다.

    Args:
        ql: quarterLength (music21 내부 시간 단위)
        bpm: 템포 (beats per minute)

    Returns:
        seconds (float): 초 단위 시간

    Example:
        >>> quarter_length_to_seconds(1.0, 60)  # 1 quarterLength, 60 BPM
        1.0  # 1 quarterLength = 1초

        >>> quarter_length_to_seconds(1.0, 120)  # 1 quarterLength, 120 BPM
        0.5  # 1 quarterLength = 0.5초
    """
    beats_per_second = bpm / 60.0
    return ql / beats_per_second


def notes_to_stream(
    notes: List[Note], bpm: float, key: str, time_signature: str = "4/4"
) -> music21.stream.Stream:
    """
    Note 리스트를 music21 Stream 객체로 변환합니다.

    이 함수는 다음 작업을 수행합니다:
    1. Stream 객체 생성
    2. 메타데이터 설정 (템포, 조성, 박자표)
    3. Note 리스트를 music21 Note 객체로 변환 (초 → quarterLength)
    4. 16분음표 그리드로 퀀타이즈

    Task 7에서 이 함수의 반환값에 코드 심볼을 추가합니다.

    Args:
        notes: List[Note] - 초 단위 시간의 Note 리스트
        bpm: float - 템포 (beats per minute)
        key: str - 조성 (예: "C major", "G minor", "D major")
        time_signature: str - 박자표 (기본값: "4/4", 현재 4/4만 지원)

    Returns:
        music21.stream.Stream - 메타데이터와 음표가 포함된 Stream 객체

    Note:
        - 박자표는 현재 4/4로 고정됩니다 (변박 미지원)
        - 퀀타이즈: quarterLengthDivisors=[4] (16분음표 그리드)
        - 셋잇단음표는 제외됩니다 (단순화 목적)

    Example:
        >>> from backend.core.midi_parser import Note
        >>> notes = [
        ...     Note(pitch=60, onset=0.0, duration=0.5, velocity=100),
        ...     Note(pitch=62, onset=0.5, duration=0.5, velocity=100),
        ... ]
        >>> stream = notes_to_stream(notes, bpm=120, key="C major")
        >>> isinstance(stream, music21.stream.Stream)
        True
    """
    stream = music21.stream.Stream()

    # 메타데이터 설정
    stream.append(music21.tempo.MetronomeMark(number=bpm))
    stream.append(music21.key.Key(key))
    stream.append(music21.meter.TimeSignature(time_signature))

    # Note 변환 (초 → quarterLength)
    for n in notes:
        m21_note = music21.note.Note(n.pitch)
        m21_note.offset = seconds_to_quarter_length(n.onset, bpm)
        m21_note.duration.quarterLength = seconds_to_quarter_length(n.duration, bpm)
        m21_note.volume.velocity = n.velocity
        stream.append(m21_note)

    # 퀀타이즈 (16분음표 그리드)
    # quarterLengthDivisors=[4] → 4분음표를 4등분 → 16분음표
    stream.quantize(quarterLengthDivisors=[4], inPlace=True)

    return stream


def stream_to_musicxml(stream: music21.stream.Stream) -> str:
    """
    music21 Stream을 MusicXML 문자열로 변환합니다.

    music21은 MusicXML 생성 시 파일 경로를 요구하므로,
    임시 파일을 생성하여 MusicXML을 작성한 후 읽고 삭제합니다.

    Args:
        stream: music21.stream.Stream - 변환할 Stream 객체

    Returns:
        str - MusicXML 형식의 문자열

    Note:
        - 임시 파일은 함수 실행 후 자동으로 삭제됩니다
        - UTF-8 인코딩으로 읽습니다

    Example:
        >>> stream = music21.stream.Stream()
        >>> stream.append(music21.note.Note('C4'))
        >>> musicxml_str = stream_to_musicxml(stream)
        >>> '<?xml' in musicxml_str
        True
    """
    # 임시 파일 생성
    with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as f:
        temp_path = f.name

    try:
        # Stream을 MusicXML 파일로 작성
        stream.write("musicxml", fp=temp_path)

        # MusicXML 파일을 문자열로 읽기
        with open(temp_path, "r", encoding="utf-8") as f:
            musicxml_str = f.read()

        return musicxml_str
    finally:
        # 임시 파일 삭제
        Path(temp_path).unlink(missing_ok=True)


def notes_to_musicxml(
    notes: List[Note], bpm: float, key: str, time_signature: str = "4/4"
) -> str:
    """
    Note 리스트를 MusicXML 문자열로 변환하는 편의 함수입니다.

    내부적으로 notes_to_stream() + stream_to_musicxml()을 순차 호출합니다.

    코드 심볼을 추가해야 하는 경우 notes_to_stream()을 직접 사용하고,
    stream_to_musicxml()으로 변환하세요.

    Args:
        notes: List[Note] - 초 단위 시간의 Note 리스트
        bpm: float - 템포 (beats per minute)
        key: str - 조성 (예: "C major", "G minor")
        time_signature: str - 박자표 (기본값: "4/4")

    Returns:
        str - MusicXML 형식의 문자열

    Example:
        >>> from backend.core.midi_parser import Note
        >>> notes = [Note(pitch=60, onset=0.0, duration=0.5, velocity=100)]
        >>> musicxml_str = notes_to_musicxml(notes, bpm=120, key="C major")
        >>> '<?xml' in musicxml_str
        True
    """
    stream = notes_to_stream(notes, bpm, key, time_signature)
    return stream_to_musicxml(stream)
