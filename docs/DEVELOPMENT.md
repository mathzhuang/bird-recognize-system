# Local Development Documentation

本文件是开发文档入口。完整的当前架构、契约、数据布局、启动方式、测试矩阵、风险和交接检查表见 [HANDOFF.md](HANDOFF.md)；按提交和协作窗口整理的历史见 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)。

## 权威文件

- 产品范围和暂不包含内容：[PLAN.md](../PLAN.md)
- 跨模块语义：[CONTRACTS.md](../CONTRACTS.md)
- 机器可读 API：[openapi.yaml](openapi.yaml)
- 快速启动和样例：[README.md](../README.md)
- 当前交接：[HANDOFF.md](HANDOFF.md)
- 开发历史：[DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)
- 只追加协作记录：[AI_WORK_LOG.md](AI_WORK_LOG.md)

## 日常命令

```powershell
# 安装基础环境
.\scripts\setup.ps1

# 安装真实 YOLO、锁定依赖并准备权重
.\scripts\setup.ps1 -WithDetector

# 下载并校验两个本机样例
.\scripts\fetch-sample.ps1

# 启动真实模式；启动脚本会输出实际 URL
.\scripts\start.ps1

# 没有模型时只看 UI mock
.\scripts\start.ps1 -Mock

# 检查和测试
backend/.venv/Scripts/python.exe -m ruff check backend scripts
backend/.venv/Scripts/python.exe -m pytest -q
cd frontend
npm.cmd run lint
npm.cmd run build
npm.cmd test -- --reporter=dot
npm.cmd run test:browser
```

PowerShell 执行策略受限时，在命令前使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File`。服务端和前端只监听 loopback；实际端口和数据目录以 `.local-run/services.json` 为准。

## 修改契约时

编辑 `docs/openapi.yaml` 后，从 `frontend/` 执行：

```powershell
npm.cmd run api:types
npm.cmd run build
```

同时检查 `CONTRACTS.md`、后端 Pydantic/API 序列化和前端 client，不要在单个模块中发明不同的时间或 bbox 语义。
