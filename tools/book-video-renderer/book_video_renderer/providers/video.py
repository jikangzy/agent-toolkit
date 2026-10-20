"""Video provider boundary; the MVP deliberately uses local stills."""
from pathlib import Path
from typing import Protocol
from .image import PlaceholderImage


class VideoProvider(Protocol):
    def generate_video(self, scene: dict, font_path: Path | None, output_path: Path) -> Path: ...


class StaticVideoFallback:
    cache_key = 'static-video-v1'

    def generate_video(self, scene, font_path, output_path):
        return PlaceholderImage().generate_image(scene, font_path, output_path)
