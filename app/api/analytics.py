from fastapi import APIRouter, Depends
from app.api.auth import verify_api_key
from app.db.crud import get_analytics_summary

router = APIRouter()


@router.get("/summary")
async def analytics_summary(_: str = Depends(verify_api_key)):
    return await get_analytics_summary()
