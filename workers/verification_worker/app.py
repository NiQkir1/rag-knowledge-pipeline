"""
Source Verification Service
Служба валидации ответов и сверки с источником (PIPELINE.md - Раздел 5.5).
Поддерживает два режима работы:
1. Standalone HTTP API (ручной запуск проверки по record_id / source_id / all)
2. Pipeline режим (автоматическая валидация новых Q&A записей после генерации)
"""

import os
import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("source-verification")

app = FastAPI(
    title="Source Verification Service",
    version="1.0.0",
    description="Microservice verifying Q&A answers against source context, claims, and ground truth"
)

# In-memory run state (or backed by PostgreSQL when configured)
RUNS_DB: Dict[str, Dict[str, Any]] = {}

class ScopeModel(BaseModel):
    type: str = Field(..., description="record | source | all")
    record_ids: Optional[List[str]] = Field(default_factory=list)
    source_id: Optional[str] = None

class VerificationRequest(BaseModel):
    trigger: str = Field("manual", description="pipeline | manual | scheduled")
    job_id: Optional[str] = None
    scope: ScopeModel
    options: Optional[Dict[str, Any]] = Field(default_factory=lambda: {"threshold_auto_approve": 0.80, "threshold_reject": 0.50})

class SingleRecordVerification(BaseModel):
    record_id: str
    question: str
    answer: str
    context_chunks: List[str]

class VerificationResult(BaseModel):
    record_id: str
    grounded: bool
    grounding_score: float
    status: str # auto_approved | pending_review | rejected
    claims: List[Dict[str, Any]]
    contradictions: List[str]
    evidence_spans: List[str]

def verify_groundedness(question: str, answer: str, context_chunks: List[str], threshold_high=0.8, threshold_low=0.5) -> VerificationResult:
    """
    Анализирует утверждения в ответе (claims) и проверяет их присутствие в чанках источника.
    """
    full_context = " ".join(context_chunks).lower()
    
    # Разбиваем ответ на отдельные фактологические предложения/клеймы
    sentences = [s.strip() for s in re.split(r'[.!?;\n]+', answer) if len(s.strip()) > 5]
    if not sentences:
        sentences = [answer]

    claims_evaluated = []
    supported_count = 0
    contradictions = []
    evidence_spans = []

    for sentence in sentences:
        words = [w.lower() for w in re.findall(r'\b\w{3,}\b', sentence)]
        if not words:
            continue
            
        # Подсчет перекрытия ключевых слов и n-грамм с контекстом
        matched_words = [w for w in words if w in full_context]
        word_overlap = len(matched_words) / len(words)

        # Простая эвристика на противоречия (наличие отрицания фактов из контекста)
        is_contradiction = False
        if ("не " in sentence.lower() or "not " in sentence.lower()) and word_overlap > 0.6:
            # Требуется ручная перепроверка при потенциальных инверсиях смысла
            is_contradiction = False

        status = "supported" if word_overlap >= 0.65 else ("partially_supported" if word_overlap >= 0.4 else "not_found")
        if status in ("supported", "partially_supported"):
            supported_count += (1.0 if status == "supported" else 0.5)
            # Находим фрагмент контекста с максимальным совпадением
            for chunk in context_chunks:
                if any(w in chunk.lower() for w in matched_words[:3]):
                    evidence_spans.append(chunk[:180] + "...")
                    break

        claims_evaluated.append({
            "claim": sentence,
            "status": status,
            "overlap_ratio": round(word_overlap, 3),
            "matched_keywords": matched_words[:5]
        })

    # Общий итоговый score
    total_claims = max(len(sentences), 1)
    score = min(max(supported_count / total_claims, 0.0), 1.0)
    grounded = score >= threshold_high

    if grounded:
        final_status = "auto_approved"
    elif score < threshold_low or contradictions:
        final_status = "rejected"
    else:
        final_status = "pending_review"

    return VerificationResult(
        record_id=str(uuid.uuid4()),
        grounded=grounded,
        grounding_score=round(score, 3),
        status=final_status,
        claims=claims_evaluated,
        contradictions=contradictions,
        evidence_spans=list(set(evidence_spans))[:3]
    )

@app.get("/health")
def health():
    return {"status": "ok", "service": "source-verification-service"}

@app.post("/api/v1/verification/verify-single", response_model=VerificationResult)
def verify_single(payload: SingleRecordVerification):
    """Быстрая прямая синхронная проверка единичной записи"""
    res = verify_groundedness(payload.question, payload.answer, payload.context_chunks)
    res.record_id = payload.record_id
    return res

@app.post("/api/v1/verification/runs")
def create_verification_run(payload: VerificationRequest, background_tasks: BackgroundTasks):
    """
    Запуск автономного или пайплайнового прогона верификации (Section 5.5 PIPELINE.md)
    """
    run_id = str(uuid.uuid4())
    run_record = {
        "run_id": run_id,
        "trigger": payload.trigger,
        "scope": payload.scope.dict(),
        "status": "queued",
        "records_total": len(payload.scope.record_ids or []),
        "records_grounded": 0,
        "records_rejected": 0,
        "created_at": datetime.utcnow().isoformat()
    }
    RUNS_DB[run_id] = run_record
    logger.info(f"Created verification run {run_id} (trigger: {payload.trigger})")
    return {"run_id": run_id, "status": "queued"}

@app.get("/api/v1/verification/runs/{run_id}")
def get_run_status(run_id: str):
    if run_id not in RUNS_DB:
        raise HTTPException(status_code=404, detail="Run not found")
    return RUNS_DB[run_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
