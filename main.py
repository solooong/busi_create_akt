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


def main(root_dir: str, trigger: str = "ДДУ"):
    """
    Главная функция консольного прототипа.
    1. Обходит корневую папку, находит и распаковывает ZIP-архивы.
    2. Находит все PDF-файлы, в имени которых есть триггер (по умолчанию "ДДУ").
    3. Парсит каждый PDF и собирает данные участников.
    4. Сохраняет результат в Excel в текущей директории.
    """
    logger.info(f"Запуск обработки. Корневая папка: {root_dir}")
    if not os.path.isdir(root_dir):
        logger.error(f"Указанная папка не существует: {root_dir}")
        sys.exit(1)

    # Шаг 1: извлечение из ZIP и получение списка PDF с триггером
    pdf_files = process_folder(root_dir, trigger=trigger)
    if not pdf_files:
        logger.warning("Не найдено ни одного PDF-файла для обработки. Завершение.")
        return

    # Шаг 2: парсинг каждого PDF
    parser = DDUParser()
    # Конфиг парсера (можно позже вынести в общий конфиг)
    parser_config = {
        'trigger_section': 'участники долевого строительства'
    }
    all_participants = []
    for pdf_path in pdf_files:
        logger.info(f"Обрабатывается PDF: {pdf_path}")
        participants = parser.parse(pdf_path, parser_config)
        if participants:
            logger.info(f"  Найдено участников: {len(participants)}")
            all_participants.extend(participants)
        else:
            logger.warning(f"  Участники не извлечены из {pdf_path}")

    if not all_participants:
        logger.warning("Ни одного участника не извлечено из всех PDF. Excel не будет создан.")
        return

    # Шаг 3: сохранение в Excel
    writer = ExcelWriter()
    # Сохраняем в текущей папке, имя с датой
    output_path = writer.save(all_participants)
    logger.info(f"Готово! Результат сохранён в {output_path}")


if __name__ == "__main__":
    # Если передан аргумент командной строки, используем его как корневую папку
    if len(sys.argv) > 1:
        root_folder = sys.argv[1]
    else:
        # По умолчанию — текущая рабочая директория
        root_folder = os.getcwd()
        logger.info(f"Корневая папка не указана, используется текущая: {root_folder}")
    main(root_folder)