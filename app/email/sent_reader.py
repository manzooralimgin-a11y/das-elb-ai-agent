"""
Reads the Sent Items folder from IONOS Exchange via IMAP.
Used by the Style Learning system to analyze how Das ELB staff actually write emails.
"""
import email
import imaplib
import logging
import re
from datetime import datetime, timedelta
from email.header import decode_header
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)

# IONOS Exchange (German locale) stores sent mail in "Gesendete Elemente"
# Fallback candidates in priority order
SENT_FOLDER_CANDIDATES = [
    '"Gesendete Elemente"',   # IONOS Exchange German locale ✅
    '"Sent Items"',           # IONOS Exchange English locale
    "Sent",                   # Standard IMAP
    '"INBOX/Sent"',
]


def fetch_sent_emails_imap(
    max_results: int = 50,
    since_days: int = 90,
    host: str = None,
    port: int = None,
    username: str = None,
    password: str = None,
) -> List[dict]:
    """
    Fetch recent emails from the Sent folder via IMAP.
    Auto-detects the correct folder name (handles German/English IONOS Exchange).
    Returns list of dicts with subject, body, to_email, date, in_reply_to.
    """
    host = host or settings.IONOS_IMAP_HOST
    port = port or settings.IONOS_IMAP_PORT
    username = username or settings.HOTEL_EMAIL
    password = password or settings.IONOS_EMAIL_PASSWORD

    sent_emails = []

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(username, password)

        # Try each candidate folder name until one works
        selected = False
        for candidate in SENT_FOLDER_CANDIDATES:
            status, _ = conn.select(candidate, readonly=True)
            if status == "OK":
                logger.info(f"Opened sent folder: {candidate}")
                selected = True
                break

        if not selected:
            # Last resort: scan folder list for anything with \Sent flag
            _, folders = conn.list()
            for folder_bytes in (folders or []):
                folder_str = folder_bytes.decode("utf-8", errors="replace")
                if "\\Sent" in folder_str:
                    # Extract folder name from: (\HasNoChildren \Sent) "/" "Gesendete Elemente"
                    parts = folder_str.split('"/"')
                    if len(parts) >= 2:
                        folder_name = parts[-1].strip().strip('"').strip()
                        quoted = f'"{folder_name}"'
                        status, _ = conn.select(quoted, readonly=True)
                        if status == "OK":
                            logger.info(f"Auto-detected sent folder: {quoted}")
                            selected = True
                            break

        if not selected:
            logger.error("Could not find Sent folder on IONOS IMAP")
            conn.logout()
            return []

        # Only fetch recent emails (last since_days days) for performance
        since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        _, message_nums = conn.search(None, f"SINCE {since_date}")
        num_list = message_nums[0].split()
        if not num_list:
            logger.info("No sent emails found in date range")
            conn.logout()
            return []

        # Take the most recent N emails (last items in the list)
        num_list = num_list[-max_results:]

        for num in reversed(num_list):  # newest first
            try:
                _, data = conn.fetch(num, "(RFC822)")
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = _decode_header_value(msg.get("Subject", ""))
                to_raw = _decode_header_value(msg.get("To", ""))
                body = _extract_body(msg)
                date_str = msg.get("Date", "")
                in_reply_to = msg.get("In-Reply-To", "")

                # Only include emails with a meaningful body (skip empty/image-only)
                if len(body.strip()) < 30:
                    continue

                sent_emails.append({
                    "subject": subject,
                    "body": body,
                    "to_email": _parse_email(to_raw),
                    "date": date_str,
                    "in_reply_to": in_reply_to,
                    "has_reply_to": bool(in_reply_to),
                })

            except Exception as e:
                logger.error(f"Error reading sent email {num}: {e}")

        conn.logout()
        logger.info(f"Fetched {len(sent_emails)} sent email(s) from '{username}' (last {since_days} days)")

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP auth/connection error reading Sent folder: {e}")
    except Exception as e:
        logger.error(f"Error reading Sent folder: {e}", exc_info=True)

    return sent_emails


def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded).strip()


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def _parse_email(from_header: str) -> str:
    match = re.search(r"<(.+?)>", from_header)
    return match.group(1).strip().lower() if match else from_header.strip().lower()
