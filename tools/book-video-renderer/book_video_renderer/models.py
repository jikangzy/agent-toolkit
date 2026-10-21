from __future__ import annotations

from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas/book-video/storyboard.schema.json"
VERSION = "mvp-5"
WIDTH, HEIGHT, FPS = 1080, 1920, 30

class RenderError(RuntimeError):
    pass


def frame_count(scene):
    return math.floor(scene['duration_seconds'] * FPS + .5)


def total_duration(data):
    """Return planned frame-rounded playback duration, without editing the input."""
    return sum(frame_count(scene) for scene in data['scenes']) / FPS
