"""Core module for piano sheet extraction."""

from .types import Note
from .reference_extractor import extract_reference_melody
from .vocal_melody_extractor import extract_melody
from .musicxml_writer import notes_to_musicxml, save_musicxml

__all__ = [
    "Note",
    "extract_reference_melody",
    "extract_melody",
    "notes_to_musicxml",
    "save_musicxml",
]
