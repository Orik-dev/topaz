import multiprocessing
from src.core.config import settings

# Server socket
bind = f"{settings.SERVER_HOST}:{settings.SERVER_PORT}"
backlog = 2048

# Worker processes (ИСПРАВЛЕНО - МЕНЬШЕ WORKERS!)
workers = 2  # ✅ Было: multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "/app/logs/access.log"
errorlog = "/app/logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "topaz_bot"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None