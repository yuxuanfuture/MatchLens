# 本地视频传球提取回归记录

## 原始复现与原因

输入为 [Roboflow Sports 官方足球示例](https://github.com/roboflow/sports/blob/main/examples/soccer/setup.sh) 的 `0bfacc_0.mp4` 前 10 秒。本地文件 `run-output/broadcast-ground.mp4` 不随作品发布。最初自动标定运行只得到 1 条压迫，没有传球。

单帧对照确认：1280 输入可能生成多个球场候选，首候选置信度 0.979，却只有 3 个可用关键点；后一个候选反而能完成标定。只取首候选会错过有效几何。标定在相邻帧跳变还会制造不合理球速，使传球链被重置。640 原生尺度得到较完整的关键点检测。

## 修复与回归

- 检验全部候选，依据不共线内点数量及标定残差选择；不足 4 个点不输出标定。
- 关键点使用 640 尺度；相机运动跟踪后的几何作为连续性参考，拒绝跳变的重新标定。
- 足球观测失效后退出局部搜索，重新全画面寻找，避免锁在误检位置。
- 已观察到至少 3 个飞行样本的传球允许最多 240 ms 遮挡；不填造缺失位置，也不为这次传球提供飞行均速。
- 未确认方向不推断射门；射门不自动当成进球；未确认比分不显示成真实 0:0。

同一片段诊断复跑得到 126 个采样帧、3 次传球和 1 次压迫，耗时 87.13 秒。结果在 `run-output/vision-ground-fixed/`；最终代码复跑用时 102.60 秒，仍得到相同事件，结果在 `run-output/vision-acceptance/`。传球距离估计 12.64、15.88、9.75 米，后两次因短遮挡保留速度空值。

`tests/fixtures/observed_ground_tracks.json` 保存实际预训练模型产生的匿名坐标观测；测试不手填事件。`tests/test_vision.py` 覆盖多候选选择、标定连续性、共线点拒绝、短遮挡、断链、未知方向、禁止网络和实际轨迹回归。

```bash
.venv-vision/bin/python -m unittest tests.test_vision -v
.venv-vision/bin/python -m backend.vision run-output/broadcast-ground.mp4 \
  --output run-output/vision-acceptance --config run-output/vision-ground-config.json
```

这证明固定样例上的自动传球路径可用；不是人工标注数据集上的准确率、召回率或实时性能结论。原始录像只用于本地诊断，没有进入交付素材。
