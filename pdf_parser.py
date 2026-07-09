# # pdf_parser.py
# import re
# import pdfplumber
# from typing import List, Dict, Optional
# import logging

# logger = logging.getLogger(__name__)


# class BaseParser:
#     """Базовый класс для парсеров PDF."""
#     def parse(self, pdf_path: str, config: Dict) -> List[Dict]:
#         raise NotImplementedError("Метод parse должен быть переопределён в подклассе")


# class DDUParser(BaseParser):
#     """
#     Парсер для договора долевого участия (ДДУ).
#     Извлекает данные участников долевого строительства из раздела
#     'Участники долевого строительства' и паспортные данные из шапки.
#     """

#     PERSON_HEADER = re.compile(
#         r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s*,\s*'
#         r'(\d{2}\.\d{2}\.\d{4})\s*г\.\s*р\.',
#         re.IGNORECASE
#     )

#     FIELD_PATTERNS = {
#         'паспорт': r'паспорт:\s*(\d{2}\s*\d{2}\s*\d{6})',
#         'дата_выдачи': r'выдан\s+(\d{2}\.\d{2}\.\d{4})\s*г',
#         # Убраны альтернативы \n и $, теперь захват до "код подразделения"
#         'кем_выдан': r'выдан\s+\d{2}\.\d{2}\.\d{4}\s*г[.,]?\s*(.+?)\s*,?\s*код\s+подразделения',
#         'код_подразделения': r'код подразделения:\s*(\d{3}-\d{3})',
#         'адрес_проживания': r'проживающ(?:ий|ая)\s+по адресу:\s*(.+?)\s*(?:\(для корреспонденции|СНИЛС|ИНН|$|\n)',
#         'корр_адрес': r'для корреспонденции:\s*(.+?)\)',
#         'СНИЛС': r'СНИЛС:\s*(\d{3}-\d{3}-\d{3}\s?\d{2})',
#         'ИНН': r'ИНН:\s*(\d{10,12})',
#         'email': r'([\w\.-]+@[\w\.-]+\.\w+)',
#         'телефон': r'^\s*((?:\+7|8)\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})\s*$',
#     }

#     def __init__(self):
#         pass

#     def _find_trigger_pages(self, pdf, trigger_text: str) -> List[int]:
#         pages = []
#         for i, page in enumerate(pdf.pages):
#             text = page.extract_text()
#             if text and trigger_text.lower() in text.lower():
#                 pages.append(i)
#         return pages

#     def _extract_participant_block(self, text: str, trigger_text: str) -> Optional[str]:
#         idx = text.lower().find(trigger_text.lower())
#         if idx == -1:
#             return None
#         block = text[idx + len(trigger_text):]
#         end_match = re.search(r'_{3,}', block)
#         if end_match:
#             block = block[:end_match.start()]
#         return block.strip()

#     def _extract_fields_from_block(self, block_text: str) -> Dict[str, str]:
#         data = {}
#         person_match = self.PERSON_HEADER.search(block_text)
#         if not person_match:
#             return data
#         surname, name, patronymic = person_match.group(1), person_match.group(2), person_match.group(3)
#         data['ФИО'] = f"{surname} {name} {patronymic}"
#         data['дата_рождения'] = person_match.group(4)

#         for field, pattern in self.FIELD_PATTERNS.items():
#             if field in ('ФИО', 'дата_рождения'):
#                 continue
#             match = re.search(pattern, block_text, re.IGNORECASE | re.DOTALL)
#             if match:
#                 value = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
#                 value = re.sub(r'\s+', ' ', value).strip()
#                 data[field] = value

#         if not data.get('телефон'):
#             phone_match = re.search(r'(\+7[\d\s\-\(\)]{9,})', block_text)
#             if phone_match:
#                 data['телефон'] = phone_match.group(1).strip()
#         return data

#     def _extract_passport_from_first_page(self, first_page_text: str, full_name: str) -> Optional[str]:
#         """
#         Ищет паспортные данные для указанного ФИО в тексте первой страницы (шапке).
#         Возвращает номер паспорта или None.
#         """
#         if not first_page_text:
#             return None
#         # Ищем ФИО
#         name_pattern = re.escape(full_name)
#         name_match = re.search(name_pattern, first_page_text, re.IGNORECASE)
#         if not name_match:
#             return None
#         # Берём фрагмент после имени длиной 400 символов (вся инфа о человеке)
#         block = first_page_text[name_match.start():name_match.start()+400]
#         # Ищем паспорт в этом блоке
#         passport_match = re.search(r'паспорт:\s*(\d{2}\s*\d{2}\s*\d{6})', block, re.IGNORECASE)
#         if passport_match:
#             return re.sub(r'\s+', ' ', passport_match.group(1).strip())
#         return None

#     def parse(self, pdf_path: str, config: Optional[Dict] = None) -> List[Dict]:
#         if not pdf_path.lower().endswith('.pdf'):
#             logger.warning(f"Пропущен не-PDF файл: {pdf_path}")
#             return []

#         trigger = config.get('trigger_section', 'участники долевого строительства') if config else 'участники долевого строительства'

#         try:
#             with pdfplumber.open(pdf_path) as pdf:
#                 trigger_pages = self._find_trigger_pages(pdf, trigger)
#                 if not trigger_pages:
#                     logger.warning(f"Триггер '{trigger}' не найден в {pdf_path}")
#                     return []

#                 # Текст первой страницы для паспорта
#                 first_page_text = pdf.pages[0].extract_text() if len(pdf.pages) > 0 else ""

#                 participants = []
#                 seen_names = set()
#                 for page_num in trigger_pages:
#                     page = pdf.pages[page_num]
#                     text = page.extract_text()
#                     if not text:
#                         continue
#                     block = self._extract_participant_block(text, trigger)
#                     if not block:
#                         continue
#                     fields = self._extract_fields_from_block(block)
#                     if 'ФИО' not in fields:
#                         continue
#                     if fields['ФИО'] in seen_names:
#                         continue
#                     seen_names.add(fields['ФИО'])

#                     # Если паспорт не найден в этом блоке, пытаемся взять из шапки
#                     if 'паспорт' not in fields:
#                         passport = self._extract_passport_from_first_page(first_page_text, fields['ФИО'])
#                         if passport:
#                             fields['паспорт'] = passport

#                     participant = {
#                         'ФИО': fields['ФИО'],
#                         'телефон': fields.get('телефон', ''),
#                         'email': fields.get('email', ''),
#                         'доп_данные': {}
#                     }
#                     for key in fields:
#                         if key not in ('ФИО', 'телефон', 'email'):
#                             participant['доп_данные'][key] = fields[key]
#                     participants.append(participant)
#                     logger.info(f"Извлечён участник: {fields['ФИО']}")

#                 return participants

#         except Exception as e:
#             logger.error(f"Ошибка при парсинге PDF {pdf_path}: {e}")
#             return []


# if __name__ == '__main__':
#     import sys
#     if len(sys.argv) > 1:
#         test_pdf = sys.argv[1]
#     else:
#         print("Укажите путь к PDF файлу")
#         sys.exit(1)

#     parser = DDUParser()
#     result = parser.parse(test_pdf)
#     for i, p in enumerate(result, 1):
#         print(f"\nУчастник {i}:")
#         print(f"  ФИО: {p['ФИО']}")
#         print(f"  Телефон: {p['телефон']}")
#         print(f"  Email: {p['email']}")
#         print(f"  Доп.данные: {p['доп_данные']}")



# # pdf_parser.py
# import re
# import pdfplumber
# from typing import List, Dict, Optional
# import logging

# logger = logging.getLogger(__name__)


# class BaseParser:
#     """Базовый класс для парсеров PDF."""
#     def parse(self, pdf_path: str, config: Dict) -> List[Dict]:
#         raise NotImplementedError("Метод parse должен быть переопределён в подклассе")


# class DDUParser(BaseParser):
#     # --- Шапка (первая страница) ---
#     # Участник: ФИО, дата рождения, паспорт и т.д.
#     PERSON_IN_HEADER = re.compile(
#         r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s*,\s*'
#         r'(\d{2}\.\d{2}\.\d{4})\s*г\.\s*р\.[^,]*,?\s*'
#         r'(?:место рождения:\s*(.+?)\s*,\s*)?'
#         r'паспорт:\s*(\d{2}\s*\d{2}\s*\d{6})\s*,\s*'
#         r'выдан\s+(\d{2}\.\d{2}\.\d{4})\s*г[.,]?\s*'
#         r'(.+?)\s*,\s*код\s+подразделения:\s*(\d{3}-\d{3})\s*,\s*'
#         r'проживающ(?:ий|ая)\s+по адресу:\s*(.+?)\s*'
#         r'(?:\(для корреспонденции:\s*(.+?)\))?',
#         re.IGNORECASE | re.DOTALL
#     )

#     # Реквизиты договора (первая страница)
#     CONTRACT_INFO = re.compile(
#         r'Договор\s*№\s*(\S+)\s*\n\s*(.+?)\n'
#         r'(?:г\.\s*\S+\s*)?«(\d{2})»\s*([а-яё]+)\s*(\d{4})\s*г\.',
#         re.IGNORECASE
#     )
#     KADASTR_NUMBER = re.compile(r'кадастровым\s+номером\s+(\d{2}:\d{2}:\d{7}:\d{1,5})', re.IGNORECASE)

#     # --- Реквизитная часть (последние страницы) ---
#     CONTACT_FIELDS = {
#         'телефон': r'((?:\+7|8)\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})',
#         'email': r'([\w\.-]+@[\w\.-]+\.\w+)',
#         'ИНН': r'ИНН:\s*(\d{10,12})',
#         'СНИЛС': r'СНИЛС:\s*(\d{3}-\d{3}-\d{3}\s?\d{2})',
#     }

#     def __init__(self):
#         pass

#     def _extract_from_header(self, first_page_text: str) -> Dict:
#         """Извлекает участников и реквизиты договора из первой страницы."""
#         result = {
#             'участники': [],
#             'договор_№': '',
#             'название_договора': '',
#             'дата_договора': '',
#             'кадастровый_номер': ''
#         }

#         # Реквизиты договора
#         contract_match = self.CONTRACT_INFO.search(first_page_text)
#         if contract_match:
#             result['договор_№'] = contract_match.group(1).strip()
#             result['название_договора'] = contract_match.group(2).strip()
#             result['дата_договора'] = f"{contract_match.group(3)} {contract_match.group(4)} {contract_match.group(5)} г."

#         kadastr_match = self.KADASTR_NUMBER.search(first_page_text)
#         if kadastr_match:
#             result['кадастровый_номер'] = kadastr_match.group(1)

#         # Участники
#         for match in self.PERSON_IN_HEADER.finditer(first_page_text):
#             surname, name, patronymic = match.group(1), match.group(2), match.group(3)
#             participant = {
#                 'ФИО': f"{surname} {name} {patronymic}",
#                 'дата_рождения': match.group(4),
#                 'паспорт': match.group(6).replace(' ', ''),
#                 'дата_выдачи': match.group(7),
#                 'кем_выдан': match.group(8).strip(),
#                 'код_подразделения': match.group(9),
#                 'адрес_проживания': match.group(10).strip(),
#                 'корр_адрес': match.group(11).strip() if match.group(11) else '',
#             }
#             result['участники'].append(participant)

#         return result

#     def _extract_contacts_for_participant(self, req_text: str, full_name: str) -> Dict:
#         """Ищет контакты для конкретного ФИО в реквизитной части."""
#         name_escaped = re.escape(full_name)
#         name_match = re.search(name_escaped, req_text, re.IGNORECASE)
#         if not name_match:
#             return {}

#         rest = req_text[name_match.start():]
#         end_marker = re.search(r'_{3,}', rest)
#         block = rest[:end_marker.start()] if end_marker else rest[:300]

#         contacts = {}
#         for field, pattern in self.CONTACT_FIELDS.items():
#             match = re.search(pattern, block, re.IGNORECASE)
#             if match:
#                 value = match.group(1) if match.lastindex else match.group(0)
#                 contacts[field] = re.sub(r'\s+', ' ', value).strip()
#         return contacts

#     def parse(self, pdf_path: str, config: Optional[Dict] = None) -> List[Dict]:
#         if not pdf_path.lower().endswith('.pdf'):
#             logger.warning(f"Пропущен не-PDF файл: {pdf_path}")
#             return []

#         trigger = config.get('trigger_section', 'участники долевого строительства') if config else 'участники долевого строительства'

#         try:
#             with pdfplumber.open(pdf_path) as pdf:
#                 if len(pdf.pages) == 0:
#                     return []

#                 # --- Этап 1: шапка ---
#                 first_page_text = pdf.pages[0].extract_text() or ""
#                 header_data = self._extract_from_header(first_page_text)

#                 if not header_data['участники']:
#                     logger.warning(f"Участники не найдены в шапке {pdf_path}")
#                     return []

#                 # --- Этап 2: поиск контактов в реквизитной части ---
#                 # Ищем последние страницы с триггером
#                 req_text = ""
#                 trigger_pages = []
#                 for i, page in enumerate(pdf.pages):
#                     text = page.extract_text()
#                     if text and trigger.lower() in text.lower():
#                         trigger_pages.append(i)
#                 if trigger_pages:
#                     full_req = []
#                     for i in range(trigger_pages[0], len(pdf.pages)):
#                         text = pdf.pages[i].extract_text()
#                         if text:
#                             full_req.append(text)
#                     req_text = "\n".join(full_req)

#                 # Собираем итоговых участников
#                 participants = []
#                 for p in header_data['участники']:
#                     contacts = self._extract_contacts_for_participant(req_text, p['ФИО']) if req_text else {}
#                     participant = {
#                         'ФИО': p['ФИО'],
#                         'телефон': contacts.get('телефон', ''),
#                         'email': contacts.get('email', ''),
#                         'доп_данные': {
#                             'дата_рождения': p.get('дата_рождения', ''),
#                             'паспорт': p.get('паспорт', ''),
#                             'дата_выдачи': p.get('дата_выдачи', ''),
#                             'кем_выдан': p.get('кем_выдан', ''),
#                             'код_подразделения': p.get('код_подразделения', ''),
#                             'адрес_проживания': p.get('адрес_проживания', ''),
#                             'корр_адрес': p.get('корр_адрес', ''),
#                             'СНИЛС': contacts.get('СНИЛС', ''),
#                             'ИНН': contacts.get('ИНН', ''),
#                             'договор_№': header_data.get('договор_№', ''),
#                             'дата_договора': header_data.get('дата_договора', ''),
#                             'кадастровый_номер': header_data.get('кадастровый_номер', ''),
#                         }
#                     }
#                     # Убираем пустые доп.данные
#                     participant['доп_данные'] = {k: v for k, v in participant['доп_данные'].items() if v}
#                     participants.append(participant)
#                     logger.info(f"Участник: {p['ФИО']}, тел: {contacts.get('телефон', '—')}")

#                 return participants

#         except Exception as e:
#             logger.error(f"Ошибка при парсинге PDF {pdf_path}: {e}")
#             return []

# pdf_parser.py
import re
import pdfplumber
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BaseParser:
    def parse(self, pdf_path: str, config: Dict) -> List[Dict]:
        raise NotImplementedError


class DDUParser(BaseParser):
    # Шаблон участника из первой страницы: ФИО (3+ слов), дата, паспорт, выдан, кем, код, адрес
    PERSON_IN_HEADER = re.compile(
        r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){2,})\s*,\s*'
        r'(\d{2}\.\d{2}\.\d{4})\s*г\.\s*р\..*?'
        r'паспорт:\s*(\d{2}\s*\d{2}\s*\d{6})\s*,\s*'
        r'выдан\s+(\d{2}\.\d{2}\.\d{4})\s*г[.,]?\s*'
        r'(.+?)\s*,\s*код\s+подразделения:\s*(\d{3}-\d{3})\s*,\s*'
        r'проживающ(?:ий|ая)\s+по адресу:\s*(.+?)\s*'
        r'(?:\(для\s+корреспонденции:\s*(.+?)\))?\s*(?:,|$)',
        re.IGNORECASE | re.DOTALL
    )
    def _extract_from_first_page(self, text: str) -> tuple:
        """
        Извлекает всех участников и реквизиты договора из первой страницы.
        Возвращает (участники, реквизиты_договора).
        """
        if not text:
            return [], {}

        # Нормализуем пробелы
        text = re.sub(r'\s+', ' ', text)

        # --- Реквизиты договора ---
        contract_info = {}

        # Номер договора — ищем "Договор № ЦИФРЫ" или "Догово р № ЦИФРЫ" (с разрывом)
        contract_match = re.search(
            r'Догово\s*р?\s*№\s*(\d+)',
            text,
            re.IGNORECASE
        )
        if contract_match:
            contract_info['договор_№'] = contract_match.group(1).strip()
            logger.debug(f"Найден номер договора: {contract_info['договор_№']}")
        else:
            logger.warning("Номер договора не найден в тексте первой страницы")
            contract_info['договор_№'] = ''

        # Название договора
        title_match = re.search(
            r'(?:участия|долевом|строительстве)',
            text,
            re.IGNORECASE
        )
        if title_match:
            # Просто ищем стандартное название
            if 'участия в долевом строительстве' in text.lower():
                contract_info['название_договора'] = 'участия в долевом строительстве'
            else:
                contract_info['название_договора'] = ''
        else:
            contract_info['название_договора'] = ''

        # Дата договора
        date_match = re.search(
            r'«(\d{2})»\s*([а-яё]+)\s*(\d{4})\s*г\.',
            text,
            re.IGNORECASE
        )
        if date_match:
            contract_info['дата_договора'] = f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)} г."
        else:
            contract_info['дата_договора'] = ''

        # Кадастровый номер
        kadastr_match = re.search(
            r'кадастровым\s+номером\s+(\d{2}:\d{2}:\d{7}:\d{1,5})',
            text,
            re.IGNORECASE
        )
        contract_info['кадастровый_номер'] = kadastr_match.group(1) if kadastr_match else ''

        # Адрес строительства
        address_match = re.search(
            r'по строительному адресу:\s*(.+?)(?:,|Объект долевого строительства|\d+\.\d+\.)',
            text,
            re.IGNORECASE
        )
        contract_info['адрес_строительства'] = address_match.group(1).strip() if address_match else ''

        # Характеристики квартиры
        flat_match = re.search(
            r'(\d[СК])\s+(\d+)\s+(\d+)\s+([\d,]+)\s+([\d,/]+)\s+([\d,]+)',
            text,
            re.IGNORECASE
        )
        if flat_match:
            contract_info['тип_квартиры'] = flat_match.group(1)
            contract_info['номер_квартиры'] = flat_match.group(2)
            contract_info['этаж'] = flat_match.group(3)
            contract_info['общая_площадь'] = flat_match.group(4)
            contract_info['жилая_площадь'] = flat_match.group(5)
            contract_info['площадь_балкона'] = flat_match.group(6)

        # --- Участники ---
        start_match = re.search(r'(?:Устава|основании)\s*,\s*и\s', text)
        if not start_match:
            logger.warning("Не найдено 'Устава, и'")
            return [], contract_info

        after_start = text[start_match.end():]

        end_match = re.search(
            r'именуемая?\s*(?:\([^)]*\))?\s*в\s+дальнейшем\s+«Участник\s+долевого\s+строительства»',
            after_start,
            re.IGNORECASE
        )
        if end_match:
            after_start = after_start[:end_match.start()]

        person_pattern = re.compile(
            r'([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){2,})\s*,\s*(\d{2}\.\d{2}\.\d{4})\s*г\.\s*р\.',
            re.IGNORECASE
        )
        person_starts = list(person_pattern.finditer(after_start))

        participants = []
        for i, match in enumerate(person_starts):
            name = match.group(1).strip()
            birth_date = match.group(2)
            
            start_pos = match.start()
            if i + 1 < len(person_starts):
                end_pos = person_starts[i + 1].start()
            else:
                end_pos = len(after_start)
            
            block = after_start[start_pos:end_pos]
            
            # Паспорт
            passport_match = re.search(r'паспорт:\s*(\d{2}\s*\d{2}\s*\d{6})', block, re.IGNORECASE)
            passport = re.sub(r'\s+', '', passport_match.group(1)) if passport_match else ''
            
            # Дата выдачи
            issue_date_match = re.search(r'выдан\s+(\d{2}\.\d{2}\.\d{4})\s*г', block, re.IGNORECASE)
            issue_date = issue_date_match.group(1) if issue_date_match else ''
            
            # Кем выдан
            issuer_match = re.search(
                r'выдан\s+\d{2}\.\d{2}\.\d{4}\s*г[.,]?\s*(.+?)\s*,?\s*код\s+подразделения',
                block,
                re.IGNORECASE | re.DOTALL
            )
            if issuer_match:
                issuer = issuer_match.group(1).strip()
                issuer = re.sub(r'^\s*(?:ода|да|од|от|по)[,.\s]+', '', issuer, flags=re.IGNORECASE).strip(',. ')
            else:
                issuer = ''
            
            # Код подразделения
            code_match = re.search(r'код\s+подразделения:\s*(\d{3}-\d{3})', block, re.IGNORECASE)
            code = code_match.group(1) if code_match else ''
            
            # Адрес проживания
            address_match = re.search(
                r'проживающ(?:ий|ая)\s+по адресу:\s*(.+?)(?:\s*,\s*$|\s*$)',
                block,
                re.IGNORECASE | re.DOTALL
            )
            address = address_match.group(1).strip().rstrip(',') if address_match else ''
            
            # Корр. адрес
            corr_match = re.search(r'для\s+корреспонденции:\s*(.+?)\)', block, re.IGNORECASE)
            corr_address = corr_match.group(1).strip() if corr_match else ''

            participants.append({
                'ФИО': name,
                'дата_рождения': birth_date,
                'паспорт': passport,
                'дата_выдачи': issue_date,
                'кем_выдан': issuer,
                'код_подразделения': code,
                'адрес_проживания': address,
                'корр_адрес': corr_address,
            })
            logger.info(f"Найден в шапке: {name}")

        return participants, contract_info
    def _extract_contacts_from_end(self, text: str) -> List[Dict]:
        """Извлекает контакты из последних страниц (все найденные)."""
        if not text:
            return []

        # Ищем раздел "Участники долевого строительства:" (он есть в реквизитах)
        trigger_idx = text.lower().find('участники долевого строительства')
        if trigger_idx == -1:
            logger.warning("Раздел 'Участники долевого строительства' не найден в реквизитах")
            return []

        after_trigger = text[trigger_idx:]

        # Собираем все email'ы
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', after_trigger)

        # Собираем все телефоны (строки с +7 или 8)
        phones = []
        for line in after_trigger.splitlines():
            line = line.strip()
            if re.match(r'^\+7\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$', line):
                phones.append(line)
            elif re.match(r'^8\s*\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$', line):
                phones.append(line)

        # Собираем все ИНН (после триггера, чтобы не захватить ИНН застройщика)
        inns = re.findall(r'ИНН:\s*(\d{10,12})', after_trigger, re.IGNORECASE)

        # Собираем все СНИЛС
        snils_list = re.findall(r'СНИЛС:\s*(\d{3}-\d{3}-\d{3}\s?\d{2})', after_trigger, re.IGNORECASE)

        # Определяем количество участников по числу уникальных email или телефонов
        num_participants = max(len(emails), len(phones), len(inns), len(snils_list))

        contacts_list = []
        for i in range(num_participants):
            contact = {
                'email': emails[i] if i < len(emails) else '',
                'телефон': phones[i] if i < len(phones) else '',
                'ИНН': inns[i] if i < len(inns) else '',
                'СНИЛС': snils_list[i] if i < len(snils_list) else '',
            }
            contacts_list.append(contact)

        return contacts_list

    def parse(self, pdf_path: str, config: Optional[Dict] = None) -> List[Dict]:
        if not pdf_path.lower().endswith('.pdf'):
            logger.warning(f"Пропущен не-PDF файл: {pdf_path}")
            return []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) < 2:
                    logger.warning(f"Слишком мало страниц в {pdf_path}")
                    return []

                # Этап 1: первая страница — персональные данные и реквизиты договора
                first_page_text = pdf.pages[0].extract_text() or ""
                header_participants, contract_info = self._extract_from_first_page(first_page_text)

                if not header_participants:
                    logger.warning(f"Участники не найдены в шапке {pdf_path}")
                    return []

                # Этап 2: последние страницы — контакты
                last_pages_text = ""
                for i in range(max(0, len(pdf.pages) - 3), len(pdf.pages)):
                    text = pdf.pages[i].extract_text()
                    if text:
                        last_pages_text += text + "\n"

                contacts_list = self._extract_contacts_from_end(last_pages_text)

                # Этап 3: сборка
                participants = []
                for i, person in enumerate(header_participants):
                    contact = contacts_list[i] if i < len(contacts_list) else {}

                    participant = {
                        'ФИО': person['ФИО'],
                        'телефон': contact.get('телефон', ''),
                        'email': contact.get('email', ''),
                        'доп_данные': {
                            'дата_рождения': person.get('дата_рождения', ''),
                            'паспорт': person.get('паспорт', ''),
                            'дата_выдачи': person.get('дата_выдачи', ''),
                            'кем_выдан': person.get('кем_выдан', ''),
                            'код_подразделения': person.get('код_подразделения', ''),
                            'адрес_проживания': person.get('адрес_проживания', ''),
                            'корр_адрес': person.get('корр_адрес', ''),
                            'СНИЛС': contact.get('СНИЛС', ''),
                            'ИНН': contact.get('ИНН', ''),
                            # Реквизиты договора
                            'договор_№': contract_info.get('договор_№', ''),
                            'дата_договора': contract_info.get('дата_договора', ''),
                            'название_договора': contract_info.get('название_договора', ''),
                            'кадастровый_номер': contract_info.get('кадастровый_номер', ''),
                            'адрес_строительства': contract_info.get('адрес_строительства', ''),
                            'тип_квартиры': contract_info.get('тип_квартиры', ''),
                            'номер_квартиры': contract_info.get('номер_квартиры', ''),
                            'этаж': contract_info.get('этаж', ''),
                            'общая_площадь': contract_info.get('общая_площадь', ''),
                            'жилая_площадь': contract_info.get('жилая_площадь', ''),
                            'площадь_балкона': contract_info.get('площадь_балкона', ''),
                        }
                    }
                    participant['доп_данные'] = {k: v for k, v in participant['доп_данные'].items() if v}
                    participants.append(participant)
                    logger.info(f"Участник {i+1}: {person['ФИО']}")

                return participants

        except Exception as e:
            logger.error(f"Ошибка при парсинге PDF {pdf_path}: {e}")
            import traceback
            traceback.print_exc()
            return []

        except Exception as e:
            logger.error(f"Ошибка при парсинге PDF {pdf_path}: {e}")
            import traceback
            traceback.print_exc()
            return []