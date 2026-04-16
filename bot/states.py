from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    clarifying_amount = State()
    clarifying_category = State()
    clarifying_project = State()


class NoteForm(StatesGroup):
    clarifying_category = State()
    clarifying_date = State()


class CalorieForm(StatesGroup):
    clarifying_grams = State()
    entering_cal_limit = State()
    entering_macros = State()
    entering_goal_weight = State()
    entering_custom_product = State()
