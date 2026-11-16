"""
Production RAG Evaluation & Observability Framework
Метрики оценки качества RAG: Context Precision, Faithfulness, Answer Relevancy.
"""

import json
import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rag-evaluation")

class RagEvaluator:
    @staticmethod
    def evaluate_faithfulness(answer: str, context: str) -> float:
        """
        Метрика Faithfulness: доля утверждений в ответе, подтвержденных контекстом.
        1.0 = нет галлюцинаций, 0.0 = полностью выдуманный ответ.
        """
        import re
        sentences = [s.strip() for s in re.split(r'[.!?;\n]+', answer) if len(s.strip()) > 5]
        if not sentences:
            return 1.0

        supported = 0
        context_lower = context.lower()
        for s in sentences:
            words = [w.lower() for w in re.findall(r'\b\w{3,}\b', s)]
            if not words:
                continue
            matched = sum(1 for w in words if w in context_lower)
            if matched / len(words) >= 0.6:
                supported += 1

        return round(supported / len(sentences), 3)

    @staticmethod
    def evaluate_context_precision(ground_truth_answer: str, retrieved_contexts: List[str]) -> float:
        """
        Метрика Context Precision: насколько релевантные чанки находятся в топе поисковой выдачи.
        """
        import re
        target_words = set(re.findall(r'\b\w{3,}\b', ground_truth_answer.lower()))
        if not target_words or not retrieved_contexts:
            return 0.0

        hits = []
        for i, ctx in enumerate(retrieved_contexts):
            ctx_words = set(re.findall(r'\b\w{3,}\b', ctx.lower()))
            overlap = len(target_words.intersection(ctx_words)) / len(target_words)
            hits.append(1 if overlap >= 0.4 else 0)

        # Mean Average Precision approximation
        accumulated_hits = 0
        precisions = []
        for k, hit in enumerate(hits):
            if hit:
                accumulated_hits += 1
                precisions.append(accumulated_hits / (k + 1))

        return round(sum(precisions) / max(len(precisions), 1), 3) if precisions else 0.0

    @staticmethod
    def evaluate_answer_relevancy(question: str, answer: str) -> float:
        """
        Метрика Answer Relevancy: проверяет, отвечает ли модель именно на поставленный вопрос.
        """
        import re
        q_words = set(re.findall(r'\b\w{3,}\b', question.lower()))
        ans_words = set(re.findall(r'\b\w{3,}\b', answer.lower()))
        if not q_words or not ans_words:
            return 0.0

        overlap = len(q_words.intersection(ans_words))
        score = min(overlap / max(len(q_words) * 0.5, 1), 1.0)
        return round(score, 3)

    def run_benchmark(self, test_dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Запуск бенчмарка по набору тестовых сценариев
        """
        results = []
        total_faithfulness = 0.0
        total_precision = 0.0
        total_relevancy = 0.0

        for test in test_dataset:
            q = test["question"]
            ans = test["answer"]
            ctx = test.get("context", "")
            retrieved = test.get("retrieved_chunks", [ctx])

            f_score = self.evaluate_faithfulness(ans, ctx)
            p_score = self.evaluate_context_precision(test.get("ground_truth", ans), retrieved)
            r_score = self.evaluate_answer_relevancy(q, ans)

            total_faithfulness += f_score
            total_precision += p_score
            total_relevancy += r_score

            results.append({
                "question": q,
                "faithfulness": f_score,
                "context_precision": p_score,
                "answer_relevancy": r_score,
                "passed": (f_score >= 0.8 and r_score >= 0.6)
            })

        n = max(len(test_dataset), 1)
        summary = {
            "total_tests": len(test_dataset),
            "avg_faithfulness": round(total_faithfulness / n, 3),
            "avg_context_precision": round(total_precision / n, 3),
            "avg_answer_relevancy": round(total_relevancy / n, 3),
            "tests": results
        }
        return summary

if __name__ == "__main__":
    evaluator = RagEvaluator()
    sample_tests = [
        {
            "question": "Какая база данных используется для векторов?",
            "answer": "Для хранения векторов используется PostgreSQL 16 с расширением pgvector.",
            "context": "Инфраструктура включает PostgreSQL 16 с расширением pgvector для семантического поиска.",
            "ground_truth": "PostgreSQL 16 с расширением pgvector"
        }
    ]
    report = evaluator.run_benchmark(sample_tests)
    print("Benchmark Report:", json.dumps(report, ensure_ascii=False, indent=2))
