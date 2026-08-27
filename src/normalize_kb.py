"""
Скрипт: src/normalize_kb.py
Расположение: E:\AI_Workspace\corporateAIBot_Ollama\src\normalize_kb.py
Назначение: Глубокая нормализация текстовых файлов базы знаний в data/knowledge_base/

Устраняемые дефекты:
1. Схлопывание паразитных переносов строк внутри предложений и именных групп.
2. Удаление служебных маркеров: 'Слушать', '( информация о файле )', '[источник? ]'.
3. Притягивание оторванных знаков пунктуации, кавычек («...») и тире.
4. Восстановление естественных границ абзацев (\n\n) на основе терминальной пунктуации.
"""

import sys
import re
from pathlib import Path

# Принудительная установка кодировки UTF-8 для вывода в консоль Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ==============================================================================
# 1. ПУТИ К ДИРЕКТОРИЯМ
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
KB_DIR = BASE_DIR / "data" / "knowledge_base"


# ==============================================================================
# 2. АЛГОРИТМ ОЧИСТКИ И ВОССТАНОВЛЕНИЯ СВЯЗНОСТИ
# ==============================================================================
def clean_garbage_artifacts(text: str) -> str:
    """Удаляет служебный мусор Fandom MediaWiki и оторванные маркеры."""
    # 1. Удаление аудио-плашек и сносок файлов
    text = re.sub(r"Слушать\s*\(\s*информация о файле\s*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\s*информация о файле\s*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Слушать", "", text, flags=re.IGNORECASE)

    # 2. Удаление маркеров источников и незакрытых сносок вида 'источник? ]'
    text = re.sub(r"источник\?\s*\]?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\s*источник\s*\??\s*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\[править.*?\]", "", text, flags=re.IGNORECASE)

    return text


def repair_line_breaks(text: str) -> str:
    """Склеивает разорванные слова, дефисы и пунктуацию."""
    text = text.replace("\r\n", "\n")

    # Склеиваем слова с дефисом на стыке строк (например: "мужчина\n-\nчеловек" -> "мужчина-человек")
    text = re.sub(r"(\w+)\s*\n+\s*-\s*\n+\s*(\w+)", r"\1-\2", text)
    text = re.sub(r"(\w+)-\s*\n+\s*(\w+)", r"\1-\2", text)

    # Притягиваем открывающие и закрывающие кавычки
    text = re.sub(r"«\s*\n+\s*", " «", text)
    text = re.sub(r"\s*\n+\s*»", "» ", text)

    # Притягиваем оторванную пунктуацию (, . : ; ! ? )
    text = re.sub(r"\s*\n+\s*([,.:;!?…])", r"\1", text)

    # Удаляем строки, состоящие только из одиночных разделителей
    lines = [line.strip() for line in text.split("\n")]
    valid_lines = [l for l in lines if l and l not in ["—", "―", "-", "–", ":", "]"]]

    return "\n".join(valid_lines)


def reconstruct_paragraphs(text: str) -> str:
    """
    Формирует непрерывный поток предложений внутри смысловых абзацев.
    Разделяет текст на абзацы (\\n\\n) только при наличии терминальных знаков.
    """
    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not raw_lines:
        return ""

    paragraphs = []
    current_block = []

    terminal_punct = re.compile(r".*[.!?…»]$")
    dialog_speaker = re.compile(r"^[—―]\s*[А-ЯЁA-Z]")

    for line in raw_lines:
        # Если строка — подпись автора цитаты (например: "―Орион Кел Элдору Сайрусу")
        if line.startswith(("—", "―")) and len(line) < 80:
            if current_block:
                current_block.append(line)
                paragraphs.append(" ".join(current_block))
                current_block = []
            else:
                paragraphs.append(line)
            continue

        if not current_block:
            current_block.append(line)
        else:
            prev_line = current_block[-1]
            # Если предыдущая строка НЕ завершена точкой/восклицанием — склеиваем через пробел
            if not terminal_punct.match(prev_line):
                current_block.append(line)
            else:
                # Если мысль завершена и накоплен достаточный объем блока (>200 символов) — закрываем абзац
                assembled_len = sum(len(s) for s in current_block)
                if assembled_len > 220:
                    paragraphs.append(" ".join(current_block))
                    current_block = [line]
                else:
                    current_block.append(line)

    if current_block:
        paragraphs.append(" ".join(current_block))

    # Сборка финального текста с нормализацией пробельных символов
    result = "\n\n".join(paragraphs)
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"\s+([,.:;!?])", r"\1", result)

    return result.strip()


def normalize_kb_file(file_path: Path) -> bool:
    """Обрабатывает и перезаписывает целевой .txt файл."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            return False

        step1 = clean_garbage_artifacts(content)
        step2 = repair_line_breaks(step1)
        cleaned_text = reconstruct_paragraphs(step2)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)

        return True
    except Exception as e:
        print(f"[!] Ошибка обработки {file_path.name}: {e} - normalize_kb.py:142")
        return False


def main():
    print("= - normalize_kb.py:147" * 70)
    print(f"[*] ЗАПУСК ГЛУБОКОЙ НОРМАЛИЗАЦИИ БАЗЫ ЗНАНИЙ - normalize_kb.py:148")
    print(f"[*] Целевая папка: {KB_DIR} - normalize_kb.py:149")
    print("= - normalize_kb.py:150" * 70)

    if not KB_DIR.exists():
        print(f"[!] Ошибка: Каталог {KB_DIR} не найден! - normalize_kb.py:153")
        return

    txt_files = sorted(list(KB_DIR.glob("*.txt")))
    if not txt_files:
        print(f"[!] В каталоге {KB_DIR} нет файлов .txt для обработки. - normalize_kb.py:158")
        return

    success_count = 0
    for idx, file_path in enumerate(txt_files, start=1):
        print(f"[{idx:02d}/{len(txt_files):02d}] Нормализация: {file_path.name} ... - normalize_kb.py:163", end="")
        if normalize_kb_file(file_path):
            success_count += 1
            print("[OK] - normalize_kb.py:166")
        else:
            print("[FAIL] - normalize_kb.py:168")

    print("\n - normalize_kb.py:170" + "=" * 70)
    print(f"[+] Нормализация завершена: успешно обработано {success_count}/{len(txt_files)} файлов. - normalize_kb.py:171")
    print("= - normalize_kb.py:172" * 70)


if __name__ == "__main__":
    main()