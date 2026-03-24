from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    clarifying_amount = State()
    clarifying_category = State()
