# 动画人物展示的实际制作流程核查

核查日期：2026-10-27。按用户澄清，本报告只回答动画人物、球场画面、动作表现和角色界面如何制作。依据为展示源码、实际 PNG 素材及设计记录；原始比赛数据的测试结果不作为本报告的动画结论依据。

## 1. 核查结论

当前展示是“已有图片素材 + 二维 Canvas 绘制 + 位置更新 + 代码效果 + HTML/CSS 界面”。画面具有立体风格，但运行时并没有加载可操纵的三维人物模型，也没有为人物动画训练模型。

关键证据：[Canvas 渲染器](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:16>)、[动画循环](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket.js:144>)。

## 2. 人物和球场素材是什么

| 素材 | 当前实际用途 |
| --- | --- |
| stadium-roomy.png | 当前球场、看台、树木和天空等背景画面，1672×941 |
| player-blue.png | 蓝队球员底图，1254×1254 的单张透明 PNG |
| player-coral.png | 红队球员底图，1254×1254 的单张透明 PNG |
| commentator.png | 解说卡片中的人物插画，由 HTML 的 img 显示 |
| stadium.png | 保留的另一张球场图，当前 StadiumRenderer.load() 使用的是 stadium-roomy.png |

场上的不同球员复用两种队服图片。球衣号码、名字、选中光圈和阴影由代码另外绘制，并非分别制作了 22 个独立角色模型。

证据：[图片加载](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:22>)、[人物及号码绘制](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:84>)、[解说员插画](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/index.html:8>)。

## 3. 从素材到动画的具体过程

1. 准备并加载已有球场背景和透明人物 PNG。
2. 在背景图上确定草坪四个角，将场地坐标投影成屏幕像素位置，获得斜视球场的立体感。
3. 根据每名球员当前坐标，将蓝队或红队图片分别画到对应位置；按屏幕纵坐标排序，处理人物前后覆盖关系。
4. 位置变化时重新画图，让整张人物图片在球场上移动。另用正弦函数添加轻微上下起伏，用跳动、碎纸等代码效果表现进球庆祝。
5. 足球由 Canvas 的圆形、描边和阴影绘制，传球路线及压迫色块由线条和多边形绘制。
6. 用 requestAnimationFrame 持续重绘，用 HTML/CSS 放置比分、解说、战术笔记、按钮和角色设置。

证据：[场地投影](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:4>)、[背景与叠加层](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:43>)、[人物排序](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:75>)、[上下起伏](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:88>)、[足球绘制](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:77>)。

## 4. “人物在跑”实际做到了什么

| 所见效果 | 源码实际实现 |
| --- | --- |
| 人物跑到另一个位置 | 更新同一张 PNG 的绘制位置 |
| 跑步起伏 | Math.sin 计算整张图片的轻微上下偏移 |
| 不同球员 | 复用队服底图，分别叠加号码、名字和位置 |
| 足球移动或射门 | 更新球的位置及相关路线，球员身体没有单独的踢球动作素材切换 |
| 进球庆祝 | 图片跳动与代码绘制的彩色碎纸 |
| 看起来立体 | 斜视背景、坐标投影、绘制大小、阴影和前后排序 |

这不是人物骨骼驱动的走路，也没有逐帧走路、转身、铲球、踢球等姿态切换。当前浏览器主链使用最新收到的球员坐标，没有在前后两组位置之间实现连续人物位置插值。持续重绘与连续平滑位移不是同一件事。

证据：[人物函数](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:84>)、[庆祝效果](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:103>)、[最新坐标到画面](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/live-client.js:1>)。

## 5. Fan、Coach、Commentator 与人物的关系

三个选项是观看者身份，控制信息模块的布局和侧重点，并不对应三种场上人物或三套人物动画模型。

- Fan：默认进入简洁模式，显示标题和解说卡。
- Coach：默认进入 Analyst 模式，并显示战术笔记。
- Commentator：默认进入 Analyst 模式，隐藏大标题、加宽解说卡。
- 布局按“角色:模式”保存，支持调整模块显隐、大小和位置。
- 顶部 Fan / Analyst 另外控制展示详略；Analyst 还增加网格、球员名字等视觉信息。

解说卡中的 commentator.png 是一个静态人物插画，未见口型同步、肢体表演或语音驱动动画。现有展示相关素材也没有单独的 Coach 或 Fan 人物底图。

证据：[角色布局预设](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket.js:25>)、[角色切换](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket.js:131>)、[分析模式网格](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js:60>)。

## 6. 原始图片当初如何制作，能确认到哪一步

design-qa.md 将这些图片描述为 generated raster assets，并保留了视觉目标和页面截图。但现有展示文件中没有能重建这些人物/球场图片的完整生成提示词、分层工程或三维源文件。因此，可以确定“现有 PNG 怎样被组合成动画”，无法仅从当前文件夹确认图片最初具体使用哪个生成工具及完整制作步骤。

制作当前这种展示不需要先训练人物模型：可由绘图、建模渲染或现成图片生成工具准备素材，再由前端代码组合和驱动。这里描述的是可行制作方式；仓库能直接证明的是已有 PNG 和绘制实现。

证据：[设计记录](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/design-qa.md>)、[当前渲染源码](<D:/Microsoft +/Microsoft + Premier League/matchlens-live/dist/pocket-renderer.js>)。
