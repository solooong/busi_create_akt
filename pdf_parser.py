"""
PDF Parser для договоров долевого участия (ДДУ)
================================================

Назначение:
    Извлечение структурированных данных о участниках долевого строительства
    и реквизитах договора из PDF-документов.

Возможности:
    ✓ Извлечение ФИО (3 и более слов) из шапки договора
    ✓ Парсинг паспортных данных (серия, номер, дата выдачи, кем выдан)
    ✓ Извлечение реквизитов договора (номер, дата, кадастровый номер)
    ✓ Характеристики объекта (площади, этаж, номер квартиры)
    ✓ Контактные данные из реквизитов (email, телефон, ИНН, СНИЛС)
    ✓ Адреса проживания и корреспонденции

Известные проблемы:
    ⚠ БАГ: Код подразделения не извлекается для ПЕРВОГО участника, 
           если участников два и более. 
           Причина: при разбиении текста на блоки по участникам,
           regex для кода подразделения может не сработать корректно
           для первого блока из-за особенностей форматирования.
           
           Обход: Проверять наличие кода подразделения вручную
           или доработать логику разбиения блоков.

Структура данных:
    - ФИО: полное имя участника
    - телефон: в формате +7 (XXX) XXX-XX-XX
    - email: адрес электронной почты
    - ИНН: 10-12 цифр
    - СНИЛС: формат XXX-XXX-XXX XX
    - доп_данные: паспортные данные, адреса, реквизиты договора

Требования:
    - Python 3.7+
    - pdfplumber
    - regex

Автор: Эдуард
Дата: 2026
"""

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
    @staticmethod
    def get_full_text(pdf_path: str) -> str:
        """Извлекает весь текст из PDF для проверки AI."""
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(
                re.sub(r'Страница\s+\d+\s+из\s+\d+', '', page.extract_text() or '')
                for page in pdf.pages
            )
        
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