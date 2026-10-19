# Book Video Skills

This capability uses a strict two-stage boundary:

1. **story-producer**: book title → `storyboard.json`
2. **video-renderer**: `storyboard.json` → `output/final.mp4`

The renderer must not rewrite narration, reorder scenes, or alter book claims. The storyboard schema is the contract between creative planning and media execution.

## MVP progression

- V0: program-generated placeholder visuals + optional Edge TTS + scene-timed subtitles + FFmpeg (default TTS is off; explicitly opt in to send narration to the external TTS service)
- V1: agent-generated still images via `--assets-dir` + optional TTS + subtitles + FFmpeg (image generation runs outside the renderer CLI)
- V2: AI video for selected scenes, AI images for the rest
- V3: background music, transitions, style consistency, automatic QC
