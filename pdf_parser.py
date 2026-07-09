# pdf_parser.py
import re
import pdfplumber
from typing import List, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)


class BaseParser:
    """Базовый класс для парсеров PDF."""
    def parse(self, pdf_path: str, config: Dict) -> List[Dict]:
        raise NotImplementedError("Метод parse должен быть переопределён в подклассе")


class DDUParser(BaseParser):
    """
    Парсер для договора долевого участия (ДДУ).
    Извлекает данные участников долевого строительства.
    """
    
    # Стандартный маппинг: ключ в выходном словаре → возможные заголовки в первой колонке таблицы
    DEFAULT_FIELD_MAP = {
        'ФИО': ['фио', 'ф.и.о.', 'фамилия имя отчество', 'участник', 'дольщик', 'сторона-участник'],
        'телефон': ['телефон', 'тел.', 'контактный телефон', 'номер телефона'],
        'email': ['e-mail', 'email', 'эл. почта', 'почта', 'электронная почта'],
        'паспорт': ['паспорт', 'серия номер', 'документ удостоверяющий личность'],
        'адрес': ['адрес', 'место жительства', 'адрес регистрации'],
    }
    
    # Регулярки для извлечения данных из сплошного текста (fallback)
    RE_PATTERNS = {
        'ФИО': r'(?:ФИО|Ф\.И\.О\.|Участник|Дольщик)\s*[:;.]?\s*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)',
        'телефон': r'(?:тел(?:ефон)?\.?)\s*[:;.]?\s*(\+?\d[\d\s\-\(\)]{6,}\d)',
        'email': r'(?:e-?mail|эл\.?\s*почта)\s*[:;.]?\s*([\w\.-]+@[\w\.-]+\.\w+)',
    }

    def __init__(self):
        self.field_map = self.DEFAULT_FIELD_MAP.copy()
    
    def _normalize(self, text: str) -> str:
        return ' '.join(text.strip().lower().split())
    
    def _find_trigger_pages(self, pdf, trigger_text: str) -> List[int]:
        """Возвращает номера страниц (0-based), где встречается trigger_text."""
        pages = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and trigger_text.lower() in text.lower():
                pages.append(i)
                logger.debug(f"Триггер найден на странице {i+1}")
        return pages

    def _extract_from_tables(self, page, used_fields: Dict[str, str]) -> bool:
        """
        Ищет в таблицах на странице поля из used_fields.
        Если находит, заполняет значениями и возвращает True.
        """
        tables = page.extract_tables()
        found_any = False
        for table in tables:
            if not table:
                continue
            # Ищем строки, где первая ячейка соответствует одному из искомых заголовков
            for row in table:
                if not row or len(row) < 2:
                    continue
                cell0 = self._normalize(row[0] or '')
                cell1 = (row[1] or '').strip()
                if not cell0 or not cell1:
                    continue
                # Проверяем по всем полям, которые ещё не найдены
                for field_key, aliases in self.field_map.items():
                    if field_key in used_fields and used_fields[field_key]:
                        continue  # уже заполнено
                    if any(alias in cell0 for alias in aliases):
                        used_fields[field_key] = cell1
                        found_any = True
                        logger.debug(f"Из таблицы: {field_key} = {cell1}")
                        break
        return found_any

    def _extract_fallback(self, text: str, trigger_text: str) -> Dict[str, str]:
        """
        Извлекает данные из текста после trigger_text с помощью регулярных выражений.
        Возвращает словарь с ключами ФИО, телефон, email.
        """
        # Найдём позицию триггера и возьмём текст после него
        idx = text.lower().find(trigger_text.lower())
        if idx == -1:
            return {}
        after_text = text[idx + len(trigger_text):]
        
        result = {}
        for field, pattern in self.RE_PATTERNS.items():
            match = re.search(pattern, after_text, re.IGNORECASE)
            if match:
                result[field] = match.group(1).strip()
        return result

    def parse(self, pdf_path: str, config: Optional[Dict] = None) -> List[Dict]:
        """
        Основной метод парсинга PDF.
        config может содержать:
            - trigger_section: фраза для поиска (по умолчанию 'участники долевого строительства')
            - field_map: переопределение маппинга заголовков
        Возвращает список словарей с данными участников.
        """
        if config is None:
            config = {}
        
        trigger = config.get('trigger_section', 'участники долевого строительства')
        # Обновляем field_map, если передан в конфиге
        if 'field_map' in config:
            self.field_map = config['field_map']
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                trigger_pages = self._find_trigger_pages(pdf, trigger)
                if not trigger_pages:
                    logger.warning(f"Триггер '{trigger}' не найден в документе {pdf_path}")
                    return []
                
                participants = []
                # Обрабатываем каждую страницу с триггером отдельно
                for page_num in trigger_pages:
                    page = pdf.pages[page_num]
                    used_fields: Dict[str, str] = {}
                    
                    # Сначала пытаемся извлечь из таблиц
                    table_success = self._extract_from_tables(page, used_fields)
                    
                    # Если не все поля заполнены, пробуем fallback по тексту
                    if not table_success or any(k not in used_fields for k in ('ФИО', 'телефон', 'email')):
                        text = page.extract_text()
                        if text:
                            fallback_data = self._extract_fallback(text, trigger)
                            for k, v in fallback_data.items():
                                if k not in used_fields or not used_fields[k]:
                                    used_fields[k] = v
                    
                    # Если нашли хотя бы ФИО, формируем запись участника
                    if used_fields.get('ФИО'):
                        # Собираем дополнительные данные: все поля кроме ФИО, телефона и email
                        main_keys = {'ФИО', 'телефон', 'email'}
                        extra = {k: v for k, v in used_fields.items() if k not in main_keys and v}
                        participant = {
                            'ФИО': used_fields.get('ФИО', ''),
                            'телефон': used_fields.get('телефон', ''),
                            'email': used_fields.get('email', ''),
                            'доп_данные': extra if extra else ''
                        }
                        participants.append(participant)
                    else:
                        logger.warning(f"На странице {page_num+1} не удалось извлечь ФИО участника")
                
                return participants
                
        except Exception as e:
            logger.error(f"Ошибка при парсинге PDF {pdf_path}: {e}")
            return []


# Для обратной совместимости и удобного тестирования
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        test_pdf = sys.argv[1]
    else:
        print("Укажите путь к PDF файлу")
        sys.exit(1)
    
    parser = DDUParser()
    # пример конфига
    cfg = {
        'trigger_section': 'участники долевого строительства',
    }
    result = parser.parse(test_pdf, cfg)
    for i, p in enumerate(result, 1):
        print(f"\nУчастник {i}:")
        print(f"  ФИО: {p['ФИО']}")
        print(f"  Телефон: {p['телефон']}")
        print(f"  Email: {p['email']}")
        print(f"  Доп.данные: {p['доп_данные']}")