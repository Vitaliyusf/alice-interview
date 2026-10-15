from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness only: it never calls the model, so a slow provider does not restart the service."""
    return {"status": "ok"}
