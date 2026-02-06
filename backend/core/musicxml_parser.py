"""
MusicXML 파싱 모듈

MusicXML/MXL 파일을 파싱하여 음표, 메타데이터 등을 추출합니다.
music21 라이브러리를 사용합니다.

musicxml_comparator에서 분리된 파싱 전용 모듈입니다.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import music21

from core.comparison_utils import NoteEvent, NoteInfo

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ScoreMetadata:
    """악보 메타데이터"""

    measure_count: int
    time_signature: Optional[str]  # e.g., "4/4"
    key: Optional[str]  # e.g., "C major"


# ============================================================================
# Exceptions
# ============================================================================


class ParsingError(Exception):
    """MusicXML 파싱 중 발생하는 오류"""

    pass


# ============================================================================
# Parsing Functions
# ============================================================================


def parse_musicxml(file_path: str) -> music21.stream.Score:
    """
    MusicXML/MXL 파일을 파싱하여 music21 Score 객체로 반환합니다.

    Args:
        file_path: MusicXML 또는 MXL 파일 경로

    Returns:
        music21.stream.Score 객체

    Raises:
        ParsingError: 파일이 없거나 파싱 실패 시
    """
    path = Path(file_path)

    if not path.exists():
        raise ParsingError(f"File not found: {file_path}")

    try:
        score = music21.converter.parse(str(path))
        return score
    except Exception as e:
        raise ParsingError(f"Failed to parse {file_path}: {e}")


def extract_notes(score: music21.stream.Score) -> List[NoteInfo]:
    """
    Score에서 모든 음표를 추출합니다.

    Args:
        score: music21 Score 객체

    Returns:
        NoteInfo 리스트 (onset 기준 정렬됨)
    """
    notes = []

    for element in score.flatten().notes:
        # IMPORTANT: music21.harmony.ChordSymbol is a subclass of music21.chord.Chord.
        # score.flatten().notes can include ChordSymbol objects (harmony annotations),
        # which should NOT be treated as performed notes for note-level similarity.
        if isinstance(element, music21.harmony.ChordSymbol):
            continue

        if isinstance(element, music21.note.Note):
            notes.append(
                NoteInfo(
                    pitch=element.pitch.midi,
                    onset=float(element.offset),
                    duration=float(element.duration.quarterLength),
                )
            )
        elif isinstance(element, music21.chord.Chord):
            # Chord의 각 음을 개별 노트로 처리
            for pitch in element.pitches:
                notes.append(
                    NoteInfo(
                        pitch=pitch.midi,
                        onset=float(element.offset),
                        duration=float(element.duration.quarterLength),
                    )
                )

    # onset 기준 정렬
    notes.sort(key=lambda n: (n.onset, n.pitch))
    return notes


def extract_metadata(score: music21.stream.Score) -> ScoreMetadata:
    """
    Score에서 메타데이터를 추출합니다.

    Args:
        score: music21 Score 객체

    Returns:
        ScoreMetadata 객체
    """
    # 마디 수
    measures = score.getElementsByClass(music21.stream.Measure)
    if measures:
        measure_count = len(measures)
    else:
        # Part를 통해 Measure 찾기
        measure_count = 0
        for part in score.parts:
            part_measures = part.getElementsByClass(music21.stream.Measure)
            if len(part_measures) > measure_count:
                measure_count = len(part_measures)

    # 박자표
    time_sig = None
    time_sigs = score.flatten().getElementsByClass(music21.meter.TimeSignature)
    if time_sigs:
        ts = time_sigs[0]
        time_sig = f"{ts.numerator}/{ts.denominator}"

    # 조성
    key = None
    keys = score.flatten().getElementsByClass(music21.key.Key)
    if keys:
        k = keys[0]
        mode = k.mode if k.mode else "major"
        key = f"{k.tonic.name} {mode}"
    else:
        # KeySignature로 시도
        key_sigs = score.flatten().getElementsByClass(music21.key.KeySignature)
        if key_sigs:
            ks = key_sigs[0]
            # KeySignature에서 Key 추론
            inferred_key = ks.asKey()
            if inferred_key:
                mode = inferred_key.mode if inferred_key.mode else "major"
                key = f"{inferred_key.tonic.name} {mode}"

    return ScoreMetadata(
        measure_count=measure_count,
        time_signature=time_sig,
        key=key,
    )


def noteinfos_to_noteevents(
    notes: List[NoteInfo], bpm: float = 120.0
) -> List[NoteEvent]:
    """
    Convert NoteInfo (quarterLength-based) to NoteEvent (seconds-based).

    Args:
        notes: NoteInfo list (onset/duration in quarterLength)
        bpm: Tempo for conversion (default 120 BPM)

    Returns:
        List of NoteEvent with onset/offset in seconds
    """
    beats_per_second = bpm / 60.0
    events = []
    for n in notes:
        onset_sec = n.onset / beats_per_second
        duration_sec = n.duration / beats_per_second
        events.append(
            NoteEvent(
                pitch=n.pitch,
                onset=onset_sec,
                offset=onset_sec + duration_sec,
            )
        )
    return events
