"""Assemble scene videos with a seekable HyperFrames/GSAP crossfade."""
from __future__ import annotations

import html
import shutil
import subprocess
from pathlib import Path

from .ffmpeg import command
from .models import FPS, RenderError, frame_count
from .qc import verify_video


def assemble(provider, clips, scenes, output, has_audio, transition=.6):
    output = Path(output)
    work = output / 'hyperframes-transition'
    work.mkdir(exist_ok=True)
    shutil.copyfile(provider.gsap_path, work / 'gsap.min.js')
    layers, tweens = [], []
    offset = 0.0
    total = sum(frame_count(scene) / FPS for scene in scenes)
    for i, (clip, scene) in enumerate(zip(clips, scenes)):
        duration = frame_count(scene) / FPS
        last = i == len(clips) - 1
        name = f'scene-{i}.mp4'
        destination = work / name
        if last:
            shutil.copyfile(clip, destination)
        else:
            # Extend the outgoing last frame through the transition; the next
            # scene begins at its storyboard time and no scene is shortened.
            command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', clip,
                     '-vf', f'tpad=stop_mode=clone:stop_duration={transition}', '-an',
                     '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                     '-threads', '2', destination])
        clip_duration = duration if last else duration + transition
        layers.append(f'<div class="layer layer-{i}" style="z-index:{len(clips)-i}">'
                      f'<video id="clip-{i}" data-start="{offset:.6f}" '
                      f'data-duration="{clip_duration:.6f}" data-track-index="{i+1}" '
                      f'src="{html.escape(name, quote=True)}" muted playsinline></video></div>')
        offset += duration
        if not last:
            tweens.append(f"tl.to('.layer-{i}',{{opacity:0,duration:{transition},ease:'none'}},{offset:.6f});")
    document = f'''<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0}}.root{{position:relative;width:1080px;height:1920px;background:#101a20;overflow:hidden}}
.layer{{position:absolute;inset:0}}video{{width:100%;height:100%;object-fit:cover}}
</style></head><body><div class="root" id="root" data-composition-id="assembly" data-start="0" data-duration="{total:.6f}" data-width="1080" data-height="1920">{''.join(layers)}</div><script src="gsap.min.js"></script><script>window.__timelines=window.__timelines||{{}};const tl=gsap.timeline({{paused:true}});{''.join(tweens)}window.__timelines.assembly=tl;</script></body></html>'''
    (work / 'index.html').write_text(document, encoding='utf-8')
    video = work / 'visual.mp4'
    result = subprocess.run([provider.executable, 'render', str(work), '--output', str(video),
                             '--fps', str(FPS), '--quality', 'standard', '--workers', '1'],
                            capture_output=True, text=True, timeout=3600)
    if result.returncode:
        raise RenderError('HyperFrames transition render failed: ' + (result.stdout + result.stderr)[-4000:])
    verify_video(video, total, False)
    assembled = output / 'transitioned.mp4'
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', video]
    if has_audio:
        args += ['-i', output / 'unburned.mp4', '-map', '0:v:0', '-map', '1:a:0', '-c:a', 'copy']
    else:
        args += ['-map', '0:v:0', '-an']
    args += ['-c:v', 'copy', '-movflags', '+faststart', assembled]
    command(args)
    verify_video(assembled, total, has_audio)
    assembled.replace(output / 'unburned.mp4')
