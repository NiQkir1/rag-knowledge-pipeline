using System;
using System.Collections.Generic;
using Microsoft.AspNetCore.Mvc;
using KnowledgeService.Models;

namespace KnowledgeService.Controllers
{
    [ApiController]
    [Route("api/v1/[controller]")]
    public class ReviewController : ControllerBase
    {
        [HttpGet("pending")]
        public IActionResult GetPendingReviews([FromQuery] string? status)
        {
            // Возвращает список записей, требующих модерации или автоодобренных
            var sampleRecords = new List<KbRecord>
            {
                new KbRecord
                {
                    Id = Guid.NewGuid(),
                    Question = "Каковы правила размещения 4-палубного корабля?",
                    Category = "Игровые правила",
                    Subcategory = "Морской бой",
                    Answer = "Корабль занимает 4 клетки по прямой линии и не может соприкасаться с другими кораблями.",
                    Status = "auto_approved",
                    GroundingScore = 0.94,
                    PromptVersion = "v1.0"
                }
            };

            return Ok(sampleRecords);
        }

        [HttpPost("records/{recordId:guid}/approve")]
        public IActionResult ApproveRecord(Guid recordId)
        {
            return Ok(new { record_id = recordId, status = "approved", updated_at = DateTime.UtcNow });
        }

        [HttpPost("records/{recordId:guid}/reject")]
        public IActionResult RejectRecord(Guid recordId, [FromBody] RejectRequest? request)
        {
            return Ok(new
            {
                record_id = recordId,
                status = "rejected",
                reason = request?.Reason ?? "Manual rejection by operator",
                updated_at = DateTime.UtcNow
            });
        }
    }

    public class RejectRequest
    {
        public string? Reason { get; set; }
    }
}
