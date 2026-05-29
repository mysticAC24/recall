import asyncio
import sys
import traceback
from app.database import async_session
from app.models import Event

async def test_db():
    try:
        async with async_session() as session:
            event = Event(
                name="Test API",
                drive_folder_id="1234",
                status="pending",
            )
            session.add(event)
            await session.commit()
            print("Successfully inserted event!")
    except Exception as e:
        print("Exception occurred:")
        traceback.print_exc()

asyncio.run(test_db())
