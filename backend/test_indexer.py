import asyncio
import uuid
import traceback
from app.services.indexer import index_event
from app.models import Event
from app.database import async_session
from app.services.drive import drive_service

async def main():
    try:
        drive_service.build_service()
        # Create a mock event
        async with async_session() as session:
            event = Event(
                name="Test Event",
                drive_folder_id="1WFKb-lQ94tXL80l9x3q0uVOw7e01Bikq",
                status="pending"
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            event_id = event.id
        
        print(f"Testing index_event for {event_id}...")
        await index_event(event_id, "1WFKb-lQ94tXL80l9x3q0uVOw7e01Bikq")
        print("index_event completed")
    except Exception:
        traceback.print_exc()

asyncio.run(main())
