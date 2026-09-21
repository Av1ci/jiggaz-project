"""Запуск всего пайплайна: генерация -> очистка -> анализ."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import analyze, clean, generate_data  # noqa: E402

if __name__ == "__main__":
    generate_data.main()
    clean.main()
    analyze.main()
