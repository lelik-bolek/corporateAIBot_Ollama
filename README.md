# Спецификация проекта corporateAIBot_Ollama


## Запуск API-сервера:
python -m uvicorn src.bot:app --host 0.0.0.0 --port 8000


## 1. Характеристики и технологический стек

| Компонент | Выбранная технология / Модель | Назначение и параметры |
| --- | --- | --- |
| **Векторная база данных** | **ChromaDB** (PersistentClient)| Встраиваемая база данных. Хранит 768-мерные векторы, исходный текст документов и метаданные в едином локальном каталоге chroma_db/.|
| **Модель эмбеддингов** | **SentenceTransformer("intfloat/multilingual-e5-base")**<br> | Мультиязычный Bi-encoder ($d=768$). Префиксы: passage:  для документов при индексации, query:  для поисковых запросов.|
| **Генеративный движок и LLM** | **Ollama** + **qwen2.5:1.5b-instruct**<br> | C++ движок инференса на базе llama.cpp. Локальное исполнение квантованной модели (INT4/INT8) без оверхеда тяжелых фреймворков.|
| **Веб-интерфейс и API** | **FastAPI** + **Uvicorn** + **Pydantic v2**<br> | Асинхронный REST API сервер с контрактами данных, Swagger UI и эндпоинтами /health и /ask.|
| **Методы промптинга** | **Few-Shot + Chain-of-Thought (CoT)**<br> | Системный шаблон с пошаговыми рассуждениями и примерами из предметной базы для исключения галлюцинаций.|

---

## 2. Структура проекта (каталоги и файлы)

```
corporateAIBot_Ollama/
├── .gitignore                   # Исключение .venv, кэшей, временных файлов и базы chroma_db
├── README.md                    # Архитектурное описание, стек и инструкции по запуску
├── requirements.txt             # Легковесные платформонезависимые зависимости
│
├── data/                        # Слой данных (переносится без изменений)
│   ├── knowledge_base/          # Корпус из 30+ текстовых файлов (.txt)
│   └── terms_map.json           # Словарь соответствия терминов и сущностей
│
├── chroma_db/                   # Директория постоянного хранения SQLite + Parquet (ChromaDB)
│
└── src/
	├── __init__.py
	├── config.py             # Конфигурационные параметры и пути[cite: 1]
	├── prompts/              # Слой шаблонов промпт-инженерии
	│   ├── __init__.py
	│   └── templates.py      # Системные роли, CoT-инструкции, Few-Shot примеры и генераторы промптов
	├── build_index.py        # Скрипт индексации в ChromaDB[cite: 1, 2]
	├── test_search.py        # Проверка векторного поиска[cite: 1, 2]
	├── rag_pipeline.py       # Чистое RAG-ядро (поиск + инференс Ollama без хардкода промптов)[cite: 2, 5]
	└── bot.py                # REST API (FastAPI)
```


---

## 3. Особенности кроссплатформенности и синхронизации (Windows ↔ Mac M4 через GitHub)

1. **Изоляция виртуальных окружений (.venv):**
Папка .venv строго добавляется в .gitignore. На Windows и macOS создаются свои локальные окружения. Пакет requirements.txt содержит только абстрактные имена библиотек без платформозависимых бинарных хэшей.


2. **Динамические пути (pathlib.Path):**
Все пути к файлам и папкам в src/config.py вычисляются динамически от расположения скрипта, исключая проблемы со слэшами (/ vs \).


3. **Локальный движок Ollama:**
* На **Windows** (Intel Core i5-10210U) Ollama использует инструкции AVX2 процессора (ожидаемое время ответа 10–25 секунд).


* На **macOS** (Apple Silicon M4) Ollama автоматически подключает Metal GPU / Unified Memory (ожидаемое время ответа 2–5 секунд).


* В обоих случаях Python-код общается с Ollama по единому REST API адресу http://localhost:11434.


4. **Хранилище ChromaDB:**
Директория chroma_db/ добавляется в .gitignore, так как индекс быстро генерируется на любой из машин запуском одного скрипта python src/build_index.py.



---

## 4. Сравнение и список изменений относительно исходного проекта

| Файл / Компонент | Что было в Sprint7ProjectWork | Что будет в corporateAIBot_Ollama |
| --- | --- | --- |
| requirements.txt | faiss-cpu, torch, transformers, accelerate<br> | chromadb, sentence-transformers, ollama, fastapi, uvicorn, langchain-text-splitters<br> |
| src/config.py | Пути к index.faiss, index.pkl<br> | Путь CHROMA_DIR, имя коллекции COLLECTION_NAME, параметры OLLAMA_HOST и LLM_MODEL |
| src/build_index.py | Векторизация numpy + сохранение faiss.write_index + pickle.dump<br> | Прямая запись чанков, метаданных и векторов в коллекцию collection.add(...) ChromaDB|
| src/rag_pipeline.py | Поиск через faiss.search + десериализация pickle + тяжелый инференс AutoModelForCausalLM на CPU| Запрос collection.query(...) + формирование промпта Few-Shot/CoT + вызов ollama.chat()<br> |
| src/bot.py | Проверка rag_service.index.ntotal в /health<br> | Проверка доступности коллекции ChromaDB и статуса демона Ollama |

---
requirements.txt

```
# Векторная база данных
chromadb>=0.5.0

# Модель эмбеддингов
sentence-transformers>=3.0.0

# Разделение текста на чанки
langchain-text-splitters>=0.2.0

# Интеграция с локальным сервисом Ollama
ollama>=0.3.0

# REST API бэкенд и веб-сервер
fastapi>=0.110.0
uvicorn>=0.28.0
pydantic>=2.0.0

# Дополнительные утилиты
python-dotenv>=1.0.0
requests>=2.31.0
```

---
# 1. Настройка изолированного окружения в VS Code (Windows)

Чтобы VS Code не использовал глобальный Python, а работал исключительно в изолированном `.venv`, выполните следующие шаги в терминале PowerShell внутри корневой папки нового проекта `corporateAIBot_Ollama`:

**Шаг 1. Создание виртуального окружения**

```powershell
python -m venv .venv

```

**Шаг 2. Активация окружения**

```powershell
.venv\Scripts\activate

```
(В начале строки терминала появится префикс `(.venv)`).


**Шаг 3. Обновляем pip внутри изолированного .venv
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

**Шаг 4. Установка зависимостей из requirements.txt**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org

```

**Шаг 4. Привязка интерпретатора в интерфейсе VS Code**

1. Нажмите комбинацию клавиш `Ctrl + Shift + P`.


2. Начните вводить: `Python: Select Interpreter`.


3. Выберите пункт со значком **`('.venv': venv)`** по пути `.\.venv\Scripts\python.exe`.


4. Теперь все расширения (Pylance), запуск скриптов и терминал будут жестко привязаны к этому локальному окружению.

---

Выполните создание окружения, индексацию и проверочный запуск:

```powershell
python -m src.build_index
python -m src.test_search

```
---

## Инструкция по запуску проекта

Проект поддерживает два независимых сценария развертывания: в изолированных Docker-контейнерах или локально в Python-окружении (Windows / macOS).

---

### Вариант 1. Запуск через Docker Compose (Рекомендуемый)

При запуске через Docker Compose бот и движок Ollama поднимаются в единой виртуальной сети.

1. **Запуск контейнеров:**
   ```bash
   docker compose up --build -d

```

2. **Загрузка весов модели в контейнер Ollama (выполняется один раз):**
```bash
docker exec -it corporate_ollama_engine ollama pull qwen2.5:1.5b-instruct

```


3. **Индексация базы знаний внутри контейнера (если база еще не собрана):**
```bash
docker exec -it corporate_rag_bot python -m src.build_index

```


4. **Проверка работоспособности:**
* Проверка статуса: `http://localhost:8000/health`
* Документация API и интерактивный UI: `http://localhost:8000/docs`


5. **Остановка сервисов:**
```bash
docker compose down

```



---

### Вариант 2. Локальный запуск напрямую (Windows / macOS)

1. **Запуск локального приложения Ollama:**
* Убедитесь, что приложение Ollama установлено и запущено в системе.
* Загрузите модель в терминале:
```bash
ollama pull qwen2.5:1.5b-instruct

```




2. **Настройка конфигурации:**
* В файле `src/config.py` в секции `4` закомментируйте **ВАРИАНТ А** и раскомментируйте **ВАРИАНТ Б** (`OLLAMA_HOST = "http://localhost:11434"`).


3. **Активация виртуального окружения и установка зависимостей:**
* **Windows (PowerShell):**
```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt

```


* **macOS (Terminal):**
```bash
source .venv/bin/activate
pip install -r requirements.txt

```




4. **Индексация базы знаний:**
```bash
python -m src.build_index

```


5. **Запуск REST API сервера:**
```bash
python -m uvicorn src.bot:app --host 127.0.0.1 --port 8000

```



---

**1. Контрольный вопрос по сущностям (файл `mustafar.txt`):**
Какой уникальный объект создал Чу-Гон Дар на планете Пирос?

**2. Контрольный вопрос по персонажам и событиям (файлы `mustafar.txt` и `darth_vader.txt`):**
Кто сражался в Дуэли на Пиросе между Орионом Келом и Велгором?

**3. Контрольный вопрос по составу экипажа (файл `darth_vader.txt`):**
Кто находился в «Звездном Скитальце», когда он был захвачен притягивающим лучом?

**4. Контрольный вопрос по обстоятельствам захвата (файл `darth_vader.txt`):**
Как именно был захвачен «Звездный Скиталец»?

**5. Контрольный вопрос на отсечение внешнего оффтопа (проверка Guardrail):**
Какая погода в Волгограде?