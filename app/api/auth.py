from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.DASHBOARD_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key
