"""Unit tests for the one-command book-video pipeline orchestrator."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "pipeline.py"
spec = importlib.util.spec_from_file_location("book_video_pipeline", MODULE)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)

EXAMPLE = pipeline.ROOT / "examples" / "book-video" / "naval-test-001" / "storyboard.json"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="book-video-pipeline ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {
            "status": "complete",
            "overall_status": "completed",
            "final_video_path": str(self.root / "output" / "final.mp4"),
            "fallbacks": [],
            "qc": {"status": "passed"},
        }

    def test_offline_mode_skips_narration_preflight(self):
        output = self.root / "output"
        images = self.root / "images"
        with patch.object(pipeline.renderer, "render", return_value=self.manifest) as render, patch.object(
            pipeline.prepare_narration, "prepare"
        ) as prepare:
            result = pipeline.run_pipeline(
                EXAMPLE, output, assets_dir=images, tts_provider="none"
            )

        prepare.assert_not_called()
        args, kwargs = render.call_args
        self.assertEqual(args[0], EXAMPLE.resolve())
        self.assertEqual(args[1], output.resolve())
        self.assertEqual(kwargs["assets_dir"], images.resolve())
        self.assertIsNone(result["narration_preflight"])

    def test_edge_tts_mode_runs_preflight_then_uses_aligned_subtitles(self):
        output = self.root / "output"
        work_dir = self.root / ".local" / "runs" / "naval-test"
        preflight = {
            "audio_cache": {"scene_001": "hit", "scene_002": "miss"},
            "derived_target_duration_seconds": 120,
        }
        with patch.object(pipeline.prepare_narration, "prepare", return_value=preflight) as prepare, patch.object(
            pipeline.renderer, "render", return_value=self.manifest
        ) as render:
            result = pipeline.run_pipeline(
                EXAMPLE,
                output,
                tts_provider="edge-tts",
                tts_voice="zh-CN-YunxiNeural",
                force_tts=True,
                work_dir=work_dir,
            )

        prepare_args = prepare.call_args.args
        self.assertEqual(prepare_args[0], EXAMPLE.resolve())
        self.assertEqual(prepare_args[1], work_dir.resolve() / "audio")
        self.assertEqual(prepare_args[2], work_dir.resolve() / "storyboard.render.json")
        self.assertEqual(prepare_args[3], output.resolve() / "timing-report.json")
        self.assertEqual(prepare_args[4], "zh-CN-YunxiNeural")
        self.assertEqual(prepare_args[6], output.resolve() / "aligned-subtitles.srt")
        self.assertTrue(prepare_args[7])

        render_args, render_kwargs = render.call_args
        self.assertEqual(render_args[0], work_dir.resolve() / "storyboard.render.json")
        self.assertEqual(render_args[1], output.resolve())
        self.assertEqual(render_kwargs["speech_dir"], work_dir.resolve() / "audio")
        self.assertEqual(render_kwargs["speech_provider_name"], "edge-tts")
        self.assertEqual(render_kwargs["speech_voice"], "zh-CN-YunxiNeural")
        self.assertEqual(render_kwargs["subtitle_file"], output.resolve() / "aligned-subtitles.srt")
        self.assertEqual(result["narration_preflight"], preflight)

    def test_invalid_music_fails_before_any_external_tts_request(self):
        with patch.object(pipeline.prepare_narration, "prepare") as prepare:
            with self.assertRaisesRegex(pipeline.renderer.RenderError, "does not exist"):
                pipeline.run_pipeline(
                    EXAMPLE,
                    self.root / "output",
                    tts_provider="edge-tts",
                    music_file=self.root / "missing-music.mp3",
                )
        prepare.assert_not_called()

    def test_force_tts_requires_edge_tts(self):
        with self.assertRaisesRegex(pipeline.renderer.RenderError, "--force-tts requires"):
            pipeline.run_pipeline(
                EXAMPLE, self.root / "output", tts_provider="none", force_tts=True
            )

    def test_external_subtitles_cannot_override_edge_tts_alignment(self):
        with self.assertRaisesRegex(pipeline.renderer.RenderError, "--subtitle-file cannot be combined"):
            pipeline.run_pipeline(
                self.root / "not-read.json",
                self.root / "output",
                tts_provider="edge-tts",
                subtitle_file=self.root / "external.srt",
            )


if __name__ == "__main__":
    unittest.main()
