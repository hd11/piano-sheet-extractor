"""
난이도 조절 시스템 (Difficulty Adjustment System)

이 모듈은 폴리포닉 피아노 편곡을 3단계 난이도 (easy, medium, hard)로 조절하고,
코드 심볼을 추가한 후 MusicXML 파일로 저장합니다.

v3 (Heuristic-based difficulty – NO Music2MIDI):
| Level  | Content                         | Algorithm                                |
|--------|---------------------------------|------------------------------------------|
| Easy   | Melody only (RH skyline)        | Skyline → filter_short → resolve_overlap |
| Medium | Melody + simplified bass (LH)   | Skyline melody + lowest-note-per-beat LH |
| Hard   | Full Pop2Piano arrangement      | Passthrough (no reduction)               |
"""

import math
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Dict, List

import music21

from core.midi_parser import Note, parse_midi
from core.melody_extractor import apply_skyline, filter_short_notes, resolve_overlaps
from core.midi_to_musicxml import (
    notes_to_stream,
    notes_to_piano_musicxml,
    seconds_to_quarter_length,
    stream_to_musicxml,
)

# Hand-split threshold (MIDI note number): >= threshold → RH, < threshold → LH
HAND_SPLIT = 60  # C4


# ── Public 3-level API ──────────────────────────────────────────────


def generate_easy_difficulty(notes: List[Note]) -> List[Note]:
    """
    Easy: Melody extraction using skyline algorithm.

    Pipeline (reuses melody_extractor.py functions):
      1. Skyline – keep highest note per simultaneous group
      2. Filter short notes (< 50ms)
      3. Resolve overlaps

    Result is a monophonic melodic line suitable for single-staff display.

    Args:
        notes: Full polyphonic Note list from Pop2Piano output.

    Returns:
        Melody-only Note list (monophonic).
    """
    work = deepcopy(notes)
    melody = apply_skyline(work)
    melody = filter_short_notes(melody)
    melody = resolve_overlaps(melody)
    return melody


def generate_medium_difficulty(notes: List[Note], beat_sec: float = 0.5) -> List[Note]:
    """
    Medium: Melody (RH) + simplified bass accompaniment (LH).

    RH: Skyline melody (same pipeline as Easy).
    LH: Simplified bass line – keep only the lowest note per beat window
         among notes with pitch < HAND_SPLIT (C4).

    Args:
        notes: Full polyphonic Note list.
        beat_sec: Beat duration in seconds (default 0.5 = 120 BPM quarter).
                  Used to determine the beat-window size for LH simplification.

    Returns:
        Combined melody + simplified-bass Note list.
    """
    work = deepcopy(notes)

    # ── RH: skyline melody ──
    melody = apply_skyline(work)
    melody = filter_short_notes(melody)
    melody = resolve_overlaps(melody)

    # ── LH: simplified bass ──
    lh_notes = [n for n in deepcopy(notes) if n.pitch < HAND_SPLIT]
    bass = _simplify_bass(lh_notes, beat_sec)

    # Combine and sort by onset
    combined = melody + bass
    combined.sort(key=lambda n: (n.onset, n.pitch))
    return combined


def generate_hard_difficulty(notes: List[Note]) -> List[Note]:
    """
    Hard: Full Pop2Piano arrangement (passthrough).

    No reduction – returns a deep copy of the original notes.

    Args:
        notes: Full polyphonic Note list.

    Returns:
        Complete polyphonic Note list (deep copy).
    """
    return deepcopy(notes)


# ── Internal helpers ──────────────────────────────────────────────────


def _simplify_bass(lh_notes: List[Note], beat_sec: float) -> List[Note]:
    """
    Simplify left-hand notes by keeping only the lowest note per beat window.

    Groups notes into beat-sized windows, then selects the lowest-pitched
    note from each window. This produces a sparse, root-note-style bass line.

    Args:
        lh_notes: Left-hand notes (pitch < HAND_SPLIT).
        beat_sec: Beat duration in seconds for window grouping.

    Returns:
        Simplified bass Note list (one note per beat window max).
    """
    if not lh_notes or beat_sec <= 0:
        return []

    # Group by beat window
    by_beat: Dict[int, List[Note]] = defaultdict(list)
    for n in lh_notes:
        beat_idx = int(math.floor(n.onset / beat_sec))
        by_beat[beat_idx].append(n)

    # Keep lowest note per beat
    result = []
    for _beat_idx, group in sorted(by_beat.items()):
        lowest = min(group, key=lambda n: n.pitch)
        result.append(lowest)

    return result


# ── Legacy wrapper (backward-compatible) ─────────────────────────────


def adjust_difficulty(notes: List[Note], level: str, bpm: float) -> List[Note]:
    """
    Adjust note list to match difficulty level.
    All time units are in seconds.

    Delegates to the 3-level heuristic functions.

    Args:
        notes: List[Note] - 원본 Note 리스트 (초 단위 시간)
        level: str - 난이도 ("easy", "medium", "hard")
        bpm: float - 템포 (beats per minute)

    Returns:
        List[Note]: 난이도 조절된 Note 리스트
    """
    beat_sec = 60.0 / bpm

    if level == "easy":
        return generate_easy_difficulty(notes)
    elif level == "medium":
        return generate_medium_difficulty(notes, beat_sec=beat_sec)
    else:  # hard
        return generate_hard_difficulty(notes)


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
        - Chord 분석은 프레임 단위로 매우 촘촘하게 나오는 경우가 있어,
          그대로 insert하면 MusicXML export에서 매우 짧은 forward/rest가 생성되어
          "inexpressible duration" / "2048th" 오류를 유발할 수 있습니다.
        - 따라서 beat(1/4 note) 그리드로 퀀타이즈하고, 같은 시점의 코드들은
          confidence가 가장 높은 1개만 남깁니다.
        - 원본 Stream을 직접 수정하여 반환 (in-place)
    """

    if not chords:
        return stream

    beat_sec = 60.0 / bpm

    # Quantize to beat grid and keep best-confidence chord per slot
    best_by_time: Dict[float, Dict] = {}
    for chord_info in chords:
        chord_str = chord_info.get("chord")
        if not chord_str:
            continue

        # Validate chord starts with a valid root note (A-G)
        if chord_str[0].upper() not in "ABCDEFG":
            continue

        t = float(chord_info.get("time", 0.0))
        # Snap to nearest beat to avoid tiny durations
        t_q = round(t / beat_sec) * beat_sec

        prev = best_by_time.get(t_q)
        if prev is None or float(chord_info.get("confidence", 0.0)) > float(
            prev.get("confidence", 0.0)
        ):
            best_by_time[t_q] = chord_info

    for t_q, chord_info in sorted(best_by_time.items(), key=lambda x: x[0]):
        chord_str = chord_info.get("chord")
        offset_ql = seconds_to_quarter_length(t_q, bpm)

        try:
            cs = music21.harmony.ChordSymbol(chord_str)
            stream.insert(offset_ql, cs)
        except Exception as e:
            import logging

            logging.warning(f"Skipping invalid chord '{chord_str}': {e}")

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
        - 입력: melody.mid (편곡 모델 출력) + analysis.json (분석 결과)
        - 처리: MIDI → Note 리스트 → 난이도별 Note 리스트 → MusicXML
        - 출력: sheet_easy.musicxml, sheet_medium.musicxml, sheet_hard.musicxml
        - Easy: single staff (melody only), Medium/Hard: two-hand piano score
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

        # Easy: single staff (monophonic melody)
        # Medium/Hard: two-hand piano score (polyphonic)
        use_polyphonic = difficulty in ("medium", "hard")

        if use_polyphonic:
            # Two-hand piano score
            musicxml_str = notes_to_piano_musicxml(
                adjusted_notes, bpm, key, polyphonic=True
            )
        else:
            # Legacy single-staff mode with chord symbols
            stream = notes_to_stream(adjusted_notes, bpm, key)
            add_chord_symbols(stream, chords, bpm)
            musicxml_str = stream_to_musicxml(stream)

        # Save to file (atomic write)
        output_path = job_dir / f"sheet_{difficulty}.musicxml"
        write_file_atomic(output_path, musicxml_str)

        result[difficulty] = output_path

    return result
