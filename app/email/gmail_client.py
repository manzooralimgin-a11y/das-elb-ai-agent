"""
Gmail API client for Das ELB Hotel email agent.
Handles reading unread emails, marking as read, and creating draft replies.
"""
import base64
import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://mail.google.com/"]


def _get_service():
    creds = Credentials(
        token=None,
        refresh_token=settings.GMAIL_REFRESH_TOKEN,
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def fetch_unread_emails(max_results: int = 20) -> list[dict]:
    """
    Fetch unread emails from the hotel inbox.
    Marks each email as read immediately to prevent double-processing.
    Returns a list of email dicts.
    """
    service = _get_service()
    result = (
        service.users()
        .messages()
        .list(userId="me", q="is:unread in:inbox", maxResults=max_results)
        .execute()
    )

    emails = []
    for meta in result.get("messages", []):
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=meta["id"], format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            body = _extract_body(msg["payload"])

            emails.append(
                {
                    "message_id": msg["id"],
                    "thread_id": msg.get("threadId"),
                    "from_email": _parse_email(headers.get("From", "")),
                    "from_name": _parse_name(headers.get("From", "")),
                    "subject": headers.get("Subject", "(no subject)"),
                    "body": body,
                    "received_at": headers.get("Date"),
                }
            )

            # Mark as read to prevent reprocessing
            service.users().messages().modify(
                userId="me",
                id=meta["id"],
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

        except Exception as e:
            logger.error(f"Failed to fetch email {meta['id']}: {e}")

    return emails


def create_draft(
    to: str, subject: str, body: str, thread_id: str = None
) -> str | None:
    """
    Save a reply as a Gmail draft (not sent).
    Returns the draft ID, or None on failure.
    """
    service = _get_service()
    try:
        message = MIMEMultipart("alternative")
        message["to"] = to
        message["from"] = settings.HOTEL_EMAIL
        message["subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft_body: dict = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        draft = (
            service.users().drafts().create(userId="me", body=draft_body).execute()
        )
        logger.info(f"Draft created: {draft['id']} → {to}")
        return draft["id"]
    except Exception as e:
        logger.error(f"Failed to create draft for {to}: {e}")
        return None


def send_draft(draft_id: str) -> bool:
    """Send an existing draft by its ID. Returns True on success."""
    service = _get_service()
    try:
        service.users().drafts().send(
            userId="me", body={"id": draft_id}
        ).execute()
        logger.info(f"Draft {draft_id} sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send draft {draft_id}: {e}")
        return False


def send_email(to: str, subject: str, body: str, thread_id: str = None) -> bool:
    """Directly send an email (bypasses draft stage). Use only for escalation notices."""
    service = _get_service()
    try:
        message = MIMEMultipart("alternative")
        message["to"] = to
        message["from"] = settings.HOTEL_EMAIL
        message["subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body_payload: dict = {"raw": raw}
        if thread_id:
            body_payload["threadId"] = thread_id

        service.users().messages().send(
            userId="me", body=body_payload
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return ""


def _parse_email(from_header: str) -> str:
    match = re.search(r"<(.+?)>", from_header)
    return match.group(1).lower() if match else from_header.strip().lower()


def _parse_name(from_header: str) -> str:
    if "<" in from_header:
        return from_header.split("<")[0].strip().strip('"')
    return ""
