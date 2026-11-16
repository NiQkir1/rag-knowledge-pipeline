# Enterprise Production Event-Driven RAG Knowledge Pipeline

[![.NET 9](https://img.shields.io/badge/.NET-9.0-purple.svg)](https://dotnet.microsoft.com/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL 16 + pgvector](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Redpanda](https://img.shields.io/badge/Kafka%20Broker-Redpanda-red.svg)](https://redpanda.com/)
[![MinIO](https://img.shields.io/badge/Storage-MinIO%20S3-c72c48.svg)](https://min.io/)
[![Docker Compose](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED.svg)](https://docs.docker.com/compose/)

Отказоустойчивый промышленный RAG-пайплайн на базе **распределенной событийной архитектуры (Event-Driven Architecture)** с разделением на два независимых контура:
1. **Асинхронный контур инжеста (ETL Pipeline):** очередь задач с DLQ, детерминированные `chunk_id` (UUID v5) для 100% идемпотентности, семантический чанкинг без разрыва таблиц и дедупликация по SHA-256.
2. **Синхронный контур ретривала (Retrieval & Generation):** гибридный поиск (BM25 + Dense Vector), слияние кандидатов через Reciprocal Rank Fusion (RRF), Cross-Encoder реранжирование (топ-3..5 для устранения эффекта *Lost in the Middle*), Circuit Breaker и трассировка в формате Langfuse.

---

## 🏛 Общая схема архитектуры (High-Level Architecture)

```
[ Источники данных (PDF, Web, Excel) ] ──► [ Message Broker (Redpanda / Kafka / RabbitMQ) ]
                                                   │
                                                   ▼
                                 [ Ingestion Workers (Event-Driven ETL) ]
                                 ├── 1. Дедупликация (SHA-256) & Защита от Injection
                                 ├── 2. Semantic Chunking (без разрыва таблиц и кода)
                                 ├── 3. Детерминированные chunk_id (UUID v5, Idempotent)
                                 ├── 4. Dead Letter Queue (DLQ) при исчерпании retry
                                 └── 5. Запись в Vector DB (pgvector) + S3 (MinIO)
                                                   │
                                                   ▼
[ Клиент / API Gateway ] ──────────────► [ Retrieval & Generation Service ]
                                         ├── 1. Input Guardrails (санитайзинг запроса)
                                         ├── 2. Document-Level ACL (фильтрация по ролям)
                                         ├── 3. Hybrid Search: BM25 + Vector (топ-50)
                                         ├── 4. RRF (Reciprocal Rank Fusion)
                                         ├── 5. Cross-Encoder Reranking (топ-3..5)
                                         ├── 6. Circuit Breaker (защита от сбоев LLM)
                                         └── 7. Langfuse Tracing (латентность, спаны, токены)
```

---

## ⚙️ Компоненты отказоустойчивого конвейера

### А. Асинхронный инжест (Ingestion & ETL Pipeline)

Обработка тяжелых документов никогда не блокирует HTTP-потоки клиентов:
* **Брокер сообщений и Dead Letter Queue (DLQ):** Документы публикуются в топик `ingestion.requested`. При недоступности сервисов эмбеддингов задача повторяется до 3 раз с экспоненциальным backoff. При фатальном сбое сообщение автоматически маршрутизируется в `ingestion.dlq` для аудита без падения системы.
* **Детерминированные `chunk_id` (100% Idempotency):**
  Каждый чанк получает детерминированный идентификатор через `UUID v5`:
  $$\text{chunk\_id} = \text{UUIDv5}(\text{NAMESPACE}, \text{source\_id} + \text{chunk\_index} + \text{content\_hash})$$
  Повторный запуск инжеста того же документа выполняет корректный **UPSERT** в векторной базе вместо раздувания дубликатов.
* **Машина состояний метаданных:** Отслеживание статусов: `pending -> processing -> indexed -> failed`.

### Б. Ретривал с гибридным поиском (Hybrid Search)

Устраняет «слепоту» векторного поиска на точных артикулах, ГОСТах и серийных номерах:
1. **Dense Retrieval (Vector Search):** поиск по смыслу через `pgvector` (косинусное расстояние по эмбеддингам).
2. **Sparse Retrieval (BM25 / Full-Text):** точный поиск по лексическим совпадениям через PostgreSQL `tsvector` с русским словарем.
3. **Reciprocal Rank Fusion (RRF):** Объединение двух списков кандидатов:
   $$RRF(d) = \sum_{m \in \{vec, bm25\}} \frac{1}{60 + rank_m(d)}$$
   Формируется сбалансированный пул из топ-50 кандидатов.

### В. Переранжирование (Cross-Encoder Reranking)

Отправка всех 50 чанков в LLM приводит к эффекту **Lost in the Middle** (потеря фактов в середине контекста) и перерасходу токенов.
* Кросс-энкодер одновременно анализирует пару `[Запрос + Чанк]`.
* Пул сужается с топ-50 до **топ-3..5 абсолютно релевантных чанков**.
* В модель передается расширенное окно `parent_text` (Parent-Child Context Expansion).

---

## 🛡 Отказоустойчивость и безопасность (Resilience & Security)

1. **Circuit Breakers на внешние API (`workers/common/circuit_breaker.py`):**
   * Предотвращает каскадный сбой системы при таймаутах или ошибках 5xx у внешних LLM-провайдеров.
   * Состояния: `CLOSED` $\to$ `OPEN` $\to$ `HALF_OPEN`.
   * При размыкании контура трафик мгновенно переключается на локальную резервную модель (Ollama) без ожидания таймаутов.
2. **Document-Level ACL (Контроль доступа):**
   * Разграничение прав по ролям (`employee`, `management`, `finance`, `admin`) на уровне векторной выборки.
   * Сотрудник без прав никогда не увидит финансовые отчеты в поисковой выдаче.
3. **Защита от Prompt Injection:**
   * *Входные Guardrails:* фильтрация джейлбрейков (`ignore previous instructions`, `system override`).
   * *Санитайзинг базы знаний:* выявление и экранирование Indirect Prompt Injection внутри загружаемых PDF/Word файлов.
4. **Наблюдаемость (Langfuse / OpenTelemetry Tracing):**
   * Сквозное логирование `trace_id`, латентности по спанам (`guardrail`, `hybrid_search`, `rerank`, `llm`), подсчет токенов и аудит фолбэков.

---

## 🚀 Быстрый запуск

### 1. Поднятие инфраструктуры

```bash
docker compose up -d
```

### 2. Тестирование асинхронного идемпотентного инжеста (ETL)

```bash
python workers/processing_worker/async_ingest_worker.py
```

### 3. Тестирование Hybrid Search + Rerank + Langfuse Tracing

```bash
python workers/retrieval_service/engine.py
```

### 4. Тестирование Circuit Breaker

```bash
python workers/common/circuit_breaker.py
```

### 5. Запуск C# Ingestion Portal (.NET 9)

```bash
cd src/KnowledgeService
dotnet run
```

---

## 📄 Лицензия

MIT License.
