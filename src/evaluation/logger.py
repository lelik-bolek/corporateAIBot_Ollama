"""
Модуль: src/evaluation/logger.py
Назначение: Асинхронное JSON Lines логирование для оценки качества RAG-пайплайна
            (замеры latency, scores, retrieval hit rate, faithfulness).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.config import (
    EVAL_LOGS_DIR,
    DEFAULT_APP_VERSION,
    TOP_K_CHUNKS,
    SIMILARITY_THRESHOLD,
    EMBEDDING_MODEL_NAME,
    LLM_MODEL
)


class EvalLogger:
    def __init__(self, version: str = DEFAULT_APP_VERSION):
        self.log_dir = EVAL_LOGS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.version = version
        self.log_file = self.log_dir / f"eval_runs_{self.version}.jsonl"

    def log_interaction(self, payload: Dict[str, Any]) -> None:
        """
        Асинхронно дописывает запись об интеракции в формате JSON Lines.
        Вызывается через FastAPI BackgroundTasks без блокировки HTTP-ответа.
        """
        # Гарантируем наличие метаданных окружения
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        payload["app_version"] = self.version

        if "pipeline_params" not in payload:
            payload["pipeline_params"] = {
                "embedding_model": EMBEDDING_MODEL_NAME,
                "top_k": TOP_K_CHUNKS,
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "llm_model": LLM_MODEL
            }

        try:
            with open(self.log_file, mode="a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[!] Ошибка записи в evaluation log ({self.log_file}): {e} - logger.py:50")