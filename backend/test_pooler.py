import asyncio
import sys
import traceback
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

async def try_connect(name, engine):
    print(f"\n--- Testing: {name} ---")
    try:
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            print(f"SUCCESS: {name}")
    except Exception as e:
        print(f"FAILED: {name}")
        print(e)
    finally:
        await engine.dispose()

async def main():
    e1 = create_async_engine(settings.database_url, connect_args={"statement_cache_size": 0})
    await try_connect("connect_args={'statement_cache_size': 0}", e1)

    e2 = create_async_engine(settings.database_url, connect_args={"prepared_statement_cache_size": 0})
    await try_connect("connect_args={'prepared_statement_cache_size': 0}", e2)

    e3 = create_async_engine(settings.database_url, connect_args={"prepared_statement_name_cache_size": 0})
    await try_connect("connect_args={'prepared_statement_name_cache_size': 0}", e3)
    
    e4 = create_async_engine(settings.database_url, connect_args={"server_settings": {"statement_cache_size": "0"}})
    await try_connect("connect_args={'server_settings': {'statement_cache_size': '0'}}", e4)

asyncio.run(main())
