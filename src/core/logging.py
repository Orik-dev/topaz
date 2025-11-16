import logging
import sys
import os


def setup_logging():
    """Настройка логирования"""
    # Создаем директорию для логов если нет
    os.makedirs('logs', exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/bot.log', encoding='utf-8')
        ]
    )
    
    # Отключаем verbose логи от библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


# Создаем глобальный logger
logger = logging.getLogger(__name__)