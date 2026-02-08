"""Core module for piano sheet extraction."""

from .types import Note
from .reference_extractor import extract_reference_melody
from .vocal_separator import separate_vocals
from .musicxml_writer import notes_to_musicxml, save_musicxml

__all__ = [
    "Note",
    "extract_reference_melody",
    "separate_vocals",
    "notes_to_musicxml",
    "save_musicxml",
]
