# Local Development

## Requirements

- Python 3.11 or newer (the workspace was checked with Python 3.13).
- Node.js 20 or newer (the workspace was checked with Node 24).
- PowerShell on Windows, or equivalent shell commands on another OS.

The backend uses PyAV for local video probing and decoding; no separately installed FFmpeg executable or database server is needed. The default backend detector is local YOLO11n and requires separately installed `ultralytics` plus local weights. Use `scripts/start.ps1 -Mock` for a detector-free API smoke run. Do not commit model weights or source videos.

## Install

From the repository root, install the base environment:

```powershell
.\scripts\setup.ps1
```

To install the optional local YOLO runtime and download the pinned weights:

```powershell
.\scripts\setup.ps1 -WithDetector
```

If using a shell with a POSIX-style virtual environment, replace the Python path with `backend/.venv/bin/python` and invoke `npm` normally.

## Start

From the repository root:

```powershell
.\scripts\start.ps1
```

Open the address printed by the script, normally `http://127.0.0.1:5173`. It selects free loopback ports and keeps data separate when port 8000 is occupied. Stop its processes with `scripts/stop.ps1`.

## Frontend Mock

To try the frontend without using real detector results:

```powershell
cd frontend
npm.cmd run dev:mock -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173` and select the preloaded `demo-bird-video.webm` task to see fixed sample detections and two event intervals over a 3-second demo timeline; event seeking works without a source video. You can also upload a locally stored, playable video; the mock keeps it in the browser, does not upload it or contact a remote service, and applies the same sample results. Use a 3-second clip when checking player and timeline alignment. Mock tasks live only for the lifetime of the page.

The backend mock detector produces no detections unless test code supplies deterministic sample detections. Use `scripts/start.ps1 -Mock` for the synthetic UI preview, or set `BIRD_DETECTOR=mock` to check empty results through the real API. The default launcher selects local YOLO; missing weights are reported as a task error.

## Checks

```powershell
backend/.venv/Scripts/python -m pytest
cd frontend
npm.cmd run lint
npm.cmd run build
npm.cmd test
npm.cmd run test:browser
```

The shared contract is `CONTRACTS.md` and `docs/openapi.yaml`. After editing the OpenAPI file, regenerate frontend declarations with `npm.cmd run api:types` in `frontend/`, review `src/api/schema.d.ts`, then run the frontend build.
