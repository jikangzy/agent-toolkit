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


## Offline modular MVP cloud validation (2026-10-20 UTC)

The full original Naval storyboard was rendered locally in the cloud using FFmpeg,
Noto CJK, and the offline adapters. No external image/video/TTS service or music
was called or downloaded. The source JSON, narration, on-screen text and scene
order were preserved.

- Command: `PYTHONPATH=tools/book-video-renderer python -m book_video_renderer render --storyboard examples/book-video/naval-test-001/storyboard.json --output output/naval-test-001`
- Output: `output/naval-test-001/final.mp4`, 10 independent scene MP4s, SRT,
  `unburned.mp4`, and manifest/cache artifacts (all ignored by Git).
- QC: 1080×1920, 30 fps, H.264/yuv420p; 113.0 seconds versus 120-second declared
  target (5.83% difference). All 10 scenes present, subtitles burned. FFmpeg full
  decode passed. A frame was inspected to confirm readable Chinese title/subtitles.
- Speech: `fallback_no_audio`, with nullable per-scene `audio_path`. No real TTS
  was claimed. AAC encoding is covered by recorded-audio integration tests.
- Music: `skipped`, because no safe local track was supplied.
- Placeholder motion follows zoom-in, zoom-out, pan right/down, or push-in requests;
  unsupported motion falls back to gentle push-in. Scene transitions use cuts.

New regressions cover scene order and gaps, frame-rounded total duration,
per-direction motion filters, failed validation manifests, missing-CJK-font
preservation of SRT/unburned video, and retry/resume after scene_002 fails while
scene_001 remains cached. Existing tests also verify schema validation, source
immutability, real AAC encoding, cached/corrupt clips, supplied images, local music,
and mocked (never live) TTS adapters.

The final full suite passed **44 tests with zero skips** in 72.096 seconds using
`BOOK_VIDEO_FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc python -m unittest discover -s tools/book-video-renderer/tests -v`.
A second identical full Naval invocation passed QC and reported all **10 scenes as
`skipped_cached`**. The original storyboard has no Git diff. The MP4 and all run
artifacts remain local and were not committed.

After preserving the four newer upstream main commits (through `77bbd9b`), the
complete suite passed **45 tests with zero skips** in 50.061 seconds. This includes
the upstream punctuation-tolerant alignment regression. No renderer-package or
Naval source content changed during that integration.


## Naval real-media validation — current four-level status

Authoritative staged record: `openspec/changes/real-media-e2e-validation/RUN_REPORT.md`.
Base: `04edeff096fec139880b5bcbe1fdf91663dc4ff4`; work branch:
`feat/naval-real-media-e2e-validation`. This section supersedes any older absence
claim about formal source images, without changing historical test records.

| Level | Current status | Evidence and boundary |
| --- | --- | --- |
| LEVEL 1 — CODE / CI | Local frozen-source 86-test full FFmpeg run PASS, 0 skips; PR CI tracked in RUN_REPORT | Includes mock fal/Edge, actual local video decode/render, supplied WAV/test tones and cache/manifest recovery; not live service acceptance |
| LEVEL 2 — SOURCE IMAGES / PREFLIGHT | PASS | 8/8 main Git-tree originals, 941×1672 RGB PNG, full decode/hash; guarded eight/two-scene CLI reports with 0 external generation requests |
| LEVEL 3 — TWO-SCENE REAL MOTION | NOT RUN — PAID AUTHORIZATION REQUIRED | No real fal clips or narrated two-scene output. Mock/synthetic integration is not promoted to this level |
| LEVEL 4 — FULL EIGHT-SCENE REAL MOTION | NOT RUN — PAID AUTHORIZATION REQUIRED | No 8/8 actual Provider output or narrated 10-scene acceptance |

Formal small evidence lives in `examples/book-video/naval-test-001/validation/`:
source-images-report.json, storyboard-integrity.json, two-scene-storyboard.json,
eight-scene-preflight.json, two-scene-preflight.json, test-results.json.
Raw local execution logs and temporary synthetic media stay under ignored
`output/naval-e2e/`; CI uploads `naval-zero-cost-evidence` (no paid outputs).

Original narration/onscreen text/order/durations unchanged. Raw Windows CRLF
source SHA and canonical Git LF SHA are recorded separately. Current configured
estimates: USD .1425/clip, cold two-scene .285/.40, cold eight-scene 1.14/1.20.
These are estimates at the repository's rate/overhead, not confirmed live billing.
No real fal or Edge TTS request has been executed by this task; FAL_KEY is missing
and paid permission is not granted. Prepared commands and reconciliation policy
are in CODEX_RUNBOOK.md. Do not close this Change as real-media complete.
