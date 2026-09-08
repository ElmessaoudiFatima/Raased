from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
async def health_check():
    """
    Returns API service operational status.
    """
    return {"status": "ok"}
