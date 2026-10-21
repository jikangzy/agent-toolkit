# 真实媒体端到端验收

## 背景

Book Video Renderer 已具备稳定的离线渲染、字幕、缓存、QC、可选 Edge TTS，以及可选 fal.ai 图生视频 Provider。Naval 样例在最新 main 中将 8/10 个非标题场景声明为 `broll` 或 `video`，但仓库只提交了 storyboard，没有提交对应源图或真实视频资产，因此不能仅凭场景类型宣称已经生成真实动态视频。

当前 fal Provider 需要显式预算上限，并会在真正生成前执行输入和预算预检；但 Provider 构造阶段即要求 `FAL_KEY`，不利于在完全无凭证、无网络、零付费条件下执行 dry-run 验证。

## 目标

建立一个可审计、可逐步放量的“真实媒体端到端验收”流程：

1. 在不触发任何付费请求的情况下验证 storyboard、动态场景集合、源图完整性、缓存命中情况和预计费用。
2. 首先只允许选择少量动态场景进行真实视频验证，确认输出确实为可探测的视频流并进入最终合成。
3. 小样验证通过后，再扩展到 Naval 全部 8 个 `broll`/`video` 场景。
4. 中文旁白优先复用已经验证过的 Edge TTS 或本地 supplied WAV 路径；任何在线 TTS 都必须保持显式 opt-in。
5. 最终成片必须通过现有 FFmpeg/QC，且 manifest 必须能够区分真实视频、缓存视频和静态 fallback。

## 非目标

- 本 Change 不自动发起高额付费请求。
- 本 Change 不把 `broll`/`video` 类型本身视为“已生成真实视频”的证据。
- 本 Change 不引入新的背景音乐生成服务。
- 本 Change 不修改 Naval 原始 narration、onscreen_text、scene 顺序或源 storyboard。

## 当前基线（2026-10-21）

- main: `7a2573421bc41a1387bf0d8d972b5d28ed398d95`
- Naval: 10 scenes，其中 scene_002–scene_009 共 8 个动态场景；scene_001/010 为 title_card。
- 仓库中的 Naval 示例目录当前只有 `storyboard.json`，没有提交真实图片或视频资产。
- 最新 main 的 Book Video Renderer CI 已通过；常规 CI 不运行在线 Edge TTS sample，也不应运行付费 fal 生成。
