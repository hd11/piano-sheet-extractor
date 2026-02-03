#!/usr/bin/env python3
"""
E2E 테스트용 샘플 오디오 생성

저작권 문제 없는 합성 오디오를 생성합니다.
- 단순한 멜로디 (C major scale)
- 10초 길이
- MP3 형식
"""

import numpy as np
from scipy.io import wavfile
import subprocess
from pathlib import Path
import sys


def generate_test_audio(output_dir: Path = None):
    """
    테스트용 오디오 파일 생성

    Args:
        output_dir: 출력 디렉토리 (기본값: backend/tests/fixtures)

    Returns:
        Path: 생성된 MP3 파일 경로
    """
    if output_dir is None:
        # Docker 컨테이너 내부에서 실행 시
        if Path("/app").exists():
            output_dir = Path("/app/tests/fixtures")
        else:
            # 로컬 실행 시
            output_dir = Path(__file__).parent.parent / "tests" / "fixtures"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 오디오 파라미터
    sr = 44100  # Sample rate
    duration = 10  # 10초

    # C major scale (C4-C5)
    frequencies = [
        261.63,  # C4
        293.66,  # D4
        329.63,  # E4
        349.23,  # F4
        392.00,  # G4
        440.00,  # A4
        493.88,  # B4
        523.25,  # C5
    ]

    # 각 음표 생성
    audio = np.array([], dtype=np.float32)
    note_duration = duration / len(frequencies)

    for freq in frequencies:
        t = np.linspace(0, note_duration, int(sr * note_duration), False)
        note = np.sin(2 * np.pi * freq * t) * 0.5

        # Envelope (fade in/out)
        envelope = np.ones_like(note)
        fade_len = int(sr * 0.05)  # 50ms fade
        envelope[:fade_len] = np.linspace(0, 1, fade_len)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)

        audio = np.concatenate([audio, note * envelope])

    # WAV 저장
    wav_path = output_dir / "test_audio.wav"
    wavfile.write(str(wav_path), sr, (audio * 32767).astype(np.int16))
    print(f"Generated WAV: {wav_path}")

    # MP3 변환 (ffmpeg)
    mp3_path = output_dir / "test_audio.mp3"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                "-qscale:a",
                "2",
                str(mp3_path),
            ],
            check=True,
            capture_output=True,
        )
        print(f"Converted to MP3: {mp3_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error converting to MP3: {e.stderr.decode()}", file=sys.stderr)
        return wav_path  # WAV 파일 반환

    # WAV 삭제 (MP3만 필요)
    wav_path.unlink()

    print(f"\n✅ Generated: {mp3_path}")
    print(f"   Duration: 10 seconds")
    print(f"   Content: C major scale (C4-C5)")
    print(f"   Size: {mp3_path.stat().st_size / 1024:.1f} KB")

    return mp3_path


if __name__ == "__main__":
    generate_test_audio()
