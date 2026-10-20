from __future__ import annotations

import json
from pathlib import Path
from jsonschema import Draft202012Validator
from .models import SCHEMA, FPS, RenderError, frame_count

def load_storyboard(path: Path, schema: Path = SCHEMA):
    data = json.loads(path.read_text(encoding='utf-8'))
    validator = Draft202012Validator(json.loads(schema.read_text(encoding='utf-8')))
    errors = sorted(validator.iter_errors(data), key=lambda e: str(list(e.path)))
    if errors:
        raise RenderError('Invalid storyboard: ' + '; '.join(f'{list(e.path)}: {e.message}' for e in errors))
    ids = [s['id'] for s in data['scenes']]
    if len(ids) != len(set(ids)):
        raise RenderError('Duplicate scene IDs')
    expected = [f'scene_{i:03}' for i in range(1, len(ids) + 1)]
    if ids != expected:
        raise RenderError(f'Invalid scene order: expected {expected}, got {ids}; scenes will not be reordered')
    fmt = data['format']
    if (fmt['resolution'], fmt['aspect_ratio'], fmt.get('fps', FPS)) != ('1080x1920', '9:16', FPS):
        raise RenderError('MVP requires 1080x1920, 9:16, 30 fps')
    duration = sum(frame_count(s) / FPS for s in data['scenes'])
    if abs(duration - fmt['target_duration_seconds']) > fmt['target_duration_seconds'] * .08:
        raise RenderError('Scene duration sum differs from target by more than 8%; input will not be rewritten')
    return data
