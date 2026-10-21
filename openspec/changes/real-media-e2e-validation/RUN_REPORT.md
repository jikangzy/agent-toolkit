# TWO-SCENE REAL MEDIA EXECUTION REPORT

## Status and repository

**BLOCKED — FAL_KEY MISSING**. Additional independent blockers: PR #24 has NOT merged;
explicit paid authorization is NOT GRANTED. **NO PAID GENERATION EXECUTED**.

- Actual freshly fetched origin/main: `04edeff096fec139880b5bcbe1fdf91663dc4ff4` (verified twice this run, not inferred from an old report).
- PR #24: OPEN, mergedAt null, mergeCommit null; https://github.com/jikangzy/agent-toolkit/pull/24.
- New work branch: `run/naval-two-scene-real-media`, created from that main; same branch-base SHA. No existing branch overwritten; no merge/reset/force-push.
- At checks: HEAD = base, 0 commits ahead/behind; task reports/derived fixture created locally; original user ZIP remains untracked. Final submitted receipt/commit recorded in Issue #23 (a report cannot embed its own future commit SHA).
- Previous 86-test/CI results belong to unmerged PR #24, not this main. Previous branch/history and ignored run evidence preserved.
- This round is strictly scene_002 and scene_003. No full-eight preflight, generation, TTS or render executed.

## Main readiness audit

main includes the basic --video-preflight-only CLI path and basic video/hash
fields, but does not include the guarded helper, request ledger/reservations,
single-submit boundary, full-decode QC, complete source/request lineage or
verify_real_media.py. Formal fixture and RUN_REPORT did not exist on main.
Evidence: validation/two-scene-run/main-capabilities.json and remote-state.json.
No pending PR implementation is copied/cherry-picked or treated as merged code.

## Locked formal inputs: PASS (local validation)

The missing formal fixture was independently derived from current main's original
storyboard on this run branch; entire scene objects equal original scenes 002/003.
IDs, narration, onscreen_text, prompts, negative prompts, motion and per-scene
durations preserved. Target 23 seconds. JSON Schema PASS. Original local source
bytes unchanged; canonical JSON equals fresh origin/main.

- Fixture: examples/book-video/naval-test-001/validation/two-scene-storyboard.json.
- Fixture SHA-256: `994367db06caf6b0be54f7e2d1df8a819d76a1bdf23ad2a518bba699892fa1d3`.
- Original storyboard raw local SHA-256: `e11bbfa91e8916c97246d3ccf924026024920488dacb49344a127b44085cc442`.
- Original Git LF SHA-256: `07212968552b55f488463f27c2bd2edd1f761958ac99423423fee7d939bbbb1f` (Windows checkout EOL differs only).

| Scene | Bytes | Dimensions / format | SHA-256 | Decode / remote |
| --- | ---: | --- | --- | --- |
| scene_002 | 1927237 | 941×1672 RGB PNG | `2de009f630da080d7413474057880c869d79114911fd72ca9de3100e0e28f61a` | PASS / main blob equal |
| scene_003 | 2233438 | 941×1672 RGB PNG | `6f3ef26a69e97f6c6f3cd4cddb31cfcba300f820320d408667c0eea34ea6ccbc` | PASS / main blob equal |

## Fresh formal CLI preflight: BLOCKED (actual error retained)

Actual command executed under connection/API guards:

```sh
python tools/book-video-renderer/pipeline.py examples/book-video/naval-test-001/validation/two-scene-storyboard.json --output output/naval-e2e/two --assets-dir examples/book-video/naval-test-001/source-images --ai-video-provider fal-h3-max-turbo --video-clip-seconds 5 --video-budget-usd 0.40 --video-preflight-only
```

Exit 1:

```text
Pipeline failed: Invalid scene order: expected ['scene_001', 'scene_002'], got ['scene_002', 'scene_003']; scenes will not be reordered
```

Known fix and its safety companions are awaiting PR #24 merge. Do not rename
scene IDs, weaken validation or duplicate the unmerged implementation to present
this run as ready. CLI failure is not labeled PASS. No API call occurred.

## Separate Provider-local preflight: PROVISIONAL PASS

Current main's real Provider.preflight was invoked locally on exactly the two
validated scene objects, with FAL_KEY removed and socket/DNS/HTTP and generation
boundaries rejected. No mocks of cost, source hashes or cache results.
This bypasses only the failing CLI loader for diagnostic calculation; it is NOT
formal paid-readiness or genuine Provider/Renderer acceptance.

- Provider `fal-minimax-h3-max-turbo`; model `minimax/h3-max-turbo/image-to-video`; resolution `768P`.
- Scope scene_002/003, requested 5 seconds, cached [], billable [scene_002, scene_003].
- Rate from current code .025 USD/second, overhead .7s; per clip .1425 USD.
- Prior reserved 0; pending .285; total reserved + pending .285; cap .40; arithmetic budget PASS.
- Guard attempts/network/paid/image uploads all 0.
- scene_002 current-main v1 fingerprint `fd2b24b31a73b4c2799c1987234e2ee209e0056b4780065ef0bf6281272fce48`.
- scene_003 current-main v1 fingerprint `5882b6921b266c692bc447dd02c242a0fb7b65d8b42dd96aa0dd8b0bcfbdcf7e`.
- Output root `output/naval-e2e/two`; cache root `output/naval-e2e/two/video-provider-cache`.
- These v1 fingerprints MUST be recalculated after PR #24 merges v2; they are not authorization to execute older main code.

## Historical ledger/cache: no attempts found in scanned run roots

The same previously planned cache root is retained (not created or changed to
avoid history). Its directory, request-ledger.json, locks and generated cache are
absent. Scanned existing repository run roots output/ and .local/ (runs/artifacts/
cache roots absent); no request-ledger.json or request-ledger.lock found.
No ledger deleted/modified, reservation released or cache invalidated. Existing
uncertain requests: None in scanned roots. This does not query vendor billing.
Evidence: validation/two-scene-run/ledger-inspection.json.

## TWO-SCENE PAID GATE

Scenes:
- scene_002
- scene_003

```text
Requested duration: 5 seconds each
Maximum submissions: 2
Configured estimate per clip: USD .1425 (Provider-only fresh calculation)
Total estimated spend: USD .285
Hard local budget cap: USD .40
FAL_KEY: missing
Existing valid cache: None
Existing uncertain requests: None found in scanned roots
Paid requests already executed in this run: 0
Explicit authorization: NOT GRANTED
Formal CLI readiness: BLOCKED — PR #24 NOT MERGED
```

Do not upload images, submit a fal POST, poll any invented request or automatically
retry. Estimates are not confirmed fal billing. confirmed_actual_cost_usd = unknown.

## Provider / Renderer / output evidence

Both scenes: request ID none; submissions 0; output/cache/codec/duration/FPS/output
SHA/ffprobe/full-decode/Renderer visual_source/fallback provenance all NOT RUN /
not applicable. No mock clip, PNG animation, test pattern, test tone or synthetic
WAV used as acceptance evidence. REAL VISUAL E2E NOT RUN. GENUINE NARRATION E2E
NOT YET PROVEN. No Level 3 or Level 4 completion claim.

## Commands, verification and next action

Executed git status/fetch/branch/log, gh pr view 24 (twice), gh issue view 23,
main source audit, JSON Schema, whole-scene field comparisons, full PNG decode,
SHA-256 and Git blob equality, same-root ledger/lock discovery, guarded actual CLI
attempt and isolated Provider.preflight. All local integrity assertions PASS;
CLI exit 1 is recorded accurately. No production code changed, no external TTS,
no paid requests. Existing historical tests are not rerun or relabeled as fresh.

First resolve PR #24 merge, then fresh-fetch merged main, use a fresh branch and
rerun formal two-scene preflight/ledger checks with the SAME cache root. Supply
FAL_KEY privately in the execution environment. Before any upload/POST, obtain
explicit task-specific authorization covering only scene_002/003, 5 seconds each,
max 2 submissions, total local cap USD .40. Even after authorization, redo fresh
preflight and preserve uncertain history; no automatic expansion to scenes 004–009.
