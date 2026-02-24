import asyncio
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.db.database import engine

async def migrate():
    print("Running custom migration script...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE email_records ADD COLUMN thread_id VARCHAR(255)"))
            print("Successfully added thread_id column to email_records")
        except OperationalError as e:
            print("Column thread_id already exists or another error occurred:", e)

if __name__ == "__main__":
    asyncio.run(migrate())
