"""
Modality adapters: Text, Image, Audio, Video.
"""

from .audio import AudioAdapter
from .base import BaseModalityAdapter
from .image import ImageAdapter
from .text import TextAdapter
from .video import VideoAdapter

__all__ = ["BaseModalityAdapter", "TextAdapter", "ImageAdapter", "AudioAdapter", "VideoAdapter"]
