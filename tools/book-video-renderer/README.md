# Book Video Renderer MVP

Python CLI for the repository's locked storyboard contract. It validates the existing JSON Schema, preserves scene order and exact narration/on-screen text, accepts optional per-scene AI-generated still images, falls back to labeled placeholder cards for missing images, adds gentle push-in motion, creates Chinese SRT subtitles, burns them into the final video, and verifies output with ffprobe. The CLI does not itself call an image-generation API; the agent or user supplies generated images.

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
  --voice zh-CN-YunxiNeural

python tools/book-video-renderer/renderer.py \
  .local/runs/naval-test-001/storyboard.render.json \
  --output output/naval-test-001 \
  --assets-dir output/naval-test-001/images \
  --tts-audio-dir output/naval-test-001/audio \
  --tts-audio-provider edge-tts \
  --tts-audio-voice zh-CN-YunxiNeural
```

The preflight script writes one MP3 and WAV per scene, measures WAV durations, adds a default 250 ms margin rounded to a video frame, and writes a timing report. The renderer records `speech_status: generated_audio`, the provider/voice, and the external-service notice in `manifest.json`. The `--tts-audio-provider` / `--tts-audio-voice` flags describe the source of the supplied WAVs; they do not trigger another network request.

**Important limitations:** Edge TTS is an online, third-party service, not an offline engine or a guaranteed production API. It requires network access and may change or throttle. Narration text is sent to that service. The provider is optional and replaceable; the default renderer still performs no TTS network calls. Subtitle timing remains scene-proportional in this iteration, so it is not yet word-level aligned to the generated audio.

### Render the sample in GitHub Actions (no local computer required)

After the workflow file is merged into the repository's default branch, open **GitHub → Actions → Book Video Renderer tests → Run workflow**, select `main` (or the branch you want to test), and set `render_tts_sample` to `true`. GitHub only enables manual `workflow_dispatch` for workflows present on the default branch. The job renders only the first 8-second scene, preserving its narration verbatim. This is an explicit opt-in because it sends that narration to the external Edge TTS service. The workflow uploads `final.mp4`, `manifest.json`, and `subtitles.srt` as the `naval-test-001-edge-tts` artifact; generated files are not committed to Git. The default value is `false`, so normal CI runs never call the speech service.

The MVP accepts 1080x1920 / 9:16 / 30 fps only; output is H.264/yuv420p with AAC when real audio is supplied. Schema validation is followed by unique-ID and timing checks. Scene durations are rounded to the nearest frame. Total duration must fall within ±8% of the declared target; it is never silently stretched. The Naval example has 113 seconds of scenes against a 120-second target and produces a 113-second video.

Output layout:

```text
output/naval-test-001/
  final.mp4
  manifest.json
  subtitles.srt
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

Scene cache keys include the complete scene, voice/provider key, renderer source hash, font hash and FFmpeg version. Cache hits require a matching SHA-256 and passing ffprobe checks. Changed/corrupt assets are rebuilt independently; successful scene caches survive retries and restarts. SRT/final assembly are regenerated on each run. Failures retry up to `--attempts` with bounded exponential backoff. Errors/attempts and scene states are persisted in the manifest. Validation/dependency errors are not retried.

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
