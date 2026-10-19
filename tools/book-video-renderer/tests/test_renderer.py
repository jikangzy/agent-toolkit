import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'renderer.py'
spec = importlib.util.spec_from_file_location('renderer', MODULE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
EXAMPLE = r.ROOT/'examples/book-video/naval-test-001/storyboard.json'
FONT = os.environ.get('BOOK_VIDEO_FONT')


def fixture():
    data = json.loads(EXAMPLE.read_text())
    data['scenes'] = copy.deepcopy(data['scenes'][:5])
    for i, (scene, kind) in enumerate(zip(data['scenes'], ['image', 'title_card', 'broll', 'video', 'quote_card'])):
        scene.update(id=f'scene_{i+1:03}', duration_seconds=3, narration=f'这是第{i+1}个场景。', onscreen_text='中文占位画面')
        scene['visual']['type'] = kind
    data['format']['target_duration_seconds'] = 15
    return data


class UnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, data):
        path = self.root/'storyboard.json'
        path.write_text(json.dumps(data, ensure_ascii=False))
        return path

    def test_real_input_valid_and_unchanged(self):
        before = EXAMPLE.read_bytes()
        data = r.load_storyboard(EXAMPLE)
        self.assertEqual(len(data['scenes']), 10)
        self.assertEqual(sum(s['duration_seconds'] for s in data['scenes']), 113)
        self.assertEqual(EXAMPLE.read_bytes(), before)

    def test_schema_rejects_missing_narration_and_unknown_fields(self):
        for mutation in ('missing', 'unknown'):
            with self.subTest(mutation=mutation):
                data = fixture()
                if mutation == 'missing':
                    del data['scenes'][0]['narration']
                else:
                    data['scenes'][0]['unexpected'] = 1
                with self.assertRaises(r.RenderError):
                    r.load_storyboard(self.write(data))

    def test_duplicate_id(self):
        data = fixture()
        data['scenes'][1]['id'] = data['scenes'][0]['id']
        with self.assertRaisesRegex(r.RenderError, 'Duplicate'):
            r.load_storyboard(self.write(data))

    def test_invalid_duration_and_visual(self):
        for key, value in [('duration_seconds', -1), ('visual', {'type': 'unknown', 'prompt': 'x'})]:
            data = fixture()
            data['scenes'][0][key] = value
            with self.assertRaises(r.RenderError):
                r.load_storyboard(self.write(data))

    def test_target_mismatch(self):
        data = fixture()
        data['format']['target_duration_seconds'] = 100
        with self.assertRaisesRegex(r.RenderError, '8%'):
            r.load_storyboard(self.write(data))

    def test_unsupported_format(self):
        data = fixture()
        data['format']['fps'] = 24
        with self.assertRaisesRegex(r.RenderError, '30 fps'):
            r.load_storyboard(self.write(data))

    def test_subtitle_text_order_and_timing(self):
        data = r.load_storyboard(EXAMPLE)
        blocks = r.subtitles(data).strip().split('\n\n')
        text = ''.join(block.split('\n', 2)[2] for block in blocks)
        self.assertEqual(text, ''.join(s['narration'] for s in data['scenes']))
        self.assertEqual(blocks[0].splitlines()[1].split(' --> ')[0], '00:00:00,000')
        self.assertTrue(blocks[-1].splitlines()[1].endswith('00:01:53,000'))
        previous = '00:00:00,000'
        for block in blocks:
            start, end = block.splitlines()[1].split(' --> ')
            self.assertEqual(start, previous)
            self.assertLess(start, end)
            previous = end

    def test_stamp_rollover(self):
        self.assertEqual(r.stamp(3599.9996), '01:00:00,000')

    def test_retry_success_and_exhaustion(self):
        failures = []
        action = unittest.mock.Mock(side_effect=[r.RenderError('transient'), 42])
        with patch.object(r.time, 'sleep'):
            self.assertEqual(r.retry(action, 3, lambda n,e: failures.append((n,e))), 42)
        self.assertEqual(failures, [(1, 'transient')])
        with patch.object(r.time, 'sleep'), self.assertRaisesRegex(r.RenderError, 'persistent'):
            r.retry(unittest.mock.Mock(side_effect=r.RenderError('persistent')), 2, lambda n,e: None)

    def test_cache_key_changes_for_scene_and_provider(self):
        scene = fixture()['scenes'][0]
        other = copy.deepcopy(scene)
        other['narration'] += '变化'
        self.assertNotEqual(r.fingerprint([scene, 'provider1']), r.fingerprint([other, 'provider1']))
        self.assertNotEqual(r.fingerprint([scene, 'provider1']), r.fingerprint([scene, 'provider2']))

    def test_no_tts_is_explicit(self):
        provider = r.NoTTS()
        self.assertIn('NO audio', provider.fallback)
        self.assertIsNone(provider.synthesize('scene_001', '原文', {}, 3, self.root))

    def test_missing_recorded_speech_fails(self):
        with self.assertRaisesRegex(r.RenderError, 'Missing real narration'):
            r.RecordedSpeech(self.root, fixture()['scenes'])

    def test_missing_dependency_writes_failed_manifest(self):
        source = self.write(fixture())
        with patch.object(r.shutil, 'which', return_value=None), self.assertRaisesRegex(r.RenderError, 'Missing executable'):
            r.render(source, self.root/'output')
        manifest = json.loads((self.root/'output/manifest.json').read_text())
        self.assertEqual(manifest['status'], 'failed')
        self.assertIn('ffmpeg', manifest['error'])

    def test_exhausted_scene_retry_is_recorded(self):
        source = self.write(fixture())
        font = self.root/'fake-font'
        font.write_bytes(b'fixture')
        with patch.object(r, 'find_font', return_value=font), patch.object(r, 'command', return_value='ffmpeg test'), patch.object(r, 'encode_scene', side_effect=r.RenderError('encoder unavailable')), patch.object(r.time, 'sleep'):
            with self.assertRaisesRegex(r.RenderError, 'encoder unavailable'):
                r.render(source, self.root/'output', attempts=2)
        manifest = json.loads((self.root/'output/manifest.json').read_text())
        self.assertEqual(manifest['status'], 'failed')
        self.assertEqual(manifest['scenes'][0]['status'], 'failed')
        self.assertEqual(manifest['scenes'][0]['attempts'], 2)
        self.assertEqual(len(manifest['scenes'][0]['errors']), 2)

    def test_missing_font_is_actionable(self):
        with self.assertRaisesRegex(r.RenderError, 'No font covers'):
            r.find_font('/no/such/font.ttf', '中文')

    def test_output_cannot_contain_source(self):
        source = self.write(fixture())
        with self.assertRaisesRegex(r.RenderError, 'must not contain'):
            r.render(source, self.root)

    def test_ffprobe_rejects_wrong_codec(self):
        metadata = {'streams': [{'codec_type': 'video', 'codec_name': 'vp9', 'width':1080, 'height':1920,
                                 'r_frame_rate':'30/1', 'pix_fmt':'yuv420p'}], 'format':{'duration':'3'}}
        with patch.object(r, 'probe', return_value=metadata), self.assertRaisesRegex(r.RenderError, 'format'):
            r.verify_video('bad.mp4', 3, False)


@unittest.skipUnless(FONT and shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Set BOOK_VIDEO_FONT and install FFmpeg/ffprobe for integration tests')
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='renderer integration ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_all_visuals_cache_and_immutable_input(self):
        data = fixture()
        source = self.root/'storyboard.json'
        source.write_text(json.dumps(data, ensure_ascii=False))
        original = source.read_bytes()
        output = self.root/'output'
        first = r.render(source, output, FONT)
        self.assertEqual(first['status'], 'complete')
        self.assertEqual(first['scene_order'], [s['id'] for s in data['scenes']])
        self.assertEqual(first['qc']['duration_seconds'], 15)
        self.assertIsNone(first['qc']['audio_codec'])
        self.assertEqual(len(list((output/'scenes').glob('*.mp4'))), 5)
        self.assertTrue((output/'subtitles.srt').is_file())
        second = r.render(source, output, FONT)
        self.assertTrue(all(e['cache_hit'] for e in second['scenes']))
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual([e['onscreen_text'] for e in second['scenes']], [s['onscreen_text'] for s in data['scenes']])
        # Corrupt one clip: only that scene must be regenerated, verified with real ffprobe.
        clip = next((output/'cache').glob('*/clip.mp4'))
        clip.write_bytes(b'corrupt')
        third = r.render(source, output, FONT)
        self.assertEqual(sum(not e['cache_hit'] for e in third['scenes']), 1)

    def test_aac_adapter_and_reject_truncation(self):
        scene = fixture()['scenes'][0]
        # Synthetic test fixture only; never used or described as real narration.
        wav = self.root/(scene['id']+'.wav')
        r.command(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=1', wav])
        provider = r.RecordedSpeech(self.root, [scene])
        work = self.root/'work'
        work.mkdir()
        clip, audio = r.encode_scene(scene, fixture(), Path(FONT), work, provider)
        self.assertTrue(audio)
        self.assertEqual(r.verify_video(clip, 3, True)['audio_codec'], 'aac')
        data = fixture()
        for item in data['scenes'][1:]:
            shutil.copy2(wav, self.root/(item['id']+'.wav'))
        source = self.root/'storyboard.json'
        source.write_text(json.dumps(data, ensure_ascii=False))
        final = r.render(source, self.root/'audio-output', FONT, speech_dir=self.root)
        self.assertEqual(final['qc']['audio_codec'], 'aac')
        self.assertEqual(final['speech_status'], 'provided_audio')
        r.command(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=4', wav])
        with self.assertRaisesRegex(r.RenderError, 'refusing to truncate'):
            provider.synthesize(scene['id'], scene['narration'], {}, 3, work)


if __name__ == '__main__':
    unittest.main()
