from telethon.sync import TelegramClient
from telethon.tl.types import Document
from config import API_ID, API_HASH

async def main():
    async with TelegramClient("user_session", API_ID, API_HASH) as client:
        try:
            # Получи документ вручную из Forward сообщения
            msg = await client.get_messages("stickers", limit=1)
            if not msg:
                print("❌ Не найдено сообщений со стикерами")
                return
                
            doc = msg[0].media.document
            if not doc:
                print("❌ Не найден документ в сообщении")
                return

            file_ref = doc.file_reference
            sticker_data = {
                "emoji": doc.attributes[1].alt,
                "document": {
                    "_": "InputDocument",
                    "id": doc.id,
                    "access_hash": doc.access_hash,
                    "file_reference": file_ref.hex()
                }
            }

            import json
            with open("sticker_data.json", "w") as f:
                json.dump(sticker_data, f, indent=2)

            print("✅ Стикер сохранён.")
        except Exception as e:
            print(f"❌ Ошибка при сохранении стикера: {e}")

import asyncio
asyncio.run(main())
