# docx_filler.py
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)


class DocxFiller:
    """
    Заполняет шаблон акта приёма-передачи данными участников.
    """
    
    def __init__(self, template_path: str):
        """
        Args:
            template_path: путь к файлу шаблона .docx
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Шаблон не найден: {template_path}")
        self.template_path = template_path

    def fill_single_act(self, participant: Dict, output_path: str) -> str:
        """
        Заполняет акт для одного участника.
        
        Args:
            participant: словарь с данными участника
            output_path: путь для сохранения готового акта
            
        Returns:
            путь к созданному файлу
        """
        try:
            doc = Document(self.template_path)
            
            # Собираем все данные для замены
            replacements = {
                # Основные данные
                'ФИО': participant.get('ФИО', ''),
                'телефон': participant.get('телефон', ''),
                'email': participant.get('email', ''),
            }
            
            # Добавляем дополнительные данные с префиксом
            for key, value in participant.get('доп_данные', {}).items():
                replacements[key] = value
            
            # Замена в параграфах
            for paragraph in doc.paragraphs:
                self._replace_in_paragraph(paragraph, replacements)
            
            # Замена в таблицах
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            self._replace_in_paragraph(paragraph, replacements)
            
            # Создаём папку, если нужно
            output_dir = os.path.dirname(output_path)
            if output_dir:  # Создаём директорию только если она указана в пути
                os.makedirs(output_dir, exist_ok=True)
            
            # Сохраняем
            doc.save(output_path)
            logger.info(f"Акт сохранён: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка при заполнении акта для {participant.get('ФИО', '')}: {e}")
            raise

    def fill_multiple_acts(
        self, 
        participants: List[Dict], 
        output_dir: str,
        prefix: str = "Акт_"
    ) -> List[str]:
        """
        Заполняет акты для списка участников.
        
        Args:
            participants: список участников
            output_dir: папка для сохранения
            prefix: префикс имени файла
            
        Returns:
            список путей к созданным файлам
        """
        created_files = []
        for i, participant in enumerate(participants, 1):
            # Формируем имя файла
            name = participant.get('ФИО', f'участник_{i}')
            # Очищаем имя от недопустимых символов
            safe_name = "".join(c for c in name if c.isalnum() or c in ' _-')
            filename = f"{prefix}{safe_name}.docx"
            output_path = os.path.join(output_dir, filename)
            
            try:
                created = self.fill_single_act(participant, output_path)
                created_files.append(created)
            except Exception as e:
                logger.error(f"Не удалось создать акт для {name}: {e}")
                
        return created_files
    def _replace_in_paragraph(self, paragraph, replacements: Dict[str, str]):
        """
        Заменяет все {{ключ}} в параграфе за один проход, сохраняя форматирование.
        """
        full_text = paragraph.text
        if '{{' not in full_text:
            return

        # Заменяем все плейсхолдеры в тексте
        for key, value in replacements.items():
            placeholder = f'{{{{{key}}}}}'
            full_text = full_text.replace(placeholder, str(value))

        if full_text != paragraph.text:
            # Сохраняем форматирование первого run
            if paragraph.runs:
                first_font = paragraph.runs[0].font
                bold = first_font.bold
                italic = first_font.italic
                size = first_font.size
            else:
                bold = None
                italic = None
                size = None

            # Очищаем параграф и вставляем новый текст
            paragraph.clear()
            run = paragraph.add_run(full_text)
            
            # Применяем сохранённое форматирование через .font
            if bold is not None:
                run.font.bold = bold
            if italic is not None:
                run.font.italic = italic
            if size is not None:
                run.font.size = size
    def fill_acts_with_contract_info(
        self,
        participants: List[Dict],
        output_dir: str,
        contract_info: Optional[Dict] = None
    ) -> List[str]:
        """
        Заполняет акты с учётом общей информации о договоре.
        
        Args:
            participants: список участников
            output_dir: папка для сохранения
            contract_info: общая информация о договоре (если есть)
            
        Returns:
            список созданных файлов
        """
        if contract_info:
            # Добавляем инфу о договоре ко всем участникам
            for p in participants:
                if 'доп_данные' not in p:
                    p['доп_данные'] = {}
                p['доп_данные'].update(contract_info)
        
        return self.fill_multiple_acts(participants, output_dir)


if __name__ == "__main__":
    # Пример использования
    logging.basicConfig(level=logging.INFO)
    
    # Тестовый участник
    test_participant = {
        'ФИО': 'Иванов Иван Иванович',
        'телефон': '+7 (900) 123-45-67',
        'email': 'ivanov@example.com',
        'доп_данные': {
            'дата_рождения': '01.01.1990',
            'паспорт': '1234 567890',
            'адрес_проживания': 'г. Москва, ул. Примерная, д. 1, кв. 1',
            'договор_№': '123',
            'дата_договора': '01 января 2025 г.',
            'номер_квартиры': '42',
            'этаж': '5',
            'общая_площадь': '50,5',
        }
    }
    
    # Заполнение акта
    filler = DocxFiller("template_akt.docx")  # укажите путь к шаблону
    filler.fill_single_act(test_participant, "output_akt.docx")