import asyncio
import logging

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.config import Settings
from app.db import Database
from app.handlers.main import router


async def main():
    load_dotenv()
    settings = Settings.from_env()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    db = Database(settings.db_path)
    await db.init()

    bot = Bot(settings.bot_token)
    dp = Dispatcher()

    dp["db"] = db
    dp["settings"] = settings
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
