from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.db import Database
from app.formatting import format_day, format_week
from app.keyboards import foreign_group_keyboard, main_keyboard
from app.mai.client import MaiClient, normalize_group
from app.states import GroupSetup


router = Router()
_clients: dict[tuple[int, str], MaiClient] = {}


def get_client(settings: Settings) -> MaiClient:
    key = (settings.cache_ttl_seconds, str(settings.semester_start))
    if key not in _clients:
        _clients[key] = MaiClient(
            cache_ttl=settings.cache_ttl_seconds,
            semester_start=settings.semester_start,
        )
    return _clients[key]


async def ask_group(message: Message, state: FSMContext):
    await state.set_state(GroupSetup.waiting_for_group)
    await message.answer(
        "Напиши свою группу целиком.\n"
        "Например: <code>М4О-301БВ-24</code>",
        parse_mode=ParseMode.HTML,
    )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, db: Database):
    group = await db.get_group(message.from_user.id)
    if not group:
        await ask_group(message, state)
        return

    await state.clear()
    await message.answer(
        f"Твоя группа: <b>{group}</b>\nВыбирай расписание:",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


@router.message(Command("group"))
async def change_group_command(message: Message, state: FSMContext):
    await ask_group(message, state)


@router.callback_query(F.data == "group:change")
async def change_group_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GroupSetup.waiting_for_group)
    await callback.message.answer(
        "Напиши новую группу целиком. Например: <code>М4О-301БВ-24</code>",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(GroupSetup.waiting_for_group)
async def save_initial_group(
    message: Message,
    state: FSMContext,
    db: Database,
    settings: Settings,
):
    if not message.text:
        return

    group = normalize_group(message.text)
    client = get_client(settings)

    try:
        exists = await client.group_exists(group)
    except Exception:
        await message.answer(
            "МАИ сейчас не ответил нормально. Попробуй ещё раз чуть позже."
        )
        return

    if not exists:
        await message.answer(
            f"Группу <b>{group}</b> в списке МАИ не нашла.\n"
            "Проверь название и отправь ещё раз.",
            parse_mode=ParseMode.HTML,
        )
        return

    await db.set_group(message.from_user.id, group)
    await state.clear()

    await message.answer(
        f"Группа сохранена: <b>{group}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


async def render_period(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    mode: str,
    override_group: str | None = None,
):
    group = override_group or await db.get_group(callback.from_user.id)
    if not group:
        await callback.answer("Сначала укажи группу.", show_alert=True)
        return

    client = get_client(settings)
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()

    await callback.answer()

    try:
        if mode == "today":
            target = today
            day = await client.schedule_for_date(group, target)
            text = format_day(group, target, day)

        elif mode == "tomorrow":
            target = today + timedelta(days=1)
            day = await client.schedule_for_date(group, target)
            text = format_day(group, target, day)

        elif mode in {"this_week", "next_week"}:
            target = today + (timedelta(days=7) if mode == "next_week" else timedelta())
            monday = target - timedelta(days=target.weekday())
            days = await client.schedule_for_week(group, target)
            text = format_week(group, days, monday)

        else:
            return

        await callback.message.answer(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard() if override_group is None else None,
        )

    except Exception:
        await callback.message.answer(
            "Сайт МАИ сейчас ответил какой-то хуйнёй или недоступен. "
            "Попробуй ещё раз позже."
        )


@router.callback_query(F.data.startswith("schedule:"))
async def schedule_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
):
    await render_period(
        callback,
        db,
        settings,
        callback.data.split(":", 1)[1],
    )


@router.message(F.text)
async def arbitrary_group(
    message: Message,
    state: FSMContext,
    db: Database,
    settings: Settings,
):
    if await state.get_state():
        return

    raw = message.text.strip()
    if len(raw) > 40 or "-" not in raw:
        return

    group = normalize_group(raw)
    own = await db.get_group(message.from_user.id)
    if own == group:
        await message.answer(
            f"Это уже твоя основная группа: <b>{group}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard(),
        )
        return

    client = get_client(settings)
    try:
        exists = await client.group_exists(group)
    except Exception:
        return

    if not exists:
        return

    await message.answer(
        f"Нашла группу <b>{group}</b>. Что делаем?",
        parse_mode=ParseMode.HTML,
        reply_markup=foreign_group_keyboard(group),
    )


@router.callback_query(F.data.startswith("foreign:set:"))
async def foreign_set(callback: CallbackQuery, db: Database):
    group = normalize_group(callback.data.split(":", 2)[2])
    await db.set_group(callback.from_user.id, group)
    await callback.answer("Группа сохранена")
    await callback.message.edit_text(
        f"Основная группа теперь: <b>{group}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(),
    )


@router.callback_query(F.data.startswith("foreign:view:"))
async def foreign_view(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
):
    group = normalize_group(callback.data.split(":", 2)[2])
    await callback.answer()
    await callback.message.answer(
        f"Расписание группы <b>{group}</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=__import__("aiogram").types.InlineKeyboardMarkup(inline_keyboard=[
            [
                __import__("aiogram").types.InlineKeyboardButton(
                    text="Сегодня", callback_data=f"foreign_period:today:{group}"
                ),
                __import__("aiogram").types.InlineKeyboardButton(
                    text="Завтра", callback_data=f"foreign_period:tomorrow:{group}"
                ),
            ],
            [
                __import__("aiogram").types.InlineKeyboardButton(
                    text="Эта неделя", callback_data=f"foreign_period:this_week:{group}"
                ),
                __import__("aiogram").types.InlineKeyboardButton(
                    text="Следующая неделя", callback_data=f"foreign_period:next_week:{group}"
                ),
            ],
        ]),
    )


@router.callback_query(F.data.startswith("foreign_period:"))
async def foreign_period(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
):
    _, mode, group = callback.data.split(":", 2)
    await render_period(callback, db, settings, mode, override_group=group)


@router.callback_query(F.data == "foreign:cancel")
async def foreign_cancel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()
