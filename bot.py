"""Main bot entry point."""
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
    """Set bot commands visible in Telegram UI."""
    commands = [
        BotCommand(command="start", description="Начать / показать кнопки"),
        BotCommand(command="status", description="Текущий список"),
        BotCommand(command="reset", description="Сбросить сессию (админ)"),
        BotCommand(command="close", description="Закрыть сессию (админ)"),
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Bot commands set successfully")
    except TelegramRetryAfter as e:
        logging.warning(
            f"Could not set commands due to flood control. Retry after {e.retry_after}s. Bot will continue."
        )
    except Exception as e:
        logging.error(f"Error setting commands: {e}. Bot will continue.")


async def main() -> None:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Start Prometheus metrics server
    try:
        logging.info("Starting metrics server...")
        start_metrics_server(port=8000)
        logging.info("Metrics server started on port 8000")
    except Exception as e:
        logging.error(f"Failed to start metrics server: {e}", exc_info=True)
        raise
    
    # Initialize database
    await init_db()
    
    # Create bot instance
    bot = Bot(token=BOT_TOKEN)
    
    # Set bot info for metrics
    bot_info = await bot.get_me()
    set_bot_info(
        name=bot_info.full_name,
        username=bot_info.username or "",
        bot_id=bot_info.id
    )
    
    # Set commands
    await set_commands(bot)
    
    # Create dispatcher
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    # Setup scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    
    logging.info("Bot starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
