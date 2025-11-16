FROM python:3.11-slim

# Рабочая директория
WORKDIR /app

# Копируем requirements
COPY requirements.txt .

# Устанавливаем Python зависимости (БЕЗ системных пакетов MySQL!)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Создаем директорию для логов
RUN mkdir -p /app/logs

# Права на выполнение скрипта запуска
RUN chmod +x /app/start.sh 2>/dev/null || true

EXPOSE 8000

# Запуск через Gunicorn
CMD ["gunicorn", "src.web.server:app", "-c", "gunicorn.conf.py"]