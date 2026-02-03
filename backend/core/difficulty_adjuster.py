"""
난이도 조절 시스템 (Difficulty Adjustment System)

이 모듈은 멜로디 노트를 3단계 난이도 (easy, medium, hard)로 조절하고,
코드 심볼을 추가한 후 MusicXML 파일로 저장합니다.

난이도별 규칙:
| Rule             | Easy           | Medium           | Hard      |
|------------------|----------------|------------------|-----------|
| Quantize grid    | 1 beat (초)    | 0.5 beat (초)    | 0.25 beat |
| Min note dur     | 0.5초          | 0.25초           | 0.125초   |
| Pitch range      | C4-C5 (60-72)  | C4-G5 (60-79)    | Original  |
| Max simultaneous | 1 (monophonic) | 2                | Original  |
| Fast passages    | Remove         | Simplify         | Keep      |
| Ornaments        | Remove         | Remove           | Keep      |
"""

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Dict, List

import music21

from backend.core.midi_parser import Note, parse_midi
from backend.core.midi_to_musicxml import (
    notes_to_stream,
    seconds_to_quarter_length,
    stream_to_musicxml,
)


def adjust_difficulty(notes: List[Note], level: str, bpm: float) -> List[Note]:
    """
    Adjust note list to match difficulty level.
    All time units are in seconds.

    Args:
        notes: List[Note] - 원본 Note 리스트 (초 단위 시간)
        level: str - 난이도 ("easy", "medium", "hard")
        bpm: float - 템포 (beats per minute)

    Returns:
        List[Note]: 난이도 조절된 Note 리스트

    Note:
        - hard 레벨은 원본 노트를 그대로 반환 (단, deepcopy 적용)
        - easy/medium은 다음 순서로 처리:
          1. 짧은 음 제거 (min_duration 미만)
          2. 퀀타이즈 (onset을 grid에 스냅)
          3. 옥타브 조정 (범위 밖 음표 이동)
          4. 동시 발음 제한 (max_simultaneous 초과 시 높은 음만 유지)
    """
    # Always create a deep copy to avoid mutating original notes
    adjusted = deepcopy(notes)

    beat_sec = 60.0 / bpm  # 1 beat in seconds

    if level == "easy":
        quantize_grid = beat_sec  # quarter note
        min_duration = 0.5  # seconds
        octave_range = (60, 72)  # C4-C5
        max_simultaneous = 1
    elif level == "medium":
        quantize_grid = beat_sec / 2  # 8th note
        min_duration = 0.25  # seconds
        octave_range = (60, 79)  # C4-G5
        max_simultaneous = 2
    else:  # hard
        return adjusted  # keep original (already deep copied)

    # 1. Remove short notes (fast passages / ornaments)
    filtered = [n for n in adjusted if n.duration >= min_duration]

    # 2. Quantize (snap onset to grid)
    for note in filtered:
        note.onset = round(note.onset / quantize_grid) * quantize_grid

    # 3. Adjust pitch range (octave shift)
    for note in filtered:
        while note.pitch < octave_range[0]:
            note.pitch += 12
        while note.pitch > octave_range[1]:
            note.pitch -= 12

    # 4. Limit simultaneous notes
    filtered = limit_simultaneous_notes(filtered, max_simultaneous)

    return filtered


def limit_simultaneous_notes(notes: List[Note], max_count: int) -> List[Note]:
    """
    Keep only max_count notes at same onset (highest pitch priority).

    Args:
        notes: List[Note] - 노트 리스트
        max_count: int - 최대 동시 발음 수

    Returns:
        List[Note]: 동시 발음 수가 제한된 노트 리스트

    Note:
        - 동일 onset 기준 그룹화
        - pitch 내림차순 정렬 (높은 음 우선)
        - 상위 max_count개만 유지
    """
    if not notes:
        return []

    by_onset: Dict[float, List[Note]] = defaultdict(list)
    for n in notes:
        by_onset[n.onset].append(n)

    result = []
    for onset, group in by_onset.items():
        # Sort by pitch descending (highest first)
        sorted_group = sorted(group, key=lambda x: -x.pitch)
        result.extend(sorted_group[:max_count])

    # Return sorted by onset
    return sorted(result, key=lambda x: x.onset)


def add_chord_symbols(
    stream: music21.stream.Stream, chords: List[Dict], bpm: float
) -> music21.stream.Stream:
    """
    Add chord symbols to music21 Stream.

    Args:
        stream: music21.stream.Stream - 음표가 포함된 Stream 객체
        chords: List[Dict] - 코드 정보 리스트
            Each dict: {"time": float, "duration": float, "chord": str, "confidence": float}
        bpm: float - 템포 (beats per minute)

    Returns:
        music21.stream.Stream: 코드 심볼이 추가된 Stream 객체

    Note:
        - time(초) → quarterLength 변환 후 Stream에 insert
        - music21.harmony.ChordSymbol 사용
        - 원본 Stream을 직접 수정하여 반환 (in-place)
    """
    for chord_info in chords:
        offset_ql = seconds_to_quarter_length(chord_info["time"], bpm)

        # Create music21 ChordSymbol
        cs = music21.harmony.ChordSymbol(chord_info["chord"])
        cs.offset = offset_ql

        stream.insert(offset_ql, cs)

    return stream


def write_file_atomic(target_path: Path, content: str) -> None:
    """
    Atomic file write (temp → replace).

    Args:
        target_path: Path - 최종 파일 경로
        content: str - 파일 내용

    Note:
        - 임시 파일(.tmp)에 먼저 작성
        - 작성 완료 후 replace()로 원자적 이동
        - 실패 시 임시 파일 정리
    """
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")

    try:
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(target_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def generate_all_sheets(
    job_dir: Path, melody_mid: Path, analysis: Dict
) -> Dict[str, Path]:
    """
    Generate 3 difficulty levels of MusicXML files.

    Args:
        job_dir: Path - Job 디렉토리 경로
        melody_mid: Path - 멜로디 MIDI 파일 경로
        analysis: Dict - 분석 결과
            {"bpm": float, "key": str, "chords": List[Dict]}

    Returns:
        Dict[str, Path]: 난이도별 MusicXML 파일 경로
            {"easy": Path, "medium": Path, "hard": Path}

    Note:
        - 입력: melody.mid (Task 4 출력) + analysis.json (Task 6 출력)
        - 처리: MIDI → Note 리스트 → 난이도별 Note 리스트 → MusicXML
        - 출력: sheet_easy.musicxml, sheet_medium.musicxml, sheet_hard.musicxml
        - 각 난이도에 코드 심볼 추가
    """
    # 1. MIDI → Note list
    notes = parse_midi(melody_mid)

    bpm = analysis["bpm"]
    key = analysis["key"]
    chords = analysis.get("chords", [])

    # 2. Process each difficulty and save
    result: Dict[str, Path] = {}

    for difficulty in ["easy", "medium", "hard"]:
        # Adjust difficulty
        adjusted_notes = adjust_difficulty(notes, difficulty, bpm)

        # Create music21 Stream (Task 5 function)
        stream = notes_to_stream(adjusted_notes, bpm, key)

        # Add chord symbols to Stream
        add_chord_symbols(stream, chords, bpm)

        # Stream → MusicXML string (Task 5 function)
        musicxml_str = stream_to_musicxml(stream)

        # Save to file (atomic write)
        output_path = job_dir / f"sheet_{difficulty}.musicxml"
        write_file_atomic(output_path, musicxml_str)

        result[difficulty] = output_path

    return result
