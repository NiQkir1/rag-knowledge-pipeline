-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Jobs: Tracking pipeline stages with retry & trace
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id VARCHAR(64),
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
    status VARCHAR(50) NOT NULL DEFAULT 'queued', 
    -- queued -> parsing -> chunking -> indexing -> enriching -> validating -> completed / failed
    source_type VARCHAR(50) NOT NULL, -- pdf, docx, web, excel
    error_message TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    qa_total INT NOT NULL DEFAULT 0,
    qa_approved INT NOT NULL DEFAULT 0,
    qa_rejected INT NOT NULL DEFAULT 0,
    options JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Sources: Raw source metadata with Versioning & ACL
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
    type VARCHAR(50) NOT NULL, -- pdf, docx, web, excel
    uri TEXT NOT NULL,
    title VARCHAR(255),
    checksum VARCHAR(64) NOT NULL, -- SHA-256 for deduplication
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    allowed_roles TEXT[] DEFAULT ARRAY['employee']::TEXT[], -- Document-level ACL
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Chunks: Semantic Chunks with Parent-Child context & Full-Text Search
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
    parent_id UUID, -- Parent-Child Context Window
    parent_text TEXT, -- Expanded surrounding context for generation
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('russian', text)) STORED, -- BM25 / Full-text
    embedding vector(1024), -- Dense vector representation
    allowed_roles TEXT[] DEFAULT ARRAY['employee']::TEXT[], -- Inherited ACL
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. KB Records: Extracted Question & Answers with Source Verification
CREATE TABLE IF NOT EXISTS kb_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
    question TEXT NOT NULL,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    answer TEXT NOT NULL,
    chunk_ids UUID[] DEFAULT '{}',
    question_search_vector tsvector GENERATED ALWAYS AS (to_tsvector('russian', question || ' ' || answer)) STORED,
    question_embedding vector(1024),
    allowed_roles TEXT[] DEFAULT ARRAY['employee']::TEXT[],
    status VARCHAR(50) NOT NULL DEFAULT 'pending_validation',
    -- pending_validation | auto_approved | pending_review | approved | rejected
    grounding_score FLOAT DEFAULT 0.0,
    confidence_level FLOAT DEFAULT 0.0,
    validation_report JSONB DEFAULT '{}'::jsonb,
    validated_at TIMESTAMPTZ,
    last_verification_run_id UUID,
    prompt_version VARCHAR(50) DEFAULT 'v2.0-guardrails',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Validation Runs: History of Verification Service executions
CREATE TABLE IF NOT EXISTS validation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trigger VARCHAR(50) NOT NULL, -- pipeline, manual, scheduled
    scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    records_total INT NOT NULL DEFAULT 0,
    records_grounded INT NOT NULL DEFAULT 0,
    records_rejected INT NOT NULL DEFAULT 0,
    avg_grounding_score FLOAT DEFAULT 0.0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Audit & Observability Logs: Query traces, latency, and tokens
CREATE TABLE IF NOT EXISTS query_traces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'default',
    user_id VARCHAR(64),
    user_roles TEXT[],
    query TEXT NOT NULL,
    retrieval_mode VARCHAR(50) DEFAULT 'hybrid', -- vector, bm25, hybrid
    retrieved_chunk_ids UUID[],
    rerank_scores FLOAT[],
    response TEXT,
    confidence FLOAT,
    routed_to_fallback BOOLEAN DEFAULT FALSE,
    latency_ms INT,
    tokens_used INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for high-performance Hybrid Search and Filtering
CREATE INDEX IF NOT EXISTS idx_sources_checksum ON sources(checksum);
CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON chunks USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_chunks_roles ON chunks USING GIN(allowed_roles);
CREATE INDEX IF NOT EXISTS idx_kb_records_fts ON kb_records USING GIN(question_search_vector);
CREATE INDEX IF NOT EXISTS idx_kb_records_roles ON kb_records USING GIN(allowed_roles);
CREATE INDEX IF NOT EXISTS idx_kb_records_status ON kb_records(status);
CREATE INDEX IF NOT EXISTS idx_query_traces_trace ON query_traces(trace_id);
