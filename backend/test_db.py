import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from sqlalchemy import text

settings = get_settings()

async def test_db():
    try:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT count(*) FROM events"))
            count = result.scalar()
            print(f"Events table exists, row count: {count}")
    except Exception as e:
        print(f"DB Error: {e}")

asyncio.run(test_db())
