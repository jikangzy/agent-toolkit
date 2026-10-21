# Tasks

## Code and zero-cost preparation

- [x] Fresh fetch origin/main；从最新基准创建 feat/naval-real-media-e2e-validation，保留已有附件。
- [x] 阅读 Issue #23、旧分支独立文档差异、OpenSpec、Pipeline、Video/TTS、Renderer、Manifest、QC、测试与 CI。
- [x] 验证远端 main Git tree 的 8 张正式 PNG，与本地和 Git blob 内容对应；记录尺寸、颜色模式、SHA-256 和完整解码。
- [x] 原始 storyboard 保持不变：10 scenes、2 title cards、8 动态场景，记录本地 CRLF 与 Git LF 哈希。
- [x] 使用真实 8 张 PNG 执行 8 场景零网络/零付费 preflight（5 秒，USD 1.20 cap），保存完整输出和网络阻断计数。
- [x] 创建 scene_002/003 派生 fixture，逐字段保留源文案/提示/时长/ID，修复连续 ID 起点限制并添加测试。
- [x] 使用正式源图执行两场景零网络/零付费 preflight（5 秒，USD .40 cap）。
- [x] 添加持久化请求预算预留、失败/不确定请求禁止自动重试、并发锁、输入指纹、缓存损坏和非有限预算测试。
- [x] 视频和最终成片 QC 增加完整 FFmpeg 解码；Manifest 追踪 Provider、输入图 hash、输出 hash、缓存、失败和 title card。
- [x] supplied WAV 完整解码；保留 narration，修正 supplied-audio 来源标签；保留既有时长/字幕/Edge mock 测试。
- [x] 准备付费生成后的自动来源/QC 审计命令；mock fal + 本地合成视频集成验证（不是真实 fal 验收）。
- [x] 最新代码完整 compile/unit/FFmpeg 回归全部通过：82 tests，0 failures/errors/skips（见 test-results.json）。
- [ ] 本工作分支 PR CI 通过，并提供运行链接和证据 artifact。
- [ ] 提交并推送工作分支，创建目标 main 的 PR；最终报告与 Issue #23 同步。

## Real-service acceptance — NOT RUN / paid authorization required

- [ ] 获得本次 scene_002/003 真实消费授权及 FAL_KEY；fresh preflight 与账单风险复核。
- [ ] 两场景真实 fal clip 生成及逐个 ffprobe/full decode、输入/输出指纹、请求证据和成本记录。
- [ ] 两个真实 clip 进入 --require-video-assets Renderer，并通过最终视觉 QC。
- [ ] 接入经授权的真实 narration，完成两场景音视频/字幕验收；不得用 test tone 代替。
- [ ] 两场景通过后 fresh full preflight；独立取得剩余 6 场景消费授权。
- [ ] 8/8 正式动态场景均具有真实 fal 输出/有效缓存证据。
- [ ] 10 场景完整有声成片通过 H.264/1080x1920/30fps/AAC/字幕/场景数/full decode QC。
- [ ] 独立审核全部真实媒体证据后再进行 Change 收口；当前保持 OPEN / PARTIAL。
