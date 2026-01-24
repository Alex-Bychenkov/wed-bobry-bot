import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from db import init_db
from handlers import router
from scheduler import setup_scheduler


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Начать / показать кнопки"),
        BotCommand(command="status", description="Текущий список"),
        BotCommand(command="reset", description="Сбросить сессию (админ)"),
        BotCommand(command="close", description="Закрыть сессию (админ)"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    await set_commands(bot)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
