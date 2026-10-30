# 明朝那些事儿·开篇篇章视觉素材包

## 内容
- `scenes/`：8 张原创生成的历史场景图
- `characters/`：朱元璋青年时期正面人物参考图及人物设定参考板
- `ASSET-MANIFEST.json`：素材索引、尺寸、SHA-256、用途和审核状态
- `docs/`：预览联系表

## 使用建议
1. 先阅读 `ASSET-MANIFEST.json`，按 `scene_hint` 对照 storyboard。
2. 原始图片为横向电影构图；在 HyperFrames 中进行 9:16 裁切时，保留主体和镜头运动余量。
3. 人物设定图用于保持角色外观一致，不应当作朱元璋真实肖像。
4. 所有图片均为艺术化 AI 生成素材，不是历史证据。正式成片前需审核服饰、建筑、道具和历史情节是否匹配。
5. `review_status` 初始为 `pending_user_review`，审核通过后再更新。

## 建议放入仓库的位置
`examples/book-video/ming-dynasty-ch01/assets/generated/`

## Git 建议
素材体积较大。用户已要求纳入 Git；提交前请检查仓库体积策略及是否已有 Git LFS 约定。不要覆盖现有文件。
