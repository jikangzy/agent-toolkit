# Book Video Skills

This capability uses a strict two-stage boundary:

1. **story-producer**: book title → `storyboard.json`
2. **video-renderer**: `storyboard.json` → `output/final.mp4`

The renderer must not rewrite narration, reorder scenes, or alter book claims. The storyboard schema is the contract between creative planning and media execution.

## MVP progression

- V0: placeholder visuals + TTS + subtitles + FFmpeg
- V1: AI images + TTS + subtitles + FFmpeg
- V2: AI video for selected scenes, AI images for the rest
- V3: background music, transitions, style consistency, automatic QC
