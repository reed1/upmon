from fastapi import APIRouter

router = APIRouter(include_in_schema=False)


@router.get("/health")
async def health():
    return {"status": "UP"}
