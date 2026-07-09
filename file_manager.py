# file_manager.py
import os
import zipfile
import shutil
import logging
from pathlib import Path
from typing import List, Optional

# Настройка логирования (можно позже вынести в общий конфиг)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_zip_files(root_dir: str, max_depth: int = 2) -> List[str]:
    """
    Обходит каталог root_dir и все подкаталоги до глубины max_depth,
    собирая пути всех файлов с расширением .zip (регистр не учитывается).
    """
    zip_files = []
    root_path = Path(root_dir).resolve()
    if not root_path.exists():
        logger.error(f"Корневая папка не существует: {root_path}")
        return zip_files

    logger.info(f"Поиск ZIP-файлов в {root_path} (глубина: {max_depth})...")
    for current_root, dirs, files in os.walk(root_path):
        # Вычисляем текущую глубину относительно root_path
        relative_depth = len(Path(current_root).relative_to(root_path).parts)
        if relative_depth > max_depth:
            # Пропускаем вложенность глубже заданной
            dirs.clear()
            continue
        for file in files:
            if file.lower().endswith('.zip'):
                full_path = os.path.join(current_root, file)
                zip_files.append(full_path)
                logger.debug(f"Найден ZIP: {full_path}")
    logger.info(f"Найдено ZIP-архивов: {len(zip_files)}")
    return zip_files


def extract_zip(zip_path: str, extract_to: str) -> bool:
    """
    Извлекает содержимое zip_path в папку extract_to.
    Возвращает True при успехе, False при ошибке.
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Создаём целевую папку, если её нет
            os.makedirs(extract_to, exist_ok=True)
            zf.extractall(extract_to)
            logger.info(f"Распакован: {zip_path} -> {extract_to}")
            return True
    except Exception as e:
        logger.error(f"Ошибка распаковки {zip_path}: {e}")
        return False


def find_files_with_trigger(directory: str, trigger: str) -> List[str]:
    """
    Рекурсивно ищет в directory файлы, в имени которых содержится
    подстрока trigger (без учёта регистра). Возвращает список полных путей.
    """
    matched = []
    directory_path = Path(directory)
    if not directory_path.exists():
        logger.warning(f"Папка для поиска не найдена: {directory_path}")
        return matched

    logger.info(f"Поиск файлов с триггером '{trigger}' в {directory_path}...")
    for root, _, files in os.walk(directory_path):
        for file in files:
            if trigger.lower() in file.lower():
                full_path = os.path.join(root, file)
                matched.append(full_path)
                logger.debug(f"Найден подходящий файл: {full_path}")
    logger.info(f"Найдено файлов с триггером '{trigger}': {len(matched)}")
    return matched


def process_folder(
    root_dir: str,
    trigger: str = "ДДУ",
    extract_base_dir: Optional[str] = None
) -> List[str]:
    """
    Основная функция для Шага 1:
    1. Ищет ZIP-архивы в root_dir (глубина 2).
    2. Распаковывает каждый архив в подпапку временной/локальной папки.
    3. Ищет в полученных файлах те, что содержат trigger в имени.
    4. Возвращает список путей к этим файлам.
    
    Параметры:
        root_dir: корневая папка для обхода (может быть сетевой)
        trigger: подстрока для фильтрации имён файлов (по умолчанию "ДДУ")
        extract_base_dir: папка для распаковки. Если None, создаётся
                         временная директория "extracted" внутри root_dir.
    """
    # Базовая папка для распаковки
    if extract_base_dir is None:
        extract_base_dir = os.path.join(root_dir, "_extracted")
        logger.info(f"Используется временная папка для распаковки: {extract_base_dir}")

    # Убедимся, что базовая папка существует
    os.makedirs(extract_base_dir, exist_ok=True)

    # Поиск ZIP
    zip_paths = find_zip_files(root_dir, max_depth=2)
    if not zip_paths:
        logger.warning("Не найдено ни одного ZIP-архива. Завершение.")
        return []

    # Распаковка каждого ZIP в отдельную папку
    extracted_dirs = []
    for zip_path in zip_paths:
        # Имя папки для распаковки = имя ZIP без расширения + суффикс для уникальности
        zip_name = os.path.splitext(os.path.basename(zip_path))[0]
        dest_dir = os.path.join(extract_base_dir, zip_name)
        # Если папка уже существует (например, от предыдущего запуска), добавим счётчик
        counter = 1
        original_dest_dir = dest_dir
        while os.path.exists(dest_dir):
            dest_dir = f"{original_dest_dir}_{counter}"
            counter += 1
        success = extract_zip(zip_path, dest_dir)
        if success:
            extracted_dirs.append(dest_dir)

    # Поиск файлов с заданным триггером во всех папках распаковки
    matched_files = []
    for ext_dir in extracted_dirs:
        files = find_files_with_trigger(ext_dir, trigger)
        matched_files.extend(files)

    logger.info(f"Итого файлов '{trigger}' для обработки: {len(matched_files)}")
    return matched_files


if __name__ == "__main__":
    # Тестовый запуск: передаём папку как аргумент командной строки
    import sys
    if len(sys.argv) > 1:
        test_root = sys.argv[1]
    else:
        test_root = "."  # текущая папка по умолчанию
    result = process_folder(test_root)
    print("\nНайденные файлы для обработки:")
    for f in result:
        print(f" - {f}")