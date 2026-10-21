"""Offline contract and failure-recovery regression tests."""
import copy
import json
import math
import struct
import subprocess
import wave
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from book_video_renderer.models import ROOT, FPS, RenderError, total_duration
from book_video_renderer.validator import load_storyboard
from book_video_renderer.scene import motion_filter
from book_video_renderer.renderer import render
import book_video_renderer.renderer as engine
from test_renderer import fixture, FONT


class MVPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, data):
        path = self.root/'storyboard.json'
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return path

    def test_scene_order_rejected_without_sorting_or_changing_source(self):
        for mutation in ('reorder', 'gap', 'start'):
            data = fixture()
            if mutation == 'reorder':
                data['scenes'][0], data['scenes'][1] = data['scenes'][1], data['scenes'][0]
            elif mutation == 'gap':
                data['scenes'][2]['id'] = 'scene_009'
            else:
                data['scenes'][0]['id'] = 'scene_000'
            source = self.source(data)
            original = source.read_bytes()
            with self.subTest(mutation=mutation), self.assertRaisesRegex(RenderError, 'scene order'):
                load_storyboard(source)
            self.assertEqual(original, source.read_bytes())

    def test_naval_example_declares_dynamic_scenes_as_video_or_broll(self):
        naval = json.loads((ROOT/'examples/book-video/naval-test-001/storyboard.json').read_text(encoding='utf-8'))
        by_id = {scene['id']: scene['visual']['type'] for scene in naval['scenes']}
        self.assertEqual(by_id['scene_003'], 'broll')
        self.assertEqual(by_id['scene_004'], 'broll')
        self.assertEqual(by_id['scene_005'], 'video')
        self.assertEqual(by_id['scene_007'], 'broll')
        self.assertEqual(by_id['scene_008'], 'broll')
        self.assertEqual(by_id['scene_001'], 'title_card')
        self.assertEqual(by_id['scene_010'], 'title_card')

    def test_duration_rounds_each_scene_to_frames(self):
        data = fixture()
        data['scenes'][0]['duration_seconds'] = 3.019
        original = copy.deepcopy(data)
        self.assertAlmostEqual(total_duration(data), 12 + 91/FPS)
        self.assertEqual(data, original)
        naval = json.loads((ROOT/'examples/book-video/naval-test-001/storyboard.json').read_text())
        self.assertEqual(total_duration(naval), 113)

    def test_motion_direction_mapping_and_safe_default(self):
        scene = fixture()['scenes'][0]
        filters = {}
        for motion in ('slow zoom-in', 'slow zoom-out', 'slow pan left', 'slow pan right', 'slow pan down', 'slow push-in', 'unknown'):
            scene['visual']['motion'] = motion
            filters[motion] = motion_filter(scene)
        self.assertIn('1.04-0.025', filters['slow zoom-out'])
        self.assertNotEqual(filters['slow pan left'], filters['slow pan right'])
        self.assertIn('(ih-ih/zoom)', filters['slow pan down'])
        self.assertEqual(filters['unknown'], filters['slow push-in'])

    def test_invalid_input_writes_actionable_manifest(self):
        source = self.source({'invalid': True})
        output = self.root/'output'
        with self.assertRaisesRegex(RenderError, 'Invalid storyboard'):
            render(source, output)
        manifest = json.loads((output/'manifest.json').read_text())
        self.assertEqual(manifest['overall_status'], 'failed')
        self.assertEqual(manifest['storyboard_path'], str(source))
        self.assertIsNone(manifest['final_video_path'])
        self.assertIn('required property', manifest['error'])

    @unittest.skipUnless(FONT, 'Set BOOK_VIDEO_FONT for real FFmpeg integration')
    def test_missing_cjk_font_retains_srt_and_unburned_video(self):
        source = self.source(fixture())
        original = source.read_bytes()
        output = self.root/'output'
        with patch.object(engine, 'find_font', side_effect=RenderError('No font covers all characters')):
            with self.assertRaisesRegex(RenderError, 'unburned.mp4 and subtitles.srt preserved'):
                render(source, output, attempts=1)
        manifest = json.loads((output/'manifest.json').read_text())
        self.assertEqual(manifest['overall_status'], 'failed')
        self.assertEqual(manifest['subtitles']['status'], 'failed')
        self.assertTrue((output/'unburned.mp4').is_file())
        self.assertTrue((output/'subtitles.srt').is_file())
        self.assertFalse((output/'final.mp4').exists())
        self.assertEqual(len(list((output/'scenes').glob('*.mp4'))), 5)
        self.assertEqual(source.read_bytes(), original)


    @unittest.skipUnless(FONT, 'Set BOOK_VIDEO_FONT for real FFmpeg integration')
    def test_supplied_images_audio_music_and_subtitles_render_offline_and_cache(self):
        data = fixture()
        source = self.source(data)
        original = source.read_bytes()
        output = self.root/'output'
        assets = self.root/'assets'
        audio = self.root/'audio'
        assets.mkdir()
        audio.mkdir()
        sample_rate = 16000

        def write_tone(path, duration, frequency):
            frames = bytearray()
            for index in range(int(sample_rate * duration)):
                value = int(1800 * math.sin(2 * math.pi * frequency * index / sample_rate))
                frames.extend(struct.pack('<h', value))
            with wave.open(str(path), 'wb') as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(sample_rate)
                stream.writeframes(frames)

        def srt_timestamp(seconds):
            milliseconds = round(seconds * 1000)
            hours, milliseconds = divmod(milliseconds, 3_600_000)
            minutes, milliseconds = divmod(milliseconds, 60_000)
            whole_seconds, milliseconds = divmod(milliseconds, 1000)
            return f'{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}'

        cues = []
        for index, scene in enumerate(data['scenes']):
            Image.new('RGB', (320, 568), (25 + index * 20, 45, 80)).save(
                assets/(scene['id'] + '.png')
            )
            # Synthetic local audio fixtures exercise the supplied-audio path;
            # they are test tones, not claimed to be human speech or TTS output.
            write_tone(audio/(scene['id'] + '.wav'), 2.5, 220 + index * 35)
            start, end = index * 3, (index + 1) * 3
            cues.append(
                f'{index + 1}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n'
                f'{scene["narration"]}'
            )

        music = self.root/'music.wav'
        write_tone(music, 1.0, 110)
        subtitle_file = self.root/'aligned.srt'
        subtitle_file.write_text('\n\n'.join(cues) + '\n', encoding='utf-8')

        result = render(
            source, output, FONT, attempts=1,
            speech_dir=audio, assets_dir=assets,
            music_file=music, subtitle_file=subtitle_file,
        )

        self.assertEqual(result['overall_status'], 'completed')
        self.assertEqual(result['speech_status'], 'provided_audio')
        self.assertEqual(result['music']['status'], 'supplied')
        self.assertEqual(result['subtitle_alignment']['status'], 'supplied_srt')
        self.assertEqual(result['subtitle_alignment']['cue_count'], len(data['scenes']))
        self.assertEqual(result['qc']['status'], 'passed')
        self.assertEqual(result['qc']['scene_count'], len(data['scenes']))
        self.assertTrue(all(scene['audio'] for scene in result['scenes']))
        self.assertTrue(all(not scene['placeholder'] for scene in result['scenes']))
        self.assertFalse(any('Program-generated placeholder visuals' in item for item in result['fallbacks']))
        self.assertFalse(any('background music omitted' in item for item in result['fallbacks']))
        self.assertFalse(any('scene-proportional timing' in item for item in result['fallbacks']))
        self.assertFalse(any('NO audio' in item or 'No Chinese TTS configured' in item for item in result['fallbacks']))
        self.assertEqual(source.read_bytes(), original)
        subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', str(output/'final.mp4'), '-f', 'null', '-'],
            check=True,
        )

        # A second identical run must reuse every scene clip without a provider call.
        cached = render(
            source, output, FONT, attempts=1,
            speech_dir=audio, assets_dir=assets,
            music_file=music, subtitle_file=subtitle_file,
        )
        self.assertTrue(all(scene['cache_hit'] for scene in cached['scenes']))
        self.assertTrue(all(scene['status'] == 'skipped_cached' for scene in cached['scenes']))
        self.assertEqual(source.read_bytes(), original)


    def test_real_video_assets_render_as_motion_footage_and_invalidate_only_the_changed_scene(self):
        data = fixture()
        source = self.source(data)
        original = source.read_bytes()
        output = self.root/'video-output'
        images = self.root/'images'
        videos = self.root/'videos'
        images.mkdir()
        videos.mkdir()

        for index, scene in enumerate(data['scenes']):
            Image.new('RGB', (320, 568), (30 + index * 20, 60, 100)).save(
                images/(scene['id'] + '.png')
            )

        for scene_id in ('scene_003', 'scene_004'):
            engine.command([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'lavfi', '-i', 'testsrc2=size=360x640:rate=24:duration=1',
                '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                videos/(scene_id + '.mp4')
            ])

        first = render(
            source, output, FONT, attempts=1, assets_dir=images,
            video_assets_dir=videos, require_video_assets=True,
        )
        self.assertEqual(first['overall_status'], 'completed')
        self.assertEqual(first['scenes'][0]['visual_source'], 'image')
        self.assertEqual(first['scenes'][1]['visual_source'], 'image')
        self.assertEqual(first['scenes'][2]['visual_source'], 'video')
        self.assertEqual(first['scenes'][3]['visual_source'], 'video')
        self.assertEqual(first['scenes'][4]['visual_source'], 'image')
        self.assertFalse(first['scenes'][2]['placeholder'])
        self.assertFalse(first['scenes'][3]['placeholder'])
        self.assertEqual(first['video_provider'], 'supplied-video')
        self.assertEqual(first['video_assets']['scene_003']['duration_seconds'], 1.0)
        self.assertEqual(first['qc']['scene_count'], 5)
        self.assertFalse(any('Program-generated placeholder visuals' in item for item in first['fallbacks']))
        subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', str(output/'final.mp4'), '-f', 'null', '-'],
            check=True,
        )

        second = render(
            source, output, FONT, attempts=1, assets_dir=images,
            video_assets_dir=videos, require_video_assets=True,
        )
        self.assertTrue(all(scene['cache_hit'] for scene in second['scenes']))

        # Replacing one source clip invalidates only its scene's cached render.
        engine.command([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc=size=360x640:rate=24:duration=1',
            '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            videos/'scene_003.mp4'
        ])
        third = render(
            source, output, FONT, attempts=1, assets_dir=images,
            video_assets_dir=videos, require_video_assets=True,
        )
        self.assertFalse(third['scenes'][2]['cache_hit'])
        self.assertTrue(all(third['scenes'][i]['cache_hit'] for i in (0, 1, 3, 4)))
        self.assertEqual(source.read_bytes(), original)

    def test_require_video_assets_fails_closed_for_missing_broll(self):
        data = fixture()
        source = self.source(data)
        videos = self.root/'incomplete-videos'
        videos.mkdir()
        engine.command([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc2=size=360x640:rate=24:duration=1',
            '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
            videos/'scene_004.mp4'
        ])
        with self.assertRaisesRegex(RenderError, 'scene_003'):
            render(
                source, self.root/'strict-output', FONT, attempts=1,
                video_assets_dir=videos, require_video_assets=True,
            )
        manifest = json.loads((self.root/'strict-output/manifest.json').read_text())
        self.assertEqual(manifest['overall_status'], 'failed')
        self.assertIn('Missing required video clips', manifest['error'])


class RecoveryTests(unittest.TestCase):
    setUp = MVPTests.setUp
    source = MVPTests.source
    @unittest.skipUnless(FONT, 'Set BOOK_VIDEO_FONT for real FFmpeg integration')
    def test_failed_scene_preserves_completed_scene_and_resumes(self):
        source = self.source(fixture())
        output = self.root/'output'
        real_encode = engine.encode_scene

        def fail_second(scene, *args, **kwargs):
            if scene['id'] == 'scene_002':
                raise RenderError('simulated second-scene failure')
            return real_encode(scene, *args, **kwargs)

        with patch.object(engine, 'encode_scene', side_effect=fail_second):
            with self.assertRaisesRegex(RenderError, 'second-scene failure'):
                render(source, output, FONT, attempts=2)
        failed = json.loads((output/'manifest.json').read_text())
        first_hash = failed['scenes'][0]['sha256']
        self.assertEqual(failed['scenes'][0]['status'], 'completed')
        self.assertEqual(failed['scenes'][1]['status'], 'failed')
        self.assertEqual(failed['scenes'][1]['retry_count'], 1)
        self.assertEqual(failed['scenes'][2]['status'], 'pending')
        self.assertTrue((output/'scenes/scene_001.mp4').is_file())
        result = render(source, output, FONT, attempts=1)
        self.assertEqual(result['scenes'][0]['status'], 'skipped_cached')
        self.assertEqual(result['scenes'][0]['sha256'], first_hash)
        self.assertEqual(result['scenes'][1]['retry_count'], 2)
        self.assertEqual(result['overall_status'], 'completed')
        for entry in result['scenes']:
            self.assertTrue(Path(entry['visual_asset_path']).is_file())
            self.assertTrue(Path(entry['scene_video_path']).is_file())
            self.assertIsNone(entry['audio_path'])
            self.assertEqual(entry['duration'], 3)
