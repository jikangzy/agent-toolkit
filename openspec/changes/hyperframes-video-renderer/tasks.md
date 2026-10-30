# Tasks

- [x] Inspect plugin skills, environment, repository and PR #24 merge; create branch from origin/main.
- [x] Define independent change, design, requirements and acceptance criteria.
- [x] Implement HyperFrames provider and Python pipeline integration with provenance and caching.
- [x] Render official Naval scene 002 and 003 assets, preserving all storyboard text.
- [x] Validate animation, estimated captions, transitions, CLI, integration, manifest, cache and FFmpeg QC.
- [x] Record actual output and limitations; commit, push, create PR, inspect CI and update issue #23.

## Continuation evidence

- [x] Fetch origin without overwriting the working tree; HEAD equals origin/main.
- [x] Diagnose duplicate overlay and re-render both official scenes; inspect sampled frames.
- [x] Generate a review candidate and run probe, complete decode and blackdetect.
- [x] Verify actual cache invalidation for animation, image and storyboard changes using isolated real renders.

- [x] Implement and render native HyperFrames/GSAP crossfade; probe, decode, blackdetect and visually review the full-resolution result.
- [x] Run full regression with CJK font: 92 passed, no skips; rerun six updated provider tests.
- [x] Verify real unchanged-input scene cache hits at both provider and pipeline layers.
- [x] Verify input-change cache invalidation with separate real HyperFrames renders. Supplied real speech and speech-aligned subtitle timing remain NOT RUN.
- [x] Finish the repeated native render and verify cache hits and final hash.
- [x] Review and commit; push, create PR and update Issue #23.
- [x] Check GitHub Actions: run 91 on 8cada4e passed; optional TTS job was skipped.

## Full Naval HyperFrames validation

- [x] Map scene camera animation from storyboard visual.motion hints instead of hard-coded scene IDs; unit-test pan directions, zoom-in/out, push-in, forward pan and fade-in.
- [ ] Render all 10 original scenes offline with the 8 verified source PNGs and the two built-in title-card scenes.
- [ ] Verify 10/10 scene order, 113-second duration, 1080x1920, 30 fps, H.264, full decode and black-frame detection.
- [ ] Repeat the render; verify all 8 HyperFrames provider caches and all 10 pipeline scene caches hit, with identical final SHA-256.
- [ ] Inspect and retain a 10-scene contact sheet, ffprobe report, manifest and run report as a short-lived CI artifact.
- [ ] Record the exact silent scope: no narration audio, no music, scene-proportional subtitles, no fal.ai or TTS calls. Scene 001 and 010 use local title-card graphics, not generated AI images.
