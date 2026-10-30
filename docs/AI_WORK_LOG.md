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
