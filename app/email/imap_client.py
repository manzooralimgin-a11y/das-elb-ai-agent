"""
IONOS Exchange IMAP/SMTP email client for Das ELB Hotel (info@das-elb.de).
- IMAP (read):  exchange.ionos.eu:993       SSL/TLS      ✅ confirmed working
- SMTP (send):  smtp.exchange.ionos.eu:587  STARTTLS    ✅ confirmed working

info@das-elb.de is a IONOS Microsoft Exchange account — NOT standard IONOS mail.
IMAP must be enabled first at: https://xadmin.exchange.ionos.com
  → Connectivity Settings → check IMAP → Apply → wait ~60 min.
"""
import email
import imaplib
import logging
import re
import smtplib
from datetime import datetime, timedelta
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


# ─── IMAP: Read incoming emails ──────────────────────────────────────────────

def fetch_unread_emails_imap(
    host: str = None,
    port: int = None,
    username: str = None,
    password: str = None,
    max_results: int = 20,
    since_days: int = 2,
) -> List[dict]:
    """
    Fetch recent emails from IONOS inbox using SINCE filter (last since_days days).
    Does NOT rely on UNSEEN flag — IONOS Exchange marks emails as read when opened
    in Outlook/webmail before the poller sees them, causing UNSEEN=0 false negatives.
    Deduplication is handled by the pipeline (is_email_already_processed check on message_id).
    """
    return _fetch_emails_imap(
        host=host, port=port, username=username, password=password,
        max_results=max_results, unseen_only=False, since_days=since_days,
    )


def fetch_all_emails_imap(
    host: str = None,
    port: int = None,
    username: str = None,
    password: str = None,
    max_per_folder: int = 500,
    since_days: int = 180,
    folders: Optional[List[str]] = None,
) -> List[dict]:
    """
    Fetch ALL emails from IONOS inbox + all relevant subfolders for initial import.
    Uses IMAP SINCE filter to limit to last `since_days` days (default: 6 months).
    Folders searched: INBOX, INBOX/Archiv, INBOX/KS, INBOX/Bagusch intern das ELB Haus.
    The pipeline's is_email_already_processed() deduplication prevents re-processing.
    """
    host = host or settings.IONOS_IMAP_HOST
    port = port or settings.IONOS_IMAP_PORT
    username = username or settings.HOTEL_EMAIL
    password = password or settings.IONOS_EMAIL_PASSWORD

    if folders is None:
        folders = [
            "INBOX",
            "INBOX/Archiv",
            "INBOX/KS",
            "INBOX/Bagusch intern das ELB Haus",
        ]

    all_emails: List[dict] = []

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(username, password)

        for folder in folders:
            folder_emails = _fetch_folder_emails(
                conn=conn,
                folder=folder,
                max_results=max_per_folder,
                since_days=since_days,
            )
            logger.info(f"Folder '{folder}': fetched {len(folder_emails)} email(s)")
            all_emails.extend(folder_emails)

        conn.logout()

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP auth/connection error for {username}: {e}")
    except Exception as e:
        logger.error(f"IMAP multi-folder error: {e}", exc_info=True)

    logger.info(f"Multi-folder import total: {len(all_emails)} email(s) from {len(folders)} folder(s)")
    return all_emails


def _fetch_folder_emails(
    conn: imaplib.IMAP4_SSL,
    folder: str,
    max_results: int = 500,
    since_days: int = 180,
) -> List[dict]:
    """
    Internal: fetch emails from a single IMAP folder using SINCE date filter.
    Returns list of email dicts. Does NOT close the connection.
    """
    emails = []
    since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")

    try:
        # Quote folder name if it contains spaces
        folder_name = f'"{folder}"' if " " in folder else folder
        status, _ = conn.select(folder_name, readonly=True)
        if status != "OK":
            logger.warning(f"Could not select folder '{folder}' (status={status}) — skipping")
            return []

        _, message_nums = conn.search(None, f"SINCE {since_date}")
        num_list = message_nums[0].split()
        if not num_list:
            return []

        # Take last max_results (most recent)
        num_list = num_list[-max_results:]

        for num in num_list:
            try:
                _, data = conn.fetch(num, "(RFC822)")
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = _decode_header_value(msg.get("Subject", ""))
                from_raw = _decode_header_value(msg.get("From", ""))
                body = _extract_body_imap(msg)

                emails.append(
                    {
                        "message_id": msg.get("Message-ID", str(num)).strip(),
                        "thread_id": msg.get("Thread-Index"),
                        "in_reply_to": msg.get("In-Reply-To"),
                        "from_email": _parse_email(from_raw),
                        "from_name": _parse_name(from_raw),
                        "subject": subject,
                        "body": body,
                        "received_at": msg.get("Date"),
                        "source_folder": folder,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to process IMAP message {num} in '{folder}': {e}")

    except Exception as e:
        logger.warning(f"Error fetching from folder '{folder}': {e}")

    return emails


def _fetch_emails_imap(
    host: str = None,
    port: int = None,
    username: str = None,
    password: str = None,
    max_results: int = 20,
    unseen_only: bool = False,
    since_days: int = 2,
) -> List[dict]:
    """
    Internal: fetch recent emails from INBOX via IMAP SSL (used by the live poller).
    Uses SINCE date filter instead of UNSEEN flag — more reliable since IONOS Exchange
    marks emails as read when opened in Outlook before the poller sees them.
    Deduplication is done by message_id in the pipeline, not by IMAP flags.
    """
    host = host or settings.IONOS_IMAP_HOST
    port = port or settings.IONOS_IMAP_PORT
    username = username or settings.HOTEL_EMAIL
    password = password or settings.IONOS_EMAIL_PASSWORD

    emails = []

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(username, password)
        conn.select("INBOX", readonly=True)  # readonly=True — no flag changes needed

        # Use SINCE filter — much more reliable than UNSEEN on Exchange
        since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        _, message_nums = conn.search(None, f"SINCE {since_date}")
        num_list = message_nums[0].split()
        if not num_list:
            conn.logout()
            return []

        # Take the last max_results (most recent first)
        num_list = num_list[-max_results:]

        for num in num_list:
            try:
                _, data = conn.fetch(num, "(RFC822)")
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = _decode_header_value(msg.get("Subject", ""))
                from_raw = _decode_header_value(msg.get("From", ""))
                body = _extract_body_imap(msg)

                emails.append(
                    {
                        "message_id": msg.get("Message-ID", str(num)).strip(),
                        "thread_id": msg.get("Thread-Index"),
                        "in_reply_to": msg.get("In-Reply-To"),
                        "from_email": _parse_email(from_raw),
                        "from_name": _parse_name(from_raw),
                        "subject": subject,
                        "body": body,
                        "received_at": msg.get("Date"),
                    }
                )

            except Exception as e:
                logger.error(f"Failed to process IMAP message {num}: {e}")

        conn.logout()
        logger.info(
            f"Fetched {len(emails)} email(s) from {username} (last {since_days} days)"
        )

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP auth/connection error for {username}: {e}")
    except Exception as e:
        logger.error(f"IMAP error: {e}", exc_info=True)

    return emails


# ─── SMTP: Send outgoing emails ───────────────────────────────────────────────

def send_reply_smtp(
    to: str,
    subject: str,
    body: str,
    in_reply_to_message_id: str = None,
) -> bool:
    """
    Send an email reply via IONOS Exchange SMTP (smtp.exchange.ionos.com:587 STARTTLS).
    Sets In-Reply-To and References headers if in_reply_to_message_id is provided
    so the reply appears as a thread in the guest's email client.
    Returns True on success, False on failure.
    """
    from_addr = settings.HOTEL_EMAIL
    password = settings.IONOS_EMAIL_PASSWORD

    if not password:
        logger.error("IONOS_EMAIL_PASSWORD is not set — cannot send email")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = from_addr
        msg["To"] = to
        msg["Subject"] = subject

        # Thread headers so reply appears correctly in guest's inbox
        if in_reply_to_message_id:
            msg["In-Reply-To"] = in_reply_to_message_id
            msg["References"] = in_reply_to_message_id

        msg.attach(MIMEText(body, "plain", "utf-8"))

        # IONOS Exchange uses STARTTLS on port 587 (not SSL on 465)
        with smtplib.SMTP(settings.IONOS_SMTP_HOST, settings.IONOS_SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(from_addr, password)
            server.sendmail(from_addr, [to], msg.as_string())

        logger.info(f"Email sent via IONOS Exchange SMTP → {to} | Subject: {subject[:60]}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed — check IONOS_EMAIL_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending to {to}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {to}: {e}", exc_info=True)
        return False


# ─── Private helpers ──────────────────────────────────────────────────────────

def _decode_header_value(value: str) -> str:
    """Decode RFC 2047 encoded email headers (handles UTF-8, latin-1, etc.)."""
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


def _extract_body_imap(msg: email.message.Message) -> str:
    """Recursively extract plain text body from an email message."""
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


def _parse_name(from_header: str) -> str:
    if "<" in from_header:
        return from_header.split("<")[0].strip().strip('"')
    return ""
