"""Video provider boundary; the MVP deliberately uses local stills."""
from pathlib import Path
from typing import Protocol
from .image import PlaceholderImage
from ..models import RenderError


class VideoProvider(Protocol):
    def generate_video(self, scene: dict, font_path: Path | None, output_path: Path) -> Path: ...


def find_video_asset(assets_dir, scene_id):
    """Find an optional pre-generated motion clip named <scene_id>.<video extension>."""
    if assets_dir is None:
        return None
    extensions = ('.mp4', '.mov', '.m4v', '.webm', '.mkv')
    matches = [
        Path(assets_dir) / (scene_id + ext)
        for ext in extensions
        if (Path(assets_dir) / (scene_id + ext)).is_file()
    ]
    if len(matches) > 1:
        raise RenderError(
            f"{scene_id}: multiple video assets found; keep exactly one of "
            "MP4, MOV, M4V, WebM, or MKV."
        )
    return matches[0] if matches else None



class StaticVideoFallback:
    cache_key = 'static-video-v1'

    def generate_video(self, scene, font_path, output_path):
        return PlaceholderImage().generate_image(scene, font_path, output_path)
