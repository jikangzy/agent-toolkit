# MVP validation — ChatGPT Work cloud

Execution date: 2026-10-20 (Asia/Shanghai).
Base main: `5926cd8dc2c6ee673852184d307bf81d7017cde2`.

## Environment

- Python 3.12.14.
- FFmpeg and ffprobe 6.1.1, libx264 and libass available.
- Pillow 12.3.0, fontTools and jsonschema available after installing jsonschema.
- No Chinese system font initially. Used a separately downloaded NotoSansCJKsc-Regular.otf with `--font`; system package installation was unavailable. Font is not committed.
- No Chinese TTS engine configured. Naval run uses the explicit no-audio fallback.

## Automated checks

Command (font path varies by machine):

```bash
BOOK_VIDEO_FONT=/path/to/NotoSansCJKsc-Regular.otf \
  python -m unittest discover -s tools/book-video-renderer/tests -v
```

Result: **19 tests passed, zero skipped**. Includes full-resolution FFmpeg integration tests for all five schema visual types, AAC audio encoding, rejecting audio that would truncate narration, input/content preservation, cache reuse, corrupt-cache recovery, bounded retry exhaustion and failed-manifest recording. Audio codec tests use synthetic fixtures only.

## Actual Naval render

Input: `examples/book-video/naval-test-001/storyboard.json` (unchanged).
Output: `output/naval-test-001/` (ignored, not committed).

- `final.mp4` really generated, not a mock or placeholder file.
- 1080×1920, 30 fps, H.264, yuv420p, 113.000 seconds.
- Ten independently encoded scene MP4s in original order.
- UTF-8 Chinese `subtitles.srt`, also burned into the final video.
- Complete `manifest.json` with input/content hashes, per-scene states, cache details, fallbacks and ffprobe QC.
- Default output deliberately has **no audio track**. It is not real Chinese narration. The AAC path is separately exercised by integration tests.
- Rendered frame inspected: Chinese title and subtitle glyphs visible.
- A second identical run reused all ten scene caches.
- Complete final video decoded successfully with FFmpeg (no decode errors).
- Git diff contains only new renderer source, tests, configuration and documentation. No input, existing business file, generated video/audio, cache or font is committed.

The storyboard scene sum is 113 seconds versus its declared 120-second target (5.83% difference), within the skill's ±8% tolerance. Durations and narration were not stretched or rewritten.

## Explicit limitations / not executed

Real Chinese TTS synthesis and speech-to-subtitle forced alignment were **not executed**: there is no configured speech engine. Caller-provided real WAV audio is supported behind the provider protocol, but transcript correctness requires caller verification. No paid image/video API or real stock-media sourcing was tested or included. Background music and requested cinematic transitions are omitted; placeholders use gentle push-in and cuts. These fallbacks are written to the manifest.
