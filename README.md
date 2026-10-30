# Local Bird Video Analyzer

本项目是一个本机离线鸟类视频检测原型：视频保存在本机，后台任务使用视频呈现时间戳生成鸟类框和连续事件，前端播放时叠加框并在时间轴高亮事件。

## 快速启动

在仓库根目录打开 PowerShell：

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

浏览器访问 `http://127.0.0.1:5173`。默认后端使用本地 YOLO11n；若没有模型权重，任务会进入失败状态并显示安装提示。显式下载可选模型和依赖：

```powershell
.\scripts\setup.ps1 -WithDetector
.\scripts\start.ps1
```

运行真实视频浏览器验收前先准备本机验证视频：

```powershell
.\scripts\fetch-sample.ps1
.\scripts\start.ps1
$env:BIRD_TEST_VIDEO = (Resolve-Path .\bird-data\samples\cathedral-hawk-fledges.mp4).Path
$run = Get-Content -Raw .\.local-run\services.json | ConvertFrom-Json
$env:VITE_API_TARGET = "http://127.0.0.1:$($run.api_port)"
cd frontend
npm.cmd run test:browser:real
```

该公开视频来自 Flickr，经 Internet Archive 提供 MP4 衍生文件；原作者 Jeremy Seto，CC BY-NC-SA 2.0。脚本只下载到被 Git 忽略的本机目录，不会随项目分发。

没有模型时可用 synthetic UI mock 检查上传、播放、画框和时间轴交互。mock 结果是合成数据，不代表模型推理：

```powershell
.\scripts\start.ps1 -Mock
```

若要通过真实 API 检查空结果链路，可将 `BIRD_DETECTOR=mock` 后启动；后端 mock detector 默认不伪造检测框。

`start.ps1 -Mock` 启用上面的 synthetic UI mock：

```powershell
cd frontend
npm.cmd run dev:mock -- --host 127.0.0.1 --port 5173 --strictPort
```

后端默认地址是 `http://127.0.0.1:8000`，前端通过 Vite 代理访问 `/api`。若端口被占用，启动脚本会选择后续可用端口并写入独立的 `bird-data-<port>/`。视频、模型、缓存和构建产物均已加入 Git 忽略规则。

## 检查

```powershell
backend/.venv/Scripts/python.exe -m pytest
cd frontend
npm.cmd run build
npm.cmd run lint
npm.cmd test
npm.cmd run test:browser
```

契约源文件是 [CONTRACTS.md](CONTRACTS.md) 和 [docs/openapi.yaml](docs/openapi.yaml)。修改 OpenAPI 后在 `frontend/` 运行 `npm.cmd run api:types`。

## 模型与限制

YOLO11n 使用 COCO 的 bird 类别，权重需单独下载并按 Ultralytics 的 AGPL-3.0 或 Enterprise 条件核查；项目不会自动下载权重。检测效果、漏检率和速度取决于素材、采样间隔、CPU/GPU 和鸟在画面中的像素大小。当前没有提交公开样例视频或人工标注集，不能据此宣称准确率。

支持 MP4、MOV、M4V、MKV 和 WebM；实际可播放性仍取决于 PyAV 与浏览器对编码器的支持。时间戳使用解码 PTS，事件为半开区间 `[start_seconds, end_seconds)`，bbox 是旋转后显示画面的归一化 `[x1, y1, x2, y2]`。
