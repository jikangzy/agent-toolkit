from __future__ import annotations

import re
from pathlib import Path
from .models import FPS, RenderError, frame_count
from .manifest import digest

def stamp(seconds):
    ms = round(seconds * 1000)
    seconds, ms = divmod(ms, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def subtitles(data):
    """Scene-timed fallback, not forced alignment. Never strip or rewrite narration."""
    entries, offset = [], 0
    for scene in data['scenes']:
        narration = scene['narration']
        chunks = [narration[i:i+18] for i in range(0, len(narration), 18)]
        duration = frame_count(scene) / FPS
        for i, text in enumerate(chunks):
            start = offset + duration * (i * 18) / len(narration)
            end = offset + duration * min((i+1)*18, len(narration)) / len(narration)
            entries.append(f'{len(entries)+1}\n{stamp(start)} --> {stamp(end)}\n{text}\n')
        offset += duration
    return '\n'.join(entries)


def _srt_seconds(value):
    match = re.fullmatch(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', value)
    if not match:
        raise RenderError(f'Invalid SRT timestamp: {value}')
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def validate_subtitle_file(path, duration):
    """Validate an externally generated SRT before burning it into the video."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise RenderError(f'Subtitle file does not exist: {path}')
    content = path.read_text(encoding='utf-8-sig')
    pattern = re.compile(
        r'(?m)^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*$'
    )
    matches = list(pattern.finditer(content))
    if not matches:
        raise RenderError('Subtitle file has no valid SRT timing entries')
    previous_start = -1.0
    for match in matches:
        start, end = _srt_seconds(match.group(1)), _srt_seconds(match.group(2))
        if end <= start:
            raise RenderError('Subtitle cue end must be after its start')
        if start < previous_start:
            raise RenderError('Subtitle cues must be ordered by start time')
        if end > duration + 0.15:
            raise RenderError('Subtitle cue extends beyond the final video duration')
        previous_start = start
    return {'path': path, 'sha256': digest(path), 'cue_count': len(matches)}
