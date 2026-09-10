"""
Скрипт: src/build_index.py
Назначение: Чанкинг документов и построение персистентной векторной базы ChromaDB.
Модель эмбеддингов: intfloat/multilingual-e5-base (префикс 'passage: ')
"""

import sys
import time
import pickle
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi
import nltk
from nltk.stem.snowball import SnowballStemmer

# Гарантия корректной кодировки UTF-8 в консоли Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.config import (
    KB_DIR,
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    PASSAGE_PREFIX,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    BM25_INDEX_PATH,
)


def load_and_chunk_documents(kb_dir: Path) -> List[Dict[str, Any]]:
    """Считывает все .txt файлы из базы знаний и разбивает их на чанки с метаданными."""
    if not kb_dir.exists():
        raise FileNotFoundError(f"Каталог базы знаний {kb_dir} не найден!")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks_data: List[Dict[str, Any]] = []
    txt_files = sorted(list(kb_dir.glob("*.txt")))

    if not txt_files:
        raise ValueError(f"В каталоге {kb_dir} не найдено .txt файлов для индексации!")

    chunk_global_id = 0
    for file_path in txt_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            continue

        raw_chunks = splitter.split_text(content)
        for chunk_idx, text_chunk in enumerate(raw_chunks):
            clean_chunk = text_chunk.strip()
            if len(clean_chunk) < 20:
                continue

            chunks_data.append({
                "id": f"chunk_{chunk_global_id}",
                "text": clean_chunk,
                "metadata": {
                    "source_file": file_path.name,
                    "chunk_index": chunk_idx,
                    "char_count": len(clean_chunk)
                }
            })
            chunk_global_id += 1

    return chunks_data


# ==============================================================================
# ТОКЕНИЗАЦИЯ ДЛЯ BM25 (SPARSE RETRIEVAL) — добавлено Step 3
# ==============================================================================
_TOKEN_PATTERN = r"[a-zA-Z0-9_\-\.\$]+|[а-яА-ЯёЁ]+"
_RU_STEMMER = SnowballStemmer("russian")


def tokenize_for_bm25(text: str) -> list[str]:
    """
    Выделяет токены для разрежённого индекса BM25.
    - Кириллические токены -> SnowballStemmer("russian")
    - Латиница, спецсимволы, цифры -> .lower() без искажения основы
    """
    import re
    raw_tokens = re.findall(_TOKEN_PATTERN, text)
    result = []
    for tok in raw_tokens:
        if re.search(r"[а-яА-ЯёЁ]", tok):
            result.append(_RU_STEMMER.stem(tok.lower()))
        else:
            result.append(tok.lower())
    return result


def build_and_save_index():
    print("= - build_index.py:78" * 70)
    print("ГЕНЕРАЦИЯ ВЕКТОРНОГО ХРАНИЛИЩА CHROMADB (intfloat/multilinguale5base) - build_index.py:79")
    print("= - build_index.py:80" * 70)

    # 1. Чанкинг документов
    print(f"[*] Считывание файлов из: {KB_DIR} - build_index.py:83")
    chunks = load_and_chunk_documents(KB_DIR)
    print(f"[+] Всего сформировано чанков: {len(chunks)} - build_index.py:85")

    # 2. Инициализация клиента ChromaDB
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Сброс старой коллекции при переиндексации
    try:
        chroma_client.delete_collection(name=COLLECTION_NAME)
        print(f"[*] Старая коллекция '{COLLECTION_NAME}' удалена. - build_index.py:94")
    except Exception:
        pass

    # Создание коллекции с косинусной метрикой расстояния
    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # 3. Загрузка модели эмбеддингов
    print(f"[*] Загрузка модели эмбеддингов: {EMBEDDING_MODEL_NAME}... - build_index.py:105")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # Подготовка текстов с обязательным префиксом passage: для модели E5
    passage_texts = [f"{PASSAGE_PREFIX}{item['text']}" for item in chunks]

    # 4. Векторизация и запись в ChromaDB
    print(f"[*] Генерация эмбеддингов и запись в ChromaDB для {len(passage_texts)} фрагментов... - build_index.py:112")
    start_time = time.perf_counter()

    batch_size = 64
    total_chunks = len(chunks)

    for i in range(0, total_chunks, batch_size):
        batch_end = min(i + batch_size, total_chunks)
        batch_passages = passage_texts[i:batch_end]
        batch_chunks = chunks[i:batch_end]

        # Генерация эмбеддингов батчем с нормализацией для косинусного пространства
        batch_embeddings = model.encode(
            batch_passages,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).tolist()

        collection.add(
            ids=[c["id"] for c in batch_chunks],
            embeddings=batch_embeddings,
            documents=[c["text"] for c in batch_chunks],
            metadatas=[c["metadata"] for c in batch_chunks]
        )
        print(f"> Загружено {batch_end}/{total_chunks} чанков... - build_index.py:138")

    elapsed_time = time.perf_counter() - start_time
    print(f"[+] Индексация успешно завершена за {elapsed_time:.2f} сек. - build_index.py:141")
    print(f"[+] Всего записей в ChromaDB: {collection.count()} - build_index.py:142")
    print(f"[+] Путь к хранилищу: {CHROMA_DIR} - build_index.py:143")
    print("= - build_index.py:144" * 70)

    # ==========================================================================
    # 5. ПОСТРОЕНИЕ РАЗРЕЖЁННОГО ИНДЕКСА BM25 — добавлено Step 3
    # ==========================================================================
    print(f"\n[*] Построение разрежённого индекса BM25... - build_index.py:bm25")
    bm25_start = time.perf_counter()

    tokenized_corpus = [tokenize_for_bm25(item["text"]) for item in chunks]
    bm25_instance = BM25Okapi(tokenized_corpus)

    bm25_payload = {
        "bm25": bm25_instance,
        "chunks": [
            {
                "chunk_id": str(i),
                "text": doc["text"],
                "source_file": doc["metadata"]["source_file"]
            }
            for i, doc in enumerate(chunks)
        ]
    }

    BM25_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(bm25_payload, f)

    bm25_elapsed = time.perf_counter() - bm25_start
    print(f"[+] BM25 индекс сохранён: {BM25_INDEX_PATH} - build_index.py:bm25")
    print(f"[+] Размер корпуса BM25: {len(tokenized_corpus)} документов")
    print(f"[+] Построение BM25 заняло: {bm25_elapsed:.2f} сек.")


if __name__ == "__main__":
    build_and_save_index()