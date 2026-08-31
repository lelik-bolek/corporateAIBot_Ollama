"""
Скрипт: src/build_index.py
Назначение: Чанкинг документов и построение персистентной векторной базы ChromaDB.
Модель эмбеддингов: intfloat/multilingual-e5-base (префикс 'passage: ')
"""

import sys
import time
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
    CHUNK_OVERLAP
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


if __name__ == "__main__":
    build_and_save_index()