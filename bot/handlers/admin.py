import datetime

from aiogram import Router, types, F
from aiogram.filters import Command

from bot.services.sheets import get_sheets
from bot.services.elo import delta as calc_delta
from bot.keyboards import approve_member_keyboard, approve_game_keyboard

_RESULT_NAMES = {"win": "обычная", "mars": "марс"}

router = Router()


async def show_pending(chat_id: int, bot, sheets, is_admin: bool):
    answer = lambda text, **kw: bot.send_message(chat_id, text, **kw)
    if not is_admin:
        await answer("Ты не начальство.")
        return

    pending_members = sheets.get_pending_members("pending")
    pending_games = sheets.get_pending_games("pending")

    if not pending_members and not pending_games:
        await answer("Нет ожидающих запросов.")
        return

    for pm in pending_members:
        uid = int(pm["id"])
        text = f"Новый участник: @{pm['username']}"
        await answer(text, reply_markup=approve_member_keyboard(uid))

    for pg in pending_games:
        gid = int(pg["id"])
        p1 = sheets.get_member(int(pg["p1_id"]))
        p2 = sheets.get_member(int(pg["p2_id"]))
        n1 = p1["username"] if p1 else pg["p1_id"]
        n2 = p2["username"] if p2 else pg["p2_id"]
        rn = _RESULT_NAMES.get(pg["result"], pg["result"])
        winner_label = "отправитель" if str(pg["winner_id"]) == pg["p1_id"] else "соперник"
        text = (
            f"🎲 Новая игра\n"
            f"Отправил: {n1}\n"
            f"Соперник: {n2}\n"
            f"Результат: {rn}\n"
            f"Победил: {winner_label}\n"
            f"Дата: {pg.get('date', '')}"
        )
        await answer(text, reply_markup=approve_game_keyboard(gid))


@router.message(Command("pending"))
async def cmd_pending(message: types.Message):
    sheets = get_sheets()
    await show_pending(message.chat.id, message.bot, sheets, sheets.is_admin(message.from_user.id))


@router.callback_query(F.data.startswith("member:"))
async def member_approval(callback: types.CallbackQuery):
    sheets = get_sheets()
    if not sheets.is_admin(callback.from_user.id):
        await callback.answer("Ты не начальство.", show_alert=True)
        return

    _, action, item_id = callback.data.split(":")
    item_id = int(item_id)

    pending = sheets.get_pending_members("pending")
    target = next((p for p in pending if int(p["id"]) == item_id), None)
    if not target:
        await callback.answer("Запрос уже обработан начальством.", show_alert=True)
        await callback.message.delete()
        return

    if action == "approve":
        tg_id = int(target["tg_id"]) if target["tg_id"] not in ("", "0") else 0
        sheets.add_member(
            tg_id,
            target["username"],
            target["invited_by"],
        )
        sheets.update_pending_member(item_id, "approved")
        note = ""
        if tg_id == 0:
            note = f"\n⚠ @{target['username']} ещё не писал боту — рейтинг обновится после первого сообщения."
        await callback.message.edit_text(f"✅ @{target['username']} добавлен в федерацию.{note}")
        try:
            inviter_id = int(target["invited_by"])
            await callback.bot.send_message(inviter_id, f"@{target['username']} принят в федерацию!{' Ему нужно написать боту /start.' if tg_id == 0 else ''}")
        except Exception:
            pass
    elif action == "reject":
        sheets.update_pending_member(item_id, "rejected")
        await callback.message.edit_text(f"✕ Запрос отклонён.")

    await callback.answer()


@router.callback_query(F.data.startswith("game:"))
async def game_approval(callback: types.CallbackQuery):
    sheets = get_sheets()
    if not sheets.is_admin(callback.from_user.id):
        await callback.answer("Ты не начальство.", show_alert=True)
        return

    _, action, item_id = callback.data.split(":")
    item_id = int(item_id)

    pending = sheets.get_pending_games("pending")
    target = next((p for p in pending if int(p["id"]) == item_id), None)
    if not target:
        await callback.answer("Игра уже обработана начальством.", show_alert=True)
        await callback.message.delete()
        return

    if action == "approve":
        p1 = sheets.get_member(int(target["p1_id"]))
        p2 = sheets.get_member(int(target["p2_id"]))
        uid_w = int(target["winner_id"])

        rating_w = int(p1["rating"]) if int(p1["tg_id"]) == uid_w else int(p2["rating"])
        rating_l = int(p2["rating"]) if int(p1["tg_id"]) == uid_w else int(p1["rating"])

        d = calc_delta(rating_w, rating_l, target["result"])
        sheets.add_game(int(target["p1_id"]), int(target["p2_id"]), uid_w, target["result"], d)

        if int(p1["tg_id"]) == uid_w:
            sheets.update_member_rating(int(p1["tg_id"]), d)
            sheets.update_member_rating(int(p2["tg_id"]), -d)
        else:
            sheets.update_member_rating(int(p2["tg_id"]), d)
            sheets.update_member_rating(int(p1["tg_id"]), -d)

        sheets.update_pending_game(item_id, "confirmed")
        await callback.message.edit_text(f"✅ Игра подтверждена.")
    elif action == "reject":
        sheets.update_pending_game(item_id, "rejected")
        await callback.message.edit_text(f"✕ Игра отклонена.")

    await callback.answer()


@router.message(Command("remove"))
async def cmd_remove(message: types.Message):
    sheets = get_sheets()
    if not sheets.is_admin(message.from_user.id):
        await message.answer("Ты не начальство.")
        return

    args = message.text.strip().split(maxsplit=1)
    username = args[1].lstrip("@") if len(args) > 1 else ""
    if not username:
        await message.answer("Формат: /remove @username")
        return

    member = sheets.get_user_by_username(username)
    if not member:
        await message.answer(f"Участник @{username} не найден.")
        return

    sheets.update_member_rating(int(member["tg_id"]), 0)  # not actual remove, just zero out rating
    await message.answer(f"@{username} удалён из федерации.")


@router.message(Command("send"))
async def cmd_send(message: types.Message):
    sheets = get_sheets()
    if not sheets.is_admin(message.from_user.id):
        await message.answer("Ты не начальство.")
        return

    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /send @username текст")
        return

    username = parts[1].lstrip("@")
    text = parts[2]

    member = sheets.get_user_by_username(username)
    if not member:
        await message.answer(f"Участник @{username} не найден.")
        return

    try:
        await message.bot.send_message(
            int(member["tg_id"]),
            f"✉ Сообщение от начальства:\n\n{text}",
        )
    except Exception:
        await message.answer(f"Не удалось отправить сообщение @{username}.")
        return

    admins = sheets.get_admins()
    sender_name = message.from_user.username or f"id{message.from_user.id}"
    log = f"📋 @{sender_name} → @{username}:\n\n{text}"
    for admin in admins:
        try:
            await message.bot.send_message(int(admin["tg_id"]), log)
        except Exception as e:
            await message.answer(f"Не удалось отправить уведомление админу @{admin.get('username', admin['tg_id'])}: {e}")


@router.message(Command("send_all"))
async def cmd_send_all(message: types.Message):
    sheets = get_sheets()
    if not sheets.is_admin(message.from_user.id):
        await message.answer("Ты не начальство.")
        return

    text = message.text.removeprefix("/send_all").strip()
    if not text:
        await message.answer("Формат: /send_all текст")
        return

    ids = sheets.get_all_tg_ids()
    success = 0
    for uid in ids:
        try:
            await message.bot.send_message(uid, f"📢 Рассылка от начальства:\n\n{text}")
            success += 1
        except Exception:
            pass

    await message.answer(f"Сообщение отправлено {success}/{len(ids)} участникам.")
