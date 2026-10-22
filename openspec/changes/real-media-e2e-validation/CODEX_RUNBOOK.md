# Naval Real-Media E2E Validation — current runbook

This replaces the old branch's independent runbook, after reviewing its one
documentation-only commit `4cc9d37`. Develop from fresh main on
`feat/naval-real-media-e2e-validation`; never develop directly on main.
Base for this run: `04edeff096fec139880b5bcbe1fdf91663dc4ff4`.
See RUN_REPORT.md for fresh identity, stage results, limitations and PR/CI.

## 1. Source and contract validation (no generation)

Read Issue #23 and the Change proposal/tasks/spec first. Run `git fetch origin`;
record origin/main SHA, branch base, HEAD, ahead/behind and worktree status.
Do not reset, clean or overwrite another branch. Formal sources are original
`scene_002.png` through `scene_009.png`, not WebP, under
`examples/book-video/naval-test-001/source-images/`. Preserve README and source
storyboard. No substitute, placeholder or regenerated source image is accepted.

```sh
python tools/book-video-renderer/validate_naval.py --remote-ref origin/main
python -m compileall -q tools/book-video-renderer
```

The source report compares freshly fetched main blobs to local original PNGs;
optionally pass a freshly saved recursive GitHub tree JSON with `--remote-tree`.
It records full Pillow decode, dimensions, mode, bytes, SHA-256 and scene mapping.
The separate integrity file records local CRLF and canonical Git LF byte hashes.
The derived fixture preserves the entire scene_002/003 objects and sums their
durations (23 seconds). No source narration/text/prompt/hint/ID is rewritten.

## 2. Eight-scene and two-scene guarded offline CLI runs

Run from repository root. Neither command needs FAL_KEY. The wrapper removes it,
blocks connection/DNS/upload/generation boundaries and records attempts. Reports
are real-input CLI results, not fabricated mock preflight results.

```sh
python tools/book-video-renderer/offline_preflight.py --report examples/book-video/naval-test-001/validation/eight-scene-preflight.json examples/book-video/naval-test-001/storyboard.json --output output/naval-e2e/full --assets-dir examples/book-video/naval-test-001/source-images --ai-video-provider fal-h3-max-turbo --video-clip-seconds 5 --video-budget-usd 1.20 --video-preflight-only
python tools/book-video-renderer/offline_preflight.py --report examples/book-video/naval-test-001/validation/two-scene-preflight.json examples/book-video/naval-test-001/validation/two-scene-storyboard.json --output output/naval-e2e/two --assets-dir examples/book-video/naval-test-001/source-images --ai-video-provider fal-h3-max-turbo --video-clip-seconds 5 --video-budget-usd .40 --video-preflight-only
python tools/book-video-renderer/check_e2e_contract.py
```

Require exact scope, accurate cached/billable split, finite sufficient budget,
zero network/paid/upload attempts. Estimates use actual repository configuration
`(requested seconds + overhead) × configured USD/second`, not a guaranteed vendor
bill. Preserve complete reports and any existing valid cache.

## 3. Full offline regression and CI

Provide FFmpeg/ffprobe and a CJK font; set BOOK_VIDEO_FONT to its path, then run:

```sh
python -m unittest discover -s tools/book-video-renderer/tests -v
```

This includes supplied WAV/test-tone codec, subtitle alignment, actual local
FFmpeg rendering, corrupt cache, durable reservation, uncertain API failure,
scope/fingerprint/lock and no-network CLI tests. Fake fal + synthetic local
motion is explicitly test evidence, never real-service acceptance.
On Windows, tests need local OS socketpair and atomic rename permissions. Report
real environment failures and rerun with required access; do not add skips.
CI runs the full suite and guarded preflight on formal PNGs, uploading a small
`naval-zero-cost-evidence` artifact. The live Edge TTS sample remains explicit
workflow_dispatch opt-in and is not invoked by this task.

## 4. Mandatory paid gate — do not execute yet

Current task grants NO paid generation permission and NO external TTS permission.
Check FAL_KEY as `present`/`missing` only. Scope is scene_002/003, requested clip
length 5 seconds, maximum two generation submissions, budget USD .40. Read fresh
preflight for cached/billable counts and exact configured estimate (.285 USD
when both are cold under current settings). Keep output/cache root unchanged.

Command prepared for use ONLY after specific paid authorization and model/rate/
SDK/credential verification (not executed in this run):

```sh
python tools/book-video-renderer/pipeline.py examples/book-video/naval-test-001/validation/two-scene-storyboard.json --output output/naval-e2e/two --assets-dir examples/book-video/naval-test-001/source-images --ai-video-provider fal-h3-max-turbo --video-clip-seconds 5 --video-budget-usd .40 --require-video-assets --tts-provider none --attempts 1
```

This is a silent visual run; no narration PASS may be claimed. Provider ledger
reserves estimates before submission, retains uncertain failures and never
automatically resubmits identical input. Local encoder retry is separate from
Provider invocation. Do not delete/recreate/move the ledger to bypass it. A stale
lock, missing result, failed download/decode or uncertain response requires
manual service-result/billing reconciliation before any retry. Preserve a valid
successful scene_002 cache if scene_003 fails. Actual billing remains unknown
without trustworthy vendor evidence; local caps are conservative estimates,
not a provider-enforced monetary ceiling. The audited fal-client 1.0.3 retries queue POSTs up to 10 times. Inference now bypasses subscribe: exactly one authenticated HTTPS queue POST, redirects refused, no submission retry, request ID saved immediately, followed by GET-only polling. Upload SDK may retry storage transfers, not inference. Live model availability/rate/service billing still requires review before execution.

## 5. Automatic post-generation audit (local only, ready but not real-run)

```sh
python tools/book-video-renderer/verify_real_media.py --storyboard examples/book-video/naval-test-001/validation/two-scene-storyboard.json --output output/naval-e2e/two --source-images examples/book-video/naval-test-001/source-images --evidence output/naval-e2e/two/real-media-audit.json
```

Verify each source hash/input fingerprint, Provider/model/origin/cache status,
actual clip path/hash, codec/dimensions/FPS/duration, full decode, encoded scene
hash and final hash/QC. Keep any service request ID and billing receipts. Local
audit success cannot authenticate a service receipt or confirm billing. Inspect
Manifest's audio source/status and subtitle alignment independently. No generated
clip or narrated E2E success exists in this run.

## 6. Expansion and reports

Only after two real clips enter Renderer and pass full visual QC may the next
stage be considered. Narrated two-scene acceptance additionally requires genuine
authorized narration. Supplied WAV is local; preserve narration, extend only a
derived timeline as necessary, never truncate text. Edge TTS requires separate
explicit permission, sends narration externally and has no verified availability
or fee evidence in this task.

Then fresh full preflight must revalidate scene_002/003 caches and calculate the
remaining six billable scenes. Two-scene permission does not authorize expansion.
Do not generate remaining clips without separate full-scope authorization.
Full acceptance requires 8 real dynamic clips + 2 title cards, 10-scene order,
H.264/1080x1920/30fps, actual narration/AAC/subtitles, provenance and full decode.
Keep RUN_REPORT.md, tasks.md, VALIDATION.md and Issue #23 accurate. Mark only
proved stages complete; leave real-service tasks open. Publish FINAL REVIEW
PACKET, commit only related source/docs/small evidence, push work branch and open
a PR to main. Do not merge or force-push.
