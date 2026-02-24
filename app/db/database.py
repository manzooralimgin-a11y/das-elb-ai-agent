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


async def init_db():
    from app.db import models  # noqa: F401 — ensure models are registered
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Force migration for missing thread_id column in existing SQLite databases
        try:
            await conn.execute(text("ALTER TABLE email_records ADD COLUMN thread_id VARCHAR(255)"))
        except (OperationalError, Exception):
            pass  # Column already exists (ProgrammingError in asyncpg/Postgres)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
