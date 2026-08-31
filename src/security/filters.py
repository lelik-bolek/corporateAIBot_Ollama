"""
Модуль: src/security/filters.py
Назначение: Низкоуровневые фильтры безопасности для защиты от промпт-инъекций
            и предотвращения утечек чувствительных корпоративных данных.

1. Сквозная фильтрация: санитизируются ОБА поля — и `answer`, и `chain_of_thought`.
   При детекции утечки CoT заменяется на заглушку аудита безопасности.
2. Grounding Verification: строгая двухфакторная проверка опоры ответа на контекст
   для предотвращения ложноположительного флага `is_known: true`.
3. Параметры и константы берутся строго из src.config.
"""

import re
from typing import List, Tuple, Dict, Any

from src.config import (
    COMPILED_INJECTIONS,
    COMPILED_LEAKS,
    REFUSAL_MARKERS,
    SIMILARITY_THRESHOLD,
    GROUNDING_OVERLAP_THRESHOLD,
    GROUNDING_MIN_WORD_LENGTH,
    SECURITY_BLOCKED_ANSWER,
    SECURITY_BLOCKED_COT,
)


# ==============================================================================
# 1. ФИЛЬТРАЦИЯ ВХОДЯЩИХ ДАННЫХ И КОНТЕКСТА
# ==============================================================================
def check_input_injection(query: str) -> bool:
    """Проверяет входящий запрос пользователя на явные попытки инъекций."""
    return any(pattern.search(query) for pattern in COMPILED_INJECTIONS)


def sanitize_context_chunks(chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
    """Отсеивает чанки с непрямыми инъекциями или утечками."""
    cleaned_chunks = []
    poison_detected = False

    for ch in chunks:
        text = ch.get("text", "")
        has_injection = any(p.search(text) for p in COMPILED_INJECTIONS)
        has_canary = any(p.search(text) for p in COMPILED_LEAKS)

        if has_injection or has_canary:
            poison_detected = True
            continue

        cleaned_chunks.append(ch)

    return cleaned_chunks, poison_detected


# ==============================================================================
# 2. ФИЛЬТРАЦИЯ ВЫВОДА (ANSWER + CHAIN_OF_THOUGHT)
# ==============================================================================
def sanitize_output(answer: str, cot: str) -> Tuple[str, str, bool]:
    """
    Устранение замечания 1: проверяет на утечки И поле `answer`, И поле `chain_of_thought`.
    При обнаружении канарейки (swordfish, токены, пароли) ответ заменяется на отказ,
    а цепочка рассуждений скрывается служебной заглушкой безопасности.
    """
    leak_detected = any(p.search(answer) for p in COMPILED_LEAKS)

    if not leak_detected:
        leak_detected = any(p.search(cot) for p in COMPILED_LEAKS)

    if leak_detected:
        return SECURITY_BLOCKED_ANSWER, SECURITY_BLOCKED_COT, True

    return answer, cot, False


# ==============================================================================
# 4. ВЕРИФИКАЦИЯ ОПОРЫ НА КОНТЕКСТ (GROUNDING)
# ==============================================================================
def verify_grounding(answer: str, context_chunks: List[Dict[str, Any]], confidence_score: float) -> bool:
    """
    Проверяет, опирается ли ответ на контекст.
    Флаг `is_known: true` выставляется ТОЛЬКО если:
      1. Скор семантического сходства >= ... .
      2. Модель не выдала явную фразу отказа.
      3. Использован реальный контекст чанков (проверка лексического перекрытия).
    """
    if confidence_score < SIMILARITY_THRESHOLD or not context_chunks:
        return False

    low_answer = answer.lower().strip()

    if any(marker in low_answer for marker in REFUSAL_MARKERS):
        return False

    regex_pattern = rf"\b[а-яёa-z]{{{GROUNDING_MIN_WORD_LENGTH},}}\b"

    answer_words = set(re.findall(regex_pattern, low_answer))
    if not answer_words:
        return False

    context_text = " ".join([ch.get("text", "").lower() for ch in context_chunks])
    context_words = set(re.findall(regex_pattern, context_text))

    overlap = answer_words.intersection(context_words)
    overlap_ratio = len(overlap) / len(answer_words)

    return overlap_ratio >= GROUNDING_OVERLAP_THRESHOLD