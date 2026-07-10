# ai_checker.py
import requests
import json
import re
import logging

logger = logging.getLogger(__name__)


class AIChecker:
    """Проверка извлечённых данных через LM Studio (локальную LLM)."""
    def __init__(self, api_url="http://localhost:1234/v1/chat/completions", model="local-model"):
        self.api_url = api_url
        self.model = model

    def check_participant(self, full_text: str, extracted: dict) -> dict:
        prompt = self._build_prompt(full_text, extracted)
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Ты — эксперт по извлечению данных из договоров долевого участия. Твоя задача — проверить и исправить структурированные данные, извлечённые из текста договора. Отвечай только JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 10000
                },
                timeout=600
            )
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                # Очистка от ```json ... ```
                content = re.sub(r'^```json\s*', '', content.strip())
                content = re.sub(r'\s*```$', '', content)
                try:
                    fixed_data = json.loads(content)
                    logger.info("AI проверил данные участника")
                    return fixed_data
                except json.JSONDecodeError:
                    logger.warning("AI вернул не JSON, используются исходные данные")
                    return extracted
            else:
                logger.error(f"AI ответил с ошибкой {response.status_code}: {response.text}")
                return extracted
        except Exception as e:
            logger.error(f"Ошибка связи с AI: {e}")
            return extracted

    def _build_prompt(self, full_text: str, extracted: dict) -> str:
        
        text_snippet = full_text # if len(full_text) <= 4000 else full_text[:4000] # Ограничим текст до 3000 символов, если слишком длинный, но оставим весь
        prompt = f"""Проверь и исправь извлечённые данные участника долевого строительства на основе ПОЛНОГО текста договора.

Полный текст договора (может быть обрезан):
{text_snippet}

Извлечённые данные (JSON):
{json.dumps(extracted, ensure_ascii=False, indent=2)}

Исправь любые ошибки: перепутанные ФИО, телефон, email, ИНН, СНИЛС, паспортные данные, адреса, реквизиты договора. Если данных нет в тексте, оставь поле пустым. Верни только JSON, без комментариев.
"""
        return prompt