"""
Pipeline Orchestrator
Runs all 5 agents in the optimal order (parallel where possible)
and saves results to the database.

Execution order:
  Stage 1 (parallel): Agent 1 (Intent) + Agent 2 (Entities) + Agent 5 (Risk)
  Stage 2 (sequential): Agent 3 (Policy) — needs Agent 2 output + live API
  Stage 3 (sequential): Agent 4 (Response) — needs all above
  Stage 4: Save draft to DB (staff approves via dashboard → IONOS SMTP send)
  Stage 5: Save full record to DB, send notifications if needed
"""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

BERLIN = ZoneInfo("Europe/Berlin")

def now_berlin() -> datetime:
    return datetime.now(tz=BERLIN)

from app.agents.intent_classifier import classify_intent
from app.agents.entity_extractor import extract_entities
from app.agents.policy_validator import validate_policy
from app.agents.response_writer import write_response
from app.agents.risk_analyzer import analyze_risk
from app.integrations.notifications import notify_staff_if_needed
from app.db.crud import save_email_record, is_vip_guest, get_latest_style_profile

logger = logging.getLogger(__name__)

# Gemini API calls are synchronous — run in thread pool
# Keep max_workers low to avoid overwhelming Gemini rate limits during bulk import
_executor = ThreadPoolExecutor(max_workers=3)


def _run_in_thread(func, *args):
    """Run a synchronous function in the thread pool executor."""
    loop = asyncio.get_running_loop()  # must use get_running_loop() inside async context
    return loop.run_in_executor(_executor, func, *args)


async def process_email(email_data: dict) -> dict:
    """
    Full multi-agent pipeline for a single incoming email.
    Returns the full record dict saved to DB.
    If email_data contains '_update_id', updates that existing record instead of inserting.
    """
    email_id = email_data["message_id"]
    update_id = email_data.get("_update_id")  # existing DB row id to update in-place
    subject = email_data.get("subject", "(no subject)")
    raw_body = email_data.get("body", "")
    body = _clean_body(raw_body)   # strip HTML, truncate to 4000 chars for all agents
    from_email = email_data.get("from_email", "")

    logger.info(f"Processing email [{email_id}]: {subject[:60]}")

    try:
        # ── Stage 1: Run Agents 1, 2, and 5 in PARALLEL ──────────────────
        # Claude SDK is synchronous; use thread pool so all 3 run concurrently
        intent_future = _run_in_thread(classify_intent, subject, body)
        entity_future = _run_in_thread(extract_entities, subject, body, "unknown")
        risk_future = _run_in_thread(analyze_risk, subject, body, "unknown", None)
        vip_future = asyncio.ensure_future(is_vip_guest(from_email))

        intent_result, entities_result, risk_result, vip_info = await asyncio.gather(
            intent_future,
            entity_future,
            risk_future,
            vip_future,
        )

        intent = intent_result.get("primary_intent", "other")
        language = intent_result.get("language", "de")
        estimated_revenue = entities_result.get("estimated_revenue")

        logger.info(
            f"Intent={intent} lang={language} confidence={intent_result.get('confidence')}"
        )

        # ── No-Reply Detection ────────────────────────────────────────────
        # Check if this email doesn't need a reply at all
        style_profile = await get_latest_style_profile()
        if _is_no_reply_needed(intent_result, risk_result, email_data, style_profile):
            logger.info(f"Email [{email_id}] classified as no_reply_needed — skipping draft generation")
            record_data = {
                "message_id": email_id,
                "thread_id": email_data.get("thread_id"),
                "from_email": from_email,
                "from_name": email_data.get("from_name"),
                "subject": subject,
                "body": raw_body,  # store original, not truncated
                "received_at": _parse_date(email_data.get("received_at")),
                "processed_at": now_berlin(),
                "intent": intent,
                "confidence": intent_result.get("confidence"),
                "language": language,
                "risk": risk_result,
                "risk_score": float(risk_result.get("overall_risk_score", 0.0)),
                "status": "no_reply_needed",
                "revenue_attributed": 0.0,
            }
            await save_email_record(record_data, update_id=update_id)
            return record_data

        # ── Stage 2: Policy Validator (needs entities + live API) ─────────
        policy_result = await _run_in_thread(validate_policy, entities_result, intent)

        # ── Stage 3: Response Writer (needs all above) ────────────────────
        style_injection = style_profile.get("injected_prompt", "") if style_profile else ""
        response_result = await _run_in_thread(
            write_response,
            subject,
            body,
            intent,
            entities_result,
            policy_result,
            risk_result,
            language,
            vip_info,
            style_injection,
        )

        # ── Stage 4: Draft is stored in DB (no external draft service) ──────
        # Staff reviews and approves via dashboard → IONOS SMTP sends the reply.
        draft_subject = response_result.get("subject", f"Re: {subject}")
        draft_body = response_result.get("body_text", "")

        # ── Stage 5: Save to DB ───────────────────────────────────────────
        record_data = {
            "message_id": email_id,
            "thread_id": email_data.get("thread_id"),
            "from_email": from_email,
            "from_name": email_data.get("from_name"),
            "subject": subject,
            "body": raw_body,  # store original, not truncated
            "received_at": _parse_date(email_data.get("received_at")),
            "processed_at": now_berlin(),
            "intent": intent,
            "secondary_intent": intent_result.get("secondary_intent"),
            "confidence": intent_result.get("confidence"),
            "language": language,
            "urgency": intent_result.get("urgency"),
            "entities": entities_result,
            "policy": policy_result,
            "risk": risk_result,
            "risk_score": float(risk_result.get("overall_risk_score", 0.0)),
            "draft_subject": draft_subject,
            "draft_body": draft_body,
            "draft_id": None,  # No external draft — stored in DB, sent via IONOS SMTP on approval
            "status": "draft_created",
            "requires_manager_approval": policy_result.get(
                "requires_manager_approval", False
            ),
            "revenue_attributed": float(estimated_revenue or 0.0),
        }

        record = await save_email_record(record_data, update_id=update_id)

        # ── Stage 5b: Notify staff if needed ─────────────────────────────
        await notify_staff_if_needed(
            risk_result=risk_result,
            policy_result=policy_result,
            email_subject=subject,
            from_email=from_email,
            record_id=record.id if hasattr(record, "id") else None,
        )

        logger.info(
            f"Email [{email_id}] processed. Draft saved to DB. "
            f"Priority: {risk_result.get('recommended_priority')}"
        )
        return record_data

    except Exception as e:
        logger.error(f"Pipeline error for [{email_id}]: {e}", exc_info=True)
        # Save a failed record so it shows up in the dashboard
        try:
            await save_email_record(
                {
                    "message_id": email_id,
                    "thread_id": email_data.get("thread_id"),
                    "from_email": from_email,
                    "from_name": email_data.get("from_name"),
                    "subject": subject,
                    "body": raw_body,
                    "received_at": _parse_date(email_data.get("received_at")),
                    "processed_at": now_berlin(),
                    "status": "failed",
                },
                update_id=update_id,
            )
        except Exception:
            pass
        raise


def _is_no_reply_needed(
    intent_result: dict,
    risk_result: dict,
    email_data: dict,
    style_profile: Optional[dict] = None,
) -> bool:
    """
    Determines if an email does NOT need an AI reply.
    Conservative — when in doubt, generate a reply (draft_created).
    Only skips truly automated/system messages, not real guest emails.
    """
    subject = (email_data.get("subject") or "").lower()
    from_email = (email_data.get("from_email") or "").lower()
    body_raw = (email_data.get("body") or "")
    body = body_raw.lower()[:2000]  # only check first 2000 chars

    # 1. Email sent FROM the hotel itself — don't reply to ourselves
    hotel_senders = ["rezeption@das-elb.de", "info@das-elb.de", "das-elb.de"]
    for hs in hotel_senders:
        if from_email.endswith(hs) or from_email == hs:
            return True

    # 2. Hard no-reply sender addresses (exact noreply patterns only)
    no_reply_sender_patterns = [
        "noreply@", "no-reply@", "donotreply@", "do-not-reply@",
        "mailer-daemon@", "postmaster@",
    ]
    for pattern in no_reply_sender_patterns:
        if from_email.startswith(pattern) or f"<{pattern}" in from_email:
            return True

    # 3. Known automated booking system senders (not guests)
    automated_senders = [
        "dirs21.de", "booking.com", "expedia.com", "hotels.com",
        "airbnb.com", "trivago.com", "hrs.com", "hrs.de",
        "newsletter.", "versandbestaetigung@", "amazon.de",
        "ionos-online-marketing", "bueromarkt", "paypal",
    ]
    for pattern in automated_senders:
        if pattern in from_email:
            return True

    # 4. Unambiguous auto-reply subject lines (exact phrases only)
    auto_subject_patterns = [
        "automatische antwort", "auto-reply", "out of office",
        "abwesenheitsnotiz", "außer haus", "nicht im büro",
        "unsubscribe", "delivery failure", "undelivered",
        "unzustellbar", "mailer-daemon",
    ]
    for pattern in auto_subject_patterns:
        if pattern in subject:
            return True

    # 5. Unambiguous automated body markers
    auto_body_markers = [
        "diese e-mail wurde automatisch generiert",
        "diese nachricht wurde automatisch",
        "this is an automated message",
        "this email was sent automatically",
        "do not reply to this email",
        "bitte nicht auf diese e-mail antworten",
    ]
    for marker in auto_body_markers:
        if marker in body:
            return True

    # 6. AI explicitly flagged as automated AND it's truly a system message intent
    if risk_result.get("is_automated_message") and intent_result.get("primary_intent") == "other":
        return True

    # 7. Learned patterns from style profile
    if style_profile and style_profile.get("profile_json"):
        profile = style_profile["profile_json"]
        learned_senders = profile.get("no_reply_sender_patterns", [])
        for sender_pat in learned_senders:
            if sender_pat.lower() in from_email:
                return True

    return False


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def _clean_body(body: str, max_chars: int = 4000) -> str:
    """
    Strip HTML tags and truncate email body before sending to Gemini.
    Many booking confirmation emails are full HTML pages (50k+ chars) that
    blow the token budget. Strip tags first, then cap at max_chars.
    """
    import re as _re
    if not body:
        return ""
    # Strip HTML tags
    text = _re.sub(r"<[^>]+>", " ", body)
    # Collapse whitespace
    text = _re.sub(r"[ \t]+", " ", text)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    return text
