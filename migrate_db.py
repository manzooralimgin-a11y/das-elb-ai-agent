import asyncio
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from app.db.database import engine

# All columns that were added after initial schema creation.
# Each is wrapped individually so an already-existing column is silently skipped.
MIGRATIONS = [
    ("email_records", "thread_id",              "VARCHAR(255)"),
    ("email_records", "secondary_intent",        "VARCHAR(100)"),
    ("email_records", "risk_score",              "FLOAT DEFAULT 0.0"),
    ("email_records", "requires_manager_approval","BOOLEAN DEFAULT FALSE"),
    ("email_records", "revenue_attributed",       "FLOAT DEFAULT 0.0"),
    ("email_records", "booking_reference",        "VARCHAR(100)"),
    ("email_records", "prompt_version",           "VARCHAR(20) DEFAULT 'v1'"),
    ("audit_logs",    "diff_chars",              "INTEGER"),
]

async def migrate():
    print("Running custom migration script...")
    async with engine.begin() as conn:
        for table, column, col_type in MIGRATIONS:
            try:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )
                print(f"  ✓ Added {table}.{column}")
            except (OperationalError, ProgrammingError):
                print(f"  ~ {table}.{column} already exists (skipping)")

if __name__ == "__main__":
    asyncio.run(migrate())

