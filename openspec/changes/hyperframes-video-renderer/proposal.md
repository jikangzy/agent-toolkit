# HyperFrames video renderer

Introduce a local HyperFrames rendering provider alongside the existing Python pipeline and fal provider. Convert storyboard scenes to timed compositions using supplied media, preserve identifiers and text, render independently with content-addressed caching, and retain FFmpeg assembly and QC. No paid video or TTS services are required.

Acceptance: Naval scenes 002 and 003 use their official images and unchanged text, produce distinct animated 1080×1920 H.264 at 30 fps with a transition, and pass full decode and duration checks. Provenance and all omissions must be explicit in the manifest. The real-media-e2e-validation change remains independent.
