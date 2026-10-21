# Codex Runbook: Naval Real-Media Validation

## Operating rule

Work through all non-blocked tasks in order without waiting for additional prompts. Do not stop merely to report intermediate progress. Continue to the next task whenever the next task does not require a missing credential, missing source asset, explicit paid-service authorization, or a destructive/irreversible action.

Do not claim that a scene contains real motion footage merely because its storyboard type is `broll` or `video`. Evidence must come from an actual validated video file and the renderer manifest.

Baseline main commit: `baa617fa5ab9a2a7ff22d2810b7b61a772b8b879`.

Expected source-image directory:

`examples/book-video/naval-test-001/source-images/`

Expected assets:

- `scene_002.webp`
- `scene_003.webp`
- `scene_004.webp`
- `scene_005.webp`
- `scene_006.webp`
- `scene_007.webp`
- `scene_008.webp`
- `scene_009.webp`

The source images are AI-generated 9:16 first-frame assets prepared specifically for this sample.

## Task 1 — Inspect and validate repository state

1. Rebase/check against latest `main`.
2. Read:
   - `openspec/changes/real-media-e2e-validation/**`
   - `tools/book-video-renderer/pipeline.py`
   - `tools/book-video-renderer/book_video_renderer/providers/video.py`
   - `examples/book-video/naval-test-001/storyboard.json`
3. Confirm Naval still has exactly 10 scenes and exactly 8 dynamic scenes: `scene_002` through `scene_009`.
4. Confirm source narration, onscreen text, durations, and scene order have not been modified.
5. Run the existing Book Video Renderer test suite before making functional changes.

Do not stop after reporting this inspection; proceed to Task 2 if the expected source images exist.

## Task 2 — Validate all source images locally

For every expected source image:

1. Verify it decodes successfully.
2. Record width, height, MIME/format, and SHA-256.
3. Confirm portrait orientation and roughly 9:16 geometry.
4. Reject empty/corrupt assets.
5. Do not contact fal.ai or any other external generation service.

Add a small machine-readable validation report under the ignored/local run area or CI artifact area rather than committing generated runtime output.

Proceed immediately to Task 3 if all 8 images validate.

## Task 3 — Run the zero-cost full Naval video preflight

Run `pipeline.py --video-preflight-only` against the real 8 source images with:

- provider: `fal-h3-max-turbo`
- clip length: 5 seconds
- explicit budget cap: USD 1.20
- no `FAL_KEY` requirement
- no Edge TTS
- no network generation request

Verify:

- dynamic scene IDs are exactly scene_002..scene_009
- 8 uncached clips are reported unless valid cache already exists
- conservative estimated cost is consistent with current provider constants
- `network_requests_made == 0`
- `paid_requests_made == 0`

Update the OpenSpec task list to mark the real-source-image zero-cost preflight complete only when this passes.

Do not stop after success; proceed to Task 4.

## Task 4 — Build a two-scene paid-validation fixture without spending money

Create a derived validation storyboard containing only `scene_002` and `scene_003`.

Requirements:

- preserve narration verbatim
- preserve visual prompts, negative prompts, motion hints, and onscreen text
- preserve scene order
- set `target_duration_seconds` to the sum of those two scenes
- do not modify the checked-in source Naval storyboard

Run zero-cost preflight on this two-scene fixture using a budget cap of USD 0.40 and 5-second clips.

Record the exact estimated paid cost and expected request count.

Then prepare, but DO NOT execute, the paid fal command.

### Mandatory paid-service gate

Stop only here if a real fal request would be the next action and there is no explicit user authorization for that spend. Report:

- exact scene IDs
- exact estimated maximum spend
- exact command ready to run
- whether `FAL_KEY` is available in the execution environment, without printing the secret

If explicit authorization for this low-budget sample is already available in the active task context, proceed to Task 5. Otherwise this is a legitimate blocker.

## Task 5 — Generate only two real clips after authorization

Generate only `scene_002` and `scene_003`.

Hard controls:

- 5-second clip setting
- budget cap no higher than USD 0.40
- no other dynamic scenes
- reuse valid provider cache if present
- never print or commit credentials

For each returned clip verify:

- non-empty file
- real video stream via ffprobe
- positive duration
- readable codec metadata
- complete FFmpeg decode
- provider cache metadata contains input fingerprint/hash, provider/model, output hash, and estimated cost

If one request fails, preserve successful cache/output and diagnose before retrying. Do not widen to more scenes to compensate.

Proceed to Task 6 only when both clips are proven real.

## Task 6 — Prove the two real clips enter the renderer

Render the two-scene fixture with `--require-video-assets`.

Verify:

- both scenes use real video as the visual source
- no static-image fallback is accepted for the two dynamic scenes
- final video passes existing QC and full decode
- manifest records the actual provider/video evidence
- source storyboard and source images remain unchanged

Use supplied narration WAV if already available. Otherwise, if Edge TTS is explicitly permitted in the current environment, it may be used; do not silently send narration text to an external service.

Proceed to Task 7 after the visual path is proven.

## Task 7 — Run regression tests and document evidence

1. Run the complete Python/FFmpeg suite.
2. Update `tools/book-video-renderer/VALIDATION.md` with evidence, clearly separating:
   - code/CI validation
   - real-source-image zero-cost preflight
   - two-scene real-motion validation
   - eight-scene full validation (still pending unless actually performed)
3. Update the OpenSpec tasks accurately.
4. Commit only source/config/docs/tests. Do not commit provider caches, secrets, or rendered runtime outputs unless the repository explicitly treats the source images as checked-in fixtures.

If the two-scene paid gate remains blocked, continue all documentation/testing work that does not depend on the paid output.

## Task 8 — Full eight-scene expansion only after the two-scene gate passes

Only after Tasks 5–7 pass:

1. Run a fresh zero-cost full preflight for all 8 dynamic scenes.
2. Report cached vs billable clips and exact estimated remaining cost.
3. Do not initiate the full eight-scene paid generation without explicit authorization for that full estimated spend.
4. After authorization, generate/reuse all 8 clips.
5. Run the complete narrated Naval pipeline with `--require-video-assets`.
6. Verify all 8 dynamic scenes have real video evidence.
7. Verify title cards remain static.
8. Verify final H.264 / 1080x1920 / 30fps / subtitle / audio / full-decode QC.
9. Update OpenSpec and VALIDATION.md with exact evidence.

## Definition of done

The project is not considered fully real-media validated until all 8 dynamic scenes have validated motion clips and the final narrated Naval video passes full QC. Until then, always describe the achieved level precisely.
