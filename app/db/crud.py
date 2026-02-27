from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List
from app.db.database import AsyncSessionLocal
from app.db.models import EmailRecord, AuditLog, VIPGuest, StyleProfile

BERLIN = ZoneInfo("Europe/Berlin")

def now_berlin() -> datetime:
    return datetime.now(tz=BERLIN)


async def is_email_already_processed(message_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(EmailRecord.id).where(EmailRecord.message_id == message_id)
        )
        return result.scalar() is not None


async def delete_email_record(email_id: int) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(EmailRecord).where(EmailRecord.id == email_id)
        )
        await session.commit()


async def update_email_record_fields(email_id: int, fields: dict) -> None:
    """Update specific fields of an email record by ID."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(EmailRecord).where(EmailRecord.id == email_id).values(**fields)
        )
        await session.commit()


async def save_email_record(data: dict, update_id: int = None) -> EmailRecord:
    """
    Save a new email record, or update an existing one if update_id is provided.
    When update_id is set, updates ALL pipeline output fields on the existing row.
    """
    # Strip internal-only keys not in the DB model
    db_data = {k: v for k, v in data.items() if not k.startswith("_")}

    if update_id is not None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(EmailRecord).where(EmailRecord.id == update_id).values(**db_data)
            )
            await session.commit()
            result = await session.execute(
                select(EmailRecord).where(EmailRecord.id == update_id)
            )
            return result.scalar_one()
    else:
        async with AsyncSessionLocal() as session:
            record = EmailRecord(**db_data)
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record


async def get_all_emails(
    status: str = None,
    intent: str = None,
    limit: int = 50,
    offset: int = 0,
) -> List[dict]:
    async with AsyncSessionLocal() as session:
        # Sort by received_at (actual email date) newest first; fall back to processed_at
        query = select(EmailRecord).order_by(
            EmailRecord.received_at.desc().nulls_last(),
            EmailRecord.processed_at.desc(),
        )
        if status:
            query = query.where(EmailRecord.status == status)
        if intent:
            query = query.where(EmailRecord.intent == intent)
        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        records = result.scalars().all()
        return [_record_to_dict(r) for r in records]


async def get_email_by_id(email_id: int) -> Optional[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(EmailRecord).where(EmailRecord.id == email_id)
        )
        record = result.scalar_one_or_none()
        return _record_to_dict(record) if record else None


async def update_email_status(
    email_id: int,
    status: str,
    approved_by: str = None,
    rejection_reason: str = None,
) -> None:
    async with AsyncSessionLocal() as session:
        values = {"status": status}
        if status == "sent":
            values["sent_at"] = now_berlin()
            if approved_by:
                values["approved_by"] = approved_by
                values["approved_at"] = now_berlin()
        elif status == "rejected" and rejection_reason:
            values["rejection_reason"] = rejection_reason

        await session.execute(
            update(EmailRecord).where(EmailRecord.id == email_id).values(**values)
        )
        await session.commit()


async def add_audit_log(
    email_record_id: int,
    action: str,
    performed_by: str,
    notes: str = None,
    diff_chars: int = None,
) -> None:
    async with AsyncSessionLocal() as session:
        log = AuditLog(
            email_record_id=email_record_id,
            action=action,
            performed_by=performed_by,
            notes=notes,
            diff_chars=diff_chars,
        )
        session.add(log)
        await session.commit()


async def is_vip_guest(email: str) -> Optional[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(VIPGuest).where(VIPGuest.email == email.lower())
        )
        vip = result.scalar_one_or_none()
        return {"name": vip.name, "tier": vip.tier, "company": vip.company} if vip else None


async def get_analytics_summary() -> dict:
    async with AsyncSessionLocal() as session:
        from sqlalchemy import func

        total = await session.scalar(select(func.count(EmailRecord.id))) or 0
        pending = await session.scalar(
            select(func.count(EmailRecord.id)).where(
                EmailRecord.status == "draft_created"
            )
        ) or 0
        sent_today_count = await session.scalar(
            select(func.count(EmailRecord.id)).where(
                EmailRecord.status == "sent",
                EmailRecord.sent_at >= now_berlin().replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            )
        ) or 0
        try:
            avg_confidence = await session.scalar(
                select(func.avg(EmailRecord.confidence))
            )
        except Exception:
            avg_confidence = None
        try:
            total_revenue = await session.scalar(
                select(func.sum(EmailRecord.revenue_attributed))
            )
        except Exception:
            total_revenue = None
        return {
            "total_emails": total,
            "pending_review": pending,
            "sent_today": sent_today_count,
            "avg_confidence": round(avg_confidence or 0, 3),
            "total_revenue_attributed": round(total_revenue or 0, 2),
        }


async def save_style_profile(emails_analyzed: int, profile_json: dict, injected_prompt: str) -> None:
    async with AsyncSessionLocal() as session:
        profile = StyleProfile(
            learned_at=now_berlin(),
            emails_analyzed=emails_analyzed,
            profile_json=profile_json,
            injected_prompt=injected_prompt,
        )
        session.add(profile)
        await session.commit()


async def get_latest_style_profile() -> Optional[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(StyleProfile).order_by(StyleProfile.learned_at.desc()).limit(1)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None
        return {
            "id": profile.id,
            "learned_at": profile.learned_at.isoformat(),
            "emails_analyzed": profile.emails_analyzed,
            "profile_json": profile.profile_json,
            "injected_prompt": profile.injected_prompt,
        }


def _record_to_dict(record: EmailRecord) -> dict:
    return {
        "id": record.id,
        "message_id": record.message_id,
        "thread_id": record.thread_id,
        "from_email": record.from_email,
        "from_name": record.from_name,
        "subject": record.subject,
        "body": record.body,
        "received_at": record.received_at.isoformat() if record.received_at else None,
        "processed_at": record.processed_at.isoformat() if record.processed_at else None,
        "intent": record.intent,
        "secondary_intent": record.secondary_intent,
        "confidence": record.confidence,
        "language": record.language,
        "urgency": record.urgency,
        "entities": record.entities,
        "policy": record.policy,
        "risk": record.risk,
        "risk_score": record.risk_score,
        "draft_subject": record.draft_subject,
        "draft_body": record.draft_body,
        "draft_id": record.draft_id,
        "status": record.status,
        "approved_by": record.approved_by,
        "approved_at": record.approved_at.isoformat() if record.approved_at else None,
        "sent_at": record.sent_at.isoformat() if record.sent_at else None,
        "rejection_reason": record.rejection_reason,
        "requires_manager_approval": record.requires_manager_approval,
        "revenue_attributed": record.revenue_attributed,
        "booking_reference": record.booking_reference,
    }
