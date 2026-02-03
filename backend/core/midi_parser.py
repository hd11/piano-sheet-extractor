"""
MIDI 파싱 SSOT 모듈 - pretty_midi만 사용

이 모듈은 프로젝트 전체에서 MIDI 파싱의 Single Source of Truth입니다.
다른 모듈에서는 이 모듈의 parse_midi() 함수만 사용해야 합니다.
"""

import pretty_midi
from dataclasses import dataclass
from typing import List
from pathlib import Path


@dataclass
class Note:
    """MIDI 노트 표현 (초 단위 시간)"""

    pitch: int  # MIDI pitch (0-127, 60=C4)
    onset: float  # 시작 시간 (초)
    duration: float  # 길이 (초)
    velocity: int  # 세기 (0-127)


def parse_midi(midi_path: Path) -> List[Note]:
    """
    MIDI 파일을 Note 리스트로 파싱 (SSOT 함수)

    Args:
        midi_path: MIDI 파일 경로

    Returns:
        List[Note]: 초 단위 시간의 Note 리스트

    Note:
        - pretty_midi는 내부적으로 tempo map을 처리하여 초 단위 시간 반환
        - 본 프로젝트는 단일 BPM을 가정하므로 tempo 변화는 무시됨
        - 여러 트랙이 있으면 모든 트랙의 노트를 합침 (멜로디 추출은 별도 처리)
        - 드럼 트랙은 제외
    """
    pm = pretty_midi.PrettyMIDI(str(midi_path))

    notes = []
    for instrument in pm.instruments:
        if instrument.is_drum:
            continue  # 드럼 트랙 제외

        for note in instrument.notes:
            notes.append(
                Note(
                    pitch=note.pitch,
                    onset=note.start,  # 이미 초 단위
                    duration=note.end - note.start,  # 이미 초 단위
                    velocity=note.velocity,
                )
            )

    # onset 기준 정렬
    notes.sort(key=lambda n: n.onset)
    return notes
