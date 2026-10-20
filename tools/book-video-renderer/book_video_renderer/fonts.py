from __future__ import annotations

from pathlib import Path
from fontTools.ttLib import TTFont
from .ffmpeg import command
from .models import RenderError

def font_has_text(path: Path, text: str) -> bool:
    try:
        with TTFont(str(path), fontNumber=0) as font:
            cmap = font.getBestCmap() or {}
            return all(ord(c) in cmap for c in text if not c.isspace())
    except Exception:
        return False


def find_font(requested, text):
    candidates = [Path(requested)] if requested else []
    if not requested:
        try:
            candidates += [Path(p) for p in command(['fc-list', '-f', '%{file}\n', ':lang=zh']).splitlines()]
        except RenderError:
            pass
        candidates += [Path(p) for p in (
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            'C:/Windows/Fonts/msyh.ttc', '/System/Library/Fonts/PingFang.ttc')]
    for p in candidates:
        if p.is_file() and font_has_text(p, text):
            return p.resolve()
    raise RenderError('No font covers all storyboard characters; install Noto Sans CJK or pass --font PATH')
