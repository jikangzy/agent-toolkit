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
        videos = self.root / "videos"
        with patch.object(pipeline.renderer, "render", return_value=self.manifest) as render, patch.object(
            pipeline.prepare_narration, "prepare"
        ) as prepare:
            result = pipeline.run_pipeline(
                EXAMPLE, output, assets_dir=images, video_assets_dir=videos, tts_provider="none"
            )

        prepare.assert_not_called()
        args, kwargs = render.call_args
        self.assertEqual(args[0], EXAMPLE.resolve())
        self.assertEqual(args[1], output.resolve())
        self.assertEqual(kwargs["assets_dir"], images.resolve())
        self.assertEqual(kwargs["video_assets_dir"], videos.resolve())
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

    def test_supplied_audio_mode_derives_timing_and_renders_without_network_tts(self):
        output = self.root / "output"
        work_dir = self.root / ".local" / "runs" / "supplied"
        audio_dir = self.root / "audio"
        audio_dir.mkdir()
        for scene_id in ("scene_001", "scene_002"):
            (audio_dir / f"{scene_id}.wav").write_bytes(b"wav")
        subtitle = self.root / "aligned.srt"
        subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\n字幕\n", encoding="utf-8")

        data = {
            "format": {"target_duration_seconds": 6, "fps": 30},
            "music": {"enabled": False, "volume_db": -24},
            "voice": {"speed": 1.0},
            "scenes": [
                {"id": "scene_001", "duration_seconds": 3, "narration": "一", "onscreen_text": "一"},
                {"id": "scene_002", "duration_seconds": 3, "narration": "二", "onscreen_text": "二"},
            ],
        }
        derived = {
            **data,
            "format": {"target_duration_seconds": 7, "fps": 30},
            "scenes": [
                {**data["scenes"][0], "duration_seconds": 3.5},
                {**data["scenes"][1], "duration_seconds": 3.5},
            ],
        }
        scene_report = {
            "scene_001": {"speech_seconds": 3.2, "original_scene_seconds": 3, "allocated_scene_seconds": 3.5},
            "scene_002": {"speech_seconds": 3.2, "original_scene_seconds": 3, "allocated_scene_seconds": 3.5},
        }
        with patch.object(pipeline.renderer, "load_storyboard", return_value=data), patch.object(
            pipeline.renderer, "resolve_music", return_value=(None, None)
        ), patch.object(
            pipeline.renderer, "probe",
            return_value={"streams": [{"codec_type": "audio"}], "format": {"duration": "3.2"}},
        ), patch.object(
            pipeline.prepare_narration, "allocate_scene_durations", return_value=(derived, scene_report)
        ) as allocate, patch.object(
            pipeline.renderer, "save_json"
        ) as save_json, patch.object(
            pipeline.renderer, "render", return_value=self.manifest
        ) as render, patch.object(
            pipeline.prepare_narration, "prepare"
        ) as online_prepare:
            result = pipeline.run_pipeline(
                EXAMPLE,
                output,
                tts_provider="supplied",
                tts_audio_dir=audio_dir,
                tts_audio_provider="edge-tts",
                tts_audio_voice="zh-CN-YunxiNeural",
                subtitle_file=subtitle,
                work_dir=work_dir,
            )

        online_prepare.assert_not_called()
        allocate.assert_called_once()
        self.assertEqual(allocate.call_args.args[1], {"scene_001": 3.2, "scene_002": 3.2})
        self.assertEqual(save_json.call_args_list[0].args[0], work_dir.resolve() / "storyboard.render.json")
        self.assertEqual(save_json.call_args_list[1].args[0], output.resolve() / "timing-report.json")

        render_args, render_kwargs = render.call_args
        self.assertEqual(render_args[0], work_dir.resolve() / "storyboard.render.json")
        self.assertEqual(render_kwargs["speech_dir"], audio_dir.resolve())
        self.assertEqual(render_kwargs["speech_provider_name"], "edge-tts")
        self.assertEqual(render_kwargs["speech_voice"], "zh-CN-YunxiNeural")
        self.assertEqual(render_kwargs["subtitle_file"], subtitle.resolve())
        self.assertEqual(result["narration_preflight"]["audio_cache"]["scene_001"], "supplied")

    def test_supplied_audio_requires_existing_complete_wav_directory(self):
        with self.assertRaisesRegex(pipeline.renderer.RenderError, "--tts-provider supplied requires"):
            pipeline.run_pipeline(
                EXAMPLE, self.root / "output", tts_provider="supplied"
            )

        missing_dir = self.root / "missing-audio"
        with self.assertRaisesRegex(pipeline.renderer.RenderError, "does not exist"):
            pipeline.run_pipeline(
                EXAMPLE,
                self.root / "output",
                tts_provider="supplied",
                tts_audio_dir=missing_dir,
            )

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
