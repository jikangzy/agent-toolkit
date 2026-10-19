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
11. Write final output to `output/final.mp4` and render manifest to `output/manifest.json`.

## Suggested local structure
output/
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
