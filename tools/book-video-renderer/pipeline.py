#!/usr/bin/env python3
"""One-command orchestration for narration preflight and final book-video rendering."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import prepare_narration  # noqa: E402
import renderer  # noqa: E402


def run_pipeline(
    storyboard,
    output,
    font=None,
    attempts=3,
    assets_dir=None,
    tts_provider="none",
    tts_voice="zh-CN-YunxiNeural",
    music_file=None,
    music_volume_db=None,
    subtitle_file=None,
    margin_seconds=0.25,
    force_tts=False,
    work_dir=None,
):
    """Run preflight (when enabled), then render; never edit the source storyboard."""
    source = Path(storyboard).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    assets_dir = Path(assets_dir).expanduser().resolve() if assets_dir is not None else None
    music_file = Path(music_file).expanduser().resolve() if music_file is not None else None
    subtitle_file = Path(subtitle_file).expanduser().resolve() if subtitle_file is not None else None

    if source == output or output in source.parents:
        raise renderer.RenderError("Output directory must not contain the input storyboard")
    if attempts < 1 or attempts > 10:
        raise renderer.RenderError("attempts must be between 1 and 10")
    if tts_provider not in ("none", "edge-tts"):
        raise renderer.RenderError("tts_provider must be 'none' or 'edge-tts'")
    if force_tts and tts_provider != "edge-tts":
        raise renderer.RenderError("--force-tts requires --tts-provider edge-tts")

    if tts_provider == "none":
        manifest = renderer.render(
            source,
            output,
            font,
            attempts,
            assets_dir=assets_dir,
            music_file=music_file,
            music_volume_db=music_volume_db,
            subtitle_file=subtitle_file,
        )
        return {"manifest": manifest, "narration_preflight": None}

    if subtitle_file is not None:
        raise renderer.RenderError(
            "--subtitle-file cannot be combined with --tts-provider edge-tts; "
            "the narration preflight generates aligned-subtitles.srt"
        )

    # Validate the source and local music before making any external TTS request.
    data = renderer.load_storyboard(source)
    renderer.resolve_music(data, music_file, music_volume_db)
    voice_id = tts_voice or "zh-CN-YunxiNeural"
    if work_dir is None:
        work_dir = ROOT / ".local" / "runs" / output.name
    else:
        work_dir = Path(work_dir).expanduser().resolve()
    if work_dir == output or output in work_dir.parents:
        raise renderer.RenderError("Narration work directory must be outside the renderer output directory")

    audio_dir = work_dir / "audio"
    derived_storyboard = work_dir / "storyboard.render.json"
    timing_report = output / "timing-report.json"
    aligned_subtitles = output / "aligned-subtitles.srt"

    preflight = prepare_narration.prepare(
        source,
        audio_dir,
        derived_storyboard,
        timing_report,
        voice_id,
        margin_seconds,
        aligned_subtitles,
        force_tts,
    )
    manifest = renderer.render(
        derived_storyboard,
        output,
        font,
        attempts,
        speech_dir=audio_dir,
        tts_provider="none",
        assets_dir=assets_dir,
        speech_provider_name="edge-tts",
        speech_voice=voice_id,
        music_file=music_file,
        music_volume_db=music_volume_db,
        subtitle_file=aligned_subtitles,
    )
    return {"manifest": manifest, "narration_preflight": preflight}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path, help="Source storyboard JSON (never modified)")
    parser.add_argument("--output", type=Path, required=True, help="Ignored output directory for final video and QC")
    parser.add_argument("--font", help="CJK font covering all storyboard characters")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--assets-dir", type=Path, help="Generated stills named <scene_id>.png/.jpg/.jpeg/.webp")
    parser.add_argument(
        "--tts-provider",
        choices=("none", "edge-tts"),
        default="none",
        help="none is offline/no narration; edge-tts sends narration text to an external online service",
    )
    parser.add_argument("--tts-voice", default="zh-CN-YunxiNeural")
    parser.add_argument("--force-tts", action="store_true", help="Ignore the narration cache and re-synthesize all scenes")
    parser.add_argument("--margin-seconds", type=float, default=0.25)
    parser.add_argument("--music-file", type=Path, help="Optional local background music file")
    parser.add_argument("--music-volume-db", type=float, help="Override storyboard music gain (-60 to 0 dB)")
    parser.add_argument("--subtitle-file", type=Path, help="Optional pre-aligned SRT; only valid with --tts-provider none")
    parser.add_argument("--work-dir", type=Path, help="Optional cache/work directory outside --output")
    args = parser.parse_args()

    try:
        result = run_pipeline(
            args.storyboard,
            args.output,
            font=args.font,
            attempts=args.attempts,
            assets_dir=args.assets_dir,
            tts_provider=args.tts_provider,
            tts_voice=args.tts_voice,
            music_file=args.music_file,
            music_volume_db=args.music_volume_db,
            subtitle_file=args.subtitle_file,
            margin_seconds=args.margin_seconds,
            force_tts=args.force_tts,
            work_dir=args.work_dir,
        )
        manifest = result["manifest"]
        preflight = result["narration_preflight"]
        print(json.dumps({
            "status": manifest.get("status"),
            "overall_status": manifest.get("overall_status"),
            "final_video_path": manifest.get("final_video_path"),
            "speech_status": manifest.get("speech_status"),
            "music": manifest.get("music"),
            "subtitle_alignment": manifest.get("subtitle_alignment"),
            "narration_cache": preflight.get("audio_cache") if preflight else None,
            "timing_report": str(Path(args.output).expanduser().resolve() / "timing-report.json") if preflight else None,
            "fallbacks": manifest.get("fallbacks", []),
            "qc": manifest.get("qc"),
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
