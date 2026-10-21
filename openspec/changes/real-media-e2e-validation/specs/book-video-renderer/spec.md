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
