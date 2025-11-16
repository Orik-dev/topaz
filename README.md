# Topaz AI Bot

Telegram бот для улучшения фото и видео с помощью Topaz Labs API.

## Возможности

- 📸 Улучшение фото (AI upscale, denoise, sharpen)
- 🎬 Улучшение видео (AI upscale, frame interpolation)
- 💳 Оплата через YooKassa и Telegram Stars
- ⚡ Автоматический возврат генераций при ошибках
- 📊 Админ-панель с рассылками и статистикой

## Технологии

- **Backend**: Python 3.11, FastAPI, aiogram 3.14
- **Workers**: ARQ (асинхронные очереди)
- **Database**: MySQL 5.7
- **Cache**: Redis 7
- **API**: Topaz Labs Image/Video API
- **Payments**: YooKassa, Telegram Stars

## Архитектура
```
┌─────────────┐
│   Nginx     │ (Reverse Proxy)
└──────┬──────┘
       │
┌──────▼──────────────────┐
│  FastAPI (Gunicorn)     │ (Webhooks)
└──────┬──────────────────┘
       │
       ├─────────┬──────────┬─────────┐
       │         │          │         │
┌──────▼───┐ ┌──▼────┐ ┌───▼────┐ ┌──▼──────┐
│  MySQL   │ │ Redis │ │ Image  │ │  Video  │
│          │ │       │ │ Worker │ │ Worker  │
└──────────┘ └───────┘ └────────┘ └─────────┘
```

## Установка

### 1. Клонировать репозиторий
```bash
git clone <repo_url>
cd topaz-bot
```

### 2. Настроить .env
```bash
cp .env.example .env
nano .env
```

Заполнить все переменные окружения.

### 3. Создать базу данных
```bash
mysql -h servers.local -u u2969681_devlz -p < db/create.sql
```

### 4. Запустить через Docker
```bash
docker-compose up -d --build
```

### 5. Проверить логи
```bash
docker-compose logs -f bot
docker-compose logs -f image_worker
docker-compose logs -f video_worker
```

## Локальная разработка
```bash
# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Установить зависимости
pip install -r requirements.txt

# Запустить Redis
docker run -d -p 6379:6379 redis:7-alpine

# Запустить бота
python -m uvicorn src.web.server:app --reload --host 0.0.0.0 --port 8000

# В отдельных терминалах запустить workers
arq src.workers.image_worker.WorkerSettings
arq src.workers.video_worker.WorkerSettings
```

## Команды бота

- `/start` - Начать работу
- `/help` - Справка
- `/bots` - Наши боты
- `/balance` - Баланс генераций
- `/topup` - Пополнить

**Админ команды:**
- `/broadcast` - Рассылка
- `/stats` - Статистика

## Мониторинг

- Health check: `http://yourdomain.com/healthz`
- Logs: `./logs/bot.log`
- Docker logs: `docker-compose logs -f`

## Поддержка

Telegram: @guardGpt

## Лицензия

Proprietary