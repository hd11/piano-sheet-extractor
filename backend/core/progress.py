"""
Progress calculation SSOT module

This module defines the progress ranges for each processing stage
and provides utilities to calculate overall progress.
"""

from typing import Dict, Tuple


def get_stage_ranges() -> Dict[str, Tuple[int, int]]:
    """
    Returns progress ranges for each processing stage.

    SSOT for all progress calculations in the system.

    Returns:
        Dict mapping stage name to (start_progress, end_progress)

    Stages:
        - youtube_download: 0-20% (YouTube input only)
        - audio_to_midi: 20-50% (Basic Pitch conversion)
        - melody_extraction: 50-60% (Skyline algorithm)
        - analysis: 60-70% (BPM/Key/Chord detection)
        - sheet_generation: 70-100% (MusicXML generation)
    """
    return {
        "youtube_download": (0, 20),
        "audio_to_midi": (20, 50),
        "melody_extraction": (50, 60),
        "analysis": (60, 70),
        "sheet_generation": (70, 100),
    }


def calculate_progress(stage: str, stage_progress: float) -> int:
    """
    Calculate overall progress from stage and stage-specific progress.

    Args:
        stage: Stage name (from get_stage_ranges keys)
        stage_progress: Progress within stage (0.0-1.0)

    Returns:
        Overall progress (0-100)

    Example:
        >>> calculate_progress("audio_to_midi", 0.5)
        35  # 20 + (50-20) * 0.5
    """
    ranges = get_stage_ranges()
    if stage not in ranges:
        return 0

    start, end = ranges[stage]
    return int(start + (end - start) * stage_progress)
