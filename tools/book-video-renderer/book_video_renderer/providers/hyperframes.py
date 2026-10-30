"""Local HyperFrames scene renderer; no network video or speech service."""
from __future__ import annotations

import html
import json
import shutil
import subprocess
from pathlib import Path

from ..manifest import digest, fingerprint, save_json
from ..models import RenderError
from ..qc import verify_video
from .image import find_visual_asset


class HyperFramesVideoProvider:
    provider_name = 'hyperframes'
    text_in_video = True

    def __init__(self, assets_dir, executable, gsap_path):
        self.assets_dir = Path(assets_dir).resolve()
        self.executable = str(Path(executable).resolve())
        self.gsap_path = Path(gsap_path).resolve()
        if not Path(self.executable).is_file() or not self.gsap_path.is_file():
            raise RenderError('HyperFrames executable and local GSAP file are required')
        result = subprocess.run([self.executable, '--version'], capture_output=True, text=True, check=True)
        self.version = result.stdout.strip()
        self.cache_key = fingerprint(['hyperframes-v1', self.version, digest(self.gsap_path), digest(Path(__file__))])
        self.scene_records = {}

    def get_or_generate_video(self, scene, duration_seconds, workdir):
        image = find_visual_asset(self.assets_dir, scene['id'])
        if image is None:
            raise RenderError(f"Missing required image for {scene['id']}")
        key = fingerprint([self.cache_key, scene, duration_seconds, digest(image)])
        workdir = Path(workdir) / key
        workdir.mkdir(parents=True, exist_ok=True)
        output, meta = workdir / 'scene.mp4', workdir / 'complete.json'
        hit = False
        if output.is_file() and meta.is_file():
            try:
                record = json.loads(meta.read_text())
                hit = record['sha256'] == digest(output) and bool(verify_video(output, duration_seconds, False))
            except (ValueError, KeyError, OSError, RenderError):
                pass
        if not hit:
            shutil.copyfile(image, workdir / 'image.png')
            shutil.copyfile(self.gsap_path, workdir / 'gsap.min.js')
            (workdir / 'index.html').write_text(composition(scene, duration_seconds), encoding='utf-8')
            result = subprocess.run([self.executable, 'render', str(workdir), '--output', str(output), '--fps', '30', '--quality', 'standard', '--workers', '1'], capture_output=True, text=True, timeout=3600)
            if result.returncode:
                raise RenderError('HyperFrames render failed: ' + (result.stdout + result.stderr)[-4000:])
            verify_video(output, duration_seconds, False)
            save_json(meta, {'sha256': digest(output)})
        self.scene_records[scene['id']] = {'origin': 'local_hyperframes', 'provider': self.provider_name,
            'version': self.version, 'source_image': str(image), 'source_sha256': digest(image),
            'output_path': str(output), 'sha256': digest(output), 'cache_hit': hit, 'composition': str(workdir / 'index.html')}
        return output



def camera_tween(scene, duration):
    """Map the storyboard motion hint to a deterministic GSAP camera animation."""
    motion = str(scene.get('visual', {}).get('motion', '')).strip().lower()
    if 'zoom-out' in motion or 'zoom out' in motion:
        return f'tl.fromTo(".picture", {{scale:1.18}}, {{scale:1.04,duration:{duration},ease:"sine.inOut"}}, 0);'
    if 'pan' in motion:
        if 'right' in motion:
            return f'tl.fromTo(".picture", {{scale:1.12,x:-65}}, {{scale:1.12,x:65,duration:{duration},ease:"sine.inOut"}}, 0);'
        if 'left' in motion:
            return f'tl.fromTo(".picture", {{scale:1.12,x:65}}, {{scale:1.12,x:-65,duration:{duration},ease:"sine.inOut"}}, 0);'
        if 'down' in motion:
            return f'tl.fromTo(".picture", {{scale:1.12,y:-65}}, {{scale:1.12,y:65,duration:{duration},ease:"sine.inOut"}}, 0);'
        if 'up' in motion:
            return f'tl.fromTo(".picture", {{scale:1.12,y:65}}, {{scale:1.12,y:-65,duration:{duration},ease:"sine.inOut"}}, 0);'
    if 'fade-in' in motion or 'fade in' in motion:
        fade_duration = min(float(duration), 1.2)
        return f'tl.fromTo(".picture", {{opacity:0}}, {{opacity:1,duration:{fade_duration},ease:"power1.out"}}, 0);'
    if any(token in motion for token in ('zoom-in', 'zoom in', 'push-in', 'push in', 'forward')):
        return f'tl.fromTo(".picture", {{scale:1.04}}, {{scale:1.18,duration:{duration},ease:"sine.inOut"}}, 0);'
    return f'tl.fromTo(".picture", {{scale:1.04}}, {{scale:1.18,duration:{duration},ease:"sine.inOut"}}, 0);'


def composition(scene, duration):
    """Create a deterministic scene composition with untouched display text."""
    text = scene['onscreen_text']
    keyword = '财富与幸福' if scene['id'] == 'scene_002' else '财富'
    before, found, after = text.partition(keyword)
    title = (html.escape(before) + '<span class="keyword">' + html.escape(found) + '</span>' + html.escape(after)) if found else html.escape(text)
    ident = html.escape(scene['id'], quote=True)
    move = camera_tween(scene, duration)
    second = scene['id'] == 'scene_003'
    accent = '#b8d6df' if second else '#edc48a'
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:"Noto Sans CJK SC";src:local("Noto Sans CJK SC")}} *{{box-sizing:border-box}} body{{margin:0}} .root{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#101a20;color:#fff;font-family:"Noto Sans CJK SC",sans-serif}}
.picture{{position:absolute;inset:0;background:url('image.png') center/cover;will-change:transform,opacity}} .shade{{position:absolute;inset:0;background:linear-gradient(0deg,rgba(8,13,20,.87),transparent 68%)}}
.content{{position:relative;width:100%;height:100%;display:flex;flex-direction:column;justify-content:flex-end;padding:120px 90px 270px;gap:30px}} .marker{{width:125px;height:8px;background:{accent}}} .title{{font-size:68px;line-height:1.45;font-weight:700;text-shadow:0 3px 12px #000;max-width:900px}} .label{{color:{accent};font-size:30px;letter-spacing:4px}} .keyword{{color:#fff;display:inline}}
</style></head><body><div class="root" id="root" data-composition-id="{ident}" data-start="0" data-duration="{duration}" data-width="1080" data-height="1920"><div class="picture"></div><div class="shade"></div><div class="content"><div class="label">纳瓦尔宝典 · 读书分享</div><div class="marker"></div><div class="title">{title}</div></div></div><script src="gsap.min.js"></script><script>window.__timelines=window.__timelines||{{}};const tl=gsap.timeline({{paused:true}});{move} tl.from('.label',{{y:25,opacity:0,duration:.7,ease:'power2.out'}},.2);tl.from('.marker',{{scaleX:0,transformOrigin:'left',duration:.8,ease:'expo.out'}},.4);tl.from('.title',{{y:55,opacity:0,duration:1,ease:'power3.out'}},.6);tl.to('.keyword',{{color:'{accent}',duration:.8,ease:'sine.inOut'}},2.2);window.__timelines[{json.dumps(scene['id'])}]=tl;</script></body></html>'''
