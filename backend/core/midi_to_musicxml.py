"""
MIDI → MusicXML 변환 유틸리티 모듈

이 모듈은 Note 리스트를 music21 Stream 객체로 변환하고,
Stream을 MusicXML 문자열로 변환하는 함수들을 제공합니다.

Task 7 (난이도 조절)에서 이 모듈의 notes_to_stream() 함수를 사용하여
코드 심볼을 추가합니다.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import music21

from core.midi_parser import Note, parse_midi

logger = logging.getLogger(__name__)


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
        >>> from core.midi_parser import Note
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

    # Parse key string (e.g., "A major" → Key('A', 'major'))
    key_parts = key.split()
    if len(key_parts) == 2:
        tonic, mode = key_parts
        stream.append(music21.key.Key(tonic, mode))
    else:
        # Fallback: try to parse as-is
        stream.append(music21.key.Key(key))

    stream.append(music21.meter.TimeSignature(time_signature))

    # Note 변환 (초 → quarterLength)
    # Use coarse quantization grid to avoid very short durations
    # Quantize to 8th note (0.5 quarter note) grid
    # Use finer grid to reduce MusicXML "inexpressible duration" errors
    # (music21 can express standard durations better with 16th-note resolution)
    quantize_grid = 0.25  # 16th note

    for n in notes:
        m21_note = music21.note.Note(n.pitch)

        # Quantize offset/duration to grid
        offset_ql = seconds_to_quarter_length(n.onset, bpm)
        offset_ql = max(0.0, round(offset_ql / quantize_grid) * quantize_grid)

        duration_ql = seconds_to_quarter_length(n.duration, bpm)
        duration_ql = max(
            quantize_grid, round(duration_ql / quantize_grid) * quantize_grid
        )

        m21_note.duration.quarterLength = duration_ql
        m21_note.volume.velocity = n.velocity

        # IMPORTANT: use insert() to preserve the quantized offset.
        # Stream.append() will place the element at the end and overwrite offsets.
        stream.insert(offset_ql, m21_note)

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
        # Clean up stream: remove any elements with invalid durations
        # This is a workaround for music21 export issues
        for element in stream.flatten().notes:
            if element.duration.quarterLength <= 0:
                element.duration.quarterLength = 0.5  # Default to 8th note

        # Always normalize notation/measures before export
        stream = stream.makeMeasures(inPlace=False)
        stream = stream.makeNotation(inPlace=False)

        # Stream을 MusicXML 파일로 작성
        stream.write("musicxml", fp=temp_path)

        # MusicXML 파일을 문자열로 읽기
        with open(temp_path, "r", encoding="utf-8") as f:
            musicxml_str = f.read()

        return musicxml_str
    except Exception as e:
        # If export fails, try rebuilding a clean, notated stream.
        # Common failure cause: non-expressible durations / missing measure structure.
        import logging

        logging.warning(
            f"MusicXML export failed: {e}. Retrying with rebuilt/notated stream..."
        )

        try:
            # Rebuild stream by inserting only notes/chords at their offsets.
            rebuilt = music21.stream.Stream()

            # Preserve metadata from original stream when possible
            for cls in (
                music21.tempo.MetronomeMark,
                music21.key.Key,
                music21.meter.TimeSignature,
            ):
                for el in stream.getElementsByClass(cls):
                    rebuilt.insert(float(el.offset), el)

            for element in stream.flatten().notes:
                rebuilt.insert(float(element.offset), element)

            # Make notation/measures to satisfy MusicXML writer
            rebuilt = rebuilt.makeMeasures(inPlace=False)
            rebuilt = rebuilt.makeNotation(inPlace=False)

            rebuilt.write("musicxml", fp=temp_path)
            with open(temp_path, "r", encoding="utf-8") as f:
                musicxml_str = f.read()
            return musicxml_str
        except Exception as e2:
            logging.error(f"Rebuilt export also failed: {e2}")
            raise

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
        >>> from core.midi_parser import Note
        >>> notes = [Note(pitch=60, onset=0.0, duration=0.5, velocity=100)]
        >>> musicxml_str = notes_to_musicxml(notes, bpm=120, key="C major")
        >>> '<?xml' in musicxml_str
        True
    """
    stream = notes_to_stream(notes, bpm, key, time_signature)
    return stream_to_musicxml(stream)


# ============================================================================
# Polyphonic Two-Hand Piano Support
# ============================================================================


def split_hands(notes: List[Note], split_point: int = 60) -> tuple:
    """
    Split notes into right hand (treble) and left hand (bass).

    Args:
        notes: List[Note] - All notes
        split_point: MIDI pitch split point (default 60 = C4)
            Notes >= split_point go to right hand (treble clef)
            Notes < split_point go to left hand (bass clef)

    Returns:
        (rh_notes, lh_notes) tuple of List[Note]
    """
    rh_notes = [n for n in notes if n.pitch >= split_point]
    lh_notes = [n for n in notes if n.pitch < split_point]
    return rh_notes, lh_notes


def notes_to_piano_score(
    notes: List[Note],
    bpm: float,
    key: str,
    time_signature: str = "4/4",
    split_point: int = 60,
) -> music21.stream.Score:
    """
    Convert Note list to a two-staff piano Score (treble + bass clef).

    This creates a proper piano score with:
    - Part 1 (Right Hand): Treble clef, notes >= split_point
    - Part 2 (Left Hand): Bass clef, notes < split_point

    Args:
        notes: List[Note] - 초 단위 시간의 Note 리스트
        bpm: float - 템포
        key: str - 조성 (예: "C major")
        time_signature: str - 박자표 (기본값: "4/4")
        split_point: int - RH/LH split MIDI pitch (default 60 = C4)

    Returns:
        music21.stream.Score with two Parts (RH treble, LH bass)
    """
    rh_notes, lh_notes = split_hands(notes, split_point)

    # Create Score
    score = music21.stream.Score()

    # Parse key
    key_parts = key.split()
    if len(key_parts) == 2:
        tonic, mode = key_parts
        key_obj = music21.key.Key(tonic, mode)
    else:
        key_obj = music21.key.Key(key)

    ts_obj = music21.meter.TimeSignature(time_signature)
    tempo_obj = music21.tempo.MetronomeMark(number=bpm)

    quantize_grid = 0.25  # 16th note

    # Helper to build a Part from notes
    def _build_part(part_notes: List[Note], clef_obj) -> music21.stream.Part:
        part = music21.stream.Part()
        part.insert(0, clef_obj)
        part.insert(0, key_obj.__deepcopy__())
        part.insert(0, ts_obj.__deepcopy__())
        part.insert(0, tempo_obj.__deepcopy__())

        for n in part_notes:
            m21_note = music21.note.Note(n.pitch)

            offset_ql = seconds_to_quarter_length(n.onset, bpm)
            offset_ql = max(0.0, round(offset_ql / quantize_grid) * quantize_grid)

            duration_ql = seconds_to_quarter_length(n.duration, bpm)
            duration_ql = max(
                quantize_grid, round(duration_ql / quantize_grid) * quantize_grid
            )

            m21_note.duration.quarterLength = duration_ql
            m21_note.volume.velocity = n.velocity
            part.insert(offset_ql, m21_note)

        return part

    # Right Hand (treble clef)
    rh_part = _build_part(rh_notes, music21.clef.TrebleClef())
    rh_part.partName = "Piano"
    rh_part.partAbbreviation = "Pno."

    # Left Hand (bass clef)
    lh_part = _build_part(lh_notes, music21.clef.BassClef())

    score.insert(0, rh_part)
    score.insert(0, lh_part)

    return score


def notes_to_piano_musicxml(
    notes: List[Note],
    bpm: float,
    key: str,
    time_signature: str = "4/4",
    split_point: int = 60,
    polyphonic: bool = True,
) -> str:
    """
    Convert Note list to MusicXML string, optionally as two-hand piano score.

    Args:
        notes: List[Note] - 초 단위 시간의 Note 리스트
        bpm: float - 템포
        key: str - 조성
        time_signature: str - 박자표 (기본값: "4/4")
        split_point: int - RH/LH split MIDI pitch (default 60 = C4)
        polyphonic: bool - If True, create two-staff piano score.
                          If False, use legacy single-staff mode.

    Returns:
        str - MusicXML 형식의 문자열
    """
    if not polyphonic:
        # Legacy single-staff mode
        return notes_to_musicxml(notes, bpm, key, time_signature)

    score = notes_to_piano_score(notes, bpm, key, time_signature, split_point)
    return stream_to_musicxml(score)


# ============================================================================
# File-level Conversion API
# ============================================================================


def convert_midi_to_musicxml(
    midi_path: Path,
    output_path: Path,
    polyphonic: bool = True,
    split_threshold: int = 60,
    bpm: Optional[float] = None,
    key: str = "C major",
    time_signature: str = "4/4",
) -> Dict[str, Any]:
    """
    Convert a MIDI file to a MusicXML file.

    This is the top-level convenience function that reads a MIDI file,
    optionally splits notes into two hands, and writes a MusicXML file.

    Args:
        midi_path: Path to input MIDI file
        output_path: Path to save MusicXML file
        polyphonic: If True, create two-staff piano score (RH treble + LH bass).
                    If False, create single-staff monophonic score.
        split_threshold: MIDI pitch for RH/LH split (default 60 = middle C).
                         Notes >= split_threshold → right hand (treble clef).
                         Notes < split_threshold → left hand (bass clef).
        bpm: Override BPM. If None, extracted from the MIDI file tempo map.
             Falls back to 120 BPM if MIDI has no tempo information.
        key: Key signature string (default "C major")
        time_signature: Time signature string (default "4/4")

    Returns:
        Dictionary with conversion metadata:
            - output_path: str path to generated MusicXML
            - note_count: total number of notes
            - rh_notes: number of right-hand notes (polyphonic only)
            - lh_notes: number of left-hand notes (polyphonic only)
            - polyphonic: whether polyphonic mode was used
            - bpm: BPM used for conversion
            - key: key signature used

    Raises:
        FileNotFoundError: If MIDI file does not exist
    """
    import pretty_midi as pm_lib

    midi_path = Path(midi_path)
    output_path = Path(output_path)

    if not midi_path.exists():
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")

    # Parse notes from MIDI
    notes = parse_midi(midi_path)
    logger.info(f"Parsed {len(notes)} notes from {midi_path}")

    # Extract BPM from MIDI if not provided
    if bpm is None:
        pm = pm_lib.PrettyMIDI(str(midi_path))
        tempo_changes = pm.get_tempo_changes()
        if len(tempo_changes[1]) > 0:
            bpm = float(tempo_changes[1][0])  # Use first tempo marking
            logger.info(f"Extracted BPM from MIDI: {bpm}")
        else:
            bpm = 120.0  # Safe default
            logger.info(f"No tempo in MIDI, using default BPM: {bpm}")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate MusicXML
    if polyphonic:
        musicxml_str = notes_to_piano_musicxml(
            notes,
            bpm,
            key,
            time_signature,
            split_point=split_threshold,
            polyphonic=True,
        )
        rh_notes, lh_notes = split_hands(notes, split_threshold)
        rh_count = len(rh_notes)
        lh_count = len(lh_notes)
        logger.info(
            f"Polyphonic mode: {rh_count} RH notes, {lh_count} LH notes "
            f"(split at MIDI {split_threshold})"
        )
    else:
        musicxml_str = notes_to_musicxml(notes, bpm, key, time_signature)
        rh_count = len(notes)
        lh_count = 0
        logger.info(f"Monophonic mode: {len(notes)} notes")

    # Write MusicXML to file
    output_path.write_text(musicxml_str, encoding="utf-8")
    logger.info(f"MusicXML written to {output_path}")

    return {
        "output_path": str(output_path),
        "note_count": len(notes),
        "rh_notes": rh_count,
        "lh_notes": lh_count,
        "polyphonic": polyphonic,
        "bpm": bpm,
        "key": key,
    }
