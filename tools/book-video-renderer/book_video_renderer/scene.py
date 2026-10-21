from __future__ import annotations

from .models import FPS, RenderError, frame_count
from .ffmpeg import command, probe
from .qc import verify_video
from .manifest import save_json
from .providers.image import prepare_visual, create_text_overlay

def encode_scene(scene, data, font, work, provider, visual_asset=None, video_asset=None):
    image, clip = work/'visual.png', work/'clip.mp4'
    duration = frame_count(scene) / FPS
    audio = provider.synthesize(scene['id'], scene['narration'], data['voice'], duration, work)
    save_json(work/'speech.json', {'audio_path': str(audio.resolve()) if audio else None})
    if audio:
        info = probe(audio)
        if not any(s.get('codec_type') == 'audio' for s in info['streams']):
            raise RenderError(f"{scene['id']}: provider returned a file without audio")
        if float(info['format']['duration']) > duration + .001:
            raise RenderError(f"{scene['id']}: speech exceeds scene duration; refusing to truncate narration")

    if video_asset is not None:
        video_info = probe(video_asset)
        if not any(stream.get('codec_type') == 'video' for stream in video_info.get('streams', [])):
            raise RenderError(f"{scene['id']}: supplied video asset contains no video stream: {video_asset}")
        if float(video_info.get('format', {}).get('duration', 0)) <= 0:
            raise RenderError(f"{scene['id']}: supplied video asset has invalid duration: {video_asset}")
        # Save a poster frame for the manifest and cache integrity checks.
        command([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-i', video_asset, '-frames:v', '1',
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920',
            image,
        ])
        overlay = work/'text-overlay.png'
        create_text_overlay(scene, font, overlay)
        args = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-stream_loop', '-1', '-i', video_asset,
        ]
        audio_index = None
        if audio:
            audio_index = 1
            args += ['-i', audio]
        overlay_index = 2 if audio else 1
        args += ['-loop', '1', '-i', overlay]
        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,fps=30,trim=duration={duration:.6f},"
            f"setpts=PTS-STARTPTS[base];"
            f"[base][{overlay_index}:v]overlay=0:0:shortest=1,format=yuv420p[v]"
        )
        args += [
            '-filter_complex', filter_complex, '-map', '[v]',
            '-frames:v', frame_count(scene),
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-pix_fmt', 'yuv420p', '-threads', '2',
        ]
        if audio:
            args += [
                '-map', f'{audio_index}:a:0', '-af', 'apad', '-t', f'{duration:.6f}',
                '-c:a', 'aac', '-ar', '48000', '-ac', '2',
            ]
        else:
            args += ['-an']
        args += ['-movflags', '+faststart', clip]
        command(args)
        verify_video(clip, duration, audio is not None)
        return clip, audio is not None

    prepare_visual(scene, font, image, visual_asset)
    zoom = motion_filter(scene)
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', image]
    if audio:
        args += ['-i', audio]
    args += ['-vf', zoom, '-frames:v', frame_count(scene), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p', '-threads', '2']
    if audio:
        args += ['-af', 'apad', '-t', duration, '-c:a', 'aac', '-ar', '48000', '-ac', '2']
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
