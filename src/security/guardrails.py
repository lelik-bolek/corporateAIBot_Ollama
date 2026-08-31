"""
Модуль: src/security/guardrails.py
Назначение: Высокоуровневый оркестратор контуров защиты (Guardrails Manager).
Поддерживает три режима:
  - 'none': Защита отключена (для демонстрации атаки и уязвимости).
  - 'pre_only': Работает только системная изоляция в промпте.
  - 'full': Полная защита (Input Filter -> Chunk Filter -> Prompt Isolation -> Output Sanitizer).
"""

from typing import List, Dict, Any, Tuple
from src.security.filters import (
    check_input_injection,
    sanitize_context_chunks,
    sanitize_output,
    verify_grounding
)


class SecurityManager:
    def __init__(self, mode: str = "full"):
        self.mode = mode.lower()

    def process_input(self, query: str) -> Tuple[bool, str]:
        """
        Проверка запроса на этапе Input Sanitization.
        Возвращает (is_blocked, reason).
        """
        if self.mode != "full":
            return False, ""

        if check_input_injection(query):
            return True, "Обнаружена прямая попытка инъекции инструкций в запросе."

        return False, ""

    def process_chunks(self, chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Проверка и очистка извлеченных чанков (Chunk Sanitization).
        Возвращает (безопасные_чанки, признак_детекции_вредоноса).
        """
        if self.mode != "full":
            return chunks, False

        return sanitize_context_chunks(chunks)

    def process_output(
        self,
        answer: str,
        cot: str,
        chunks: List[Dict[str, Any]],
        confidence_score: float
    ) -> Tuple[str, str, bool, bool]:
        """
        Постобработка генерации (Output Guardrail & Grounding).
        Возвращает:
          (final_answer, final_cot, is_known, security_triggered)
        """
        if self.mode == "none":
            # В режиме без защиты ничего не скрываем, проверяем только наивный отказ
            is_known = not any(m in answer.lower() for m in ["я не знаю", "нет информации"])
            return answer, cot, is_known, False

        # Санитизация answer и chain_of_thought
        clean_answer, clean_cot, triggered = sanitize_output(answer, cot)

        if triggered:
            return clean_answer, clean_cot, False, True

        # Проверка обоснованности (Grounding check)
        is_grounded = verify_grounding(clean_answer, chunks, confidence_score)

        return clean_answer, clean_cot, is_grounded, False