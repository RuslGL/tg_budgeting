from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    clarifying_amount = State()
    clarifying_category = State()


class NoteForm(StatesGroup):
    clarifying_category = State()
    clarifying_date = State()
