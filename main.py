# main.py
import os
import sys
import logging
from pathlib import Path

# Импорты наших модулей
from file_manager import process_folder
from pdf_parser import DDUParser
from excel_writer import ExcelWriter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("processing.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")


def main(root_dir: str):
    """
    Главная функция консольного прототипа.
    1. Обходит корневую папку, находит и распаковывает ZIP-архивы.
    2. Находит все PDF-файлы, в имени которых есть триггер (по умолчанию "ДДУ").
    3. Парсит каждый PDF и собирает данные участников.
    4. Сохраняет результат в Excel в текущей директории.
    """
    logger.info(f"Запуск обработки. Корневая папка: {root_dir}")
    
    # Шаг 1: поиск и распаковка
    triggers = {"ДДУ", "Договор долевого участия"}  # можно добавить другие
    pdf_files = process_folder(root_dir, triggers=triggers)
    
    # Фильтруем только PDF
    pdf_files = [f for f in pdf_files if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.warning("Не найдено PDF-файлов для обработки.")
        return
    
    # Шаг 2: парсинг
    parser = DDUParser()
    # main.py (фрагмент)
    all_participants = []
    seen_participants = set()
    for pdf_path in pdf_files:
        logger.info(f"Обрабатывается PDF: {pdf_path}")
        participants = parser.parse(pdf_path)
        for p in participants:
            # Уникальный ключ: ФИО + дата рождения
            key = (p['ФИО'], p['доп_данные'].get('дата_рождения', ''))
            if key not in seen_participants:
                seen_participants.add(key)
                all_participants.append(p)    
    # Шаг 3: сохранение в Excel
    if all_participants:
        writer = ExcelWriter()
        output_path = writer.save(all_participants)
        logger.info(f"Готово! Результат сохранён в {output_path}")
    else:
        logger.warning("Ни одного участника не извлечено.")


if __name__ == "__main__":
    # Если передан аргумент командной строки, используем его как корневую папку
    if len(sys.argv) > 1:
        root_folder = sys.argv[1]
    else:
        # По умолчанию — текущая рабочая директория
        root_folder = os.getcwd()
        logger.info(f"Корневая папка не указана, используется текущая: {root_folder}")
    main(root_folder)