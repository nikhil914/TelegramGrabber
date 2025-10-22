import os
from dotenv import load_dotenv
from telethon import TelegramClient
from config import SESSION_NAME
import asyncio

load_dotenv()
TELEGRAM_API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

async def test():
    client = TelegramClient(SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.connect()
    
    chat = await client.get_entity('shadowslave6')
    async for msg in client.iter_messages(chat, limit=100):
        if msg.reply_markup:
            print("Found Message ID:", msg.id)
            print("Text:", msg.text)
            for row in getattr(msg.reply_markup, 'rows', []):
                for btn in getattr(row, 'buttons', []):
                    print("  Button Type:", type(btn), "Data:", btn.to_dict())
            break
            
    await client.disconnect()

asyncio.run(test())
