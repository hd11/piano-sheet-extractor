"""
멜로디 추출 모듈 - Skyline 알고리즘 및 MIDI 이벤트 처리 정책

폴리포닉 MIDI를 모노포닉 멜로디로 변환합니다.
"""

from pathlib import Path
from typing import List
from core.midi_parser import Note, parse_midi


def apply_skyline(notes: List[Note]) -> List[Note]:
    """
    동일 onset에 여러 음표가 있을 때 최고음만 선택

    정책:
    - onset 차이가 ONSET_TOLERANCE 이내면 "동시 발음"으로 간주
    - 동시 발음 중 pitch가 가장 높은 음표만 유지
    - 나머지는 삭제

    Args:
        notes: Note 리스트

    Returns:
        Skyline 적용된 Note 리스트
    """
    ONSET_TOLERANCE = 0.02  # 20ms 이내는 동시 발음으로 간주

    if not notes:
        return notes

    # onset 기준 정렬
    sorted_notes = sorted(notes, key=lambda n: (n.onset, -n.pitch))

    result = []
    i = 0
    while i < len(sorted_notes):
        current = sorted_notes[i]

        # 동시 발음 그룹 찾기
        group = [current]
        j = i + 1
        while (
            j < len(sorted_notes)
            and abs(sorted_notes[j].onset - current.onset) <= ONSET_TOLERANCE
        ):
            group.append(sorted_notes[j])
            j += 1

        # 최고음 선택 (이미 pitch 내림차순 정렬됨)
        highest = max(group, key=lambda n: n.pitch)
        result.append(highest)

        i = j

    return result


def filter_short_notes(notes: List[Note]) -> List[Note]:
    """
    너무 짧은 음표 제거

    정책:
    - MIN_DURATION (50ms) 미만인 음표는 제거
    - 이 기준은 "duration" 기준 (onset 간격 아님)

    Args:
        notes: Note 리스트

    Returns:
        필터링된 Note 리스트
    """
    MIN_DURATION = 0.05  # 50ms

    return [n for n in notes if n.duration >= MIN_DURATION]


def resolve_overlaps(notes: List[Note]) -> List[Note]:
    """
    음표 겹침(overlap) 해결

    정책:
    - 이전 음표가 끝나기 전에 다음 음표가 시작되면
    - 이전 음표의 duration을 잘라서 겹침 제거
    - 연속 타이(tie)는 별도 처리 안 함 (단순화)

    Args:
        notes: Note 리스트

    Returns:
        겹침이 해결된 Note 리스트
    """
    if not notes:
        return notes

    sorted_notes = sorted(notes, key=lambda n: n.onset)
    result = [sorted_notes[0]]

    for i in range(1, len(sorted_notes)):
        prev = result[-1]
        curr = sorted_notes[i]

        # 겹침 확인
        prev_end = prev.onset + prev.duration
        if prev_end > curr.onset:
            # 이전 음표 duration 조정
            prev.duration = curr.onset - prev.onset
            if prev.duration < 0.01:  # 너무 짧아지면 제거
                result.pop()

        result.append(curr)

    return result


def normalize_octave(
    notes: List[Note], min_pitch: int = 48, max_pitch: int = 84
) -> List[Note]:
    """
    옥타브 정규화 (C3-C6 범위로)

    정책:
    - 범위 밖의 음표는 옥타브 이동 (±12)
    - 범위 내의 음표는 변경 없음

    Args:
        notes: Note 리스트
        min_pitch: 최소 pitch (기본 48 = C3)
        max_pitch: 최대 pitch (기본 84 = C6)

    Returns:
        정규화된 Note 리스트
    """
    result = []
    for note in notes:
        new_pitch = note.pitch

        # 범위보다 낮으면 옥타브 올림
        while new_pitch < min_pitch:
            new_pitch += 12

        # 범위보다 높으면 옥타브 내림
        while new_pitch > max_pitch:
            new_pitch -= 12

        result.append(
            Note(
                pitch=new_pitch,
                onset=note.onset,
                duration=note.duration,
                velocity=note.velocity,
            )
        )

    return result


def extract_melody(midi_path: Path) -> List[Note]:
    """
    MIDI에서 멜로디 추출 전체 파이프라인

    순서:
    1. MIDI 파싱 → Note 리스트
    2. Skyline 적용 (동시 발음 → 최고음)
    3. 짧은 음표 제거 (< 50ms)
    4. Overlap 해결
    5. 옥타브 정규화 (C3-C6)

    Args:
        midi_path: MIDI 파일 경로

    Returns:
        추출된 멜로디 Note 리스트
    """
    # 1. MIDI 파싱
    notes = parse_midi(midi_path)

    # 2. Skyline
    notes = apply_skyline(notes)

    # 3. 짧은 음표 제거
    notes = filter_short_notes(notes)

    # 4. Overlap 해결
    notes = resolve_overlaps(notes)

    # 5. 옥타브 정규화
    notes = normalize_octave(notes, min_pitch=48, max_pitch=84)  # C3-C6

    return notes
