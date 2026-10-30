from fastapi import APIRouter

from app.api.errors import ContractRoute
from app.api.jobs import router as jobs_router
from app.api.videos import router as videos_router
from app.services.runtime import start_runtime, stop_runtime

router = APIRouter(route_class=ContractRoute)


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "bird-video-analyzer",
        "version": "0.1.0",
        "mode": "local",
    }


router.include_router(videos_router)
router.include_router(jobs_router)
router.add_event_handler("startup", start_runtime)
router.add_event_handler("shutdown", stop_runtime)
