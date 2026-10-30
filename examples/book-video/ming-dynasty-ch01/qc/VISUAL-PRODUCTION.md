# 静音视觉预览 QC｜2026-10-30—31

当前交付范围：8 场景视觉预览；82 秒，1080×1920，30fps。正式旁白、音乐、最终音画同步均未验收。

## 隔离

原仓库实际分支为 feat/ming-dynasty-opening，而不是用户假定的 work。创建前 HEAD 与 fetch 后 origin/feat/ming-dynasty-opening 均为 ae152d1af80d66a22e95751bf57ee757dc3687ef。新 worktree D:/AI-Tools/agent-toolkit-ming-video，分支 feat/ming-visual-production，初始干净。原仓库未跟踪 qwen3_tts_probe.py 保留；本任务没有写入原仓库或 Naval 内容，也没有切换原分支。

## 素材与文字

10 PNG SHA-256、尺寸和完整解码通过；8 场景图 1672×941，正面参考 540×1024，设定板 1536×1024。映射及人物限制见 visual/README.md。保留画面艺术重建标记。所有字幕使用现有 narration.json 原文，未新增史实。场景图以 object-fit:cover 或同比例 background-size:cover 重构，未拉伸。

## 检查记录

- HyperFrames lint/validate/inspect：以最终本地 JSON 及下方实测结果为准。
- GSAP 与字幕浏览器审计：129 个时间轴子项，18 条字幕全部检查，无越出安全区；所有 img 解码成功，本机 Song/Kai/Sans 字体可用。字幕左右 >=110px，底边 >=300px；当前字幕容器底边为1600px。
- 9 个 HyperFrames 截图已逐场抓取，含 S04 两个画面；最终编码帧另由 FFmpeg 抽取。
- 最终视频 codec、尺寸、帧数、全片解码、黑场和音轨检查由 scripts/visual-qc.py 输出 render-qc.json，完成后补记。

## TTS 状态

本机发现 D:/AI-Tools/qwen3-tts-ming-test-20261030 正在准备 Qwen3 测试。检查时 model.safetensors.part 尚未完整，无 WAV 或 audio-validation.json。进程枚举受限，不能据此判断任务是否运行或结束。旧 TECHNICAL-PROOF.md 记载 Linux Kokoro zf_001 的三段技术音频，发音仍待人工审核，当前 Windows 无可接入的已验收 Kokoro 旁白。本任务没有安装/运行/改动 TTS，没有调用付费 API。

## 未完成

第二阶段待 TTS 输出与发音/语速人工听审，再按真实 WAV 时长重排场景、同步字幕、接入已授权音乐并混音。人物、服饰、建筑的最终历史/美术审核仍需人工；当前技术 QC 通过不代表历史复原或发布审核通过。

## 经验检索记录

Experience Retrieval: Trigger=SHOULD_SEARCH；Query=Windows/Edge 在并行渲染复检期间启动超时；Result=NO_MATCH；Selected Experience=NONE；Full Reads=0；Candidate Reads=0；Reuse Applied=NO。仅检查政策与 Verified 索引，无匹配卡片，未读取或修改候选。超时发生时渲染正常采集，尚未证明唯一根因；将渲染后串行重跑。Knowledge Placement: SKIP_EXTRACT（无已确认可复用根因），WRITE_STATUS=NOT_APPLICABLE。

## 修订与复检

首轮完整渲染成功，82秒/2460帧，31.1MiB。视觉复核发现游方地图的点沿直线移动而非曲线，已改为 SVG 路径弧长 120 段确定性采样；保留第一版于本地 ming-opening-first-pass.mp4，不作为本次交付。修正后重新完整渲染。

串行复检：lint 0错误/0警告；validate 浏览器错误0、警告0、contrastFailures=0；inspect 在4/15/27/38/40/49/60/69/79秒检测，0错误/0警告/0信息。此前一次浏览器启动超时已经串行复跑通过，未证明唯一根因。

原仓库后续出现 requirements-qwen3-tts-cpu.txt，与既有 qwen3_tts_probe.py 均为并行任务未跟踪文件；本任务未写入或提交。原分支与已跟踪内容不变。2026-10-31再次检查外部 TTS：model-download.json已记录约2.50GB模型文件完成，install-uv.log仍在依赖准备，未发现当前可验收旁白或根目录audio-validation.json。模型下载完成不等于发音或音频验收通过。

## 最终编码验收｜2026-10-31

结论：PASS（仅限第一阶段静音视觉版）。修正版完整渲染约4分43秒。H.264，1080×1920，30/1fps，82.000000秒，2460帧，32601655字节。音轨0，符合静音预览定义。

- ffprobe 参数检查 PASS；FFmpeg 全片 decode PASS，stderr无解码错误。
- blackdetect：d=0.1、pix_th=0.08、pic_th=0.98，无黑场区间。
- 从最终 MP4 在4/15/27/38/49/60/69/79秒抽帧并查看联系表：无缺图、乱码、明显字幕覆盖或形变；S04第二画面另有40秒HyperFrames截图。此为抽样视觉审阅，不是逐帧人工观看。
- 浏览器复查：129个时间轴子项、18条字幕、0安全区失败；地图37个时点最大偏差0.1002 SVG像素；所有图片解码和三种字体检查通过。
- 动画时间区间审计无超过1秒的空档；全片采用前景/主画面/背景光雾的分层光学视差，不宣称人物已经做了真实三维建模。
- 视频SHA-256：`bd631f7fe1ab3a7abb6319e344b35b6d5509571bb912d5fec94d7a921954b105`。

本地成品：`.local/visual/ming-opening-silent-preview.mp4`；约31.1MiB，不提交。联系表：`qc/visual-contact-sheet.jpg`。机器可读结果及源码SHA：`qc/VISUAL-CHECKS.json`。完整日志与原始帧留在忽略目录 `.local/visual/`。

发布限制：仍是静音视觉预览；语音发音、语速、最终音画同步、音乐授权、混音与有声成片QC未完成。未调用付费API，未合并main，未改已有PR。
