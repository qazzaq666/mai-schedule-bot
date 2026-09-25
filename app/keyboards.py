from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data="schedule:today"),
            InlineKeyboardButton(text="Завтра", callback_data="schedule:tomorrow"),
        ],
        [
            InlineKeyboardButton(text="Эта неделя", callback_data="schedule:this_week"),
            InlineKeyboardButton(text="Следующая неделя", callback_data="schedule:next_week"),
        ],
        [
            InlineKeyboardButton(text="Сменить группу", callback_data="group:change"),
        ],
    ])


def foreign_group_keyboard(group: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Посмотреть",
                callback_data=f"foreign:view:{group}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="Сделать моей группой",
                callback_data=f"foreign:set:{group}",
            ),
        ],
        [
            InlineKeyboardButton(text="Отмена", callback_data="foreign:cancel"),
        ],
    ])
