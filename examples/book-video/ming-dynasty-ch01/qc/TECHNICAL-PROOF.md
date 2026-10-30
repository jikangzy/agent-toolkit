# 技术验证报告｜2026-10-30

## 环境与依赖
基准 `2c4c2b532e3e7d625bf8410d496c1f97cf58e3ee`；Linux x86_64，Node 24.19.0，Python 3.12.14，FFmpeg 7.1.5，Chromium 系统版，内存上限 8 GiB。项目内 `npm ci` 完成；HyperFrames 0.8.221 保持不变，新增锁定 GSAP 3.14.2。修复缺少 `npm run tts` 脚本；`npm run tts -- --list` 成功。`npm run doctor` 能运行，但 whisper、MusicGen、Docker 缺失，受限沙箱中 Python 子进程检查也报 EPERM；不能声称 doctor 所有项目通过。

## 语音
`.venv` 是隔离 Python 环境，使用 `kokoro-onnx==0.6.1`、`soundfile==0.14.0` 和 espeakng-loader，完整版本见 requirements-tts-lock.txt；未修改系统 Python。CLI 0.8.221 的默认模型是英文 v1.0；中文 v1.1 包不含 `zf_xiaobei`，实际用中文模型的 `zf_001`，`lang=cmn`、speed=1.0，通过 Python API 合成，并非声称通过 CLI 的默认模型完成。三个 WAV 均为 PCM、24kHz、单声道，FFmpeg 全量解码成功：T01 8.501秒、T02 9.429秒、T03 5.383秒。峰值分别 0.4351、0.4630、0.3249，RMS 分别 0.0632、0.0646、0.0614；非全静音且未达到数字满幅。不能由波形推断是否念对：人名、地名、年代、自然度、停顿、语速、语义内容均**待人工试听**，此项未验收。

上游中文模型卡标注 Apache-2.0；本次未克隆真人声音，但具体音色的训练数据和正式发布权利仍应核实。静态模型下载无付费 API：上游 [v1.1 文件](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1) 中文模型 326 MB、音色 53 MB（发布说明十进制数）；实际目录合计 362 MiB。模型 SHA-256 `859f9ded9f53be16c24857cdab3254a45da53c3afd5ba6ef134c7de3f822e326`，音色 `14cb6186c99e4f6016871405f62046c5df863ae27465cbdc4ee08be7dd703acd`。[模型许可](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh)。`.venv` 约184 MiB，node_modules 约145 MiB；本地缓存被 Git 忽略。

## 复现
`npm ci`；`python3 -m venv .venv`；`.venv/bin/pip install -r requirements-tts-lock.txt`；将上述发布页的 `kokoro-v1.1-zh.onnx` 和 `voices-v1.1-zh.bin` 下载到 `.local/models/` 并核对 SHA-256；运行 `.venv/bin/python scripts/make_audio.py`。后者生成三段试听和程序合成音垫。调用 `HYPERFRAMES_BROWSER_PATH=/usr/bin/chromium ./node_modules/.bin/hyperframes render --output .local/tts/proof.mp4 --fps 30 --quality draft --workers 2`。路径可按本机 Chromium 调整；输出文件、模型及虚拟环境不提交 Git。

## 费用
Kokoro 本地推理及公开模型文件下载 API 费用 0；音频生成 API、付费视频生成、fal.ai、HeyGen 计费请求均为 0。网络流量、存储和本机算力有资源成本，未计价；未购买素材。
