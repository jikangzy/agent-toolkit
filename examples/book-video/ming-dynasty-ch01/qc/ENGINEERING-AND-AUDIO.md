# 工程、音频与费用检查（2026-10-30）

## 仓库
`work` 分支，初始 HEAD ad0a11c，初始工作区干净；单一 worktree。未切换分支、合并、删除或修改 Naval。没有发现 AGENTS.md。远程 origin 为 jikangzy/agent-toolkit；`gh pr list` 因代理连接被系统拒绝，无法确认当前开放 PR 或其他远程任务。历史报告记录 PR #24；不能将历史状态当成实时状态。

现有 `tools/book-video-renderer` 是 Python/FFmpeg 管线，有 Provider、场景缓存、manifest、字幕及 QC；不是 HyperFrames。Naval 双场景证据是离线 preflight：2 个场景、0 次生成，历史报告明确没有真实动态素材或配音，不是已完成的真实视频验证。仓库没有发现 HyperFrames/GSAP 文件。官方插件的技能说明可读取；Node v24 与 FFmpeg 存在，但本地未发现 HyperFrames 命令或 node_modules；`npx --no-install hyperframes --version` 未返回版本，不能声称 CLI 可用。没有安装或付费请求。

## 音频及费用预估（生成前）
| 候选 | API/方式 | 样片预计请求 | 费用 | 密钥 | 状态 |
|---|---|---:|---|---|---|
| HyperFrames Kokoro | 本地 `hyperframes tts`，中文 z 系列 | 本地6段，云API 0 | API $0；首次模型下载和计算资源 | 不需要 | CLI、模型及中文依赖尚不可用；专业质量待试听 |
| Edge TTS | 仓库可选 edge-tts adapter | 最多6段，缓存命中减少 | 非官方服务，实际计费/条款无法保证；不承诺免费 | 通常不需 | 包未安装，网络未验证；文字发送第三方 |
| HeyGen TTS | 语音接口/官方 helper | 最多6段 | 取决于账户与现行价格，未知 | 需要或账户认证 | 未检查授权与余额，不调用 |
| fal H3 Max Turbo | 仓库 image-to-video adapter | 假设6段×5秒 | 仓库旧配置估算 6×(5+0.7)×$0.025=$0.855；现价未核验，非报价 | 需要 | 未授权，不调用 |

参考 [HyperFrames 官方 TTS 文档](https://github.com/heygen-com/hyperframes/blob/main/skills/media-use/audio/references/tts.md)。任何付费服务先获得预算确认；不以现有额度推断授权。素材来源/许可未确定，音乐未生成。需要实际配音后测量每段时长，依据词边界或人工校对字幕；混音以实测响度、真峰值和听感报告为准。

## QC 状态
未渲染：解码、分辨率/编码、黑场/闪帧、画面连续性、字幕同步、音频响度、联系表均未执行，不能验收。历史准确性与重建画面需人工审查。API 实际调用和费用：0。

补充：HyperFrames 0.8.221 已安装在 `/tmp/ming-hyperframes`，`--version` 和 `doctor` 成功运行，系统 Chromium 与 FFmpeg 可用；未测试实际渲染。CLI `tts --list` 显示中文 zf_xiaobei；Kokoro、中文依赖、语音模型及 MusicGen 尚未安装，转录工具缺失。临时目录非持久依赖。运行环境显示 FAL_KEY 就绪，但不代表付费授权，未使用。
