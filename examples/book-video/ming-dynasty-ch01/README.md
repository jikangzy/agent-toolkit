# 明朝那些事儿：开篇篇章（策划工作稿）

状态：阶段 A 部分完成；样片、语音、音乐、HyperFrames 项目与 QC 均未完成。已参考用户提供的第三方合集 PDF 开篇；该文件未明确出版版次及第一章边界，发行授权未核实。历史事实仍以独立资料交叉核验。旁白和分镜均未锁定。不要将规划时间当作实测字幕。

阅读顺序：research → script/narration.md → storyboard/STORYBOARD.md → DESIGN.md → qc/ENGINEERING-AND-AUDIO.md。目标 1080×1920、30fps、H.264，先交付 60–90 秒样片并验收，再扩展。项目与 Naval 隔离；大素材和 MP4 不提交 Git。

完成路径：确认可运行的 HyperFrames CLI、GSAP 和中文 TTS → 合法获取/生成历史重建素材和原创或授权音乐 → 对每段旁白生成语音并测量时长/词边界 → 生成 JSON 与 SRT → 按实测时间制作 HyperFrames 合成 → lint/validate/inspect → 渲染 → 全量解码、音量/字幕/黑场与关键帧人工检查。禁止将占位图、静音或模拟音作为最终交付。

本阶段新增 [史实核查](research/FACT-CHECK.md)、[TTS评估与试听方案](audio/TTS-EVALUATION.md)、[工程报告](qc/HYPERFRAMES-ENGINEERING.md) 和 [样片计划](storyboard/NEXT-STAGE.md)。安装 Node 依赖使用 `npm ci`；本地语音模型不包含在 lock 中。
