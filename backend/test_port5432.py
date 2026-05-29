import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

url = "postgresql+asyncpg://postgres.ychzhhvimbyezqlhrkpw:segdyd-fibMu4-feqgyn@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

async def main():
    engine = create_async_engine(url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
        print("SUCCESS ON PORT 5432!")
    await engine.dispose()

asyncio.run(main())
