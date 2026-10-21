"""Video asset providers.

The current CLI adapter ingests local MP4/MOV/WebM files. Future AI video
providers can implement the same get_or_generate_video contract and own their
provider-specific request/cache policy; no external video API is called here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..ffmpeg import probe
from ..models import RenderError
from .image import PlaceholderImage

VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".mkv", ".webm")


class VideoProvider(Protocol):
    """Return a reusable local video file for a scene, or None if unavailable."""

    cache_key: str
    provider_name: str

    def get_or_generate_video(
        self, scene: dict, duration_seconds: float, workdir: Path
    ) -> Path | None: ...


def find_video_asset(assets_dir: Path | str | None, scene_id: str) -> Path | None:
    """Find exactly one pre-generated clip named after a scene ID."""
    if assets_dir is None:
        return None
    directory = Path(assets_dir).expanduser().resolve()
    matches = [directory / f"{scene_id}{extension}" for extension in VIDEO_EXTENSIONS
               if (directory / f"{scene_id}{extension}").is_file()]
    if len(matches) > 1:
        raise RenderError(
            f"{scene_id}: multiple video assets found; keep exactly one of "
            + ", ".join(VIDEO_EXTENSIONS)
        )
    return matches[0] if matches else None


def validate_video_asset(path: Path | str) -> dict:
    """Fail fast for unreadable files or assets without a real video stream."""
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise RenderError(f"Video asset does not exist or is empty: {path}")
    try:
        metadata = probe(path)
    except Exception as exc:
        raise RenderError(f"Cannot probe video asset {path}: {exc}") from exc
    stream = next((item for item in metadata.get("streams", [])
                   if item.get("codec_type") == "video"), None)
    if stream is None:
        raise RenderError(f"Video asset contains no video stream: {path}")
    try:
        duration = float(metadata["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RenderError(f"Video asset has no valid duration: {path}") from exc
    if duration <= 0:
        raise RenderError(f"Video asset has invalid duration: {path}")
    return {"path": str(path), "duration_seconds": duration,
            "width": stream.get("width"), "height": stream.get("height"),
            "codec": stream.get("codec_name")}


class SuppliedVideoProvider:
    """Resolve caller-supplied MP4/MOV/WebM clips without any network request."""

    cache_key = "supplied-video-v1"
    provider_name = "supplied-video"

    def __init__(self, assets_dir: Path | str):
        self.assets_dir = Path(assets_dir).expanduser().resolve()
        if not self.assets_dir.is_dir():
            raise RenderError(f"Video assets directory does not exist: {self.assets_dir}")

    def get_or_generate_video(self, scene, duration_seconds, workdir):
        asset = find_video_asset(self.assets_dir, scene["id"])
        if asset is not None:
            validate_video_asset(asset)
        return asset


class StaticVideoFallback:
    """Legacy still-image fallback for storyboard scenes without a supplied clip."""

    cache_key = "static-video-v1"

    def generate_video(self, scene, font_path, output_path):
        return PlaceholderImage().generate_image(scene, font_path, output_path)
