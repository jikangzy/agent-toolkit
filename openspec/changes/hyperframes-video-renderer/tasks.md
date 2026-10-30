# Tasks

- [x] Inspect plugin skills, environment, repository and PR #24 merge; create branch from origin/main.
- [x] Define independent change, design, requirements and acceptance criteria.
- [x] Implement HyperFrames provider and Python pipeline integration with provenance and caching.
- [x] Render official Naval scene 002 and 003 assets, preserving all storyboard text.
- [x] Validate animation, estimated captions, transitions, CLI, integration, manifest, cache and FFmpeg QC.
- [ ] Record actual output and limitations; commit, push, create PR, inspect CI and update issue #23.

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
- [ ] Check GitHub Actions for the current PR head.
