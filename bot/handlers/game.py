import datetime

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.sheets import get_sheets
from bot.keyboards import opponent_keyboard, winloss_keyboard, result_keyboard, approve_game_keyboard, back_button

_RESULT_NAMES = {"win": "обычная", "mars": "марс"}

router = Router()


class GameFSM(StatesGroup):
    choosing_opponent = State()
    choosing_winloss = State()
    choosing_result = State()


@router.message(Command("game"))
async def cmd_game(message: types.Message, state: FSMContext):
    sheets = get_sheets()
    sender = sheets.get_member(message.from_user.id)
    if not sender:
        await message.answer("Ты не зарегистрирован в федерации.")
        return

    members = sheets.get_members()
    candidates = [(int(m["tg_id"]), m["username"]) for m in members if int(m["tg_id"]) != message.from_user.id]
    if not candidates:
        await message.answer("Нет других участников для игры.")
        return

    await state.update_data(winner_id=message.from_user.id)
    await state.set_state(GameFSM.choosing_opponent)
    kb = opponent_keyboard(candidates, message.from_user.id)
    back = back_button("main")
    final = kb.inline_keyboard + back.inline_keyboard
    kb = types.InlineKeyboardMarkup(inline_keyboard=final)
    await message.answer("Выбери соперника:", reply_markup=kb)


@router.callback_query(F.data == "game:opponent")
async def game_back_to_opponent(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(GameFSM.choosing_opponent)
    sheets = get_sheets()
    sender = sheets.get_member(callback.from_user.id)
    if not sender:
        await callback.message.edit_text("Ты не зарегистрирован в федерации.")
        await state.clear()
        return
    members = sheets.get_members()
    candidates = [(int(m["tg_id"]), m["username"]) for m in members if int(m["tg_id"]) != callback.from_user.id]
    if not candidates:
        await callback.message.edit_text("Нет других участников для игры.")
        await state.clear()
        return
    kb = opponent_keyboard(candidates, callback.from_user.id)
    back = back_button("main")
    final = kb.inline_keyboard + back.inline_keyboard
    kb = types.InlineKeyboardMarkup(inline_keyboard=final)
    await callback.message.edit_text("Выбери соперника:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "game:winloss")
async def game_back_to_winloss(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(GameFSM.choosing_winloss)
    kb = winloss_keyboard()
    back = back_button("game:opponent")
    final = kb.inline_keyboard + back.inline_keyboard
    kb = types.InlineKeyboardMarkup(inline_keyboard=final)
    await callback.message.edit_text("Ты победил или проиграл?", reply_markup=kb)
    await callback.answer()


@router.callback_query(GameFSM.choosing_opponent, F.data.startswith("opponent:"))
async def opponent_chosen(callback: types.CallbackQuery, state: FSMContext):
    opponent_id = int(callback.data.split(":")[1])
    await state.update_data(opponent_id=opponent_id)
    await state.set_state(GameFSM.choosing_winloss)
    kb = winloss_keyboard()
    back = back_button("game:opponent")
    final = kb.inline_keyboard + back.inline_keyboard
    kb = types.InlineKeyboardMarkup(inline_keyboard=final)
    await callback.message.edit_text("Ты победил или проиграл?", reply_markup=kb)
    await callback.answer()


@router.callback_query(GameFSM.choosing_winloss, F.data.startswith("winloss:"))
async def winloss_chosen(callback: types.CallbackQuery, state: FSMContext):
    winloss = callback.data.split(":")[1]
    await state.update_data(winloss=winloss)
    await state.set_state(GameFSM.choosing_result)
    kb = result_keyboard()
    back = back_button("game:winloss")
    final = kb.inline_keyboard + back.inline_keyboard
    kb = types.InlineKeyboardMarkup(inline_keyboard=final)
    await callback.message.edit_text("Выбери результат:", reply_markup=kb)
    await callback.answer()


@router.callback_query(GameFSM.choosing_result, F.data.startswith("game_result:"))
async def result_chosen(callback: types.CallbackQuery, state: FSMContext):
    result = callback.data.split(":")[1]
    data = await state.get_data()
    opponent_id = data["opponent_id"]
    submitter_id = data["winner_id"]
    winloss = data["winloss"]

    if winloss == "loss":
        winner_id = opponent_id
    else:
        winner_id = submitter_id

    sheets = get_sheets()
    game_id = sheets.add_pending_game(submitter_id, opponent_id, winner_id, result, submitter_id)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    submitter = sheets.get_member(submitter_id)
    opponent = sheets.get_member(opponent_id)
    sn = submitter["username"] or f"id{submitter_id}"
    on = opponent["username"] or f"id{opponent_id}"
    rn = _RESULT_NAMES.get(result, result)

    admin_text = (
        f"🎲 Новая игра\n"
        f"Отправил: {sn}\n"
        f"Соперник: {on}\n"
        f"Результат: {rn}\n"
        f"Победил: {'отправитель' if winloss == 'win' else 'соперник'}\n"
        f"Дата: {now}"
    )

    await callback.message.edit_text(
        "Результат отправлен начальству на подтверждение."
    )

    admins = sheets.get_admins()
    bot = callback.bot
    for admin in admins:
        try:
            await bot.send_message(
                int(admin["tg_id"]),
                admin_text,
                reply_markup=approve_game_keyboard(game_id),
            )
        except Exception:
            pass

    await state.clear()
    await callback.answer()
