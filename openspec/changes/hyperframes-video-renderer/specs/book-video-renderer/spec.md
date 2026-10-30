# Requirements

- The renderer SHALL preserve scene IDs, narration and on-screen text while converting a validated storyboard to timed HyperFrames compositions.
- It SHALL support supplied images, audio and captions, scene-specific animation, transitions, per-scene output, incremental caching and final assembly.
- The manifest SHALL identify actual renderer, source media hashes, cache status, audio availability and output hashes.
- FFmpeg QC SHALL verify duration, dimensions, frame rate, codec and complete decode; missing assets SHALL fail rather than silently become placeholders.
- The existing fal provider and Python pipeline SHALL remain available.
- Automated tests SHALL cover conversion, composition, animation, captions, transitions, CLI invocation, integration, manifest, cache and QC. Real Naval rendering SHALL be separately verified without mocks.
