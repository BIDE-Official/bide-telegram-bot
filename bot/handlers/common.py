import os

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import get_build_date
from bot.services.sheets import get_sheets
from bot.services.elo import predict as elo_predict
from bot.keyboards import (
    main_keyboard,
    opponent_keyboard,
    history_menu_keyboard,
    admin_menu_keyboard,
    member_list_keyboard,
    approve_member_keyboard,
    history_pagination_keyboard,
    back_button,
)
from bot.handlers.game import GameFSM
from bot.handlers.history import _build_page
from bot.handlers.admin import show_pending

router = Router()


BIDE_MD_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "BIDE.md")


async def _send_bide_md(message: types.Message) -> None:
    try:
        doc = FSInputFile(BIDE_MD_PATH)
        await message.answer_document(doc, caption="Устав федерации BIDE")
    except FileNotFoundError:
        await message.answer("Устав федерации временно недоступен.")


async def _send_bide_by_cid(cid: int, bot) -> None:
    try:
        doc = FSInputFile(BIDE_MD_PATH)
        await bot.send_document(cid, doc, caption="Устав федерации BIDE")
    except FileNotFoundError:
        await bot.send_message(cid, "Устав федерации временно недоступен.")


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    sheets = get_sheets()
    uid = message.from_user.id
    username = message.from_user.username or ""

    member = sheets.get_member(uid)
    if member:
        is_admin = sheets.is_admin(uid)
        await message.answer("С возвращением!", reply_markup=main_keyboard(is_admin))
        return

    fixed = sheets.update_member_tg_id(username, uid)
    if fixed:
        is_admin = sheets.is_admin(uid)
        await message.answer(
            "Добро пожаловать в BIDE! Твой рейтинг активирован, "
            "теперь доступны все команды.",
            reply_markup=main_keyboard(is_admin),
        )
        await _send_bide_md(message)
        return

    text = (
            "Добро пожаловать в BIDE — Backgammon International Dice Experts.\n\n"
        "Доступные команды: /help"
    )
    await message.answer(text)
    await _send_bide_md(message)


@router.message(Command("rules"))
async def cmd_rules(message: types.Message):
    await _send_bide_md(message)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Доступные команды:\n\n"
        "/start — приветствие\n"
        "/rules — устав федерации\n"
        "/rating — общий рейтинг\n"
        "/rating @user — рейтинг игрока\n"
        "/history — все игры\n"
        "/history @user — игры игрока\n"
        "/predict @user — прогноз рейтинга\n"
        "/game — добавить результат игры\n"
        "/invite @user — пригласить нового игрока\n"
        "/report текст — связаться с начальством\n"
        "/cancel — отменить текущее действие\n"
        "/help — эта справка"
    )


@router.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Нет активного действия.")
        return
    await state.clear()
    await message.answer("Действие отменено.")


@router.callback_query(F.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    await callback.answer()


# ── Helpers ──────────────────────────────────────────────────────

async def _nav_main(cid: int, bot, uid: int):
    """Render main navigation message."""
    sheets = get_sheets()
    kb = InlineKeyboardBuilder()
    kb.button(text="🆕 Игра", callback_data="nav:game")
    kb.button(text="📊 Рейтинг", callback_data="nav:rating")
    kb.button(text="📜 История", callback_data="nav:history")
    kb.button(text="📈 Прогноз", callback_data="nav:predict")
    kb.button(text="👥 Пригласить", callback_data="nav:invite")
    kb.button(text="✉ Начальству", callback_data="nav:report")
    kb.button(text="📜 Устав", callback_data="nav:rules")
    kb.adjust(1)
    await bot.send_message(cid, "Главное меню:", reply_markup=kb.as_markup())


async def _nav_rating(cid: int, bot, uid: int, msg_id: int, action: str = "", arg: str = ""):
    sheets = get_sheets()
    text = _format_rating(sheets)
    kb = back_button("main")
    await bot.edit_message_text(text=text, chat_id=cid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)


async def _nav_history(cid: int, bot, uid: int, msg_id: int, action: str = "", arg: str = ""):
    sheets = get_sheets()
    if action == "all":
        text, total = _build_page(sheets.get_games()[::-1], 1)
        kb = history_pagination_keyboard(1, total, "", "history")
        await bot.edit_message_text(text=text, chat_id=cid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)
    elif action == "me":
        me = sheets.get_member(uid)
        if not me:
            await bot.edit_message_text(text="Ты не в федерации.", chat_id=cid, message_id=msg_id)
            return
        await _nav_history_user(cid, bot, uid, msg_id, me["username"])
    elif action == "user" and arg:
        await _nav_history_user(cid, bot, uid, msg_id, arg)
    elif action == "user":
        members = sheets.get_members()
        candidates = [(int(m["tg_id"]), m["username"]) for m in members]
        kb = member_list_keyboard("nhistory", candidates, uid)
        back = back_button("history")
        final = kb.inline_keyboard + back.inline_keyboard
        kb = types.InlineKeyboardMarkup(inline_keyboard=final)
        await bot.edit_message_text(text="Выбери игрока:", chat_id=cid, message_id=msg_id, reply_markup=kb)
    else:
        await bot.edit_message_text(text="История:", chat_id=cid, message_id=msg_id, reply_markup=history_menu_keyboard())


async def _nav_history_user(cid: int, bot, uid: int, msg_id: int, username: str):
    sheets = get_sheets()
    all_games = sheets.get_games()[::-1]
    user = sheets.get_user_by_username(username)
    if not user:
        await bot.edit_message_text(text=f"Участник @{username} не найден.", chat_id=cid, message_id=msg_id)
        return
    filtered = [g for g in all_games if g["p1_id"] == user["tg_id"] or g["p2_id"] == user["tg_id"]]
    text, total = _build_page(filtered, 1, username)
    kb = history_pagination_keyboard(1, total, username, "history")
    await bot.edit_message_text(text=text, chat_id=cid, message_id=msg_id, parse_mode="HTML", reply_markup=kb)


async def _nav_predict(cid: int, bot, uid: int, msg_id: int, target_username: str = ""):
    sheets = get_sheets()
    if target_username:
        sender = sheets.get_member(uid)
        opponent = sheets.get_user_by_username(target_username)
        if not sender or not opponent:
            await bot.edit_message_text(text="Ошибка.", chat_id=cid, message_id=msg_id)
            return
        ra, rb = int(sender["rating"]), int(opponent["rating"])
        p = elo_predict(ra, rb)
        su = sender["username"] or f"id{uid}"
        ou = opponent["username"]
        text = (
            f"<b>@{su}</b> ({ra}) vs <b>@{ou}</b> ({rb})\n\n"
            f"🏆 Победа: <code>+{p['win']}</code>\n"
            f"🔥 Марс: <code>+{p['mars']}</code>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"😢 Поражение: <code>{p['loss']}</code>\n"
            f"😞 Марс: <code>{p['loss_mars']}</code>"
        )
        await bot.edit_message_text(text=text, chat_id=cid, message_id=msg_id, parse_mode="HTML", reply_markup=back_button("predict"))
    else:
        members = sheets.get_members()
        sender = sheets.get_member(uid)
        if not sender:
            await bot.edit_message_text(text="Ты не в федерации.", chat_id=cid, message_id=msg_id)
            return
        candidates = [(int(m["tg_id"]), m["username"]) for m in members if int(m["tg_id"]) != uid]
        if not candidates:
            await bot.edit_message_text(text="Нет других участников.", chat_id=cid, message_id=msg_id)
            return
        kb = member_list_keyboard("npredict", candidates)
        back = back_button("main")
        final = kb.inline_keyboard + back.inline_keyboard
        kb = types.InlineKeyboardMarkup(inline_keyboard=final)
        await bot.edit_message_text(text="Выбери соперника для прогноза:", chat_id=cid, message_id=msg_id, reply_markup=kb)


async def _nav_admin(cid: int, bot, uid: int, msg_id: int, action: str = ""):
    sheets = get_sheets()
    if not sheets.is_admin(uid):
        await bot.edit_message_text(text="Ты не начальство.", chat_id=cid, message_id=msg_id)
        return
    if action == "pending":
        await bot.delete_message(cid, msg_id)
        await show_pending(cid, bot, sheets, True)
    elif action == "remove":
        members = sheets.get_members()
        b = InlineKeyboardBuilder()
        for m in members:
            b.button(text=f"@{m['username']}", callback_data=f"nremove:{m['username']}")
        b.adjust(2)
        back = back_button("admin")
        final = b.as_markup().inline_keyboard + back.inline_keyboard
        kb = types.InlineKeyboardMarkup(inline_keyboard=final)
        await bot.edit_message_text(text="Выбери игрока для удаления:", chat_id=cid, message_id=msg_id, reply_markup=kb)
    elif action == "send":
        members = sheets.get_members()
        candidates = [(int(m["tg_id"]), m["username"]) for m in members]
        kb = member_list_keyboard("nsend", candidates)
        b = InlineKeyboardBuilder()
        b.button(text="📢 Отправить всем", callback_data="nsend:all")
        back = back_button("admin")
        final = kb.inline_keyboard + b.as_markup().inline_keyboard + back.inline_keyboard
        kb_with_all = types.InlineKeyboardMarkup(inline_keyboard=final)
        await bot.edit_message_text(text="Выбери получателя:", chat_id=cid, message_id=msg_id, reply_markup=kb_with_all)
    else:
        await bot.edit_message_text(text=f"Кабинет начальства:\n🛠 {get_build_date()}", chat_id=cid, message_id=msg_id, reply_markup=admin_menu_keyboard())


def _format_rating(sheets, username: str = "") -> str:
    if username:
        m = sheets.get_user_by_username(username)
        if not m:
            return f"Участник @{username} не найден."
        return f'@{m["username"]} — {m["rating"]}'
    members = sheets.get_members()
    if not members:
        return "В федерации пока нет участников."
    members.sort(key=lambda x: int(x["rating"]), reverse=True)
    lines = ["<b>Рейтинг BIDE</b>\n"]
    for i, m in enumerate(members, 1):
        lines.append(f'{i}. @{m["username"]} — {m["rating"]}')
    return "\n".join(lines)


# ── Main menu handlers (reply keyboard) ───────────────────────────

@router.message(F.text == "📋 Меню")
async def menu_open(message: types.Message):
    await _nav_main(message.chat.id, message.bot, message.from_user.id)


@router.message(F.text == "🔧 Кабинет начальства")
async def menu_admin_cabinet(message: types.Message):
    sheets = get_sheets()
    if not sheets.is_admin(message.from_user.id):
        await message.answer("Ты не начальство.")
        return
    await message.answer(f"Кабинет начальства:\n🛠 {get_build_date()}", reply_markup=admin_menu_keyboard())


class InviteFSM(StatesGroup):
    waiting_username = State()


@router.message(InviteFSM.waiting_username, F.text)
async def invite_username(message: types.Message, state: FSMContext):
    raw = message.text.strip().lstrip("@")
    if not raw or raw.startswith("/"):
        return
    sheets = get_sheets()
    existing = sheets.get_user_by_username(raw)
    if existing:
        await message.answer(f"@{raw} уже в федерации.")
        await state.clear()
        return
    sheets.add_pending_member("0", raw, str(message.from_user.id))
    await message.answer(f"Запрос на добавление @{raw} отправлен начальству.")
    pm = sheets.get_pending_members("pending")
    last_id = int(pm[-1]["id"]) if pm else 1
    admins = sheets.get_admins()
    for admin in admins:
        try:
            await message.bot.send_message(
                int(admin["tg_id"]),
                f"Новый запрос на вступление: @{raw}",
                reply_markup=approve_member_keyboard(last_id),
            )
        except Exception:
            pass
    await state.clear()


class ReportFSM(StatesGroup):
    waiting_text = State()


@router.message(ReportFSM.waiting_text, F.text)
async def report_text(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text or text.startswith("/"):
        return
    sheets = get_sheets()
    await message.answer("Сообщение отправлено начальству.")
    admins = sheets.get_admins()
    for admin in admins:
        try:
            await message.bot.send_message(
                int(admin["tg_id"]),
                f"✉ Сообщение от @{message.from_user.username or message.from_user.id}:\n\n{text}",
            )
        except Exception:
            pass
    await state.clear()


# ── Navigation callbacks ──────────────────────────────────────────

async def _start_game(cid: int, bot, uid: int, state: FSMContext):
    sheets = get_sheets()
    sender = sheets.get_member(uid)
    if not sender:
        await bot.send_message(cid, "Ты не зарегистрирован в федерации.")
        return
    members = sheets.get_members()
    candidates = [(int(m["tg_id"]), m["username"]) for m in members if int(m["tg_id"]) != uid]
    if not candidates:
        await bot.send_message(cid, "Нет других участников для игры.")
        return
    await state.update_data(winner_id=uid)
    await state.set_state(GameFSM.choosing_opponent)
    kb = opponent_keyboard(candidates, uid)
    back = back_button("main")
    final = kb.inline_keyboard + back.inline_keyboard
    kb = types.InlineKeyboardMarkup(inline_keyboard=final)
    await bot.send_message(cid, "Выбери соперника:", reply_markup=kb)


async def _start_invite(cid: int, bot, uid: int, state: FSMContext):
    sheets = get_sheets()
    sender = sheets.get_member(uid)
    if not sender:
        await bot.send_message(cid, "Ты не зарегистрирован в федерации.")
        return
    await state.set_state(InviteFSM.waiting_username)
    await bot.send_message(cid, "Напиши @username нового игрока:")


async def _start_report(cid: int, bot, uid: int, state: FSMContext):
    sheets = get_sheets()
    member = sheets.get_member(uid)
    if not member:
        await bot.send_message(cid, "Ты не зарегистрирован в федерации.")
        return
    await state.set_state(ReportFSM.waiting_text)
    await bot.send_message(cid, "Напиши сообщение для начальства:")


@router.callback_query(F.data.startswith("nav:"))
async def nav_callback(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    screen = parts[1] if len(parts) > 1 else ""
    action = parts[2] if len(parts) > 2 else ""
    arg = parts[3] if len(parts) > 3 else ""

    uid = callback.from_user.id
    cid = callback.message.chat.id
    bot = callback.bot
    mid = callback.message.message_id

    if screen == "main":
        await state.clear()
        await callback.message.delete()
        await _nav_main(cid, bot, uid)
    elif screen == "game":
        await callback.message.delete()
        await _start_game(cid, bot, uid, state)
    elif screen == "invite":
        await callback.message.delete()
        await _start_invite(cid, bot, uid, state)
    elif screen == "report":
        await callback.message.delete()
        await _start_report(cid, bot, uid, state)
    elif screen == "rules":
        await callback.answer()
        await _send_bide_by_cid(cid, bot)
        return
    elif screen == "rating":
        await _nav_rating(cid, bot, uid, mid, action, arg)
    elif screen == "history":
        await _nav_history(cid, bot, uid, mid, action, arg)
    elif screen == "predict":
        await _nav_predict(cid, bot, uid, mid, action)
    elif screen == "admin":
        await _nav_admin(cid, bot, uid, mid, action)

    await callback.answer()


@router.callback_query(F.data.startswith("hhist:"))
async def nav_history_pagination(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    if parts[1] == "page":
        page = int(parts[2])
        username = ""
    else:
        username = parts[1]
        page = int(parts[3])
    sheets = get_sheets()
    all_games = sheets.get_games()[::-1]
    if username:
        user = sheets.get_user_by_username(username)
        if user:
            all_games = [g for g in all_games if g["p1_id"] == user["tg_id"] or g["p2_id"] == user["tg_id"]]
    text, total = _build_page(all_games, page, username)
    kb = history_pagination_keyboard(page, total, username, "history")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("nhistory:"))
async def nav_history_user(callback: types.CallbackQuery):
    _, tg_id = callback.data.split(":")
    sheets = get_sheets()
    m = sheets.get_member(int(tg_id))
    if m:
        await _nav_history(callback.message.chat.id, callback.bot, callback.from_user.id,
                           callback.message.message_id, "user", m["username"])
    await callback.answer()


@router.callback_query(F.data.startswith("npredict:"))
async def nav_predict_user(callback: types.CallbackQuery):
    _, tg_id = callback.data.split(":")
    sheets = get_sheets()
    opp = sheets.get_member(int(tg_id))
    if opp:
        await _nav_predict(callback.message.chat.id, callback.bot, callback.from_user.id,
                           callback.message.message_id, opp["username"])
    await callback.answer()


@router.callback_query(F.data.startswith("nremove:"))
async def nav_remove_user(callback: types.CallbackQuery):
    _, username = callback.data.split(":", 1)
    sheets = get_sheets()
    m = sheets.get_user_by_username(username)
    if m:
        sheets.remove_member(int(m["tg_id"]))
        await callback.message.edit_text(f"@{username} удалён из федерации.")
        await callback.message.answer("Главное меню:", reply_markup=main_keyboard(sheets.is_admin(callback.from_user.id)))
    await callback.answer()


class SendFSM(StatesGroup):
    waiting_text = State()


@router.callback_query(F.data.startswith("nsend:"))
async def nav_send_user(callback: types.CallbackQuery, state: FSMContext):
    _, target = callback.data.split(":")
    await state.update_data(send_target=target)
    await state.set_state(SendFSM.waiting_text)
    label = "всем" if target == "all" else "выбранному пользователю"
    await callback.message.edit_text(f"Напиши текст сообщения (будет отправлено {label}):")
    await callback.answer()


@router.message(SendFSM.waiting_text, F.text)
async def nav_send_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target = data["send_target"]
    text = message.text.strip()
    if not text or text.startswith("/"):
        return
    sheets = get_sheets()
    if target == "all":
        members = sheets.get_members()
        sent = 0
        failed = 0
        for m in members:
            try:
                await message.bot.send_message(int(m["tg_id"]), f"📢 Рассылка от начальства:\n\n{text}")
                sent += 1
            except Exception:
                failed += 1
        await message.answer(f"Сообщение отправлено {sent} участникам{' (' + str(failed) + ' ошибок)' if failed else ''}.")
    else:
        m = sheets.get_member(int(target))
        if m:
            try:
                await message.bot.send_message(int(m["tg_id"]), f"✉ Сообщение от начальства:\n\n{text}")

                admins = sheets.get_admins()
                sender_name = message.from_user.username or f"id{message.from_user.id}"
                log = f"📋 @{sender_name} → @{m['username']}:\n\n{text}"
                for admin in admins:
                    try:
                        await message.bot.send_message(int(admin["tg_id"]), log)
                    except Exception:
                        pass

                await message.answer(f"Сообщение отправлено @{m['username']}.")
            except Exception:
                await message.answer(f"Не удалось отправить @{m['username']}.")
    await state.clear()
