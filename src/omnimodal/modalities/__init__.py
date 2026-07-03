"""
Modality adapters: Text, Image, Audio, Video.
"""

from .base import BaseModalityAdapter
from .text import TextAdapter
from .image import ImageAdapter
from .audio import AudioAdapter
from .video import VideoAdapter

__all__ = ["BaseModalityAdapter", "TextAdapter", "ImageAdapter", "AudioAdapter", "VideoAdapter"]
