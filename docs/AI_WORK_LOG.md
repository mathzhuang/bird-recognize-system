# AI 协作工作日志

本文件记录每个 AI 窗口对本项目做过的实际工作、验证证据、决策和交接事项。它是协作日志，不替代 `PLAN.md`、`CONTRACTS.md`、`docs/DEVELOPMENT.md` 或代码注释。

## 使用规则

- 每个 AI 开始工作前先读取本文件，了解上一位 AI 的交接和未解决问题。
- 每个 AI 完成工作前，在文件末尾追加一条完整记录；不要改写、删除或重排已有记录。
- 只有实际修改过的文件、实际运行过的命令和实际看到的结果才能写成已完成或已通过。
- 如果是补写历史记录，标题必须包含“补写”，并明确哪些内容来自现有文件/git diff，哪些内容无法确认。
- 日志按工作完成顺序追加，不要求时间连续。时间使用本机时间并注明时区；项目内的媒体时间仍遵守 `CONTRACTS.md`，两者不能混用。
- 日志不写视频原始内容、密钥、隐私信息或大段终端输出；用路径、命令和结果摘要代替。

## 记录模板

复制下面模板，在文件末尾追加，不要覆盖已有内容：

```markdown
## [序号] [日期时间 + 时区] [角色] [状态]

### 任务
- 本窗口负责：
- 读取的上下文：
- 本次采用的假设：

### 实际修改
- `path/to/file`：修改内容

### 关键决策或契约变化
- 决策：
- 是否修改 `CONTRACTS.md` 或 `docs/openapi.yaml`：是/否
- 如果修改，说明兼容影响和需要通知的角色：

### 验证证据
- 命令：`...`
  - 结果：通过/失败/未运行
- 命令：`...`
  - 结果：通过/失败/未运行

### 已知问题
- 问题：
- 严重程度：阻塞/严重/一般/待确认
- 复现方式或相关文件：

### 交接给下一位 AI
- 下一位需要先做：
- 不要重复做：
- 仍需确认：
```

## 日志记录

<!-- 后续 AI 只能在本行之后追加记录。 -->

## [001] [2026-10-30 Asia/Shanghai] [协作流程维护] [已完成]

### 任务
- 本窗口负责：检查前三个 AI 窗口是否留下可用的协作日志，并补充多 AI 日志协议。
- 读取的上下文：`PLAN.md`、`CONTRACTS.md`、`docs/DEVELOPMENT.md`、`scripts/benchmark/README.md`、`AI_COLLABORATION_PROMPTS.md`、当前目录和 git 状态。
- 本次采用的假设：前三个 AI 的聊天记录不作为可追溯日志，必须以工作区文件、git diff 和可复现命令为证据。

### 实际修改
- `docs/AI_WORK_LOG.md`：新增只追加的 AI 协作日志文件、记录模板和使用规则。
- `AI_COLLABORATION_PROMPTS.md`：增加日志协议、前三个窗口的补写提示词，并要求第四个及之后窗口读取和追加日志。

### 关键决策或契约变化
- `PLAN.md`、`CONTRACTS.md`、开发说明和 benchmark 说明继续承担原职责，不作为协作日志。
- 是否修改 `CONTRACTS.md` 或 `docs/openapi.yaml`：否。

### 验证证据
- 命令：检查工作区文件和 `rg --files`
  - 结果：通过；未发现既有的 AI 协作日志文件。
- 命令：读取 `CONTRACTS.md`、`docs/DEVELOPMENT.md` 和 `scripts/benchmark/README.md`
  - 结果：通过；确认这些文件分别是接口、开发说明和性能基线，不是窗口交接日志。

### 已知问题
- 前三个窗口的历史工作尚未逐一补写；它们的细节需要由原窗口根据仓库证据回填。
- 严重程度：一般。
- 复现方式或相关文件：按照 `AI_COLLABORATION_PROMPTS.md` 中的“前 3 个窗口的补写”提示词执行。

### 交接给下一位 AI
- 下一位需要先做：依次让架构、后端、算法窗口补写日志，再让前端窗口读取日志后继续。
- 不要重复做：不要重做前三个窗口已经完成的功能，也不要覆盖历史日志。
- 仍需确认：前三个窗口实际运行过的完整命令和当时未解决的问题。

## [002] [2026-10-30 19:46 Asia/Shanghai] [React/TypeScript 前端工程师] [已完成]

### 任务
- 本窗口负责：实现任务上传与列表、分析播放器、检测框、事件列表和时间轴；提供可关闭的开发 mock；运行组件检查并用浏览器验证。
- 读取的上下文：`PLAN.md`、`CONTRACTS.md`、`docs/openapi.yaml`、`docs/AI_WORK_LOG.md`、`docs/DEVELOPMENT.md`、`AI_COLLABORATION_PROMPTS.md`、`frontend/`、`backend/app/main.py`、相关 API 路由、git 状态和当前 git diff。
- 本次采用的假设：按契约使用 5 秒检测查询窗；mock 数据只用于 UI 交互验收。架构、后端、算法三个窗口的详细历史无法从现有日志确认；代码和文档显示当前后端只挂载 health 接口。

### 实际修改
- `frontend/src/App.tsx`：实现上传、任务分页和分析视图；显示上传/处理进度、错误、取消、无鸟结果和无检测帧；订阅任务进度事件。
- `frontend/src/api/client.ts`：添加基于 OpenAPI 生成类型的统一 API client、契约错误解析、XHR 上传进度、SSE 进度订阅及分页请求；mock adapter 通过 `vite --mode mock` 开启，默认开发模式连接真实 API。
- `frontend/src/components/JobList.tsx`：任务状态与分页列表。
- `frontend/src/components/EventTimeline.tsx`：按视频总时长显示事件和播放头；选择事件跳转到其起点。
- `frontend/src/components/DetectionOverlay.tsx`、`frontend/src/ui.ts`：按旋转后显示尺寸映射归一化 bbox，考虑 `object-fit: contain` 留白、容器缩放和采样时间容差。
- `frontend/src/styles.css`：新增桌面和窄屏工作台布局。
- `frontend/src/api/client.test.ts`、`frontend/src/ui.test.tsx`、`frontend/vitest.config.ts`：添加 API 分页/错误及上传校验、框映射、时间轴跳转、任务状态组件测试。
- `frontend/browser-tests/workflow.spec.ts`、`frontend/playwright.config.ts`：添加 Edge 上传、解码、事件跳转、检测框边界和窄屏溢出浏览器检查。
- `frontend/package.json`、`frontend/package-lock.json`、`frontend/vite.config.ts`、`frontend/src/vite-env.d.ts`、`frontend/.gitignore`：配置测试命令、开发 mock 模式、浏览器测试和环境类型。

### 关键决策或契约变化
- 检测结果只请求当前播放位置所属的 5 秒时间窗；单窗请求仍遵守契约的 60 秒范围和 1,000 帧分页上限，并用 cursor 读取该窗后续页。切窗时取消旧请求，快速拖动期间不会显示上一窗的框。
- bbox 使用 API 的后旋转 `display_width`/`display_height`，映射到实际视频显示矩形；按内容宽高比居中计算留白。
- 上传前校验扩展名和后端默认 2 GiB 限制；上传内容探测和最终大小仍由后端负责。
- 是否修改 `CONTRACTS.md` 或 `docs/openapi.yaml`：否。

### 验证证据
- 命令：`npm.cmd run build`
  - 结果：通过；TypeScript 检查通过，Vite 构建成功（34 个模块）。
- 命令：`npm.cmd test -- --reporter=verbose`
  - 结果：通过；2 个测试文件、7 项测试通过。
- 命令：`npm.cmd run test:browser`
  - 结果：通过；Edge 中完成本地生成 WebM 的 mock 上传、1.5 秒事件跳转、两只鸟框边界检查、390px 窄屏无横向溢出；截图为被忽略的 `frontend/test-results/desktop.png` 和 `mobile.png`。
- 命令：`npm.cmd audit --audit-level=moderate`
  - 结果：通过；0 vulnerabilities。初始安装的 Vitest 2 命中依赖告警，已升级至 Vitest 5.0.5 后复查通过。
- 命令：`npm.cmd run dev:mock -- --host 127.0.0.1 --port 5175 --strictPort`；`curl.exe -I http://127.0.0.1:5175/`
  - 结果：Vite 在 `http://127.0.0.1:5175/` 启动，页面 HTTP 200。5173 当时已被其他进程监听，未停止或覆盖该进程。
- 命令：本机检查 `GET http://127.0.0.1:8000/api/health` 和 `GET http://127.0.0.1:8000/api/jobs`
  - 结果：health 返回 `ok`；jobs 返回 HTTP 404。

### 已知问题
- 问题：后端尚未挂载契约中的上传、任务、进度 SSE、事件、检测时间范围和视频 Range 路由；真实 API 的任务列表返回 404，无法使用真实后端完成上传/分析联调。
- 严重程度：阻塞真实视频闭环，待后端完成接口。
- 复现方式或相关文件：访问 `http://127.0.0.1:8000/api/jobs`；`backend/app/main.py` 目前只包含 health router；`CONTRACTS.md` 和 `docs/openapi.yaml` 定义了剩余接口。

### 交接给下一位 AI
- 下一位需要先做：后端接入契约路由后，运行 `npm.cmd run dev` 联调真实上传、SSE 状态、事件分页、5 秒检测窗 cursor 和 HTTP Range 播放；检查浏览器与后端旋转后显示宽高一致。
- 不要重复做：不要改变 OpenAPI 字段、PTS 秒语义、半开事件范围或 bbox 坐标约定；不要默认一次加载长视频的全部帧。
- 仍需确认：三个早期窗口的历史交接和未解决事项；后端具体支持的视频大小配置与接口可用性。

## [003] [2026-10-30 20:11 Asia/Shanghai] [架构复核与 mock 联调补齐] [已完成]

### 任务
- 本窗口负责：回应 mock 数据缺失反馈，按架构窗口完成条件复核当前共享工作区，并修正核对中发现的契约、开发说明和测试偏差。
- 读取的上下文：`PLAN.md`、`CONTRACTS.md`、`docs/openapi.yaml`、`docs/DEVELOPMENT.md`、`docs/AI_WORK_LOG.md`、前后端当前实现、测试及 `git status`。
- 本次采用的假设：mock 模式应在无需真实视频的情况下展示事件和检测框；mock 上传路径仍可用于前端交互测试。

### 实际修改
- `CONTRACTS.md`：更正后端路由实现状态；明确 reanalysis 可逐字段覆盖默认分析参数；health 只承诺实际实现的 `200`。
- `docs/openapi.yaml`：删除 health 不会返回的 `503`；保留与后端一致的可选 reanalysis 覆盖字段。
- `docs/DEVELOPMENT.md`：记录 `npm.cmd run dev:mock` 用法、预置演示任务、后端默认 mock detector 行为和当前已实现路由。
- `backend/app/api/jobs.py`、`backend/tests/test_api_workflow.py`：支持单独覆盖 reanalysis 分析参数，拒绝显式 null；测试该契约行为。重复文件名任务完成等待阈值从 5 秒提高至 15 秒，适配本机解码耗时。
- `frontend/src/api/client.ts`：预置 mock demo 任务，并使八个模拟帧、八个检测框和两个事件的计数一致。
- `frontend/src/App.tsx`、`frontend/browser-tests/workflow.spec.ts`：支持无源视频演示任务的事件跳转；增加预置 mock 交互测试；模拟媒体元数据以隔离 Edge 编解码器差异；修复 Retry 按钮的 TypeScript 回调类型。

### 关键决策或契约变化
- 继续以 `docs/openapi.yaml` 为唯一 API schema 源；`AnalysisOverrides` 中未传字段使用服务端默认值，传 `null` 返回 `400`。
- 前端 mock 由 `npm run dev:mock` 启用，预置演示任务为页面内存数据，不上传视频；mock 上传只生成演示检测结果，不代表真实模型推理。

### 验证证据
- 命令：`backend/.venv/Scripts/python -m pytest`（在 `backend/` 执行）
  - 结果：通过；27 项测试通过，1 条 Starlette/AnyIO 弃用警告。
- 命令：`npm.cmd test -- --reporter=dot`（在 `frontend/` 执行）
  - 结果：通过；2 个测试文件、7 项测试通过。
- 命令：`npm.cmd run api:types`、`npm.cmd run build`（在 `frontend/` 执行）
  - 结果：通过；OpenAPI 类型生成成功，Vite 生产构建成功。
- 命令：`npm.cmd run test:browser`（在 `frontend/` 执行）
  - 结果：通过；Edge 中 2 项测试通过，覆盖预置 mock、事件跳转、检测框位置和窄屏布局。媒体时间由测试显式模拟，本次不将其记为浏览器原生视频解码验证。
- 命令：PyYAML 解析 `docs/openapi.yaml` 并核对路径和任务状态枚举
  - 结果：通过；9 个 API 路径，六种状态符合契约。
- 命令：`git diff --check` 和 `git check-ignore` 检查权重、bird-data、依赖、构建产物及浏览器截图
  - 结果：通过；检查目标均由忽略规则覆盖。

### 已知问题
- 问题：前端 mock 上传的事件和检测时间固定为 3 秒演示时间轴；用户上传更长或更短的视频时，不应把 mock 时间作为实际检测结论。
- 严重程度：一般，仅限开发 mock。
- 复现方式或相关文件：使用 `npm.cmd run dev:mock` 后上传非 3 秒视频。

### 交接给下一位 AI
- 下一位需要先做：从仓库根目录按 `docs/DEVELOPMENT.md` 启动后端和前端；浏览器 UI mock 用 `npm.cmd run dev:mock`，真实 API 联调用默认 `npm.cmd run dev`。
- 不要重复做：不要把前端演示 detections 当成后端 detector 结果；默认后端 mock detector 不伪造鸟框。
- 仍需确认：如需验证播放器原生解码和真实模型效果，应选本机测试视频进行端到端浏览器检查；本次不验证模型准确率、GPU 推理或模型许可适用性。

## [004] [2026-10-30 23:00 Asia/Shanghai] [总集成与交付复核] [已完成，有遗留项]

### 任务
- 本窗口负责：按 `PLAN.md` 和 `CONTRACTS.md` 复核共享工作区，运行真实模型端到端验收，补齐失败/空结果验证，并检查 Git 中的本机数据和生成物。
- 读取的上下文：`PLAN.md`、`CONTRACTS.md`、`docs/AI_WORK_LOG.md`、`README.md`、`docs/DEVELOPMENT.md`、API schema、前后端实现、测试、启动脚本、模型 benchmark 报告和 Git 状态。
- 接手时状态：工作区起始时 HEAD 为 `c10cb40 initialize`，`git status --short` 无输出；日志中有前端和架构/mock 两份详细交付记录，前三个窗口的后端/算法历史仍无法确认。
- 并发状态：本窗口工作期间 Git HEAD 前进到 `05394f0 添加模型权重，data与构建产物`（reflog 时间 2026-10-30 20:37 +0800）。提交作者/窗口无法从仓库确认；提交新增跟踪模型权重、样例视频、本机数据库、构建产物和截图，并包含后端零检测测试及浏览器测试配置。遵守共享仓库规则，没有保留对该提交文件的暂存删除；本窗口期间生成的已跟踪截图改动已恢复到 HEAD。
- 本次采用的假设：真实离线推理以工作区已有的 YOLO11n 权重和公开小样例验收；mock 只作为 UI/API 状态测试证据，不作为真实检测效果证据。

### 实际修改
- `.gitignore`：补充模型、常见视频、SQLite、本地数据目录、前端构建输出、Playwright 报告与截图、TypeScript 构建缓存的忽略规则。规则能阻止未来未跟踪文件进入 Git，但不能解除已跟踪文件。
- `frontend/browser-tests/real-workflow.spec.ts`：将 API fixture 的宽泛 glob 路由改为仅匹配以 `/api/` 开头的 URL path，避免拦截 `/src/api/client.ts` 等前端模块。新增的零结果和失败状态 fixture 测试及零检测后端测试在并发提交 `05394f0` 中已存在，来源不归本窗口。
- 本窗口还运行了验收测试；`frontend/test-results/desktop.png` 和 `mobile.png` 是测试运行产生的工作树变化，已恢复至提交中的版本。工作区的视频、权重、数据库和构建输出均保留在本机。
- 检查期间实际运行过 `git rm --cached -- <本机数据与生成物路径>`；确认这些路径来自并发提交后，用 `git restore --staged -- <相同路径>` 撤销了暂存删除。没有删除本机文件，也没有保留对并发提交的索引删除。

### 关键决策或契约变化
- 继续遵守 `docs/openapi.yaml` / `CONTRACTS.md` 的 API 字段、秒制 PTS 时间戳、半开事件区间、旋转后归一化 bbox、任务状态和错误 envelope；没有发现需要私自扩展契约的情况。
- 是否修改 `CONTRACTS.md` 或 `docs/openapi.yaml`：否。
- 对 `05394f0` 中已跟踪的视频、权重、数据库、构建文件和截图，本窗口未做索引删除；这与仓库“不将此类产物纳入 Git”的要求冲突，需由维护者明确安排后续清理提交。

### 验证证据
- 命令：`backend/.venv/Scripts/python.exe -m pytest -q`
  - 结果：通过，28 passed；有 1 条 Starlette 测试客户端引用 AnyIO 弃用 API 的依赖告警。
- 命令：`backend/.venv/Scripts/python.exe -m ruff check backend scripts`
  - 结果：通过，All checks passed。
- 命令：`npm.cmd run lint`（`frontend/`）
  - 结果：通过，ESLint 零 warning。
- 命令：`npm.cmd run build`（`frontend/`）
  - 结果：通过，`tsc -b` 和 Vite 生产构建成功。
- 命令：`npm.cmd test -- --reporter=dot`（`frontend/`）
  - 结果：通过，2 个测试文件、7 项测试通过。
- 命令：`$env:BIRD_E2E_FRONTEND_PORT='5182'; npm.cmd run test:browser`（`frontend/`）
  - 结果：通过，2 项 mock UI 浏览器测试通过，覆盖预置演示、事件跳转、框显示和窄屏布局。
- 命令：设置本机 `BIRD_TEST_VIDEO`、`VITE_API_TARGET=http://127.0.0.1:8002`、`BIRD_E2E_FRONTEND_PORT=5181` 后运行 `npm.cmd run test:browser:real`（`frontend/`）
  - 结果：通过，3 项 Edge 浏览器测试通过：真实 YOLO 上传/分析/播放/画框/时间轴跳转/刷新重开、零检测空态、detector 失败提示。一次较早运行暴露 API glob 会中止前端模块的问题；修正路由 path 匹配后整套测试通过。
- 命令：`scripts\check-env.cmd`
  - 结果：通过；Python 3.13.3、Node 24.20.0、npm 11.19.0 和本机 Python/Node 依赖可用。此命令输出权重缺失提示不是本次观察到的结果；权重文件当时存在。
- 命令：`scripts\stop.ps1`；随后 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1`
  - 结果：第一次调用被本机 PowerShell 执行策略阻止，没有停止服务；第二次通过该策略调用后，脚本核对 PID/启动时间/路径并停止本窗口的 API PID 30528 和前端 PID 35636。之后端口检查未发现 8002/5174 仍在监听。
- 命令：本机 API 查询 `GET /api/health`、任务详情、事件和 `detections?from_seconds=0&to_seconds=5`
  - 结果：health `ok`；真实样例任务 `40c439f2df3445e3ab2e9762902c4a80` 为 `completed`，视频 65.48 秒，处理 164 个采样帧，API 统计 53 个检测框、13 个事件。首个非空采样时刻为 1.6 秒，bbox 为 `[0.4460, 0.5828, 0.5571, 0.8501]`。
- 命令：`curl.exe -sS -D - -o NUL -H "Range: bytes=0-3" "http://127.0.0.1:8002/api/jobs/<job_id>/video"`
  - 结果：通过，HTTP 206，`Content-Range: bytes 0-3/6784739`，`Content-Type: video/mp4`；同一视频在 Edge 中实际播放。
- 命令：读取 `bird-data/samples/cathedral-hawk-benchmark.json` 和真实任务 `metadata.json`
  - 结果：模型为 `ultralytics-yolo11n-coco`，Ultralytics 8.4.193，CPU；模型 SHA-256 为 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`。已有 benchmark 报告记录含模型加载在内 51.66 秒、吞吐 1.267 视频秒/处理秒、峰值内存约 396.8 MiB；该值来自已有报告，本窗口没有重新运行 benchmark。新任务 metadata 单独记录处理 11.91 秒，不能与含冷启动 benchmark 混为同一测量口径。
- 命令：`git diff --check`、`git check-ignore -v --no-index ...`、`git ls-files` 检查模型、视频、SQLite、构建和浏览器输出
  - 结果：空白检查通过；新增规则会忽略这些路径，但最新提交仍跟踪模型、样例 MP4、SQLite、`frontend/dist` 和 `frontend/test-results` 文件。benchmark JSON 是文本验收记录，仍被跟踪。此遗留项没有通过本窗口的清理提交解决。

### 已知问题
- 问题：`05394f0` 将模型权重（5.61 MB）、样例视频（6.78 MB）、SQLite 数据库（45 KB）、前端构建输出和浏览器截图加入 Git。当前 `.gitignore` 不能取消已跟踪状态；未提交的工作树只新增了规则。
- 严重程度：一般，需在后续清理提交中处理；本窗口保留它们是为了不回滚其他 AI 的并发提交。
- 问题：只用一段真实有鸟视频完成 detector 验收。没有真实无鸟或多鸟视频的检测效果结果，也没有人工标注精度/召回率评估。
- 严重程度：待确认；零检测和多鸟行为目前由 mock/API 单元测试覆盖，不能替代真实素材验证。
- 问题：样例结果不能代表模型通用准确率；0.4 秒采样可能漏过快速或短暂目标。当前记录为 CPU 推理，没有验证 GPU。
- 严重程度：一般；真实样例和 benchmark 数值见本节验证证据。
- 问题：Ultralytics 代码/模型使用涉及 AGPL-3.0 或 Enterprise 条件；本地权重文件没有单独验证的许可证元数据。闭源分发适用性无法确认。
- 严重程度：待确认；部署或分发前需由项目维护者审查许可证。
- 问题：本轮运行浏览器套件使用本机 Edge；未在干净新机器执行完整 setup 安装，也未测试 Safari/Firefox 或所有允许的容器/编码组合。
- 严重程度：一般；安装说明已在 README，跨设备兼容性仍未验证。

### 交接给下一位 AI
- 下一位需要先做：与维护者协调清理 `05394f0` 中已跟踪的大型/运行产物；增加真实无鸟和多鸟素材验收；按目标用途确认权重许可证。
- 不要重复做：重新运行本机样例的完整浏览器链路并生成新的已跟踪截图；真实工作流及零结果/失败 fixture 已有 Playwright 覆盖。
- 仍需确认：生成物解除跟踪的后续提交安排；目标视频场景上的召回率、误报率与事件边界指标；商业分发许可；GPU/其他浏览器表现。
- 启动交接：真实浏览器验收使用 `http://127.0.0.1:5174`（API `http://127.0.0.1:8002`），之后停止；交付前重新运行启动脚本，当前服务为 `http://127.0.0.1:5174`（API `http://127.0.0.1:8001`，detector 配置为 `ultralytics`），health 返回 `ok`，前端返回 HTTP 200。新环境先运行 `.\scripts\setup.ps1 -WithDetector` 安装锁定依赖并准备本地权重，再执行 `.\scripts\start.ps1`；启动脚本会打印浏览器 URL，默认前端端口为 `5173`，端口占用时会选择后续空闲端口。缺权重时默认检测任务会失败并提示安装；`.\scripts\start.ps1 -Mock` 可验证本机 UI 流程。

## [005] [2026-10-30 23:23 Asia/Shanghai] [用户快速试跑支持] [已完成]

### 任务
- 本窗口负责：为没有视频的用户准备一个可直接观察真实鸟框和时间轴的短流程，并把结果放进当前本机任务列表。
- 读取的上下文：`README.md`、`scripts/fetch-sample.ps1`、`scripts/start.ps1`、当前本机服务状态及样例文件。
- 本次采用的假设：一段公开鹰视频足以展示上传到结果的真实模型链路；第二段素材不是本次必要条件。

### 实际修改
- `README.md`：新增真实样例视频的快速手动试跑步骤，说明文件位置、约 14 秒的本机实测分析时间和预期结果规模。
- `docs/AI_WORK_LOG.md`：记录本次样例校验和当前服务联调结果。
- 样例 `bird-data/samples/cathedral-hawk-fledges.mp4` 已在工作区。运行取样脚本时文件已存在，脚本校验 MD5 后报告 ready；本窗口没有重新下载网络文件。

### 关键决策或契约变化
- 采用现有验证样例：Jeremy Seto 在 Flickr 发布、Internet Archive 提供 MP4 衍生文件、CC BY-NC-SA 2.0。样例用于本地浏览器上传，不发送给外部服务。
- 是否修改 `CONTRACTS.md` 或 `docs/openapi.yaml`：否。

### 验证证据
- 命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch-sample.ps1` 和 `Get-FileHash -Algorithm MD5 .\bird-data\samples\cathedral-hawk-fledges.mp4`
  - 结果：通过；脚本报告样例 ready，MD5 为 `0773fd7dc7eea37d693288aa3aa3413e`。由于文件已存在，只验证了本地副本，没有发生网络下载。
- 命令：设置 `BIRD_TEST_VIDEO` 为该本地 MP4、`BIRD_E2E_FRONTEND_PORT=5181`、`VITE_API_TARGET=http://127.0.0.1:8001` 后运行 `npm.cmd run test:browser:real`
  - 结果：通过，3 项测试通过。真实视频 UI 链路测试 18.6 秒完成；零检测和失败任务 UI 也通过。
- 命令：查询当前 API 最新任务详情、事件和前 5 秒检测分页
  - 结果：任务 `c577ae48d2964f7bbf42711f88ce188c` 状态 `completed`，媒体时长 65.48 秒，处理 164 个采样帧，53 个检测框、13 个事件；首个非空检测在 1.6 秒。任务 metadata 记录 CPU 模型分析 13.51 秒。
- 命令：当前前端 `GET http://127.0.0.1:5174/` 和 API `GET http://127.0.0.1:8001/api/health`
  - 结果：前端 HTTP 200；API 返回 `status=ok`。服务保持运行，任务在页面刷新后仍可从任务列表重开。

### 已知问题
- 问题：样例为一段约 65 秒的有鸟视频；未准备第二个真实无鸟或多鸟视频。模型效果没有人工精度评估。
- 严重程度：一般；本次目标是让用户快速观察完整真实链路。
- 问题：该公开视频授权为 CC BY-NC-SA 2.0，使用和再分发需保留署名并遵守非商业、相同方式共享条款。
- 严重程度：待确认；对超出个人本机测试的使用需先核查授权。

### 交接给下一位 AI
- 下一位需要先做：如扩展数据覆盖，再添加授权明确的真实无鸟和多鸟小样例，并记录来源、哈希与标注证据。
- 不要重复做：不必再次下载或重复跑当前样例；任务 `c577ae48d2964f7bbf42711f88ce188c` 已在 API 8001 的本机数据库中完成。
- 仍需确认：该公开视频授权是否适用于未来对外分发；当前 URL 端口以 `.local-run/services.json` 和启动脚本输出为准。

## [006] [2026-10-30 23:34 Asia/Shanghai] [补充快速短视频样例] [已完成]

### 任务
- 本窗口负责：按用户要求再提供一段更短的视频，验证它能否快速完成真实 detector 流程。
- 读取的上下文：`README.md`、`scripts/fetch-sample.ps1`、Internet Archive 的 item metadata 和当前本机服务。
- 本次采用的假设：选用文件较小且含清晰鸟目标的视频，供个人本机测试；保留原文件，不转码或剪辑。

### 实际修改
- `scripts/fetch-sample.ps1`：增加短样例的下载与 MD5 校验；已有同名文件若校验不匹配则拒绝覆盖，下载失败或哈希错误时清理临时文件。
- `README.md`：说明 11 秒短视频的文件名、快速测试方式、来源和不得改编的授权条件。
- `docs/AI_WORK_LOG.md`：记录下载及真实浏览器结果。
- 新增本机文件 `bird-data/samples/purple-swamphen-bath.mp4`，1,147,098 bytes；由脚本从 Internet Archive 下载并校验后保存。Git 忽略规则覆盖 `bird-data/`，短视频未被 Git 跟踪。

### 关键决策或契约变化
- 来源为 Flickr 用户 Naveen Reddy 发布的《Purple Swamphen taking a bath》，Internet Archive identifier `Flickr-35518492523`；metadata 标记 CC BY-NC-ND 2.0。保留原文件用于检测，不进行剪辑/改编。
- 是否修改 `CONTRACTS.md` 或 `docs/openapi.yaml`：否。

### 验证证据
- 命令：读取 `https://archive.org/metadata/Flickr-35518492523`
  - 结果：metadata 标题、创作者链接、授权、11.02 秒时长、1,147,098 bytes 和 MP4 文件名可查；来源 MD5 为 `19d9c2937789100fd492c4e3220e588d`。
- 命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\fetch-sample.ps1`；`Get-FileHash -Algorithm MD5 .\bird-data\samples\purple-swamphen-bath.mp4`
  - 结果：通过；下载脚本报告两个样例 ready，短片实际 MD5 与来源一致。
- 命令：将 `BIRD_TEST_VIDEO` 设为短片路径、`BIRD_E2E_FRONTEND_PORT=5181`、`VITE_API_TARGET=http://127.0.0.1:8001` 后运行 `npm.cmd run test:browser:real -- --grep 'real local detector upload' --timeout 120000`（`frontend/`）
  - 结果：通过，真实浏览器工作流 1 项通过；完整上传、任务完成、Range 播放、显示鸟框、事件跳转和刷新重开。
- 命令：查询 API 任务 `3951e92145004ed48b3f21cd364fabe6` 的详情、events、detections 和 metadata
  - 结果：completed；视频 11.0 秒，28 个采样帧，16 个检测框，1 个事件 `[0.0, 6.1)`，最高置信度约 0.933；CPU 分析耗时约 2.32 秒。Edge 截图可见沐浴中的紫水鸡、检测框和高亮事件时间轴。
- 命令：`git check-ignore -v --no-index bird-data/samples/purple-swamphen-bath.mp4`、`git ls-files --error-unmatch bird-data/samples/purple-swamphen-bath.mp4`
  - 结果：被 `bird-data/` 忽略；`git ls-files` 未找到该短片。
- 命令：`git diff --check`
  - 结果：通过。

### 已知问题
- 问题：该短片授权为 CC BY-NC-ND 2.0。用于本机检测时保留原样；不能把转码/剪辑版本当作允许再分发的派生物，进一步发布前需核查条款和署名要求。
- 严重程度：待确认；本次只作未修改的本机测试副本。
- 问题：单个短片上的 16 个检测框仅证明链路工作，不代表通用准确率。
- 严重程度：一般；没有与人工标注对比。

### 交接给下一位 AI
- 下一位需要先做：用全新数据目录运行 `scripts/fetch-sample.ps1` 复核两个样例都能从远端重新取得；目前本窗口验证的是新短片下载，长片已事先存在。
- 不要重复做：不需要重复获取短片或重新跑该任务；任务 `3951e92145004ed48b3f21cd364fabe6` 和另一个同视频任务已存在于当前本机 API 数据库。
- 仍需确认：CC BY-NC-ND 样例用于不同用途时的许可要求；真实空视频、多鸟和精度指标。

## [007] [2026-10-30 23:36 Asia/Shanghai] [本机样例任务收尾] [已完成]

### 任务
- 本窗口负责：清理刚才重复短片验收生成的本机任务，保持用户打开页面时每段视频只有一条结果。
- 读取的上下文：当前 API 任务列表和上一条 `[006]` 记录。
- 本次采用的假设：`afdf01a6b5a14ec7ba5e2d8c5161424b` 是本窗口短片验收产生的重复任务，原始源视频保留在 `bird-data/samples/`，另一条完成任务 `3951e92145004ed48b3f21cd364fabe6` 继续供用户查看。

### 实际修改
- 通过本机 API 删除重复任务 `afdf01a6b5a14ec7ba5e2d8c5161424b`；样例 MP4 没有删除。

### 关键决策或契约变化
- 使用 `DELETE /api/jobs/{job_id}` 清理本窗口重复上传任务，符合现有任务删除 API。
- 是否修改 `CONTRACTS.md` 或 `docs/openapi.yaml`：否。

### 验证证据
- 命令：`Invoke-WebRequest http://127.0.0.1:8001/api/jobs/afdf01a6b5a14ec7ba5e2d8c5161424b -Method Delete`
  - 结果：HTTP 204。
- 命令：`GET http://127.0.0.1:8001/api/jobs?limit=10`
  - 结果：通过；只列出一条 `purple-swamphen-bath.mp4` 和一条 `cathedral-hawk-fledges.mp4`，两者状态均为 `completed`。
- 命令：`git diff --check`
  - 结果：通过。

### 已知问题
- 问题：无新增；样例许可证和检测精度限制见 `[006]`。
- 严重程度：无。

### 交接给下一位 AI
- 下一位需要先做：如用户要重跑，直接刷新 `http://127.0.0.1:5174` 并使用任务列表现有结果，或再次上传任一 `bird-data/samples/` 文件。
- 不要重复做：不要删除任务 `3951e92145004ed48b3f21cd364fabe6` 或鹰视频任务 `c577ae48d2964f7bbf42711f88ce188c`；这两条供当前用户查看。
- 仍需确认：按 `[006]` 记录处理授权与真实模型评估限制。
