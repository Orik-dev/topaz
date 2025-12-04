FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (для кэширования)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p /app/logs /app/temp_inputs

# Set permissions for scripts
RUN chmod +x /app/cleanup_cron.sh || true && \
    chmod +x /app/run_image_worker.py || true && \
    chmod +x /app/run_video_worker.py || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Default command (will be overridden by docker-compose)
CMD ["gunicorn", "src.web.server:app", \
    "--workers", "4", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--bind", "0.0.0.0:8000", \
    "--timeout", "120", \
    "--access-logfile", "/app/logs/access.log", \
    "--error-logfile", "/app/logs/error.log", \
    "--log-level", "info"]
