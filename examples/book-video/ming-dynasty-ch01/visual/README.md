# 八场景静音视觉预览

状态：第一阶段视觉审阅版；82 秒为 provisional duration。没有旁白或背景音乐，不是最终成片。

入口：项目 index.html。film.css 定义国风排版、画窗、光雾与字幕样式；film.js 定义主时间轴；map.js 定义路线意象动画；audio-provider.js 保留未来经人工发音审核 WAV 的输入合约。Audio Provider 只返回受检 manifest，不合成、不加载临时音频；接入真实媒体和词级同步仍属于第二阶段。

## 素材与镜头映射

| 场景 | 素材 | 运镜与表达 |
|---|---|---|
| S01 0–9s | MD08 | 古村落缓推、章名、朱印 |
| S02 9–21s | MD02 | 农家横移、侧光、前景遮挡 |
| S03 21–33s | MD03 | 哀悼环境克制微移、1344 年标记 |
| S04 33–43s | MD01 + MD04 | 山门拉远，38s 溶解到寺院生活，晨雾 |
| S05 43–56s | MD06 | 行旅横移、山形与动态路线意象 |
| S06 56–64s | MD05 | 归寺纵向重构、冷暖光影 |
| S07 64–75s | MD07 城镇右侧局部 | 缓慢俯移、1328/1344/1352 时间轴 |
| S08 75–82s | MD07 人物与远景 | 背影推进、悬念标题与印章 |

S07 对 MD07 的扩展用途记录于此，不修改来源 manifest。画面是艺术重建，不是考证后的濠州城复原。MD03 不指认具体葬地、死亡顺序或地主故事。地图无真实边界或确切行程。全部旁白字幕逐句来自 script/narration.json，时序只按镜头预算分配。

## 人物一致性

唯一正面参照：MD11_ZHU_YUANZHANG_CHARACTER_FRONT.png；设定板辅助。青年形象采用灰褐粗布交领、绳带、布包、束发，优先使用已有背影，不生成新的不一致面孔。MD02 年幼人物对应家庭早年。参考图与场景为艺术化历史重建，不能证明真实历史容貌；不宣称每张素材的人脸经过身份验证。

## 重现

npm ci --ignore-scripts；设置 HYPERFRAMES_BROWSER_PATH 指向本机 Chrome/Edge；设置 HYPERFRAMES_FFMPEG_PATH 与 HYPERFRAMES_FFPROBE_PATH 指向可运行二进制。无需 TTS 环境。

```powershell
.\node_modules\.bin\hyperframes.cmd lint --json
.\node_modules\.bin\hyperframes.cmd validate --json
.\node_modules\.bin\hyperframes.cmd inspect --at 4,15,27,38,49,60,69,79 --json
node scripts/visual-audit.mjs
.\node_modules\.bin\hyperframes.cmd render --output .local/visual/ming-opening-silent-preview.mp4 --fps 30 --quality standard --workers 2
python scripts/visual-qc.py
```

本次工具：HyperFrames 0.8.221、GSAP 3.14.2、Node 22.22.3、Edge、FFmpeg 6.1.1（已有本机缓存）、ffprobe n7.1（已有本机 Remotion 工具）。机器特定可执行路径见本地 render.log/报告，不写入影片内容。portable 工具下载目录 .local/tooling 不提交；模型、缓存、MP4、WAV 不提交。

原 10 秒技术验证源码保留于 visual/technical-proof.html，相关旧 QC 描述的是历史技术验证，不是本次 82 秒静音视觉版。其资源路径已调整为从 visual/ 访问项目依赖；历史 TTS 文件不在当前 worktree，不能据此宣称当前可播放。
