import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from db import init_db
from handlers import router
from metrics import set_bot_info, start_metrics_server
from scheduler import setup_scheduler


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Начать / показать кнопки"),
        BotCommand(command="status", description="Текущий список"),
        BotCommand(command="reset", description="Сбросить сессию (админ)"),
        BotCommand(command="close", description="Закрыть сессию (админ)"),
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Команды бота успешно установлены")
    except TelegramRetryAfter as e:
        logging.warning(f"Не удалось установить команды из-за flood control. Повтор через {e.retry_after} секунд. Бот продолжит работу.")
    except Exception as e:
        logging.error(f"Ошибка при установке команд: {e}. Бот продолжит работу.")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    
    # Start Prometheus metrics server
    try:
        logging.info("Attempting to start metrics server...")
        start_metrics_server(port=8000)
        logging.info("Metrics server started on port 8000")
    except Exception as e:
        logging.error(f"Failed to start metrics server: {e}", exc_info=True)
        raise
    
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    
    # Set bot info for metrics
    bot_info = await bot.get_me()
    set_bot_info(
        name=bot_info.full_name,
        username=bot_info.username or "",
        bot_id=bot_info.id
    )
    
    await set_commands(bot)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
