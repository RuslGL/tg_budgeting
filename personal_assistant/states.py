from aiogram.fsm.state import State, StatesGroup


class AssistantForm(StatesGroup):
    choosing_contact = State()  # disambiguation: user picks from list of matches
