# Спецификация проекта corporateAIBot_Ollama

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
└── src/                         # Исходный код приложения
    ├── __init__.py
    ├── config.py                # Конфигурация путей (pathlib), параметров ChromaDB и Ollama API
    ├── build_index.py           # Чанкинг (RecursiveSplitter), эмбеддинги E5 и запись в ChromaDB
    ├── rag_pipeline.py          # Ядро RAG: поиск в ChromaDB, сборка CoT/Few-Shot промпта, вызов Ollama
    └── bot.py                   # REST API сервер на базе FastAPI (эндпоинты /health, /ask)
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

## 5. Пошаговый план выполнения

* **Шаг 1:** Фиксация .gitignore и универсального requirements.txt.
* **Шаг 2:** Создание централизованного конфигурационного файла src/config.py.
* **Шаг 3:** Разработка модуля индексации src/build_index.py (чанкинг и сохранение в ChromaDB).
* **Шаг 4:** Разработка ядра src/rag_pipeline.py (поиск в ChromaDB + Few-Shot / CoT + генерация через Ollama).
* **Шаг 5:** Разработка REST API точки входа src/bot.py на FastAPI.
* **Шаг 6:** Тестирование пайплайна на контрольных вопросах (оценка качества ответов и времени генерации).

---
