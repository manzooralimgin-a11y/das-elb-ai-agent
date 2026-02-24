from fastapi import APIRouter
from app.api import emails, analytics, learning

api_router = APIRouter()

api_router.include_router(emails.router, prefix="/emails", tags=["emails"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
