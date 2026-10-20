"""Offline contract and failure-recovery regression tests."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

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
