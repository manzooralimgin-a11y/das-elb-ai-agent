"""
Learning API — Style sync and profile retrieval endpoints.
POST /learning/sync  — Reads Sent Items folder and updates the style profile
GET  /learning/profile — Returns the current learned style profile
"""
import logging
from typing import Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from app.api.auth import verify_api_key
from app.email.sent_reader import fetch_sent_emails_imap
from app.agents.style_learner import analyze_sent_emails, build_style_injection
from app.agents.rag_store import rag_store
from app.db.crud import save_style_profile, get_latest_style_profile

router = APIRouter()
logger = logging.getLogger(__name__)

class ProfileUpdatePayload(BaseModel):
    profile_json: Dict[str, Any]
    injected_prompt: str


@router.post("/sync")
async def sync_style_profile(_=Depends(verify_api_key)):
    """
    Fetches the hotel's Sent Items folder, analyzes the writing style with Gemini,
    and saves the updated style profile to the database.
    """
    logger.info("Starting style profile sync...")
    try:
        # Fetch a solid chunk for the RAG index
        sent_emails = fetch_sent_emails_imap(max_results=100)
        logger.info(f"Fetched {len(sent_emails)} sent emails for RAG and style analysis")

        import asyncio
        # Run the intensive embedding task and the LLM analysis concurrently or off-thread
        # We only feed the first 15 to the LLM to avoid token limits
        profile_json = await asyncio.to_thread(analyze_sent_emails, sent_emails[:15])
        injected_prompt = build_style_injection(profile_json)

        # Build the RAG index with all 100 emails
        await asyncio.to_thread(rag_store.update_index, sent_emails)

        await save_style_profile(
            emails_analyzed=len(sent_emails),
            profile_json=profile_json,
            injected_prompt=injected_prompt,
        )

        return {
            "synced": True,
            "emails_analyzed": len(sent_emails),
            "no_reply_patterns_found": len(profile_json.get("no_reply_indicators", [])),
            "greeting_patterns_found": len(profile_json.get("greeting_patterns", [])),
            "sign_off_detected": bool(profile_json.get("sign_off")),
        }

    except Exception as e:
        logger.error(f"Style sync failed: {e}", exc_info=True)
        return {"synced": False, "error": str(e), "emails_analyzed": 0}


@router.get("/profile")
async def get_style_profile(_=Depends(verify_api_key)):
    """Returns the latest learned style profile, or null if not yet synced."""
    profile = await get_latest_style_profile()
    if not profile:
        return {
            "synced": False,
            "message": "No style profile yet. Click 'Sync Now' to analyze sent emails.",
        }
    return {"synced": True, **profile}


@router.put("/profile")
async def update_style_profile(payload: ProfileUpdatePayload, _=Depends(verify_api_key)):
    """Manually update the style profile."""
    latest = await get_latest_style_profile()
    count = latest.get("emails_analyzed", 0) if latest else 0
    await save_style_profile(
        emails_analyzed=count,
        profile_json=payload.profile_json,
        injected_prompt=payload.injected_prompt,
    )
    return {"status": "success"}
