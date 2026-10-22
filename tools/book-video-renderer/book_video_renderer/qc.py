from __future__ import annotations

import math
from .models import WIDTH, HEIGHT, FPS, RenderError
from .ffmpeg import probe, command

def verify_video(path, duration, audio):
    info = probe(path)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if not video or (video['width'], video['height'], video['codec_name'], video['r_frame_rate'], video['pix_fmt']) != (WIDTH, HEIGHT, 'h264', '30/1', 'yuv420p'):
        raise RenderError(f'Invalid output video format: {path}')
    tracks = [s for s in info['streams'] if s['codec_type'] == 'audio']
    if bool(tracks) != audio or any(s['codec_name'] != 'aac' for s in tracks):
        raise RenderError(f'Unexpected audio tracks: {path}')
    actual_duration = float(info['format']['duration'])
    if not math.isfinite(actual_duration) or actual_duration <= 0 or abs(actual_duration - duration) > .15:
        raise RenderError(f'Unexpected duration: {path}')
    command(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', path, '-f', 'null', '-'])
    return {'width': WIDTH, 'height': HEIGHT, 'fps': FPS, 'video_codec': 'h264',
            'audio_codec': 'aac' if tracks else None, 'duration_seconds': float(info['format']['duration']),
            'ffprobe_status': 'PASS', 'full_decode_status': 'PASS'}
