"""
Модуль: src/bot.py
Назначение: REST API точка входа на FastAPI для корпоративного RAG-бота corporateAIBot_Ollama.
"""

import sys
import time
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Гарантия корректной кодировки UTF-8 в консоли Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.config import API_HOST, API_PORT, LLM_MODEL, EMBEDDING_MODEL_NAME
from src.rag_pipeline import RAGPipeline

rag_service: Optional[RAGPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл сервиса: загрузка моделей и клиентов при старте."""
    global rag_service
    print("\n - bot.py:29" + "=" * 70)
    print("[*] ЗАПУСК СЕРВИСА corporateAIBot_Ollama: инициализация ресурсов... - bot.py:30")
    print("= - bot.py:31" * 70)
    try:
        rag_service = RAGPipeline()
    except Exception as e:
        print(f"[!] Критическая ошибка при инициализации RAGпайплайна: {e} - bot.py:35")
        raise e
    yield
    print("\n[*] ОСТАНОВКА СЕРВИСА: освобождение системных ресурсов... - bot.py:38")


app = FastAPI(
    title="Corporate AI Bot (Ollama + ChromaDB)",
    description="REST API корпоративного RAG-ассистента по измененной вселенной Star Wars.",
    version="1.0.0",
    lifespan=lifespan
)


# ==============================================================================
# 1. PYDANTIC МОДЕЛИ ЗАПРОСА И ОТВЕТА
# ==============================================================================
class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Вопрос к базе знаний",
        examples=["Какой уникальный объект создал Чу-Гон Дар на планете Пирос?"]
    )


class QueryResponse(BaseModel):
    question: str
    answer: str
    chain_of_thought: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    confidence_score: float = Field(..., description="Косинусное сходство Top-1 чанка")
    is_known: bool = Field(..., description="Флаг наличия прямого факта в базе знаний")
    latency_ms: float = Field(..., description="Сквозное время обработки запроса сервером (в мс)")


# ==============================================================================
# 2. ЭНДПОИНТЫ REST API
# ==============================================================================
@app.get("/health", tags=["System"])
def health_check():
    """Проверка доступности RAG-пайплайна, ChromaDB и конфигурации моделей."""
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG-пайплайн еще не инициализирован.")
    
    try:
        total_chunks = rag_service.collection.count()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка подключения к ChromaDB: {e}")

    return {
        "status": "healthy",
        "vector_store": "ChromaDB",
        "indexed_chunks": total_chunks,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "llm_model": LLM_MODEL
    }


@app.post("/ask", response_model=QueryResponse, tags=["RAG"])
def ask_question(request: QueryRequest):
    """Сквозная обработка вопроса пользователя через контур ChromaDB -> Ollama."""
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG-пайплайн недоступен.")

    try:
        result = rag_service.answer_question(query=request.question)
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка выполнения RAG-пайплайна: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.bot:app", host=API_HOST, port=API_PORT, reload=False)