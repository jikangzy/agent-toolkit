from __future__ import annotations

from .models import WIDTH, HEIGHT, FPS, RenderError
from .ffmpeg import probe

def verify_video(path, duration, audio):
    info = probe(path)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if not video or (video['width'], video['height'], video['codec_name'], video['r_frame_rate'], video['pix_fmt']) != (WIDTH, HEIGHT, 'h264', '30/1', 'yuv420p'):
        raise RenderError(f'Invalid output video format: {path}')
    tracks = [s for s in info['streams'] if s['codec_type'] == 'audio']
    if bool(tracks) != audio or any(s['codec_name'] != 'aac' for s in tracks):
        raise RenderError(f'Unexpected audio tracks: {path}')
    if abs(float(info['format']['duration']) - duration) > .15:
        raise RenderError(f'Unexpected duration: {path}')
    return {'width': WIDTH, 'height': HEIGHT, 'fps': FPS, 'video_codec': 'h264',
            'audio_codec': 'aac' if tracks else None, 'duration_seconds': float(info['format']['duration'])}
