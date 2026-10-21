#!/usr/bin/env python3
"""Pre-synthesize scene narration and derive safe timings without changing the source storyboard."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import math
import unicodedata
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


def narration_cache_key(scene, voice_id, rate, provider):
    """Fingerprint all stable inputs that affect speech and word-boundary metadata."""
    payload = {
        "provider": "edge-tts",
        "provider_version": getattr(provider.edge_tts, "__version__", "unknown"),
        "voice_id": voice_id,
        "rate": rate,
        "narration": scene["narration"],
        "boundary": "WordBoundary",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_cached_narration(mp3_path, wav_path, cache_path, cache_key):
    """Return verified cached duration and word boundaries, or None on any cache miss."""
    try:
        if not all(path.is_file() for path in (mp3_path, wav_path, cache_path)):
            return None
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if cache.get("cache_key") != cache_key:
            return None
        if cache.get("mp3_sha256") != renderer.digest(mp3_path):
            return None
        if cache.get("wav_sha256") != renderer.digest(wav_path):
            return None
        metadata = renderer.probe(wav_path)
        if not any(stream.get("codec_type") == "audio" for stream in metadata.get("streams", [])):
            return None
        duration = float(metadata["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            return None
        if abs(duration - float(cache.get("duration_seconds", 0))) > 0.01:
            return None
        boundaries = cache.get("boundaries")
        if not isinstance(boundaries, list):
            return None
        return duration, boundaries
    except (ValueError, TypeError, KeyError, OSError, renderer.RenderError):
        # A damaged or stale cache is recoverable: synthesize that scene again.
        return None


async def synthesize_audio(storyboard, audio_dir, voice_id, force=False, cache_status=None):
    """Generate or reuse per-scene Edge TTS audio and its word-boundary metadata."""
    provider = renderer.EdgeTTS(voice_id)
    audio_dir.mkdir(parents=True, exist_ok=True)
    rate = provider.rate_for(storyboard["voice"])
    durations = {}
    boundaries_by_scene = {}
    cache_status = cache_status if cache_status is not None else {}

    for scene in storyboard["scenes"]:
        scene_id = scene["id"]
        mp3_path = audio_dir / f"{scene_id}.mp3"
        wav_path = audio_dir / f"{scene_id}.wav"
        cache_path = audio_dir / f"{scene_id}.cache.json"
        cache_key = narration_cache_key(scene, voice_id, rate, provider)

        cached = None if force else load_cached_narration(
            mp3_path, wav_path, cache_path, cache_key
        )
        if cached is not None:
            duration, scene_boundaries = cached
            durations[scene_id] = duration
            boundaries_by_scene[scene_id] = scene_boundaries
            cache_status[scene_id] = "hit"
            print(
                f"{scene_id}: reused cached narration {duration:.3f}s; "
                f"word boundaries={len(scene_boundaries)}"
            )
            continue

        cache_status[scene_id] = "forced" if force else "miss"
        for path in (mp3_path, wav_path, cache_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

        scene_boundaries = []
        try:
            communicate = provider.edge_tts.Communicate(
                text=scene["narration"],
                voice=provider.voice_id,
                rate=rate,
                boundary="WordBoundary",
            )
            stream = getattr(communicate, "stream", None)
            if callable(stream):
                # Save the same audio stream that emits timing metadata; avoid a
                # second billable/network synthesis call just to get timestamps.
                with mp3_path.open("wb") as audio_file:
                    async for message in communicate.stream():
                        if message.get("type") == "audio":
                            audio_file.write(message["data"])
                        elif message.get("type") == "WordBoundary":
                            try:
                                start_seconds = float(message["offset"]) / 10_000_000
                                duration_seconds = float(message["duration"]) / 10_000_000
                                text = str(message.get("text", ""))
                            except (KeyError, TypeError, ValueError):
                                continue
                            if text and math.isfinite(start_seconds) and math.isfinite(duration_seconds) and duration_seconds > 0:
                                scene_boundaries.append({
                                    "start_seconds": start_seconds,
                                    "end_seconds": start_seconds + duration_seconds,
                                    "text": text,
                                })
            else:
                # Compatibility fallback for older adapters that only expose save().
                await communicate.save(str(mp3_path))
        except Exception as exc:
            raise renderer.RenderError(f"{scene_id}: Edge TTS synthesis failed: {exc}") from exc

        if not mp3_path.is_file() or mp3_path.stat().st_size == 0:
            raise renderer.RenderError(f"{scene_id}: Edge TTS returned no audio file")

        renderer.command([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", mp3_path, "-vn", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav_path,
        ])
        if not wav_path.is_file() or wav_path.stat().st_size == 0:
            raise renderer.RenderError(f"{scene_id}: Edge TTS WAV conversion produced no audio file")
        metadata = renderer.probe(wav_path)
        if not any(stream["codec_type"] == "audio" for stream in metadata["streams"]):
            raise renderer.RenderError(f"{scene_id}: converted WAV contains no audio stream")
        duration = float(metadata["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise renderer.RenderError(f"{scene_id}: converted WAV has invalid duration")

        cache = {
            "cache_key": cache_key,
            "mp3_sha256": renderer.digest(mp3_path),
            "wav_sha256": renderer.digest(wav_path),
            "duration_seconds": duration,
            "boundaries": scene_boundaries,
        }
        cache_temp = cache_path.with_name(cache_path.name + ".tmp")
        cache_temp.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cache_temp.replace(cache_path)

        durations[scene_id] = duration
        boundaries_by_scene[scene_id] = scene_boundaries
        print(f"{scene_id}: synthesized narration {duration:.3f}s; word boundaries={len(scene_boundaries)}")

    return durations, rate, boundaries_by_scene


def map_boundaries_to_source(narration, boundaries):
    """Map provider timings to exact source slices while tolerating omitted punctuation."""
    if not boundaries:
        return None

    def is_content(char):
        # TTS boundary metadata commonly omits punctuation (including Chinese
        # quotation marks and the middle dot in transliterated names). Compare
        # only spoken characters, but keep punctuation in the source slices.
        return not char.isspace() and not unicodedata.category(char).startswith("P")

    source_positions = [index for index, char in enumerate(narration) if is_content(char)]
    source_normalized = "".join(narration[index] for index in source_positions)
    boundary_texts = [str(boundary.get("text", "")) for boundary in boundaries]
    boundary_normalized = "".join(
        char for text in boundary_texts for char in text if is_content(char)
    )
    if not source_positions or boundary_normalized != source_normalized:
        return None

    mapped = []
    cursor = 0
    for boundary, text in zip(boundaries, boundary_texts):
        count = sum(1 for char in text if is_content(char))
        if count == 0:
            continue
        start_index = 0 if cursor == 0 else source_positions[cursor]
        next_cursor = cursor + count
        end_index = len(narration) if next_cursor == len(source_positions) else source_positions[next_cursor]
        start_seconds = float(boundary["start_seconds"])
        end_seconds = float(boundary["end_seconds"])
        if not math.isfinite(start_seconds) or not math.isfinite(end_seconds) or end_seconds <= start_seconds:
            return None
        mapped.append({
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "text": narration[start_index:end_index],
        })
        cursor = next_cursor
    return mapped if cursor == len(source_positions) and mapped else None



def build_aligned_srt(storyboard, boundaries_by_scene, max_chars=16, max_duration=2.4):
    """Build compact word-boundary captions, falling back per scene when text cannot be aligned exactly."""
    entries = []
    report = {}
    offset = 0.0

    def add_entry(start, end, text):
        if not text:
            return
        start = max(0.0, start)
        end = max(start + 0.08, end)
        entries.append({
            "start": start,
            "end": end,
            "text": text,
        })

    for scene in storyboard["scenes"]:
        scene_id = scene["id"]
        narration = scene["narration"]
        duration = renderer.frame_count(scene) / renderer.FPS
        raw_boundaries = sorted(
            boundaries_by_scene.get(scene_id, []),
            key=lambda item: float(item.get("start_seconds", 0)),
        )
        mapped = map_boundaries_to_source(narration, raw_boundaries)
        if mapped:
            groups = []
            current = None
            for boundary in mapped:
                start = min(duration, max(0.0, boundary["start_seconds"]))
                end = min(duration, max(start + 0.08, boundary["end_seconds"]))
                if start >= duration or end <= start:
                    continue
                text = boundary["text"]
                if current and (
                    len(current["text"] + text) > max_chars
                    or end - current["start"] > max_duration
                ):
                    groups.append(current)
                    current = None
                if current is None:
                    current = {"start": start, "end": end, "text": text}
                else:
                    current["end"] = max(current["end"], end)
                    current["text"] += text
                if current["text"].rstrip().endswith(("。", "！", "？", "；", "：")):
                    groups.append(current)
                    current = None
            if current:
                groups.append(current)
            for group in groups:
                add_entry(offset + group["start"], offset + group["end"], group["text"])
            alignment = "word_boundary"
        else:
            # Keep every source character even when the provider's metadata does
            # not exactly match the narration; do not fabricate word timestamps.
            chunk_size = 18
            for index in range(0, len(narration), chunk_size):
                text = narration[index:index + chunk_size]
                start = offset + duration * index / len(narration)
                end = offset + duration * min(index + chunk_size, len(narration)) / len(narration)
                add_entry(start, end, text)
            alignment = "scene_proportional_fallback"

        report[scene_id] = {
            "alignment": alignment,
            "word_boundaries": len(raw_boundaries),
            "source_text_matched": alignment == "word_boundary",
        }
        offset += duration

    # Word-boundary timestamps from remote TTS can overlap by a few milliseconds.
    # Keep captions ordered and non-overlapping after grouping, without changing text.
    for index in range(1, len(entries)):
        previous = entries[index - 1]
        current = entries[index]
        if current["start"] < previous["end"]:
            if current["start"] - previous["start"] >= 0.08:
                previous["end"] = current["start"]
            else:
                current["start"] = previous["end"]
                if current["end"] <= current["start"]:
                    current["end"] = current["start"] + 0.08

    srt = "\n\n".join(
        f"{index}\n{renderer.stamp(entry['start'])} --> {renderer.stamp(entry['end'])}\n{entry['text']}\n"
        for index, entry in enumerate(entries, 1)
    )
    return srt, report

def prepare(source, audio_dir, derived_storyboard, timing_report, voice_id=None, margin_seconds=0.25, subtitle_output=None, force=False):
    source = Path(source).resolve()
    audio_dir = Path(audio_dir).resolve()
    derived_storyboard = Path(derived_storyboard).resolve()
    timing_report = Path(timing_report).resolve()
    subtitle_output = Path(subtitle_output).resolve() if subtitle_output else timing_report.with_name("aligned-subtitles.srt")

    output_paths = [derived_storyboard, timing_report, subtitle_output]
    if source in output_paths or len(set(output_paths)) != len(output_paths):
        raise renderer.RenderError("Output paths must not overwrite the source storyboard or each other")
    if not 0 <= margin_seconds <= 5:
        raise renderer.RenderError("margin-seconds must be between 0 and 5")

    source_bytes = source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    data = renderer.load_storyboard(source)
    original_ids = [scene["id"] for scene in data["scenes"]]
    original_narration = [scene["narration"] for scene in data["scenes"]]
    voice_id = voice_id or "zh-CN-YunxiNeural"

    audio_cache = {}
    durations, rate, boundaries_by_scene = asyncio.run(
        synthesize_audio(data, audio_dir, voice_id, force=force, cache_status=audio_cache)
    )
    derived, scenes_report = allocate_scene_durations(data, durations, margin_seconds)
    aligned_srt, subtitle_report = build_aligned_srt(derived, boundaries_by_scene)
    if [scene["id"] for scene in derived["scenes"]] != original_ids:
        raise renderer.RenderError("Scene order changed during timing preparation")
    if [scene["narration"] for scene in derived["scenes"]] != original_narration:
        raise renderer.RenderError("Narration changed during timing preparation")

    derived_storyboard.parent.mkdir(parents=True, exist_ok=True)
    timing_report.parent.mkdir(parents=True, exist_ok=True)
    subtitle_output.parent.mkdir(parents=True, exist_ok=True)
    renderer.save_json(derived_storyboard, derived)
    subtitle_output.write_text(aligned_srt, encoding="utf-8")
    report = {
        "source_storyboard_sha256": source_hash,
        "derived_storyboard_sha256": renderer.digest(derived_storyboard),
        "provider": "EdgeTTS",
        "voice": voice_id,
        "rate": rate,
        "margin_seconds": margin_seconds,
        "derived_target_duration_seconds": derived["format"]["target_duration_seconds"],
        "scenes": scenes_report,
        "subtitle_output": str(subtitle_output),
        "subtitle_alignment": subtitle_report,
        "audio_cache": audio_cache,
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
    parser.add_argument("--subtitle-output", type=Path, help="Output SRT with word-boundary timing when available")
    parser.add_argument("--voice", default="zh-CN-YunxiNeural")
    parser.add_argument("--margin-seconds", type=float, default=0.25)
    parser.add_argument("--force", action="store_true", help="Ignore the narration cache and re-synthesize every scene")
    args = parser.parse_args()
    try:
        report = prepare(args.storyboard, args.audio_dir, args.derived_storyboard,
                         args.timing_report, args.voice, args.margin_seconds, args.subtitle_output, args.force)
        print(json.dumps({
            "status": "complete",
            "provider": report["provider"],
            "voice": report["voice"],
            "scenes": len(report["scenes"]),
            "target_duration_seconds": report["derived_target_duration_seconds"],
            "derived_storyboard": str(args.derived_storyboard),
            "audio_dir": str(args.audio_dir),
            "timing_report": str(args.timing_report),
            "subtitle_output": report["subtitle_output"],
            "subtitle_alignment": report["subtitle_alignment"],
            "audio_cache": report["audio_cache"],
        }, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"Narration preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
