from aiogram import Router, types
from aiogram.filters import Command

from bot.services.sheets import get_sheets
from bot.keyboards import approve_member_keyboard

router = Router()


@router.message(Command("invite"))
async def cmd_invite(message: types.Message):
    sheets = get_sheets()

    sender = sheets.get_member(message.from_user.id)
    if not sender:
        await message.answer("Ты не зарегистрирован в федерации.")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /invite @username")
        return

    raw_username = parts[1].lstrip("@")

    existing = sheets.get_user_by_username(raw_username)
    if existing:
        await message.answer(f"@{raw_username} уже в федерации.")
        return

    member_id = sheets.add_pending_member("0", raw_username, str(message.from_user.id))

    await message.answer(f"Запрос на добавление @{raw_username} отправлен начальству.")

    admins = sheets.get_admins()
    for admin in admins:
        try:
            await message.bot.send_message(
                int(admin["tg_id"]),
                f"Новый запрос на вступление: @{raw_username}\n"
                f"Пригласил: @{message.from_user.username or message.from_user.id}",
                reply_markup=approve_member_keyboard(member_id),
            )
        except Exception:
            pass
