import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from kopilka.config import load_settings
from kopilka.db import init_db
from kopilka.handlers.chat import router as chat_router
from kopilka.handlers.onboarding import router as onboarding_router

logger = logging.getLogger(__name__)

COMMANDS = (
    BotCommand(command="start", description="Начать или показать сводку"),
    BotCommand(command="help", description="Что я умею"),
    BotCommand(command="week", description="Остаток бюджета на неделю"),
    BotCommand(command="piggy", description="Виртуальная копилка"),
    BotCommand(command="expenses", description="Последние траты"),
    BotCommand(command="challenge", description="7 суток без категории"),
    BotCommand(command="digest", description="Дайджест подписок"),
    BotCommand(command="subs", description="Повторяющиеся списания"),
    BotCommand(command="cards", description="Карты и кэшбэк"),
    BotCommand(command="hint", description="Какой картой платить"),
)


async def run_bot(token: str) -> None:
    bot = Bot(token=token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(onboarding_router)
    dispatcher.include_router(chat_router)
    await bot.set_my_commands(list(COMMANDS))
    logger.info("Копилка слушает Telegram")
    await dispatcher.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    init_db(settings.database_url)
    asyncio.run(run_bot(settings.telegram_token))
