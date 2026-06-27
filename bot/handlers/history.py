from aiogram import Router, types
from aiogram.filters import Command
from aiogram import F

from bot.services.sheets import get_sheets
from bot.keyboards import history_pagination_keyboard

router = Router()
PAGE_SIZE = 5


def _build_page(games: list[dict], page: int, username: str = "") -> tuple[str, int]:
    total = max((len(games) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = max(1, min(page, total))
    start = (page - 1) * PAGE_SIZE
    items = games[start:start + PAGE_SIZE]

    heading = f"<b>История @{username} (стр. {page}/{total})</b>" if username else f"<b>Все игры (стр. {page}/{total})</b>"
    lines = [heading, ""]

    for i, g in enumerate(items, start + 1):
        dt = g.get("date", "")[:10]
        pid1, pid2 = g["p1_id"], g["p2_id"]
        wid = g["winner_id"]
        res = g["result"]
        dlt = g["delta"]
        sheets = get_sheets()
        m1 = sheets.get_member(int(pid1))
        m2 = sheets.get_member(int(pid2))
        n1 = m1["username"] if m1 else pid1
        n2 = m2["username"] if m2 else pid2

        if int(wid) == int(pid1):
            lines.append(f"{i}. {dt} {n1} > {n2} — {res} (+{dlt})")
        else:
            lines.append(f"{i}. {dt} {n2} > {n1} — {res} (+{dlt})")

    return "\n".join(lines), total


async def show_history(chat_id: int, bot, sheets, username: str = ""):
    answer = lambda text, **kw: bot.send_message(chat_id, text, **kw)

    all_games = sheets.get_games()
    all_games.reverse()

    if username:
        user = sheets.get_user_by_username(username)
        if not user:
            await answer(f"Участник @{username} не найден.")
            return
        all_games = [g for g in all_games if g["p1_id"] == user["tg_id"] or g["p2_id"] == user["tg_id"]]

    text, total = _build_page(all_games, 1, username)
    await answer(text, parse_mode="HTML", reply_markup=history_pagination_keyboard(1, total, username))


@router.message(Command("history"))
async def cmd_history(message: types.Message):
    sheets = get_sheets()
    args = message.text.strip().split(maxsplit=1)
    username = args[1].lstrip("@") if len(args) > 1 else ""
    await show_history(message.chat.id, message.bot, sheets, username)


@router.callback_query(F.data.startswith("history"))
async def history_pagination(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    if parts[1] == "page":
        page = int(parts[2])
        username = ""
    else:
        username = parts[1]
        page = int(parts[3])

    sheets = get_sheets()

    all_games = sheets.get_games()
    all_games.reverse()

    if username:
        user = sheets.get_user_by_username(username)
        if user:
            uid = user["tg_id"]
            all_games = [g for g in all_games if g["p1_id"] == uid or g["p2_id"] == uid]

    text, total = _build_page(all_games, page, username)
    kb = history_pagination_keyboard(page, total, username)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()
