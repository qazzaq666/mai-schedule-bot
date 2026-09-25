from aiogram.fsm.state import State, StatesGroup


class GroupSetup(StatesGroup):
    waiting_for_group = State()
