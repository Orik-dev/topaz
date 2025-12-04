from aiogram.fsm.state import State, StatesGroup


class ImageStates(StatesGroup):
    """Состояния для обработки фото"""
    waiting_for_image = State()
    selecting_model = State()


class VideoStates(StatesGroup):
    """Состояния для обработки видео"""
    waiting_for_video = State()
    selecting_model = State()


class PaymentStates(StatesGroup):
    """Состояния для оплаты"""
    waiting_for_email = State()
    entering_email = State()


class BroadcastStates(StatesGroup):
    """Состояния для рассылки"""
    waiting_for_content = State()