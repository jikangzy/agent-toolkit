#!/usr/bin/env python3
"""Pre-synthesize scene narration and derive safe timings without changing the source storyboard."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

# Make the sibling renderer importable when this script is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import renderer  # noqa: E402


def allocate_scene_durations(data, speech_durations, margin_seconds=0.25):
    """Return a derived storyboard whose scene durations fit measured WAV durations."""
    if not 0 <= margin_seconds <= 5:
        raise renderer.RenderError("margin-seconds must be between 0 and 5")
    derived = copy.deepcopy(data)
    scene_ids = [scene["id"] for scene in derived["scenes"]]
    if set(scene_ids) != set(speech_durations):
        raise renderer.RenderError("Speech durations must be supplied for every scene ID exactly once")

    report = {}
    for scene in derived["scenes"]:
        scene_id = scene["id"]
        speech_seconds = float(speech_durations[scene_id])
        if not math.isfinite(speech_seconds) or speech_seconds <= 0:
            raise renderer.RenderError(f"{scene_id}: invalid measured speech duration {speech_seconds}")
        original_seconds = float(scene["duration_seconds"])
        # Round up to a whole frame and leave room for encoder delay and audio padding.
        safe_seconds = math.ceil((speech_seconds + margin_seconds) * renderer.FPS) / renderer.FPS
        allocated_seconds = max(original_seconds, safe_seconds)
        scene["duration_seconds"] = allocated_seconds
        report[scene_id] = {
            "speech_seconds": round(speech_seconds, 3),
            "original_scene_seconds": original_seconds,
            "allocated_scene_seconds": allocated_seconds,
        }

    derived["format"]["target_duration_seconds"] = sum(
        scene["duration_seconds"] for scene in derived["scenes"]
    )
    return derived, report


async def synthesize_audio(storyboard, audio_dir, voice_id):
    """Generate original narration to MP3, convert to WAV, and measure exact WAV duration."""
    try:
        provider = renderer.EdgeTTS(voice_id)
    except renderer.RenderError:
        raise

    audio_dir.mkdir(parents=True, exist_ok=True)
    rate = provider.rate_for(storyboard["voice"])
    durations = {}

    for scene in storyboard["scenes"]:
        scene_id = scene["id"]
        mp3_path = audio_dir / f"{scene_id}.mp3"
        wav_path = audio_dir / f"{scene_id}.wav"
        if mp3_path.exists():
            mp3_path.unlink()
        if wav_path.exists():
            wav_path.unlink()

        try:
            communicate = provider.edge_tts.Communicate(
                text=scene["narration"],
                voice=provider.voice_id,
                rate=rate,
            )
            await communicate.save(str(mp3_path))
        except Exception as exc:
            raise renderer.RenderError(f"{scene_id}: Edge TTS synthesis failed: {exc}") from exc

        if not mp3_path.is_file() or mp3_path.stat().st_size == 0:
            raise renderer.RenderError(f"{scene_id}: Edge TTS returned no audio file")

        renderer.command([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", mp3_path, "-vn", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav_path,
        ])
        metadata = renderer.probe(wav_path)
        if not any(stream["codec_type"] == "audio" for stream in metadata["streams"]):
            raise renderer.RenderError(f"{scene_id}: converted WAV contains no audio stream")
        duration = float(metadata["format"]["duration"])
        if duration <= 0:
            raise renderer.RenderError(f"{scene_id}: converted WAV has invalid duration")
        durations[scene_id] = duration
        print(f"{scene_id}: measured narration {duration:.3f}s")

    return durations, rate


def prepare(source, audio_dir, derived_storyboard, timing_report, voice_id=None, margin_seconds=0.25):
    source = Path(source).resolve()
    audio_dir = Path(audio_dir).resolve()
    derived_storyboard = Path(derived_storyboard).resolve()
    timing_report = Path(timing_report).resolve()

    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    data = renderer.load_storyboard(source)
    original_ids = [scene["id"] for scene in data["scenes"]]
    original_narration = [scene["narration"] for scene in data["scenes"]]
    voice_id = voice_id or "zh-CN-YunxiNeural"

    durations, rate = asyncio.run(synthesize_audio(data, audio_dir, voice_id))
    derived, scenes_report = allocate_scene_durations(data, durations, margin_seconds)
    if [scene["id"] for scene in derived["scenes"]] != original_ids:
        raise renderer.RenderError("Scene order changed during timing preparation")
    if [scene["narration"] for scene in derived["scenes"]] != original_narration:
        raise renderer.RenderError("Narration changed during timing preparation")

    derived_storyboard.parent.mkdir(parents=True, exist_ok=True)
    timing_report.parent.mkdir(parents=True, exist_ok=True)
    renderer.save_json(derived_storyboard, derived)
    report = {
        "source_storyboard_sha256": source_hash,
        "derived_storyboard_sha256": renderer.digest(derived_storyboard),
        "provider": "EdgeTTS",
        "voice": voice_id,
        "rate": rate,
        "margin_seconds": margin_seconds,
        "derived_target_duration_seconds": derived["format"]["target_duration_seconds"],
        "scenes": scenes_report,
    }
    renderer.save_json(timing_report, report)
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise renderer.RenderError("Source storyboard changed during preparation")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--audio-dir", type=Path, required=True, help="Directory for generated MP3 and WAV files")
    parser.add_argument("--derived-storyboard", type=Path, required=True, help="Output path outside the renderer output directory")
    parser.add_argument("--timing-report", type=Path, required=True)
    parser.add_argument("--voice", default="zh-CN-YunxiNeural")
    parser.add_argument("--margin-seconds", type=float, default=0.25)
    args = parser.parse_args()
    try:
        report = prepare(args.storyboard, args.audio_dir, args.derived_storyboard,
                         args.timing_report, args.voice, args.margin_seconds)
        print(json.dumps({
            "status": "complete",
            "provider": report["provider"],
            "voice": report["voice"],
            "scenes": len(report["scenes"]),
            "target_duration_seconds": report["derived_target_duration_seconds"],
            "derived_storyboard": str(args.derived_storyboard),
            "audio_dir": str(args.audio_dir),
            "timing_report": str(args.timing_report),
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"Narration preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
