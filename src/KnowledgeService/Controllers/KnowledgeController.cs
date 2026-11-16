using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Microsoft.AspNetCore.Mvc;

namespace KnowledgeService.Controllers
{
    [ApiController]
    [Route("api/v1/[controller]")]
    public class KnowledgeController : ControllerBase
    {
        private static readonly string[] DangerousPatterns = new[]
        {
            "ignore previous instructions", "system override", "developer mode", "jailbreak"
        };

        [HttpGet("search")]
        public IActionResult SearchKnowledgeBase(
            [FromQuery] string query,
            [FromQuery] string? category,
            [FromQuery] int limit = 5,
            [FromHeader(Name = "X-User-Roles")] string? userRolesHeader = "employee",
            [FromHeader(Name = "X-Tenant-Id")] string? tenantId = "default")
        {
            var sw = Stopwatch.StartNew();
            var traceId = Guid.NewGuid().ToString("N");

            // 1. Input Guardrail: Валидация запроса и защита от Prompt Injection
            if (string.IsNullOrWhiteSpace(query))
                return BadRequest(new { error = "Search query cannot be empty", trace_id = traceId });

            var queryLower = query.ToLowerInvariant();
            if (DangerousPatterns.Any(p => queryLower.Contains(p)))
            {
                return BadRequest(new
                {
                    error = "Query blocked by Security Guardrail: unsafe instructions detected",
                    trace_id = traceId,
                    routed_to_fallback = true
                });
            }

            // 2. Document-Level ACL: Разграничение прав по ролям
            var userRoles = (userRolesHeader ?? "employee")
                .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            // 3. Симуляция гибридного поиска (Hybrid Search: Vector + BM25 с RRF)
            var candidates = new List<SearchResultCandidate>
            {
                new SearchResultCandidate
                {
                    ChunkId = Guid.NewGuid(),
                    Question = "Как устроен пайплайн базы знаний?",
                    Answer = "Пайплайн включает прием файлов, парсинг таблиц, семантический чанкинг, генерацию Q&A и Source Verification.",
                    SourceRef = "docs/architecture.md",
                    AllowedRoles = new[] { "employee", "admin" },
                    VectorSim = 0.92,
                    Bm25Score = 0.88,
                    ParentContext = "Раздел 1: Архитектурные принципы. Пайплайн базы знаний включает прием файлов, парсинг таблиц, семантический чанкинг, генерацию Q&A и Source Verification."
                },
                new SearchResultCandidate
                {
                    ChunkId = Guid.NewGuid(),
                    Question = "Финансовый отчет Q3",
                    Answer = "Чистая прибыль составила 12.4 млн руб.",
                    SourceRef = "finance/report_q3.xlsx",
                    AllowedRoles = new[] { "finance", "executive" },
                    VectorSim = 0.85,
                    Bm25Score = 0.90,
                    ParentContext = "Финансовые показатели за 3 квартал."
                }
            };

            // Фильтрация по ACL
            var authorizedResults = candidates
                .Where(c => c.AllowedRoles.Any(r => userRoles.Contains(r)) || userRoles.Contains("admin"))
                .ToList();

            // 4. Переранжирование и оценка уверенности (Confidence Gate)
            var topCandidate = authorizedResults.FirstOrDefault();
            double maxConfidence = topCandidate != null ? 0.94 : 0.0;
            const double confidenceThreshold = 0.60;

            sw.Stop();

            // Маршрутизация на оператора при низкой уверенности
            if (maxConfidence < confidenceThreshold)
            {
                return Ok(new
                {
                    trace_id = traceId,
                    query = query,
                    confidence = maxConfidence,
                    routed_to_fallback = true,
                    fallback_message = "Точный ответ не найден в базе знаний в рамках ваших прав доступа. Запрос перенаправлен оператору.",
                    latency_ms = sw.ElapsedMilliseconds,
                    results = Array.Empty<object>()
                });
            }

            return Ok(new
            {
                trace_id = traceId,
                tenant_id = tenantId,
                query = query,
                confidence = maxConfidence,
                routed_to_fallback = false,
                latency_ms = sw.ElapsedMilliseconds,
                total_found = authorizedResults.Count,
                results = authorizedResults.Select(r => new
                {
                    chunk_id = r.ChunkId,
                    question = r.Question,
                    answer = r.Answer,
                    source_ref = r.SourceRef,
                    parent_context = r.ParentContext, // Parent-Child expansion
                    relevance_score = 0.94,
                    grounded = true
                })
            });
        }
    }

    public class SearchResultCandidate
    {
        public Guid ChunkId { get; set; }
        public string Question { get; set; } = string.Empty;
        public string Answer { get; set; } = string.Empty;
        public string SourceRef { get; set; } = string.Empty;
        public string ParentContext { get; set; } = string.Empty;
        public string[] AllowedRoles { get; set; } = Array.Empty<string>();
        public double VectorSim { get; set; }
        public double Bm25Score { get; set; }
    }
}
