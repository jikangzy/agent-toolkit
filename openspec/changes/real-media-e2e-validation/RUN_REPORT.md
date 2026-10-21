# Naval Real-Media E2E Validation — RUN REPORT

## Stage A — repository and code audit: PARTIAL

- Actual origin/main, work branch base and current HEAD: `04edeff096fec139880b5bcbe1fdf91663dc4ff4`.
- Work branch: `feat/naval-real-media-e2e-validation`, freshly created from origin/main. Zero commits ahead at stage start; no tracked pre-existing changes. Untracked user ZIP attachment preserved and excluded from staging.
- Commands: `git status --short --branch`; `git fetch origin`; `gh issue view 23 --json title,body,comments`; `git log origin/main..origin/feat/naval-source-images-and-codex-runbook`; `git diff --stat origin/main...origin/feat/naval-source-images-and-codex-runbook`.
- Historical branch has one independent documentation commit (4cc9d37), adding CODEX_RUNBOOK.md; no implementation fixes. Read it; do not develop from that branch.
- Read proposal/tasks/spec, README/VALIDATION, pipeline/video/tts/renderer/manifest/qc/scene/subtitle/prepare_narration, tests and CI.
- Baseline pipeline suite: 11 tests PASS (`output/naval-e2e/baseline-pipeline-tests.log`). Full baseline suite pending FFmpeg setup; interrupted previous run is not counted.
- Findings: preserved-ID fixture rejected by start-at-001 validator; video assets lack full-decode/FPS checks; budget checked only in preflight (direct calls/restarts need durable protection); error manifests omit provider failure provenance. Provider invocation is outside local encoder retry, but rerunning after an uncertain API failure can resubmit without a ledger.
- AIKnowledge: SHOULD_SEARCH for environment/debugging, index-first NO_MATCH, zero full-card/candidate reads, no knowledge writes.
- Cache: no real motion cache validated. Generation/TTS network requests 0; paid requests 0. GitHub and dependency-download traffic is separate from generation counters.
- Next: formal-source checks, guarded preflight, defect fixes, complete tests/CI.

## Stage B — formal source images and storyboard: PASS

- Repository identity as Stage A; branch has local validation scripts/reports, no commits yet. Fresh GitHub branch/tree API confirms main above and tree `bf7a4f1438a7c962ad0d063e3cc110455c1cf2d8`. Every PNG tree blob compared byte-for-byte with freshly fetched Git content and local files.
- Command: `python tools/book-video-renderer/validate_naval.py --remote-tree output/naval-source-upload/current-main-tree.json`.
- `examples/book-video/naval-test-001/validation/source-images-report.json`: 8/8 original PNGs, full Pillow decode PASS; all 941×1672 RGB, portrait approximately 9:16. No conversion/replacement; README untouched.
- `validation/storyboard-integrity.json`: 10 scenes, 8 dynamic IDs scene_002..009, two title cards; all JSON fields identical to origin/main. Local original unchanged.
- Raw local storyboard SHA-256 (Windows CRLF): `e11bbfa91e8916c97246d3ccf924026024920488dacb49344a127b44085cc442`.
- Git LF blob SHA-256: `07212968552b55f488463f27c2bd2edd1f761958ac99423423fee7d939bbbb1f`. Byte-hash difference is checkout EOL only, explicitly recorded rather than hidden.
- `validation/two-scene-storyboard.json`: exact original scene_002/003 objects, target 23s, unchanged narration/text/prompts/hints/order/durations.
- Cache: no real clips; no real-motion or E2E success claimed. Generation network 0, paid 0, authorized spend NONE.
- Next: guarded preflights, durable budget protections, regression tests.

## Stage C — guarded formal-source preflights: PASS

- Base/start/current committed HEAD: `04edeff096fec139880b5bcbe1fdf91663dc4ff4`; work branch `feat/naval-real-media-e2e-validation`; source/docs/tests modified locally, not yet committed. Main unchanged.
- Actual CLI runs through `offline_preflight.py`, which removes FAL_KEY, blocks socket connection/DNS/HTTP events, and rejects upload/submit/subscribe calls. This exercises actual CLI/image/cache/budget logic, not mocked preflight results.
- Full command: `python tools/book-video-renderer/offline_preflight.py --report examples/book-video/naval-test-001/validation/eight-scene-preflight.json examples/book-video/naval-test-001/storyboard.json --output output/naval-e2e/full --assets-dir examples/book-video/naval-test-001/source-images --ai-video-provider fal-h3-max-turbo --video-clip-seconds 5 --video-budget-usd 1.20 --video-preflight-only`.
- Two-scene command: same wrapper with `validation/two-scene-storyboard.json`, `--output output/naval-e2e/two`, budget `.40`, report `validation/two-scene-preflight.json`.
- Full: scene_002..009 exactly, cached [], billable 8; per-clip configured estimate `(5 + 0.7) * 0.025 = USD .1425`, total USD 1.14, cap 1.20 PASS.
- Two: scene_002/003 exactly, cached [], billable 2, estimate USD .285, cap .40 PASS.
- Both: guard connection attempts 0, generation attempts 0, network requests 0, paid requests 0, image uploads 0. No real clip generated. Rates are repository configuration, not a verified vendor bill/price guarantee.
- Repair: validator now permits positive contiguous original IDs from any start; rejects gaps/reordering/zero. Original source untouched.
- Tests: baseline 11 pipeline tests passed; full regression is running with local FFmpeg 9.0.2 and Microsoft YaHei. Initial sandbox run hung in asyncio socketpair; faulthandler identified it, own stalled processes ended, tests rerun with required local OS access. Temp-path normalization fixes Windows 8.3 aliases in tests; no skips added to bypass failures.
- Paid scope scene_002/003, 5 seconds, max 2 clips, cap .40; authorization NOT GRANTED. FAL_KEY status will be recorded in final packet. NO PAID GENERATION EXECUTED.
- Next: finish budget/cache/manifest/full-decode regressions, documentation, CI and PR; paid media stays blocked.

## Stage D — non-paid repair and test evidence: PARTIAL (final frozen-code run in progress)

- Base/start/committed HEAD remains `04edeff096fec139880b5bcbe1fdf91663dc4ff4`; work branch `feat/naval-real-media-e2e-validation`; source/docs/tests and small validation evidence changed, original storyboard/PNG/README unchanged. No commits ahead yet.
- Completed an 80-test full FFmpeg run with no skips: `output/naval-e2e/final-regression-2.log`, 125.503s, PASS. Latest source snapshot/audio-decode/local-auditor changes and two additional regressions are being run once more on frozen code; final report will use that run.
- Earlier real failures: missing FFmpeg; asyncio socketpair sandbox hang; Windows 8.3 vs resolved temp paths; test assumptions labeling deterministic title cards as fallback. Installed FFmpeg only under ignored output; allowed local test OS access; normalized test temp paths; strengthened title-card assertions while preserving dynamic fallback checks. No acceptance condition or skip was relaxed.
- Implemented: preserved contiguous positive source IDs, full video/final decode, finite codec/FPS/duration validation, finite budget cap, durable per-cache-root request reservations/lock, uncertain request reconciliation, immutable upload snapshot, source/config fingerprint, cache provenance, request-vs-preflight counters, redacted API failures, failed/unstarted scene states, actual Renderer clip/scene hashes, explicit title cards, supplied WAV source/hash/full decode.
- Budget formula is conservative configured estimate only; failed/uncertain submissions retain reservation. Actual billing null, SDK retry/model availability/live price not verified. Cache root must not be changed to bypass request history.
- `verify_real_media.py` checks fingerprint, source/clip/encoded-scene/final hashes, Provider/model/origin, decoded video metadata and final QC; local audit cannot authenticate a vendor receipt. Mock fal + synthetic local moving test source traversed Provider -> Renderer -> final QC and valid-cache reuse; explicitly NOT real fal media evidence.
- No real cache/clip produced. Generation/TTS external requests 0; paid 0. GitHub and FFmpeg package download network occurred separately.
- FAL_KEY: missing. Two-scene/full-eight authorization: NOT GRANTED. NO PAID GENERATION EXECUTED.
- Real-motion and narrated acceptance remain NOT RUN. Next: finish frozen-code test evidence, structural OpenSpec check, PR/CI and final packet. No paid action is pending execution in this task.

# FINAL REVIEW PACKET

## 1. Overall Status

PARTIAL. All available non-paid local preparation PASS. Real motion remains
BLOCKED — PAID AUTHORIZATION REQUIRED. NO PAID GENERATION EXECUTED.

## 2. Repository

- Repository jikangzy/agent-toolkit; base main; fresh initial main and work base `04edeff096fec139880b5bcbe1fdf91663dc4ff4`.
- Work branch `feat/naval-real-media-e2e-validation`.
- Executable validation commit: pending submission.
- Current HEAD at report preparation: 04edeff096fec139880b5bcbe1fdf91663dc4ff4 (task changes uncommitted at test time).
- Relative main: 0 commits at test time; task changes in worktree.
- Worktree: task source/docs/small evidence changes; user ZIP untracked; ignored runtime outputs excluded.
- PR: pending submission; CI: pending PR (NOT RUN yet).
- Exact final report-only commit is the PR head and is also published to Issue #23; a committed report cannot embed its own future object hash. Tested Python file hashes bind the executable revision independently of report-only commits.

## 3. OpenSpec

Change `openspec/changes/real-media-e2e-validation/`: OPEN / PARTIAL.
Completed: audit, remote PNG/source integrity, preserved-ID fixture, both guarded
preflights, budget/lock/uncertain-request protections, validated cache/provenance,
full-decode QC, local WAV/mock TTS, full regression, current runbook/evidence.
Blocked tasks: real two-scene generation/render/narration, separately authorized
eight-scene expansion and genuine narrated 10-scene acceptance. No real-service
checkbox complete. Spec adds source preservation, zero-network proof, durable
reservation, cache/provenance/full-decode and four independent acceptance levels.

## 4. Source Images

8/8 originals PASS; fresh GitHub main tree `bf7a4f1438a7c962ad0d063e3cc110455c1cf2d8` and fetched
blobs compared byte-for-byte with local PNGs; full Pillow verify/load, portrait
ratio within .01 of 9:16 and Renderer format mapping PASS. Inspected contact sheet
shows eight distinct non-empty book/life/concept compositions, not program
placeholders. Derived sheet stays local at output/naval-e2e/source-contact-sheet.png.
Machine evidence: examples/book-video/naval-test-001/validation/source-images-report.json.

| Scene | Path | Bytes | Dimensions / format | SHA-256 | Decode / remote |
| --- | --- | ---: | --- | --- | --- |
| scene_002 | `examples/book-video/naval-test-001/source-images/scene_002.png` | 1927237 | 941×1672 PNG RGB | `2de009f630da080d7413474057880c869d79114911fd72ca9de3100e0e28f61a` | PASS / main verified |
| scene_003 | `examples/book-video/naval-test-001/source-images/scene_003.png` | 2233438 | 941×1672 PNG RGB | `6f3ef26a69e97f6c6f3cd4cddb31cfcba300f820320d408667c0eea34ea6ccbc` | PASS / main verified |
| scene_004 | `examples/book-video/naval-test-001/source-images/scene_004.png` | 1974714 | 941×1672 PNG RGB | `46038119697b102dc0907c9ea54df24f22978d66716e2237b3b77264c3598794` | PASS / main verified |
| scene_005 | `examples/book-video/naval-test-001/source-images/scene_005.png` | 2286574 | 941×1672 PNG RGB | `6d8b55cb3d3a1bbbafc93fef872dc16aa0a6a08e32550083ae9daccf66ee4943` | PASS / main verified |
| scene_006 | `examples/book-video/naval-test-001/source-images/scene_006.png` | 2162267 | 941×1672 PNG RGB | `6f76ec1c9f0829cae343e8bffec4d57e91b810adb9b6333ca944d6920f196779` | PASS / main verified |
| scene_007 | `examples/book-video/naval-test-001/source-images/scene_007.png` | 2130289 | 941×1672 PNG RGB | `e0e0744a6efbdd0c7b1502a12bd53846f3ef1b7d3e27cbdba89fe5ed99e4a8d0` | PASS / main verified |
| scene_008 | `examples/book-video/naval-test-001/source-images/scene_008.png` | 1786242 | 941×1672 PNG RGB | `b4d33602eaba574215adfeb0ac2ebc4c717874df46ce2f888b9446e9ee0d707d` | PASS / main verified |
| scene_009 | `examples/book-video/naval-test-001/source-images/scene_009.png` | 1880009 | 941×1672 PNG RGB | `db82eccd52acabfe20ab1e832e0640b1962481d9bed5d86a48e129d97a810b75` | PASS / main verified |

## 5. Original Storyboard Integrity

- Raw local Windows CRLF SHA-256 `e11bbfa91e8916c97246d3ccf924026024920488dacb49344a127b44085cc442`.
- Canonical Git LF SHA-256 `07212968552b55f488463f27c2bd2edd1f761958ac99423423fee7d939bbbb1f`.
- Before/after local bytes unchanged; all JSON fields and canonical LF equal main.
- Narration, onscreen text, IDs/order, durations/prompts/negative prompts/motion unchanged.
- 10 scenes, 8 dynamic scene_002..009, title cards scene_001/010; sum 113s / target 120s.
- Exact preserved scene_002/003 objects form the derived fixture, target 23s.
- Evidence: validation/storyboard-integrity.json and two-scene-storyboard.json.

## 6. Eight-Scene Preflight

PASS. Exact scene_002..009; cached []; billable 8; prior reserved 0.
Configured formula `(5 + .7) × .025 = USD .1425/clip`; estimated USD 1.14,
cap 1.20, budget PASS. Network requests 0, paid 0, image uploads 0, generation
API calls 0; network/API guard attempts 0. Full real-input CLI arguments/output:
validation/eight-scene-preflight.json. Rate is repository configuration, not a
confirmed vendor bill/price guarantee.

## 7. Two-Scene Preflight

PASS. Exact scene_002/003; cached []; billable 2; requested clips 5s each;
estimate USD .285, cap .40, budget PASS. Network/paid/uploads/API calls 0;
guard attempts 0. Full output: validation/two-scene-preflight.json.
Both preflights used actual CLI/local sources under credentials-removed network/
upload/generation guards; preflight calculations were not mocked.

## 8. Paid Gate

Scope scene_002/003; 5s; maximum 2 submissions; cap USD .40; expected billable 2;
configured maximum estimate .285. FAL_KEY: missing.
Two-scene authorization NOT GRANTED; full-eight authorization NOT GRANTED.
Actual paid requests 0; estimated incurred spend 0. Confirmed vendor charge:
not queried/no billing evidence. Nominal budget proposal .40 unspent; actual
authorized spend NONE. Real request ledger absent. NO PAID GENERATION EXECUTED.
Before any future spend verify live model/rate/SDK retry/service constraints;
local estimate caps do not enforce vendor charges. Keep cache root unchanged;
uncertain/failed submissions retain reservations and require manual result/billing
reconciliation. Accurate prepared generation and post-QC commands: CODEX_RUNBOOK.md.

## 9. Real Video Evidence

TWO-SCENE REAL MOTION VALIDATION: NOT RUN — PAID AUTHORIZATION REQUIRED.
FULL EIGHT-SCENE REAL MOTION VALIDATION: NOT RUN — PAID AUTHORIZATION REQUIRED.
Configured target Provider fal-minimax-h3-max-turbo / model
minimax/h3-max-turbo/image-to-video is intent only. Every scene lacks real output
path/hash, codec/duration/resolution/FPS, request/billing evidence, ffprobe/full
decode and actual Renderer proof. No fallback is accepted as genuine footage.

| Scene | Formal source SHA-256 | Real request | Output/cache | Actual cost | Renderer / QC |
| --- | --- | --- | --- | --- | --- |
| scene_002 | `2de009f630da080d7413474057880c869d79114911fd72ca9de3100e0e28f61a` | NOT RUN | none | none | NOT PROVEN |
| scene_003 | `6f3ef26a69e97f6c6f3cd4cddb31cfcba300f820320d408667c0eea34ea6ccbc` | NOT RUN | none | none | NOT PROVEN |
| scene_004 | `46038119697b102dc0907c9ea54df24f22978d66716e2237b3b77264c3598794` | NOT RUN | none | none | NOT PROVEN |
| scene_005 | `6d8b55cb3d3a1bbbafc93fef872dc16aa0a6a08e32550083ae9daccf66ee4943` | NOT RUN | none | none | NOT PROVEN |
| scene_006 | `6f76ec1c9f0829cae343e8bffec4d57e91b810adb9b6333ca944d6920f196779` | NOT RUN | none | none | NOT PROVEN |
| scene_007 | `e0e0744a6efbdd0c7b1502a12bd53846f3ef1b7d3e27cbdba89fe5ed99e4a8d0` | NOT RUN | none | none | NOT PROVEN |
| scene_008 | `b4d33602eaba574215adfeb0ac2ebc4c717874df46ce2f888b9446e9ee0d707d` | NOT RUN | none | none | NOT PROVEN |
| scene_009 | `db82eccd52acabfe20ab1e832e0640b1962481d9bed5d86a48e129d97a810b75` | NOT RUN | none | none | NOT PROVEN |

Mock fal + a synthetic local moving test pattern passed actual Provider ->
Renderer -> scene/final decode/QC and valid-cache reuse/fingerprint-tampering
tests. This is explicitly offline test evidence, not F/G/H/I real-service success.
verify_real_media.py audits local lineage/QC but cannot authenticate vendor receipts.

## 10. TTS

Formal run provider none; voice unused; no genuine narration asset. Local supplied
per-scene WAV is supported, full-decoded and hashed, with source labels, duration/
no-truncation checks and derived measured timeline. Tests cover local synthetic
WAV/test tones, AAC, mixing, aligned/non-overlapping SRT and Edge mock behavior.
Test tones are not narrated output. Optional Edge provider/zh-CN-YunxiNeural needs
explicit permission and sends text externally; adapter requires no key, but live
availability/fee/quality not verified. External TTS requests 0. Real spoken content,
voice quality and production audio/video alignment remain unverified.

## 11. Final Render

Formal final MP4 NOT RUN. Duration/resolution/FPS/codecs/audio/subtitles/scene
count/real-motion inputs/Manifest/full decode/QC NOT PROVEN for real media.
Target H.264 1080×1920 30fps; AAC when genuine narration supplied; 8 true dynamic
clips + 2 title cards in original order. Do not promote silent/synthetic tests to
genuine narrated E2E acceptance.

## 12. Tests and CI

- Compile PASS: python -m compileall -q tools/book-video-renderer.
- Full frozen-source local suite: 82 PASS, 0 failures/errors/skips, 119.938s, Python 3.12.1, FFmpeg 9.0.2 + YaHei.
- CLI/Pipeline/Provider/TTS/Renderer/Manifest/cache/source/fixture/preflight/supplied WAV/real FFmpeg integration included; per-test IDs and canonical tested-source hashes in validation/test-results.json; full log output/naval-e2e/review-regression.log.
- Prior missing dependency/socketpair/Windows alias/title-card assertion failures fixed and rerun; no deleted tests or added skips.
- OpenSpec structural/evidence/paid-boundary check PASS (check_e2e_contract.py). Official upstream OpenSpec CLI NOT RUN: not installed/configured here; not falsely counted as a pass.
- Workflow YAML parse, CLI --help and git diff --check PASS.
- CI: pending PR; pending URL. CI uses formal PNGs, guarded preflight and full local suite; live Edge job remains opt-in and not executed. Artifact: naval-zero-cost-evidence.
- GitHub/dependency download traffic occurred; global network count was not instrumented. Zero request claims above refer only to guarded preflights and generation/TTS boundaries.

## 13. Proven Claims

A code implemented; B full local automation PASS; D formal main originals PASS;
E actual-source zero-network preflights PASS. C CI separately recorded above.
Original inputs preserved. No actual video generation/upload/external TTS.
Budget/cache/provenance/QC behaviors proved within offline/mock/local-test scope.

## 14. Not Yet Proven

F genuine fal output; G genuine Provider clip enters Renderer; H real narrated
two-scene E2E; I full-eight/10-scene real narrated E2E. Live SDK/model/rate/billing,
voice quality and independent service evidence remain unverified.

## 15. Remaining Blockers

Missing FAL_KEY and specific paid authorization; live monetary-cap/SDK retry/model
behavior requires review before spend; actual narration source or explicit external
TTS permission absent. These block real media only; all feasible local prep/docs/
tests/PR/CI work is carried forward. Do not close Change as media-complete.

## 16. Next Recommended Action

Review PR/evidence. If proceeding later, privately supply credential, verify live
service/budget/retry constraints, authorize only scene_002/003 (5s, max2, cap .40,
current estimate .285), fresh-preflight the same cache root, then run the prepared
command and local auditor, retaining receipts and genuine audio evidence.
Separate six-scene/full-scope permission is required for expansion. No paid action
is awaiting automatic execution in this task.
