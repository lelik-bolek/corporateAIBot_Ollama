Для переноса и запуска проекта **`corporateAIBot_Ollama`** через Docker на Windows и macOS M4 необходимо учесть две кроссплатформенные особенности:

1. **Разделение контуров сервисов:** Python-приложение работает в собственном контейнере, а Ollama запускается в отдельном контейнере на базе официального образа `ollama/ollama`.


2. **Кроссплатформенность путей и окружения:** Исходный код монтируется через тома, а переменные окружения динамически указывают хост Ollama (`http://ollama_service:11434` в Docker или `http://localhost:11434` локально).


3. **Платформонезависимый базовый образ:** Базовый образ `python:3.11-slim` нативно собирается под `linux/amd64` (Windows) и `linux/arm64` (Apple Silicon M4).



---

### 1. Файл `docker/Dockerfile`

Создайте файл `docker/Dockerfile`:

```dockerfile
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

```

---

### 2. Файл `docker-compose.yml`

Создайте файл `docker-compose.yml` в **корне проекта**:

```yaml
version: '3.8'

services:
  # 1. Сервис локального инференса Ollama
  ollama_service:
    image: ollama/ollama:latest
    container_name: corporate_ollama_engine
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      # Сохранение скачанных моделей GGUF между перезапусками
      - ollama_models:/root/.ollama
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:11434/api/tags || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # 2. Сервис RAG-бота (FastAPI + ChromaDB + SentenceTransformers)
  rag_bot:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: corporate_rag_bot
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      # Монтирование персистентной базы ChromaDB и данных для синхронизации
      - ./chroma_db:/app/chroma_db
      - ./data:/app/data
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - OLLAMA_HOST=http://ollama_service:11434
    depends_on:
      ollama_service:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s

volumes:
  ollama_models:

```

---

### 3. Обновление `src/config.py` для поддержки переменной среды Docker

Чтобы бот автоматически понимал, где находится Ollama (внутри Docker по адресу `http://ollama_service:11434` или локально на хосте `http://localhost:11434`), обновите блок конфигурации в `src/config.py`:

```python
import os
from pathlib import Path

# ...

# НАСТРОЙКИ ДВИЖКА OLLAMA
# Считывает адрес из переменной окружения Docker или берет дефолтный localhost
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LLM_MODEL = "qwen2.5:1.5b-instruct"
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 450
TOP_K_CHUNKS = 4
SIMILARITY_THRESHOLD = 0.80

```

---

### 4. Инструкция по сборке и запуску (Windows и macOS)

**Шаг 1. Запуск контейнеров**

```bash
docker compose up --build -d

```

**Шаг 2. Однократная загрузка модели внутрь контейнера Ollama**

```bash
docker exec -it corporate_ollama_engine ollama pull qwen2.5:1.5b-instruct

```

**Шаг 3. Первичная индексация базы знаний внутри контейнера (если база еще не создана на хосте)**

```bash
docker exec -it corporate_rag_bot python -m src.build_index

```

**Шаг 4. Проверка работоспособности**

* Проверка здоровья: [http://localhost:8000/health](http://localhost:8000/health)

* Документация Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)


---

Файлы контейнеризации подготовлены. Можем ли мы переходить к проверке запуска контейнеров и отправке изменений в GitHub?