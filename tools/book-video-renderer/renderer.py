#!/usr/bin/env python3
"""Offline storyboard renderer. Source content is immutable; media is placeholder-only."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Protocol

from jsonschema import Draft202012Validator
from PIL import Image, ImageDraw, ImageFont, ImageOps
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'schemas/book-video/storyboard.schema.json'
VERSION = 'mvp-3'
WIDTH, HEIGHT, FPS = 1080, 1920, 30


class RenderError(RuntimeError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save_json(path: Path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def command(args, timeout=900):
    try:
        result = subprocess.run([str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RenderError(str(exc)) from exc
    if result.returncode:
        raise RenderError(f'{args[0]} exited {result.returncode}: {result.stderr[-4000:]}')
    return result.stdout


def probe(path):
    return json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))


def load_storyboard(path: Path, schema: Path = SCHEMA):
    data = json.loads(path.read_text(encoding='utf-8'))
    validator = Draft202012Validator(json.loads(schema.read_text(encoding='utf-8')))
    errors = sorted(validator.iter_errors(data), key=lambda e: str(list(e.path)))
    if errors:
        raise RenderError('Invalid storyboard: ' + '; '.join(f'{list(e.path)}: {e.message}' for e in errors))
    ids = [s['id'] for s in data['scenes']]
    if len(ids) != len(set(ids)):
        raise RenderError('Duplicate scene IDs')
    fmt = data['format']
    if (fmt['resolution'], fmt['aspect_ratio'], fmt.get('fps', FPS)) != ('1080x1920', '9:16', FPS):
        raise RenderError('MVP requires 1080x1920, 9:16, 30 fps')
    duration = sum(frame_count(s) / FPS for s in data['scenes'])
    if abs(duration - fmt['target_duration_seconds']) > fmt['target_duration_seconds'] * .08:
        raise RenderError('Scene duration sum differs from target by more than 8%; input will not be rewritten')
    return data


def frame_count(scene):
    return math.floor(scene['duration_seconds'] * FPS + .5)


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
        r'(?m)^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*def resolve_music(data, music_file=None, volume_override=None):
    """Validate an optional local music track; never synthesize or download music."""
    music = data.get('music', {})
    enabled = music.get('enabled', True)
    if music_file is None:
        if volume_override is not None:
            raise RenderError('--music-volume-db requires --music-file')
        return None, None
    if not enabled:
        raise RenderError('--music-file was supplied but storyboard music.enabled is false')
    path = Path(music_file).expanduser().resolve()
    if not path.is_file():
        raise RenderError(f'Background music file does not exist: {path}')
    metadata = probe(path)
    if not any(stream.get('codec_type') == 'audio' for stream in metadata.get('streams', [])):
        raise RenderError(f'Background music file contains no audio stream: {path}')
    try:
        volume_db = float(volume_override if volume_override is not None else music.get('volume_db', -24))
    except (TypeError, ValueError) as exc:
        raise RenderError('Background music volume must be a number between -60 and 0 dB') from exc
    if not math.isfinite(volume_db) or not -60 <= volume_db <= 0:
        raise RenderError('Background music volume must be between -60 and 0 dB')
    return path, volume_db


class TTSProvider(Protocol):
    """Replace with a local/remote synthesizer; pass narration verbatim.

    Return a real speech file or None. cache_key must change whenever voice,
    configuration, implementation or source audio changes. Never silently fake speech.
    """
    cache_key: str
    fallback: str | None

    def synthesize(self, scene_id: str, narration: str, voice: dict, duration: float, workdir: Path) -> Path | None: ...


class NoTTS:
    cache_key = 'no-tts-v1'
    speech_status = 'fallback_no_audio'
    fallback = 'No Chinese TTS configured: video has NO audio track; this is not real narration.'

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        return None


class RecordedSpeech:
    """Adapter for caller-provided real narration WAVs; does not claim to synthesize."""
    fallback = None
    speech_status = 'provided_audio'

    def __init__(self, directory, scenes, provider_name=None, voice_id=None):
        self.directory = Path(directory).resolve()
        self.files = {s['id']: self.directory / (s['id'] + '.wav') for s in scenes}
        missing = [str(p) for p in self.files.values() if not p.is_file()]
        if missing:
            raise RenderError('Missing real narration WAV files: ' + ', '.join(missing))
        self.provider_name = provider_name or 'RecordedSpeech'
        self.voice_id = voice_id
        self.speech_status = 'generated_audio' if provider_name else 'provided_audio'
        if provider_name and provider_name.lower() in ('edge-tts', 'edgetts'):
            self.provider_notice = (
                'Narration was pre-synthesized through the external Edge TTS service; '
                'internet access was required and narration text was sent to that service.'
            )
        elif provider_name:
            self.provider_notice = f'Narration WAV files were pre-synthesized by provider: {provider_name}.'
        else:
            self.provider_notice = None
        self.cache_key = fingerprint({
            'provider': self.provider_name,
            'voice_id': self.voice_id,
            'files': {k: digest(p) for k, p in self.files.items()},
        })

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        path = self.files[scene_id]
        metadata = probe(path)
        if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
            raise RenderError(f'{scene_id}: speech file contains no audio')
        if float(metadata['format']['duration']) > duration + .001:
            raise RenderError(f'{scene_id}: speech exceeds scene duration; refusing to truncate narration')
        return path


class EdgeTTS:
    """Optional online Chinese speech synthesis through the edge-tts package.

    This calls an external Microsoft Edge online TTS service. It is not offline,
    has no availability guarantee, and should be replaceable by another provider.
    """
    fallback = None
    speech_status = 'generated_audio'
    provider_notice = (
        'Speech generated through the external Edge TTS service; internet access is required '
        'and service availability/voice behavior may change.'
    )

    def __init__(self, voice_id=None):
        try:
            import edge_tts
        except ImportError as exc:
            raise RenderError(
                'Edge TTS is optional. Install it with: '
                'python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt'
            ) from exc
        self.edge_tts = edge_tts
        self.voice_id = voice_id or 'zh-CN-YunxiNeural'
        self.cache_key = fingerprint({
            'provider': 'edge-tts',
            'package_version': getattr(edge_tts, '__version__', 'unknown'),
            'voice_id': self.voice_id,
        })

    @staticmethod
    def rate_for(voice):
        speed = float(voice.get('speed', 1.0))
        if not 0.5 <= speed <= 2.0:
            raise RenderError('voice.speed for Edge TTS must be between 0.5 and 2.0')
        return f'{round((speed - 1.0) * 100):+d}%'

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        output = workdir / f'{scene_id}.edge-tts.mp3'
        if output.exists():
            output.unlink()
        rate = self.rate_for(voice)

        async def save_audio():
            communicate = self.edge_tts.Communicate(
                text=narration,
                voice=self.voice_id,
                rate=rate,
            )
            await communicate.save(str(output))

        try:
            asyncio.run(save_audio())
        except Exception as exc:
            raise RenderError(f'{scene_id}: Edge TTS synthesis failed: {exc}') from exc

        if not output.is_file() or output.stat().st_size == 0:
            raise RenderError(f'{scene_id}: Edge TTS returned no audio file')

        metadata = probe(output)
        if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
            raise RenderError(f'{scene_id}: Edge TTS output contains no audio stream')

        audio_duration = float(metadata['format']['duration'])
        if audio_duration > duration:
            # Leave headroom for MP3 encoder delay/padding and frame boundaries.
            # This avoids treating container padding as overlong spoken narration.
            target_duration = max(0.1, duration - 0.15)
            speedup = audio_duration / target_duration
            # Preserve every word. Only allow a modest speed-up; fail rather than
            # silently truncate narration or make speech unnaturally fast.
            if speedup > 1.15:
                raise RenderError(
                    f'{scene_id}: generated speech is {audio_duration:.2f}s but the scene is '
                    f'{duration:.2f}s. Refusing to truncate or excessively speed up narration; '
                    'increase this scene duration or choose a faster voice rate.'
                )
            fitted = workdir / f'{scene_id}.edge-tts-fitted.mp3'
            command([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-i', output, '-filter:a', f'atempo={speedup:.5f}', '-vn', fitted,
            ])
            fitted_info = probe(fitted)
            fitted_duration = float(fitted_info['format']['duration'])
            if fitted_duration > duration:
                raise RenderError(
                    f'{scene_id}: speech still exceeds scene duration after safe tempo adjustment; '
                    'refusing to truncate narration.'
                )
            return fitted

        return output


def wrap(text, font, width):
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for c in paragraph:
            if line and font.getlength(line + c) > width:
                lines.append(line)
                line = ''
            line += c
        lines.append(line)
    return lines


def placeholder(scene, font_path, path):
    palette = {'image': '#172b40', 'video': '#252440', 'broll': '#173d36',
               'title_card': '#252a32', 'quote_card': '#382a30'}
    image = Image.new('RGB', (WIDTH, HEIGHT), palette[scene['visual']['type']])
    draw = ImageDraw.Draw(image)
    for i in range(8):
        x, y = 100 + i*110, 260 + i*145
        draw.ellipse((x-120, y-120, x+180, y+180), outline='#40566a', width=3)
    label_font = ImageFont.truetype(str(font_path), 30)
    draw.text((100, 110), f"{scene['id']} | {scene['visual']['type']}", font=label_font, fill='#b8c7d6')
    draw.text((100, 175), 'MVP PLACEHOLDER', font=label_font, fill='#b8c7d6')
    image = draw_onscreen_text(image, scene, font_path)
    draw = ImageDraw.Draw(image)
    draw.text((100, 1620), '程序生成占位画面 · 非真实素材', font=label_font, fill='#b8c7d6')
    image.save(path)


def draw_onscreen_text(image, scene, font_path):
    draw = ImageDraw.Draw(image)
    for size in range(58, 23, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap(scene['onscreen_text'], font, WIDTH-240)
        if len(lines) * (size+22) <= 650:
            break
    else:
        raise RenderError('onscreen_text too long to fit without truncation')
    y = 730 - len(lines) * (size+22) // 2
    for line in lines:
        draw.text(((WIDTH-font.getlength(line))/2, y), line, font=font,
                  fill='#fff4db', stroke_width=max(2, size//18), stroke_fill='#111820')
        y += size+22
    return image


def find_visual_asset(assets_dir, scene_id):
    if assets_dir is None:
        return None
    extensions = ('.png', '.jpg', '.jpeg', '.webp')
    matches = [Path(assets_dir)/(scene_id + ext) for ext in extensions
               if (Path(assets_dir)/(scene_id + ext)).is_file()]
    if len(matches) > 1:
        raise RenderError(
            f'{scene_id}: multiple visual assets found; keep exactly one of '
            'PNG, JPG, JPEG, or WebP.'
        )
    return matches[0] if matches else None


def normalize_image_asset(source, destination):
    try:
        with Image.open(source) as opened:
            opened = ImageOps.exif_transpose(opened)
            if opened.mode in ('RGBA', 'LA') or 'transparency' in opened.info:
                rgba = opened.convert('RGBA')
                background = Image.new('RGBA', rgba.size, (24, 32, 42, 255))
                background.alpha_composite(rgba)
                image = background.convert('RGB')
            else:
                image = opened.convert('RGB')
            fitted = ImageOps.fit(
                image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )
            fitted.save(destination, format='PNG')
    except Exception as exc:
        raise RenderError(f'Cannot load visual asset {source}: {exc}') from exc


def prepare_visual(scene, font_path, destination, visual_asset=None):
    if visual_asset is None:
        placeholder(scene, font_path, destination)
        return True
    normalize_image_asset(visual_asset, destination)
    with Image.open(destination) as opened:
        image = opened.convert('RGB')
    image = draw_onscreen_text(image, scene, font_path)
    image.save(destination)
    return False


def retry(action, attempts, on_failure):
    for attempt in range(1, attempts+1):
        try:
            return action()
        except Exception as exc:
            on_failure(attempt, str(exc))
            if attempt == attempts:
                raise
            time.sleep(min(.25 * 2**(attempt-1), 2))


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


def encode_scene(scene, data, font, work, provider, visual_asset=None):
    image, clip = work/'visual.png', work/'clip.mp4'
    duration = frame_count(scene) / FPS
    prepare_visual(scene, font, image, visual_asset)
    audio = provider.synthesize(scene['id'], scene['narration'], data['voice'], duration, work)
    # Gentle push-in of the generated card, with large safe margins for text.
    zoom = f"zoompan=z='1.015+0.025*on/{frame_count(scene)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frame_count(scene)}:s=1080x1920:fps=30"
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


def render(source, output, font=None, attempts=3, provider=None, speech_dir=None, tts_provider='none', tts_voice=None, assets_dir=None, speech_provider_name=None, speech_voice=None, music_file=None, music_volume_db=None, subtitle_file=None):
    if attempts < 1 or attempts > 10:
        raise RenderError('attempts must be between 1 and 10')
    source, output = Path(source).resolve(), Path(output).resolve()
    # Never replace an input with an output artifact.
    if source == output or output in source.parents:
        raise RenderError('Output directory must not contain the input storyboard')
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output/'manifest.json'
    manifest = {'version': VERSION, 'status': 'running', 'scenes': [], 'fallbacks': []}
    try:
        source_hash = digest(source)
        data = load_storyboard(source)
        music_path, music_volume_db = resolve_music(data, music_file, music_volume_db)
        music_enabled = data.get('music', {}).get('enabled', True)
        assets_dir = Path(assets_dir).resolve() if assets_dir is not None else None
        subtitle_path = Path(subtitle_file).expanduser().resolve() if subtitle_file is not None else None
        target_duration = sum(frame_count(scene) / FPS for scene in data['scenes'])
        subtitle_info = validate_subtitle_file(subtitle_path, target_duration) if subtitle_path else None
        if assets_dir is not None and not assets_dir.is_dir():
            raise RenderError(f'Visual assets directory does not exist: {assets_dir}')
        visual_assets = {
            scene['id']: find_visual_asset(assets_dir, scene['id'])
            for scene in data['scenes']
        }
        for tool in ('ffmpeg', 'ffprobe'):
            if not shutil.which(tool):
                raise RenderError(f'Missing executable: {tool}')
        text = '程序生成占位画面非真实素材' + ''.join(s['onscreen_text'] + s['narration'] for s in data['scenes'])
        font_path = find_font(font, text)
        if provider is None:
            if speech_dir and tts_provider != 'none':
                raise RenderError('Use either --tts-audio-dir or --tts-provider edge-tts, not both')
            if tts_voice and tts_provider != 'edge-tts':
                raise RenderError('--tts-voice can only be used with --tts-provider edge-tts')
            if (speech_provider_name or speech_voice) and not speech_dir:
                raise RenderError('--tts-audio-provider/--tts-audio-voice require --tts-audio-dir')
            if speech_voice and not speech_provider_name:
                raise RenderError('--tts-audio-voice requires --tts-audio-provider')
            if speech_dir:
                provider = RecordedSpeech(
                    speech_dir, data['scenes'],
                    provider_name=speech_provider_name, voice_id=speech_voice
                )
            elif tts_provider == 'edge-tts':
                provider = EdgeTTS(tts_voice)
            else:
                provider = NoTTS()
        manifest.update(storyboard_sha256=source_hash, scene_order=[s['id'] for s in data['scenes']],
                        font=str(font_path), tts_provider=getattr(provider, 'provider_name', type(provider).__name__),
                        tts_voice=getattr(provider, 'voice_id', None),
                        speech_status=getattr(provider, 'speech_status', 'provided_audio'),
                        visual_assets_supplied=assets_dir is not None)
        missing_assets = [scene['id'] for scene in data['scenes'] if visual_assets[scene['id']] is None]
        manifest['visual_assets'] = {
            scene['id']: ({
                'file': visual_assets[scene['id']].name,
                'sha256': digest(visual_assets[scene['id']])
            } if visual_assets[scene['id']] is not None else None)
            for scene in data['scenes']
        }
        manifest['fallbacks'] = []
        if missing_assets:
            manifest['fallbacks'].append(
                'Program-generated placeholder visuals used for scenes without supplied assets: '
                + ', '.join(missing_assets)
            )
        if subtitle_info:
            manifest['subtitle_alignment'] = {
                'status': 'supplied_srt',
                'file': subtitle_path.name,
                'sha256': subtitle_info['sha256'],
                'cue_count': subtitle_info['cue_count'],
            }
        else:
            manifest['subtitle_alignment'] = {'status': 'scene_proportional'}
            manifest['fallbacks'].append('Subtitles use scene-proportional timing, not speech alignment.')
        manifest['fallbacks'].append('Transitions use cuts; requested transitions are recorded per scene.')
        if provider.fallback:
            manifest['fallbacks'].append(provider.fallback)
        if getattr(provider, 'provider_notice', None):
            manifest.setdefault('provider_notes', []).append(provider.provider_notice)
        if music_path is not None:
            manifest['music'] = {
                'status': 'supplied',
                'file': music_path.name,
                'sha256': digest(music_path),
                'volume_db': music_volume_db,
                'looped_or_trimmed_to_video': True,
            }
        elif music_enabled:
            manifest['music'] = {'status': 'omitted', 'volume_db': data.get('music', {}).get('volume_db', -24)}
            manifest['fallbacks'].append('Requested background music omitted; pass --music-file to mix a local audio track.')
        else:
            manifest['music'] = {'status': 'disabled'}
        if subtitle_path is not None:
            destination_srt = (output/'subtitles.srt').resolve()
            if subtitle_path != destination_srt:
                shutil.copy2(subtitle_path, destination_srt)
        else:
            (output/'subtitles.srt').write_text(subtitles(data), encoding='utf-8')
        scenes_dir, cache = output/'scenes', output/'cache'
        scenes_dir.mkdir(exist_ok=True)
        cache.mkdir(exist_ok=True)
        settings = {'version': VERSION, 'implementation': digest(Path(__file__)), 'font': digest(font_path),
                    'tts': provider.cache_key, 'voice': data['voice'], 'ffmpeg': command(['ffmpeg', '-version']).splitlines()[0],
                    'assets_dir_supplied': assets_dir is not None}
        clips, audio_flags = [], []
        for scene in data['scenes']:
            visual_asset = visual_assets[scene['id']]
            visual_asset_sha = digest(visual_asset) if visual_asset is not None else None
            entry = {'id': scene['id'], 'status': 'pending', 'attempts': 0, 'errors': [],
                     'visual_type': scene['visual']['type'], 'placeholder': visual_asset is None,
                     'visual_asset': visual_asset.name if visual_asset is not None else None,
                     'visual_asset_sha256': visual_asset_sha,
                     'motion_requested': scene['visual'].get('motion'), 'transition_requested': scene.get('transition', 'cut'),
                     'narration': scene['narration'], 'onscreen_text': scene['onscreen_text']}
            manifest['scenes'].append(entry)
            save_json(manifest_path, manifest)
            work = cache / fingerprint([scene, settings, visual_asset_sha or 'placeholder-v1'])
            work.mkdir(exist_ok=True)
            cached, meta = work/'clip.mp4', work/'complete.json'
            def failure(attempt, error):
                entry.update(status='retrying', attempts=attempt)
                entry['errors'].append(error)
                save_json(manifest_path, manifest)
            def produce():
                entry['attempts'] += 1
                clip, audio = encode_scene(scene, data, font_path, work, provider, visual_asset)
                save_json(meta, {'sha256': digest(clip), 'audio': audio})
                return clip, audio
            valid_cache = False
            if cached.is_file() and meta.is_file():
                try:
                    record = json.loads(meta.read_text())
                    if record['sha256'] == digest(cached):
                        verify_video(cached, frame_count(scene)/FPS, record['audio'])
                        valid_cache = True
                except (ValueError, KeyError, RenderError):
                    pass
            if valid_cache:
                clip, audio = cached, record['audio']
                entry['cache_hit'] = True
            else:
                clip, audio = retry(produce, attempts, failure)
                entry['cache_hit'] = False
            destination = scenes_dir/(scene['id'] + '.mp4')
            shutil.copy2(clip, destination)
            clips.append(destination)
            audio_flags.append(audio)
            entry.update(status='complete', sha256=digest(destination), audio=audio)
            save_json(manifest_path, manifest)
        if len(set(audio_flags)) != 1:
            raise RenderError('Provider returned mixed speech/no-speech scenes; refusing incomplete narration')
        manifest['speech_status'] = getattr(provider, 'speech_status', 'provided_audio') if audio_flags[0] else 'fallback_no_audio'
        if not audio_flags[0] and not provider.fallback:
            manifest['fallbacks'].append('Provider returned no audio: output has no real narration.')
        # Fixed internal filenames avoid ffmpeg concat/filter escaping of user paths.
        (output/'concat.txt').write_text(''.join(f"file 'scenes/{p.name}'\n" for p in clips), encoding='utf-8')
        fonts = output/'fonts'
        fonts.mkdir(exist_ok=True)
        shutil.copy2(font_path, fonts/font_path.name)
        with TTFont(str(font_path), fontNumber=0) as ft:
            family = ft['name'].getDebugName(1)
        if not family or any(c in family for c in ",':\\"):
            raise RenderError('Unsupported subtitle font family name')
        final_temp = output/'final.partial.mp4'
        total_duration = sum(frame_count(s)/FPS for s in data['scenes'])
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '1', '-i', 'concat.txt']
        if music_path is not None:
            cmd += ['-stream_loop', '-1', '-i', music_path]
        cmd += ['-vf', f"subtitles=subtitles.srt:fontsdir=fonts:force_style='FontName={family},FontSize=8,MarginV=24,Outline=1'",
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p', '-threads', '2']
        has_final_audio = bool(audio_flags[0] or music_path is not None)
        if music_path is not None:
            music_filter = (
                f"[1:a]volume={music_volume_db}dB,atrim=duration={total_duration:.6f},"
                "asetpts=N/SR/TB[music]"
            )
            if audio_flags[0]:
                filter_complex = (
                    "[0:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo[narration];"
                    + music_filter
                    + ";[narration][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
                )
            else:
                filter_complex = music_filter + ";[music]anull[aout]"
            cmd += ['-filter_complex', filter_complex, '-map', '0:v:0', '-map', '[aout]',
                    '-c:a', 'aac', '-ar', '48000', '-ac', '2']
        elif audio_flags[0]:
            cmd += ['-c:a', 'aac']
        else:
            cmd += ['-an']
        cmd += ['-movflags', '+faststart', final_temp.name]
        def assemble():
            # cwd is explicit; no process-global directory mutation.
            result = subprocess.run([str(a) for a in cmd], cwd=output, capture_output=True, text=True, timeout=1800)
            if result.returncode:
                raise RenderError('Final assembly failed: ' + result.stderr[-4000:])
            return verify_video(final_temp, total_duration, has_final_audio)
        manifest['qc'] = retry(assemble, attempts, lambda n,e: manifest.setdefault('assembly_errors', []).append(e))
        if digest(source) != source_hash:
            raise RenderError('Input storyboard changed during render')
        final_temp.replace(output/'final.mp4')
        manifest.update(status='complete', final_sha256=digest(output/'final.mp4'))
        save_json(manifest_path, manifest)
        return manifest
    except Exception as exc:
        for entry in manifest['scenes']:
            if entry['status'] in ('pending', 'retrying'):
                entry['status'] = 'failed'
        manifest.update(status='failed', error=str(exc))
        save_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('storyboard', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--font', help='CJK font covering all storyboard characters')
    parser.add_argument('--assets-dir', type=Path, help='Optional directory of generated images named <scene_id>.png/.jpg/.jpeg/.webp')
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--tts-audio-dir', type=Path, help='Real narration WAV files named scene_001.wav, etc.')
    parser.add_argument('--tts-audio-provider', help='Provider label for pre-synthesized WAVs, e.g. edge-tts')
    parser.add_argument('--tts-audio-voice', help='Voice ID used to pre-synthesize the WAVs')
    parser.add_argument('--tts-provider', choices=['none', 'edge-tts'], default='none', help='Optional speech synthesis provider; default none keeps rendering offline')
    parser.add_argument('--tts-voice', help='Edge TTS voice ID, e.g. zh-CN-YunxiNeural')
    parser.add_argument('--music-file', type=Path, help='Optional local background music file; storyboard music.enabled must be true')
    parser.add_argument('--music-volume-db', type=float, help='Override storyboard music.volume_db (allowed range: -60 to 0 dB)')
    parser.add_argument('--subtitle-file', type=Path, help='Optional pre-aligned SRT; validated and burned instead of scene-proportional captions')
    args = parser.parse_args()
    try:
        result = render(args.storyboard, args.output, args.font, args.attempts,
                        speech_dir=args.tts_audio_dir, tts_provider=args.tts_provider,
                        tts_voice=args.tts_voice, assets_dir=args.assets_dir,
                        speech_provider_name=args.tts_audio_provider, speech_voice=args.tts_audio_voice,
                        music_file=args.music_file, music_volume_db=args.music_volume_db,
                        subtitle_file=args.subtitle_file)
        print(json.dumps({'status': result['status'], 'speech_status': result.get('speech_status'), 'tts_provider': result.get('tts_provider'), 'music': result.get('music'), 'subtitle_alignment': result.get('subtitle_alignment'), 'fallbacks': result['fallbacks'], 'provider_notes': result.get('provider_notes', []), 'qc': result['qc']}, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f'Render failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

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


def resolve_music(data, music_file=None, volume_override=None):
    """Validate an optional local music track; never synthesize or download music."""
    music = data.get('music', {})
    enabled = music.get('enabled', True)
    if music_file is None:
        if volume_override is not None:
            raise RenderError('--music-volume-db requires --music-file')
        return None, None
    if not enabled:
        raise RenderError('--music-file was supplied but storyboard music.enabled is false')
    path = Path(music_file).expanduser().resolve()
    if not path.is_file():
        raise RenderError(f'Background music file does not exist: {path}')
    metadata = probe(path)
    if not any(stream.get('codec_type') == 'audio' for stream in metadata.get('streams', [])):
        raise RenderError(f'Background music file contains no audio stream: {path}')
    try:
        volume_db = float(volume_override if volume_override is not None else music.get('volume_db', -24))
    except (TypeError, ValueError) as exc:
        raise RenderError('Background music volume must be a number between -60 and 0 dB') from exc
    if not math.isfinite(volume_db) or not -60 <= volume_db <= 0:
        raise RenderError('Background music volume must be between -60 and 0 dB')
    return path, volume_db


class TTSProvider(Protocol):
    """Replace with a local/remote synthesizer; pass narration verbatim.

    Return a real speech file or None. cache_key must change whenever voice,
    configuration, implementation or source audio changes. Never silently fake speech.
    """
    cache_key: str
    fallback: str | None

    def synthesize(self, scene_id: str, narration: str, voice: dict, duration: float, workdir: Path) -> Path | None: ...


class NoTTS:
    cache_key = 'no-tts-v1'
    speech_status = 'fallback_no_audio'
    fallback = 'No Chinese TTS configured: video has NO audio track; this is not real narration.'

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        return None


class RecordedSpeech:
    """Adapter for caller-provided real narration WAVs; does not claim to synthesize."""
    fallback = None
    speech_status = 'provided_audio'

    def __init__(self, directory, scenes, provider_name=None, voice_id=None):
        self.directory = Path(directory).resolve()
        self.files = {s['id']: self.directory / (s['id'] + '.wav') for s in scenes}
        missing = [str(p) for p in self.files.values() if not p.is_file()]
        if missing:
            raise RenderError('Missing real narration WAV files: ' + ', '.join(missing))
        self.provider_name = provider_name or 'RecordedSpeech'
        self.voice_id = voice_id
        self.speech_status = 'generated_audio' if provider_name else 'provided_audio'
        if provider_name and provider_name.lower() in ('edge-tts', 'edgetts'):
            self.provider_notice = (
                'Narration was pre-synthesized through the external Edge TTS service; '
                'internet access was required and narration text was sent to that service.'
            )
        elif provider_name:
            self.provider_notice = f'Narration WAV files were pre-synthesized by provider: {provider_name}.'
        else:
            self.provider_notice = None
        self.cache_key = fingerprint({
            'provider': self.provider_name,
            'voice_id': self.voice_id,
            'files': {k: digest(p) for k, p in self.files.items()},
        })

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        path = self.files[scene_id]
        metadata = probe(path)
        if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
            raise RenderError(f'{scene_id}: speech file contains no audio')
        if float(metadata['format']['duration']) > duration + .001:
            raise RenderError(f'{scene_id}: speech exceeds scene duration; refusing to truncate narration')
        return path


class EdgeTTS:
    """Optional online Chinese speech synthesis through the edge-tts package.

    This calls an external Microsoft Edge online TTS service. It is not offline,
    has no availability guarantee, and should be replaceable by another provider.
    """
    fallback = None
    speech_status = 'generated_audio'
    provider_notice = (
        'Speech generated through the external Edge TTS service; internet access is required '
        'and service availability/voice behavior may change.'
    )

    def __init__(self, voice_id=None):
        try:
            import edge_tts
        except ImportError as exc:
            raise RenderError(
                'Edge TTS is optional. Install it with: '
                'python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt'
            ) from exc
        self.edge_tts = edge_tts
        self.voice_id = voice_id or 'zh-CN-YunxiNeural'
        self.cache_key = fingerprint({
            'provider': 'edge-tts',
            'package_version': getattr(edge_tts, '__version__', 'unknown'),
            'voice_id': self.voice_id,
        })

    @staticmethod
    def rate_for(voice):
        speed = float(voice.get('speed', 1.0))
        if not 0.5 <= speed <= 2.0:
            raise RenderError('voice.speed for Edge TTS must be between 0.5 and 2.0')
        return f'{round((speed - 1.0) * 100):+d}%'

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        output = workdir / f'{scene_id}.edge-tts.mp3'
        if output.exists():
            output.unlink()
        rate = self.rate_for(voice)

        async def save_audio():
            communicate = self.edge_tts.Communicate(
                text=narration,
                voice=self.voice_id,
                rate=rate,
            )
            await communicate.save(str(output))

        try:
            asyncio.run(save_audio())
        except Exception as exc:
            raise RenderError(f'{scene_id}: Edge TTS synthesis failed: {exc}') from exc

        if not output.is_file() or output.stat().st_size == 0:
            raise RenderError(f'{scene_id}: Edge TTS returned no audio file')

        metadata = probe(output)
        if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
            raise RenderError(f'{scene_id}: Edge TTS output contains no audio stream')

        audio_duration = float(metadata['format']['duration'])
        if audio_duration > duration:
            # Leave headroom for MP3 encoder delay/padding and frame boundaries.
            # This avoids treating container padding as overlong spoken narration.
            target_duration = max(0.1, duration - 0.15)
            speedup = audio_duration / target_duration
            # Preserve every word. Only allow a modest speed-up; fail rather than
            # silently truncate narration or make speech unnaturally fast.
            if speedup > 1.15:
                raise RenderError(
                    f'{scene_id}: generated speech is {audio_duration:.2f}s but the scene is '
                    f'{duration:.2f}s. Refusing to truncate or excessively speed up narration; '
                    'increase this scene duration or choose a faster voice rate.'
                )
            fitted = workdir / f'{scene_id}.edge-tts-fitted.mp3'
            command([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-i', output, '-filter:a', f'atempo={speedup:.5f}', '-vn', fitted,
            ])
            fitted_info = probe(fitted)
            fitted_duration = float(fitted_info['format']['duration'])
            if fitted_duration > duration:
                raise RenderError(
                    f'{scene_id}: speech still exceeds scene duration after safe tempo adjustment; '
                    'refusing to truncate narration.'
                )
            return fitted

        return output


def wrap(text, font, width):
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for c in paragraph:
            if line and font.getlength(line + c) > width:
                lines.append(line)
                line = ''
            line += c
        lines.append(line)
    return lines


def placeholder(scene, font_path, path):
    palette = {'image': '#172b40', 'video': '#252440', 'broll': '#173d36',
               'title_card': '#252a32', 'quote_card': '#382a30'}
    image = Image.new('RGB', (WIDTH, HEIGHT), palette[scene['visual']['type']])
    draw = ImageDraw.Draw(image)
    for i in range(8):
        x, y = 100 + i*110, 260 + i*145
        draw.ellipse((x-120, y-120, x+180, y+180), outline='#40566a', width=3)
    label_font = ImageFont.truetype(str(font_path), 30)
    draw.text((100, 110), f"{scene['id']} | {scene['visual']['type']}", font=label_font, fill='#b8c7d6')
    draw.text((100, 175), 'MVP PLACEHOLDER', font=label_font, fill='#b8c7d6')
    image = draw_onscreen_text(image, scene, font_path)
    draw = ImageDraw.Draw(image)
    draw.text((100, 1620), '程序生成占位画面 · 非真实素材', font=label_font, fill='#b8c7d6')
    image.save(path)


def draw_onscreen_text(image, scene, font_path):
    draw = ImageDraw.Draw(image)
    for size in range(58, 23, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap(scene['onscreen_text'], font, WIDTH-240)
        if len(lines) * (size+22) <= 650:
            break
    else:
        raise RenderError('onscreen_text too long to fit without truncation')
    y = 730 - len(lines) * (size+22) // 2
    for line in lines:
        draw.text(((WIDTH-font.getlength(line))/2, y), line, font=font,
                  fill='#fff4db', stroke_width=max(2, size//18), stroke_fill='#111820')
        y += size+22
    return image


def find_visual_asset(assets_dir, scene_id):
    if assets_dir is None:
        return None
    extensions = ('.png', '.jpg', '.jpeg', '.webp')
    matches = [Path(assets_dir)/(scene_id + ext) for ext in extensions
               if (Path(assets_dir)/(scene_id + ext)).is_file()]
    if len(matches) > 1:
        raise RenderError(
            f'{scene_id}: multiple visual assets found; keep exactly one of '
            'PNG, JPG, JPEG, or WebP.'
        )
    return matches[0] if matches else None


def normalize_image_asset(source, destination):
    try:
        with Image.open(source) as opened:
            opened = ImageOps.exif_transpose(opened)
            if opened.mode in ('RGBA', 'LA') or 'transparency' in opened.info:
                rgba = opened.convert('RGBA')
                background = Image.new('RGBA', rgba.size, (24, 32, 42, 255))
                background.alpha_composite(rgba)
                image = background.convert('RGB')
            else:
                image = opened.convert('RGB')
            fitted = ImageOps.fit(
                image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )
            fitted.save(destination, format='PNG')
    except Exception as exc:
        raise RenderError(f'Cannot load visual asset {source}: {exc}') from exc


def prepare_visual(scene, font_path, destination, visual_asset=None):
    if visual_asset is None:
        placeholder(scene, font_path, destination)
        return True
    normalize_image_asset(visual_asset, destination)
    with Image.open(destination) as opened:
        image = opened.convert('RGB')
    image = draw_onscreen_text(image, scene, font_path)
    image.save(destination)
    return False


def retry(action, attempts, on_failure):
    for attempt in range(1, attempts+1):
        try:
            return action()
        except Exception as exc:
            on_failure(attempt, str(exc))
            if attempt == attempts:
                raise
            time.sleep(min(.25 * 2**(attempt-1), 2))


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


def encode_scene(scene, data, font, work, provider, visual_asset=None):
    image, clip = work/'visual.png', work/'clip.mp4'
    duration = frame_count(scene) / FPS
    prepare_visual(scene, font, image, visual_asset)
    audio = provider.synthesize(scene['id'], scene['narration'], data['voice'], duration, work)
    # Gentle push-in of the generated card, with large safe margins for text.
    zoom = f"zoompan=z='1.015+0.025*on/{frame_count(scene)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frame_count(scene)}:s=1080x1920:fps=30"
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


def render(source, output, font=None, attempts=3, provider=None, speech_dir=None, tts_provider='none', tts_voice=None, assets_dir=None, speech_provider_name=None, speech_voice=None, music_file=None, music_volume_db=None):
    if attempts < 1 or attempts > 10:
        raise RenderError('attempts must be between 1 and 10')
    source, output = Path(source).resolve(), Path(output).resolve()
    # Never replace an input with an output artifact.
    if source == output or output in source.parents:
        raise RenderError('Output directory must not contain the input storyboard')
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output/'manifest.json'
    manifest = {'version': VERSION, 'status': 'running', 'scenes': [], 'fallbacks': []}
    try:
        source_hash = digest(source)
        data = load_storyboard(source)
        music_path, music_volume_db = resolve_music(data, music_file, music_volume_db)
        music_enabled = data.get('music', {}).get('enabled', True)
        assets_dir = Path(assets_dir).resolve() if assets_dir is not None else None
        if assets_dir is not None and not assets_dir.is_dir():
            raise RenderError(f'Visual assets directory does not exist: {assets_dir}')
        visual_assets = {
            scene['id']: find_visual_asset(assets_dir, scene['id'])
            for scene in data['scenes']
        }
        for tool in ('ffmpeg', 'ffprobe'):
            if not shutil.which(tool):
                raise RenderError(f'Missing executable: {tool}')
        text = '程序生成占位画面非真实素材' + ''.join(s['onscreen_text'] + s['narration'] for s in data['scenes'])
        font_path = find_font(font, text)
        if provider is None:
            if speech_dir and tts_provider != 'none':
                raise RenderError('Use either --tts-audio-dir or --tts-provider edge-tts, not both')
            if tts_voice and tts_provider != 'edge-tts':
                raise RenderError('--tts-voice can only be used with --tts-provider edge-tts')
            if (speech_provider_name or speech_voice) and not speech_dir:
                raise RenderError('--tts-audio-provider/--tts-audio-voice require --tts-audio-dir')
            if speech_voice and not speech_provider_name:
                raise RenderError('--tts-audio-voice requires --tts-audio-provider')
            if speech_dir:
                provider = RecordedSpeech(
                    speech_dir, data['scenes'],
                    provider_name=speech_provider_name, voice_id=speech_voice
                )
            elif tts_provider == 'edge-tts':
                provider = EdgeTTS(tts_voice)
            else:
                provider = NoTTS()
        manifest.update(storyboard_sha256=source_hash, scene_order=[s['id'] for s in data['scenes']],
                        font=str(font_path), tts_provider=getattr(provider, 'provider_name', type(provider).__name__),
                        tts_voice=getattr(provider, 'voice_id', None),
                        speech_status=getattr(provider, 'speech_status', 'provided_audio'),
                        visual_assets_supplied=assets_dir is not None)
        missing_assets = [scene['id'] for scene in data['scenes'] if visual_assets[scene['id']] is None]
        manifest['visual_assets'] = {
            scene['id']: ({
                'file': visual_assets[scene['id']].name,
                'sha256': digest(visual_assets[scene['id']])
            } if visual_assets[scene['id']] is not None else None)
            for scene in data['scenes']
        }
        manifest['fallbacks'] = []
        if missing_assets:
            manifest['fallbacks'].append(
                'Program-generated placeholder visuals used for scenes without supplied assets: '
                + ', '.join(missing_assets)
            )
        manifest['fallbacks'].extend([
            'Subtitles use scene-proportional timing, not speech alignment.',
            'Transitions use cuts; requested transitions are recorded per scene.'
        ])
        if provider.fallback:
            manifest['fallbacks'].append(provider.fallback)
        if getattr(provider, 'provider_notice', None):
            manifest.setdefault('provider_notes', []).append(provider.provider_notice)
        if music_path is not None:
            manifest['music'] = {
                'status': 'supplied',
                'file': music_path.name,
                'sha256': digest(music_path),
                'volume_db': music_volume_db,
                'looped_or_trimmed_to_video': True,
            }
        elif music_enabled:
            manifest['music'] = {'status': 'omitted', 'volume_db': data.get('music', {}).get('volume_db', -24)}
            manifest['fallbacks'].append('Requested background music omitted; pass --music-file to mix a local audio track.')
        else:
            manifest['music'] = {'status': 'disabled'}
        (output/'subtitles.srt').write_text(subtitles(data), encoding='utf-8')
        scenes_dir, cache = output/'scenes', output/'cache'
        scenes_dir.mkdir(exist_ok=True)
        cache.mkdir(exist_ok=True)
        settings = {'version': VERSION, 'implementation': digest(Path(__file__)), 'font': digest(font_path),
                    'tts': provider.cache_key, 'voice': data['voice'], 'ffmpeg': command(['ffmpeg', '-version']).splitlines()[0],
                    'assets_dir_supplied': assets_dir is not None}
        clips, audio_flags = [], []
        for scene in data['scenes']:
            visual_asset = visual_assets[scene['id']]
            visual_asset_sha = digest(visual_asset) if visual_asset is not None else None
            entry = {'id': scene['id'], 'status': 'pending', 'attempts': 0, 'errors': [],
                     'visual_type': scene['visual']['type'], 'placeholder': visual_asset is None,
                     'visual_asset': visual_asset.name if visual_asset is not None else None,
                     'visual_asset_sha256': visual_asset_sha,
                     'motion_requested': scene['visual'].get('motion'), 'transition_requested': scene.get('transition', 'cut'),
                     'narration': scene['narration'], 'onscreen_text': scene['onscreen_text']}
            manifest['scenes'].append(entry)
            save_json(manifest_path, manifest)
            work = cache / fingerprint([scene, settings, visual_asset_sha or 'placeholder-v1'])
            work.mkdir(exist_ok=True)
            cached, meta = work/'clip.mp4', work/'complete.json'
            def failure(attempt, error):
                entry.update(status='retrying', attempts=attempt)
                entry['errors'].append(error)
                save_json(manifest_path, manifest)
            def produce():
                entry['attempts'] += 1
                clip, audio = encode_scene(scene, data, font_path, work, provider, visual_asset)
                save_json(meta, {'sha256': digest(clip), 'audio': audio})
                return clip, audio
            valid_cache = False
            if cached.is_file() and meta.is_file():
                try:
                    record = json.loads(meta.read_text())
                    if record['sha256'] == digest(cached):
                        verify_video(cached, frame_count(scene)/FPS, record['audio'])
                        valid_cache = True
                except (ValueError, KeyError, RenderError):
                    pass
            if valid_cache:
                clip, audio = cached, record['audio']
                entry['cache_hit'] = True
            else:
                clip, audio = retry(produce, attempts, failure)
                entry['cache_hit'] = False
            destination = scenes_dir/(scene['id'] + '.mp4')
            shutil.copy2(clip, destination)
            clips.append(destination)
            audio_flags.append(audio)
            entry.update(status='complete', sha256=digest(destination), audio=audio)
            save_json(manifest_path, manifest)
        if len(set(audio_flags)) != 1:
            raise RenderError('Provider returned mixed speech/no-speech scenes; refusing incomplete narration')
        manifest['speech_status'] = getattr(provider, 'speech_status', 'provided_audio') if audio_flags[0] else 'fallback_no_audio'
        if not audio_flags[0] and not provider.fallback:
            manifest['fallbacks'].append('Provider returned no audio: output has no real narration.')
        # Fixed internal filenames avoid ffmpeg concat/filter escaping of user paths.
        (output/'concat.txt').write_text(''.join(f"file 'scenes/{p.name}'\n" for p in clips), encoding='utf-8')
        fonts = output/'fonts'
        fonts.mkdir(exist_ok=True)
        shutil.copy2(font_path, fonts/font_path.name)
        with TTFont(str(font_path), fontNumber=0) as ft:
            family = ft['name'].getDebugName(1)
        if not family or any(c in family for c in ",':\\"):
            raise RenderError('Unsupported subtitle font family name')
        final_temp = output/'final.partial.mp4'
        total_duration = sum(frame_count(s)/FPS for s in data['scenes'])
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '1', '-i', 'concat.txt']
        if music_path is not None:
            cmd += ['-stream_loop', '-1', '-i', music_path]
        cmd += ['-vf', f"subtitles=subtitles.srt:fontsdir=fonts:force_style='FontName={family},FontSize=8,MarginV=24,Outline=1'",
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p', '-threads', '2']
        has_final_audio = bool(audio_flags[0] or music_path is not None)
        if music_path is not None:
            music_filter = (
                f"[1:a]volume={music_volume_db}dB,atrim=duration={total_duration:.6f},"
                "asetpts=N/SR/TB[music]"
            )
            if audio_flags[0]:
                filter_complex = (
                    "[0:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo[narration];"
                    + music_filter
                    + ";[narration][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
                )
            else:
                filter_complex = music_filter + ";[music]anull[aout]"
            cmd += ['-filter_complex', filter_complex, '-map', '0:v:0', '-map', '[aout]',
                    '-c:a', 'aac', '-ar', '48000', '-ac', '2']
        elif audio_flags[0]:
            cmd += ['-c:a', 'aac']
        else:
            cmd += ['-an']
        cmd += ['-movflags', '+faststart', final_temp.name]
        def assemble():
            # cwd is explicit; no process-global directory mutation.
            result = subprocess.run([str(a) for a in cmd], cwd=output, capture_output=True, text=True, timeout=1800)
            if result.returncode:
                raise RenderError('Final assembly failed: ' + result.stderr[-4000:])
            return verify_video(final_temp, total_duration, has_final_audio)
        manifest['qc'] = retry(assemble, attempts, lambda n,e: manifest.setdefault('assembly_errors', []).append(e))
        if digest(source) != source_hash:
            raise RenderError('Input storyboard changed during render')
        final_temp.replace(output/'final.mp4')
        manifest.update(status='complete', final_sha256=digest(output/'final.mp4'))
        save_json(manifest_path, manifest)
        return manifest
    except Exception as exc:
        for entry in manifest['scenes']:
            if entry['status'] in ('pending', 'retrying'):
                entry['status'] = 'failed'
        manifest.update(status='failed', error=str(exc))
        save_json(manifest_path, manifest)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('storyboard', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--font', help='CJK font covering all storyboard characters')
    parser.add_argument('--assets-dir', type=Path, help='Optional directory of generated images named <scene_id>.png/.jpg/.jpeg/.webp')
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--tts-audio-dir', type=Path, help='Real narration WAV files named scene_001.wav, etc.')
    parser.add_argument('--tts-audio-provider', help='Provider label for pre-synthesized WAVs, e.g. edge-tts')
    parser.add_argument('--tts-audio-voice', help='Voice ID used to pre-synthesize the WAVs')
    parser.add_argument('--tts-provider', choices=['none', 'edge-tts'], default='none', help='Optional speech synthesis provider; default none keeps rendering offline')
    parser.add_argument('--tts-voice', help='Edge TTS voice ID, e.g. zh-CN-YunxiNeural')
    parser.add_argument('--music-file', type=Path, help='Optional local background music file; storyboard music.enabled must be true')
    parser.add_argument('--music-volume-db', type=float, help='Override storyboard music.volume_db (allowed range: -60 to 0 dB)')
    args = parser.parse_args()
    try:
        result = render(args.storyboard, args.output, args.font, args.attempts,
                        speech_dir=args.tts_audio_dir, tts_provider=args.tts_provider,
                        tts_voice=args.tts_voice, assets_dir=args.assets_dir,
                        speech_provider_name=args.tts_audio_provider, speech_voice=args.tts_audio_voice,
                        music_file=args.music_file, music_volume_db=args.music_volume_db)
        print(json.dumps({'status': result['status'], 'speech_status': result.get('speech_status'), 'tts_provider': result.get('tts_provider'), 'music': result.get('music'), 'fallbacks': result['fallbacks'], 'provider_notes': result.get('provider_notes', []), 'qc': result['qc']}, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f'Render failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
