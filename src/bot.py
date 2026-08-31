"""
Модуль: src/bot.py
Назначение: REST API точка входа на FastAPI для корпоративного RAG-бота corporateAIBot_Ollama.
Особенности:
    - Динамическое управление режимами безопасности: none / pre_only / full
    - Асинхронное JSONL логирование метрик через FastAPI BackgroundTasks
    - Метрики времени (Retrieval, LLM, Total Latency)
    - Полный перехват любых типов исключений с записью в logs/system/app.log
"""

import time
import uuid
from typing import List, Optional, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config import API_HOST, API_PORT, DEFAULT_APP_VERSION
from src.rag_pipeline import RAGPipeline
from src.evaluation.logger import EvalLogger
from src.utils.logger import sys_logger

rag_service: Optional[RAGPipeline] = None
eval_logger = EvalLogger(version=DEFAULT_APP_VERSION)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл сервиса: инициализация и корректное завершение."""
    global rag_service
    sys_logger.info("=== Запуск REST API сервиса corporateAIBot_Ollama ===")
    try:
        rag_service = RAGPipeline()
        sys_logger.info("RAG-пайплайн успешно подключен к API.")
    except Exception as e:
        sys_logger.critical(f"Критический сбой при инициализации RAG: {e}", exc_info=True)
        raise e
    yield
    sys_logger.info("=== Остановка REST API сервиса ===")


app = FastAPI(
    title="Corporate RAG Assistant (corporateAIBot_Ollama)",
    description="REST API корпоративного RAG-бота на базе ChromaDB и Ollama со сквозной телеметрией и ИБ-защитой.",
    version="3.0.0",
    lifespan=lifespan
)


# ==============================================================================
# MIDDLEWARE СКВОЗНОГО ТРЕКИНГА И ОБРАБОТКИ ЛЮБЫХ ОШИБОК
# ==============================================================================
@app.middleware("http")
async def trace_requests_middleware(request: Request, call_next):
    """
    Отслеживает все входящие запросы, замеряет длительность,
    логирует технические параметры и перехватывает сбои.
    """
    correlation_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    sys_logger.info(f"--> [REQ_START] {request.method} {request.url.path} | IP: {client_ip} | Trace-ID: {correlation_id}")

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        sys_logger.info(f"<-- [REQ_DONE] {request.method} {request.url.path} | Status: {response.status_code} | Duration: {duration_ms} мс | Trace-ID: {correlation_id}")
        response.headers["X-Trace-ID"] = correlation_id
        return response

    except HTTPException as http_exc:
        # Сохраняем реальные коды ошибок FastAPI (400, 404, 422, 503)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        sys_logger.warning(
            f"[HTTP_EXC {http_exc.status_code}] {request.method} {request.url.path} | "
            f"Trace-ID: {correlation_id} | Длительность: {duration_ms} мс | Причина: {http_exc.detail}"
        )
        return JSONResponse(
            status_code=http_exc.status_code,
            content={"detail": http_exc.detail, "trace_id": correlation_id},
            headers={"X-Trace-ID": correlation_id}
        )

    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        sys_logger.error(
            f"[!!! INTERNAL ERROR 500] Сбой при обработке {request.method} {request.url.path} | "
            f"Trace-ID: {correlation_id} | Длительность: {duration_ms} мс | Ошибка: {exc}",
            exc_info=True
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Внутренняя ошибка сервера: {str(exc)}",
                "trace_id": correlation_id
            },
            headers={"X-Trace-ID": correlation_id}
        )


# ==============================================================================
# PYDANTIC СХЕМЫ
# ==============================================================================
class LatencyMetrics(BaseModel):
    total_latency_ms: float = Field(..., description="Полное время обработки запроса (мс)")
    retrieval_latency_ms: float = Field(..., description="Время поиска в ChromaDB (мс)")
    llm_latency_ms: float = Field(..., description="Время генерации в Ollama (мс)")


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        description="Вопрос к базе знаний",
        examples=["Как складывался брачный союз Хана и Лиры?"]
    )
    security_mode: Literal["none", "pre_only", "full"] = Field(
        default="full",
        description="Уровень защиты: none / pre_only / full"
    )


class QueryResponse(BaseModel):
    request_id: str
    question: str
    answer: str
    chain_of_thought: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    confidence_score: float
    is_known: bool
    security_mode: str
    security_triggered: bool
    metrics: LatencyMetrics


# ==============================================================================
# ЭНДПОИНТЫ
# ==============================================================================
@app.get("/health", tags=["System"])
def health_check():
    """Мониторинг доступности индекса и моделей."""
    if rag_service is None:
        sys_logger.warning("Запрос /health: RAG Pipeline не готов (503).")
        raise HTTPException(status_code=503, detail="RAG Pipeline еще не загружен")

    chunks_count = rag_service.collection.count()
    sys_logger.info(f"Запрос /health: статус OK. Проиндексировано чанков: {chunks_count}")
    return {
        "status": "healthy",
        "app_version": DEFAULT_APP_VERSION,
        "indexed_chunks": chunks_count,
        "embedding_model": "intfloat/multilingual-e5-base",
        "llm_model": "qwen2.5:1.5b-instruct"
    }


@app.post("/ask", response_model=QueryResponse, tags=["RAG"])
def ask_question(request: QueryRequest, background_tasks: BackgroundTasks):
    """Основной эндпоинт генерации ответа по базе знаний."""
    if rag_service is None:
        sys_logger.error("Запрос /ask: RAG Pipeline недоступен.")
        raise HTTPException(status_code=503, detail="RAG Pipeline недоступен")

    request_id = str(uuid.uuid4())

    try:
        result = rag_service.answer_question(
            query=request.question,
            security_mode=request.security_mode
        )

        eval_payload = {
            "request_id": request_id,
            "query": request.question,
            "security_mode": request.security_mode,
            "security_triggered": result["security_triggered"],
            "retrieved_chunks": result["retrieved_chunks"],
            "response": result["answer"],
            "chain_of_thought": result["chain_of_thought"],
            "sources": result["sources"],
            "confidence_score": result["confidence_score"],
            "is_known": result["is_known"],
            "metrics": result["metrics"]
        }

        # Асинхронное логирование метрик RAG
        background_tasks.add_task(eval_logger.log_interaction, eval_payload)

        return QueryResponse(
            request_id=request_id,
            question=result["question"],
            answer=result["answer"],
            chain_of_thought=result["chain_of_thought"],
            sources=result["sources"],
            confidence_score=result["confidence_score"],
            is_known=result["is_known"],
            security_mode=result["security_mode"],
            security_triggered=result["security_triggered"],
            metrics=LatencyMetrics(**result["metrics"])
        )

    except Exception as e:
        sys_logger.error(f"Ошибка при выполнении RAG-пайплайна: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.bot:app", host=API_HOST, port=API_PORT, reload=False)