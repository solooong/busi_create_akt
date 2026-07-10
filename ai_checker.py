# ai_checker.py
import requests
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AIChecker:
    """
    Проверка извлечённых данных через LLM API (LM Studio / OpenAI-совместимый).
    
    Примеры:
        # Локальная LM Studio (без токена)
        checker = AIChecker(api_url="http://localhost:1234/v1/chat/completions")
        
        # Удалённый сервер с токеном
        checker = AIChecker(
            api_url="http://26.250.90.120:1234/v1/chat/completions",
            api_token="sk-lm-oPeN5xTy:JWPSzgAj1W44Rouiv3qN"
        )
        
        # OpenAI API
        checker = AIChecker(
            api_url="https://api.openai.com/v1/chat/completions",
            api_token="sk-...",
            model="gpt-4o-mini"
        )
    """
    
    def __init__(
        self,
        api_url: str = "http://localhost:1234/v1/chat/completions",
        api_token: Optional[str] = None,
        model: str = "local-model",
        timeout: int = 3600
    ):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.model = model
        self.timeout = timeout

    def _get_headers(self) -> dict:
        """Формирует заголовки запроса."""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def check_participant(self, full_text: str, extracted: dict) -> dict:
        """
        Отправляет полный текст PDF и извлечённые данные в LLM.
        Возвращает исправленный словарь.
        """
        prompt = self._build_prompt(full_text, extracted)
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — эксперт по извлечению данных из договоров долевого участия. "
                        "Твоя задача — проверить и исправить структурированные данные, "
                        "извлечённые из текста договора. Отвечай только JSON без комментариев."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 15500
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return self._parse_response(response.json(), extracted)
            elif response.status_code == 401:
                logger.error("AI: ошибка авторизации (неверный токен)")
            elif response.status_code == 404:
                logger.error(f"AI: эндпоинт не найден ({self.api_url})")
            else:
                logger.error(f"AI ответил с ошибкой {response.status_code}: {response.text[:200]}")
            
            return extracted
            
        except requests.exceptions.Timeout:
            logger.error(f"AI: таймаут ({self.timeout} сек)")
            return extracted
        except requests.exceptions.ConnectionError:
            logger.error(f"AI: не удалось подключиться к {self.api_url}")
            return extracted
        except Exception as e:
            logger.error(f"AI: неожиданная ошибка: {e}")
            return extracted
    def _parse_response(self, response_data: dict, fallback: dict) -> dict:
        try:
            content = response_data['choices'][0]['message']['content']
            content = re.sub(r'^```(?:json)?\s*', '', content.strip())
            content = re.sub(r'\s*```$', '', content)
            
            fixed = json.loads(content)
            
            # Нормализация: всё кроме ФИО/телефон/email → доп_данные
            normalized = {
                'ФИО': fixed.pop('ФИО', fallback.get('ФИО', '')),
                'телефон': fixed.pop('телефон', fallback.get('телефон', '')),
                'email': fixed.pop('email', fallback.get('email', '')),
                'доп_данные': {}
            }
            
            # Собираем доп_данные
            extra = fixed.pop('доп_данные', {}) if isinstance(fixed.get('доп_данные'), dict) else {}
            # Всё оставшееся тоже в доп_данные
            extra.update(fixed)
            normalized['доп_данные'] = extra
            
            logger.info("AI успешно проверил данные")
            return normalized
            
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"AI вернул некорректный JSON: {e}")
            return fallback
    def _build_prompt(self, full_text: str, extracted: dict) -> str:
        """Создаёт промпт для LLM."""
        text_snippet = full_text #if len(full_text) <= 4000 else full_text[:4000]
        
        prompt = f"""Проверь и исправь извлечённые данные участника долевого строительства на основе ПОЛНОГО текста договора.

    Текст договора:
    {text_snippet}

    Извлечённые данные (JSON):
    {json.dumps(extracted, ensure_ascii=False, indent=2)}

    Правила проверки ВСЕХ полей:

    1. ФИО: фамилия, имя, отчество (может быть 4 слова для иностранцев). Не должно содержать "ограниченной ответственностью" и других частей названия юрлица.

    2. Телефон: формат +7 (XXX) XXX-XX-XX или 8 XXX XXX-XX-XX. Должен быть номером физического лица, не банка и не застройщика.

    3. Email: должен содержать @ и домен. Принадлежит участнику, не застройщику.

    4. Дата рождения: формат ДД.ММ.ГГГГ. Только одна дата — дата рождения участника.

    5. Паспорт: 4 цифры, пробел, 6 цифр (XX XX XXXXXX). Принадлежит участнику, не застройщику.

    6. Дата выдачи паспорта: формат ДД.ММ.ГГГГ. Дата выдачи паспорта участника.

    7. Кем выдан: полное название органа, выдавшего паспорт. Не должно содержать реквизитов застройщика (ИНН, ОГРН, расчётный счёт, БИК и т.п.). Убрать "ода,", "да," и другой мусор в начале.

    8. Код подразделения: формат XXX-XXX (3 цифры, дефис, 3 цифры). Иногда может быть пропуск дефиса. Относится к участнику. 

    9. Адрес проживания: полный адрес с городом, улицей, домом, квартирой. Адрес регистрации участника. Не путать с юридическим адресом застройщика и адресом строительства.

    10. Корр. адрес: адрес для корреспонденции, если указан. Может отличаться от адреса проживания.

    11. ИНН: 10 или 12 цифр. Должен быть ИНН участника (обычно указан в разделе "Участники долевого строительства"). Не ИНН застройщика (обычно 5404305790) и не ИНН банка.

    12. СНИЛС: формат XXX-XXX-XXX XX (3-3-3, пробел, 2 цифры). Принадлежит участнику.

    13. Договор №: номер договора участия в долевом строительстве (например, "22", "92"). Обычно в начале документа: "Договор № XX".

    14. Дата договора: дата заключения договора (например, "11 августа 2025 г."). Обычно в начале документа в формате «ДД» месяц ГГГГ г.

    15. Название договора: обычно "участия в долевом строительстве".

    16. Кадастровый номер: формат XX:XX:XXXXXXX:XX. Кадастровый номер земельного участка, на котором строится дом. Начинается обычно с "54:" для Новосибирской области.

    17. Адрес строительства: адрес строящегося дома. Обычно указан как "по строительному адресу: ...". Не путать с адресом проживания участника и юридическим адресом застройщика.

    18. Номер квартиры: строительный номер квартиры (обычно указан в таблице характеристик квартиры и в разделе "Объект долевого строительства").

    19. Этаж: номер этажа, на котором находится квартира.

    20. Общая площадь: общая площадь квартиры с учётом лоджии/балкона (например, "31,92" или "58,59").

    21. Жилая площадь: жилая площадь квартиры (может быть указана через дробь, например "27,40/14,87").

    22. Площадь балкона/лоджии: площадь балкона или лоджии (например, "4,52" или "4,44").

    23. Тип квартиры: тип квартиры (например, "1С", "2К" — указан в таблице характеристик).

    ВАЖНО:
    - Не путай данные участника с данными застройщика (ООО СЗ «КМ», ИНН 5404305790).
    - Не путай данные участника с данными банков (АО «Альфа-Банк», ПАО «Сбербанк», АО «Банк ДОМ.РФ»).
    - Если данных нет в тексте, оставь поле пустым.
    - Иногда имена полей могут начинаться не с заглавной буквы. При поиске в наименовании полей, старайся найти по любому из регистров. 
    - Используй предыдущие результаты поиска для понимания структуры хранения и возможных написаний данных 
    - Верни ТОЛЬКО исправленный JSON, без комментариев и без форматирования markdown."""
        return prompt