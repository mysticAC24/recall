import asyncio
import traceback
from app.services.drive import drive_service, parse_folder_id

async def main():
    try:
        # Initialize the service first (normally done at app startup)
        drive_service.build_service()
        
        folder_id = parse_folder_id("https://drive.google.com/drive/folders/1WFKb-lQ94tXL80l9x3q0uVOw7e01Bikq?usp=sharing")
        print(f"Parsed folder ID: {folder_id}")
        
        loop = asyncio.get_running_loop()
        files = await loop.run_in_executor(None, drive_service.list_image_files, folder_id)
        print(f"Found {len(files)} files")
        for f in files[:5]:
            print(f"  - {f['name']} ({f['id']})")
    except Exception:
        traceback.print_exc()

asyncio.run(main())
