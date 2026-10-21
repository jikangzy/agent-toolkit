# Book Video Renderer MVP

## Offline MVP (no API key required)

From the repository root, install Python dependencies and ensure `ffmpeg` / `ffprobe`
(with libx264 and libass) are on PATH. Install a CJK font, for example the Ubuntu
`fonts-noto-cjk` package, or pass `--font /path/to/font.ttc`.

```bash
python -m pip install -r tools/book-video-renderer/requirements.txt
python tools/book-video-renderer/renderer.py render \
  --storyboard examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001
```

Equivalent module invocation:

```bash
PYTHONPATH=tools/book-video-renderer python -m book_video_renderer render \
  --storyboard examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001
```

Run the same command again to reuse verified per-scene caches. Each run regenerates
SRT and final assembly. One process may own an output directory at a time.

This default is fully offline: deterministic placeholder visuals, unchanged source
`onscreen_text`, Ken Burns motion selected from `visual.motion`, proportional subtitle
timing, no narration audio, and no BGM. `NoTTS` explicitly records `fallback_no_audio`;
it never labels silence as synthesized speech. Real narration produces AAC audio.
`video` / `broll` use the static visual fallback. Unknown motion (including fade-in)
uses gentle push-in; transitions currently use cuts.

Validation uses the shared schema and requires unique, contiguous scene IDs in
original order (`scene_001`, `scene_002`, ...). Invalid order fails; it is never sorted.
Scene durations are rounded per frame and summed without editing the input. The
Naval example produces 113 seconds (10 scenes), within 8% of its declared 120 seconds.

`manifest.json` records `storyboard_path`, `storyboard_hash`, `renderer_version`,
`total_duration_seconds`, `target_duration_seconds`, and `overall_status`. Each scene
records `input_hash`, `visual_asset_path`, nullable `audio_path`, `scene_video_path`,
`duration`, `error`, `retry_count` (including retries across runs with the same input),
plus `pending` / `rendering` / `completed` / `failed` / `skipped_cached` status.
`final_video_path` is populated only after successful QC. The legacy top-level
`status: complete` is retained for compatibility. Music without a local file is
`skipped`. Scene cache reuse verifies the clip, visual, and audio hashes and ffprobe
metadata; failed scenes retain other successful scene outputs.

The renderer discovers a font and checks glyph coverage for all source text. If no
font covers the text, it still preserves scene backgrounds, `subtitles.srt`, and
`unburned.mp4`, records the subtitle/font failure, and exits nonzero. These backgrounds
have no title overlay. It does **not** report a successful final video. Installing a
font and rerunning completes title overlays and subtitle burn-in. After any failed
run, an old `final.mp4` may remain; consult the current manifest, not file existence.

### Implementation and future providers

`renderer.py` is a compatibility entrypoint. The `book_video_renderer/` package
separates `cli`, `models`, `validator`, `renderer`, `scene`, `ffmpeg`, `fonts`,
`subtitle`, `manifest` (hash/cache/retry utilities), `qc`, and `providers/{image,video,tts,music}`.

- `TTSProvider.synthesize(scene_id, narration, voice, duration, workdir)` receives the
  narration verbatim and returns a real speech path or `None`. A future local or
  cloud adapter implements this protocol and provides a configuration-sensitive
  `cache_key`; pass an instance through `render(..., provider=adapter)`. Validate
  or convert its output before returning it. Overlong audio fails rather than
  being cut. Add CLI selection when a real provider is chosen; keep credentials in
  environment/configuration outside source control. `RecordedSpeech` already accepts
  caller-supplied WAV files. No paid or external-account provider was used for MVP validation.
- `ImageProvider.generate_image` defines the still-image boundary. `VideoProvider.get_or_generate_video(scene, duration_seconds, workdir)` defines the dynamic-footage boundary; `SuppliedVideoProvider` currently ingests caller-provided clips. An AI-video adapter can implement the same protocol later and must cache requests by scene prompt and provider/model configuration.
- `MusicProvider.get_or_generate_music` defines the music boundary; `NoMusic` returns
  `None`. Local, properly licensed files remain optional through `--music-file`.

The pre-existing Edge TTS adapter below is opt-in, online, and excluded from base
requirements. The default command does not import it or contact its service.

Automatic QC verifies readable H.264 video, 1080×1920, 30 fps, yuv420p, expected AAC
when audio is present, full scene count, final duration against both scene sum and
storyboard target. QC is printed by the CLI and saved under `manifest.qc`.
`unburned.mp4` is retained for diagnosis even on successful runs.


Python CLI for the repository's locked storyboard contract. It validates the existing JSON Schema, preserves scene order and exact narration/on-screen text, accepts optional per-scene still images and real motion clips, applies gentle push-in motion only to stills, creates Chinese SRT subtitles, burns them into the final video, and verifies output with ffprobe. The CLI does not itself call an image- or AI-video-generation API; the agent or user supplies generated assets.

## Setup

Requires Python 3.10+, FFmpeg/ffprobe (libx264, AAC, libass/subtitles filter), and a Chinese font covering all input characters. The default `none` TTS mode remains offline. An optional Edge TTS provider makes an external network request to synthesize speech; review that service's terms and privacy implications before sending narration text.

```bash
python -m pip install -r tools/book-video-renderer/requirements.txt
# Debian/Ubuntu, if needed:
sudo apt-get install ffmpeg fonts-noto-cjk
```

Font discovery uses fontconfig on Linux and common system font paths on Windows/macOS. Set `--font` explicitly when discovery is unavailable. Missing glyphs cause an actionable failure instead of blank Chinese text. A freely available alternative is Noto Sans CJK SC Regular from the notofonts/noto-cjk project (SIL Open Font License); fonts are not vendored in this repository.

## Run from repository root

```bash
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001
```

Optional: `--font /path/to/NotoSansCJKsc-Regular.otf`, `--attempts 3` (1–10).

### One-command pipeline (recommended for narrated videos)

Generate the per-scene stills under `output/naval-test-001/images/` and real MP4 clips for each `video`/`broll` scene under `output/naval-test-001/videos/`. The pipeline then pre-synthesizes narration, measures actual speech duration, builds aligned subtitles, and renders the final video in one command. `--require-video-assets` prevents accidental still-image fallback:

```bash
python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt
python tools/book-video-renderer/pipeline.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001 \
  --assets-dir output/naval-test-001/images \
  --video-assets-dir output/naval-test-001/videos \
  --require-video-assets \
  --tts-provider edge-tts \
  --tts-voice zh-CN-YunxiNeural \
  --music-file output/naval-test-001/music.mp3
```

The pipeline does **not** generate images or music; those must be supplied locally. Edge TTS sends narration text to an external online service. Speech MP3/WAV files and word-boundary metadata are cached per scene under `.local/runs/<output-name>/audio/`; unchanged scenes are reused without another TTS request. Use `--force-tts` to regenerate all narration. The source storyboard is never rewritten. For offline/no-narration rendering, use `--tts-provider none` or call `renderer.py` directly.

If narration was produced elsewhere (another TTS provider, a studio recording, or a previous verified run), the same pipeline can render it without any network TTS call. Put one WAV per scene in a local directory and use:

```bash
python tools/book-video-renderer/pipeline.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001 \
  --assets-dir output/naval-test-001/images \
  --tts-provider supplied \
  --tts-audio-dir output/naval-test-001/narration \
  --tts-audio-provider edge-tts \
  --tts-audio-voice zh-CN-YunxiNeural \
  --subtitle-file output/naval-test-001/aligned-subtitles.srt \
  --music-file output/naval-test-001/music.mp3
```

In `supplied` mode the pipeline validates every `scene_XXX.wav`, measures its real duration, writes a derived storyboard under the work directory, and records the supplied provider/voice in the manifest. This makes the pipeline provider-neutral and suitable for reusing already-approved narration without another synthesis request.


### Use AI-generated images

Generate one still image per scene with the image-generation tool available to your agent, then save each image under an ignored output directory using the scene ID as its filename:

```text
output/naval-test-001/images/
  scene_001.png
  scene_002.png
  scene_003.png
  ...
```

Use vertical 9:16 compositions where possible. Ask the image model for **no text, logos, watermarks, or fake book-cover lettering**; the renderer overlays the storyboard's exact `onscreen_text` itself. Center the key subject because non-9:16 images are center-cropped to 1080×1920.

Then render with the asset directory:

```bash
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001 \
  --assets-dir output/naval-test-001/images \
  --tts-provider edge-tts \
  --tts-voice zh-CN-YunxiNeural
```

Accepted image formats: PNG, JPG/JPEG, WebP. Use exactly one image per scene ID. Missing images fall back to clearly labeled placeholders and are listed in `manifest.json`; invalid or ambiguous assets fail clearly. Asset SHA-256 hashes participate in per-scene cache keys, so replacing one image regenerates only that scene. Image generation still happens outside the CLI, using the agent's available image tool; the renderer never pretends a placeholder is a generated image.

### Use real motion-video clips (no silent still-image fallback)

The renderer can now ingest actual motion clips for storyboard scenes whose `visual.type` is `video` or `broll`. Put one clip per scene in a separate directory:

```text
output/naval-test-001/videos/
  scene_003.mp4
  scene_004.mp4
  scene_005.mp4
  ...
```

Supported input extensions are MP4, MOV, M4V, MKV, and WebM. Then render with:

```bash
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001 \
  --assets-dir output/naval-test-001/images \
  --video-assets-dir output/naval-test-001/videos \
  --require-video-assets \
  --tts-audio-dir output/naval-test-001/audio \
  --tts-audio-provider edge-tts \
  --tts-audio-voice zh-CN-YunxiNeural \
  --subtitle-file output/naval-test-001/aligned-subtitles.srt \
  --music-file output/naval-test-001/music.mp3
```

`--require-video-assets` makes the render fail before scene assembly if any `video` or `broll` scene lacks a valid clip. Without it, missing clips use a supplied still image if available, otherwise a clearly recorded placeholder. The manifest records each scene's `visual_source` as `video`, `image`, or `placeholder`, along with source hashes. Replacing one MP4 invalidates only that scene's cache. Imported footage is looped or trimmed to its scene duration, center-cropped to 9:16, normalized to 1080×1920 at 30 fps, and overlaid with the storyboard's exact on-screen text. Audio embedded in source clips is deliberately discarded; narration and optional music are mixed as separate tracks.

This is the provider-neutral ingestion boundary, not an AI video-generation API. The CLI does not create or download video clips. A future service adapter can implement `VideoProvider.get_or_generate_video(scene, duration_seconds, workdir)`; that adapter must own a stable cache keyed by the scene prompt and provider/model configuration. The supplied-file adapter makes the complete dynamic-video rendering path testable without paid credits or external API credentials.

### Optional background music

The renderer can mix a **local audio file** into the final MP4. It does not generate or download music. Set `music.enabled: true` in the storyboard (the default for this schema), then provide the file:

```bash
python tools/book-video-renderer/renderer.py \
  .local/runs/naval-test-001/storyboard.render.json \
  --output output/naval-test-001 \
  --assets-dir output/naval-test-001/images \
  --tts-audio-dir output/naval-test-001/audio \
  --tts-audio-provider edge-tts \
  --tts-audio-voice zh-CN-YunxiNeural \
  --music-file output/naval-test-001/music.mp3
```

The default music gain comes from `music.volume_db` in the storyboard (for example, `-24` dB). Override it with `--music-volume-db -24`; the accepted range is `-60` to `0` dB. FFmpeg loops short music files and trims them to the video duration, then mixes the track under narration. Music-only output is also supported, but the manifest still clearly marks narration as missing. If music is enabled but no file is supplied, rendering continues without music and records the fallback in `manifest.json`. A supplied file is validated as an audio stream, and its hash, filename, and gain are recorded in the manifest. Music is a final-assembly input, so changing the music does not invalidate the per-scene video cache.

### Optional real Chinese TTS

Install the separate optional dependency (it is intentionally excluded from the offline base requirements):

```bash
python -m pip install -r tools/book-video-renderer/requirements-tts-edge.txt
```

For a quick render when you already know the narration fits each scene, the CLI can synthesize inline:

```bash
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001-edge-tts \
  --tts-provider edge-tts \
  --tts-voice zh-CN-YunxiNeural
```

For multi-scene videos, **prefer the preflight path below**. Actual spoken duration can differ substantially from estimates in the storyboard; this path measures each generated WAV and extends only a derived storyboard's scene timings before final rendering. The original storyboard and narration are not rewritten.

```bash
# Keep the derived storyboard outside the renderer output directory.
python tools/book-video-renderer/prepare_narration.py \
  examples/book-video/naval-test-001/storyboard.json \
  --audio-dir output/naval-test-001/audio \
  --derived-storyboard .local/runs/naval-test-001/storyboard.render.json \
  --timing-report output/naval-test-001/timing-report.json \
  --subtitle-output output/naval-test-001/aligned-subtitles.srt \
  --voice zh-CN-YunxiNeural

python tools/book-video-renderer/renderer.py \
  .local/runs/naval-test-001/storyboard.render.json \
  --output output/naval-test-001 \
  --assets-dir output/naval-test-001/images \
  --tts-audio-dir output/naval-test-001/audio \
  --tts-audio-provider edge-tts \
  --tts-audio-voice zh-CN-YunxiNeural \
  --subtitle-file output/naval-test-001/aligned-subtitles.srt
```

The preflight script writes one MP3 and WAV per scene, measures WAV durations, adds a default 250 ms margin rounded to a video frame, and writes a timing report plus `aligned-subtitles.srt`. When Edge TTS word-boundary metadata matches the spoken characters in the original narration, captions are timed from those boundaries and grouped into short readable lines. Punctuation and whitespace omitted by the provider are ignored for matching but restored from the original narration in the resulting caption text. If the spoken characters truly differ, that scene safely falls back to scene-proportional timing rather than altering the source narration. The renderer validates the SRT duration and burns it when passed `--subtitle-file`; without that argument, it uses its scene-proportional fallback. The renderer records `speech_status: generated_audio`, the provider/voice, subtitle alignment status, and the external-service notice in `manifest.json`. The `--tts-audio-provider` / `--tts-audio-voice` flags describe the source of supplied WAVs; they do not trigger another network request.

The preflight caches each scene's MP3, WAV, and word-boundary metadata. Cache keys include the exact narration, voice, synthesis rate, and Edge TTS package version; intact cache entries are reused without another TTS request. Cache hit/miss status is written to `timing-report.json`. Pass `--force` to re-synthesize every scene when you explicitly want fresh audio.

**Important limitations:** Edge TTS is an online, third-party service, not an offline engine or a guaranteed production API. It requires network access and may change or throttle. Narration text is sent to that service. The provider is optional and replaceable; the default renderer still performs no TTS network calls. Word-level timing depends on the external service returning usable metadata; fallback captions are still available.

### Render the sample in GitHub Actions (no local computer required)

After the workflow file is merged into the repository's default branch, open **GitHub → Actions → Book Video Renderer tests → Run workflow**, select `main` (or the branch you want to test), and set `render_tts_sample` to `true`. GitHub only enables manual `workflow_dispatch` for workflows present on the default branch. The job renders only the first 8-second scene, preserving its narration verbatim. This is an explicit opt-in because it sends that narration to the external Edge TTS service. The workflow uploads `final.mp4`, `manifest.json`, and `subtitles.srt` as the `naval-test-001-edge-tts` artifact; generated files are not committed to Git. The default value is `false`, so normal CI runs never call the speech service.

The MVP accepts 1080x1920 / 9:16 / 30 fps only; output is H.264/yuv420p with AAC when real audio is supplied. Schema validation is followed by unique-ID and timing checks. Scene durations are rounded to the nearest frame. Total duration must fall within ±8% of the declared target; it is never silently stretched. The Naval example has 113 seconds of scenes against a 120-second target and produces a 113-second video.

Output layout:

```text
output/naval-test-001/
  final.mp4
  manifest.json
  subtitles.srt
  unburned.mp4
  scenes/scene_001.mp4 ...
  cache/<content-hash>/visual.png, clip.mp4, complete.json
  fonts/                         # local subtitle font copy
  concat.txt
```

All generated data stays under the output directory, already ignored by the repository `.gitignore`. Do not commit it. Original repository files and the input JSON are never rewritten. The output directory must not contain the source storyboard.

## Explicit MVP fallbacks

- When no `--assets-dir` image is supplied for a scene, `image`, `title_card`, `broll`, `video`, and `quote_card` use a labeled program-generated placeholder. The renderer does not call an image/video API. Supplied still images are normalized and animated with a gentle push-in; AI video clips are not supported yet.
- Default `NoTTS` returns no audio. `manifest.json` records `speech_status: fallback_no_audio` and an explicit fallback warning. No silent track or synthetic tone is presented as speech.
- Requested music is omitted and recorded in the manifest.
- Scene transitions use cuts; requested transitions remain recorded in the manifest.
- Subtitles contain the unchanged narration, split into short cues using proportional timing inside each scene. This is not word-level speech alignment.

## Replaceable speech provider

`TTSProvider` is a Python protocol with `cache_key`, `fallback`, and `synthesize(scene_id, narration, voice, duration, workdir) -> Path | None`. A provider receives the original narration verbatim and must return a real audio file or explicitly return `None`. Its cache key must include the voice, model/configuration, implementation and external audio identity. Never use a fake tone as narration.

The included `RecordedSpeech` adapter supports caller-provided narration WAVs:

```bash
python tools/book-video-renderer/renderer.py \
  examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001 \
  --tts-audio-dir /path/to/real-narration
```

Provide `scene_001.wav` through `scene_010.wav`, each matching its scene's exact narration. Matching transcript content is the caller's responsibility; this MVP does not perform speech recognition. Short audio is padded to the scene duration; overlong audio fails rather than truncating narration. Missing WAVs fail. Mixed speech/no-speech scenes fail. Output audio is encoded to AAC, 48 kHz stereo. An optional Edge TTS provider can synthesize Chinese speech when explicitly enabled; the default remains no-audio and offline.

## Retry, resume and failure behavior

Scene cache keys include the complete scene, voice/provider key, renderer package source hash, font hash and FFmpeg version. Cache hits require a matching SHA-256 and passing ffprobe checks. Changed/corrupt assets are rebuilt independently; successful scene caches survive retries and restarts. SRT/final assembly are regenerated on each run. Failures retry up to `--attempts` with bounded exponential backoff. Errors/attempts and scene states are persisted in the manifest. Validation/dependency errors are not retried.

The final MP4 is verified before atomic replacement. On failure the CLI exits nonzero and records a failed manifest; any older `final.mp4` is not proof that the new run succeeded. Use manifest status and final SHA-256 to identify a successful run. Run one process per output directory.

## Automated tests

```bash
# Unit tests; integration tests are explicitly skipped unless BOOK_VIDEO_FONT is set.
python -m unittest discover -s tools/book-video-renderer/tests -v

# Complete suite, including real FFmpeg rendering at full output resolution:
BOOK_VIDEO_FONT=/path/to/NotoSansCJKsc-Regular.otf \
  python -m unittest discover -s tools/book-video-renderer/tests -v
```

Integration tests cover every visual type, AAC encoding, oversized audio rejection, source immutability, real cache reuse and corrupt-cache recovery. Synthetic sine audio is used only as a codec test fixture, never in the Naval video or as narration. See [VALIDATION.md](VALIDATION.md) for the cloud execution evidence and limitations.
