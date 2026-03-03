"""Data types for piano sheet extraction."""

from dataclasses import dataclass

import numpy as np


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


@dataclass
class F0Contour:
    """Continuous fundamental frequency contour.

    Attributes:
        times: Time stamps in seconds per frame
        frequencies: F0 in Hz per frame (0.0 = unvoiced)
        confidence: Confidence/periodicity per frame (0.0-1.0)
    """

    times: np.ndarray
    frequencies: np.ndarray
    confidence: np.ndarray
