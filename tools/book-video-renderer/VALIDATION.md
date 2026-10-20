# Book Video Renderer validation

Validation date: 2026-10-20 (Asia/Shanghai).

## Automated CI

- The image-assets feature passed the full Python/FFmpeg integration suite: https://github.com/jikangzy/agent-toolkit/actions/runs/39344047019 (26 tests).
- The narration-preflight and source-path safety changes passed the full Python/FFmpeg integration suite on main: https://github.com/jikangzy/agent-toolkit/actions/runs/39346398793 (29 tests).
- Optional background music mixing passed the full Python/FFmpeg integration suite on main: https://github.com/jikangzy/agent-toolkit/actions/runs/39347334657 (33 tests), including narration+music and music-only output.
- Word-boundary subtitle preparation, SRT validation, and rendering a supplied aligned SRT passed the full Python/FFmpeg suite in PR CI: https://github.com/jikangzy/agent-toolkit/actions/runs/39348739700 (38 tests).
- Punctuation-tolerant boundary mapping and exact source-text preservation passed the full Python/FFmpeg suite: https://github.com/jikangzy/agent-toolkit/actions/runs/39433464396 (39 tests).
- Full 10-scene live Edge TTS, word-boundary subtitles, background-audio mixing, H.264/AAC output, and full decode passed: https://github.com/jikangzy/agent-toolkit/actions/runs/39436447215 (117.833-second MP4; 10/10 scenes aligned; 0 fallback scenes; 51 subtitle cues). The background track was generated procedurally for integration testing, not intended as the final soundtrack.
- The Edge TTS MP3-padding fix passed the full suite: https://github.com/jikangzy/agent-toolkit/actions/runs/39343543818.
- GitHub Actions uses Python 3.12 on Ubuntu with FFmpeg/ffprobe, libx264, libass and Noto CJK fonts.
- The suite includes unit coverage for pure narration-duration allocation and pre-synthesized provider metadata. Live Edge TTS is intentionally not run by ordinary PR CI.

## Successful 8-second live TTS sample

Run: https://github.com/jikangzy/agent-toolkit/actions/runs/39343331034

- Source: `examples/book-video/naval-test-001/storyboard.json`; only `scene_001` was used. Its narration was preserved verbatim.
- Status: `complete`; speech status: `generated_audio`.
- Voice: `zh-CN-YunxiNeural` via the optional external Edge TTS service.
- Output: 1080×1920, 30 fps, H.264/yuv420p, AAC audio, 8.033333 seconds.
- Final MP4 size: approximately 3.08 MB.
- FFprobe validation and full decode passed; an extracted frame confirmed that Chinese title/subtitle glyphs render.
- The visual is still a program-generated placeholder. No generated AI image, AI video, word-level subtitle alignment, or background music was included.

## Successful full narration render

Run: https://github.com/jikangzy/agent-toolkit/actions/runs/39345043963

- All 10 original scenes were synthesized through Edge TTS and assembled into a single 117.833333-second video (about 1:58).
- Output: 1080×1920, 30 fps, H.264/yuv420p, AAC audio; full FFmpeg decode passed.
- Scene durations in a temporary derived storyboard were extended only where measured WAV duration plus a 250 ms safety margin required it. The original storyboard and narration were not modified.
- The longest measured speech was scene_005 at 14.472 seconds; scene_002 needed 12.400 seconds instead of its original 10 seconds.
- The workflow artifact includes `final.mp4`, `manifest.json`, `subtitles.srt`, and `timing-report.json`; it expires after 7 days and is not committed to Git.
- The video still uses placeholder visuals. Background music and word-level subtitle alignment are not included.
- Edge TTS requires internet and sends narration text to the external service.

## Successful live word-boundary subtitle render

Run: https://github.com/jikangzy/agent-toolkit/actions/runs/39433762252

- Two scenes were synthesized with Edge TTS voice `zh-CN-YunxiNeural` and rendered into a 20.77-second portrait video.
- The provider emitted 20 word-boundary events for scene 1 and 26 for scene 2.
- Both scenes were aligned using the provider timings; punctuation omitted from boundary text was restored from the original narration. No scene-level fallback was needed.
- The original source storyboard remained unchanged. The short-lived artifact contains the MP4, manifest, aligned SRT, and timing report; it expires after 7 days.
- This is an explicit live-service experiment, not part of ordinary PR CI.

## Successful full 10-scene integration render

Run: https://github.com/jikangzy/agent-toolkit/actions/runs/39436447215

- All 10 original scenes were synthesized through Edge TTS voice `zh-CN-YunxiNeural` and assembled into a 117.833-second vertical video.
- All 10 scenes used real provider word-boundary timings; zero scenes fell back to proportional subtitle timing. The final SRT contains 51 grouped caption cues and preserves source punctuation.
- A procedural ambient test track was generated during the workflow and mixed under narration at -24 dB. This verifies the audio-mixing path; it is not a production soundtrack.
- Output passed full FFmpeg decode and ffprobe checks: H.264, 1080×1920, 30 fps, AAC stereo.
- The source storyboard was not modified. The short-lived artifact contains the MP4, manifest, aligned SRT, timing report, and test music; it expires after 7 days.
- Visuals are still explicitly labeled program-generated placeholders. This run validates the narration/audio/subtitle pipeline, not final visual quality.

## Current capabilities and limitations

- The CLI accepts externally generated still images through `--assets-dir`; it does not call an image-generation API itself. Each asset is named `<scene_id>.png`, `.jpg`, `.jpeg`, or `.webp`. Assets are center-cropped to 1080×1920, storyboard `onscreen_text` is overlaid locally, and asset hashes participate in per-scene cache keys.
- Missing images fall back to labeled placeholders and are recorded in the manifest. AI video generation is not implemented.
- The new `prepare_narration.py` utility pre-synthesizes each scene, measures WAV durations, and writes a derived storyboard with safe scene timings; it never rewrites the source storyboard. Pure duration allocation is unit-tested; live TTS is kept out of normal CI.
- The renderer can mix a supplied local music file via `--music-file`, loop/trim it to the video duration, and apply the storyboard's `music.volume_db`; it does not generate music. Cinematic transitions are not implemented and cuts are used.
- The TTS preflight collects Edge TTS word-boundary events from the same synthesis stream. It aligns spoken characters to the original narration while ignoring punctuation omitted by the provider, then restores all original punctuation in the timed source slices. If spoken text truly differs, it falls back per scene to proportional timing. The renderer validates and burns an optional supplied SRT through `--subtitle-file`. Live TTS is not part of normal PR CI; both two-scene and full 10-scene live Edge TTS experiments passed.
- Generated media, audio, image assets, fonts and caches belong under ignored local `output/` / `.local/runs/` directories or short-lived CI artifacts, never in Git.
