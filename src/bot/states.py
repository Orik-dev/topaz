from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    """Состояния оплаты"""
    waiting_for_email = State()


class BroadcastStates(StatesGroup):
    """Состояния рассылки"""
    waiting_for_content = State()


class ImageStates(StatesGroup):
    """Состояния обработки фото"""
    waiting_for_image = State()
    selecting_model = State()


class VideoStates(StatesGroup):
    """Состояния обработки видео"""
    waiting_for_video = State()
    selecting_model = State()