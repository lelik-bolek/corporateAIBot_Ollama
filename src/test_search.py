"""
Скрипт: src/test_search.py
Назначение: Верификация семантического поиска в ChromaDB (Top-K) с замером Latency в миллисекундах.
"""

import sys
import time
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    QUERY_PREFIX,
    TOP_K_CHUNKS,
    SIMILARITY_THRESHOLD
)


def search_chroma(
    query_text: str,
    model: SentenceTransformer,
    collection: chromadb.Collection,
    top_k: int = TOP_K_CHUNKS
) -> Dict[str, Any]:
    """
    Выполняет полный цикл:
    1. Замер времени старта (time.perf_counter).
    2. Векторизация запроса с префиксом 'query: '.
    3. Поиск Top-K векторов в ChromaDB.
    4. Преобразование Cosine Distance в Cosine Similarity.
    5. Замер финального latency в мс.
    """
    start_time = time.perf_counter()

    # 1. Векторизация запроса
    prepared_query = f"{QUERY_PREFIX}{query_text}"
    query_embedding = model.encode(
        [prepared_query],
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True
    ).tolist()

    # 2. Поиск в ChromaDB
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    # Замер времени обработки запроса
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # 3. Извлечение результатов и пересчет скоров
    retrieved_items = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        # В ChromaDB при cosine-метрике возвращается косинусное расстояние (1 - similarity)
        similarity_score = round(1.0 - dist, 4)
        retrieved_items.append({
            "source_file": meta.get("source_file", "unknown"),
            "chunk_index": meta.get("chunk_index", -1),
            "similarity_score": similarity_score,
            "text": doc
        })

    top_score = retrieved_items[0]["similarity_score"] if retrieved_items else 0.0
    is_known = top_score >= SIMILARITY_THRESHOLD

    return {
        "query": query_text,
        "latency_ms": latency_ms,
        "top_k": top_k,
        "top_score": top_score,
        "is_known": is_known,
        "results": retrieved_items
    }


def main():
    print("= - test_search.py:92" * 70)
    print(f"ТЕСТИРОВАНИЕ ПОИСКА CHROMADB (TOP_K = {TOP_K_CHUNKS}, ПОРОГ = {SIMILARITY_THRESHOLD}) - test_search.py:93")
    print("= - test_search.py:94" * 70)

    # Загрузка клиента и коллекции
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_collection(name=COLLECTION_NAME)

    print(f"[*] Загрузка модели: {EMBEDDING_MODEL_NAME}... - test_search.py:100")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print(f"[+] Подключено к коллекции '{COLLECTION_NAME}' (всего чанков: {collection.count()})\n - test_search.py:102")

    test_queries = [
        "Какой уникальный объект создал Чу-Гон Дар на планете Пирос?",
        "Кто сражался в Дуэли на Пиросе между Орионом Келом и Велгором?",
        "Как был захвачен Звездный Скиталец?",
        "Кто находился в Звездном Скиталце когда он был захвачен?",
        "Какая погода сегодня в Париже?"  # Проверка отсечения неизвестного вопроса
    ]

    for q_idx, query in enumerate(test_queries, start=1):
        output = search_chroma(query, model, collection, top_k=TOP_K_CHUNKS)
        
        print(f"────────────────────────────────────────────────────────────────────── - test_search.py:115")
        print(f"[Запрос {q_idx}]: \"{output['query']}\" - test_search.py:116")
        print(f"⏱ Время выполнения (Latency): {output['latency_ms']} мс - test_search.py:117")
        print(f"🎯 Top1 Скор: {output['top_score']} | Прошел порог ({SIMILARITY_THRESHOLD}): {output['is_known']} - test_search.py:118")
        print(f"Найденные Top{output['top_k']} фрагменты: - test_search.py:119")

        for rank, item in enumerate(output["results"], start=1):
            snippet = item["text"].replace("\n", " ")[:150]
            print(f"#{rank} | Сходство: {item['similarity_score']:.4f} | Файл: {item['source_file']} - test_search.py:123")
            print(f"Фрагмент: \"{snippet}...\"\n - test_search.py:124")

    print("= - test_search.py:126" * 70)


if __name__ == "__main__":
    main()