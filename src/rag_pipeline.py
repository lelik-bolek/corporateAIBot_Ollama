"""
Модуль: src/rag_pipeline.py
Назначение: Ядро RAG-пайплайна корпоративного бота corporateAIBot_Ollama.
    Замер изолированных интервалов времени: retrieval_latency_ms (поиск в ChromaDB) и llm_latency_ms (инференс Ollama).  
    Поддержка параметра security_mode (none / pre_only / full) через вызов оркестратора SecurityManager.  
    Сквозная фильтрация вывода: санитизация и answer, и chain_of_thought при обнаружении swordfish и секретов.  
    Двухфакторная верификация опоры на контекст (is_known выставляется на основе verify_grounding).  
"""

import time
from typing import Dict, Any, List, Tuple
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
import ollama

from src.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    QUERY_PREFIX,
    TOP_K_CHUNKS,
    SIMILARITY_THRESHOLD,
    OLLAMA_HOST,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    REPEAT_PENALTY,
    SECURITY_BLOCKED_ANSWER,
    SECURITY_BLOCKED_COT,
)
from src.prompts.templates import format_rag_messages
from src.security.guardrails import SecurityManager
from src.utils.logger import sys_logger


class RAGPipeline:
    def __init__(self):
        sys_logger.info("Старт инициализации RAG-пайплайна (corporateAIBot_Ollama v3)...")

        if not Path(CHROMA_DIR).exists():
            sys_logger.error(f"Директория векторной базы ChromaDB не найдена: {CHROMA_DIR}")
            raise FileNotFoundError(f"ChromaDB не найдена: {CHROMA_DIR}")

        sys_logger.info(f"Подключение к ChromaDB: {CHROMA_DIR} | Коллекция: {COLLECTION_NAME}")
        self.chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.chroma_client.get_collection(name=COLLECTION_NAME)

        sys_logger.info(f"Загрузка модели эмбеддингов: {EMBEDDING_MODEL_NAME}...")
        self.embed_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        sys_logger.info(f"Подключение к Ollama API: {OLLAMA_HOST} | Модель: {LLM_MODEL}")
        self.ollama_client = ollama.Client(host=OLLAMA_HOST)
        sys_logger.info("RAG-пайплайн успешно инициализирован.")

    def retrieve(self, query: str, top_k: int = TOP_K_CHUNKS) -> List[Dict[str, Any]]:
        """Извлечение Top-K наиболее релевантных чанков из ChromaDB."""
        prepared_query = f"{QUERY_PREFIX}{query.strip()}"
        query_vector = self.embed_model.encode(
            [prepared_query],
            convert_to_numpy=True,
            normalize_embeddings=True
        ).tolist()[0]

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        retrieved_chunks = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            distances = results["distances"][0]

            for doc, meta, dist in zip(docs, metas, distances):
                # Косинусное сходство: Cosine Similarity = 1 - Cosine Distance
                sim_score = max(0.0, min(1.0, 1.0 - float(dist)))
                retrieved_chunks.append({
                    "text": doc,
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_id": meta.get("chunk_id", -1),
                    "similarity_score": round(sim_score, 4)
                })

        return retrieved_chunks

    def _parse_generation(self, raw_text: str) -> Tuple[str, str]:
        """Разделяет вывод модели на chain_of_thought и финальный ответ."""
        raw_text = raw_text.strip()
        cot = ""
        answer = raw_text

        if "Ответ:" in raw_text:
            parts = raw_text.split("Ответ:", 1)
            cot = parts[0].replace("Рассуждение:", "").strip()
            answer = parts[1].strip()
        elif "Рассуждение:" in raw_text:
            parts = raw_text.split("Рассуждение:", 1)
            cot = parts[1].strip()
            answer = "Ответ сформулирован в блоке рассуждений."

        return cot, answer

    def answer_question(self, query: str, security_mode: str = "full") -> Dict[str, Any]:
        sys_logger.info(f"Начало обработки запроса: '{query}' | Режим ИБ: {security_mode}")
        security = SecurityManager(mode=security_mode)
        start_total = time.perf_counter()

        # ----------------------------------------------------------------------
        # РУБЕЖ 1. Input Sanitization (Проверка входящего запроса)
        # ----------------------------------------------------------------------
        is_blocked, block_reason = security.process_input(query)
        if is_blocked:
            total_lat = round((time.perf_counter() - start_total) * 1000, 2)
            sys_logger.warning(f"[Security Block]: Запрос заблокирован на входе: '{query}'. Причина: {block_reason}")
            return {
                "question": query,
                "answer": SECURITY_BLOCKED_ANSWER,
                "chain_of_thought": SECURITY_BLOCKED_COT,
                "sources": [],
                "confidence_score": 0.0,
                "is_known": False,
                "security_mode": security_mode,
                "security_triggered": True,
                "metrics": {
                    "total_latency_ms": total_lat,
                    "retrieval_latency_ms": 0.0,
                    "llm_latency_ms": 0.0
                },
                "retrieved_chunks": []
            }

        # ----------------------------------------------------------------------
        # ЭТАП 2. Retrieval (Поиск в ChromaDB)
        # ----------------------------------------------------------------------
        t_ret_start = time.perf_counter()
        raw_chunks = self.retrieve(query, top_k=TOP_K_CHUNKS)
        retrieval_latency_ms = round((time.perf_counter() - t_ret_start) * 1000, 2)
        top_score = raw_chunks[0]["similarity_score"] if raw_chunks else 0.0
        sys_logger.info(f"ChromaDB поиск завершен ({retrieval_latency_ms} мс). Чанков: {len(raw_chunks)} | Top-1 скор: {top_score}")

        # ----------------------------------------------------------------------
        # РУБЕЖ 2. Chunk Sanitization (Очистка отравленных чанков)
        # ----------------------------------------------------------------------
        clean_chunks, chunk_poisoned = security.process_chunks(raw_chunks)
        if chunk_poisoned:
            sys_logger.warning("[Security Alert]: Из контекста удален отравленный вредоносный чанк!")

        # Проверка порога уверенности (SIMILARITY_THRESHOLD)
        if top_score < SIMILARITY_THRESHOLD or not clean_chunks:
            total_lat = round((time.perf_counter() - start_total) * 1000, 2)
            sys_logger.info(f"Отказ по порогу: Top-1 скор {top_score} < {SIMILARITY_THRESHOLD}")
            return {
                "question": query,
                "answer": "Я не знаю. В корпоративной базе знаний нет информации по данному вопросу.",
                "chain_of_thought": (
                    f"1. Выполнен поиск по базе знаний ChromaDB.\n"
                    f"2. Максимальный скор сходства составил {top_score:.4f}, что ниже порога {SIMILARITY_THRESHOLD}.\n"
                    f"3. Факты для формирования ответа отсутствуют."
                ),
                "sources": [],
                "confidence_score": top_score,
                "is_known": False,
                "security_mode": security_mode,
                "security_triggered": chunk_poisoned,
                "metrics": {
                    "total_latency_ms": total_lat,
                    "retrieval_latency_ms": retrieval_latency_ms,
                    "llm_latency_ms": 0.0
                },
                "retrieved_chunks": raw_chunks
            }

        # ----------------------------------------------------------------------
        # ЭТАП 3. LLM Inference (Генерация ответа в Ollama)
        # ----------------------------------------------------------------------
        messages = format_rag_messages(query, clean_chunks)
        sys_logger.info(f"Отправка запроса в Ollama ({LLM_MODEL})...")

        t_llm_start = time.perf_counter()
        ollama_response = self.ollama_client.chat(
            model=LLM_MODEL,
            messages=messages,
            options={
                "temperature": float(LLM_TEMPERATURE),
                "num_predict": int(LLM_MAX_TOKENS),
                "repeat_penalty": float(REPEAT_PENALTY)
            }
        )
        llm_latency_ms = round((time.perf_counter() - t_llm_start) * 1000, 2)
        total_latency_ms = round((time.perf_counter() - start_total) * 1000, 2)
        sys_logger.info(f"Ollama завершила генерацию за {llm_latency_ms} мс.")

        raw_output = ollama_response["message"]["content"]
        raw_cot, raw_answer = self._parse_generation(raw_output)

        # ----------------------------------------------------------------------
        # РУБЕЖ 3. Output Guardrail & Grounding Verification
        # ----------------------------------------------------------------------
        final_answer, final_cot, is_known, sec_triggered = security.process_output(
            answer=raw_answer,
            cot=raw_cot,
            chunks=clean_chunks,
            confidence_score=top_score
        )

        if sec_triggered:
            sys_logger.warning("[Security Alert]: Сработал Output Guardrail (обнаружен маркер утечки данных).")

        sources = sorted(list(set(c["source_file"] for c in clean_chunks))) if is_known else []
        sys_logger.info(f"Завершение запроса. is_known={is_known}, security_triggered={sec_triggered or chunk_poisoned}")

        return {
            "question": query,
            "answer": final_answer,
            "chain_of_thought": final_cot,
            "sources": sources,
            "confidence_score": top_score,
            "is_known": is_known,
            "security_mode": security_mode,
            "security_triggered": sec_triggered or chunk_poisoned,
            "metrics": {
                "total_latency_ms": total_latency_ms,
                "retrieval_latency_ms": retrieval_latency_ms,
                "llm_latency_ms": llm_latency_ms
            },
            "retrieved_chunks": raw_chunks
        }