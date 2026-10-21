from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Protocol
from ..models import RenderError
from ..manifest import digest, fingerprint
from ..ffmpeg import command, probe

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
        self.speech_status = ('generated_audio' if provider_name and provider_name.lower() in ('edge-tts', 'edgetts')
                              else 'provided_audio')
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
        seconds = float(metadata['format']['duration'])
        if not math.isfinite(seconds) or seconds <= 0:
            raise RenderError(f'{scene_id}: speech has invalid duration')
        if seconds > duration + .001:
            raise RenderError(f'{scene_id}: speech exceeds scene duration; refusing to truncate narration')
        command(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', path,
                 '-map', '0:a:0', '-f', 'null', '-'])
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
