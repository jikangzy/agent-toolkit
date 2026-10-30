# 中文 TTS 技术评估与三段测试方案

状态：尚无试听音频，质量、发音、停顿、语速均未实测。2026-10-30 检查。

| 方案 | 自然度/情绪/长文本和停顿 | 部署与费用 | 决策 |
|---|---|---|---|
| HyperFrames CLI + Kokoro ONNX | 支持中文音色及速率；中文实际自然度、情绪、标点必须听测；按句分段减少长文本风险。无明确情绪参数 | 本地 CPU；CLI 显示 zf_xiaobei；Python、kokoro-onnx、soundfile、音素化依赖及模型缺失。参考资料估计模型约311MB、音色约27MB，依赖另计，实际尺寸待校；无需 API 密钥，API $0 | 第一候选，先测试而不把它当专业音质结论 |
| 仓库 Edge TTS | 有中文神经音色，速率可调；标点与表现需实测；仓库支持逐场景、缓存和词边界 | 第三方在线服务，发送文本；非正式服务，免费/可用性/条款无法保证，无需通常意义的 API 密钥 | 备用，不假定已有免费额度 |
| Azure AI Speech 标准神经音色 | 提供多种音色和 SSML 控制；实际自然度和情绪须试听；应按服务限额切段 | 官方列免费层标准神经声音每月50万字符，资格、区域与超额价格需核实；需账户及密钥 | 若本地效果不足再申请具体授权；当前不调用 |
| HeyGen Voice API | 有 TTS 及多种声音；是否适合纪录片须试听，控制能力以接口文档为准 | 账户、密钥与额度/定价待查；可能收费 | 未经预算授权不调用 |

参考：[HyperFrames 官方 TTS](https://github.com/heygen-com/hyperframes/blob/main/skills/media-use/audio/references/tts.md)、[Kokoro 音色与局限](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)、[Azure 定价](https://azure.microsoft.com/en-us/pricing/details/speech/)、[HeyGen Voice](https://www.heygen.com/models/heygen-voice-1)。模型与具体音色的授权及来源须在发布前逐项核验；不得克隆他人声音。音色列表或声称支持不证明实际中文可用。

## 已执行的技术探针
临时安装 HyperFrames 0.8.221，`tts --list` 列出 zf_xiaobei；调用一小段中文命令退出码1：找不到带 kokoro-onnx 和 soundfile 的 Python 环境，未生成 WAV、未下载语音模型。主机 python3 存在，CLI 错误措辞“Python 3 is required”不应误解为系统完全没有 Python。CLI 代码默认请求 Kokoro v1.0 模型和音色文件；列出中文并不证明这组权重、音色、中文音素器的组合兼容。先验证版本和许可再下载；`HYPERFRAMES_PYTHON` 可指定隔离环境，但 CLI 缓存路径还需保证可写。当前未下载大型模型；样本为可执行方案而非已完成试听。

## 试听输入与评判

- T01 平静：`一三二八年，朱元璋出生在濠州钟离，也就是今天安徽凤阳一带。`
- T02 情绪：`一三四四年，灾荒和疾病袭来。他的父母和多位亲人相继去世。一个家，就这样散了。`
- T03 专名：`一三五二年，朱元璋在濠州加入了郭子兴的队伍。`

配置同一公开音色 zf_xiaobei、速度1.0、zh，分3次本地调用，API 0次、预计 API 费用0、无需密钥；不启用任何声音克隆。安装前确认约338MB模型及其他依赖的下载量与使用许可，核实缓存可写、离线重跑可用。输出置于被 Git 忽略的 `audio/*.wav`。用 ffprobe 核验采样率、时长、声道，FFmpeg 全量解码，测响度与峰值；分别人工听审专名、逐字年份、停顿、语速、情绪及断句，每项记录通过/失败与时间点。合格后再处理整段旁白和字幕对齐；不得用文字时间估算代替语音对齐。
