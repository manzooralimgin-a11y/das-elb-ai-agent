from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


_MIGRATIONS = [
    # (table, column, column_type)
    ("email_records", "thread_id",               "VARCHAR(255)"),
    ("email_records", "secondary_intent",         "VARCHAR(100)"),
    ("email_records", "risk_score",               "FLOAT DEFAULT 0.0"),
    ("email_records", "requires_manager_approval","BOOLEAN DEFAULT FALSE"),
    ("email_records", "revenue_attributed",        "FLOAT DEFAULT 0.0"),
    ("email_records", "booking_reference",         "VARCHAR(100)"),
    ("email_records", "prompt_version",            "VARCHAR(20) DEFAULT 'v1'"),
    ("audit_logs",    "diff_chars",               "INTEGER"),
]


async def init_db():
    from app.db import models  # noqa: F401 — ensure models are registered
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Run idempotent column migrations (each in its own transaction)
    for table, column, col_type in _MIGRATIONS:
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )
        except Exception:
            pass  # Column already exists — safe to ignore


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

