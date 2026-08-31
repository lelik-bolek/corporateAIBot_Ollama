# Базовый образ Python с поддержкой архитектур amd64 (x86_64) и arm64 (Apple Silicon)
FROM python:3.11-slim

# Установка системных утилит для сборки и сетевых проверок
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Оптимизация вывода логов Python и отключение предупреждений
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false

# Установка Python-зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода и данных
COPY src/ /app/src/
COPY data/ /app/data/

# Экспорт порта REST API
EXPOSE 8000

# Запуск FastAPI через Uvicorn
CMD ["uvicorn", "src.bot:app", "--host", "0.0.0.0", "--port", "8000"]