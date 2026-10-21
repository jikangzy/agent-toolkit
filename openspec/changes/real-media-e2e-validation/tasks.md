# Tasks

- [x] 核对最新 main、CI、Pipeline CLI、动态视频 Provider、TTS 与 Naval 样例。
- [x] 确认 Naval 当前只有 storyboard，不能仅凭 8 个 broll/video 标记宣称真实视频已生成。
- [ ] 增加完全无付费、无网络的 AI 视频 dry-run preflight；不得要求 FAL_KEY，不得调用 fal API。
- [ ] 为 dry-run preflight 增加自动化测试：动态场景统计、缺失源图、无效源图、缓存命中、预算不足、预算足够。
- [ ] 生成或提供 1–2 个动态场景的合法源图，并在低预算上限内执行首次真实视频小样。
- [ ] 验证小样生成的视频包含真实 video stream、可被 ffprobe/FFmpeg 完整读取，并在 manifest 中记录 provider/model/cache/cost evidence。
- [ ] 使用 `--require-video-assets` 验证小样进入最终合成，缺真实视频时必须 fail closed，不允许静态 fallback 冒充真实视频。
- [ ] 为小样接入中文旁白：优先 supplied WAV；如使用 Edge TTS，必须显式 opt-in 并记录 provider/voice/字幕对齐结果。
- [ ] 小样通过后，将真实视频验证扩展到 Naval 全部 8 个动态场景。
- [ ] 全量成片通过 H.264/1080x1920/30fps/AAC/字幕/scene count/full decode QC。
- [ ] 更新 VALIDATION.md，区分“代码/CI 已验证”“真实媒体小样已验证”“8 场景全量已验证”，不得混用。


## Current two-scene execution attempt (main checked live)

- [x] Fresh fetch/API verify PR #24 is OPEN and not merged; create run/naval-two-scene-real-media from actual main.
- [x] Revalidate only scene_002/003 formal PNGs and exact derived fixture; preserve original storyboard and report SHA-256.
- [x] Inspect same planned cache root/history without deleting ledgers or evading reservations; no history found in scanned repository roots.
- [x] Execute and record guarded current-main CLI failure, plus separate provisional local Provider cost/fingerprint check (not formal readiness).
- [x] Record FAL_KEY missing, explicit authorization NOT GRANTED, submissions/uploads/paid requests 0; preserve paid Gate.
- [ ] PR #24 actually merged into latest main and guarded formal two-scene CLI preflight PASS.
- [ ] FAL_KEY present and explicit two-scene paid authorization granted after fresh checks.
- [ ] scene_002 real generation + receipt/full decode/provenance (NOT RUN).
- [ ] scene_003 real generation + receipt/full decode/provenance (NOT RUN).
- [ ] Both real clips enter require-video-assets Renderer and pass visual E2E (NOT RUN).
- [ ] Genuine narration E2E (NOT RUN; separate external TTS permission required if needed).

Current execution evidence: RUN_REPORT.md and examples/book-video/naval-test-001/validation/two-scene-run/.
