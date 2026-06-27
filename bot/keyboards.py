from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ── Approve / Reject ──────────────────────────────────────────

def approve_reject_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✓ Подтвердить", callback_data=f"{action}:approve:{item_id}")
    builder.button(text="✕ Отклонить", callback_data=f"{action}:reject:{item_id}")
    return builder.as_markup()


def approve_member_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return approve_reject_keyboard("member", item_id)


def approve_game_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return approve_reject_keyboard("game", item_id)


# ── Pagination ─────────────────────────────────────────────────

def pagination_keyboard(prefix: str, page: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="← Назад", callback_data=f"{prefix}:page:{page - 1}")
    builder.button(text=f"{page}/{total}", callback_data="noop")
    if page < total:
        builder.button(text="Вперёд →", callback_data=f"{prefix}:page:{page + 1}")
    return builder.as_markup()


def history_pagination_keyboard(page: int, total: int, username: str = "", nav_back: str = "") -> InlineKeyboardMarkup:
    if nav_back:
        prefix = f"hhist:{username}" if username else "hhist"
    else:
        prefix = f"history:{username}" if username else "history"
    kb = pagination_keyboard(prefix, page, total)
    if nav_back:
        builder = InlineKeyboardMarkup(inline_keyboard=kb.inline_keyboard + [
            [InlineKeyboardButton(text="← В меню", callback_data=f"nav:{nav_back}")]
        ])
        return builder
    return kb


# ── Game result selection ──────────────────────────────────────

def winloss_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Победил", callback_data="winloss:win")
    builder.button(text="Проиграл", callback_data="winloss:loss")
    return builder.as_markup()


def result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Обычная", callback_data="game_result:win")
    builder.button(text="Марс", callback_data="game_result:mars")
    return builder.as_markup()


# ── Opponent selection ─────────────────────────────────────────

def opponent_keyboard(members: list[tuple[int, str]], exclude_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tg_id, username in members:
        if tg_id != exclude_id:
            builder.button(text=f"@{username}", callback_data=f"opponent:{tg_id}")
    builder.adjust(2)
    return builder.as_markup()


def member_list_keyboard(prefix: str, members: list[tuple[int, str]], exclude_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tg_id, username in members:
        if exclude_id is not None and tg_id == exclude_id:
            continue
        builder.button(text=f"@{username}", callback_data=f"{prefix}:{tg_id}")
    builder.adjust(2)
    return builder.as_markup()


# ── Navigation inline keyboards ───────────────────────────────────

def back_button(target: str = "main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data=f"nav:{target}")
    return builder.as_markup()


def history_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 Вся история", callback_data="nav:history:all")
    builder.button(text="👤 Моя история", callback_data="nav:history:me")
    builder.button(text="🔍 История игрока", callback_data="nav:history:user")
    builder.button(text="← Назад", callback_data="nav:main")
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Ожидающие запросы", callback_data="nav:admin:pending")
    builder.button(text="🗑 Удалить участника", callback_data="nav:admin:remove")
    builder.button(text="📨 Отправить сообщение", callback_data="nav:admin:send")
    builder.button(text="← Назад", callback_data="nav:main")
    builder.adjust(1)
    return builder.as_markup()


# ── Role-based reply keyboards ───────────────────────────────────

MEMBER_BUTTONS = [["📋 Меню"]]

ADMIN_BUTTONS = [["🔧 Кабинет начальства"]]


def main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for row in MEMBER_BUTTONS:
        builder.row(*[KeyboardButton(text=t) for t in row])
    if is_admin:
        for row in ADMIN_BUTTONS:
            builder.row(*[KeyboardButton(text=t) for t in row])
    return builder.as_markup(resize_keyboard=True)  # type: ignore[arg-type]
