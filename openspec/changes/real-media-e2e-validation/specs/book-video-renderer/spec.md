# Book Video Renderer: Real Media End-to-End Validation

## Requirement: zero-cost dry-run preflight

系统 MUST 提供一个显式的 dry-run/preflight 路径，用于检查 AI 视频生成前置条件，并且该路径 MUST NOT 上传文件、调用外部生成 API 或产生付费请求。

### Scenario: no API credential

- GIVEN Naval storyboard 和本地源图目录
- AND 未设置 `FAL_KEY`
- WHEN 执行视频 dry-run preflight
- THEN 命令能够完成本地检查
- AND 输出动态场景数、缓存命中、预计待生成场景、预计费用和预算上限
- AND 不进行任何网络生成请求

### Scenario: missing source image

- GIVEN 任一 `video`/`broll` 场景缺少对应源图
- WHEN 执行 preflight
- THEN 命令失败
- AND 明确列出缺失 scene id
- AND 不进行付费请求

### Scenario: budget exceeded

- GIVEN 所有源图有效
- AND 预计费用高于显式预算上限
- WHEN 执行 preflight
- THEN 命令失败
- AND 报告预计费用、预算和待生成 clip 数
- AND 不进行付费请求

## Requirement: staged paid validation

真实 AI 视频生成 MUST 采用逐步放量策略。第一次真实请求 SHOULD 限定为 1–2 个动态场景；只有这些场景通过视频流、合成和 QC 验证后，才可扩展到全部 8 个 Naval 动态场景。

### Scenario: first paid sample

- GIVEN 用户已提供/确认有效 Provider 凭证
- AND 显式预算上限足够覆盖 1–2 个 clip
- WHEN 执行小样生成
- THEN 实际请求数不得超过所选小样场景
- AND 每个结果必须存在可探测 video stream
- AND 生成文件必须可被 FFmpeg 完整解码
- AND manifest/缓存元数据记录 provider、model、输入 fingerprint、结果 hash 和成本估计

## Requirement: real motion evidence

系统 MUST NOT 将 storyboard 中的 `video` 或 `broll` 类型本身作为“真实动态视频已生成”的证据。

### Scenario: missing generated clip

- GIVEN 场景类型为 `broll` 或 `video`
- AND 没有本地真实 clip、有效缓存或成功 Provider 输出
- WHEN 以真实媒体验收模式运行
- THEN `--require-video-assets` 必须使流程失败
- AND manifest 不得把静态图 fallback 标记为真实视频

## Requirement: full Naval acceptance

全部 8 个动态场景的真实媒体验收完成时，系统 MUST 证明每个动态场景都有真实 motion clip，并完成最终成片验证。

### Scenario: eight-scene completion

- GIVEN scene_002 至 scene_009 均有经过验证的真实动态 clip
- WHEN 运行完整 Pipeline
- THEN manifest 对这 8 个场景均记录 `visual_source=video` 或等价真实视频证据
- AND scene_001/010 可继续使用 title card
- AND 最终视频通过 H.264、1080x1920、30fps、场景数、字幕和完整 FFmpeg decode QC

## Requirement: narration evidence

中文旁白 MUST 使用显式配置的 supplied WAV 或在线 TTS Provider；默认 no-audio 模式不得被描述为完成了有声成片。

### Scenario: Edge TTS

- GIVEN 显式选择 `edge-tts`
- WHEN Pipeline 完成
- THEN manifest 记录 provider 和 voice
- AND timing report 记录字幕对齐方法
- AND 源 narration 不被改写或截断

## Requirement: preserved source IDs and formal PNG evidence

A two-scene derived fixture MUST preserve every field of scene_002 and scene_003. The original storyboard MUST NOT change. The validator MUST accept contiguous positive IDs beginning at the first preserved source ID, while rejecting gaps, zero IDs, duplicates and reordering. Formal PNG reports MUST bind a fresh remote main Git tree and blob to each decoded local image; checkout newline differences in JSON MUST be disclosed with separate byte hashes.

### Scenario: offline formal-source preflight

- GIVEN the eight checked-in original PNGs and no FAL_KEY
- WHEN full and preserved-ID two-scene CLI preflights run under network/upload guards
- THEN measured connection/upload/generation attempts MUST be zero
- AND complete outputs MUST record scope, cached/billable scenes, configured per-clip estimate, total and cap
- AND the CI MUST use the formal PNGs instead of synthetic replacement source images.

## Requirement: durable request accounting and uncertain failures

Budget estimates MUST use the configured model rate and duration overhead. Nonfinite/nonpositive caps MUST fail closed. Each paid attempt MUST reserve its conservative estimated cost durably before external submission. A lock MUST prevent concurrent writers to the same request ledger. Failed or uncertain attempts MUST retain their reservation across restarts, and MUST NOT be automatically resubmitted. Changing the output/cache root is not a permitted retry mechanism. Service billing can differ from local estimates; actual cost MUST remain unknown until independently supported by billing evidence.

### Scenario: uncertain API error

- GIVEN a submitted request that errors or produces an invalid/missing result
- WHEN the run restarts with identical input and no valid cache
- THEN preflight/generation MUST require manual result/billing reconciliation
- AND no automatic paid retry may occur
- AND errors/ledger/manifest MUST NOT expose the credential.

## Requirement: validated cache and auditable visual origin

Video cache reuse MUST verify the input fingerprint, source image hash, Provider/model/origin, output SHA-256, positive finite duration, codec/dimensions/FPS and full FFmpeg decode. Headers or an MP4 suffix alone are insufficient. A missing optional request ID MUST NOT be invented. A successful local audit MUST NOT be presented as external service or billing verification.

### Scenario: corrupt or incomplete cache

- GIVEN matching input metadata but an undecodable clip or missing provenance
- WHEN preflight checks the cache
- THEN it MUST NOT count a cache hit
- AND any existing request reservation MUST prevent an implicit repeat charge.

### Scenario: renderer provenance

- GIVEN a validated Provider output or verified cached clip
- WHEN Renderer consumes it
- THEN manifest MUST bind source image/input fingerprint/clip hash to the actual video_asset_path and encoded scene hash
- AND distinguish generated, cached, supplied video, title_card, static image, fallback, provider_failed, invalid output and not_generated
- AND final QC MUST fully decode the output.

## Requirement: honest validation levels

CODE/CI, SOURCE/PREFLIGHT, TWO-SCENE REAL MOTION and FULL EIGHT-SCENE REAL MOTION MUST be reported independently. Mock service tests, local synthetic clips and supplied test tones MUST be labeled test evidence only. No real-service or narrated end-to-end PASS may be inferred from these tests.
