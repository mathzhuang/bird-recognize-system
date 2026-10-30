from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Local Bird Video Analyzer",
    version="0.1.0",
    description="Local-only video analysis API. See CONTRACTS.md for the shared API contract.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(health_router, prefix="/api")
