# Development Log

这是面向维护者的项目开发汇总。它把 Git 提交、协作日志和当前代码复核结果放在一起，便于新窗口接手。逐窗口原始事实仍以 `docs/AI_WORK_LOG.md` 为准。

## 1. 证据规则

- 产品范围以 `PLAN.md` 为准。
- 跨模块字段、时间、bbox、状态和 API 以 `CONTRACTS.md` 与 `docs/openapi.yaml` 为准。
- Git 能证明提交快照和时间，但不能单独证明哪个 AI 窗口完成了具体代码；缺失历史不补造。
- 性能、准确率和浏览器结论只有在有实际命令或测试证据时才标记为已验证。

## 2. 当前快照

- 复核日期：2026-10-31，Asia/Singapore。
- 当前 HEAD：`bc15a9e`，`完善real workflow`。
- 提交链：`c10cb40 initialize` -> `05394f0 添加模型权重，data与构建产物` -> `bc15a9e 完善real workflow`。
- 当前实现是本机离线 MVP：FastAPI、单后台 worker、SQLite、JSONL、React/Vite 和可选 YOLO detector。
- 当前工作树在本次复核开始时干净；本次文档工作会产生新的文档改动。

## 3. Git 提交历史

### `c10cb40 initialize`

该提交包含当前主要实现结构：FastAPI API 和统一错误处理、上传/任务/SSE/事件/检测/Range/删除/重分析路由；SQLite/JSONL 存储；PyAV PTS 探测和抽帧；mock 与 YOLO detector adapter；事件合并；React/Vite 播放器、检测框、时间轴和任务列表；单元、API、浏览器测试；benchmark 和启动脚本。

仓库没有可确认的独立早期后端/算法窗口报告，因此上述阶段细节由当前代码、测试和契约复核得出，不推断缺失的历史。

### `05394f0 添加模型权重，data与构建产物`

该提交新增或跟踪了 YOLO 权重、真实鹰视频、benchmark JSON、本地 SQLite、Vite `dist`、TypeScript build info 和 Playwright 截图，并加入零检测 API 测试和真实 workflow 配置。它留下维护问题：模型、视频、数据库和生成物不应进入 Git。后续 `.gitignore` 已覆盖这些路径，但忽略规则不能自动解除已经跟踪的文件。

### `bc15a9e 完善real workflow`

该提交扩充了 README 的样例试跑说明，扩展了 `scripts/fetch-sample.ps1` 的双样例下载/MD5 校验，补充了模型、视频、数据库、构建和 Playwright 输出的忽略规则，并修正真实 Playwright fixture 只拦截 `/api/` path，避免误拦截 `/src/api/client.ts`。它还包含前一轮交接日志。

## 4. 协作窗口历史

以下摘要来自 `docs/AI_WORK_LOG.md` 的 `[001]` 至 `[007]`，并与当前实现交叉检查。具体提交归属无法完全从 Git 映射。

### `[001]` 协作流程维护

建立只追加的 AI 工作日志、记录模板和多窗口交接规则，要求用文件、Git 和可复现命令作为证据。

### `[002]` React/TypeScript 前端

实现上传、任务列表、SSE、播放器、检测框、事件列表、时间轴、文件校验、API client、前端 mock、组件测试和 mock 浏览器测试。前端按旋转后显示尺寸与 contain 留白映射 bbox，并按时间窗口读取检测结果。该记录当时认为后端 API 尚未挂载；那是历史状态，不是当前状态。

### `[003]` 架构复核与 mock 联调

补齐预置 mock 任务、事件跳转和检测框演示，明确 OpenAPI 为唯一 schema 源，修正 reanalysis 参数覆盖语义，更新契约/开发说明并补后端工作流测试。

### `[004]` 总集成与交付复核

记录真实 YOLO11n CPU 链路：上传、排队、分析、Range、检测框、事件时间轴、跳转和刷新重开；记录了 65.48 秒样例、53 个检测框、13 个事件，以及 pytest、Ruff、lint、build、Vitest 和浏览器检查。也记录了许可证、CPU 性能、真实无鸟/多鸟未验证和 Git 产物跟踪风险。

### `[005]` 用户快速试跑支持

确认鹰视频样例可重复校验，更新 README，并把完成任务留在本机任务列表。

### `[006]` 补充快速短视频样例

从 Internet Archive metadata 核对并下载《Purple Swamphen taking a bath》MP4，记录 CC BY-NC-ND 2.0、大小和 MD5；真实浏览器 workflow 通过，产生 16 个框和 1 个事件。

### `[007]` 本机样例任务收尾

删除重复短片任务，保留鹰视频和短片各一条已完成任务，避免用户看到重复验收结果。

## 5. 已确认的技术决策

### 时间和坐标

媒体时间使用 PyAV 解码 PTS，首个显示帧归零；事件使用半开区间；bbox 使用旋转后显示图像的归一化坐标。这样可以覆盖 VFR 和旋转元数据，避免用名义 FPS 或 coded pixels 造成前后端错位。

### 存储和任务

SQLite 记录任务摘要和索引，JSONL 流式保存采样帧，`frames` 表保存行号、PTS 和字节偏移。长视频查询按范围读取。单 worker 保持 MVP 简单，重启时将中断任务重新排队。

### Detector

`DetectorAdapter` 分离模型实现和服务。backend factory 未设置时默认 mock；启动脚本普通模式显式选择 Ultralytics。真实 adapter 只筛选 COCO `bird`，记录模型版本、权重哈希、设备和分析参数；缺权重或依赖时任务失败并提供安装提示。ByteTrack 是可选项，尚无真实多鸟标注集验证 ID 稳定性。

### 事件和前端同步

`EventBuilder` 默认以 0.8 秒 gap 合并，最短事件 0.3 秒，边界 padding 0.1 秒。前端按播放时间读取 5 秒检测窗口，使用最近采样帧和容差，不足够近时不复用旧框。终态 SSE 后再次读取任务和事件，避免计数停留在旧值。

## 6. 验证记录汇总

这些结果来自工作日志和实际命令记录；新维护者应按 `docs/HANDOFF.md` 重跑。

| 命令/检查 | 已记录结果 | 证明范围 |
| --- | --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -q` | `28 passed`，1 条 Starlette/AnyIO 弃用警告 | 后端 API、存储、detector、事件和错误流程 |
| `backend/.venv/Scripts/python.exe -m ruff check backend scripts` | 通过 | Python 静态检查 |
| `npm.cmd run lint` | 通过 | ESLint |
| `npm.cmd run build` | 通过，34 个模块 | TypeScript 和 Vite 构建 |
| `npm.cmd test -- --reporter=dot` | 7 项通过 | 前端辅助函数、API 和组件 |
| `npm.cmd run test:browser` | 2 项通过 | mock 任务、上传、事件、框布局和窄屏 |
| `npm.cmd run test:browser:real` | 3 项通过 | 真实视频闭环、空结果和失败 fixture |
| `scripts/check-env.cmd` | 通过 | Python/Node/基础依赖 |
| 真实 `/video` Range | HTTP 206 | 浏览器按字节寻址播放 |
| 真实刷新重开 | 通过 | SQLite 和文件持久化 |

已有鹰视频 benchmark 报告记录 CPU、YOLO11n、0.4 秒采样和约 1.27 视频秒/处理秒；该值包含模型加载且只适用于当时机器和视频。短紫水鸡任务 metadata 记录过约 2.32 秒处理时间，同样不是通用性能指标。

## 7. 未解决问题

1. Git 仍跟踪模型、视频、数据库、构建输出和截图，需要维护者安排清理索引/历史。
2. 没有真实标注集，因此没有可信的召回率、精确率、IoU、误检率或事件边界指标。
3. 真实无鸟、多鸟、遮挡、远景和高速飞行场景未完整实测。
4. GPU、Safari、Firefox、干净机器安装和全部容器/编码器未验证。
5. Ultralytics/YOLO 许可对闭源商业分发的适用性未确认。
6. 单 worker 和本地磁盘模型只适合本机 MVP，不是多用户生产架构。

## 8. 下一步执行顺序

1. 清理 Git 中不应提交的权重、视频、数据库、dist 和截图，保留下载脚本和文本 benchmark。
2. 固化样例清单和许可证，加入静止鸟、飞鸟、远景、小目标、多鸟、遮挡和无鸟片段。
3. 建立人工标注与评估脚本，输出召回率、误检率、IoU、事件边界和速度报告。
4. 用评估结果校准采样、阈值、事件 gap 和 tracking。
5. 按部署目标复核许可证，必要时替换 detector adapter 后端。
6. 长期运行前再考虑任务取消 API、磁盘配额、日志轮转、备份和独立队列。

## 9. 新窗口最小步骤

```powershell
Get-Content -Encoding utf8 PLAN.md
Get-Content -Encoding utf8 CONTRACTS.md
Get-Content -Encoding utf8 docs/AI_WORK_LOG.md -Tail 220
git status --short --branch
git diff --check
```

之后按 `docs/HANDOFF.md` 启动和验证。完成工作前必须在 `docs/AI_WORK_LOG.md` 末尾追加接手状态、实际修改、实际命令/结果、未解决问题和交接事项。
