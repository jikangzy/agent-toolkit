---
name: book-video-renderer
description: 将已确认的 storyboard.json 转成视频素材、配音、字幕并用 FFmpeg 合成 final.mp4；不得改写口播内容。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# book-video-renderer

## Purpose
Consume a validated `storyboard.json` and produce a finished MP4. Content is locked; this skill is an execution layer, not a writer.

## Hard rules
- DO NOT rewrite narration.
- DO NOT reorder scenes.
- DO NOT change the thesis or book claims.
- You MAY improve generation prompts without changing scene meaning.
- You MAY adjust visual clip length to match actual narration timing.
- Cache every generated asset and only regenerate failed/missing scenes.

## Expected input
`storyboard.json` conforming to `schemas/book-video/storyboard.schema.json`.

## Pipeline
1. Validate storyboard JSON.
2. Create an output directory and a manifest recording scene status.
3. Generate narration audio. Once images are ready, prefer `tools/book-video-renderer/pipeline.py` for one-command orchestration. It calls `prepare_narration.py`, measures speech duration, creates a derived storyboard, and then invokes the renderer. Keep derived storyboard/audio cache under `.local/runs/<run-id>/`, outside the renderer output directory, and never rewrite the source storyboard. The lower-level preflight script remains available for debugging.
4. Obtain word/sentence timestamps from TTS where available; otherwise align from scene timings.
5. Generate visual assets with the image-generation tool available in the current agent environment, if one is available:
   - Save each still as `<run-dir>/images/<scene_id>.png` (PNG, JPG/JPEG, or WebP are accepted).
   - Follow the scene's `visual.prompt` and `negative_prompt`; prefer vertical 9:16, no text/logos/watermarks, and a centered subject that can survive center-cropping.
   - Never ask the image model to write the title/subtitles into the image; the renderer overlays the exact storyboard `onscreen_text`.
   - If the current environment cannot generate or save images, do not claim that it did; continue with labeled placeholders and report the limitation.
   - For scenes with `visual.type` `video` or `broll`, generate or obtain real MP4/MOV/WebM clips when a video-capable provider is available. Save them as `<run-dir>/videos/<scene_id>.mp4`.
   - The CLI ingests real clips but does not call an AI video API yet. If no real clips are available, use stills only when explicitly acceptable and disclose the fallback.
6. Normalize stills to 1080x1920; normalize supplied motion clips to 1080x1920/30fps, overlay the exact `onscreen_text`, and strip source-clip audio so narration/music remain separate. Missing assets are recorded in the manifest.
7. Render one MP4 per scene, passing `--assets-dir <run-dir>/images` and `--video-assets-dir <run-dir>/videos`. For production runs, add `--require-video-assets` so any missing `video`/`broll` clip fails instead of silently falling back.
8. Concatenate all scenes in storyboard order.
9. Add narration, optional background music, and subtitles.
10. Run QC:
    - video opens successfully
    - correct resolution and fps
    - contains audio stream
    - final duration within +/- 8% of target
    - no missing scene files
11. Write final output under a local ignored run directory such as `output/<run-id>/final.mp4`.

## Current repository MVP

The checked-in CLI accepts agent-generated stills via `--assets-dir` and real motion clips via `--video-assets-dir`. It normalizes clips, overlays exact storyboard text, and records per-scene `visual_source` in the manifest. `--require-video-assets` fails closed if any `video`/`broll` scene lacks a valid clip. The CLI does not itself call an image- or AI-video-generation API, and it does not generate background music. It can optionally synthesize real Chinese narration through Edge TTS. Do not describe a default no-audio render as a finished narrated video.

Run commands from the repository root:

```bash
python -m pip install -r tools/book-video-renderer/requirements.txt
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/<run-id> \
  --assets-dir output/<run-id>/images
```

Before rendering, save per-scene images to `output/<run-id>/images/scene_001.png`, etc., and real motion clips for every `video`/`broll` scene to `output/<run-id>/videos/scene_003.mp4`, etc. Do not commit generated assets. Use `--require-video-assets` for production so missing motion clips are a hard failure rather than a silent still-image fallback. The `video` provider currently ingests supplied files; a real AI-video service adapter remains future work.

The default `--tts-provider none` is offline and produces no audio track. Once the per-scene images are ready, use this single command for measured Chinese TTS, aligned subtitles, optional local music, and final rendering:

```bash
python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt
python tools/book-video-renderer/pipeline.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/<run-id> \
  --assets-dir output/<run-id>/images \
  --video-assets-dir output/<run-id>/videos \
  --require-video-assets \
  --tts-provider edge-tts \
  --tts-voice zh-CN-YunxiNeural \
  --music-file output/<run-id>/music.mp3
```

The pipeline does not generate images or music. Edge TTS is online and sends narration text to an external service. Per-scene MP3/WAV and word-boundary metadata are cached under `.local/runs/<run-id>/audio/`; unchanged scenes are reused, and `--force-tts` explicitly regenerates them. Remove `--music-file` when no local soundtrack is available, and disclose any manifest fallbacks. For lower-level debugging, the two-step preflight workflow remains available:

```bash
python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt
python tools/book-video-renderer/prepare_narration.py \
  examples/book-video/naval-test-001/storyboard.json \
  --audio-dir output/<run-id>/audio \
  --derived-storyboard .local/runs/<run-id>/storyboard.render.json \
  --timing-report output/<run-id>/timing-report.json \
  --subtitle-output output/<run-id>/aligned-subtitles.srt \
  --voice zh-CN-YunxiNeural

python tools/book-video-renderer/renderer.py \
  .local/runs/<run-id>/storyboard.render.json \
  --output output/<run-id> \
  --assets-dir output/<run-id>/images \
  --video-assets-dir output/<run-id>/videos \
  --require-video-assets \
  --tts-audio-dir output/<run-id>/audio \
  --tts-audio-provider edge-tts \
  --tts-audio-voice zh-CN-YunxiNeural \
  --subtitle-file output/<run-id>/aligned-subtitles.srt
```

Before enabling Edge TTS, disclose that narration text is sent to an external service and requires internet access. It is optional and has no availability guarantee. The preflight adjusts only a derived storyboard's scene durations to fit measured speech; the original narration and scene order remain unchanged. If synthesis fails, report the failure rather than claiming success or truncating narration. Generated video/audio/images/cache/font assets belong under ignored `output/` or `.local/runs/` directories or CI artifacts, never in source control. The preflight emits `aligned-subtitles.srt` from Edge TTS word-boundary metadata where its text exactly matches the source narration; pass it through `--subtitle-file`. Scenes with unusable/mismatched metadata fall back to scene-proportional timing, and the timing report records which method was used.

If a local music asset is available and `music.enabled` is true in the storyboard, pass `--music-file <path>` to the renderer. It reads the default gain from `music.volume_db` (or accepts `--music-volume-db` between -60 and 0 dB), loops/trims the track to final duration, and mixes it below narration. Never claim music was generated if only a supplied file was used. If no track is available, omit the argument and ensure the manifest's music fallback is disclosed.

## Suggested local structure
output/
  <run-id>/
    manifest.json
    audio/
    images/
    videos/
    scenes/
    subtitles/
    final.mp4

## Provider abstraction
Implement provider adapters rather than hard-coding vendors:
- `generate_image(prompt, ...)`
- `generate_video(prompt, duration, ...)`
- `generate_speech(text, voice, ...)`
- `get_or_generate_music(style, duration, ...)`

## Rendering
Prefer FFmpeg for deterministic final composition. If a visual is a still image, create subtle Ken Burns motion rather than leaving it static.

## Failure handling
A failed scene should not invalidate successful assets. Record error state in manifest and retry only the failed operation with bounded retries.
