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
3. Generate narration audio per scene or as a full track using the configured TTS provider.
4. Obtain word/sentence timestamps from TTS where available; otherwise align from scene timings.
5. Generate visual assets:
   - `image`: generate a still image, then animate with slow pan/zoom.
   - `video`: call the configured video-generation provider.
   - `title_card` / `quote_card`: render deterministically with local graphics tooling.
   - `broll`: use the configured stock or generation provider.
6. Normalize assets to target resolution/fps/aspect ratio.
7. Render one MP4 per scene.
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

The checked-in CLI currently renders **program-generated placeholder visuals**, not AI-generated images or video. It can optionally synthesize real Chinese narration through Edge TTS. Do not describe a default no-audio render as a finished narrated video.

Run commands from the repository root:

```bash
python -m pip install -r tools/book-video-renderer/requirements.txt
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/<run-id>
```

The default `--tts-provider none` is offline and produces no audio track. To explicitly enable online Chinese narration:

```bash
python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/<run-id> \
  --tts-provider edge-tts \
  --tts-voice zh-CN-YunxiNeural
```

Before enabling Edge TTS, disclose that narration text is sent to an external service and requires internet access. It is optional and has no availability guarantee. If synthesis fails or speech does not fit the scene without excessive speed-up, report the failure rather than claiming success or truncating narration. Generated video/audio/cache/font assets belong under the ignored `output/` directory or CI artifacts, never in source control. Subtitles currently use scene-proportional timing, not word-level forced alignment.

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
