from aiogram import Router, types
from aiogram.filters import Command

from bot.services.sheets import get_sheets

router = Router()


@router.message(Command("report"))
async def cmd_report(message: types.Message):
    sheets = get_sheets()
    text = message.text.removeprefix("/report").strip()
    if not text:
        await message.answer("Формат: /report текст")
        return

    admins = sheets.get_admins()
    if not admins:
        await message.answer("Сейчас нет доступного начальства.")
        return

    sender = message.from_user
    username = sender.username or f"id{sender.id}"

    sent_to = 0
    for admin in admins:
        try:
            await message.bot.send_message(
                int(admin["tg_id"]),
                f"✉ Сообщение от @{username}:\n\n{text}",
            )
            sent_to += 1
        except Exception:
            pass

    if sent_to:
        await message.answer("Сообщение отправлено начальству.")
    else:
        await message.answer("Не удалось доставить сообщение начальству.")
