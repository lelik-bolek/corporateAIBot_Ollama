import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

# Принудительная установка кодировки UTF-8 для вывода в консоль Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Корректное добавление корня проекта в sys.path для кроссплатформенного запуска
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import EVAL_LOGS_DIR


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Вычисляет процентиль (P50, P95) без использования сторонних библиотек."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    if c < len(sorted_vals):
        return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])
    return sorted_vals[f]


def analyze_latencies():
    if not EVAL_LOGS_DIR.exists():
        print(f"[!] Директория логов не найдена: {EVAL_LOGS_DIR} - latency_calculator.py:35")
        sys.exit(1)

    # Находим все файлы журналов в EVAL_LOGS_DIR
    log_files = sorted(list(EVAL_LOGS_DIR.glob("eval_runs_*.jsonl")))
    if not log_files:
        print(f"[!] Файлы eval_runs_*.jsonl не найдены в {EVAL_LOGS_DIR} - latency_calculator.py:41")
        sys.exit(1)

    # Структура: grouped_data[(date_str, app_version)] -> {retrieval: [], llm: [], total: [], sec_triggered: 0, count: 0}
    grouped_data: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {
        "retrieval": [],
        "llm": [],
        "total": [],
        "sec_triggered": 0,
        "count": 0
    })

    total_lines = 0

    for file_path in log_files:
        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Извлечение даты и версии
                timestamp_raw = entry.get("timestamp", "")
                date_str = timestamp_raw[:10] if len(timestamp_raw) >= 10 else "UNKNOWN_DATE"
                version = entry.get("app_version", "unknown_ver")
                
                group_key = (date_str, version)

                metrics = entry.get("metrics", {})
                ret_lat = metrics.get("retrieval_latency_ms")
                llm_lat = metrics.get("llm_latency_ms")
                tot_lat = metrics.get("total_latency_ms", (ret_lat or 0) + (llm_lat or 0))

                if ret_lat is not None and llm_lat is not None:
                    bucket = grouped_data[group_key]
                    bucket["retrieval"].append(float(ret_lat))
                    bucket["llm"].append(float(llm_lat))
                    bucket["total"].append(float(tot_lat))
                    bucket["count"] += 1
                    if entry.get("security_triggered", False):
                        bucket["sec_triggered"] += 1
                    total_lines += 1

    if not grouped_data:
        print("[!] Не удалось извлечь ни одной валидной записи с метриками. - latency_calculator.py:90")
        return

    # Вывод результатов в виде структурированной таблицы
    print(f"\n{'=' * 95} - latency_calculator.py:94")
    print(f"{'ДАТА':<12} | {'ВЕРСИЯ':<8} | {'ЗАПРОСОВ':<8} | {'RETRIEVAL (P50 / Ср / P95)':<26} | {'LLM (P50 / Ср / P95)':<24} | {'БЛОК ИБ (от общего числа запросов)'} - latency_calculator.py:95")
    print(f"{'' * 95} - latency_calculator.py:96")

    for (date_str, version), data in sorted(grouped_data.items(), key=lambda x: (x[0][0], x[0][1])):
        n = data["count"]
        ret = data["retrieval"]
        llm = data["llm"]

        avg_ret = sum(ret) / n
        p50_ret = calculate_percentile(ret, 50)
        p95_ret = calculate_percentile(ret, 95)

        avg_llm = sum(llm) / n
        p50_llm = calculate_percentile(llm, 50)
        p95_llm = calculate_percentile(llm, 95)

        sec_percent = (data["sec_triggered"] / n) * 100

        ret_str = f"{p50_ret:5.1f} / {avg_ret:5.1f} / {p95_ret:5.1f} ms"
        llm_str = f"{p50_llm:5.1f} / {avg_llm:5.1f} / {p95_llm:5.1f} ms"

        print(f"{date_str:<12} | {version:<8} | {n:<8} | {ret_str:<26} | {llm_str:<24} | {data['sec_triggered']} ({sec_percent:.0f}%) - latency_calculator.py:116")

    print(f"{'=' * 95} - latency_calculator.py:118")
    print(f"Всего проанализировано валидных запросов: {total_lines}\n - latency_calculator.py:119")


if __name__ == "__main__":
    analyze_latencies()