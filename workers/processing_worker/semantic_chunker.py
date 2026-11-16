"""
Semantic Chunker & Sanitizer
Интеллектуальный чанкинг с учетом структуры Markdown, таблиц, заголовков и защита от Indirect Prompt Injection.
"""

import re
import hashlib
from typing import List, Dict, Any, Tuple

# Паттерны для обнаружения Indirect Prompt Injection в индексируемых файлах
INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"(?i)disregard\s+the\s+above",
    r"(?i)you\s+are\s+now\s+(an?\s+)?unrestricted",
    r"(?i)system\s+prompt\s*:",
    r"(?i)override\s+system\s+instructions",
    r"(?i)developer\s+mode\s+enabled",
    r"(?i)<script\b[^>]*>",
    r"(?i)base64\s*,\s*[A-Za-z0-9+/=]{40,}"
]

def calculate_checksum(content_bytes: bytes) -> str:
    """Вычисляет SHA-256 хеш документа для версионирования и дедупликации"""
    return hashlib.sha256(content_bytes).hexdigest()

def sanitize_document_text(text: str) -> Tuple[str, List[str]]:
    """
    Санитайзинг текста от Indirect Prompt Injection.
    Нейтрализует вредоносные инструкции злоумышленников внутри документов.
    """
    detected_threats = []
    sanitized = text

    for pattern in INJECTION_PATTERNS:
        matches = re.findall(pattern, sanitized)
        if matches:
            detected_threats.append(pattern)
            # Экранируем/нейтрализуем потенциальную инъекцию
            sanitized = re.sub(pattern, "[FILTERED_POTENTIAL_INJECTION]", sanitized)

    return sanitized, detected_threats

def semantic_chunk_markdown(markdown_text: str, max_chunk_tokens: int = 512, overlap_tokens: int = 50) -> List[Dict[str, Any]]:
    """
    Интеллектуальный чанкинг (Semantic Chunking):
    1. Не разрывает Markdown-таблицы (| col | col |).
    2. Не разрывает блоки кода (```...```).
    3. Привязывает текст к пути заголовков (# Title -> ## Section).
    4. Генерирует Parent-Child контекст (Parent: весь раздел, Child: конкретный абзац).
    """
    # 1. Защита от prompt injection
    clean_text, threats = sanitize_document_text(markdown_text)

    # 2. Разбиение по основным заголовкам (#, ##, ###)
    sections = re.split(r'(?m)(?=^#{1,4}\s+)', clean_text)
    chunks = []
    chunk_index = 0

    for sec_idx, section in enumerate(sections):
        section_text = section.strip()
        if not section_text:
            continue

        # Извлекаем заголовок секции
        header_match = re.match(r'^(#{1,4}\s+[^\n]+)', section_text)
        header_title = header_match.group(1).strip() if header_match else "Общий контекст"

        # Проверяем наличие таблиц или блоков кода
        # Блоки кода и таблицы изолируем как атомарные единицы
        sub_blocks = re.split(r'(\n```[\s\S]*?```|\n\|[^\n]+\|\n(?:\|[-:| ]+\|\n)+(?:\|[^\n]+\|\n?)*)', section_text)
        
        current_child = ""
        for block in sub_blocks:
            if not block.strip():
                continue

            # Если блок — таблица или код, держим его целиком
            if block.strip().startswith("```") or (block.strip().startswith("|") and "|" in block.strip()):
                if current_child:
                    chunks.append({
                        "chunk_index": chunk_index,
                        "header": header_title,
                        "text": current_child.strip(),
                        "parent_text": section_text[:1500], # Parent-Child окно
                        "is_table_or_code": False
                    })
                    chunk_index += 1
                    current_child = ""

                chunks.append({
                    "chunk_index": chunk_index,
                    "header": header_title,
                    "text": block.strip(),
                    "parent_text": section_text[:1500],
                    "is_table_or_code": True
                })
                chunk_index += 1
                continue

            # Обычные абзацы
            paragraphs = block.split("\n\n")
            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    continue

                if len(current_child) + len(p_clean) > max_chunk_tokens * 4: # приблизительно 4 символа на токен
                    chunks.append({
                        "chunk_index": chunk_index,
                        "header": header_title,
                        "text": current_child.strip(),
                        "parent_text": section_text[:1500],
                        "is_table_or_code": False
                    })
                    chunk_index += 1
                    current_child = p_clean
                else:
                    current_child += ("\n\n" if current_child else "") + p_clean

        if current_child:
            chunks.append({
                "chunk_index": chunk_index,
                "header": header_title,
                "text": current_child.strip(),
                "parent_text": section_text[:1500],
                "is_table_or_code": False
            })
            chunk_index += 1

    return chunks
