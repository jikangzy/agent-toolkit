#!/usr/bin/env python3
"""Backward-compatible entrypoint; implementation lives in book_video_renderer."""
from book_video_renderer.models import *
from book_video_renderer.manifest import *
from book_video_renderer.ffmpeg import *
from book_video_renderer.validator import *
from book_video_renderer.fonts import *
from book_video_renderer.subtitle import *
from book_video_renderer.providers.image import *
from book_video_renderer.providers.music import *
from book_video_renderer.providers.tts import *
from book_video_renderer.qc import *
from book_video_renderer.scene import *
from book_video_renderer.renderer import render
from book_video_renderer.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
