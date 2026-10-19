# Book Video Renderer validation

Validation date: 2026-10-20 (Asia/Shanghai).

## Automated CI

GitHub Actions run: https://github.com/jikangzy/agent-toolkit/actions/runs/39343331034

- Python 3.12 on Ubuntu; FFmpeg/ffprobe, libx264, libass and Noto CJK fonts installed by the workflow.
- The regular renderer suite passed after the Edge TTS MP3-padding adjustment.
- The initial live-TTS attempts exposed two real issues and were fixed on the experiment branch: the production storyboard schema intentionally requires at least 15 seconds, and MP3 encoder padding could trigger a false scene-overrun error.
- The successful cloud sample used a temporary schema copy with an 8-second minimum for the derived one-scene sample only. The committed production schema and original storyboard were not changed.
- The successful run produced an artifact containing `final.mp4`, `manifest.json`, and `subtitles.srt`. The artifact is stored in GitHub Actions for 7 days and is not committed to Git.

## Successful 8-second live TTS sample

- Source: `examples/book-video/naval-test-001/storyboard.json`; only `scene_001` was used. Its narration was preserved verbatim.
- Status: `complete`; speech status: `generated_audio`.
- Voice: `zh-CN-YunxiNeural` via the optional external Edge TTS service.
- Output: 1080×1920, 30 fps, H.264/yuv420p, AAC audio, 8.033333 seconds.
- Final MP4 size: approximately 3.08 MB.
- FFprobe validation and full decode passed; an extracted frame confirmed that Chinese title/subtitle glyphs render.
- Current visual is still a program-generated placeholder. No generated AI image, AI video, word-level subtitle alignment, or background music was included.
- Edge TTS requires internet and sends the scene narration text to the external service.

## Current limitations

- The CLI now accepts externally generated still images through `--assets-dir`; it does not call an image-generation API itself. Each asset is named `<scene_id>.png`, `.jpg`, `.jpeg`, or `.webp`. Assets are center-cropped to 1080×1920, storyboard `onscreen_text` is overlaid locally, and asset hashes participate in per-scene cache keys.
- Missing images fall back to labeled placeholders and are recorded in the manifest. AI video generation is not implemented.
- Background music and cinematic transitions are not implemented; transitions currently use cuts.
- Subtitles are scene-proportionally timed rather than word-level aligned to the generated voice.
- Generated media, audio, image assets, fonts and caches belong under ignored local `output/` directories or short-lived CI artifacts, never in Git.
