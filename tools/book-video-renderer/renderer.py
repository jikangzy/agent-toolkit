#!/usr/bin/env python3
"""Offline storyboard renderer. Source content is immutable; media is placeholder-only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Protocol

from jsonschema import Draft202012Validator
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'schemas/book-video/storyboard.schema.json'
VERSION = 'mvp-1'
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
    fallback = 'No Chinese TTS configured: video has NO audio track; this is not real narration.'

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        return None


class RecordedSpeech:
    """Adapter for caller-provided real narration WAVs; does not claim to synthesize."""
    fallback = None

    def __init__(self, directory, scenes):
        self.directory = Path(directory).resolve()
        self.files = {s['id']: self.directory / (s['id'] + '.wav') for s in scenes}
        missing = [str(p) for p in self.files.values() if not p.is_file()]
        if missing:
            raise RenderError('Missing real narration WAV files: ' + ', '.join(missing))
        self.cache_key = fingerprint({k: digest(p) for k, p in self.files.items()})

    def synthesize(self, scene_id, narration, voice, duration, workdir):
        path = self.files[scene_id]
        metadata = probe(path)
        if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
            raise RenderError(f'{scene_id}: speech file contains no audio')
        if float(metadata['format']['duration']) > duration + .001:
            raise RenderError(f'{scene_id}: speech exceeds scene duration; refusing to truncate narration')
        return path


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
    for size in range(58, 23, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap(scene['onscreen_text'], font, WIDTH-240)
        if len(lines) * (size+22) <= 650:
            break
    else:
        raise RenderError('onscreen_text too long to fit without truncation')
    y = 730 - len(lines) * (size+22) // 2
    for line in lines:
        draw.text(((WIDTH-font.getlength(line))/2, y), line, font=font, fill='#fff4db')
        y += size+22
    draw.text((100, 1620), '程序生成占位画面 · 非真实素材', font=label_font, fill='#b8c7d6')
    image.save(path)


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


def encode_scene(scene, data, font, work, provider):
    image, clip = work/'visual.png', work/'clip.mp4'
    duration = frame_count(scene) / FPS
    placeholder(scene, font, image)
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


def render(source, output, font=None, attempts=3, provider=None, speech_dir=None):
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
        for tool in ('ffmpeg', 'ffprobe'):
            if not shutil.which(tool):
                raise RenderError(f'Missing executable: {tool}')
        text = '程序生成占位画面非真实素材' + ''.join(s['onscreen_text'] + s['narration'] for s in data['scenes'])
        font_path = find_font(font, text)
        provider = provider or (RecordedSpeech(speech_dir, data['scenes']) if speech_dir else NoTTS())
        manifest.update(storyboard_sha256=source_hash, scene_order=[s['id'] for s in data['scenes']],
                        font=str(font_path), tts_provider=type(provider).__name__,
                        speech_status='fallback_no_audio' if isinstance(provider, NoTTS) else 'provided_audio')
        manifest['fallbacks'] = ['All visual types use program-generated placeholders with a gentle push-in.',
                                 'Subtitles use scene-proportional timing, not speech alignment.',
                                 'Transitions use cuts; requested transitions are recorded per scene.']
        if provider.fallback:
            manifest['fallbacks'].append(provider.fallback)
        if data.get('music', {}).get('enabled'):
            manifest['fallbacks'].append('Requested background music omitted; no music provider configured.')
        (output/'subtitles.srt').write_text(subtitles(data), encoding='utf-8')
        scenes_dir, cache = output/'scenes', output/'cache'
        scenes_dir.mkdir(exist_ok=True)
        cache.mkdir(exist_ok=True)
        settings = {'version': VERSION, 'implementation': digest(Path(__file__)), 'font': digest(font_path),
                    'tts': provider.cache_key, 'voice': data['voice'], 'ffmpeg': command(['ffmpeg', '-version']).splitlines()[0]}
        clips, audio_flags = [], []
        for scene in data['scenes']:
            entry = {'id': scene['id'], 'status': 'pending', 'attempts': 0, 'errors': [],
                     'visual_type': scene['visual']['type'], 'placeholder': True,
                     'motion_requested': scene['visual'].get('motion'), 'transition_requested': scene.get('transition', 'cut'),
                     'narration': scene['narration'], 'onscreen_text': scene['onscreen_text']}
            manifest['scenes'].append(entry)
            save_json(manifest_path, manifest)
            work = cache / fingerprint([scene, settings])
            work.mkdir(exist_ok=True)
            cached, meta = work/'clip.mp4', work/'complete.json'
            def failure(attempt, error):
                entry.update(status='retrying', attempts=attempt)
                entry['errors'].append(error)
                save_json(manifest_path, manifest)
            def produce():
                entry['attempts'] += 1
                clip, audio = encode_scene(scene, data, font_path, work, provider)
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
        manifest['speech_status'] = 'provided_audio' if audio_flags[0] else 'fallback_no_audio'
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
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '1', '-i', 'concat.txt',
               '-vf', f"subtitles=subtitles.srt:fontsdir=fonts:force_style='FontName={family},FontSize=8,MarginV=24,Outline=1'",
               '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p', '-threads', '2']
        cmd += ['-c:a', 'aac'] if audio_flags[0] else ['-an']
        cmd += ['-movflags', '+faststart', final_temp.name]
        def assemble():
            # cwd is explicit; no process-global directory mutation.
            result = subprocess.run([str(a) for a in cmd], cwd=output, capture_output=True, text=True, timeout=1800)
            if result.returncode:
                raise RenderError('Final assembly failed: ' + result.stderr[-4000:])
            return verify_video(final_temp, sum(frame_count(s)/FPS for s in data['scenes']), audio_flags[0])
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
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--tts-audio-dir', type=Path, help='Real narration WAV files named scene_001.wav, etc.')
    args = parser.parse_args()
    try:
        result = render(args.storyboard, args.output, args.font, args.attempts, speech_dir=args.tts_audio_dir)
        print(json.dumps({'status': result['status'], 'fallbacks': result['fallbacks'], 'qc': result['qc']}, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f'Render failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
