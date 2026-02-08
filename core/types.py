"""Data types for piano sheet extraction."""

from dataclasses import dataclass


@dataclass
class Note:
    """Represents a musical note.

    Attributes:
        pitch: MIDI pitch number (0-127)
        onset: Time in seconds when note starts
        duration: Duration in seconds
        velocity: MIDI velocity (0-127), defaults to 80
    """

    pitch: int
    onset: float
    duration: float
    velocity: int = 80
