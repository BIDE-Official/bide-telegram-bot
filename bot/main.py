import asyncio
import logging

from bot.config import BOT_TOKEN
from bot.dispatcher import dp
from bot.services.sheets import get_sheets
from bot.handlers import common, rating, history, game, members, admin, report

logging.basicConfig(level=logging.INFO)

dp.include_routers(
    common.router,
    rating.router,
    history.router,
    game.router,
    members.router,
    admin.router,
    report.router,
)


async def on_startup():
    get_sheets()


async def main():
    dp.startup.register(on_startup)

    from aiogram import Bot
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
