import asyncio
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import book_video_renderer.renderer as engine
import book_video_renderer.providers.tts as tts
import book_video_renderer.providers.music as music
import book_video_renderer.providers.video as video_provider
import book_video_renderer.qc as qc

MODULE = Path(__file__).resolve().parents[1] / 'renderer.py'
spec = importlib.util.spec_from_file_location('renderer', MODULE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
PREPARE_MODULE = MODULE.parent / 'prepare_narration.py'
prepare_spec = importlib.util.spec_from_file_location('prepare_narration', PREPARE_MODULE)
prepare_narration = importlib.util.module_from_spec(prepare_spec)
prepare_spec.loader.exec_module(prepare_narration)
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
        self.root = Path(self.temp.name).resolve()

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

    def test_word_boundary_mapping_preserves_exact_source_text(self):
        narration = "为什么有人睡觉？"
        boundaries = [
            {"start_seconds": 0.0, "end_seconds": 0.4, "text": "为什么"},
            {"start_seconds": 0.4, "end_seconds": 0.7, "text": "有人"},
            {"start_seconds": 0.7, "end_seconds": 1.0, "text": "睡觉"},
            {"start_seconds": 1.0, "end_seconds": 1.2, "text": "？"},
        ]
        mapped = prepare_narration.map_boundaries_to_source(narration, boundaries)
        self.assertIsNotNone(mapped)
        self.assertEqual("".join(item["text"] for item in mapped), narration)

        mismatch = prepare_narration.map_boundaries_to_source(narration, [
            {"start_seconds": 0.0, "end_seconds": 0.5, "text": "不匹配"}
        ])
        self.assertIsNone(mismatch)

    def test_word_boundary_mapping_ignores_punctuation_omitted_by_tts(self):
        narration = "为什么有人睡觉的时候，财富还在增长？《纳瓦尔宝典》给出的答案，可能和你的直觉相反。"
        boundary_texts = [
            "为什么有人睡觉的时候",
            "财富还在增长",
            "纳瓦尔宝典",
            "给出的答案",
            "可能和你的",
            "直觉相反",
        ]
        boundaries = [
            {
                "start_seconds": index * 0.4,
                "end_seconds": (index + 1) * 0.4,
                "text": text,
            }
            for index, text in enumerate(boundary_texts)
        ]
        mapped = prepare_narration.map_boundaries_to_source(narration, boundaries)
        self.assertIsNotNone(mapped)
        self.assertEqual("".join(item["text"] for item in mapped), narration)
        self.assertIn("，", mapped[0]["text"] + mapped[1]["text"])
        self.assertIn("《", mapped[1]["text"])
        self.assertTrue(mapped[-1]["text"].endswith("。"))

    def test_aligned_srt_uses_word_timing_and_falls_back_without_text_mismatch(self):
        data = fixture()
        boundaries = {
            "scene_001": [
                {"start_seconds": 0.0, "end_seconds": 0.4, "text": "这是第"},
                {"start_seconds": 0.4, "end_seconds": 0.8, "text": "1个场景。"},
            ],
            "scene_002": [
                {"start_seconds": 0.0, "end_seconds": 0.5, "text": "wrong"}
            ],
        }
        srt, report = prepare_narration.build_aligned_srt(data, boundaries, max_chars=3)
        self.assertEqual(report["scene_001"]["alignment"], "word_boundary")
        self.assertEqual(report["scene_002"]["alignment"], "scene_proportional_fallback")
        self.assertIn("00:00:00,000 --> 00:00:00,400", srt)
        self.assertIn("00:00:03,000", srt)
        cue_text = [
            line for line in srt.splitlines()
            if line and not line.isdigit() and " --> " not in line
        ]
        self.assertEqual("".join(cue_text), "".join(scene["narration"] for scene in data["scenes"]))

    def test_aligned_srt_clamps_overlapping_word_boundary_cues(self):
        data = fixture()
        boundaries = {
            "scene_001": [
                {"start_seconds": 0.0, "end_seconds": 0.4, "text": "这是第"},
                {"start_seconds": 0.395, "end_seconds": 0.8, "text": "1个场景。"},
            ],
        }
        srt, report = prepare_narration.build_aligned_srt(data, boundaries, max_chars=3)
        self.assertEqual(report["scene_001"]["alignment"], "word_boundary")
        blocks = [block for block in srt.strip().split("\n\n\n") if block.strip()]

        def seconds(stamp):
            hours, minutes, rest = stamp.split(":")
            seconds, millis = rest.split(",")
            return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000

        previous_end = 0.0
        for block in blocks:
            _, timing, *_ = block.splitlines()
            start, end = (seconds(value) for value in timing.split(" --> "))
            self.assertGreaterEqual(start, previous_end)
            self.assertGreater(end, start)
            previous_end = end

        cue_text = [
            line for line in srt.splitlines()
            if line and not line.isdigit() and " --> " not in line
        ]
        self.assertEqual("".join(cue_text), "".join(scene["narration"] for scene in data["scenes"]))

    def test_external_srt_validation_checks_timestamps_and_video_duration(self):
        valid = self.root/'valid.srt'
        valid.write_text("1\n00:00:00,000 --> 00:00:01,000\n中文字幕\n", encoding="utf-8")
        result = r.validate_subtitle_file(valid, 3)
        self.assertEqual(result["cue_count"], 1)
        invalid = self.root/'invalid.srt'
        invalid.write_text("1\n00:00:02,000 --> 00:00:04,000\n越界字幕\n", encoding="utf-8")
        with self.assertRaisesRegex(r.RenderError, 'beyond the final video duration'):
            r.validate_subtitle_file(invalid, 3)

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

    def test_visual_asset_is_normalized_to_vertical_frame(self):
        source = self.root/'square.png'
        target = self.root/'normalized.png'
        r.Image.new('RGB', (400, 400), (30, 60, 90)).save(source)
        r.normalize_image_asset(source, target)
        with r.Image.open(target) as image:
            self.assertEqual(image.size, (1080, 1920))
            self.assertEqual(image.mode, 'RGB')

    def test_find_visual_asset_rejects_ambiguous_extensions(self):
        assets = self.root/'assets'
        assets.mkdir()
        r.Image.new('RGB', (10, 10), (0, 0, 0)).save(assets/'scene_001.png')
        self.assertEqual(r.find_visual_asset(assets, 'scene_001'), assets/'scene_001.png')
        r.Image.new('RGB', (10, 10), (0, 0, 0)).save(assets/'scene_001.jpg')
        with self.assertRaisesRegex(r.RenderError, 'multiple visual assets'):
            r.find_visual_asset(assets, 'scene_001')

    def test_preflight_refuses_to_overwrite_source_or_each_other(self):
        with patch.object(prepare_narration.asyncio, 'run') as synthesize:
            with self.assertRaisesRegex(
                prepare_narration.renderer.RenderError, 'must not overwrite'
            ):
                prepare_narration.prepare(
                    EXAMPLE, self.root/'audio', EXAMPLE, self.root/'timing-report.json'
                )
            with self.assertRaisesRegex(
                prepare_narration.renderer.RenderError, 'must not overwrite'
            ):
                prepare_narration.prepare(
                    EXAMPLE, self.root/'audio', self.root/'derived.json', EXAMPLE
                )
            with self.assertRaisesRegex(
                prepare_narration.renderer.RenderError, 'must not overwrite'
            ):
                prepare_narration.prepare(
                    EXAMPLE, self.root/'audio', self.root/'same.json', self.root/'same.json'
                )
            with self.assertRaisesRegex(
                prepare_narration.renderer.RenderError, 'must not overwrite'
            ):
                prepare_narration.prepare(
                    EXAMPLE, self.root/'audio', self.root/'derived.json',
                    self.root/'timing.json', subtitle_output=EXAMPLE
                )
            synthesize.assert_not_called()

    def test_preflight_collects_word_boundaries_from_same_audio_stream(self):
        calls = []

        class FakeCommunicate:
            def __init__(self, text, voice, rate, boundary):
                self.text = text
                calls.append({"text": text, "voice": voice, "rate": rate, "boundary": boundary})

            async def stream(self):
                yield {"type": "audio", "data": b"fake-mp3"}
                yield {
                    "type": "WordBoundary",
                    "offset": 2_000_000,
                    "duration": 4_000_000,
                    "text": self.text,
                }

        class FakeProvider:
            edge_tts = types.SimpleNamespace(Communicate=FakeCommunicate)
            voice_id = "zh-CN-YunxiNeural"

            @staticmethod
            def rate_for(voice):
                return "+0%"

        data = fixture()
        audio_dir = self.root/"audio"

        def fake_convert(args):
            Path(args[-1]).write_bytes(b"fake-wav")

        with patch.object(prepare_narration.renderer, "EdgeTTS", return_value=FakeProvider()), patch.object(
            prepare_narration.renderer, "command", side_effect=fake_convert
        ), patch.object(
            prepare_narration.renderer, "probe",
            return_value={"streams": [{"codec_type": "audio"}], "format": {"duration": "1.25"}},
        ):
            first_cache = {}
            durations, rate, boundaries = asyncio.run(
                prepare_narration.synthesize_audio(
                    data, audio_dir, "zh-CN-YunxiNeural", cache_status=first_cache
                )
            )
            self.assertTrue(all(value == "miss" for value in first_cache.values()))

            cached_status = {}
            cached_durations, cached_rate, cached_boundaries = asyncio.run(
                prepare_narration.synthesize_audio(
                    data, audio_dir, "zh-CN-YunxiNeural", cache_status=cached_status
                )
            )
            self.assertTrue(all(value == "hit" for value in cached_status.values()))
            self.assertEqual(cached_durations, durations)
            self.assertEqual(cached_rate, rate)
            self.assertEqual(cached_boundaries, boundaries)
            self.assertEqual(len(calls), len(data["scenes"]))

            # Changing one scene's narration invalidates only that scene's audio.
            data["scenes"][0]["narration"] += "缓存失效"
            changed_status = {}
            asyncio.run(
                prepare_narration.synthesize_audio(
                    data, audio_dir, "zh-CN-YunxiNeural", cache_status=changed_status
                )
            )
            self.assertEqual(changed_status["scene_001"], "miss")
            self.assertTrue(all(
                changed_status[scene["id"]] == "hit" for scene in data["scenes"][1:]
            ))
            self.assertEqual(len(calls), len(data["scenes"]) + 1)

            forced_status = {}
            asyncio.run(
                prepare_narration.synthesize_audio(
                    data, audio_dir, "zh-CN-YunxiNeural", force=True,
                    cache_status=forced_status
                )
            )
            self.assertTrue(all(value == "forced" for value in forced_status.values()))
            self.assertEqual(len(calls), 2 * len(data["scenes"]) + 1)

        self.assertEqual(rate, "+0%")
        self.assertTrue(all(call["boundary"] == "WordBoundary" for call in calls))
        self.assertEqual(durations["scene_001"], 1.25)
        self.assertAlmostEqual(boundaries["scene_001"][0]["start_seconds"], 0.2)
        self.assertAlmostEqual(boundaries["scene_001"][0]["end_seconds"], 0.6)
        self.assertEqual(boundaries["scene_001"][0]["text"], fixture()["scenes"][0]["narration"])
        self.assertTrue((audio_dir/"scene_001.mp3").is_file())
        self.assertTrue((audio_dir/"scene_001.cache.json").is_file())

    def test_preflight_timing_extends_only_overlong_scenes_without_mutating_source(self):
        data = fixture()
        original = copy.deepcopy(data)
        durations = {scene['id']: 2.7 for scene in data['scenes']}
        durations['scene_002'] = 4.12

        derived, report = prepare_narration.allocate_scene_durations(data, durations, 0.25)

        self.assertEqual(data, original)
        self.assertEqual(
            [scene['narration'] for scene in derived['scenes']],
            [scene['narration'] for scene in original['scenes']]
        )
        self.assertEqual(
            [scene['id'] for scene in derived['scenes']],
            [scene['id'] for scene in original['scenes']]
        )
        self.assertEqual(derived['scenes'][0]['duration_seconds'], 3)
        self.assertEqual(derived['scenes'][1]['duration_seconds'], 4.4)
        self.assertEqual(
            derived['format']['target_duration_seconds'],
            sum(scene['duration_seconds'] for scene in derived['scenes'])
        )
        self.assertEqual(report['scene_002']['speech_seconds'], 4.12)
        self.assertEqual(report['scene_002']['allocated_scene_seconds'], 4.4)

    def test_recorded_speech_metadata_labels_pre_synthesized_provider(self):
        scenes = fixture()['scenes']
        for scene in scenes:
            (self.root/(scene['id']+'.wav')).write_bytes(b'fixture audio')
        provider = r.RecordedSpeech(
            self.root, scenes, provider_name='edge-tts', voice_id='zh-CN-YunxiNeural'
        )
        self.assertEqual(provider.provider_name, 'edge-tts')
        self.assertEqual(provider.voice_id, 'zh-CN-YunxiNeural')
        self.assertEqual(provider.speech_status, 'generated_audio')
        self.assertIn('external Edge TTS service', provider.provider_notice)

    def test_music_requires_enabled_flag_and_valid_local_audio(self):
        data = fixture()
        data['music']['enabled'] = False
        supplied = self.root/'music.wav'
        supplied.write_bytes(b'fake audio')
        with self.assertRaisesRegex(r.RenderError, 'music.enabled is false'):
            r.resolve_music(data, supplied)

        data['music']['enabled'] = True
        with patch.object(music, 'probe', return_value={
            'streams': [{'codec_type': 'audio'}], 'format': {'duration': '1.0'}
        }):
            path, volume = r.resolve_music(data, supplied)
            self.assertEqual(path, supplied.resolve())
            self.assertEqual(volume, -24)
            self.assertEqual(r.resolve_music(data, supplied, -18)[1], -18)
            for invalid in (-60.1, 0.1, float('nan'), float('inf')):
                with self.subTest(volume=invalid), self.assertRaisesRegex(r.RenderError, 'between -60 and 0'):
                    r.resolve_music(data, supplied, invalid)

        with patch.object(music, 'probe', return_value={
            'streams': [{'codec_type': 'video'}], 'format': {'duration': '1.0'}
        }), self.assertRaisesRegex(r.RenderError, 'contains no audio stream'):
            r.resolve_music(data, supplied)

    def test_music_volume_override_requires_file(self):
        with self.assertRaisesRegex(r.RenderError, 'requires --music-file'):
            r.resolve_music(fixture(), None, -24)

    def test_no_tts_is_explicit(self):
        provider = r.NoTTS()
        self.assertIn('NO audio', provider.fallback)
        self.assertIsNone(provider.synthesize('scene_001', '原文', {}, 3, self.root))

    def test_missing_recorded_speech_fails(self):
        with self.assertRaisesRegex(r.RenderError, 'Missing real narration'):
            r.RecordedSpeech(self.root, fixture()['scenes'])

    def test_missing_dependency_writes_failed_manifest(self):
        source = self.write(fixture())
        with patch.object(engine.shutil, 'which', return_value=None), self.assertRaisesRegex(r.RenderError, 'Missing executable'):
            r.render(source, self.root/'output')
        manifest = json.loads((self.root/'output/manifest.json').read_text())
        self.assertEqual(manifest['status'], 'failed')
        self.assertIn('ffmpeg', manifest['error'])

    def test_exhausted_scene_retry_is_recorded(self):
        source = self.write(fixture())
        font = self.root/'fake-font'
        font.write_bytes(b'fixture')
        with patch.object(engine, 'find_font', return_value=font), patch.object(engine, 'command', return_value='ffmpeg test'), patch.object(engine, 'encode_scene', side_effect=r.RenderError('encoder unavailable')), patch.object(r.time, 'sleep'):
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
        with patch.object(qc, 'probe', return_value=metadata), self.assertRaisesRegex(r.RenderError, 'format'):
            r.verify_video('bad.mp4', 3, False)


    def test_fal_video_preflight_can_run_without_api_key_or_network(self):
        data = fixture()
        images = self.root/'fal-preflight-images'
        images.mkdir()
        for scene in data['scenes']:
            if scene['visual']['type'] in ('video', 'broll'):
                Image.new('RGB', (32, 32), (24, 48, 72)).save(images/(scene['id']+'.png'))

        with patch.dict(os.environ, {}, clear=True):
            adapter = video_provider.FalH3MaxTurboVideoProvider(
                images, budget_usd=1.0, clip_seconds=5, require_api_key=False
            )
            report = adapter.preflight(data['scenes'], self.root/'fal-preflight-cache')

        self.assertEqual(report['cached_scene_ids'], [])
        self.assertEqual(report['billable_scene_ids'], ['scene_003', 'scene_004'])
        self.assertEqual(report['estimated_uncached_clips'], 2)
        self.assertAlmostEqual(report['estimated_cost_usd'], 0.285)
        self.assertFalse((self.root/'fal-preflight-cache').exists())

        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(
            r.RenderError, 'FAL_KEY is required before paid'
        ):
            adapter.get_or_generate_video(
                data['scenes'][2], 3.0, self.root/'fal-preflight-cache'/'scene_003'
            )

    def test_fal_video_preflight_enforces_budget_before_any_paid_request(self):
        data = fixture()
        images = self.root/'fal-images'
        images.mkdir()
        for scene in data['scenes']:
            if scene['visual']['type'] in ('video', 'broll'):
                Image.new('RGB', (32, 32), (24, 48, 72)).save(images/(scene['id']+'.png'))

        with patch.dict(os.environ, {'FAL_KEY': 'test-key'}):
            adapter = video_provider.FalH3MaxTurboVideoProvider(
                images, budget_usd=0.01, clip_seconds=5
            )
            with self.assertRaisesRegex(r.RenderError, 'exceeds video budget'):
                adapter.preflight(data['scenes'], self.root/'fal-cache')

        self.assertFalse((self.root/'fal-cache').exists())

    def test_fal_video_preflight_rejects_corrupt_images_before_api_requests(self):
        data = fixture()
        images = self.root/'fal-invalid-images'
        images.mkdir()
        for scene in data['scenes']:
            if scene['visual']['type'] in ('video', 'broll'):
                (images/(scene['id']+'.png')).write_bytes(b'not a real image')

        with patch.dict(os.environ, {'FAL_KEY': 'test-key'}):
            adapter = video_provider.FalH3MaxTurboVideoProvider(
                images, budget_usd=1.0, clip_seconds=5
            )
            with self.assertRaisesRegex(r.RenderError, 'invalid source image'):
                adapter.preflight(data['scenes'], self.root/'fal-invalid-cache')

        self.assertFalse((self.root/'fal-invalid-cache').exists())

    def test_fal_video_provider_reuses_cached_clip_without_rebilling(self):
        data = fixture()
        scene = data['scenes'][2]  # broll
        images = self.root/'fal-images'
        images.mkdir()
        image_path = images/(scene['id']+'.png')
        Image.new('RGB', (32, 32), (24, 48, 72)).save(image_path)
        workdir = self.root/'fal-cache'/scene['id']
        calls = {'upload': 0, 'subscribe': 0, 'download': 0}
        fake_client = types.ModuleType('fal_client')

        def upload_file(path):
            calls['upload'] += 1
            self.assertEqual(Path(path).read_bytes(), image_path.read_bytes())
            return 'https://fal.example/image.png'

        def subscribe(model_id, arguments):
            calls['subscribe'] += 1
            self.assertEqual(model_id, 'minimax/h3-max-turbo/image-to-video')
            self.assertEqual(arguments['image_url'], 'https://fal.example/image.png')
            self.assertEqual(arguments['duration'], 5)
            self.assertIn(scene['visual']['prompt'], arguments['prompt'])
            return {'video': {'url': 'https://fal.example/generated.mp4'}}

        fake_client.upload_file = upload_file
        fake_client.subscribe = subscribe

        def fake_download(url, destination):
            calls['download'] += 1
            Path(destination).write_bytes(b'fake mp4 bytes')
            return Path(destination)

        with patch.dict(os.environ, {'FAL_KEY': 'test-key'}), patch.dict(
            sys.modules, {'fal_client': fake_client}
        ), patch.object(video_provider, 'download_video', side_effect=fake_download), patch.object(
            video_provider, 'validate_video_asset',
            return_value={'path': str(workdir/'generated.mp4'), 'duration_seconds': 5.7, 'width': 768, 'height': 1366, 'codec': 'h264'}
        ), patch.object(video_provider, 'submit_fal_once',
                        side_effect=lambda model, arguments, on_enqueue: (on_enqueue('mock-request'), subscribe(model, arguments))[1]
        ):
            adapter = video_provider.FalH3MaxTurboVideoProvider(
                images, budget_usd=1.0, clip_seconds=5
            )
            first = adapter.get_or_generate_video(scene, 3.0, workdir)
            second = adapter.get_or_generate_video(scene, 3.0, workdir)

        self.assertEqual(first, second)
        self.assertTrue(first.is_file())
        self.assertEqual(calls, {'upload': 1, 'subscribe': 1, 'download': 1})
        record = json.loads((workdir/'complete.json').read_text(encoding='utf-8'))
        self.assertEqual(record['provider'], 'fal-minimax-h3-max-turbo')
        self.assertAlmostEqual(record['estimated_cost_usd'], 0.1425)

    def test_video_download_rejects_non_https_urls(self):
        with self.assertRaisesRegex(r.RenderError, 'non-HTTPS'):
            video_provider.download_video('http://example.com/video.mp4', self.root/'video.mp4')

    def test_edge_tts_uses_verbatim_text_and_voice_rate_without_network(self):
        calls = {}

        class FakeCommunicate:
            def __init__(self, text, voice, rate):
                calls.update(text=text, voice=voice, rate=rate)

            async def save(self, path):
                Path(path).write_bytes(b'fake audio bytes')

        fake_edge_tts = types.SimpleNamespace(__version__='test-version', Communicate=FakeCommunicate)

        with patch.dict(sys.modules, {'edge_tts': fake_edge_tts}), patch.object(
            tts, 'probe',
            return_value={'streams': [{'codec_type': 'audio'}], 'format': {'duration': '2.5'}}
        ):
            provider = r.EdgeTTS('zh-CN-YunxiNeural')
            audio = provider.synthesize(
                'scene_001', '这段口播必须逐字保留。', {'speed': 0.95}, 3.0, self.root
            )

        self.assertEqual(calls, {
            'text': '这段口播必须逐字保留。',
            'voice': 'zh-CN-YunxiNeural',
            'rate': '-5%',
        })
        self.assertTrue(audio.is_file())
        self.assertEqual(provider.speech_status, 'generated_audio')
        self.assertIn('external Edge TTS service', provider.provider_notice)

    def test_edge_tts_rejects_oversized_speech_instead_of_truncating(self):
        class FakeCommunicate:
            def __init__(self, text, voice, rate):
                pass

            async def save(self, path):
                Path(path).write_bytes(b'fake audio bytes')

        fake_edge_tts = types.SimpleNamespace(__version__='test-version', Communicate=FakeCommunicate)

        with patch.dict(sys.modules, {'edge_tts': fake_edge_tts}), patch.object(
            tts, 'probe',
            return_value={'streams': [{'codec_type': 'audio'}], 'format': {'duration': '5.0'}}
        ):
            provider = r.EdgeTTS('zh-CN-YunxiNeural')
            with self.assertRaisesRegex(r.RenderError, 'Refusing to truncate'):
                provider.synthesize('scene_001', '完整旁白', {'speed': 1.0}, 3.0, self.root)

    def test_edge_tts_fits_slightly_overlong_speech_before_video_encoding(self):
        class FakeCommunicate:
            def __init__(self, text, voice, rate):
                pass

            async def save(self, path):
                Path(path).write_bytes(b'fake audio bytes')

        fake_edge_tts = types.SimpleNamespace(__version__='test-version', Communicate=FakeCommunicate)
        probe_results = [
            {'streams': [{'codec_type': 'audio'}], 'format': {'duration': '3.05'}},
            {'streams': [{'codec_type': 'audio'}], 'format': {'duration': '2.98'}},
        ]
        with patch.dict(sys.modules, {'edge_tts': fake_edge_tts}), patch.object(
            tts, 'probe', side_effect=probe_results
        ), patch.object(tts, 'command') as ffmpeg:
            provider = r.EdgeTTS('zh-CN-YunxiNeural')
            audio = provider.synthesize(
                'scene_001', '完整旁白', {'speed': 1.0}, 3.0, self.root
            )

        self.assertEqual(audio.name, 'scene_001.edge-tts-fitted.mp3')
        self.assertTrue(ffmpeg.called)
        args = ffmpeg.call_args.args[0]
        self.assertTrue(any(str(arg).startswith('atempo=') for arg in args))
        filter_index = args.index('-filter:a')
        self.assertEqual(args[filter_index + 1], 'atempo=1.07018')


    def test_edge_tts_rate_bounds(self):
        self.assertEqual(r.EdgeTTS.rate_for({'speed': 1.0}), '+0%')
        self.assertEqual(r.EdgeTTS.rate_for({'speed': 1.2}), '+20%')
        with self.assertRaisesRegex(r.RenderError, 'between 0.5 and 2.0'):
            r.EdgeTTS.rate_for({'speed': 2.5})


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
        self.assertTrue(any('Static image/placeholder fallback used for video/broll scenes' in item for item in first['fallbacks']))
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

    def test_supplied_image_asset_is_used_and_invalidates_only_its_scene_cache(self):
        data = fixture()
        source = self.root/'storyboard.json'
        source.write_text(json.dumps(data, ensure_ascii=False))
        original = source.read_bytes()
        assets = self.root/'images'
        assets.mkdir()
        image_path = assets/'scene_001.png'
        r.Image.new('RGB', (640, 640), (25, 80, 120)).save(image_path)
        output = self.root/'asset-output'

        first = r.render(source, output, FONT, assets_dir=assets)
        self.assertEqual(first['status'], 'complete')
        self.assertFalse(first['scenes'][0]['placeholder'])
        self.assertEqual(first['scenes'][0]['visual_asset'], 'scene_001.png')
        for scene in first['scenes'][1:]:
            if scene['visual_type'] in ('title_card', 'quote_card'):
                self.assertFalse(scene['placeholder'])
                self.assertEqual(scene['visual_source'], scene['visual_type'])
            else:
                self.assertTrue(scene['placeholder'])
        self.assertFalse(any('scene_002' in item for item in first['fallbacks']))
        self.assertTrue(any('scene_003' in item for item in first['fallbacks']))
        self.assertEqual(source.read_bytes(), original)

        second = r.render(source, output, FONT, assets_dir=assets)
        self.assertTrue(all(scene['cache_hit'] for scene in second['scenes']))

        r.Image.new('RGB', (640, 640), (120, 40, 20)).save(image_path)
        third = r.render(source, output, FONT, assets_dir=assets)
        self.assertFalse(third['scenes'][0]['cache_hit'])
        self.assertTrue(all(scene['cache_hit'] for scene in third['scenes'][1:]))
        self.assertEqual(source.read_bytes(), original)

    def test_background_music_mixes_with_narration_and_is_recorded(self):
        data = fixture()
        source = self.root/'storyboard.json'
        source.write_text(json.dumps(data, ensure_ascii=False))
        audio_dir = self.root/'narration'
        audio_dir.mkdir()
        for scene in data['scenes']:
            r.command([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'lavfi', '-i', 'sine=frequency=660:duration=1',
                '-ar', '48000', '-ac', '2', audio_dir/(scene['id']+'.wav')
            ])
        music = self.root/'music.wav'
        r.command([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'sine=frequency=220:duration=2',
            '-ar', '48000', '-ac', '2', music
        ])

        result = r.render(
            source, self.root/'mixed-output', FONT, speech_dir=audio_dir,
            speech_provider_name='test-tts', speech_voice='test-voice',
            music_file=music
        )
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['qc']['audio_codec'], 'aac')
        self.assertLessEqual(abs(result['qc']['duration_seconds'] - 15), 0.1)
        self.assertEqual(result['music']['status'], 'supplied')
        self.assertEqual(result['music']['file'], 'music.wav')
        self.assertEqual(result['music']['sha256'], r.digest(music))
        self.assertEqual(result['music']['volume_db'], -24)
        self.assertFalse(any('music omitted' in item for item in result['fallbacks']))

    def test_background_music_can_be_the_only_audio_track(self):
        data = fixture()
        source = self.root/'music-only-storyboard.json'
        source.write_text(json.dumps(data, ensure_ascii=False))
        music = self.root/'music-only.wav'
        r.command([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'sine=frequency=330:duration=2',
            '-ar', '48000', '-ac', '2', music
        ])

        result = r.render(source, self.root/'music-only-output', FONT, music_file=music)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['speech_status'], 'fallback_no_audio')
        self.assertEqual(result['qc']['audio_codec'], 'aac')
        self.assertEqual(result['music']['status'], 'supplied')
        self.assertTrue(any('NO audio track' in item for item in result['fallbacks']))

    def test_supplied_aligned_subtitles_are_validated_and_burned(self):
        data = fixture()
        source = self.root/'storyboard.json'
        source.write_text(json.dumps(data, ensure_ascii=False))
        custom_srt = self.root/'aligned.srt'
        custom_srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n这是第一条字幕。\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n这是第二条字幕。\n",
            encoding='utf-8'
        )
        result = r.render(source, self.root/'aligned-output', FONT, subtitle_file=custom_srt)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['subtitle_alignment']['status'], 'supplied_srt')
        self.assertEqual(result['subtitle_alignment']['cue_count'], 2)
        self.assertEqual((self.root/'aligned-output/subtitles.srt').read_text(), custom_srt.read_text())
        self.assertFalse(any('scene-proportional timing' in item for item in result['fallbacks']))

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
