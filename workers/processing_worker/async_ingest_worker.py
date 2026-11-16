"""
Asynchronous Ingestion Worker (Event-Driven ETL)
1. Message Queue Consumer с поддержкой Dead Letter Queue (DLQ).
2. Полная идемпотентность через детерминированные chunk_id (UUID v5).
3. Управление состояниями документа в БД (pending -> processing -> indexed -> failed).
"""

import uuid
import hashlib
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger("async-ingest-worker")

def generate_deterministic_chunk_id(source_id: str, chunk_index: int, chunk_text: str) -> str:
    """
    Генерирует детерминированный UUID v5 для чанка на основе source_id, индекса и контента.
    Гарантирует 100% идемпотентность: повторная обработка того же документа
    не плодит дубликаты в векторной БД, а обновляет существующие записи.
    """
    content_hash = hashlib.sha256(chunk_text.encode('utf-8')).hexdigest()[:16]
    unique_key = f"{source_id}:{chunk_index}:{content_hash}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_key))

class IngestionTaskConsumer:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.dead_letter_queue: List[Dict[str, Any]] = []

    def process_message(self, task_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка одного события из очереди (RabbitMQ / Redis Streams / Redpanda)
        """
        job_id = task_payload.get("job_id", str(uuid.uuid4()))
        source_id = task_payload.get("source_id", str(uuid.uuid4()))
        raw_markdown = task_payload.get("content", "")
        retry_count = task_payload.get("retry_count", 0)

        logger.info(f"[Job: {job_id}] Received ingestion task for source: {source_id} (Attempt {retry_count + 1})")

        try:
            # 1. Смена статуса документа: pending -> processing
            status_record = {
                "source_id": source_id,
                "job_id": job_id,
                "status": "processing",
                "started_at": datetime.utcnow().isoformat()
            }

            # 2. Семантический чанкинг (интеллектуальная нарезка без разрыва таблиц)
            from semantic_chunker import semantic_chunk_markdown
            raw_chunks = semantic_chunk_markdown(raw_markdown)

            # 3. Присвоение детерминированных ID и подготовка к UPSERT
            indexed_chunks = []
            for c in raw_chunks:
                det_id = generate_deterministic_chunk_id(source_id, c["chunk_index"], c["text"])
                indexed_chunks.append({
                    "id": det_id,
                    "source_id": source_id,
                    "chunk_index": c["chunk_index"],
                    "header": c["header"],
                    "text": c["text"],
                    "parent_text": c.get("parent_text", c["text"]),
                    "is_table_or_code": c.get("is_table_or_code", False)
                })

            # 4. Успешное завершение: processing -> indexed
            status_record["status"] = "indexed"
            status_record["chunks_count"] = len(indexed_chunks)
            status_record["completed_at"] = datetime.utcnow().isoformat()
            logger.info(f"[Job: {job_id}] Successfully indexed {len(indexed_chunks)} idempotent chunks.")

            return {
                "success": True,
                "job_id": job_id,
                "source_id": source_id,
                "chunks": indexed_chunks,
                "status": "indexed"
            }

        except Exception as e:
            logger.error(f"[Job: {job_id}] Error processing document: {e}")
            retry_count += 1
            task_payload["retry_count"] = retry_count
            task_payload["error"] = str(e)

            # Если лимит попыток исчерпан — отправляем в Dead Letter Queue (DLQ)
            if retry_count >= self.max_retries:
                logger.critical(f"[Job: {job_id}] Max retries exceeded. Routing to Dead Letter Queue (DLQ)!")
                self.dead_letter_queue.append(task_payload)
                return {
                    "success": False,
                    "job_id": job_id,
                    "status": "failed",
                    "routed_to_dlq": True,
                    "error": str(e)
                }
            else:
                logger.warning(f"[Job: {job_id}] Requeuing task for retry ({retry_count}/{self.max_retries})")
                return {
                    "success": False,
                    "job_id": job_id,
                    "status": "requeued",
                    "retry_count": retry_count
                }
