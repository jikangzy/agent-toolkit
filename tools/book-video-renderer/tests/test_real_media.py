"""Formal source/fixture checks and offline paid-boundary regressions.

Fake fal calls below prove adapter behavior, never live service success.
"""
import copy
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import book_video_renderer.providers.video as video
import book_video_renderer.renderer as engine
from book_video_renderer.providers.tts import RecordedSpeech
from book_video_renderer.validator import load_storyboard
from book_video_renderer.models import ROOT, RenderError
from book_video_renderer.manifest import digest, save_json
from book_video_renderer.renderer import render
from PIL import Image
from verify_real_media import verify as verify_media

HERE = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples/book-video/naval-test-001'
VALIDATION = SAMPLE / 'validation'
FONT = os.environ.get('BOOK_VIDEO_FONT')


class FormalSourcesTests(unittest.TestCase):
    def test_original_pngs_decode_and_match_checked_report(self):
        report = json.loads((VALIDATION/'source-images-report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['image_count'], 8)
        self.assertEqual([x['scene_id'] for x in report['images']], [f'scene_{i:03}' for i in range(2, 10)])
        for record in report['images']:
            path = ROOT / record['path']
            self.assertEqual(path.stat().st_size, record['size_bytes'])
            self.assertEqual(digest(path), record['sha256'])
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                self.assertEqual(image.format, 'PNG')
                self.assertEqual(image.size, (record['width'], record['height']))
                self.assertEqual(image.mode, record['mode'])
                self.assertLess(abs(image.width/image.height - 9/16), .01)

    def test_derived_fixture_preserves_all_original_fields_and_source(self):
        path = SAMPLE/'storyboard.json'
        before = path.read_bytes()
        source = load_storyboard(path)
        fixture = load_storyboard(VALIDATION/'two-scene-storyboard.json')
        self.assertEqual(fixture['scenes'], source['scenes'][1:3])
        self.assertEqual([s['id'] for s in fixture['scenes']], ['scene_002', 'scene_003'])
        self.assertEqual(fixture['format']['target_duration_seconds'], sum(s['duration_seconds'] for s in fixture['scenes']))
        self.assertEqual(path.read_bytes(), before)
        # Use canonical Git LF hash so Windows CRLF checkout does not weaken the
        # content-integrity assertion or require rewriting the original.
        info = json.loads((VALIDATION/'storyboard-integrity.json').read_text())
        self.assertEqual(hashlib.sha256(before.replace(b'\r\n', b'\n')).hexdigest(), info['remote_git_content_sha256'])

    def test_actual_cli_runs_full_and_two_preflight_with_network_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            for source, cap, count in ((SAMPLE/'storyboard.json', '1.20', 8),
                                       (VALIDATION/'two-scene-storyboard.json', '.40', 2)):
                report = temp/f'{count}.json'
                process = subprocess.run([sys.executable, str(HERE/'offline_preflight.py'),
                    '--report', str(report), str(source), '--output', str(temp/f'run-{count}'),
                    '--assets-dir', str(SAMPLE/'source-images'), '--ai-video-provider', 'fal-h3-max-turbo',
                    '--video-clip-seconds', '5', '--video-budget-usd', cap, '--video-preflight-only'],
                    capture_output=True, encoding='utf-8', timeout=60)
                self.assertEqual(process.returncode, 0, process.stderr)
                data = json.loads(report.read_text(encoding='utf-8'))
                self.assertEqual(data['video_preflight']['estimated_uncached_clips'], count)
                self.assertEqual(data['execution_guard']['network_attempts_blocked'], 0)
                self.assertEqual(data['execution_guard']['generation_api_attempts_blocked'], 0)
                self.assertEqual(data['video_preflight']['dynamic_scene_ids'], [f'scene_{i:03}' for i in range(2, 2+count)])


class PaidBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.images = self.root/'images'
        self.images.mkdir()
        self.scenes = json.loads((VALIDATION/'two-scene-storyboard.json').read_text(encoding='utf-8'))['scenes']
        for scene in self.scenes:
            Image.new('RGB', (32, 56), 'navy').save(self.images/(scene['id']+'.png'))
        self.fake = types.SimpleNamespace(upload_file=lambda path: 'https://fake/image.png',
                                          subscribe=lambda *args, **kw: {'video': {'url': 'https://fake/video.mp4'}})
        self.cache = self.root/'cache'

    def provider(self, budget=.40):
        return video.FalH3MaxTurboVideoProvider(self.images, budget, require_api_key=False)

    def test_rejects_nonfinite_and_nonpositive_budget(self):
        for budget in (float('nan'), float('inf'), -.1, 0):
            with self.subTest(budget=budget), self.assertRaises(RenderError):
                self.provider(budget)

    def test_preflight_rejects_budget_before_external_boundary(self):
        with patch.dict(sys.modules, {'fal_client': self.fake}), patch.object(self.fake, 'upload_file') as upload:
            with self.assertRaisesRegex(RenderError, 'exceeds video budget'):
                self.provider(.1).preflight(self.scenes, self.cache)
            upload.assert_not_called()

    def test_input_changed_after_preflight_is_rejected(self):
        provider = self.provider()
        provider.preflight(self.scenes, self.cache)
        changed = copy.deepcopy(self.scenes[0])
        changed['visual']['prompt'] += ' altered'
        with patch.dict(os.environ, {'FAL_KEY': 'test-only'}), self.assertRaisesRegex(RenderError, 'differs from preflight'):
            provider.get_or_generate_video(changed, 10, self.cache/changed['id'])

    def test_failed_or_uncertain_request_is_reserved_across_restart_and_secret_redacted(self):
        provider = self.provider()
        provider.preflight(self.scenes, self.cache)
        self.fake.subscribe = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('secret-value'))
        def fail_after_receipt(*args, **kwargs):
            kwargs['on_enqueue']('known-test-id')
            return self.fake.subscribe()
        with patch.dict(os.environ, {'FAL_KEY': 'secret-value'}), patch.dict(sys.modules, {'fal_client': self.fake}), patch.object(video, 'submit_fal_once', side_effect=fail_after_receipt):
            with self.assertRaises(RenderError) as error:
                provider.get_or_generate_video(self.scenes[0], 10, self.cache/'scene_002')
            self.assertNotIn('secret-value', str(error.exception))
            self.assertIsNone(error.exception.__cause__)
            with self.assertRaisesRegex(RenderError, 'prior request'):
                self.provider().get_or_generate_video(self.scenes[0], 10, self.cache/'scene_002')
        ledger = json.loads((self.cache/'request-ledger.json').read_text())
        self.assertEqual(len(ledger['attempts']), 1)
        self.assertEqual(ledger['attempts'][0]['paid_request_attempts'], 1)
        self.assertEqual(ledger['attempts'][0]['request_id'], 'known-test-id')
        self.assertEqual(ledger['attempts'][0]['estimated_reserved_usd'], provider.estimated_clip_cost)
        self.assertNotIn('secret-value', json.dumps(ledger))

    def test_reservations_reduce_budget_for_other_scenes(self):
        self.cache.mkdir()
        save_json(self.cache/'request-ledger.json', {'version': 1, 'attempts': [
            {'input_key': 'different-input', 'estimated_reserved_usd': .285}]})
        with self.assertRaisesRegex(RenderError, 'exceeds video budget'):
            self.provider().preflight(self.scenes[:1], self.cache)

    def test_corrupt_ledger_fails_closed(self):
        self.cache.mkdir()
        (self.cache/'request-ledger.json').write_text('{}')
        with self.assertRaisesRegex(RenderError, 'Invalid request ledger'):
            self.provider().preflight(self.scenes, self.cache)

    def test_concurrent_generation_lock_fails_closed(self):
        provider = self.provider()
        provider.preflight(self.scenes, self.cache)
        self.cache.mkdir()
        (self.cache/'request-ledger.lock').write_text('another process')
        with patch.dict(os.environ, {'FAL_KEY': 'test-only'}), self.assertRaisesRegex(RenderError, 'locked'):
            provider.get_or_generate_video(self.scenes[0], 10, self.cache/'scene_002')

    def test_cache_key_includes_source_image_and_visual_configuration(self):
        provider = self.provider()
        scene = self.scenes[0]
        image = self.images/(scene['id']+'.png')
        before = provider._input_key(scene, image)
        Image.new('RGB', (32, 56), 'red').save(image)
        self.assertNotEqual(before, provider._input_key(scene, image))
        changed = copy.deepcopy(scene)
        changed['visual']['motion'] = 'changed'
        self.assertNotEqual(provider._input_key(scene, image), provider._input_key(changed, image))

    def test_cached_mp4_extension_and_matching_hash_do_not_bypass_decode(self):
        provider = self.provider()
        scene = self.scenes[0]
        image = self.images/(scene['id']+'.png')
        work = self.cache/scene['id']
        work.mkdir(parents=True)
        (work/'generated.mp4').write_bytes(b'not a video')
        save_json(work/'complete.json', dict(input_key=provider._input_key(scene, image),
            sha256=digest(work/'generated.mp4'), provider=provider.provider_name,
            model=provider.model_id, origin='generated_video', source_image_sha256=digest(image)))
        with patch.object(video, 'validate_video_asset', side_effect=RenderError('full decode failed')):
            self.assertIsNone(provider._valid_cache(scene, image, work))

    def test_full_decode_failure_is_not_accepted_even_with_valid_headers(self):
        path = self.root/'corrupt.mp4'
        path.write_bytes(b'corrupt')
        info = {'format': {'duration': '5'}, 'streams': [{'codec_type':'video', 'codec_name':'h264',
                'width': 360, 'height': 640, 'avg_frame_rate':'24/1'}]}
        with patch.object(video, 'probe', return_value=info), patch.object(video, 'command', side_effect=RenderError('decode failed')):
            with self.assertRaisesRegex(RenderError, 'decode failed'):
                video.validate_video_asset(path)

    def test_provider_failure_is_bound_to_scene_and_unstarted_scenes_remain_explicit(self):
        provider = types.SimpleNamespace(provider_name='test-failing-provider',
            preflight=lambda *a: {'billable_scene_ids':['scene_002','scene_003']},
            get_or_generate_video=lambda *a: (_ for _ in ()).throw(RenderError('test provider failed')))
        output = self.root/'failed-render'
        with patch.object(engine.shutil, 'which', return_value='test-tool'), patch.object(engine, 'find_font', return_value=Path(__file__)):
            with self.assertRaisesRegex(RenderError, 'test provider failed'):
                render(VALIDATION/'two-scene-storyboard.json', output, assets_dir=self.images,
                       video_provider=provider, require_video_assets=True)
        manifest = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['scenes'][0]['visual_source'], 'provider_failed')
        self.assertEqual(manifest['scenes'][0]['status'], 'failed')
        self.assertEqual(manifest['scenes'][1]['visual_source'], 'not_generated')
        self.assertEqual(manifest['video_provider'], 'test-failing-provider')
        self.assertEqual(manifest['overall_status'], 'failed')

    def test_supplied_audio_label_does_not_claim_synthesis(self):
        for scene in self.scenes:
            (self.root/(scene['id']+'.wav')).write_bytes(b'test')
        supplied = RecordedSpeech(self.root, self.scenes, provider_name='supplied-audio')
        self.assertEqual(supplied.speech_status, 'provided_audio')


@unittest.skipUnless(FONT and shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg + CJK font required')
class SyntheticProviderIntegrationTests(unittest.TestCase):
    setUp = PaidBoundaryTests.setUp
    provider = PaidBoundaryTests.provider
    def test_mock_provider_to_renderer_and_cache_with_actual_decoded_synthetic_video(self):
        # This is an offline integration test, NOT a real fal output acceptance.
        clip = self.root/'synthetic.mp4'
        video.command(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                       'testsrc2=size=180x320:rate=24:duration=1','-an','-c:v','libx264',
                       '-pix_fmt','yuv420p',clip])
        fixture = load_storyboard(VALIDATION/'two-scene-storyboard.json')
        provider = self.provider()
        output = self.root/'render'
        def download(url, dest):
            shutil.copyfile(clip, dest)
            return Path(dest)
        def submit(model, arguments, on_enqueue):
            on_enqueue('synthetic-test-request')
            return self.fake.subscribe(model, arguments)
        with patch.dict(os.environ, {'FAL_KEY':'test-only'}), patch.dict(sys.modules, {'fal_client':self.fake}), patch.object(video, 'download_video', side_effect=download), patch.object(video, 'submit_fal_once', side_effect=submit):
            manifest = render(VALIDATION/'two-scene-storyboard.json', output, FONT, attempts=1,
                              assets_dir=self.images, require_video_assets=True, video_provider=provider)
        self.assertEqual(manifest['qc']['full_decode_status'], 'PASS')
        self.assertEqual(manifest['qc']['scene_count'], 2)
        self.assertEqual(manifest['speech_status'], 'fallback_no_audio')
        audited = verify_media(VALIDATION/'two-scene-storyboard.json', output, self.images)
        self.assertEqual(audited['status'], 'LOCAL_PROVENANCE_AND_QC_PASS')
        for scene in manifest['scenes']:
            self.assertEqual(scene['visual_source'], 'video')
            self.assertEqual(scene['video_asset_sha256'], digest(clip))
            self.assertEqual(scene['video_provenance']['cache_status'], 'miss_generated')
            self.assertEqual(scene['video_provenance']['video_metadata']['full_decode_status'], 'PASS')
        cached_provider = self.provider()
        cached = cached_provider.preflight(fixture['scenes'], output/'video-provider-cache')
        self.assertEqual(cached['estimated_uncached_clips'], 0)
        self.assertEqual(cached['cached_scene_ids'], ['scene_002','scene_003'])
        with patch.dict(os.environ, {'FAL_KEY': ''}):
            for scene in fixture['scenes']:
                self.assertIsNotNone(cached_provider.get_or_generate_video(scene, scene['duration_seconds'], output/'video-provider-cache'/scene['id']))
                self.assertEqual(cached_provider.scene_records[scene['id']]['cache_status'], 'hit')
        manifest['scenes'][0]['video_provenance']['input_key'] = 'wrong'
        save_json(output/'manifest.json', manifest)
        with self.assertRaisesRegex(RenderError, 'input fingerprint mismatch'):
            verify_media(VALIDATION/'two-scene-storyboard.json', output, self.images)


class QueueSubmissionTests(unittest.TestCase):
    def test_exactly_one_post_then_get_polling_and_receipt_before_poll(self):
        calls, receipts = [], []
        outputs = [dict(request_id='test-request',status_url='https://queue.fal.run/status',response_url='https://queue.fal.run/result'),
                   dict(status='IN_PROGRESS'),dict(status='COMPLETED'),dict(video=dict(url='https://example.test/clip.mp4'))]
        def open_request(req, timeout):
            calls.append(req.get_method())
            if req.get_method() == 'GET':
                self.assertEqual(receipts, ['test-request'])
            return io.BytesIO(json.dumps(outputs.pop(0)).encode())
        with patch.dict(os.environ, {'FAL_KEY':'test-only'}), patch.object(video, 'build_opener', return_value=types.SimpleNamespace(open=open_request)), patch.object(video.time,'sleep'):
            result = video.submit_fal_once(video.FAL_H3_MAX_TURBO_MODEL, {}, receipts.append)
        self.assertEqual(calls, ['POST','GET','GET','GET'])
        self.assertIn('video', result)

    def test_post_transport_error_never_retries(self):
        opener=types.SimpleNamespace(open=Mock(side_effect=OSError('test disconnect')))
        with patch.dict(os.environ, {'FAL_KEY':'test-only'}), patch.object(video,'build_opener',return_value=opener):
            with self.assertRaises(OSError):
                video.submit_fal_once(video.FAL_H3_MAX_TURBO_MODEL, {}, lambda request_id: None)
        self.assertEqual(opener.open.call_count, 1)

    def test_untrusted_receipt_cannot_receive_authorization_header(self):
        receipt=dict(request_id='test-request',status_url='https://evil.test/status',response_url='https://queue.fal.run/result')
        opener=types.SimpleNamespace(open=Mock(return_value=io.BytesIO(json.dumps(receipt).encode())))
        with patch.dict(os.environ, {'FAL_KEY':'test-only'}), patch.object(video,'build_opener',return_value=opener):
            with self.assertRaisesRegex(RenderError,'Untrusted fal queue'):
                video.submit_fal_once(video.FAL_H3_MAX_TURBO_MODEL, {}, lambda request_id: None)
        self.assertEqual(opener.open.call_count,1)

    def test_authenticated_redirects_fail_closed(self):
        with self.assertRaisesRegex(RenderError,'Redirect refused'):
            video._NoRedirect().redirect_request(None,None,302,'test',{},'https://evil.test/')
