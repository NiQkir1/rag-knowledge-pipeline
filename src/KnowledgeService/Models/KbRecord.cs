using System;
using System.Text.Json;

namespace KnowledgeService.Models
{
    public class KbRecord
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public Guid SourceId { get; set; }
        public string Question { get; set; } = string.Empty;
        public string? Category { get; set; }
        public string? Subcategory { get; set; }
        public string Answer { get; set; } = string.Empty;
        public Guid[] ChunkIds { get; set; } = Array.Empty<Guid>();
        public float[]? QuestionEmbedding { get; set; }
        public string Status { get; set; } = "pending_validation"; 
        // pending_validation | auto_approved | pending_review | approved | rejected
        public double GroundingScore { get; set; } = 0.0;
        public JsonDocument? ValidationReport { get; set; }
        public DateTime? ValidatedAt { get; set; }
        public Guid? LastVerificationRunId { get; set; }
        public string PromptVersion { get; set; } = "v1.0";
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    }
}
