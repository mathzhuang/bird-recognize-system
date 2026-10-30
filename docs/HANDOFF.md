# Local Bird Video Analyzer Handoff

本文档描述当前仓库可由代码和命令复现的运行、架构、契约、测试和风险状态。它不把单个样例上的模型输出当作通用准确率。

## 1. 当前状态

| 项目 | 状态 |
| --- | --- |
| 目标 | 本机离线上传视频，检测 COCO `bird`，显示检测框和连续出现片段 |
| 当前 HEAD | `bc15a9e`，`完善real workflow` |
| 后端 | FastAPI + Uvicorn，单个后台分析 worker |
| 前端 | React 19 + TypeScript + Vite |
| 解码 | PyAV，使用解码 PTS |
| 真实 detector | Ultralytics YOLO11n，本地 `backend/models/yolo11n.pt` |
| 默认分析参数 | 0.4 秒采样、置信度 0.25、输入尺寸 640、跟踪关闭 |
| 存储 | SQLite 任务元数据、JSONL 帧结果、每任务源视频 |
| 已验证 | API 工作流、SSE、Range、刷新重开、真实样例、空结果态、失败态、mock UI |
| 未完成评估 | 真实无鸟/多鸟准确率、召回率、误检率、事件边界误差、多浏览器兼容性 |

已验证的本机样例：`cathedral-hawk-fledges.mp4` 约 65.48 秒，曾产生 53 个检测框和 13 个事件；`purple-swamphen-bath.mp4` 约 11 秒，曾产生 16 个检测框和 1 个事件。样例位于被 Git 忽略的 `bird-data/samples/`，来源和校验值见 `scripts/fetch-sample.ps1` 与 `docs/AI_WORK_LOG.md` 的 `[005]`、`[006]`。

## 2. 快速启动

### 2.1 真实 YOLO

在仓库根目录 PowerShell 执行：

```powershell
.\scripts\setup.ps1 -WithDetector
.\scripts\fetch-sample.ps1
.\scripts\start.ps1
```

启动脚本默认请求 API `8000`、前端 `5173`；端口占用时会向后寻找空闲 loopback 端口，并把实际值写入 `.local-run/services.json`。打开脚本打印的 `Frontend` 地址，从 `bird-data\samples\` 选择视频并点击 `Start analysis`。

建议检查：任务到达 `Completed`、视频可播放、框随时间出现、时间轴有绿色片段、点击事件跳转、刷新后任务仍存在。

### 2.2 UI mock

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1 -Mock
```

`-Mock` 将后端 detector 设为 `mock`，并将前端切换为内存 synthetic adapter。它只验证 UI 交互，不代表真实模型推理。只启动前端 mock：

```powershell
cd frontend
npm.cmd run dev:mock -- --host 127.0.0.1 --port 5173 --strictPort
```

如果 PowerShell 禁止脚本：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -WithDetector
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

停止时只使用 `.local-run/services.json` 记录的服务，不要按端口杀掉其他窗口的进程。

## 3. 安装和配置

目标环境是 Python 3.11+、Node 20+、PowerShell；本机已检查 Python 3.13.3、Node 24.20.0、npm 11.19.0。PyAV 负责本地视频探测和解码，不需要单独安装 FFmpeg 可执行文件；浏览器对编码器的支持仍然独立存在。

安装脚本会创建 `backend/.venv`，安装锁定 Python 依赖，执行 `npm ci` 并由 OpenAPI 生成 TypeScript 类型。`-WithDetector` 还安装 Ultralytics 依赖、下载 YOLO11n 并校验 SHA-256。

主要环境变量：

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `BIRD_DATA_DIR` | 相对 `../bird-data` | SQLite、视频、结果和日志目录 |
| `BIRD_DETECTOR` | factory 为 `mock`；启动脚本为 `ultralytics` | detector 后端 |
| `BIRD_MODEL_PATH` | `backend/models/yolo11n.pt` | 自定义本地权重路径 |
| `BIRD_MAX_UPLOAD_BYTES` | 2 GiB | 上传上限 |
| `BIRD_UPLOAD_RESERVE_BYTES` | 1 MiB | 磁盘保留空间 |
| `BIRD_ALLOWED_EXTENSIONS` | mp4/mov/m4v/mkv/webm | 扩展名 allowlist |
| `BIRD_SAMPLE_INTERVAL_SECONDS` | 0.4 | 抽帧间隔，范围 `(0, 5]` |
| `BIRD_CONFIDENCE_THRESHOLD` | 0.25 | detector 置信度阈值 |
| `BIRD_EVENT_MERGE_GAP_SECONDS` | 0.8 | 事件合并最大时间间隔 |
| `VITE_API_TARGET` | `http://127.0.0.1:8000` | Vite `/api` 代理目标 |
| `VITE_USE_MOCK` | Vite mock mode 自动设为 true | 前端是否使用内存 adapter |

## 4. 架构和数据流

```text
React/Vite browser
  | XHR upload, fetch, EventSource, HTML5 video
  v
FastAPI/Uvicorn on 127.0.0.1
  |-- ContractRoute: 统一错误 envelope
  |-- upload/probe/job/SSE/events/detections/Range
  |-- AnalysisWorker: 单线程队列、取消、恢复
  |     |-- PyAV PTS 抽帧
  |     |-- DetectorAdapter: mock 或 YOLO
  |     |-- EventBuilder: 时间间隔合并
  |     `-- SQLite + JSONL
  `-- 本机源视频和分析 metadata
```

一次真实分析：上传先写 `.staging/*.part`，检查大小、磁盘和视频内容；成功后创建 job 目录和 SQLite 记录，worker 依次进入 `queued -> probing -> running`，按 PTS 抽帧、检测、写 JSONL/索引、合并事件，最后进入 `completed`。异常进入 `failed`，删除或停止进入 `cancelled`。服务启动会把中断的 `probing/running` 任务清空部分结果并重新排队。

## 5. 本地数据布局

```text
bird-data[-<api_port>]/
  app.db
  .staging/
  videos/<job_id>/
    source.<ext>
    detections.jsonl
    metadata.json
  logs/
    api-<port>.stdout.log
    api-<port>.stderr.log
    vite-<port>.stdout.log
    vite-<port>.stderr.log
```

SQLite 表为 `jobs`、`frames`、`events`。`frames` 保存 JSONL 行号、PTS 和字节偏移，所以查询长视频时可以按时间范围读取，不必把全部帧载入内存。`metadata.json` 保存视频探测信息、分析参数、模型版本、权重哈希、设备和处理时长。重分析会创建新 job；源任务删除后，子任务保留自己的源文件或硬链接和 `source_job_id` lineage。

## 6. 契约和 API

契约来源是 `CONTRACTS.md`；机器可读唯一 schema 是 `docs/openapi.yaml`；`frontend/src/api/schema.d.ts` 由它生成。修改 OpenAPI 后执行：

```powershell
cd frontend
npm.cmd run api:types
npm.cmd run build
```

时间和坐标必须保持以下语义：

- 媒体时间是从第一个显示帧开始的秒，使用解码 PTS，不用帧号/FPS、请求时间或 UTC 时间。
- 检测查询和事件使用半开区间 `[start, end)`，事件不能越过视频时长。
- bbox 是旋转后显示图像上的 `[x1, y1, x2, y2]`，左上角原点，归一化到 `[0, 1]`，要求 `x1 < x2`、`y1 < y2`。
- Range 是源文件字节偏移，与视频秒数无关。

| 方法 | 路径 | 作用 | 约束 |
| --- | --- | --- | --- |
| GET | `/api/health` | 健康检查 | `status=ok` |
| POST | `/api/videos` | 上传并排队 | `multipart/form-data`，成功 `202` |
| GET | `/api/jobs` | 任务分页 | `limit` 1-100，可按状态过滤 |
| GET | `/api/jobs/{job_id}` | 任务详情 | 含视频元数据、计数、播放 URL |
| GET | `/api/jobs/{job_id}/progress` | SSE 进度 | 初始快照、进度、终态后关闭 |
| GET | `/api/jobs/{job_id}/events` | 事件分页 | `limit` 1-200 |
| GET | `/api/jobs/{job_id}/detections` | 检测帧 | 时间范围最多 60 秒，每页最多 1000 帧 |
| GET | `/api/jobs/{job_id}/video` | 本地播放 | 支持单个 closed/open/suffix Range |
| DELETE | `/api/jobs/{job_id}` | 删除任务 | 活跃任务先取消并等待 |
| POST | `/api/jobs/{job_id}/reanalyze` | 新建分析 | 返回新 job，旧结果保留 |

状态只允许 `queued`、`probing`、`running`、`completed`、`failed`、`cancelled`。错误统一为 `error.code/message/details/request_id` envelope。常见 code 有 `invalid_request`、`unsupported_media_type`、`payload_too_large`、`insufficient_storage`、`invalid_cursor`、`invalid_time_range`、`results_not_ready`、`invalid_range`、`detector_unavailable`、`analysis_failed` 和 `not_found`。

cursor 绑定 job、排序、过滤条件和检测时间范围；更改查询参数必须从新请求开始。SSE 的 job-local sequence 只作重连提示，重连后的初始快照是权威状态，不保证历史补发。

## 7. 模块地图

| 路径 | 责任 |
| --- | --- |
| `backend/app/api/errors.py` | 统一错误、验证和异常转换 |
| `backend/app/api/videos.py` | 上传、磁盘检查、探测、建任务 |
| `backend/app/api/jobs.py` | 任务、SSE、事件、检测、Range、删除、重分析 |
| `backend/app/services/video.py` | PyAV 探测、PTS 抽帧、旋转、MIME |
| `backend/app/services/analysis.py` | worker 队列、状态、detector、事件、失败 |
| `backend/app/storage/database.py` | SQLite、JSONL 索引、恢复、文件清理 |
| `backend/app/detectors/base.py` | Detection 和 adapter protocol、mock |
| `backend/app/detectors/yolo.py` | YOLO bird 过滤、bbox 归一化、可选 ByteTrack |
| `backend/app/tracking/events.py` | 按时间 gap 合并事件 |
| `frontend/src/App.tsx` | 上传、列表、SSE、分析视图、空态 |
| `frontend/src/api/client.ts` | 真实 fetch/XHR/EventSource 和内存 mock |
| `frontend/src/components/DetectionOverlay.tsx` | contain 留白和 bbox 映射 |
| `frontend/src/components/EventTimeline.tsx` | 事件高亮、播放头、跳转 |
| `frontend/src/components/JobList.tsx` | 任务状态、分页、刷新 |
| `frontend/src/ui.ts` | 文件校验、时间、最近帧、几何辅助 |
| `scripts/start.ps1` | 选端口、启动 API/Vite、写服务状态 |
| `scripts/setup.ps1` | venv、锁依赖、npm、schema、模型 |
| `scripts/fetch-sample.ps1` | 下载并校验两个公开视频样例 |
| `scripts/benchmark/run.py` | 本地 detector 性能和输出统计 |

## 8. Detector 和前端同步

参考权重来源为 `https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt`，SHA-256 为 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`。Ultralytics 代码/模型涉及 AGPL-3.0 或 Enterprise 条件，权重没有单独可验证许可证；闭源商业分发前必须复核或替换。

factory 未设置 backend 时默认 mock，但 `scripts/start.ps1` 普通模式明确设置 `ultralytics`。缺权重或依赖会让任务进入 `failed` 并显示安装提示。ByteTrack 需要 `lap>=0.5.12`，当前没有真实多鸟标注集证明 ID 稳定性。

真实前端按播放位置读取 5 秒检测窗口，自动读 cursor 页，使用最近采样帧且容差为 `max(0.65, sample_interval * 1.5)`；没有足够近的帧时不复用旧框。终态 SSE 到达后会再次读取任务和事件，避免计数停留在旧值。前端 mock 只存在于页面内存。

## 9. 测试和验收

```powershell
backend/.venv/Scripts/python.exe -m ruff check backend scripts
backend/.venv/Scripts/python.exe -m pytest -q
cd frontend
npm.cmd run lint
npm.cmd run build
npm.cmd test -- --reporter=dot
$env:BIRD_E2E_FRONTEND_PORT = "5182"
npm.cmd run test:browser
```

真实视频测试：

```powershell
$env:BIRD_TEST_VIDEO = (Resolve-Path ..\bird-data\samples\purple-swamphen-bath.mp4).Path
$env:BIRD_E2E_FRONTEND_PORT = "5181"
$env:VITE_API_TARGET = "http://127.0.0.1:8001"
npm.cmd run test:browser:real
```

已有验证记录为：后端 `28 passed`；Ruff 通过；前端 lint/build 通过；Vitest 7 项通过；mock browser 2 项通过；真实 browser 3 项通过。后端测试覆盖存储状态机、恢复、上传错误、VFR/PTS、Range、SSE、重分析、失败 detector、缺权重、删除等待和事件；前端测试覆盖文件校验、bbox 映射、时间轴、任务状态和浏览器交互。pytest 有一条 Starlette/AnyIO 弃用警告。

benchmark 命令：

```powershell
backend/.venv/Scripts/python.exe scripts/benchmark/run.py `
  --video D:\path\to\video.mp4 --detector ultralytics --device auto `
  --sample-interval 0.4 --input-size 640 --confidence 0.25 `
  --output benchmark.json
```

benchmark 的性能只适用于指定机器、视频和参数；不能替代标注集准确率评估。

## 10. 风险和下一步

1. `05394f0` 仍跟踪模型、视频、SQLite、`frontend/dist` 和测试截图；当前忽略规则只能阻止未来新增，不能解除已跟踪状态。
2. 没有真实无鸟、多鸟、遮挡、远景和人工标注集，不能给出召回率、精确率、IoU、误检率或事件边界指标。
3. 0.4 秒采样可能漏掉高速/短暂目标；事件 gap 0.8 秒和 padding 0.1 秒仍需用标注数据校准。
4. 单 worker、内存队列和本地磁盘只适合 MVP，不适合多用户生产部署；没有自动清理、备份或权限隔离。
5. 尚未验证 GPU、Safari/Firefox、干净机器安装、旋转视频浏览器显示和全部容器/编码组合。

下一步顺序：先清理 Git 产物；再建立有许可证、哈希和人工标注的静止鸟/飞鸟/远景/多鸟/无鸟集；运行 benchmark 和检测评估；校准采样、阈值、事件 gap 和 tracking；最后根据部署目标复核模型许可证并决定是否更换 detector。

## 11. 新窗口检查表

- [ ] 读取 `PLAN.md`、`CONTRACTS.md`、`docs/openapi.yaml` 和 `docs/AI_WORK_LOG.md`。
- [ ] 执行 `git status --short --branch`、`git diff --check`。
- [ ] 运行 `scripts/check-env.cmd` 和必要的 `setup.ps1`。
- [ ] 运行 `fetch-sample.ps1`，检查两个样例 MD5。
- [ ] 启动后从 `.local-run/services.json` 读取实际端口。
- [ ] 运行后端 pytest/Ruff、前端 lint/build/unit、mock browser 和真实 browser。
- [ ] 修改契约后运行 `npm.cmd run api:types` 和 build。
- [ ] 完成工作后在 `docs/AI_WORK_LOG.md` 末尾追加实际命令、结果、限制和交接。

## 12. 权威文件

- 产品范围：`PLAN.md`
- 跨模块契约：`CONTRACTS.md`
- API schema：`docs/openapi.yaml`
- 快速启动：`README.md`
- 当前交接：本文档
- 历史汇总：`docs/DEVELOPMENT_LOG.md`
- 原始协作日志：`docs/AI_WORK_LOG.md`
