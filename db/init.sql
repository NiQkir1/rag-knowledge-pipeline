-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Jobs: Tracking pipeline stages
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(50) NOT NULL DEFAULT 'queued', 
    -- queued -> parsing -> chunking -> indexing -> enriching -> validating -> completed / failed
    source_type VARCHAR(50) NOT NULL, -- file, url, text
    error_message TEXT,
    qa_total INT NOT NULL DEFAULT 0,
    qa_approved INT NOT NULL DEFAULT 0,
    qa_rejected INT NOT NULL DEFAULT 0,
    options JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Sources: Raw source metadata
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- pdf, docx, web, excel
    uri TEXT NOT NULL,
    title VARCHAR(255),
    checksum VARCHAR(64),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Chunks: Text chunks and embeddings for search & grounding
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1024), -- multilingual-e5-large / bge dimension
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. KB Records: Extracted Question & Answers with Source Verification
CREATE TABLE IF NOT EXISTS kb_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    answer TEXT NOT NULL,
    chunk_ids UUID[] DEFAULT '{}',
    question_embedding vector(1024),
    status VARCHAR(50) NOT NULL DEFAULT 'pending_validation',
    -- pending_validation | auto_approved | pending_review | approved | rejected
    grounding_score FLOAT DEFAULT 0.0,
    validation_report JSONB DEFAULT '{}'::jsonb,
    validated_at TIMESTAMPTZ,
    last_verification_run_id UUID,
    prompt_version VARCHAR(50) DEFAULT 'v1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Validation Runs: History of Verification Service executions
CREATE TABLE IF NOT EXISTS validation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trigger VARCHAR(50) NOT NULL, -- pipeline, manual, scheduled
    scope JSONB NOT NULL DEFAULT '{}'::jsonb, -- {type: "record | source | all", ids: [...]}
    status VARCHAR(50) NOT NULL DEFAULT 'queued', -- queued, running, completed, failed
    records_total INT NOT NULL DEFAULT 0,
    records_grounded INT NOT NULL DEFAULT 0,
    records_rejected INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Validation Run Items: Detailed mapping between Run and KB Record
CREATE TABLE IF NOT EXISTS validation_run_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID REFERENCES validation_runs(id) ON DELETE CASCADE,
    record_id UUID REFERENCES kb_records(id) ON DELETE CASCADE,
    grounded BOOLEAN NOT NULL DEFAULT FALSE,
    score FLOAT DEFAULT 0.0,
    report JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_sources_job_id ON sources(job_id);
CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_kb_records_source_id ON kb_records(source_id);
CREATE INDEX IF NOT EXISTS idx_kb_records_status ON kb_records(status);
CREATE INDEX IF NOT EXISTS idx_validation_runs_status ON validation_runs(status);
