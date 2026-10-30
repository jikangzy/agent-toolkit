import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from book_video_renderer.providers.hyperframes import HyperFramesVideoProvider, composition
from book_video_renderer.models import RenderError


SCENE = {'id': 'scene_002', 'duration_seconds': 10, 'narration': '原文',
         'onscreen_text': '财富与幸福', 'visual': {'type': 'broll'}}


class HyperFramesTests(unittest.TestCase):
    def test_composition_retains_id_and_text_and_timing(self):
        html = composition(SCENE, 10)
        self.assertIn('data-composition-id="scene_002"', html)
        self.assertIn('data-duration="10"', html)
        self.assertIn('>财富与幸福</span>', html)
        self.assertIn("tl.to('.keyword'", html)
        self.assertIn('window.__timelines', html)
        self.assertIn('scale:1.18', html)

    def test_scene_three_uses_its_storyboard_zoom_hint(self):
        scene = {
            **SCENE,
            'id': 'scene_003',
            'visual': {'type': 'broll', 'motion': 'slow zoom-in'},
        }
        html = composition(scene, 13)
        self.assertIn('scale:1.04', html)
        self.assertIn('scale:1.18', html)
        self.assertNotIn('x:65', html)

    def test_storyboard_motion_maps_to_camera_tweens(self):
        cases = [
            ('slow pan right', ('x:-65', 'x:65')),
            ('slow pan left', ('x:65', 'x:-65')),
            ('slow pan down', ('y:-65', 'y:65')),
            ('slow pan up', ('y:65', 'y:-65')),
            ('slow zoom-out', ('scale:1.18', 'scale:1.04')),
            ('slow zoom-in', ('scale:1.04', 'scale:1.18')),
            ('slow push-in', ('scale:1.04', 'scale:1.18')),
            ('slow pan forward', ('scale:1.04', 'scale:1.18')),
            ('slow fade-in', ('opacity:0', 'opacity:1')),
        ]
        for motion, expected in cases:
            with self.subTest(motion=motion):
                scene = {
                    **SCENE,
                    'id': 'scene_777',
                    'visual': {'type': 'broll', 'motion': motion},
                }
                html = composition(scene, 10)
                for fragment in expected:
                    self.assertIn(fragment, html)

    def test_html_escapes_storyboard_content(self):
        html = composition({**SCENE, 'onscreen_text': '<script> & text'}, 10)
        self.assertIn('&lt;script&gt; &amp; text', html)

    def test_missing_image_fails_without_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / 'cli'
            gsap = Path(tmp) / 'gsap.js'
            executable.write_text('')
            gsap.write_text('gsap')
            with patch('book_video_renderer.providers.hyperframes.subprocess.run', return_value=SimpleNamespace(stdout='0.8.221')):
                provider = HyperFramesVideoProvider(tmp, executable, gsap)
            with self.assertRaises(RenderError):
                provider.get_or_generate_video(SCENE, 10, Path(tmp) / 'work')

    def test_cli_invocation_cache_and_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cli = root / 'hyperframes'
            gsap = root / 'gsap.js'
            image = root / 'scene_002.png'
            cli.write_text('cli')
            gsap.write_text('gsap')
            image.write_bytes(b'image one')
            commands = []
            def run(args, **kwargs):
                commands.append(args)
                if '--version' in args:
                    return SimpleNamespace(stdout='0.8.221', returncode=0)
                Path(args[args.index('--output') + 1]).write_bytes(b'video')
                return SimpleNamespace(stdout='', stderr='', returncode=0)
            with patch('book_video_renderer.providers.hyperframes.subprocess.run', side_effect=run), \
                 patch('book_video_renderer.providers.hyperframes.verify_video', return_value={'ok': True}):
                provider = HyperFramesVideoProvider(root, cli, gsap)
                work = root / 'work'
                first = provider.get_or_generate_video(SCENE, 10, work)
                self.assertFalse(provider.scene_records['scene_002']['cache_hit'])
                self.assertEqual(first, provider.get_or_generate_video(SCENE, 10, work))
                self.assertTrue(provider.scene_records['scene_002']['cache_hit'])
                image.write_bytes(b'image two')
                second = provider.get_or_generate_video(SCENE, 10, work)
                self.assertNotEqual(first, second)
                third = provider.get_or_generate_video({**SCENE, 'narration': '不同'}, 10, work)
                self.assertNotEqual(second, third)
                renders = [args for args in commands if 'render' in args]
                self.assertEqual(len(renders), 3)
                self.assertIn('--fps', renders[0])
                self.assertIn('30', renders[0])
                # Animation implementation and GSAP changes are part of the provider fingerprint.
                gsap.write_text('gsap with altered animation dependency')
                changed_provider = HyperFramesVideoProvider(root, cli, gsap)
                self.assertNotEqual(provider.cache_key, changed_provider.cache_key)
                changed = changed_provider.get_or_generate_video(SCENE, 10, work)
                self.assertNotEqual(third, changed)
                self.assertFalse(changed_provider.scene_records['scene_002']['cache_hit'])
                first.write_bytes(b'corrupt')
                image.write_bytes(b'image one')
                provider.get_or_generate_video(SCENE, 10, work)
                self.assertFalse(provider.scene_records['scene_002']['cache_hit'])

    def test_native_transition_uses_gsap_and_preserves_audio_mapping(self):
        from book_video_renderer.hyperframes_transition import assemble
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clips = [root / 'one.mp4', root / 'two.mp4']
            for clip in clips:
                clip.write_bytes(b'scene')
            (root / 'unburned.mp4').write_bytes(b'concat')
            gsap = root / 'gsap.js'
            gsap.write_text('gsap')
            provider = SimpleNamespace(gsap_path=gsap, executable='hyperframes')
            commands = []
            def command(args):
                commands.append(args)
                Path(args[-1]).write_bytes(b'generated')
            def run(args, **kwargs):
                Path(args[args.index('--output') + 1]).write_bytes(b'video')
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            scenes = [{**SCENE, 'duration_seconds': 10}, {**SCENE, 'id': 'scene_003', 'duration_seconds': 13}]
            with patch('book_video_renderer.hyperframes_transition.command', side_effect=command), \
                 patch('book_video_renderer.hyperframes_transition.subprocess.run', side_effect=run), \
                 patch('book_video_renderer.hyperframes_transition.verify_video'):
                assemble(provider, clips, scenes, root, True)
            document = (root / 'hyperframes-transition/index.html').read_text()
            self.assertIn('data-duration="23.000000"', document)
            self.assertIn('data-start="10.000000"', document)
            self.assertIn("tl.to('.layer-0'", document)
            self.assertIn('1:a:0', commands[-1])


if __name__ == '__main__':
    unittest.main()
