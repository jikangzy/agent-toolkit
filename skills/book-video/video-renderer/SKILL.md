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
3. Generate narration audio. For multi-scene TTS, prefer `tools/book-video-renderer/prepare_narration.py`: it synthesizes each scene, measures the WAV duration, and creates a derived storyboard with scene timings extended only when needed. Keep the derived storyboard under `.local/runs/<run-id>/`, outside the renderer output directory, and never rewrite the source storyboard.
4. Obtain word/sentence timestamps from TTS where available; otherwise align from scene timings.
5. Generate visual assets with the image-generation tool available in the current agent environment, if one is available:
   - Save each still as `<run-dir>/images/<scene_id>.png` (PNG, JPG/JPEG, or WebP are accepted).
   - Follow the scene's `visual.prompt` and `negative_prompt`; prefer vertical 9:16, no text/logos/watermarks, and a centered subject that can survive center-cropping.
   - Never ask the image model to write the title/subtitles into the image; the renderer overlays the exact storyboard `onscreen_text`.
   - If the current environment cannot generate or save images, do not claim that it did; continue with labeled placeholders and report the limitation.
   - AI video generation is not implemented in the current CLI; use still images with gentle pan/zoom for now.
6. Normalize supplied assets to 1080x1920; missing assets fall back to labeled placeholders and are listed in the manifest.
7. Render one MP4 per scene, passing `--assets-dir <run-dir>/images`.
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

The checked-in CLI accepts optional **agent-generated still images** via `--assets-dir` and renders them with gentle pan/zoom. It does not call an image-generation API itself; if image assets are unavailable, it uses clearly labeled placeholders. AI video clips and automatic background-music generation are not implemented. It can optionally synthesize real Chinese narration through Edge TTS. Do not describe a default no-audio render as a finished narrated video.

Run commands from the repository root:

```bash
python -m pip install -r tools/book-video-renderer/requirements.txt
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/<run-id> \
  --assets-dir output/<run-id>/images
```

Before rendering, generate and save per-scene images to `output/<run-id>/images/scene_001.png`, etc., if the agent's image-generation tool supports saving them. Do not commit those generated assets. Missing images are explicitly recorded as placeholder fallbacks.

The default `--tts-provider none` is offline and produces no audio track. For multi-scene online Chinese narration, use the preflight workflow so speech is measured before video assembly:

```bash
python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt
python tools/book-video-renderer/prepare_narration.py \
  examples/book-video/naval-test-001/storyboard.json \
  --audio-dir output/<run-id>/audio \
  --derived-storyboard .local/runs/<run-id>/storyboard.render.json \
  --timing-report output/<run-id>/timing-report.json \
  --voice zh-CN-YunxiNeural

python tools/book-video-renderer/renderer.py \
  .local/runs/<run-id>/storyboard.render.json \
  --output output/<run-id> \
  --assets-dir output/<run-id>/images \
  --tts-audio-dir output/<run-id>/audio \
  --tts-audio-provider edge-tts \
  --tts-audio-voice zh-CN-YunxiNeural
```

Before enabling Edge TTS, disclose that narration text is sent to an external service and requires internet access. It is optional and has no availability guarantee. The preflight adjusts only a derived storyboard's scene durations to fit measured speech; the original narration and scene order remain unchanged. If synthesis fails, report the failure rather than claiming success or truncating narration. Generated video/audio/images/cache/font assets belong under ignored `output/` or `.local/runs/` directories or CI artifacts, never in source control. Subtitles currently use scene-proportional timing, not word-level forced alignment.

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
