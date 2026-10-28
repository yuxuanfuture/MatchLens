# Windows 本地视频启动

本机工作目录：`D:\Microsoft +\Microsoft + Premier League\matchlens-live`。
Windows 使用独立的 Python 3.13 环境和 CPU 推理，适用于当前 Intel Arc 电脑。

## 动画球场与三种角色

项目的动画演示主入口是 <http://127.0.0.1:43128/>。它由比赛事件流驱动，
在右上角 Your view → I’m here as a… 中切换 Fan（球迷）、Coach（教练）和
Commentator（评论员）。Fan / Analyst 是信息详略切换，三种角色各自保存布局。

在项目目录启动动画主界面：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-matchlens-windows.ps1
```

该入口复用已适配的 Windows 服务，打开动画球场。下方视频上传入口作为单独的功能保留。
动画展示、事件分析和角色切换可以离线运行；页面标为离线事实模式时，解说由规则生成，
不能把它当成已经运行了语言模型。已有模型 API 授权状态继续由独立配置控制。

| 用途 | Windows 新增路径 | 原 macOS 路径（保留） |
| --- | --- | --- |
| 视频 Python | `.venv-vision-windows\Scripts\python.exe` | `.venv-vision/bin/python` |
| 环境安装 | `scripts\setup_vision_windows.py` | `scripts/setup_vision.py` |
| 依赖版本 | `requirements-vision-windows.lock` | `requirements-vision.lock` |
| 启动入口 | `start-video-windows.ps1` | `python3 -m backend.server --port 43128` |

三份已校验的足球检测权重继续从 `models/` 读取。
Windows 安装脚本遇到已有权重校验不符会退出并保留文件，不覆盖原权重。

## 打开页面

在项目目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-video-windows.ps1
```

脚本首次缺少 Windows 环境时调用专用安装器；服务在后台运行，随后打开
<http://127.0.0.1:43128/sources.html>。服务日志位于
`run-output/windows-server.log` 和 `run-output/windows-server-error.log`。
启动时会打印服务进程编号，可用 `Stop-Process -Id <实际进程编号>` 停止。

仅安装或修复 Windows 依赖：

```powershell
python scripts\setup_vision_windows.py
```

也可在终端前台启动，按 Ctrl+C 停止：

```powershell
& '.\.venv-vision-windows\Scripts\python.exe' -X utf8 -m backend.server --port 43128
```

## 识别视频

在“02 / 本地视频分析”选择本机视频，保留自动球场标定，点击“开始本地分析”。
配置中的 `device: "auto"` 在 Windows 解析为 `cpu`，在 macOS 继续解析为 `mps`；
也支持显式指定原来的设备值。建议首次将 `max_seconds` 改为 5、`sample_fps` 改为 5，
确认素材适合后再增加分析时长。CPU 分析需要等待，页面会显示帧数与进度。

完成后可以查看检测框、导出事件，或点击“在 Pocket Stadium 中分析”。
视频分析使用本机预训练模型，不需要语言模型 API 密钥。

## 验证

```powershell
& '.\.venv-vision-windows\Scripts\python.exe' -X utf8 scripts\offline_acceptance.py
```

这会运行已有的事件数据校验、Python 和 Node 回归测试。实际视频推理结果另存，
不会把旧电脑的历史测试记录当作本机运行结果。
