"""
Модуль: src/rag_pipeline.py
Назначение: Ядро корпоративного RAG-пайплайна.
Выполняет:
  1. Векторизацию запроса и поиск Top-K в ChromaDB.
  2. Проверку порога схожести SIMILARITY_THRESHOLD.
  3. Получение готового промпта из модуля prompts.templates.
  4. Инференс через Ollama API и парсинг CoT/Answer.
"""

import time
from typing import Dict, Any, List, Tuple

import chromadb
import ollama
from sentence_transformers import SentenceTransformer

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
)
from src.prompts.templates import format_rag_messages


class RAGPipeline:
    def __init__(self):
        print("[*] Инициализация корпоративного RAGпайплайна... - rag_pipeline.py:35")

        # 1. Подключение к постоянному хранилищу ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        try:
            self.collection = self.chroma_client.get_collection(name=COLLECTION_NAME)
        except Exception as e:
            raise RuntimeError(
                f"Коллекция '{COLLECTION_NAME}' не найдена в {CHROMA_DIR}.\n"
                f"Выполните индексацию базы знаний: python -m src.build_index"
            ) from e

        # 2. Инициализация модели эмбеддингов
        print(f"[*] Загрузка модели эмбеддингов: {EMBEDDING_MODEL_NAME}... - rag_pipeline.py:48")
        self.embed_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        # 3. Настройка клиента Ollama
        self.ollama_client = ollama.Client(host=OLLAMA_HOST)
        self.model_name = LLM_MODEL
        print(f"[+] Подключен движок Ollama (Модель: {self.model_name}, Хост: {OLLAMA_HOST}) - rag_pipeline.py:54")
        print("[+] RAGпайплайн готов к работе. - rag_pipeline.py:55")

    def retrieve(self, query: str, top_k: int = TOP_K_CHUNKS) -> List[Dict[str, Any]]:
        """Векторизует запрос и извлекает Top-K чанков из ChromaDB."""
        prepared_query = f"{QUERY_PREFIX}{query.strip()}"
        query_embedding = self.embed_model.encode(
            [prepared_query],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        retrieved_chunks = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
                similarity_score = round(1.0 - dist, 4)
                retrieved_chunks.append({
                    "text": doc,
                    "source_file": meta.get("source_file", "unknown"),
                    "chunk_index": meta.get("chunk_index", -1),
                    "similarity_score": similarity_score
                })

        return retrieved_chunks

    def _parse_generation(self, raw_output: str) -> Tuple[str, str]:
        """Парсит цепочку рассуждений (CoT) и итоговый ответ."""
        raw_output = raw_output.split("---")[0].strip()
        reasoning = ""
        answer = ""

        if "Ответ:" in raw_output:
            parts = raw_output.split("Ответ:", 1)
            reasoning = parts[0].replace("Рассуждение:", "").strip()
            answer = parts[1].strip()
            if "\n\n" in answer:
                answer = answer.split("\n\n")[0].strip()
        else:
            reasoning = raw_output.replace("Рассуждение:", "").strip()
            answer = "Ответ сформулирован в блоке рассуждений."

        return reasoning, answer

    def answer_question(self, query: str) -> Dict[str, Any]:
        """Сквозной цикл обработки вопроса."""
        start_time = time.perf_counter()

        # 1. Поиск релевантных чанков
        chunks = self.retrieve(query, top_k=TOP_K_CHUNKS)
        top_score = chunks[0]["similarity_score"] if chunks else 0.0

        # 2. Проверка порога уверенности (Guardrail)
        if top_score < SIMILARITY_THRESHOLD:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
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
                "latency_ms": latency_ms
            }

        # 3. Сборка сообщений через внешний модуль шаблонов
        messages = format_rag_messages(query, chunks)

        # 4. Вызов Ollama API
        response = self.ollama_client.chat(
            model=self.model_name,
            messages=messages,
            options={
                "temperature": LLM_TEMPERATURE,
                "num_predict": LLM_MAX_TOKENS,
            }
        )

        raw_output = response["message"]["content"]
        cot, final_answer = self._parse_generation(raw_output)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        is_known = not final_answer.startswith("Я не знаю")
        sources = list(set([ch["source_file"] for ch in chunks])) if is_known else []

        return {
            "question": query,
            "answer": final_answer,
            "chain_of_thought": cot,
            "sources": sources,
            "confidence_score": top_score,
            "is_known": is_known,
            "latency_ms": latency_ms
        }