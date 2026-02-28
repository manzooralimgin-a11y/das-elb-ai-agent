import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.api.auth import verify_api_key
from app.db.crud import (
    get_all_emails,
    get_email_by_id,
    update_email_status,
    update_email_record_fields,
    add_audit_log,
    delete_email_record,
)
from app.email.imap_client import send_reply_smtp
from app.integrations.notifications import send_escalation_email
from app.email.poller import import_all_existing_emails, poll_and_process
from app.pipeline.orchestrator import process_email
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ApprovePayload(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    approved_by: str = "staff"


class RejectPayload(BaseModel):
    reason: str
    rejected_by: str = "staff"


class EscalatePayload(BaseModel):
    reason: str
    escalated_by: str = "staff"


@router.get("")
async def list_emails(
    status: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    limit: int = Query(50, le=10000),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_api_key),
):
    return await get_all_emails(status=status, intent=intent, limit=limit, offset=offset)


@router.get("/{email_id}")
async def get_email(email_id: int, _: str = Depends(verify_api_key)):
    record = await get_email_by_id(email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")
    return record


@router.post("/{email_id}/approve")
async def approve_email(
    email_id: int,
    payload: ApprovePayload,
    _: str = Depends(verify_api_key),
):
    """
    Approve and send an email reply via IONOS SMTP.
    If body/subject are provided in the payload, they override the AI draft.
    The original guest's Message-ID is passed for proper email threading.
    """
    record = await get_email_by_id(email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")
    if record["status"] == "sent":
        raise HTTPException(status_code=400, detail="Email already sent")

    original_body = record.get("draft_body", "")
    final_body = payload.body or original_body
    final_subject = payload.subject or record.get("draft_subject", f"Re: {record['subject']}")

    # Track how much staff edited the AI draft (for learning metrics)
    diff_chars = abs(len(final_body) - len(original_body))

    # Get original message ID for threading (In-Reply-To header)
    in_reply_to = record.get("message_id")

    success = send_reply_smtp(
        to=record["from_email"],
        subject=final_subject,
        body=final_body,
        in_reply_to_message_id=in_reply_to,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email via IONOS SMTP")

    await update_email_status(
        email_id, "sent", approved_by=payload.approved_by
    )
    await add_audit_log(
        email_record_id=email_id,
        action="approved_and_sent",
        performed_by=payload.approved_by,
        notes="Sent with edits" if payload.body else "Sent without edits",
        diff_chars=diff_chars,
    )

    return {"status": "sent", "email_id": email_id}


@router.post("/{email_id}/reject")
async def reject_email(
    email_id: int,
    payload: RejectPayload,
    _: str = Depends(verify_api_key),
):
    record = await get_email_by_id(email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")

    await update_email_status(
        email_id, "rejected", rejection_reason=payload.reason
    )
    await add_audit_log(
        email_record_id=email_id,
        action="rejected",
        performed_by=payload.rejected_by,
        notes=payload.reason,
    )
    return {"status": "rejected", "email_id": email_id}


@router.post("/{email_id}/escalate")
async def escalate_email(
    email_id: int,
    payload: EscalatePayload,
    _: str = Depends(verify_api_key),
):
    record = await get_email_by_id(email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")

    await update_email_status(email_id, "escalated")
    await add_audit_log(
        email_record_id=email_id,
        action="escalated",
        performed_by=payload.escalated_by,
        notes=payload.reason,
    )

    # Notify manager
    send_escalation_email(
        to="manager@das-elb.de",
        original_subject=record["subject"],
        from_email=record["from_email"],
        escalation_reason=payload.reason,
        record_id=email_id,
    )

    return {"status": "escalated", "email_id": email_id}


@router.post("/import-all")
async def import_all(
    background_tasks: BackgroundTasks,
    max_results: int = Query(500, le=2000),
    since_days: int = Query(180, ge=1, le=3650),
    _: str = Depends(verify_api_key),
):
    """
    Import emails from INBOX + all subfolders into the DB.
    Runs as a background task to avoid Render's 30s HTTP timeout.
    Already-processed emails are skipped by message_id deduplication.
    since_days: only import emails from the last N days (default 180 = 6 months).
    """
    background_tasks.add_task(import_all_existing_emails, max_results=max_results, since_days=since_days)
    return {"status": "import_started", "since_days": since_days, "max_results": max_results}


@router.post("/trigger-poll")
async def trigger_poll(
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
):
    """Manually trigger one email poll cycle (runs in background — check DB for results)."""
    background_tasks.add_task(poll_and_process)
    return {"status": "poll_triggered", "message": "Polling IONOS inbox in background — check DB in ~30s"}


@router.post("/{email_id}/retry")
async def retry_email(
    email_id: int,
    _: str = Depends(verify_api_key),
):
    """
    Re-run the AI pipeline on an email that failed or has no draft.
    Updates the same record in-place so the frontend can keep polling by the same ID.
    Works for status: failed, draft_created (no body), no_reply_needed.
    Returns immediately with {"status": "processing"} — frontend polls GET /{id} for result.
    """
    record = await get_email_by_id(email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")
    if record["status"] == "sent":
        raise HTTPException(status_code=400, detail="Cannot retry an already-sent email")

    # Mark as processing so frontend knows pipeline is running
    await update_email_record_fields(email_id, {
        "status": "failed",  # temporary — pipeline will update to draft_created or no_reply_needed
        "draft_body": None,
        "draft_subject": None,
    })

    # Collect email data to re-process
    email_data = {
        "message_id": record["message_id"] + "_retry",  # bypass dedup check
        "thread_id": record.get("thread_id"),
        "from_email": record["from_email"],
        "from_name": record.get("from_name"),
        "subject": record["subject"],
        "body": record["body"],
        "received_at": record.get("received_at"),
        "_update_id": email_id,  # signal orchestrator to update existing record
    }

    # Fire pipeline in background — returns immediately, frontend polls
    import asyncio
    async def _run_pipeline():
        try:
            await process_email(email_data)
        except Exception as e:
            logger.error(f"Background retry pipeline failed for email {email_id}: {e}", exc_info=True)
            # Mark as failed so frontend stops polling
            try:
                await update_email_record_fields(email_id, {"status": "failed"})
            except Exception:
                pass

    asyncio.ensure_future(_run_pipeline())

    return {"status": "processing", "email_id": email_id}


@router.get("/debug/test-imap")
async def test_imap(_: str = Depends(verify_api_key)):
    """Debug: test IONOS IMAP connectivity and count emails since last 7 days."""
    try:
        from app.email.imap_client import fetch_unread_emails_imap
        emails = fetch_unread_emails_imap(max_results=5, since_days=7)
        return {
            "status": "ok",
            "emails_found": len(emails),
            "subjects": [e.get("subject", "?")[:50] for e in emails],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/debug/test-pipeline")
async def test_pipeline(
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
):
    """Debug: run one test email through the full OpenAI pipeline as a background task."""
    test_email = {
        "message_id": f"test-openai-pipeline-{__import__('time').time():.0f}",
        "from_email": "test@example.com",
        "from_name": "Test Guest",
        "subject": "Zimmeranfrage Test",
        "body": "Guten Tag, ich möchte gerne ein Zimmer für 2 Nächte buchen. Haben Sie Verfügbarkeit?",
        "received_at": None,
        "thread_id": None,
    }

    async def _run():
        try:
            result = await process_email(test_email)
            logger.info(f"Test pipeline OK: intent={result.get('intent')}, status={result.get('status')}")
        except Exception as e:
            logger.error(f"Test pipeline FAILED: {e}", exc_info=True)

    background_tasks.add_task(_run)
    return {"status": "pipeline_started", "message_id": test_email["message_id"], "note": "Check DB in 60s for the result"}
