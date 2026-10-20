from __future__ import annotations

import math
from pathlib import Path
from typing import Protocol
from ..models import RenderError
from ..ffmpeg import probe

def resolve_music(data, music_file=None, volume_override=None):
    """Validate an optional local music track; never synthesize or download music."""
    music = data.get('music', {})
    enabled = music.get('enabled', True)
    if music_file is None:
        if volume_override is not None:
            raise RenderError('--music-volume-db requires --music-file')
        return NoMusic().get_or_generate_music(music, 0), None
    if not enabled:
        raise RenderError('--music-file was supplied but storyboard music.enabled is false')
    path = Path(music_file).expanduser().resolve()
    if not path.is_file():
        raise RenderError(f'Background music file does not exist: {path}')
    metadata = probe(path)
    if not any(stream.get('codec_type') == 'audio' for stream in metadata.get('streams', [])):
        raise RenderError(f'Background music file contains no audio stream: {path}')
    try:
        volume_db = float(volume_override if volume_override is not None else music.get('volume_db', -24))
    except (TypeError, ValueError) as exc:
        raise RenderError('Background music volume must be a number between -60 and 0 dB') from exc
    if not math.isfinite(volume_db) or not -60 <= volume_db <= 0:
        raise RenderError('Background music volume must be between -60 and 0 dB')
    return path, volume_db


class MusicProvider(Protocol):
    def get_or_generate_music(self, config: dict, duration: float) -> Path | None: ...


class NoMusic:
    """Never downloads, generates, or licenses music implicitly."""
    def get_or_generate_music(self, config, duration):
        return None
