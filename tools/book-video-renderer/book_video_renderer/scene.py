from __future__ import annotations

from pathlib import Path

from .models import FPS, RenderError, frame_count
from .ffmpeg import command, probe
from .qc import verify_video
from .manifest import save_json
from .providers.image import prepare_visual, prepare_text_overlay
from .providers.video import validate_video_asset


def encode_scene(scene, data, font, work, provider, visual_asset=None, video_asset=None):
    """Encode one scene from a still image or real motion footage plus narration."""
    image, clip = work/'visual.png', work/'clip.mp4'
    duration = frame_count(scene) / FPS
    if video_asset is not None:
        validate_video_asset(video_asset)
        # The PNG is a transparent text overlay, not a still-image replacement.
        prepare_text_overlay(scene, font, image)
    else:
        prepare_visual(scene, font, image, visual_asset)

    audio = provider.synthesize(scene['id'], scene['narration'], data['voice'], duration, work)
    save_json(work/'speech.json', {'audio_path': str(audio.resolve()) if audio else None})
    if audio:
        info = probe(audio)
        if not any(s.get('codec_type') == 'audio' for s in info['streams']):
            raise RenderError(f"{scene['id']}: provider returned a file without audio")
        if float(info['format']['duration']) > duration + .001:
            raise RenderError(f"{scene['id']}: speech exceeds scene duration; refusing to truncate narration")

    if video_asset is not None:
        args = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-stream_loop', '-1', '-i', video_asset,
            '-loop', '1', '-i', image,
        ]
        if audio:
            args += ['-i', audio]
        filter_complex = (
            f'[0:v]scale=1080:1920:force_original_aspect_ratio=increase,'
            f'crop=1080:1920,fps={FPS},setsar=1,'
            f'trim=duration={duration:.6f},setpts=PTS-STARTPTS[base];'
            '[1:v]format=rgba[overlay];'
            '[base][overlay]overlay=0:0:shortest=1,format=yuv420p[vout]'
        )
        args += [
            '-filter_complex', filter_complex,
            '-map', '[vout]',
            '-frames:v', frame_count(scene),
            '-t', f'{duration:.6f}',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-pix_fmt', 'yuv420p', '-threads', '2',
        ]
        if audio:
            args += ['-map', '2:a:0', '-af', 'apad', '-c:a', 'aac', '-ar', '48000', '-ac', '2']
        else:
            args += ['-an']
        args += ['-movflags', '+faststart', clip]
    else:
        zoom = motion_filter(scene)
        args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', image]
        if audio:
            args += ['-i', audio]
        args += ['-vf', zoom, '-frames:v', frame_count(scene), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p', '-threads', '2']
        if audio:
            args += ['-af', 'apad', '-t', f'{duration:.6f}', '-c:a', 'aac', '-ar', '48000', '-ac', '2']
        else:
            args += ['-an']
        args += ['-movflags', '+faststart', clip]

    command(args)
    verify_video(clip, duration, audio is not None)
    return clip, audio is not None


def motion_filter(scene):
    """Bounded Ken Burns motion; unknown motions safely use a gentle push-in."""
    frames = frame_count(scene)
    progress = f'on/{max(1, frames - 1)}'
    motion = scene['visual'].get('motion', '').lower()
    z, x, y = f'1.015+0.025*{progress}', 'iw/2-iw/zoom/2', 'ih/2-ih/zoom/2'
    if 'zoom-out' in motion or 'zoom out' in motion:
        z = f'1.04-0.025*{progress}'
    elif 'pan' in motion and any(direction in motion for direction in ('left', 'right', 'up', 'down')):
        z = '1.04'
        if 'right' in motion:
            x = f'(iw-iw/zoom)*({progress})'
        elif 'left' in motion:
            x = f'(iw-iw/zoom)*(1-{progress})'
        elif 'down' in motion:
            y = f'(ih-ih/zoom)*({progress})'
        else:
            y = f'(ih-ih/zoom)*(1-{progress})'
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s=1080x1920:fps=30"
