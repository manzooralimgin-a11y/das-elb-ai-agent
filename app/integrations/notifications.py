"""
Staff notification system.
Sends WhatsApp messages via Twilio when high-risk or high-value emails arrive.
Enabled only when ENABLE_WHATSAPP_NOTIFICATIONS=true and Twilio credentials are set.
"""
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def notify_staff_if_needed(
    risk_result: dict,
    policy_result: dict,
    email_subject: str,
    from_email: str,
    record_id: int = None,
) -> None:
    """
    Send WhatsApp alert to hotel manager if the email is flagged as:
    - notify_staff_immediately: true
    - requires_manager_approval: true (from policy)
    - critical priority
    """
    should_notify = (
        risk_result.get("notify_staff_immediately")
        or policy_result.get("requires_manager_approval")
        or risk_result.get("recommended_priority") == "urgent"
    )

    if not should_notify:
        return

    reason = risk_result.get("notification_reason") or policy_result.get(
        "manager_approval_reason", "High-priority email received"
    )
    priority = risk_result.get("recommended_priority", "high")
    revenue = risk_result.get("estimated_revenue_eur", 0)

    message = (
        f"🏨 Das ELB Hotel — AI Email Alert\n"
        f"Priority: {priority.upper()}\n"
        f"From: {from_email}\n"
        f"Subject: {email_subject[:80]}\n"
        f"Reason: {reason}\n"
        f"Est. Revenue: €{revenue:.0f}" if revenue else f"Reason: {reason}"
    )
    if record_id:
        message += f"\nDashboard: /emails/{record_id}"

    if not settings.ENABLE_WHATSAPP_NOTIFICATIONS:
        logger.info(f"[NOTIFICATION SUPPRESSED — WHATSAPP DISABLED] {message}")
        return

    _send_whatsapp(message)


def _send_whatsapp(message: str) -> None:
    """Send a WhatsApp message via Twilio."""
    if not all(
        [settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.MANAGER_WHATSAPP]
    ):
        logger.warning("Twilio credentials not fully configured — skipping WhatsApp alert")
        return

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=settings.MANAGER_WHATSAPP,
            body=message,
        )
        logger.info(f"WhatsApp alert sent to {settings.MANAGER_WHATSAPP}")
    except Exception as e:
        logger.error(f"WhatsApp notification failed: {e}")


def send_escalation_email(
    to: str,
    original_subject: str,
    from_email: str,
    escalation_reason: str,
    record_id: int = None,
) -> None:
    """Send escalation email to hotel manager via IONOS SMTP."""
    from app.email.imap_client import send_reply_smtp

    body = (
        f"Das ELB AI Email Agent — Escalation Notice\n\n"
        f"An incoming email requires your attention:\n\n"
        f"From: {from_email}\n"
        f"Subject: {original_subject}\n"
        f"Reason for escalation: {escalation_reason}\n"
    )
    if record_id:
        body += f"\nView in dashboard: /emails/{record_id}"

    send_reply_smtp(
        to=to,
        subject=f"[ESCALATION] {original_subject[:60]}",
        body=body,
    )
