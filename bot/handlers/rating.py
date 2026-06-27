from aiogram import Router, types
from aiogram.filters import Command

from bot.services.sheets import get_sheets
from bot.services.elo import predict

router = Router()


async def show_rating(chat_id: int, bot, sheets, username: str = ""):
    answer = lambda text, **kw: bot.send_message(chat_id, text, **kw)

    if username:
        member = sheets.get_user_by_username(username)
        if not member:
            await answer(f"Участник @{username} не найден.")
            return
        await answer(f'@{member["username"]} — {member["rating"]}')
        return

    members = sheets.get_members()
    if not members:
        await answer("В федерации пока нет участников.")
        return

    members.sort(key=lambda m: int(m["rating"]), reverse=True)

    lines = ["<b>Рейтинг BIDE</b>\n"]
    for i, m in enumerate(members, 1):
        lines.append(f'{i}. @{m["username"]} — {m["rating"]}')

    await answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sheets = get_sheets()
    args = message.text.strip().split(maxsplit=1)
    username = args[1].lstrip("@") if len(args) > 1 else ""
    await show_rating(message.chat.id, message.bot, sheets, username)


async def show_predict(chat_id: int, bot, sheets, from_user_id: int, username: str):
    answer = lambda text, **kw: bot.send_message(chat_id, text, **kw)

    if not username:
        await answer("Укажи соперника: /predict @username")
        return

    sender = sheets.get_member(from_user_id)
    if not sender:
        await answer("Ты не зарегистрирован в федерации.")
        return

    opponent = sheets.get_user_by_username(username)
    if not opponent:
        await answer(f"Участник @{username} не найден.")
        return

    rating_a = int(sender["rating"])
    rating_b = int(opponent["rating"])
    p = predict(rating_a, rating_b)
    opp_uname = opponent["username"]
    sender_uname = sender["username"] or f"id{sender['tg_id']}"
    await answer(
        f"@{sender_uname} ({rating_a}) vs @{opp_uname} ({rating_b})\n\n"
        f"Победа:        +{p['win']}\n"
        f"Марс:          +{p['mars']}\n"
        f"Поражение:     {p['loss']}\n"
        f"Поражение марс: {p['loss_mars']}"
    )


@router.message(Command("predict"))
async def cmd_predict(message: types.Message):
    sheets = get_sheets()
    args = message.text.strip().split(maxsplit=1)
    username = args[1].lstrip("@") if len(args) > 1 else ""
    await show_predict(message.chat.id, message.bot, sheets, message.from_user.id, username)
