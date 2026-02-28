from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.database import Base

BERLIN = ZoneInfo("Europe/Berlin")

def now_berlin() -> datetime:
    return datetime.now(tz=BERLIN).replace(tzinfo=None)


class EmailRecord(Base):
    __tablename__ = "email_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    thread_id = Column(String(255), index=True)
    from_email = Column(String(255))
    from_name = Column(String(255))
    subject = Column(Text)
    body = Column(Text)
    received_at = Column(DateTime(timezone=True))
    processed_at = Column(DateTime(timezone=True), default=now_berlin)

    # Agent 1 outputs
    intent = Column(String(100))
    secondary_intent = Column(String(100))
    confidence = Column(Float)
    language = Column(String(10))
    urgency = Column(String(20))

    # Agent 2 output
    entities = Column(JSON)

    # Agent 3 output
    policy = Column(JSON)

    # Agent 5 output
    risk = Column(JSON)
    risk_score = Column(Float, default=0.0)

    # Agent 4 output (draft)
    draft_subject = Column(Text)
    draft_body = Column(Text)
    draft_id = Column(String(255))

    # Workflow state
    # draft_created | approved | sent | rejected | escalated | failed
    status = Column(String(50), default="draft_created")
    approved_by = Column(String(100))
    approved_at = Column(DateTime(timezone=True))
    sent_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)
    requires_manager_approval = Column(Boolean, default=False)

    # Revenue tracking
    revenue_attributed = Column(Float, default=0.0)
    booking_reference = Column(String(100))

    # Prompt version for A/B testing
    prompt_version = Column(String(20), default="v1")

    audit_logs = relationship("AuditLog", back_populates="email_record")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_record_id = Column(Integer, ForeignKey("email_records.id"), index=True)
    action = Column(String(100))  # approved | rejected | escalated | edited | sent
    performed_by = Column(String(100))
    timestamp = Column(DateTime(timezone=True), default=now_berlin)
    notes = Column(Text)
    diff_chars = Column(Integer)  # how many chars changed from AI draft

    email_record = relationship("EmailRecord", back_populates="audit_logs")


class VIPGuest(Base):
    """Registry of known VIP guests for pre-pipeline cross-check."""

    __tablename__ = "vip_guests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    company = Column(String(255))
    tier = Column(String(50))  # gold | platinum | press | corporate
    notes = Column(Text)
    added_at = Column(DateTime(timezone=True), default=now_berlin)


class StyleProfile(Base):
    """
    Learned writing style extracted from the hotel's Sent Items folder.
    Updated weekly via the style sync job. Injected into Agent 4 system prompt.
    """

    __tablename__ = "style_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    learned_at = Column(DateTime(timezone=True), default=now_berlin)
    emails_analyzed = Column(Integer, default=0)
    profile_json = Column(JSON)       # full extracted profile dict
    injected_prompt = Column(Text)    # formatted prompt injection for Agent 4
