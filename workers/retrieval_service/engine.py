"""
Production Retrieval & Guardrails Engine
1. Input Guardrails (защита от Prompt Injection).
2. Document-Level ACL (разграничение прав доступа по ролям).
3. Hybrid Search: Vector + BM25 (Full-Text) с Reciprocal Rank Fusion (RRF).
4. Reranking (кросс-энкодер переранжирования).
5. Parent-Child Context Expansion.
6. Confidence Gates (безопасный фолбэк при низком скоре).
"""

import math
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("retrieval-engine")

USER_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"(?i)system\s+override",
    r"(?i)tell\s+me\s+your\s+system\s+prompt",
    r"(?i)jailbreak",
    r"(?i)developer\s+mode",
    r"(?i)dan\s+mode"
]

class RetrievalGuardrails:
    @staticmethod
    def validate_user_query(query: str, max_chars: int = 1000) -> Tuple[bool, Optional[str]]:
        """Входной гвардеец: проверка на длину и попытки джейлбрейка"""
        if len(query.strip()) < 3:
            return False, "Запрос слишком короткий."
        if len(query) > max_chars:
            return False, "Превышена максимальная длина запроса."
        
        for pattern in USER_INJECTION_PATTERNS:
            if re.search(pattern, query):
                logger.warning(f"Blocked Prompt Injection attempt: {query}")
                return False, "Обнаружена недопустимая инструкция в запросе."

        return True, None

def reciprocal_rank_fusion(vector_results: List[Dict[str, Any]], bm25_results: List[Dict[str, Any]], k: int = 60) -> List[Dict[str, Any]]:
    """
    RRF (Reciprocal Rank Fusion): объединение векторного и полнотекстового ранжирования
    RRF_score = 1 / (k + rank_vector) + 1 / (k + rank_bm25)
    """
    scores: Dict[str, float] = {}
    items: Dict[str, Dict[str, Any]] = {}

    for rank, item in enumerate(vector_results):
        item_id = item["id"]
        scores[item_id] = scores.get(item_id, 0.0) + (1.0 / (k + rank + 1))
        items[item_id] = item

    for rank, item in enumerate(bm25_results):
        item_id = item["id"]
        scores[item_id] = scores.get(item_id, 0.0) + (1.0 / (k + rank + 1))
        if item_id not in items:
            items[item_id] = item

    fused = []
    for item_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        entry = dict(items[item_id])
        entry["rrf_score"] = round(score, 5)
        fused.append(entry)

    return fused

def rerank_candidates(query: str, candidates: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
    """
    Cross-Encoder Reranker: переоценка релевантности найденных чанков под запрос.
    (В продакшене: HuggingFace cross-encoder/ms-marco-MiniLM-L-6-v2 или bge-reranker)
    """
    query_words = set(re.findall(r'\b\w{3,}\b', query.lower()))
    
    for c in candidates:
        text = c.get("text", "").lower()
        chunk_words = set(re.findall(r'\b\w{3,}\b', text))
        
        # Лексическое совпадение + исходный векторный/RRF вес
        overlap = len(query_words.intersection(chunk_words)) / max(len(query_words), 1)
        base_score = c.get("rrf_score", c.get("score", 0.5))
        
        rerank_score = (base_score * 0.4) + (overlap * 0.6)
        c["final_relevance"] = round(rerank_score, 4)

    ranked = sorted(candidates, key=lambda x: x["final_relevance"], reverse=True)
    return ranked[:top_n]

class ProductionRetriever:
    def __init__(self, confidence_threshold: float = 0.55):
        self.confidence_threshold = confidence_threshold

    def search_and_retrieve(
        self,
        query: str,
        user_roles: List[str],
        db_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Полный производственный цикл поиска с ACL, RRF, Rerank и Confidence Gate
        """
        # 1. Входная валидация (Guardrail)
        is_valid, error = RetrievalGuardrails.validate_user_query(query)
        if not is_valid:
            return {
                "success": False,
                "error": error,
                "routed_to_fallback": True,
                "reason": "guardrail_rejected"
            }

        # 2. Фильтрация по правам доступа (Document-Level ACL)
        allowed_chunks = []
        for chunk in db_chunks:
            chunk_roles = chunk.get("allowed_roles", ["employee"])
            if any(role in chunk_roles for role in user_roles) or "admin" in user_roles:
                allowed_chunks.append(chunk)

        if not allowed_chunks:
            return {
                "success": False,
                "message": "Документы по вашему уровню доступа не найдены.",
                "routed_to_fallback": False,
                "results": []
            }

        # 3. Симуляция гибридного поиска (Vector + BM25)
        # В реальной БД: SELECT ... ORDER BY embedding <=> query_emb, и ts_rank_cd(search_vector, query)
        vector_res = sorted(allowed_chunks, key=lambda x: x.get("vector_sim", 0.0), reverse=True)[:10]
        bm25_res = sorted(allowed_chunks, key=lambda x: x.get("bm25_score", 0.0), reverse=True)[:10]

        # 4. Объединение через Reciprocal Rank Fusion (RRF)
        fused = reciprocal_rank_fusion(vector_res, bm25_res)

        # 5. Переранжирование (Cross-Encoder Rerank)
        top_reranked = rerank_candidates(query, fused, top_n=3)

        # 6. Confidence Gate (Маршрутизация при низкой уверенности)
        max_confidence = top_reranked[0]["final_relevance"] if top_reranked else 0.0
        
        if max_confidence < self.confidence_threshold:
            logger.info(f"Query confidence {max_confidence} < threshold {self.confidence_threshold}. Routing to operator fallback.")
            return {
                "success": True,
                "query": query,
                "confidence": max_confidence,
                "routed_to_fallback": True,
                "fallback_message": "По вашему запросу нет точной информации в базе знаний. Запрос передан оператору поддержки.",
                "results": []
            }

        # 7. Parent-Child Context Expansion
        # Подтягиваем parent_text (окружающий раздел), чтобы LLM видела полный контекст
        expanded_results = []
        for c in top_reranked:
            expanded_results.append({
                "chunk_id": c["id"],
                "text": c["text"],
                "parent_context": c.get("parent_text", c["text"]), # Расширенный контекст
                "relevance_score": c["final_relevance"],
                "source_ref": c.get("source_ref", "документ")
            })

        return {
            "success": True,
            "query": query,
            "confidence": max_confidence,
            "routed_to_fallback": False,
            "results": expanded_results
        }
