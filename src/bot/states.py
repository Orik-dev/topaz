from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    waiting_for_content = State()


class ImageStates(StatesGroup):
    waiting_for_image = State()


class VideoStates(StatesGroup):
    waiting_for_video = State()