"""
Email poller: APScheduler async job that polls IONOS IMAP every N seconds
and runs each new email through the multi-agent pipeline.

Connection: exchange.ionos.com:993 SSL/TLS (info@das-elb.de — IONOS Exchange account)
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.email.imap_client import fetch_unread_emails_imap, fetch_all_emails_imap
from app.pipeline.orchestrator import process_email
from app.db.crud import is_email_already_processed

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def poll_and_process():
    """
    Fetch unread emails from IONOS IMAP and run each through the pipeline.
    max_instances=1 ensures polling jobs never overlap.
    """
    logger.info(f"Polling IONOS inbox ({settings.HOTEL_EMAIL})...")
    try:
        emails = fetch_unread_emails_imap(max_results=10)
        if not emails:
            logger.debug("No new emails found.")
            return

        logger.info(f"Found {len(emails)} new email(s)")
        for email_data in emails:
            if await is_email_already_processed(email_data["message_id"]):
                logger.debug(f"Skipping already-processed: {email_data['message_id']}")
                continue
            try:
                await process_email(email_data)
            except Exception as e:
                logger.error(
                    f"Pipeline failed for {email_data['message_id']}: {e}",
                    exc_info=True,
                )

    except Exception as e:
        logger.error(f"Polling cycle error: {e}", exc_info=True)


async def import_all_existing_emails(max_results: int = 500, since_days: int = 180) -> dict:
    """
    One-time import: fetch ALL emails from INBOX + subfolders and run through pipeline.
    Uses SINCE date filter to limit to last `since_days` days (default: 6 months).
    Folders: INBOX, INBOX/Archiv, INBOX/KS, INBOX/Bagusch intern das ELB Haus.
    Already-processed emails are skipped via message_id deduplication.
    Returns counts of imported and skipped.
    """
    logger.info(f"Starting full multi-folder import (max {max_results}/folder, last {since_days} days)...")
    imported = 0
    skipped = 0
    failed = 0
    total_found = 0

    try:
        emails = fetch_all_emails_imap(max_per_folder=max_results, since_days=since_days)
        total_found = len(emails)
        logger.info(f"Full import: found {total_found} total emails across all folders")

        for email_data in emails:
            if await is_email_already_processed(email_data["message_id"]):
                skipped += 1
                continue
            try:
                await process_email(email_data)
                imported += 1
            except Exception as e:
                logger.error(
                    f"Pipeline failed for {email_data['message_id']}: {e}",
                    exc_info=True,
                )
                failed += 1

    except Exception as e:
        logger.error(f"Full import error: {e}", exc_info=True)

    logger.info(f"Full import complete: {imported} imported, {skipped} skipped, {failed} failed out of {total_found} found")
    return {"imported": imported, "skipped": skipped, "failed": failed, "total_found": total_found}


def start_scheduler():
    scheduler.add_job(
        poll_and_process,
        trigger="interval",
        seconds=settings.POLL_INTERVAL_SECONDS,
        id="email_poller",
        max_instances=1,
        misfire_grace_time=30,
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"IONOS email poller started. "
        f"Inbox: {settings.HOTEL_EMAIL} | "
        f"Interval: {settings.POLL_INTERVAL_SECONDS}s"
    )
