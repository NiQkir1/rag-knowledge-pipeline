using System;
using System.Collections.Generic;
using Microsoft.AspNetCore.Mvc;

namespace KnowledgeService.Controllers
{
    [ApiController]
    [Route("api/v1/[controller]")]
    public class KnowledgeController : ControllerBase
    {
        [HttpGet("search")]
        public IActionResult SearchKnowledgeBase([FromQuery] string query, [FromQuery] string? category, [FromQuery] int limit = 5)
        {
            if (string.IsNullOrWhiteSpace(query))
                return BadRequest(new { error = "Search query cannot be empty" });

            // RAG Search response format
            var results = new List<object>
            {
                new
                {
                    question = "Как запустить краулер резидентов ПВТ?",
                    answer = "Используйте флаги -park-workers 30 -site-workers 50 для многопоточного обхода.",
                    category = "Руководство пользователя",
                    source_ref = "htp-crawler/README.md",
                    grounded = true,
                    grounding_score = 0.96,
                    relevance_score = 0.91
                }
            };

            return Ok(new
            {
                query = query,
                total_found = results.Count,
                results = results
            });
        }
    }
}
