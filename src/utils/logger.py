"""
Модуль: src/utils/logger.py
Назначение: Централизованный системный логгер приложения (System Observability).
            Логирует все действия: старт, шаги пайплайна, сетевые запросы,
            предупреждения и любые типы ошибок.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from src.config import SYSTEM_LOG_DIR, SYSTEM_LOG_FILE

# Создаем системную директорию, если отсутствует
SYSTEM_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Формат системного лога: Дата Время | Уровень | Имя модуля | Сообщение
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "corporate_rag") -> logging.Logger:
    """Создает и возвращает сконфигурированный экземпляр логгера."""
    logger = logging.getLogger(name)

    # Предотвращаем дублирование логов при повторных вызовах
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    # 1. Запись в файл logs/system/app.log с ротацией (макс 10 МБ, 5 копий)
    file_handler = RotatingFileHandler(
        filename=SYSTEM_LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)

    # 2. Вывод в консоль (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Глобальный логгер
sys_logger = setup_logger()