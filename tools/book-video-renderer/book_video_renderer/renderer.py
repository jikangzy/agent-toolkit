from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from fontTools.ttLib import TTFont
from .models import VERSION, FPS, RenderError, frame_count, total_duration as planned_duration
from .manifest import digest, fingerprint, save_json, retry
from .ffmpeg import command
from .validator import load_storyboard
from .fonts import find_font
from .subtitle import subtitles, validate_subtitle_file
from .qc import verify_video
from .scene import encode_scene
from .providers.image import find_visual_asset
from .providers.video import SuppliedVideoProvider, validate_video_asset
from .providers.music import resolve_music
from .providers.tts import NoTTS, RecordedSpeech, EdgeTTS

def render(source, output, font=None, attempts=3, provider=None, speech_dir=None, tts_provider='none', tts_voice=None, assets_dir=None, speech_provider_name=None, speech_voice=None, music_file=None, music_volume_db=None, subtitle_file=None, video_assets_dir=None, require_video_assets=False, video_provider=None):
    if attempts < 1 or attempts > 10:
        raise RenderError('attempts must be between 1 and 10')
    source, output = Path(source).resolve(), Path(output).resolve()
    # Never replace an input with an output artifact.
    if source == output or output in source.parents:
        raise RenderError('Output directory must not contain the input storyboard')
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output/'manifest.json'
    previous = {}
    if manifest_path.is_file():
        try:
            previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
    manifest = {'version': VERSION, 'renderer_version': VERSION, 'status': 'running',
                'overall_status': 'rendering', 'storyboard_path': str(source),
                'final_video_path': None, 'scenes': [], 'fallbacks': []}
    try:
        source_hash = digest(source)
        manifest.update(storyboard_sha256=source_hash, storyboard_hash=source_hash)
        data = load_storyboard(source)
        manifest.update(
                        target_duration_seconds=data['format']['target_duration_seconds'],
                        total_duration_seconds=planned_duration(data))
        # Include all scenes even if a dependency or an earlier scene fails.
        manifest['scenes'] = [dict(id=scene['id'], status='pending', input_hash=None,
                                   visual_asset_path=None, audio_path=None, scene_video_path=None,
                                   duration=frame_count(scene)/FPS, error=None, retry_count=0)
                              for scene in data['scenes']]
        music_path, music_volume_db = resolve_music(data, music_file, music_volume_db)
        music_enabled = data.get('music', {}).get('enabled', True)
        assets_dir = Path(assets_dir).resolve() if assets_dir is not None else None
        subtitle_path = Path(subtitle_file).expanduser().resolve() if subtitle_file is not None else None
        target_duration = sum(frame_count(scene) / FPS for scene in data['scenes'])
        subtitle_info = validate_subtitle_file(subtitle_path, target_duration) if subtitle_path else None
        if assets_dir is not None and not assets_dir.is_dir():
            raise RenderError(f'Visual assets directory does not exist: {assets_dir}')
        if video_assets_dir is not None:
            video_assets_dir = Path(video_assets_dir).expanduser().resolve()
            if video_provider is not None:
                raise RenderError('Use either --video-assets-dir or a programmatic video_provider, not both')
            video_provider = SuppliedVideoProvider(video_assets_dir)
        if require_video_assets and video_provider is None:
            raise RenderError('--require-video-assets requires --video-assets-dir or a video_provider')
        visual_assets = {
            scene['id']: find_visual_asset(assets_dir, scene['id'])
            for scene in data['scenes']
        }
        for tool in ('ffmpeg', 'ffprobe'):
            if not shutil.which(tool):
                raise RenderError(f'Missing executable: {tool}')
        text = '程序生成占位画面非真实素材' + ''.join(s['onscreen_text'] + s['narration'] for s in data['scenes'])
        try:
            font_path = find_font(font, text)
            manifest['subtitles'] = {'status': 'pending', 'font': str(font_path)}
        except RenderError as exc:
            font_path = None
            manifest['subtitles'] = {'status': 'failed', 'error': str(exc)}
            manifest['fallbacks'].append('Missing font: title overlays and subtitle burn-in unavailable; preserving unburned video and SRT.')
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
        video_assets = {}
        video_asset_info = {}
        if video_provider is not None:
            for scene in data['scenes']:
                # b-roll/video scenes are the explicit dynamic-footage boundary.
                if scene['visual']['type'] not in ('video', 'broll'):
                    video_assets[scene['id']] = None
                    video_asset_info[scene['id']] = None
                    continue
                asset = video_provider.get_or_generate_video(
                    scene, frame_count(scene) / FPS,
                    output/'video-provider-cache'/scene['id']
                )
                if asset is not None:
                    asset = Path(asset).expanduser().resolve()
                    info = validate_video_asset(asset)
                    video_assets[scene['id']] = asset
                    video_asset_info[scene['id']] = info
                else:
                    video_assets[scene['id']] = None
                    video_asset_info[scene['id']] = None
        else:
            video_assets = {scene['id']: None for scene in data['scenes']}
            video_asset_info = {scene['id']: None for scene in data['scenes']}

        missing_required_video = [
            scene['id'] for scene in data['scenes']
            if scene['visual']['type'] in ('video', 'broll')
            and video_assets[scene['id']] is None
        ]
        if require_video_assets and missing_required_video:
            raise RenderError(
                'Missing required video clips for video/broll scenes: '
                + ', '.join(missing_required_video)
            )

        manifest.update(storyboard_sha256=source_hash, scene_order=[s['id'] for s in data['scenes']],
                        font=str(font_path) if font_path else None, tts_provider=getattr(provider, 'provider_name', type(provider).__name__),
                        tts_voice=getattr(provider, 'voice_id', None),
                        speech_status=getattr(provider, 'speech_status', 'provided_audio'),
                        visual_assets_supplied=assets_dir is not None,
                        video_provider=getattr(video_provider, 'provider_name', None),
                        video_assets_supplied=video_provider is not None,
                        require_video_assets=require_video_assets)
        missing_assets = [
            scene['id'] for scene in data['scenes']
            if visual_assets[scene['id']] is None and video_assets[scene['id']] is None
        ]
        manifest['visual_assets'] = {
            scene['id']: ({
                'file': visual_assets[scene['id']].name,
                'sha256': digest(visual_assets[scene['id']])
            } if visual_assets[scene['id']] is not None else None)
            for scene in data['scenes']
        }
        manifest['video_assets'] = {
            scene['id']: ({
                **video_asset_info[scene['id']],
                'file': Path(video_asset_info[scene['id']]['path']).name,
                'sha256': digest(video_assets[scene['id']]),
            } if video_assets[scene['id']] is not None else None)
            for scene in data['scenes']
        }
        if missing_assets:
            manifest['fallbacks'].append(
                'Program-generated placeholder visuals used for scenes without supplied image or video assets: '
                + ', '.join(missing_assets)
            )
        if video_provider is not None:
            manifest['provider_notes'] = manifest.get('provider_notes', [])
            manifest['provider_notes'].append(
                'Supplied video clips are normalized to 1080x1920/30fps; source-clip audio is discarded. '
                'Narration and optional background music are mixed separately.'
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
            manifest['music'] = {'status': 'skipped', 'reason': 'No local music supplied', 'volume_db': data.get('music', {}).get('volume_db', -24)}
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
        settings = {'version': VERSION, 'implementation': fingerprint({str(p.relative_to(Path(__file__).parent)): digest(p) for p in sorted(Path(__file__).parent.rglob('*.py'))}), 'font': digest(font_path) if font_path else None,
                    'tts': provider.cache_key, 'voice': data['voice'], 'ffmpeg': command(['ffmpeg', '-version']).splitlines()[0],
                    'assets_dir_supplied': assets_dir is not None,
                    'video_provider': getattr(video_provider, 'cache_key', None)}
        clips, audio_flags = [], []
        for index, scene in enumerate(data['scenes']):
            visual_asset = visual_assets[scene['id']]
            video_asset = video_assets[scene['id']]
            video_asset_sha = digest(video_asset) if video_asset is not None else None
            visual_asset_sha = digest(visual_asset) if visual_asset is not None else None
            effective_visual_sha = video_asset_sha or visual_asset_sha or 'placeholder-v1'
            entry = {**manifest['scenes'][index], 'id': scene['id'], 'status': 'pending', 'attempts': 0, 'errors': [],
                     'visual_type': scene['visual']['type'],
                     'placeholder': visual_asset is None and video_asset is None,
                     'visual_source': 'video' if video_asset is not None else ('image' if visual_asset is not None else 'placeholder'),
                     'visual_asset': visual_asset.name if visual_asset is not None else None,
                     'visual_asset_sha256': visual_asset_sha,
                     'video_asset': video_asset.name if video_asset is not None else None,
                     'video_asset_path': str(video_asset) if video_asset is not None else None,
                     'video_asset_sha256': video_asset_sha,
                     'motion_requested': scene['visual'].get('motion'), 'transition_requested': scene.get('transition', 'cut'),
                     'narration': scene['narration'], 'onscreen_text': scene['onscreen_text']}
            manifest['scenes'][index] = entry
            save_json(manifest_path, manifest)
            input_hash = fingerprint([scene, settings, effective_visual_sha])
            entry['input_hash'] = input_hash
            old = next((e for e in previous.get('scenes', []) if e['id'] == scene['id'] and e.get('input_hash') == input_hash), {})
            entry['retry_count'] = old.get('retry_count', 0)
            entry['attempts_total'] = old.get('attempts_total', 0)
            work = cache / input_hash
            entry['visual_asset_path'] = str(work/'visual.png')
            work.mkdir(exist_ok=True)
            cached, meta = work/'clip.mp4', work/'complete.json'
            def failure(attempt, error):
                entry.update(status='failed', attempts=attempt, error=error)
                entry['errors'].append(error)
                save_json(manifest_path, manifest)
            def produce():
                if entry['attempts_total']:
                    entry['retry_count'] += 1
                entry['attempts'] += 1
                entry['attempts_total'] += 1
                entry['status'] = 'rendering'
                save_json(manifest_path, manifest)
                clip, audio = encode_scene(scene, data, font_path, work, provider, visual_asset, video_asset)
                speech = json.loads((work/'speech.json').read_text(encoding='utf-8'))
                assets = [work/'visual.png']
                if video_asset is not None:
                    assets.append(video_asset)
                if speech['audio_path']:
                    assets.append(Path(speech['audio_path']))
                save_json(meta, {'sha256': digest(clip), 'audio': audio,
                                 'audio_path': speech['audio_path'],
                                 'assets': {str(p): digest(p) for p in assets}})
                return clip, audio
            valid_cache = False
            if cached.is_file() and meta.is_file():
                try:
                    record = json.loads(meta.read_text())
                    if record['sha256'] == digest(cached) and all(Path(p).is_file() and digest(Path(p)) == sha for p, sha in record['assets'].items()):
                        verify_video(cached, frame_count(scene)/FPS, record['audio'])
                        valid_cache = True
                except (ValueError, KeyError, OSError, RenderError):
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
            record = json.loads(meta.read_text(encoding='utf-8'))
            entry.update(status='skipped_cached' if valid_cache else 'completed',
                         sha256=digest(destination), audio=audio, error=None,
                         audio_path=record['audio_path'], scene_video_path=str(destination),
                         speech_status='fallback_no_audio' if not audio else getattr(provider, 'speech_status', 'provided_audio'))
            save_json(manifest_path, manifest)
        if len(set(audio_flags)) != 1:
            raise RenderError('Provider returned mixed speech/no-speech scenes; refusing incomplete narration')
        manifest['speech_status'] = getattr(provider, 'speech_status', 'provided_audio') if audio_flags[0] else 'fallback_no_audio'
        if not audio_flags[0] and not provider.fallback:
            manifest['fallbacks'].append('Provider returned no audio: output has no real narration.')
        # Fixed internal filenames avoid ffmpeg concat/filter escaping of user paths.
        (output/'concat.txt').write_text(''.join(f"file 'scenes/{p.name}'\n" for p in clips), encoding='utf-8')
        # Preserve a playable unburned assembly even when subtitles cannot be rendered.
        command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                 '-f', 'concat', '-safe', '0', '-i', output/'concat.txt',
                 '-c', 'copy', '-movflags', '+faststart', output/'unburned.mp4'])
        manifest['unburned_video_path'] = str(output/'unburned.mp4')
        save_json(manifest_path, manifest)
        if font_path is None:
            raise RenderError(manifest['subtitles']['error'] + '; unburned.mp4 and subtitles.srt preserved')
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
        manifest['qc'].update(scene_count=len(clips), expected_scene_count=len(data['scenes']),
                              all_scenes_present=all(p.is_file() for p in clips),
                              target_duration_seconds=data['format']['target_duration_seconds'])
        if len(clips) != len(data['scenes']) or not all(p.is_file() for p in clips):
            raise RenderError('QC failed: missing scene outputs')
        if abs(manifest['qc']['duration_seconds'] - data['format']['target_duration_seconds']) > data['format']['target_duration_seconds'] * .08 + .15:
            raise RenderError('QC failed: final duration differs from storyboard target by more than 8%')
        manifest['qc']['status'] = 'passed'
        if digest(source) != source_hash:
            raise RenderError('Input storyboard changed during render')
        final_temp.replace(output/'final.mp4')
        manifest['subtitles']['status'] = 'burned'
        manifest.update(status='complete', overall_status='completed', final_video_path=str(output/'final.mp4'), final_sha256=digest(output/'final.mp4'))
        save_json(manifest_path, manifest)
        return manifest
    except Exception as exc:
        for entry in manifest['scenes']:
            if entry['status'] == 'rendering':
                entry['status'] = 'failed'
        manifest.update(status='failed', overall_status='failed', error=str(exc))
        manifest.setdefault('qc', {'status': 'not_run', 'reason': str(exc)})
        save_json(manifest_path, manifest)
        raise
