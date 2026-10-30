# HyperFrames 工程化检查

- 本项目 `package.json` 精确固定 `hyperframes` 0.8.221，`package-lock.json` 固定依赖解析；Node 24.19.0、FFmpeg 7.1.5、系统 Chromium 可用。临时安装 `doctor` 和 `tts --list` 运行成功，但没有渲染验收。
- 独立干净目录从 package.json 与 lock 执行 `npm ci --ignore-scripts`，安装成功，CLI 输出 0.8.221。该检查用了已有 npm 缓存及可用 registry，并不证明断网安装；浏览器、Python、模型、字体和 FFmpeg 不由 npm lock 保证。正式渲染前需独立验证完整依赖及模型哈希。
- 正式安装在项目目录运行 `npm ci`，不能依赖 `/tmp/ming-hyperframes`。不将 node_modules、模型、音频、视频提交。检查第三方包许可及供应链，必要时配置代理。安装后运行 `npm run doctor`。
- 现有 agent-toolkit 是 Python/FFmpeg 渲染管线，并非 HyperFrames。可复用其提供的已生成 WAV 输入校验、字幕校验、缓存/manifest 与 QC 思路；这些模块依赖现有 storyboard 和 renderer 合约，不能声称可直接连接到 HyperFrames。`RecordedSpeech` 校验音频与时长，`subtitle.validate_subtitle_file` 校验 SRT；对 HyperFrames 渲染出的成片可用 FFmpeg/ffprobe 检查。
- 本阶段不改公共模块、不新建未验证的适配器。下一阶段如果需要统一 manifest/素材缓存，先用项目内薄适配层明确输入、时间基准、素材指纹、输出、失败语义与测试；避免将两个渲染引擎强行嵌套或重复实现。
- 本项目尚无 composition、真实素材或渲染成品。CLI 可用不代表字幕、GSAP、音频混合或视觉验收已通过。
