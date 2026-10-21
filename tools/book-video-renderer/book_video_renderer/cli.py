from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from .renderer import render

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    if len(sys.argv) > 1 and sys.argv[1] == 'render':
        argv = sys.argv[2:]
    else:
        argv = sys.argv[1:]
    parser.add_argument('storyboard', type=Path, nargs='?')
    parser.add_argument('--storyboard', type=Path, dest='storyboard_option')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--font', help='CJK font covering all storyboard characters')
    parser.add_argument('--assets-dir', type=Path, help='Optional directory of generated images named <scene_id>.png/.jpg/.jpeg/.webp')
    parser.add_argument('--video-assets-dir', type=Path, help='Optional directory of generated motion clips named <scene_id>.mp4/.mov/.webm/.mkv; clips take precedence over stills')
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--tts-audio-dir', type=Path, help='Real narration WAV files named scene_001.wav, etc.')
    parser.add_argument('--tts-audio-provider', help='Provider label for pre-synthesized WAVs, e.g. edge-tts')
    parser.add_argument('--tts-audio-voice', help='Voice ID used to pre-synthesize the WAVs')
    parser.add_argument('--tts-provider', choices=['none', 'edge-tts'], default='none', help='Optional speech synthesis provider; default none keeps rendering offline')
    parser.add_argument('--tts-voice', help='Edge TTS voice ID, e.g. zh-CN-YunxiNeural')
    parser.add_argument('--music-file', type=Path, help='Optional local background music file; storyboard music.enabled must be true')
    parser.add_argument('--music-volume-db', type=float, help='Override storyboard music.volume_db (allowed range: -60 to 0 dB)')
    parser.add_argument('--subtitle-file', type=Path, help='Optional pre-aligned SRT; validated and burned instead of scene-proportional captions')
    args = parser.parse_args(argv)
    if bool(args.storyboard) == bool(args.storyboard_option):
        parser.error('Provide exactly one storyboard path (positional or --storyboard)')
    args.storyboard = args.storyboard or args.storyboard_option
    try:
        result = render(args.storyboard, args.output, args.font, args.attempts,
                        speech_dir=args.tts_audio_dir, tts_provider=args.tts_provider,
                        tts_voice=args.tts_voice, assets_dir=args.assets_dir,
                        speech_provider_name=args.tts_audio_provider, speech_voice=args.tts_audio_voice,
                        music_file=args.music_file, music_volume_db=args.music_volume_db,
                        subtitle_file=args.subtitle_file, video_assets_dir=args.video_assets_dir)
        print(json.dumps({'status': result['status'], 'speech_status': result.get('speech_status'), 'tts_provider': result.get('tts_provider'), 'music': result.get('music'), 'subtitle_alignment': result.get('subtitle_alignment'), 'fallbacks': result['fallbacks'], 'provider_notes': result.get('provider_notes', []), 'qc': result['qc']}, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f'Render failed: {exc}', file=sys.stderr)
        return 1
    return 0
