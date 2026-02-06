"""
멜로디 추출 모듈 - Hybrid Scoring 알고리즘 및 MIDI 이벤트 처리 정책

폴리포닉 MIDI를 모노포닉 멜로디로 변환합니다.
Hybrid Scoring: velocity + contour + register 가중 합으로 멜로디 음표 선택
"""

import json
import logging
import math
import subprocess
from pathlib import Path
from typing import List, Optional

from core.midi_parser import Note, parse_midi


def hybrid_score(note: Note, prev_pitch: Optional[int]) -> float:
    """
    Hybrid Scoring: velocity + contour + register 가중 합

    Args:
        note: 현재 노트
        prev_pitch: 이전 멜로디 노트의 pitch (없으면 None)

    Returns:
        0.0 ~ 1.0 사이의 점수
    """
    # velocity_score: 0.0 ~ 1.0
    v = note.velocity / 127

    # contour_score: 이전 음과의 거리 반비례
    if prev_pitch is not None:
        c = 1.0 / (1 + abs(note.pitch - prev_pitch))
    else:
        c = 0.5  # 첫 노트는 중립

    # register_score: C5(72) 중심 가우시안
    r = math.exp(-((note.pitch - 72) ** 2) / (2 * 12**2))

    return 0.5 * v + 0.3 * c + 0.2 * r


def apply_hybrid_scoring(notes: List[Note]) -> List[Note]:
    """
    동일 onset 그룹에서 가장 높은 hybrid_score를 가진 노트 선택

    Args:
        notes: Note 리스트

    Returns:
        Hybrid Scoring 적용된 Note 리스트
    """
    ONSET_TOLERANCE = 0.2  # 200ms

    if not notes:
        return notes

    sorted_notes = sorted(notes, key=lambda n: n.onset)
    result = []
    prev_pitch = None

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

        # 그룹에서 가장 높은 hybrid_score 선택 (동점: pitch 높은 것 선택)
        best = max(group, key=lambda n: (hybrid_score(n, prev_pitch), n.pitch))
        result.append(best)
        prev_pitch = best.pitch

        i = j

    return result


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
    ONSET_TOLERANCE = 0.2  # 200ms 이내는 동시 발음으로 간주

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
    2. Hybrid Scoring 적용 (동시 발음 → velocity + contour + register 기반 선택)
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

    # 2. Hybrid Scoring (velocity + contour + register 가중합)
    notes = apply_hybrid_scoring(notes)

    # 3. 짧은 음표 제거
    notes = filter_short_notes(notes)

    # 4. Overlap 해결
    notes = resolve_overlaps(notes)

    # 5. 옥타브 정규화
    notes = normalize_octave(notes, min_pitch=48, max_pitch=84)  # C3-C6

    return notes


def _get_wsl_script_path() -> str:
    """
    현재 repo 기준 WSL 스크립트 경로 계산

    Returns:
        WSL 형식 경로 (예: /mnt/c/Users/.../essentia_melody_extractor.py)
    """
    import os

    this_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    script_path = this_dir.parent / "scripts" / "essentia_melody_extractor.py"

    # Windows 경로 → WSL 경로 변환
    win_path = str(script_path.resolve())
    drive_letter = win_path[0].lower()
    rest_path = win_path[2:].replace("\\", "/")
    return f"/mnt/{drive_letter}{rest_path}"


def _call_essentia_wsl(audio_path: Path) -> List[Note]:
    """
    WSL에서 Essentia를 호출하여 멜로디 추출

    Args:
        audio_path: 오디오 파일 경로 (Windows 형식)

    Returns:
        추출된 Note 리스트

    Raises:
        RuntimeError: Essentia 실행 실패 시
        subprocess.TimeoutExpired: 120초 타임아웃 초과 시
    """
    # Windows 경로 → WSL 경로 변환
    win_audio = str(audio_path.resolve())
    drive_letter = win_audio[0].lower()
    rest_path = win_audio[2:].replace("\\", "/")
    wsl_audio_path = f"/mnt/{drive_letter}{rest_path}"

    script_path = _get_wsl_script_path()

    result = subprocess.run(
        ["wsl", "python3", script_path, wsl_audio_path],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Essentia failed: {result.stderr}")

    data = json.loads(result.stdout)
    return [
        Note(pitch=n["pitch"], onset=n["onset"], duration=n["duration"], velocity=80)
        for n in data
    ]


def extract_melody_with_audio(audio_path: Path, midi_path: Path) -> List[Note]:
    """
    오디오 기반 Essentia 멜로디 추출 (폴백: MIDI 기반 Skyline)

    Essentia가 실패하면 자동으로 Skyline 알고리즘으로 폴백합니다.

    Args:
        audio_path: 오디오 파일 경로 (mp3, wav 등)
        midi_path: MIDI 파일 경로 (폴백용)

    Returns:
        추출된 멜로디 Note 리스트
    """
    logger = logging.getLogger(__name__)

    try:
        notes = _call_essentia_wsl(audio_path)
        logger.info(f"Essentia extracted {len(notes)} melody notes")
    except Exception as e:
        logger.warning(f"Essentia failed: {e}, falling back to Skyline")
        notes = extract_melody(midi_path)
        return notes  # 이미 후처리됨

    # Essentia 결과에 후처리 적용
    notes = filter_short_notes(notes)
    notes = resolve_overlaps(notes)
    notes = normalize_octave(notes)
    return notes
