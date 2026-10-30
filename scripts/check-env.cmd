@echo off
setlocal

echo Python:
python --version || exit /b 1

echo Node:
node --version || exit /b 1

echo npm:
npm.cmd --version || exit /b 1

set "ROOT=%~dp0.."
set "BACKEND_PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" (
  echo Backend environment is missing. Run scripts\setup.ps1.
  exit /b 1
)
"%BACKEND_PYTHON%" -c "import fastapi, av, numpy" || exit /b 1
if not exist "%ROOT%\frontend\node_modules" (
  echo Frontend dependencies are missing. Run scripts\setup.ps1.
  exit /b 1
)
if not exist "%ROOT%\backend\models\yolo11n.pt" echo YOLO weights are missing. Run scripts\setup.ps1 -WithDetector or scripts\start.ps1 -Mock.
echo Environment check passed. Start the app with scripts\start.ps1.
