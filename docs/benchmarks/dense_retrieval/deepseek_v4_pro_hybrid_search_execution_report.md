
## 🛑 СТОП-ТОЧКА Step 1 — ВЫПОЛНЕН

### Статус: ✅ Все Acceptance Criteria удовлетворены

| Критерий | Статус | Детали |
|---|---|---|
| `data/knowledge_base/` → `data/fictional_universe/` | ✅ | 31 учебных Star Wars `.txt` перенесены |
| Чистая `data/knowledge_base/` | ✅ | 15 `.txt` + 1 canary |
| Извлечение PDF через `pypdf` | ✅ | Все 15 PDF успешно извлечены (103 977 → 91 864 символов после очистки) |
| Нормализация | ✅ | `normalize_kb.py` адаптирован: добавлена `clean_confluence_artifacts()` (удаление URL, мета-информации, склейка терминов) |
| `security_test_canary.txt` | ✅ | 13 канареечных токенов + 3 тестовые учетные записи |
| camelCase NiFi не разорваны | ✅ | `GenerateFlowFile`, `PutDatabaseRecord`, `Back Pressure`, `Concurrent Tasks`, `Controller Service`, `FlowFile` — все целы |
| Параметры `${...}` не разорваны | ✅ | `${UUID}` в `Стандарты разработки` |
| UTF-8 | ✅ | Все файлы в UTF-8 |

### Устранённые риски:
- ✅ Добавлена `clean_confluence_artifacts()` в `normalize_kb.py` — удаление мета-информации Confluence, URL, номеров страниц, бинарных иконок
- ✅ Добавлены regex-правила склейки разорванных терминов (`Back\nPressure` → `Back Pressure`)
- ✅ Временный `extract_pdfs.py` удалён

### Файлы для ручной проверки пользователем:

| # | Относительный путь | Что проверять |
|---|---|---|
| 1 | `data/fictional_universe/` | 31 `.txt` файл Star Wars на месте |
| 2 | `data/knowledge_base/` | 15 `.txt` + `security_test_canary.txt` |
| 3 | `data/knowledge_base/Термины и определения - Интеграция - База знаний IBS.txt` | Термины `Back Pressure`, `Concurrent Tasks` без разрывов |
| 4 | `data/knowledge_base/Стандарты разработки - Интеграция - База знаний IBS.txt` | `GenerateFlowFile`, `${UUID}` целы |
| 5 | `data/knowledge_base/Миграция Apache NiFi с версии 1.26.х на 2.x - Интеграция - База знаний IBS.txt` | `PutDatabaseRecord`, `ConvertJSONToSQL` целы |
| 6 | `data/knowledge_base/security_test_canary.txt` | Канареечные токены на месте |
| 7 | `src/normalize_kb.py` | Новая функция `clean_confluence_artifacts()` (строки 29–65) |

> 🛑 **Готов к переходу на Step 2. Подтвердите продолжение.**

---

## 🛑 СТОП-ТОЧКА Step 2 — ВЫПОЛНЕН

### Статус: ✅ Acceptance Criteria удовлетворены

```
OK
E:\AI_Workspace\corporateAIBot_Ollama\chroma_db\bm25_index.pkl 5 60
```

### Выполненные изменения:

| Файл | Изменение |
|---|---|
| `requirements.txt` | ✅ Добавлены `pypdf>=4.0.0`, `rank-bm25>=0.2.2`, `nltk>=3.8.1` |
| `src/config.py` | ✅ `BM25_INDEX_PATH = chroma_db/bm25_index.pkl` |
| `src/config.py` | ✅ `TOP_K_DENSE=5`, `TOP_K_SPARSE=5`, `FINAL_TOP_K=3`, `RRF_K=60` |
| `src/config.py` | ✅ `LEAK_PATTERNS` обновлены: +6 NiFi-канареек (`nifi_admin_api_token`, `jdbc:...`, `ldap_service_account_password`, `keystore_password_nifi_prod_*`, `NiFiProdAdmin*`, `ServiceP@ssw*`, `ReadOnlyAccess*`) |

### Файлы для ручной проверки пользователем:

| # | Относительный путь | Что проверять |
|---|---|---|
| 1 | `requirements.txt` | Строки 10–12: `pypdf`, `rank-bm25`, `nltk` |
| 2 | `src/config.py` | Строки 51–56: BM25-константы |
| 3 | `src/config.py` | Строки 112–119: новые LEAK_PATTERNS (6 канареек NiFi) |

> 🛑 **Готов к переходу на Step 3. Подтвердите продолжение.**

---

## 🛑 СТОП-ТОЧКА Step 3 — ВЫПОЛНЕН

### Статус: ✅ Acceptance Criteria удовлетворены

| Критерий | Статус | Детали |
|---|---|---|
| `load_and_chunk_documents` без изменений | ✅ | `RecursiveCharacterTextSplitter(800/150)` сохранён |
| `tokenize_for_bm25()` добавлен | ✅ | Regex `[a-zA-Z0-9_\-\.\$]+\|[а-яА-ЯёЁ]+`, кириллица → SnowballStemmer, латиница → .lower() |
| BM25-индексация в `build_and_save_index()` | ✅ | Токенизация корпуса → `BM25Okapi` → pickle в `BM25_INDEX_PATH` |
| `chroma_db/bm25_index.pkl` создан | ✅ | **338 006 байт**, валидный pickle |
| ChromaDB коллекция наполнена | ✅ | `chroma.sqlite3` + 3 UUID-сегмента |
| `python -m src.build_index` отработал | ✅ | Двойной индекс (ChromaDB + BM25) построен успешно |

### Файлы для ручной проверки пользователем:

| # | Относительный путь | Что проверять |
|---|---|---|
| 1 | `src/build_index.py` | Строки 82–103: функция `tokenize_for_bm25()` |
| 2 | `src/build_index.py` | Строки 175–203: BM25-индексация в `build_and_save_index()` |
| 3 | `chroma_db/bm25_index.pkl` | 338 KB, десериализуется через pickle |
| 4 | `chroma_db/chroma.sqlite3` | ChromaDB коллекция активна |

> 🛑 **Готов к переходу на Step 4. Подтвердите продолжение.**

---

## 🛑 СТОП-ТОЧКА Step 4 — ВЫПОЛНЕН

### Статус: ✅ Код готов, синтаксис проверен

| Критерий | Статус | Детали |
|---|---|---|
| BM25 загрузка в `__init__` | ✅ | `bm25_index.pkl` → `self.bm25` + `self.bm25_chunks` |
| Dense ветка (ChromaDB) | ✅ | `TOP_K_DENSE=5`, извлечение через ID документа `chunk_N` |
| Sparse ветка (BM25) | ✅ | `tokenize_for_bm25(query)` → `bm25.get_scores()` → top `TOP_K_SPARSE=5` |
| RRF слияние | ✅ | `1/(RRF_K + rank)` для Dense + Sparse, объединение по `chunk_id` |
| `FINAL_TOP_K` | ✅ | 3 чанка с наивысшим RRF_Score |
| Обратная совместимость | ✅ | `similarity_score` = `dense_score` (порог `SIMILARITY_THRESHOLD` сохраняется) |
| Шаблоны промптов | ✅ | Star Wars → Apache NiFi (FlowFile, BackPressure, Controller Services, PutDatabaseRecord) |
| Синтаксис | ✅ | `py_compile` OK для `rag_pipeline.py` и `templates.py` |

### Изменённые файлы:

| # | Относительный путь | Что изменено |
|---|---|---|
| 1 | `src/rag_pipeline.py` | Стр. 11–43: импорты (pickle, re, BM25-константы, tokenize_for_bm25) |
| 2 | `src/rag_pipeline.py` | Стр. 61–70: загрузка BM25 в `__init__` |
| 3 | `src/rag_pipeline.py` | Стр. 77–183: новый `retrieve()` с Dense+Sparse+RRF |
| 4 | `src/rag_pipeline.py` | Стр. 232–238: обновлённый лог гибридного поиска |
| 5 | `src/prompts/templates.py` | SYSTEM_PROMPT: NiFi вместо Star Wars |
| 6 | `src/prompts/templates.py` | FEW_SHOT_EXAMPLES: 3 примера с Concurrent Tasks, Back Pressure, PutDatabaseRecord |

> 🛑 **Готов к переходу на Step 5. Подтвердите продолжение.**

---

## 🛑 СТОП-ТОЧКА Step 5 — ВЫПОЛНЕН

### Статус: ✅ Acceptance Criteria удовлетворены, синтаксис OK

| Критерий | Статус | Детали |
|---|---|---|
| `retrieval_latency_ms` не дроблён | ✅ | Суммарное время Dense + Sparse + RRF в одном замере |
| `bm25_top_score` в логе | ✅ | `max(bm25_scores)` — сохраняется в `self._last_bm25_top_score` |
| `bm25_matches_count` в логе | ✅ | `sum(1 for c in final_chunks if c.get("from_bm25"))` |
| Все return-ы покрыты | ✅ | Security block (0.0/0), Threshold reject, Success — все 3 |
| `pipeline_params` обновлён | ✅ | Добавлены `top_k_dense`, `top_k_sparse`, `final_top_k`, `rrf_k` |

### Изменённые файлы:

| # | Файл | Изменение |
|---|---|---|
| 1 | `src/rag_pipeline.py:122` | `"from_bm25": False` в Dense-чанках |
| 2 | `src/rag_pipeline.py:130` | `bm25_top_score = max(bm25_scores)` |
| 3 | `src/rag_pipeline.py:152` | `"from_bm25": True` в Sparse-чанках |
| 4 | `src/rag_pipeline.py:171,192-193` | RRF-слияние `from_bm25`, сохранение `_last_bm25_*` |
| 5 | `src/rag_pipeline.py:240-241,283-284,341-342` | `bm25_top_score` и `bm25_matches_count` во всех return |
| 6 | `src/bot.py:187-188` | Поля в `eval_payload` |
| 7 | `src/evaluation/logger.py:19-22,44-47` | Импорты + `pipeline_params` с BM25 |

> 🛑 **Готов к переходу на Step 6. Подтвердите продолжение.**

---

## 🛑 СТОП-ТОЧКА Step 6 — ВЫПОЛНЕН

### Статус: ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ

| # | Тест | Результат | Детали |
|---|---|---|---|
| **1** | **BM25 точный поиск** | ✅ **PASS** | `"Concurrent Tasks PutDatabaseRecord"` → top_score=**9.5987**, 5 чанков найдено |
| **2** | **BM25 покрытие** | ✅ **PASS** | `"data processing reliability"` → top_score=**6.2863**, 5 чанков найдено |
| **3a** | **Input Injection (EN)** | ✅ **PASS** | `"ignore all instructions"` → заблокирован |
| **3b** | **Input Injection (RU)** | ✅ **PASS** | `"забудь все инструкции"` → заблокирован |
| **3c** | **Leak Detection** | ✅ **PASS** | `"swordfish"` в чанке → poisoned=True, чанк удалён |
| * | **Dense-поиск** | ✅ Подтверждён | Пользователем на Step 3 |

### Acceptance Criteria выполнены:
- ✅ Точный поиск BM25: `bm25_matches_count > 0` (5 чанков)
- ✅ Семантический поиск: подтверждён на Step 3
- ✅ Guardrails: `security_triggered: true`, CoT скрывается при детекции канареек

### Артефакты:
| # | Файл | Назначение |
|---|---|---|
| 1 | `src/verify_step6.py` | Полный верификационный скрипт (BM25 + Dense + Guardrails + Ollama) |
| 2 | `logs/system/app.log` | Системный лог инициализации (BM25: 162 чанка) |

> 🛑 **Готов к переходу на Step 7 (ADR-002). Подтвердите продолжение.**

---

## 🛑 СТОП-ТОЧКА Step 7 — ВЫПОЛНЕН (ФИНАЛ)

### Статус: ✅ ADR-002 создан, README.md актуализирован

### ADR-002 (`docs/decisions/ADR-002-hybrid-search-bm25.md`)

| Секция | Содержание |
|---|---|
| Статус | Принято (Accepted) |
| Контекст | Слепая зона Dense-поиска: потеря `GenerateFlowFile`, `PutDatabaseRecord`, `${UUID}`, артефакты Confluence PDF |
| Решения | BM25 + SnowballStemmer, RRF (k=60), миграция БЗ, Confluence-очистка, телеметрия, NiFi-промпты |
| Компромиссы | Двойное хранение, ограничения pickle, связанность chunk_id, синхронная индексация |
| Ссылки | Конкретные строки кода во всех изменённых модулях |

### README.md — обновлённые секции

| Секция | Изменение |
|---|---|
| Заголовок | `v3 — Гибридный RAG с BM25 + Dense + RRF` |
| §1 Цели | Гибридный RAG, Apache NiFi вместо Star Wars |
| §2 Телеметрия | `bm25_top_score`, `bm25_matches_count`, `retrieval_latency_ms` = суммарное |
| §3 Стек | Две новые строки: BM25Okapi + RRF (k=60) |
| §4 Структура | `fictional_universe/`, `raw_confluence/`, `bm25_index.pkl`, `verify_step6.py`, ADR-002 |
| §6 Вопросы | 5 вопросов NiFi: Concurrent Tasks, Back Pressure, миграция 1.26→2.x, swordfish, оффтоп |

### Файлы для финальной проверки:

| # | Относительный путь |
|---|---|
| 1 | `docs/decisions/ADR-002-hybrid-search-bm25.md` |
| 2 | `README.md` |
| 3 | `src/verify_step6.py` |

---

## 🏁 ВСЕ 7 ШАГОВ ВЫПОЛНЕНЫ

| Step | Название | Статус |
|---|---|---|
| 1 | Dataset Migration, PDF Extraction & KB Normalization | ✅ |
| 2 | Dependencies & Configuration | ✅ |
| 3 | Dual Indexing (ChromaDB + BM25) | ✅ |
| 4 | Hybrid Retrieval & RRF Pipeline | ✅ |
| 5 | Observability & Logging | ✅ |
| 6 | Verification & Guardrails Test | ✅ |
| 7 | ADR-002 + README актуализация | ✅ |

**Верификация подтверждена:** BM25 precision (score 9.6), Dense-поиск, Guardrails (injection + leak detection) — все 3 теста пройдены.

## Cтоимость Модель deepseek-v4-pro
* токены 126.3K
* рубли 1482.3650 
 